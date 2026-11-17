"""Configuration models for the asynchronous traffic manager."""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, model_validator


class TrafficManagerConfig(BaseModel):
    """Configuration settings for concurrency, queueing, rate admission, and retries."""

    # FIFO Queue settings
    max_queue_size: int = Field(
        default=50,
        ge=1,
        description="Maximum number of requests permitted to wait in the FIFO queue before rejecting with QueueFullError.",
    )
    max_concurrency: int = Field(
        default=5,
        ge=1,
        description="Maximum number of simultaneous active provider calls permitted in-flight.",
    )
    default_request_timeout: Optional[float] = Field(
        default=60.0,
        ge=0.01,
        description="Default deadline timeout in seconds for submitted requests (enqueued wait + execution).",
    )

    # Local Rate Admission settings (documented conservative local policies; not upstream Groq internals)
    rpm_limit: Optional[int] = Field(
        default=None,
        ge=1,
        description="Maximum requests admitted per 60-second sliding window.",
    )
    tpm_limit: Optional[int] = Field(
        default=None,
        ge=1,
        description="Maximum tokens admitted per 60-second sliding window (completed + in-flight reservations).",
    )
    daily_request_budget: Optional[int] = Field(
        default=None,
        ge=1,
        description="Maximum total requests admitted per UTC calendar day (completed + in-flight reservations).",
    )
    default_output_token_allowance: int = Field(
        default=50,
        ge=1,
        description="Conservative output token allowance reserved at admission when request.max_tokens is omitted.",
    )

    # Retry Policy settings
    max_retries: int = Field(
        default=2,
        ge=0,
        description="Maximum number of retry attempts after initial failure (total attempts = max_retries + 1).",
    )
    initial_backoff_seconds: float = Field(
        default=0.5,
        ge=0.001,
        description="Initial exponential backoff delay in seconds.",
    )
    max_backoff_seconds: float = Field(
        default=10.0,
        ge=0.01,
        description="Upper ceiling on backoff delay in seconds.",
    )
    backoff_factor: float = Field(
        default=2.0,
        ge=1.0,
        description="Multiplicative factor applied for each successive retry attempt.",
    )
    jitter_fraction: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Random proportional jitter added to computed exponential backoff delay.",
    )

    @model_validator(mode="after")
    def validate_backoff_range(self) -> "TrafficManagerConfig":
        """Ensure initial backoff does not exceed maximum backoff."""
        if self.initial_backoff_seconds > self.max_backoff_seconds:
            self.max_backoff_seconds = self.initial_backoff_seconds
        return self

