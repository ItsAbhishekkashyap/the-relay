"""Shared request, response, and error schemas for model providers.

Supports both real model providers (e.g. Groq) and the local stand-in simulator.
"""

from enum import Enum
import uuid
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator


class ErrorCategory(str, Enum):
    """Standard error classifications for model service providers."""

    RATE_LIMITED = "rate_limited"
    AUTHENTICATION_FAILURE = "authentication_failure"
    TIMEOUT = "timeout"
    SERVER_ERROR = "server_error"
    CONNECTION_FAILURE = "connection_failure"
    INVALID_RESPONSE = "invalid_response"


class ChatMessage(BaseModel):
    """A single message within a chat conversation."""

    role: str = Field(
        ...,
        description="Role of the message author: 'system', 'user', or 'assistant'.",
    )
    content: str = Field(..., description="Text content of the message.")


class TokenUsage(BaseModel):
    """Token consumption information for a generation request."""

    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    is_estimated: bool = Field(
        default=False,
        description="True if token counts are estimated by the stand-in simulator.",
    )


class GenerationRequest(BaseModel):
    """Standard input request for chat completions across all providers."""

    request_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for tracing and correlation.",
    )
    messages: List[ChatMessage] = Field(
        default_factory=list,
        description="Chronological list of conversation messages.",
    )
    prompt: Optional[str] = Field(
        default=None,
        description="Convenience single prompt string; converted to a user message if provided.",
    )
    model: Optional[str] = Field(
        default=None,
        description="Target model identifier (overrides default provider model).",
    )
    max_tokens: Optional[int] = Field(
        default=None,
        ge=1,
        description="Maximum tokens to generate in response.",
    )
    temperature: Optional[float] = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature.",
    )
    stream: bool = Field(
        default=False,
        description="Whether to stream response tokens chunk-by-chunk.",
    )

    @model_validator(mode="after")
    def validate_and_normalize(self) -> "GenerationRequest":
        """Ensure messages is populated from prompt if prompt is passed."""
        if not self.messages and self.prompt:
            self.messages = [ChatMessage(role="user", content=self.prompt)]
        if not self.messages:
            raise ValueError("Either 'messages' or 'prompt' must be provided.")
        return self


class GenerationResponse(BaseModel):
    """Standardized response from a model provider for a complete generation."""

    request_id: str = Field(..., description="Matches the request ID.")
    response_text: str = Field(..., description="Generated text content.")
    provider_name: str = Field(..., description="Name of provider ('groq' or 'simulator').")
    model_name: str = Field(..., description="Identifier of the model used.")
    time_to_first_token: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Seconds elapsed from request start to first token delivery.",
    )
    total_latency: float = Field(
        ...,
        ge=0.0,
        description="Total elapsed wall-clock seconds for request completion.",
    )
    token_usage: Optional[TokenUsage] = Field(
        default=None,
        description="Prompt and completion token counts.",
    )
    http_status: int = Field(
        default=200,
        description="HTTP status code returned by the provider/endpoint.",
    )
    error_category: Optional[ErrorCategory] = Field(
        default=None,
        description="Error classification if an error occurred.",
    )


class StreamChunk(BaseModel):
    """A streaming chunk delivered during streaming chat completion."""

    request_id: str = Field(..., description="Matches the generation request ID.")
    chunk_index: int = Field(..., ge=0, description="0-indexed sequence number.")
    delta_text: str = Field(..., description="Text delta content in this chunk.")
    is_final: bool = Field(
        default=False,
        description="True if this is the terminating chunk of the stream.",
    )
    time_offset: float = Field(
        default=0.0,
        ge=0.0,
        description="Seconds elapsed from request start to this chunk delivery.",
    )
    token_usage: Optional[TokenUsage] = Field(
        default=None,
        description="Usage statistics attached on the final chunk if available.",
    )

