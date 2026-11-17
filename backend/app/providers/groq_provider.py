"""Real Groq model service provider adapter using the official Groq Python SDK."""

import os
import re
import time
from typing import AsyncIterator, Optional, Dict, Any

from dotenv import load_dotenv

import groq
from groq import AsyncGroq

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

# Load environment variables once at module import
load_dotenv()

# Regex to sanitize API keys from error messages or logs
API_KEY_REGEX = re.compile(r"gsk_[a-zA-Z0-9]{10,}")


def _sanitize(text: str) -> str:
    """Ensure no API keys are ever leaked in error messages or logs."""
    if not text:
        return ""
    return API_KEY_REGEX.sub("[REDACTED_API_KEY]", str(text))


class GroqProvider(BaseModelProvider):
    """Adapter for Groq Cloud API chat completion models."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: Optional[str] = None,
        client: Optional[AsyncGroq] = None,
    ):
        """Initialize the Groq provider.

        Args:
            api_key: Optional Groq API key. If omitted, loaded from GROQ_API_KEY env.
            default_model: Optional default model name. If omitted, loaded from GROQ_MODEL env.
            client: Optional pre-configured AsyncGroq client (useful for unit tests / mocking).
        """
        self._api_key = api_key or os.getenv("GROQ_API_KEY")
        self._default_model = default_model or os.getenv("GROQ_MODEL") or "openai/gpt-oss-120b"

        if client is not None:
            self._client = client
        elif self._api_key:
            self._client = AsyncGroq(api_key=self._api_key)
        else:
            self._client = None

    @property
    def provider_name(self) -> str:
        return "groq"

    @property
    def model_name(self) -> str:
        return self._default_model

    def _ensure_authenticated(self) -> None:
        """Verify that credentials are present before attempting a call."""
        if self._client is None or not self._api_key:
            raise AuthenticationError(
                message="GROQ_API_KEY is not configured in environment or passed to provider.",
                status_code=401,
                provider_name=self.provider_name,
            )

    def _map_groq_error(self, e: Exception) -> ModelProviderError:
        """Translate Groq SDK exceptions into standard ModelProviderError subclasses."""
        if isinstance(e, ModelProviderError):
            return e

        safe_msg = _sanitize(str(e))

        if isinstance(e, groq.RateLimitError):
            retry_after: Optional[float] = None
            if hasattr(e, "response") and e.response is not None:
                try:
                    val = e.response.headers.get("retry-after")
                    if val is not None:
                        retry_after = float(val)
                except Exception:
                    pass
            return RateLimitError(
                message=safe_msg,
                status_code=getattr(e, "status_code", 429) or 429,
                provider_name=self.provider_name,
                details={"type": type(e).__name__},
                retry_after=retry_after,
            )

        if isinstance(e, groq.AuthenticationError):
            return AuthenticationError(
                message=safe_msg,
                status_code=getattr(e, "status_code", 401) or 401,
                provider_name=self.provider_name,
                details={"type": type(e).__name__},
            )

        if isinstance(e, groq.APITimeoutError):
            return TimeoutError(
                message=safe_msg,
                status_code=408,
                provider_name=self.provider_name,
                details={"type": type(e).__name__},
            )

        if isinstance(e, groq.APIConnectionError):
            return ConnectionError(
                message=safe_msg,
                status_code=None,
                provider_name=self.provider_name,
                details={"type": type(e).__name__},
            )

        if isinstance(e, groq.InternalServerError):
            return ProviderServerError(
                message=safe_msg,
                status_code=getattr(e, "status_code", 500) or 500,
                provider_name=self.provider_name,
                details={"type": type(e).__name__},
            )

        if isinstance(e, (groq.BadRequestError, groq.NotFoundError)):
            return InvalidResponseError(
                message=safe_msg,
                status_code=getattr(e, "status_code", 400) or 400,
                provider_name=self.provider_name,
                details={"type": type(e).__name__},
            )

        if isinstance(e, groq.APIStatusError):
            status = getattr(e, "status_code", 500) or 500
            if status == 429:
                return RateLimitError(safe_msg, status_code=status, provider_name=self.provider_name)
            elif status in (401, 403):
                return AuthenticationError(safe_msg, status_code=status, provider_name=self.provider_name)
            elif status >= 500:
                return ProviderServerError(safe_msg, status_code=status, provider_name=self.provider_name)
            else:
                return InvalidResponseError(safe_msg, status_code=status, provider_name=self.provider_name)

        return ProviderServerError(
            message=f"Unexpected error: {safe_msg}",
            status_code=500,
            provider_name=self.provider_name,
            details={"type": type(e).__name__},
        )

    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Execute a standard chat completion call."""
        self._ensure_authenticated()

        target_model = request.model or self._default_model
        messages_payload = [{"role": m.role, "content": m.content} for m in request.messages]

        t0 = time.perf_counter()
        try:
            kwargs: Dict[str, Any] = {
                "model": target_model,
                "messages": messages_payload,
            }
            if request.max_tokens is not None:
                kwargs["max_tokens"] = request.max_tokens
            if request.temperature is not None:
                kwargs["temperature"] = request.temperature

            completion = await self._client.chat.completions.create(**kwargs)
            latency = time.perf_counter() - t0

            response_text = ""
            if completion.choices and len(completion.choices) > 0:
                choice = completion.choices[0]
                if choice.message and choice.message.content:
                    response_text = choice.message.content

            usage: Optional[TokenUsage] = None
            if hasattr(completion, "usage") and completion.usage is not None:
                usage = TokenUsage(
                    prompt_tokens=getattr(completion.usage, "prompt_tokens", 0) or 0,
                    completion_tokens=getattr(completion.usage, "completion_tokens", 0) or 0,
                    total_tokens=getattr(completion.usage, "total_tokens", 0) or 0,
                    is_estimated=False,
                )

            return GenerationResponse(
                request_id=request.request_id,
                response_text=response_text,
                provider_name=self.provider_name,
                model_name=target_model,
                time_to_first_token=None,  # Non-streaming completions cannot measure TTFT
                total_latency=latency,
                token_usage=usage,
                http_status=200,
            )
        except Exception as e:
            raise self._map_groq_error(e) from e

    async def stream(self, request: GenerationRequest) -> AsyncIterator[StreamChunk]:
        """Stream chunks from Groq API chat completion."""
        self._ensure_authenticated()

        target_model = request.model or self._default_model
        messages_payload = [{"role": m.role, "content": m.content} for m in request.messages]

        t0 = time.perf_counter()
        first_token_time: Optional[float] = None
        chunk_idx = 0
        captured_usage: Optional[TokenUsage] = None

        try:
            kwargs: Dict[str, Any] = {
                "model": target_model,
                "messages": messages_payload,
                "stream": True,
                "extra_body": {"stream_options": {"include_usage": True}},
            }
            if request.max_tokens is not None:
                kwargs["max_tokens"] = request.max_tokens
            if request.temperature is not None:
                kwargs["temperature"] = request.temperature

            stream_obj = await self._client.chat.completions.create(**kwargs)

            async for chunk in stream_obj:
                now = time.perf_counter()
                offset = now - t0

                # Capture usage whenever present (including trailing usage-only chunks)
                if hasattr(chunk, "usage") and chunk.usage is not None:
                    captured_usage = TokenUsage(
                        prompt_tokens=getattr(chunk.usage, "prompt_tokens", 0) or 0,
                        completion_tokens=getattr(chunk.usage, "completion_tokens", 0) or 0,
                        total_tokens=getattr(chunk.usage, "total_tokens", 0) or 0,
                        is_estimated=False,
                    )

                delta_text = ""
                if chunk.choices and len(chunk.choices) > 0:
                    choice = chunk.choices[0]
                    delta = getattr(choice, "delta", None)
                    if delta and getattr(delta, "content", None):
                        delta_text = delta.content

                if delta_text:
                    if first_token_time is None:
                        first_token_time = offset

                    yield StreamChunk(
                        request_id=request.request_id,
                        chunk_index=chunk_idx,
                        delta_text=delta_text,
                        is_final=False,
                        time_offset=offset,
                        token_usage=None,
                    )
                    chunk_idx += 1

            # Stream consumption complete: emit terminating final chunk with collected usage
            yield StreamChunk(
                request_id=request.request_id,
                chunk_index=chunk_idx,
                delta_text="",
                is_final=True,
                time_offset=time.perf_counter() - t0,
                token_usage=captured_usage,
            )

        except Exception as e:
            raise self._map_groq_error(e) from e
