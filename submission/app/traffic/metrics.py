"""Metrics and observability models for the asynchronous traffic manager."""

from collections import deque
import threading
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class TrafficMetricsSnapshot(BaseModel):
    """Immutable point-in-time snapshot of traffic manager operational metrics."""

    # Queue metrics
    queue_capacity: int = Field(description="Configured maximum capacity of the FIFO queue.")
    queue_depth: int = Field(description="Current number of requests waiting in the FIFO queue.")

    # Request lifecycle counters
    total_accepted: int = Field(description="Total requests accepted into the queue.")
    total_rejected: int = Field(description="Total requests rejected before or during processing.")

    # Rejection and timeout counters
    queue_full_rejections: int = Field(description="Requests rejected immediately due to full queue.")
    queue_expired_requests: int = Field(description="Requests that expired while waiting in queue.")
    execution_timeouts: int = Field(description="Requests that expired during provider execution.")

    # Concurrency metrics
    current_in_flight: int = Field(description="Number of provider calls currently actively executing.")
    peak_in_flight: int = Field(description="Maximum simultaneous in-flight provider calls observed.")

    # Local rate admission metrics (sliding 60-second window)
    completed_rpm: int = Field(description="Requests completed within the sliding 60-second window.")
    reserved_rpm: int = Field(description="Requests currently in-flight holding an RPM slot reservation.")
    completed_tpm: int = Field(description="Tokens completed within the sliding 60-second window.")
    reserved_tpm: int = Field(description="Tokens currently reserved by active in-flight requests.")

    # Daily budget accounting (UTC calendar date)
    daily_completed_requests: int = Field(description="Total requests successfully completed today (UTC).")
    daily_reserved_requests: int = Field(description="Total in-flight requests currently reserved today (UTC).")
    daily_budget: Optional[int] = Field(default=None, description="Configured daily request budget ceiling.")

    # Provider interaction counters
    provider_attempts: int = Field(description="Total attempts dispatched to the upstream provider.")
    provider_retries: int = Field(description="Total retry attempts executed after transient failures.")
    rate_limit_responses: int = Field(description="Rate limit responses encountered (local admission or provider).")
    client_cancellations: int = Field(description="Requests cancelled by the caller task or client disconnect.")

    # Final outcomes
    successful_requests: int = Field(description="Requests completed successfully.")
    failed_requests: int = Field(description="Requests that ultimately terminated with an error.")

    # Live latency statistics (rolling window)
    latency_stats: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Point-in-time percentile latency statistics across recorded samples.",
    )


class TrafficMetricsTracker:
    """Thread-safe collector for cumulative and point-in-time traffic metrics."""

    def __init__(self):
        self._lock = threading.Lock()

        # Counters
        self.total_accepted: int = 0
        self.total_rejected: int = 0
        self.queue_full_rejections: int = 0
        self.queue_expired_requests: int = 0
        self.execution_timeouts: int = 0

        self.provider_attempts: int = 0
        self.provider_retries: int = 0
        self.rate_limit_responses: int = 0
        self.client_cancellations: int = 0

        self.successful_requests: int = 0
        self.failed_requests: int = 0

        # Latency tracking (rolling window of last 1,000 completed provider calls)
        self._latencies: deque = deque(maxlen=1000)

    def record_latency(self, latency_ms: float) -> None:
        """Record a completed request latency sample in milliseconds."""
        with self._lock:
            self._latencies.append(latency_ms)

    def _get_latency_stats_unlocked(self) -> Optional[Dict[str, Any]]:
        """Compute summary statistics across recorded latency samples (caller must hold lock)."""
        if not self._latencies:
            return None
        sorted_lat = sorted(self._latencies)
        n = len(sorted_lat)

        def _pct(p: float) -> float:
            idx = min(int(p * (n - 1)), n - 1)
            return round(sorted_lat[idx], 2)

        return {
            "sample_count": n,
            "window": "rolling_1000_requests",
            "p50_ms": _pct(0.50),
            "p95_ms": _pct(0.95),
            "p99_ms": _pct(0.99),
            "avg_ms": round(sum(sorted_lat) / n, 2),
            "min_ms": round(sorted_lat[0], 2),
            "max_ms": round(sorted_lat[-1], 2),
        }

    def get_latency_stats(self) -> Optional[Dict[str, Any]]:
        """Thread-safe getter for current latency summary statistics."""
        with self._lock:
            return self._get_latency_stats_unlocked()

    def record_accepted(self) -> None:
        with self._lock:
            self.total_accepted += 1

    def record_rejected(self) -> None:
        with self._lock:
            self.total_rejected += 1

    def record_queue_full(self) -> None:
        with self._lock:
            self.queue_full_rejections += 1
            self.total_rejected += 1

    def record_queue_expired(self) -> None:
        with self._lock:
            self.queue_expired_requests += 1

    def record_execution_timeout(self) -> None:
        with self._lock:
            self.execution_timeouts += 1

    def record_provider_attempt(self) -> None:
        with self._lock:
            self.provider_attempts += 1

    def record_provider_retry(self) -> None:
        with self._lock:
            self.provider_retries += 1

    def record_rate_limit(self) -> None:
        with self._lock:
            self.rate_limit_responses += 1

    def record_client_cancellation(self) -> None:
        with self._lock:
            self.client_cancellations += 1

    def record_success(self) -> None:
        with self._lock:
            self.successful_requests += 1

    def record_failed(self) -> None:
        with self._lock:
            self.failed_requests += 1

    def snapshot(
        self,
        queue_capacity: int,
        queue_depth: int,
        current_in_flight: int,
        peak_in_flight: int,
        completed_rpm: int,
        reserved_rpm: int,
        completed_tpm: int,
        reserved_tpm: int,
        daily_completed_requests: int,
        daily_reserved_requests: int,
        daily_budget: Optional[int],
    ) -> TrafficMetricsSnapshot:
        """Construct an immutable point-in-time metrics snapshot."""
        with self._lock:
            return TrafficMetricsSnapshot(
                queue_capacity=queue_capacity,
                queue_depth=queue_depth,
                total_accepted=self.total_accepted,
                total_rejected=self.total_rejected,
                queue_full_rejections=self.queue_full_rejections,
                queue_expired_requests=self.queue_expired_requests,
                execution_timeouts=self.execution_timeouts,
                current_in_flight=current_in_flight,
                peak_in_flight=peak_in_flight,
                completed_rpm=completed_rpm,
                reserved_rpm=reserved_rpm,
                completed_tpm=completed_tpm,
                reserved_tpm=reserved_tpm,
                daily_completed_requests=daily_completed_requests,
                daily_reserved_requests=daily_reserved_requests,
                daily_budget=daily_budget,
                provider_attempts=self.provider_attempts,
                provider_retries=self.provider_retries,
                rate_limit_responses=self.rate_limit_responses,
                client_cancellations=self.client_cancellations,
                successful_requests=self.successful_requests,
                failed_requests=self.failed_requests,
                latency_stats=self._get_latency_stats_unlocked(),
            )

