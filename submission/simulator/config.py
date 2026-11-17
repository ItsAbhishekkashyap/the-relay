"""Configuration settings for the local custom stand-in model simulator."""

from typing import Optional
from pydantic import BaseModel, Field


class SimulatorConfig(BaseModel):
    """Configurable runtime parameters for the mock model service."""

    # Latency parameters (in milliseconds) - calibrated from Stage 4 real Groq characterization
    base_delay_ms: float = Field(
        default=976.5,
        ge=0.0,
        description="Base artificial delay in milliseconds (calibrated from Stage 4 real Groq non-streaming median 976.5ms).",
    )
    jitter_ms: float = Field(
        default=174.0,
        ge=0.0,
        description="Target standard deviation (ms) for non-streaming latency (calibrated from Stage 4 stddev 174.0ms).",
    )
    ttft_ms: float = Field(
        default=852.0,
        ge=0.0,
        description="Delay before emitting the first token chunk in streaming mode (calibrated from Stage 4 streaming TTFT median 852.0ms).",
    )
    ttft_stddev_ms: float = Field(
        default=234.55,
        ge=0.0,
        description="Standard deviation for streaming TTFT (calibrated from Stage 4 stddev 234.55ms).",
    )
    inter_chunk_delay_ms: float = Field(
        default=20.0,
        ge=0.0,
        description="Delay between subsequent chunks in streaming mode (calibrated to ~20.0ms on host OS yielding ~218.4ms emission duration across 8 chunks).",
    )
    num_stream_chunks: int = Field(
        default=8,
        ge=1,
        description="Number of chunks to stream across during response emission.",
    )
    latency_distribution: str = Field(
        default="lognormal",
        description="Distribution used for latency generation: 'lognormal', 'normal', or 'uniform'.",
    )
    load_slowdown_factor: float = Field(
        default=0.05,
        ge=0.0,
        description="Fractional latency increase per concurrent in-flight request simulating queue/resource contention.",
    )

    # Failure parameters
    failure_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Probability (0.0 to 1.0) of throwing a transient 500 error.",
    )
    deterministic_failure: Optional[str] = Field(
        default=None,
        description="Forced failure mode: 'rate_limit', 'server_error', 'timeout', 'auth_error', or 'overload'.",
    )

    # Rate limiting (calibrated to real Groq limits for openai/gpt-oss-120b)
    rpm_limit: int = Field(
        default=30,
        ge=1,
        description="Maximum requests per 60-second sliding window (30 RPM).",
    )
    tpm_limit: int = Field(
        default=8000,
        ge=1,
        description="Maximum estimated tokens per 60-second sliding window (8,000 TPM).",
    )
    daily_budget: int = Field(
        default=1000,
        ge=1,
        description="Maximum total requests allowed in a single UTC day (1,000 RPD).",
    )
    daily_token_budget: Optional[int] = Field(
        default=200000,
        ge=1,
        description="Maximum total tokens allowed in a single UTC day (200,000 TPD).",
    )

    # Concurrency limit
    max_concurrent_requests: int = Field(
        default=10,
        ge=1,
        description="Maximum number of in-flight requests before returning overload.",
    )

    # Optional Retry-After override
    retry_after_seconds: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Optional fixed retry_after value in seconds returned on 429.",
    )

    # Token calibration overrides
    target_prompt_tokens: Optional[int] = Field(
        default=None,
        ge=1,
        description="Fixed prompt token count if overriding estimation (calibrated: 94).",
    )
    target_completion_tokens: Optional[int] = Field(
        default=None,
        ge=1,
        description="Fixed completion token count if overriding estimation (calibrated: 250).",
    )

    # Model identifier
    model_name: str = Field(
        default="simulator/mock-model-v1",
        description="Reported model identifier.",
    )

