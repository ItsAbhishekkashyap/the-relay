"""Asynchronous Traffic Manager for model providers.

Provides:
- Bounded asynchronous FIFO queue with prompt queue-full rejection.
- End-to-end request deadlines encompassing both queue wait and provider execution.
- Strict concurrency control (maximum simultaneous in-flight provider calls).
- Local rate admission accounting (RPM, TPM, and UTC daily budget).
- Centralized bounded retry policy with exponential backoff, jitter, and Retry-After support.
- Incremental streaming pass-through with exactly-once capacity lifecycle release.
- Point-in-time metrics and observability snapshotting.

Documentation Notes:
1. Local Admission vs. Upstream Limits:
   The configured local RPM, TPM, and daily budget limits represent local traffic-shaping
   and admission controls. They are not claimed to be exact clones of proprietary upstream
   provider (e.g. Groq) internal tier enforcement.
2. Network Retry Semantics:
   Retrying following an ambiguous network failure (such as a connection reset, dropped socket,
   or HTTP read timeout where the request may have reached the upstream server) carries an
   inherent risk of duplicate upstream execution. Exactly-once delivery across distributed
   networks is not guaranteed.
"""

import asyncio
from collections import deque
from datetime import datetime, timezone
import random
import time
from typing import AsyncIterator, Dict, Any, Optional, Tuple, List
import uuid

from app.providers.base import (
    BaseModelProvider,
    ModelProviderError,
    RateLimitError,
    AuthenticationError,
    TimeoutError as ProviderTimeoutError,
    ProviderServerError,
    ConnectionError as ProviderConnectionError,
    InvalidResponseError,
)
from app.providers.schemas import (
    GenerationRequest,
    GenerationResponse,
    StreamChunk,
    ErrorCategory,
)
from app.traffic.config import TrafficManagerConfig
from app.traffic.errors import (
    TrafficManagerError,
    QueueFullError,
    QueueTimeoutError,
    ExecutionTimeoutError,
    LocalRateLimitError,
    StreamAlreadyStartedError,
    TrafficManagerClosedError,
)
from app.traffic.metrics import TrafficMetricsTracker, TrafficMetricsSnapshot


def estimate_prompt_tokens(request: GenerationRequest) -> int:
    """Documented heuristic for prompt token estimation.

    Concatenates all message contents, counts whitespace-separated words, and applies
    approx 1.33 tokens per word (words * 4 // 3), with a floor of 1 token per message
    and 1 token minimum overall. This is an explicit local heuristic and does not claim
    to replicate proprietary upstream tokenizers.
    """
    total_words = 0
    for msg in request.messages:
        content = msg.content or ""
        words = len(content.strip().split())
        total_words += max(1, words)
    if total_words == 0:
        return 1
    return max(1, (total_words * 4) // 3)


class _QueueItem:
    """Internal entry in the FIFO waiting queue."""

    def __init__(
        self,
        request: GenerationRequest,
        enqueued_at: float,
        deadline_at: Optional[float],
    ):
        self.request = request
        self.enqueued_at = enqueued_at
        self.deadline_at = deadline_at
        self.event = asyncio.Event()
        self.is_cancelled: bool = False
        self.acquired: bool = False
        self.reservation_id: Optional[str] = None
        self.error: Optional[Exception] = None


class TrafficManager:
    """Asynchronous traffic manager governing provider execution."""

    def __init__(
        self,
        provider: BaseModelProvider,
        config: Optional[TrafficManagerConfig] = None,
    ):
        self.provider = provider
        self.config = config or TrafficManagerConfig()
        self._lock = asyncio.Lock()

        # FIFO Queue of waiting requests
        self._queue: deque[_QueueItem] = deque()

        # In-flight reservation tracking:
        # Maps reservation_id -> (timestamp, reserved_tokens)
        self._active_reservations: Dict[str, Tuple[float, int]] = {}

        # Completed requests sliding window: deque of (completion_timestamp, actual_tokens)
        self._completed_window: deque[Tuple[float, int]] = deque()
        self._window_seconds: float = 60.0

        # Concurrency counters
        self._in_flight: int = 0
        self._peak_in_flight: int = 0

        # Daily budget tracking (UTC calendar date)
        self._daily_date: str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self._daily_completed_requests: int = 0

        # Operational status and metrics
        self._is_closed: bool = False
        self.metrics = TrafficMetricsTracker()

    # --------------------------------------------------------------------------
    # Configuration and Observability
    # --------------------------------------------------------------------------

    def configure(self, updates: Dict[str, Any]) -> TrafficManagerConfig:
        """Update traffic manager configuration at runtime (e.g. adjust RPM or budget)."""
        current_data = self.config.model_dump()
        current_data.update(updates)
        self.config = TrafficManagerConfig(**current_data)
        return self.config

    def get_metrics(self) -> TrafficMetricsSnapshot:
        """Capture a thread-safe snapshot of all operational traffic metrics."""
        now = time.monotonic()
        # Clean expired window entries for accurate snapshot
        self._clean_window_unlocked(now)
        self._check_and_reset_daily_unlocked()

        completed_rpm = len(self._completed_window)
        reserved_rpm = len(self._active_reservations)
        completed_tpm = sum(tok for _, tok in self._completed_window)
        reserved_tpm = sum(tok for _, tok in self._active_reservations.values())
        daily_reserved = len(self._active_reservations)

        return self.metrics.snapshot(
            queue_capacity=self.config.max_queue_size,
            queue_depth=len(self._queue),
            current_in_flight=self._in_flight,
            peak_in_flight=self._peak_in_flight,
            completed_rpm=completed_rpm,
            reserved_rpm=reserved_rpm,
            completed_tpm=completed_tpm,
            reserved_tpm=reserved_tpm,
            daily_completed_requests=self._daily_completed_requests,
            daily_reserved_requests=daily_reserved,
            daily_budget=self.config.daily_request_budget,
        )

    # --------------------------------------------------------------------------
    # Public Execution Interfaces
    # --------------------------------------------------------------------------

    async def execute(
        self,
        request: GenerationRequest,
        timeout: Optional[float] = None,
    ) -> GenerationResponse:
        """Execute a non-streaming generation request through the traffic manager."""
        return await self._execute_request(request=request, timeout=timeout)

    async def generate(
        self,
        request: GenerationRequest,
        timeout: Optional[float] = None,
    ) -> GenerationResponse:
        """Alias matching the BaseModelProvider.generate signature."""
        return await self.execute(request=request, timeout=timeout)

    async def stream(
        self,
        request: GenerationRequest,
        timeout: Optional[float] = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream provider chunks with queue admission, pre-content retries, and clean teardown."""
        item = await self._enqueue_and_wait(request=request, timeout=timeout)

        deadline_at = item.deadline_at
        current_res_id = item.reservation_id
        has_emitted_content = False
        total_tokens = 0
        provider_stream: Optional[Any] = None
        stream_closed = False

        async def _close_stream_once() -> None:
            nonlocal stream_closed
            if not stream_closed and provider_stream is not None:
                stream_closed = True
                if hasattr(provider_stream, "aclose"):
                    try:
                        await provider_stream.aclose()
                    except Exception:
                        pass

        try:
            # Check remaining deadline prior to streaming
            now = time.monotonic()
            if deadline_at is not None and now >= deadline_at:
                raise ExecutionTimeoutError(
                    f"Request {request.request_id} deadline expired before stream started"
                )

            max_attempts = 1 + self.config.max_retries
            attempt = 0

            while attempt < max_attempts:
                attempt += 1
                self.metrics.record_provider_attempt()
                if attempt > 1:
                    self.metrics.record_provider_retry()

                stream_closed = False
                provider_stream = None

                try:
                    rem = (
                        deadline_at - time.monotonic() if deadline_at is not None else None
                    )
                    if rem is not None and rem <= 0:
                        raise ExecutionTimeoutError(
                            f"Request {request.request_id} deadline expired before stream attempt {attempt}"
                        )

                    start_stream = time.monotonic()
                    stream_obj = self.provider.stream(request)
                    if asyncio.iscoroutine(stream_obj):
                        provider_stream = await stream_obj
                    else:
                        provider_stream = stream_obj

                    # Consume all chunks with bounded per-chunk deadline
                    while True:
                        rem_chunk = (
                            deadline_at - time.monotonic() if deadline_at is not None else None
                        )
                        if rem_chunk is not None and rem_chunk <= 0:
                            raise ExecutionTimeoutError(
                                f"Request {request.request_id} deadline exceeded during streaming"
                            )

                        try:
                            if rem_chunk is not None:
                                chunk = await asyncio.wait_for(
                                    anext(provider_stream), timeout=rem_chunk
                                )
                            else:
                                chunk = await anext(provider_stream)
                        except StopAsyncIteration:
                            # Stream exhausted normally
                            break
                        except asyncio.TimeoutError:
                            raise ExecutionTimeoutError(
                                f"Request {request.request_id} deadline exceeded while waiting for stream chunk"
                            )

                        if chunk.token_usage:
                            total_tokens = chunk.token_usage.total_tokens

                        # Retries are disabled only once actual non-empty content is delivered
                        if chunk.delta_text:
                            has_emitted_content = True

                        yield chunk

                    # Normal stream completion
                    await _close_stream_once()
                    latency_ms = (time.monotonic() - start_stream) * 1000.0
                    self.metrics.record_latency(latency_ms)
                    await self._settle_request(
                        reservation_id=current_res_id,
                        outcome="success",
                        actual_tokens=total_tokens,
                    )
                    return

                except GeneratorExit:
                    await _close_stream_once()
                    await self._settle_request(
                        reservation_id=current_res_id,
                        outcome="cancellation",
                    )
                    raise

                except asyncio.CancelledError:
                    await _close_stream_once()
                    await self._settle_request(
                        reservation_id=current_res_id,
                        outcome="cancellation",
                    )
                    raise

                except ExecutionTimeoutError:
                    await _close_stream_once()
                    await self._settle_request(
                        reservation_id=current_res_id,
                        outcome="execution_timeout",
                    )
                    raise

                except Exception as exc:
                    await _close_stream_once()

                    if has_emitted_content:
                        await self._settle_request(
                            reservation_id=current_res_id,
                            outcome="failure",
                            is_rate_limit=isinstance(exc, RateLimitError),
                        )
                        raise StreamAlreadyStartedError(
                            f"Stream error occurred after tokens were emitted: {exc}"
                        ) from exc

                    if (
                        self._is_retryable_error(exc)
                        and attempt < max_attempts
                        and (deadline_at is None or time.monotonic() < deadline_at)
                    ):
                        backoff_delay = self._calculate_backoff(exc, attempt)
                        if (
                            deadline_at is not None
                            and (time.monotonic() + backoff_delay) >= deadline_at
                        ):
                            await self._settle_request(
                                reservation_id=current_res_id,
                                outcome="failure",
                                is_rate_limit=isinstance(exc, RateLimitError),
                            )
                            raise exc

                        async with self._lock:
                            self._release_reservation_unlocked(current_res_id)

                        await asyncio.sleep(backoff_delay)

                        async with self._lock:
                            now_retry = time.monotonic()
                            allowed, reason, retry_after = self._check_admission_unlocked(
                                request, now_retry
                            )
                            if not allowed:
                                raise LocalRateLimitError(
                                    message=reason or "Local rate limit exceeded on retry",
                                    status_code=429,
                                    retry_after=retry_after,
                                )
                            current_res_id = self._create_reservation_unlocked(
                                request, now_retry
                            )
                        continue
                    else:
                        await self._settle_request(
                            reservation_id=current_res_id,
                            outcome="failure",
                            is_rate_limit=isinstance(exc, RateLimitError),
                        )
                        raise exc

        finally:
            await _close_stream_once()
            await self._settle_request(
                reservation_id=current_res_id,
                outcome="failure",
            )

    async def close(self) -> None:
        """Close the traffic manager and cancel all waiting queue entries."""
        async with self._lock:
            self._is_closed = True
            while self._queue:
                item = self._queue.popleft()
                item.error = TrafficManagerClosedError("Traffic manager was shut down")
                item.event.set()

    # --------------------------------------------------------------------------
    # Internal Request Processing Core
    # --------------------------------------------------------------------------

    async def _settle_request(
        self,
        reservation_id: Optional[str],
        outcome: str,
        actual_tokens: int = 0,
        is_rate_limit: bool = False,
    ) -> bool:
        """Atomically settle a request reservation and release in-flight concurrency.

        Guarantees:
        - Exactly-once settlement: checks if reservation_id is in self._active_reservations.
        - Cancellation-safe: protects lock acquisition from cancellation so cleanup
          cannot be interrupted or leaked by an external task cancellation.
        - State transition (reservation deletion, in-flight decrement, metric updates, queue pump)
          occurs atomically under self._lock.
        """
        if reservation_id is None:
            return False

        cur_task = asyncio.current_task()
        cancelling = cur_task.cancelling() if cur_task and hasattr(cur_task, "cancelling") else 0
        if cancelling:
            cur_task.uncancel()

        try:
            async with self._lock:
                if reservation_id not in self._active_reservations:
                    return False

                if outcome == "success":
                    self._reconcile_completion_unlocked(reservation_id, actual_tokens)
                    self._in_flight -= 1
                    self.metrics.record_success()
                elif outcome == "cancellation":
                    self._release_reservation_unlocked(reservation_id)
                    self._in_flight -= 1
                    self.metrics.record_client_cancellation()
                elif outcome == "execution_timeout":
                    self._release_reservation_unlocked(reservation_id)
                    self._in_flight -= 1
                    self.metrics.record_execution_timeout()
                    self.metrics.record_rejected()
                    self.metrics.record_failed()
                else:  # "failure"
                    self._release_reservation_unlocked(reservation_id)
                    self._in_flight -= 1
                    if is_rate_limit:
                        self.metrics.record_rate_limit()
                    self.metrics.record_failed()

                self._pump_queue_unlocked()
                return True
        finally:
            if cancelling:
                cur_task.cancel()

    async def _execute_request(
        self,
        request: GenerationRequest,
        timeout: Optional[float],
    ) -> GenerationResponse:
        """Coordinate queue admission, rate reservation, retries, and provider execution."""
        item = await self._enqueue_and_wait(request=request, timeout=timeout)

        # Item has been admitted and holds concurrency slot + rate reservation
        deadline_at = item.deadline_at
        current_res_id = item.reservation_id

        try:
            # Check remaining deadline prior to execution
            now = time.monotonic()
            if deadline_at is not None and now >= deadline_at:
                raise ExecutionTimeoutError(
                    f"Request {request.request_id} deadline expired before execution started"
                )

            max_attempts = 1 + self.config.max_retries
            attempt = 0

            while attempt < max_attempts:
                attempt += 1
                self.metrics.record_provider_attempt()
                if attempt > 1:
                    self.metrics.record_provider_retry()

                try:
                    remaining = (
                        deadline_at - time.monotonic() if deadline_at is not None else None
                    )
                    if remaining is not None and remaining <= 0:
                        raise ExecutionTimeoutError(
                            f"Request {request.request_id} deadline expired before attempt {attempt}"
                        )

                    # Dispatch provider execution under execution deadline
                    start_exec = time.monotonic()
                    if remaining is not None:
                        response = await asyncio.wait_for(
                            self.provider.generate(request), timeout=remaining
                        )
                    else:
                        response = await self.provider.generate(request)

                    latency_ms = (time.monotonic() - start_exec) * 1000.0
                    self.metrics.record_latency(latency_ms)

                    # Successful response: reconcile reservation and release concurrency
                    actual_tokens = (
                        response.token_usage.total_tokens
                        if response.token_usage
                        else 0
                    )
                    await self._settle_request(
                        reservation_id=current_res_id,
                        outcome="success",
                        actual_tokens=actual_tokens,
                    )
                    return response

                except asyncio.TimeoutError:
                    raise ExecutionTimeoutError(
                        f"Request {request.request_id} timed out during provider execution"
                    )

                except asyncio.CancelledError:
                    raise

                except Exception as exc:
                    if not self._is_retryable_error(exc) or attempt >= max_attempts:
                        raise

                    backoff_delay = self._calculate_backoff(exc, attempt)
                    if deadline_at is not None and (time.monotonic() + backoff_delay) >= deadline_at:
                        raise

                    async with self._lock:
                        self._release_reservation_unlocked(current_res_id)

                    await asyncio.sleep(backoff_delay)

                    async with self._lock:
                        now_retry = time.monotonic()
                        allowed, reason, retry_after = self._check_admission_unlocked(
                            request, now_retry
                        )
                        if not allowed:
                            raise LocalRateLimitError(
                                message=reason or "Local rate limit exceeded on retry",
                                status_code=429,
                                retry_after=retry_after,
                            )
                        current_res_id = self._create_reservation_unlocked(
                            request, now_retry
                        )

        except ExecutionTimeoutError:
            await self._settle_request(
                reservation_id=current_res_id,
                outcome="execution_timeout",
            )
            raise

        except asyncio.CancelledError:
            await self._settle_request(
                reservation_id=current_res_id,
                outcome="cancellation",
            )
            raise

        except Exception as exc:
            await self._settle_request(
                reservation_id=current_res_id,
                outcome="failure",
                is_rate_limit=isinstance(exc, RateLimitError),
            )
            raise

        finally:
            await self._settle_request(
                reservation_id=current_res_id,
                outcome="failure",
            )



    # --------------------------------------------------------------------------
    # Queueing and Admission Lifecycle
    # --------------------------------------------------------------------------

    async def _enqueue_and_wait(
        self,
        request: GenerationRequest,
        timeout: Optional[float],
    ) -> _QueueItem:
        """Enqueue request into FIFO queue and await concurrency and rate admission."""
        enqueued_at = time.monotonic()
        req_timeout = timeout if timeout is not None else self.config.default_request_timeout
        deadline_at = enqueued_at + req_timeout if req_timeout is not None else None

        async with self._lock:
            if self._is_closed:
                raise TrafficManagerClosedError("Traffic manager is closed")

            if len(self._queue) >= self.config.max_queue_size:
                self.metrics.record_queue_full()
                raise QueueFullError(
                    f"Traffic manager request queue is full ({len(self._queue)}/{self.config.max_queue_size})"
                )

            item = _QueueItem(
                request=request,
                enqueued_at=enqueued_at,
                deadline_at=deadline_at,
            )
            self._queue.append(item)
            self.metrics.record_accepted()
            self._pump_queue_unlocked()

        # Await queue dispatch event with queue deadline
        try:
            if deadline_at is not None:
                rem_queue = max(0.0, deadline_at - time.monotonic())
                if rem_queue <= 0:
                    raise asyncio.TimeoutError()
                await asyncio.wait_for(item.event.wait(), timeout=rem_queue)
            else:
                await item.event.wait()

        except asyncio.TimeoutError:
            async with self._lock:
                if not item.acquired:
                    item.is_cancelled = True
                    if item in self._queue:
                        self._queue.remove(item)
                    self.metrics.record_queue_expired()
                    self.metrics.record_rejected()
                    raise QueueTimeoutError(
                        f"Request {request.request_id} expired in queue after {time.monotonic() - enqueued_at:.3f}s"
                    )

        except asyncio.CancelledError:
            cur_task = asyncio.current_task()
            cancelling = cur_task.cancelling() if cur_task and hasattr(cur_task, "cancelling") else 0
            if cancelling:
                cur_task.uncancel()
            try:
                async with self._lock:
                    if not item.acquired:
                        item.is_cancelled = True
                        if item in self._queue:
                            self._queue.remove(item)
                        self.metrics.record_client_cancellation()
                    else:
                        self._release_reservation_unlocked(item.reservation_id)
                        self._in_flight -= 1
                        self.metrics.record_client_cancellation()
                        self._pump_queue_unlocked()
            finally:
                if cancelling:
                    cur_task.cancel()
            raise

        if item.error is not None:
            raise item.error

        return item

    def _pump_queue_unlocked(self) -> None:
        """Drain eligible items from the front of the FIFO queue under self._lock."""
        now = time.monotonic()
        self._clean_window_unlocked(now)
        self._check_and_reset_daily_unlocked()

        while self._queue:
            head = self._queue[0]

            if head.is_cancelled:
                self._queue.popleft()
                continue

            # Check queue deadline
            if head.deadline_at is not None and now >= head.deadline_at:
                self._queue.popleft()
                head.error = QueueTimeoutError(
                    f"Request {head.request.request_id} expired in queue after {now - head.enqueued_at:.3f}s"
                )
                self.metrics.record_queue_expired()
                self.metrics.record_rejected()
                head.event.set()
                continue

            # Check concurrency ceiling
            if self._in_flight >= self.config.max_concurrency:
                break

            # Check rate admission (RPM, TPM, daily budget)
            allowed, reason, retry_after = self._check_admission_unlocked(head.request, now)
            if not allowed:
                # Local rate admission rejected this request
                self._queue.popleft()
                head.error = LocalRateLimitError(
                    message=reason or "Local rate limit exceeded",
                    status_code=429,
                    retry_after=retry_after,
                )
                self.metrics.record_rate_limit()
                self.metrics.record_rejected()
                head.event.set()
                continue

            # Admit head request
            self._queue.popleft()
            res_id = self._create_reservation_unlocked(head.request, now)
            head.reservation_id = res_id
            head.acquired = True
            self._in_flight += 1
            if self._in_flight > self._peak_in_flight:
                self._peak_in_flight = self._in_flight
            head.event.set()

    # --------------------------------------------------------------------------
    # Accounting and Rate Admission Logic
    # --------------------------------------------------------------------------

    def _check_admission_unlocked(
        self,
        request: GenerationRequest,
        now: float,
    ) -> Tuple[bool, Optional[str], Optional[float]]:
        """Evaluate local RPM, TPM, and daily budget constraints."""
        prompt_tokens = estimate_prompt_tokens(request)
        output_tokens = request.max_tokens or self.config.default_output_token_allowance
        candidate_tokens = prompt_tokens + output_tokens

        # 1. Daily Budget Check
        daily_in_flight = len(self._active_reservations)
        daily_total = self._daily_completed_requests + daily_in_flight
        if (
            self.config.daily_request_budget is not None
            and daily_total + 1 > self.config.daily_request_budget
        ):
            return (
                False,
                f"Daily request budget of {self.config.daily_request_budget} exceeded",
                None,
            )

        # 2. RPM Check (60-second sliding window)
        current_rpm = len(self._completed_window) + len(self._active_reservations)
        if self.config.rpm_limit is not None and current_rpm + 1 > self.config.rpm_limit:
            retry_after = 60.0
            if self._completed_window:
                oldest_ts = self._completed_window[0][0]
                retry_after = max(0.05, 60.0 - (now - oldest_ts) + 0.05)
            return False, f"RPM limit of {self.config.rpm_limit} exceeded", retry_after

        # 3. TPM Check (60-second sliding window)
        completed_tpm = sum(tok for _, tok in self._completed_window)
        reserved_tpm = sum(tok for _, tok in self._active_reservations.values())
        current_tpm = completed_tpm + reserved_tpm
        if (
            self.config.tpm_limit is not None
            and current_tpm + candidate_tokens > self.config.tpm_limit
        ):
            retry_after = 60.0
            if self._completed_window:
                oldest_ts = self._completed_window[0][0]
                retry_after = max(0.05, 60.0 - (now - oldest_ts) + 0.05)
            return (
                False,
                f"TPM limit of {self.config.tpm_limit} exceeded (current={current_tpm}, candidate={candidate_tokens})",
                retry_after,
            )

        return True, None, None

    def _create_reservation_unlocked(
        self,
        request: GenerationRequest,
        now: float,
    ) -> str:
        """Create an active token reservation for an admitted request."""
        prompt_tokens = estimate_prompt_tokens(request)
        output_tokens = request.max_tokens or self.config.default_output_token_allowance
        candidate_tokens = prompt_tokens + output_tokens

        res_id = str(uuid.uuid4())
        self._active_reservations[res_id] = (now, candidate_tokens)
        return res_id

    def _reconcile_completion_unlocked(
        self,
        reservation_id: Optional[str],
        actual_tokens: int,
    ) -> None:
        """Replace reservation with actual token consumption in completed window."""
        if reservation_id and reservation_id in self._active_reservations:
            del self._active_reservations[reservation_id]

        now = time.monotonic()
        self._completed_window.append((now, actual_tokens))
        self._daily_completed_requests += 1
        self._clean_window_unlocked(now)

    def _release_reservation_unlocked(
        self,
        reservation_id: Optional[str],
    ) -> None:
        """Release reservation without crediting completed tokens or daily requests."""
        if reservation_id and reservation_id in self._active_reservations:
            del self._active_reservations[reservation_id]

    def _clean_window_unlocked(self, now: float) -> None:
        """Purge window entries older than 60 seconds."""
        cutoff = now - self._window_seconds
        while self._completed_window and self._completed_window[0][0] < cutoff:
            self._completed_window.popleft()

    def _check_and_reset_daily_unlocked(self) -> None:
        """Reset daily counters when UTC date transitions."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today != self._daily_date:
            self._daily_date = today
            self._daily_completed_requests = 0

    # --------------------------------------------------------------------------
    # Retry Policy Mechanics
    # --------------------------------------------------------------------------

    def _is_retryable_error(self, exc: Exception) -> bool:
        """Determine if an exception is eligible for retry.

        Never retries:
        - AuthenticationError (401/403)
        - InvalidResponseError (400/422)
        - QueueFullError, QueueTimeoutError, ExecutionTimeoutError
        - ValueError, TypeError, etc.

        Retries:
        - RateLimitError (429)
        - ProviderServerError (500, 502, 503, 504)
        - ProviderConnectionError
        - ProviderTimeoutError
        """
        if isinstance(exc, (AuthenticationError, InvalidResponseError)):
            return False
        if isinstance(exc, (QueueFullError, QueueTimeoutError, ExecutionTimeoutError)):
            return False
        if isinstance(
            exc,
            (
                RateLimitError,
                ProviderServerError,
                ProviderConnectionError,
                ProviderTimeoutError,
            ),
        ):
            return True
        if isinstance(exc, ModelProviderError):
            if exc.error_category in (
                ErrorCategory.RATE_LIMITED,
                ErrorCategory.SERVER_ERROR,
                ErrorCategory.CONNECTION_FAILURE,
                ErrorCategory.TIMEOUT,
            ):
                return True
        return False

    def _calculate_backoff(self, exc: Exception, attempt: int) -> float:
        """Compute retry delay respecting Retry-After or bounded exponential backoff with jitter."""
        if isinstance(exc, ModelProviderError) and exc.retry_after is not None:
            return max(0.001, float(exc.retry_after))

        base_delay = min(
            self.config.max_backoff_seconds,
            self.config.initial_backoff_seconds
            * (self.config.backoff_factor ** (attempt - 1)),
        )
        jitter = random.uniform(0, self.config.jitter_fraction * base_delay)
        return base_delay + jitter
