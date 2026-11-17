"""Unit tests for the Groq provider adapter using mocked SDK responses.

Ensures complete error classification and contract adherence without real API calls.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest
import groq

from app.providers.groq_provider import GroqProvider
from app.providers.schemas import (
    GenerationRequest,
    ChatMessage,
    ErrorCategory,
)
from app.providers.base import (
    RateLimitError,
    AuthenticationError,
    TimeoutError,
    ProviderServerError,
    ConnectionError,
    InvalidResponseError,
)


@pytest.fixture
def mock_groq_client():
    """Create a mock AsyncGroq client."""
    client = MagicMock(spec=groq.AsyncGroq)
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    return client


def test_groq_provider_missing_api_key(monkeypatch):
    """Provider must raise AuthenticationError when credentials are missing."""
    async def _test():
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        provider = GroqProvider(api_key=None, client=None)

        req = GenerationRequest(prompt="Hello")
        with pytest.raises(AuthenticationError) as exc_info:
            await provider.generate(req)

        assert exc_info.value.error_category == ErrorCategory.AUTHENTICATION_FAILURE
        assert exc_info.value.status_code == 401
        assert "GROQ_API_KEY is not configured" in exc_info.value.message

    asyncio.run(_test())


def test_groq_provider_generate_contract(mock_groq_client):
    """Provider must return compliant GenerationResponse on successful completion."""
    async def _test():
        mock_choice = MagicMock()
        mock_choice.message.content = "Test response from Groq."
        mock_choice.finish_reason = "stop"

        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 12
        mock_usage.completion_tokens = 6
        mock_usage.total_tokens = 18

        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]
        mock_completion.usage = mock_usage

        mock_groq_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        provider = GroqProvider(
            api_key="gsk_mock_test_key_1234567890",
            default_model="openai/gpt-oss-120b",
            client=mock_groq_client,
        )

        req = GenerationRequest(
            request_id="req-test-101",
            messages=[ChatMessage(role="user", content="Explain attention mechanism.")],
            temperature=0.3,
            max_tokens=50,
        )

        resp = await provider.generate(req)

        assert resp.request_id == "req-test-101"
        assert resp.response_text == "Test response from Groq."
        assert resp.provider_name == "groq"
        assert resp.model_name == "openai/gpt-oss-120b"
        assert resp.http_status == 200
        assert resp.total_latency >= 0.0
        assert resp.time_to_first_token is None  # Non-streaming cannot measure TTFT
        assert resp.token_usage is not None
        assert resp.token_usage.prompt_tokens == 12
        assert resp.token_usage.completion_tokens == 6
        assert resp.token_usage.total_tokens == 18
        assert resp.token_usage.is_estimated is False

    asyncio.run(_test())


def test_groq_provider_streaming_contract(mock_groq_client):
    """Provider must stream StreamChunks with proper sequence and timing offsets."""
    async def _test():
        async def mock_stream_gen():
            chunks_data = [
                ("The ", None),
                ("attention ", None),
                ("mechanism.", "stop"),
            ]
            for delta_text, finish in chunks_data:
                c = MagicMock()
                choice = MagicMock()
                choice.delta.content = delta_text
                choice.finish_reason = finish
                c.choices = [choice]
                c.usage = None
                if finish:
                    usage = MagicMock()
                    usage.prompt_tokens = 8
                    usage.completion_tokens = 4
                    usage.total_tokens = 12
                    c.usage = usage
                yield c

        mock_groq_client.chat.completions.create = AsyncMock(return_value=mock_stream_gen())

        provider = GroqProvider(
            api_key="gsk_mock_test_key_1234567890",
            default_model="openai/gpt-oss-120b",
            client=mock_groq_client,
        )

        req = GenerationRequest(
            request_id="stream-req-1",
            messages=[ChatMessage(role="user", content="Stream this")],
            stream=True,
        )

        chunks = []
        async for chunk in provider.stream(req):
            chunks.append(chunk)

        assert len(chunks) == 4
        assert chunks[0].delta_text == "The "
        assert chunks[0].chunk_index == 0
        assert not chunks[0].is_final

        assert chunks[1].delta_text == "attention "
        assert chunks[1].chunk_index == 1
        assert not chunks[1].is_final

        assert chunks[2].delta_text == "mechanism."
        assert chunks[2].chunk_index == 2
        assert not chunks[2].is_final

        assert chunks[3].delta_text == ""
        assert chunks[3].chunk_index == 3
        assert chunks[3].is_final
        assert chunks[3].token_usage is not None
        assert chunks[3].token_usage.total_tokens == 12

    asyncio.run(_test())


def test_groq_provider_streaming_trailing_usage_chunk(mock_groq_client):
    """Provider must consume trailing usage-only chunk (choices=[]) and attach it to final chunk."""
    async def _test():
        async def mock_trailing_stream():
            # Chunk 1: Content
            c1 = MagicMock()
            choice1 = MagicMock()
            choice1.delta.content = "Chunk 1"
            choice1.finish_reason = None
            c1.choices = [choice1]
            c1.usage = None
            yield c1

            # Chunk 2: Finish reason chunk with no usage
            c2 = MagicMock()
            choice2 = MagicMock()
            choice2.delta.content = ""
            choice2.finish_reason = "stop"
            c2.choices = [choice2]
            c2.usage = None
            yield c2

            # Chunk 3: Trailing usage-only chunk with empty choices
            c3 = MagicMock()
            c3.choices = []
            usage = MagicMock()
            usage.prompt_tokens = 20
            usage.completion_tokens = 10
            usage.total_tokens = 30
            c3.usage = usage
            yield c3

        mock_groq_client.chat.completions.create = AsyncMock(return_value=mock_trailing_stream())

        provider = GroqProvider(
            api_key="gsk_mock_test_key_1234567890",
            client=mock_groq_client,
        )

        req = GenerationRequest(prompt="Test trailing usage", stream=True)
        chunks = []
        async for chunk in provider.stream(req):
            chunks.append(chunk)

        # Content chunk + terminating chunk
        assert len(chunks) == 2
        assert chunks[0].delta_text == "Chunk 1"
        assert not chunks[0].is_final

        # Final chunk captures usage from trailing chunk
        assert chunks[1].is_final
        assert chunks[1].token_usage is not None
        assert chunks[1].token_usage.prompt_tokens == 20
        assert chunks[1].token_usage.completion_tokens == 10
        assert chunks[1].token_usage.total_tokens == 30

    asyncio.run(_test())


def test_groq_non_streaming_ttft_is_none(mock_groq_client):
    """Non-streaming completions cannot measure TTFT and must represent it as None."""
    async def _test():
        mock_choice = MagicMock()
        mock_choice.message.content = "Answer."
        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]
        mock_completion.usage = None
        mock_groq_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        provider = GroqProvider(api_key="gsk_mock", client=mock_groq_client)
        resp = await provider.generate(GenerationRequest(prompt="Hello"))
        assert resp.time_to_first_token is None
        assert resp.total_latency >= 0.0

    asyncio.run(_test())


def test_groq_rate_limit_error(mock_groq_client):
    """429 RateLimitError must be mapped to RateLimitError with retry_after preserved."""
    async def _test():
        response = MagicMock()
        response.status_code = 429
        response.headers = {"retry-after": "15.5"}

        mock_groq_client.chat.completions.create = AsyncMock(
            side_effect=groq.RateLimitError(
                message="Rate limit exceeded. Please wait.",
                response=response,
                body={"error": {"code": "rate_limit_exceeded"}},
            )
        )

        provider = GroqProvider(
            api_key="gsk_mock_key_1234567890",
            client=mock_groq_client,
        )

        with pytest.raises(RateLimitError) as exc_info:
            await provider.generate(GenerationRequest(prompt="Hi"))

        err = exc_info.value
        assert err.error_category == ErrorCategory.RATE_LIMITED
        assert err.status_code == 429
        assert err.provider_name == "groq"
        assert err.retry_after == 15.5

    asyncio.run(_test())


def test_groq_authentication_error(mock_groq_client):
    """Authentication errors must map to AuthenticationError with status 401."""
    async def _test():
        response = MagicMock()
        response.status_code = 401
        mock_groq_client.chat.completions.create = AsyncMock(
            side_effect=groq.AuthenticationError(
                message="Invalid API Key provided.",
                response=response,
                body={"error": {"code": "invalid_api_key"}},
            )
        )

        provider = GroqProvider(
            api_key="gsk_invalid_1234567890",
            client=mock_groq_client,
        )

        with pytest.raises(AuthenticationError) as exc_info:
            await provider.generate(GenerationRequest(prompt="Hi"))

        assert exc_info.value.error_category == ErrorCategory.AUTHENTICATION_FAILURE
        assert exc_info.value.status_code == 401

    asyncio.run(_test())


def test_groq_timeout_error(mock_groq_client):
    """APITimeoutError must map to TimeoutError with status 408."""
    async def _test():
        mock_req = MagicMock()
        mock_groq_client.chat.completions.create = AsyncMock(
            side_effect=groq.APITimeoutError(request=mock_req)
        )

        provider = GroqProvider(
            api_key="gsk_mock_key_1234567890",
            client=mock_groq_client,
        )

        with pytest.raises(TimeoutError) as exc_info:
            await provider.generate(GenerationRequest(prompt="Hi"))

        assert exc_info.value.error_category == ErrorCategory.TIMEOUT
        assert exc_info.value.status_code == 408

    asyncio.run(_test())


def test_groq_connection_error(mock_groq_client):
    """APIConnectionError must map to ConnectionError."""
    async def _test():
        mock_req = MagicMock()
        mock_groq_client.chat.completions.create = AsyncMock(
            side_effect=groq.APIConnectionError(request=mock_req)
        )

        provider = GroqProvider(
            api_key="gsk_mock_key_1234567890",
            client=mock_groq_client,
        )

        with pytest.raises(ConnectionError) as exc_info:
            await provider.generate(GenerationRequest(prompt="Hi"))

        assert exc_info.value.error_category == ErrorCategory.CONNECTION_FAILURE

    asyncio.run(_test())


def test_groq_server_error(mock_groq_client):
    """InternalServerError must map to ProviderServerError with status 500."""
    async def _test():
        response = MagicMock()
        response.status_code = 503
        mock_groq_client.chat.completions.create = AsyncMock(
            side_effect=groq.InternalServerError(
                message="Groq upstream service unavailable.",
                response=response,
                body={},
            )
        )

        provider = GroqProvider(
            api_key="gsk_mock_key_1234567890",
            client=mock_groq_client,
        )

        with pytest.raises(ProviderServerError) as exc_info:
            await provider.generate(GenerationRequest(prompt="Hi"))

        assert exc_info.value.error_category == ErrorCategory.SERVER_ERROR
        assert exc_info.value.status_code == 503

    asyncio.run(_test())


def test_groq_invalid_response_error(mock_groq_client):
    """BadRequestError and NotFoundError must map to InvalidResponseError."""
    async def _test():
        response = MagicMock()
        response.status_code = 404
        mock_groq_client.chat.completions.create = AsyncMock(
            side_effect=groq.NotFoundError(
                message="Model not found.",
                response=response,
                body={},
            )
        )

        provider = GroqProvider(
            api_key="gsk_mock_key_1234567890",
            client=mock_groq_client,
        )

        with pytest.raises(InvalidResponseError) as exc_info:
            await provider.generate(GenerationRequest(prompt="Hi"))

        assert exc_info.value.error_category == ErrorCategory.INVALID_RESPONSE
        assert exc_info.value.status_code == 404

    asyncio.run(_test())


def test_groq_provider_redacts_api_key_in_errors(mock_groq_client):
    """Provider must never leak API keys in exception messages."""
    async def _test():
        response = MagicMock()
        response.status_code = 400
        leaky_message = "Bad request with key gsk_abcdef1234567890abcdef123456 on endpoint."
        mock_groq_client.chat.completions.create = AsyncMock(
            side_effect=groq.BadRequestError(
                message=leaky_message,
                response=response,
                body={},
            )
        )

        provider = GroqProvider(
            api_key="gsk_abcdef1234567890abcdef123456",
            client=mock_groq_client,
        )

        with pytest.raises(InvalidResponseError) as exc_info:
            await provider.generate(GenerationRequest(prompt="Hi"))

        assert "gsk_abcdef1234567890abcdef123456" not in exc_info.value.message
        assert "[REDACTED_API_KEY]" in exc_info.value.message

    asyncio.run(_test())
