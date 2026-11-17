"""Pydantic request and response schemas for the FastAPI research assistant API."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator

from app.workflow.schemas import Citation, RetrievedDocument

ALLOWED_PAPER_IDS = {
    "1706.03762v7",
    "1706.03762",
    "2410.00037v1",
    "2410.00037",
    "2507.07955v2",
    "2507.07955",
}


class AskRequest(BaseModel):
    """Input payload for the research question answering endpoint."""

    question: str = Field(
        ...,
        description="The research question to be answered from the 3 arXiv papers.",
        examples=["How does the Transformer architecture use self-attention?"],
    )
    paper_filter: Optional[str] = Field(
        default=None,
        description="Optional arXiv identifier to restrict search (e.g. '1706.03762v7').",
        examples=["1706.03762v7"],
    )

    @field_validator("question")
    @classmethod
    def validate_question_non_empty(cls, value: str) -> str:
        """Ensure question is not empty or whitespace only."""
        if not value or not value.strip():
            raise ValueError("Question cannot be empty or whitespace-only.")
        return value.strip()

    @field_validator("paper_filter")
    @classmethod
    def validate_paper_filter(cls, value: Optional[str]) -> Optional[str]:
        """Validate that paper_filter is one of the supported arXiv paper identifiers."""
        if value is not None:
            clean_val = value.strip()
            if clean_val not in ALLOWED_PAPER_IDS:
                raise ValueError(
                    f"Unsupported paper_filter '{value}'. Supported identifiers: "
                    "1706.03762v7 (Attention Is All You Need), "
                    "2410.00037v1 (Moshi), "
                    "2507.07955v2 (Dynamic Chunking)."
                )
            return clean_val
        return None


class AskResponse(BaseModel):
    """Structured response contract returned by the /v1/ask endpoint."""

    request_id: str = Field(description="Unique correlation identifier for the request.")
    question: str = Field(description="The original user research question.")
    answer: str = Field(description="The verified grounded answer or explicit refusal.")
    status: str = Field(description="Verification status: 'verified', 'refused', or 'unverified'.")
    citations: List[Citation] = Field(
        default_factory=list,
        description="Traceable citations verified against retrieved evidence.",
    )
    retrieved_passages: List[RetrievedDocument] = Field(
        default_factory=list,
        description="Evidence chunks retrieved by the hybrid retrieval engine.",
    )
    provider: str = Field(description="Name of the model provider that generated the completion.")
    refusal_reason: Optional[str] = Field(
        default=None,
        description="Reason for refusal if the question could not be answered.",
    )
    correction_occurred: bool = Field(
        default=False,
        description="True if an automatic correction attempt was performed.",
    )
    workflow_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Operational execution metadata and diagnostics.",
    )


class HealthResponse(BaseModel):
    """Basic health check response."""

    status: str = Field(default="ok", description="Service liveness status.")
    service: str = Field(default="relay-research-assistant", description="Service identifier.")


class ReadyResponse(BaseModel):
    """Readiness check response indicating operational component health."""

    status: str = Field(default="ready", description="Service readiness status.")
    provider: str = Field(description="Configured model provider.")
    model: str = Field(description="Configured model name.")
    components: Dict[str, str] = Field(
        default_factory=dict,
        description="Status of individual subcomponents.",
    )


class LatencyStats(BaseModel):
    """Live latency percentile statistics across recorded provider calls."""

    available: bool = Field(description="True if sufficient samples exist to compute statistics.")
    sample_count: int = Field(default=0, description="Number of request latency samples recorded.")
    measurement_scope: str = Field(
        default="Provider execution duration via TrafficManager (rolling 1,000 requests)",
        description="Description of measurement boundary and window.",
    )
    p50_ms: Optional[float] = Field(default=None, description="50th percentile (median) latency in ms.")
    p95_ms: Optional[float] = Field(default=None, description="95th percentile latency in ms.")
    p99_ms: Optional[float] = Field(default=None, description="99th percentile latency in ms.")
    avg_ms: Optional[float] = Field(default=None, description="Mean latency in ms.")
    min_ms: Optional[float] = Field(default=None, description="Minimum observed latency in ms.")
    max_ms: Optional[float] = Field(default=None, description="Maximum observed latency in ms.")


class RequestStats(BaseModel):
    """Cumulative request accounting metrics."""

    total_submitted: int = Field(description="Total requests received and accepted/queued by the service.")
    successful: int = Field(description="Requests completed successfully.")
    failed: int = Field(description="Requests terminating in error.")
    rate_limited: int = Field(description="Requests encountering rate limit responses.")
    timed_out: int = Field(description="Requests that exceeded queue or execution timeouts.")
    retried: int = Field(description="Total retry attempts executed by the traffic manager.")
    queue_rejections: int = Field(description="Requests rejected immediately due to queue saturation.")
    client_cancellations: int = Field(description="Requests cancelled by client disconnect or abort.")


class QueueStats(BaseModel):
    """Current FIFO request queue status."""

    current_depth: int = Field(description="Current number of requests waiting in the queue.")
    capacity: int = Field(description="Maximum configured queue capacity.")
    utilization_pct: float = Field(description="Current queue utilization percentage (0.0 to 100.0).")


class ConcurrencyStats(BaseModel):
    """Active in-flight execution and concurrency metrics."""

    active_in_flight: int = Field(description="Current number of requests actively executing.")
    peak_in_flight: int = Field(description="Maximum simultaneous in-flight requests observed.")
    max_concurrency: int = Field(description="Configured maximum concurrency limit.")


class RateLimitStats(BaseModel):
    """Sliding-window admission rates and operational limits."""

    rpm_limit: Optional[int] = Field(default=None, description="Configured requests-per-minute admission limit.")
    tpm_limit: Optional[int] = Field(default=None, description="Configured tokens-per-minute admission limit.")
    completed_rpm: int = Field(description="Requests completed in the current 60s sliding window.")
    reserved_rpm: int = Field(description="Requests currently in-flight holding an RPM slot.")
    completed_tpm: int = Field(description="Tokens completed in the current 60s sliding window.")
    reserved_tpm: int = Field(description="Tokens currently reserved by active requests.")


class ProviderInfo(BaseModel):
    """Provider identification and active model info."""

    provider_name: str = Field(description="Active model provider name (e.g. 'simulator' or 'groq').")
    model_name: str = Field(description="Active model identifier.")


class MetricsResponse(BaseModel):
    """Runtime operational metrics returned by GET /v1/metrics."""

    timestamp: str = Field(description="ISO-8601 UTC timestamp of metrics collection.")
    provider: ProviderInfo = Field(description="Active provider and model info.")
    requests: RequestStats = Field(description="Cumulative request statistics.")
    queue: QueueStats = Field(description="Current FIFO queue status and capacity.")
    concurrency: ConcurrencyStats = Field(description="Active in-flight and configured concurrency.")
    rate_limits: RateLimitStats = Field(description="Sliding-window admission rates and limits.")
    latency: LatencyStats = Field(description="Live latency statistics across completed requests.")
