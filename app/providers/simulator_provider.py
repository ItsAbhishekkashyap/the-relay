"""Client adapter for the local custom stand-in model simulator."""

import json
import time
from typing import AsyncIterator, Optional, Dict, Any

import httpx
from httpx import ASGITransport

from app.providers.base import (
    BaseModelProvider,
    ModelProviderError,
    RateLimitError,
    AuthenticationError,
    TimeoutError,
    ProviderServerError,
    ConnectionError,
    InvalidResponseError,
)
from app.providers.schemas import (
    GenerationRequest,
    GenerationResponse,
    StreamChunk,
    TokenUsage,
)


class SimulatorProvider(BaseModelProvider):
    """Adapter to communicate with the local simulator FastAPI service."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8001",
        default_model: str = "simulator/mock-model-v1",
        app: Optional[Any] = None,
        client: Optional[httpx.AsyncClient] = None,
        timeout: float = 30.0,
    ):
        """Initialize the simulator adapter.

        Args:
            base_url: HTTP URL of the running simulator service.
            default_model: Name of the mock model.
            app: Optional FastAPI app instance. If provided, connects via ASGITransport (in-memory, no socket needed).
            client: Optional pre-configured httpx.AsyncClient.
            timeout: Request timeout in seconds.
        """
        self._base_url = base_url.rstrip("/")
        self._default_model = default_model
        self._timeout = timeout

        if client is not None:
            self._client = client
            self._owns_client = False
        elif app is not None:
            transport = ASGITransport(app=app)
            self._client = httpx.AsyncClient(transport=transport, base_url=self._base_url)
            self._owns_client = True
        else:
            self._client = httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout)
            self._owns_client = True

    @property
    def provider_name(self) -> str:
        return "simulator"

    @property
    def model_name(self) -> str:
        return self._default_model

    async def aclose(self) -> None:
        """Close client session if owned."""
        if self._owns_client and self._client is not None:
            await self._client.aclose()

    def _map_http_error(self, response: httpx.Response) -> ModelProviderError:
        """Translate HTTP status codes and payloads from simulator into ModelProviderError."""
        status = response.status_code
        retry_after: Optional[float] = None
        message = f"Simulator HTTP {status}"
        details: Dict[str, Any] = {}

        try:
            body = response.json()
            if isinstance(body, dict):
                details = body
                err_dict = body.get("detail", {}).get("error", {}) if isinstance(body.get("detail"), dict) else {}
                if isinstance(err_dict, dict):
                    message = err_dict.get("message", message)
                    retry_after = err_dict.get("retry_after")
                elif "detail" in body:
                    message = str(body["detail"])
        except Exception:
            message = response.text or message

        if status == 429:
            return RateLimitError(
                message=message,
                status_code=429,
                provider_name=self.provider_name,
                details=details,
                retry_after=retry_after,
            )
        elif status in (401, 403):
            return AuthenticationError(
                message=message,
                status_code=status,
                provider_name=self.provider_name,
                details=details,
            )
        elif status in (408, 504):
            return TimeoutError(
                message=message,
                status_code=status,
                provider_name=self.provider_name,
                details=details,
            )
        elif status >= 500:
            return ProviderServerError(
                message=message,
                status_code=status,
                provider_name=self.provider_name,
                details=details,
            )
        else:
            return InvalidResponseError(
                message=message,
                status_code=status,
                provider_name=self.provider_name,
                details=details,
            )

    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Send chat completion request to the simulator."""
        payload = request.model_dump()
        payload["stream"] = False
        if not payload.get("model"):
            payload["model"] = self._default_model

        t0 = time.perf_counter()
        try:
            resp = await self._client.post(
                f"{self._base_url}/v1/chat/completions",
                json=payload,
                timeout=self._timeout,
            )
            if resp.is_error:
                raise self._map_http_error(resp)

            data = resp.json()
            total_latency = time.perf_counter() - t0

            # Parse token usage
            usage: Optional[TokenUsage] = None
            if "token_usage" in data and data["token_usage"]:
                usage = TokenUsage(**data["token_usage"])

            return GenerationResponse(
                request_id=data.get("request_id", request.request_id),
                response_text=data.get("response_text", ""),
                provider_name=self.provider_name,
                model_name=data.get("model_name", self._default_model),
                time_to_first_token=data.get("time_to_first_token", None),
                total_latency=total_latency,
                token_usage=usage,
                http_status=resp.status_code,
            )

        except httpx.ConnectError as e:
            raise ConnectionError(
                message=f"Cannot connect to simulator at {self._base_url}: {str(e)}",
                provider_name=self.provider_name,
            ) from e
        except httpx.TimeoutException as e:
            raise TimeoutError(
                message=f"Request to simulator timed out after {self._timeout}s: {str(e)}",
                status_code=408,
                provider_name=self.provider_name,
            ) from e
        except ModelProviderError:
            raise
        except Exception as e:
            raise ProviderServerError(
                message=f"Unexpected error communicating with simulator: {str(e)}",
                provider_name=self.provider_name,
            ) from e

    async def stream(self, request: GenerationRequest) -> AsyncIterator[StreamChunk]:
        """Stream chunks from the simulator."""
        payload = request.model_dump()
        payload["stream"] = True
        if not payload.get("model"):
            payload["model"] = self._default_model

        t0 = time.perf_counter()

        try:
            async with self._client.stream(
                "POST",
                f"{self._base_url}/v1/chat/completions",
                json=payload,
                timeout=self._timeout,
            ) as response:
                if response.is_error:
                    # Need to read content for error message
                    await response.aread()
                    raise self._map_http_error(response)

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data:"):
                        content = line[len("data:") :].strip()
                        if content == "[DONE]":
                            break

                        try:
                            item = json.loads(content)
                        except json.JSONDecodeError:
                            continue

                        usage: Optional[TokenUsage] = None
                        if "token_usage" in item and item["token_usage"]:
                            usage = TokenUsage(**item["token_usage"])

                        yield StreamChunk(
                            request_id=item.get("request_id", request.request_id),
                            chunk_index=item.get("chunk_index", 0),
                            delta_text=item.get("delta_text", ""),
                            is_final=item.get("is_final", False),
                            time_offset=item.get("time_offset", time.perf_counter() - t0),
                            token_usage=usage,
                        )

        except httpx.ConnectError as e:
            raise ConnectionError(
                message=f"Cannot connect to simulator stream at {self._base_url}: {str(e)}",
                provider_name=self.provider_name,
            ) from e
        except httpx.TimeoutException as e:
            raise TimeoutError(
                message=f"Stream from simulator timed out after {self._timeout}s: {str(e)}",
                status_code=408,
                provider_name=self.provider_name,
            ) from e
        except ModelProviderError:
            raise
        except Exception as e:
            raise ProviderServerError(
                message=f"Unexpected error in simulator stream: {str(e)}",
                provider_name=self.provider_name,
            ) from e

