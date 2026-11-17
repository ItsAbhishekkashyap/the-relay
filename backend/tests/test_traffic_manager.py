"""Unit and integration tests for the asynchronous TrafficManager.

Validates:
1. FIFO execution order.
2. Queue capacity and queue-full rejection.
3. Maximum concurrency under simultaneous submissions.
4. RPM admission under concurrency.
5. TPM reservation under concurrency.
6. Daily budget enforcement.
7. Queue deadline expiration without provider invocation.
8. Execution timeout and cleanup.
9. Cancellation while queued.
10. Cancellation while executing.
11. Successful transient retry.
12. Retry-After handling.
13. No retry for authentication errors.
14. No retry after deadline expiration.
15. Streaming forwards chunks incrementally.
16. Streaming cancellation and early closure release capacity.
17. Streaming does not restart after content has been emitted.
18. Metrics accurately reflect request outcomes.
19. Dynamic reconfiguration.
20. Closed manager rejection.
21. Token estimation heuristic.
22. TrafficManager interoperability with GroqProvider (mocked).
23. TrafficManager interoperability with SimulatorProvider (mocked).
"""

import asyncio
import time
from typing import AsyncIterator, List, Optional, Callable, Dict, Any
from unittest.mock import MagicMock, AsyncMock
import pytest

from app.providers.base import (
    BaseModelProvider,
    RateLimitError,
    AuthenticationError,
    ProviderServerError,
    ConnectionError as ProviderConnectionError,
)
from app.providers.schemas import (
    GenerationRequest,
    GenerationResponse,
    StreamChunk,
    TokenUsage,
    ChatMessage,
)
from app.traffic.config import TrafficManagerConfig
from app.traffic.errors import (
    QueueFullError,
    QueueTimeoutError,
    ExecutionTimeoutError,
    LocalRateLimitError,
    StreamAlreadyStartedError,
    TrafficManagerClosedError,
)
from app.traffic.manager import TrafficManager, estimate_prompt_tokens


class FakeModelProvider(BaseModelProvider):
    """Deterministic mock provider for testing traffic management in isolation."""

    def __init__(
        self,
        name: str = "fake_provider",
        model: str = "fake_model",
        generate_handler: Optional[Callable[[GenerationRequest], Any]] = None,
        stream_handler: Optional[Callable[[GenerationRequest], Any]] = None,
    ):
        self._provider_name = name
        self._model_name = model
        self.generate_handler = generate_handler
        self.stream_handler = stream_handler

        # Call tracking
        self.call_count: int = 0
        self.active_calls: int = 0
        self.peak_active_calls: int = 0
        self.call_history: List[GenerationRequest] = []
        self._lock = asyncio.Lock()

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def model_name(self) -> str:
        return self._model_name

    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        async with self._lock:
            self.call_count += 1
            self.active_calls += 1
            if self.active_calls > self.peak_active_calls:
                self.peak_active_calls = self.active_calls
            self.call_history.append(request)

        try:
            if self.generate_handler:
                result = self.generate_handler(request)
                if asyncio.iscoroutine(result):
                    return await result
                if isinstance(result, Exception):
                    raise result
                return result

            # Default simple response
            return GenerationResponse(
                request_id=request.request_id,
                response_text="Default fake completion",
                provider_name=self.provider_name,
                model_name=self.model_name,
                total_latency=0.01,
                token_usage=TokenUsage(
                    prompt_tokens=10,
                    completion_tokens=20,
                    total_tokens=30,
                ),
            )
        finally:
            async with self._lock:
                self.active_calls -= 1

    async def stream(self, request: GenerationRequest) -> AsyncIterator[StreamChunk]:
        async with self._lock:
            self.call_count += 1
            self.active_calls += 1
            if self.active_calls > self.peak_active_calls:
                self.peak_active_calls = self.active_calls
            self.call_history.append(request)

        try:
            if self.stream_handler:
                async for chunk in self.stream_handler(request):
                    yield chunk
                return

            # Default simple stream
            for i, delta in enumerate(["Hello", " ", "world!"]):
                await asyncio.sleep(0.01)
                yield StreamChunk(
                    request_id=request.request_id,
                    chunk_index=i,
                    delta_text=delta,
                    is_final=(i == 2),
                    time_offset=0.01 * (i + 1),
                    token_usage=TokenUsage(prompt_tokens=5, completion_tokens=3, total_tokens=8)
                    if i == 2
                    else None,
                )
        finally:
            async with self._lock:
                self.active_calls -= 1


# ------------------------------------------------------------------------------
# Test 1: FIFO Execution Order
# ------------------------------------------------------------------------------

def test_fifo_execution_order():
    """Verify that requests waiting in queue are dispatched in strict FIFO sequence."""
    async def _test():
        dispatch_order = []

        async def handler(req: GenerationRequest):
            dispatch_order.append(req.request_id)
            await asyncio.sleep(0.04)
            return GenerationResponse(
                request_id=req.request_id,
                response_text="ok",
                provider_name="fake",
                model_name="fake",
                total_latency=0.04,
            )

        provider = FakeModelProvider(generate_handler=handler)
        # Concurrency=1 forces sequential execution through the FIFO queue
        config = TrafficManagerConfig(max_concurrency=1, max_queue_size=10)
        manager = TrafficManager(provider=provider, config=config)

        req1 = GenerationRequest(prompt="req-1", request_id="req-1")
        req2 = GenerationRequest(prompt="req-2", request_id="req-2")
        req3 = GenerationRequest(prompt="req-3", request_id="req-3")

        # Submit all three concurrently
        results = await asyncio.gather(
            manager.execute(req1),
            manager.execute(req2),
            manager.execute(req3),
        )

        assert [r.request_id for r in results] == ["req-1", "req-2", "req-3"]
        assert dispatch_order == ["req-1", "req-2", "req-3"]

    asyncio.run(_test())


# ------------------------------------------------------------------------------
# Test 2: Queue Capacity and Queue-Full Rejection
# ------------------------------------------------------------------------------

def test_queue_capacity_and_rejection():
    """Verify that submissions beyond max_queue_size reject immediately with QueueFullError."""
    async def _test():
        release_event = asyncio.Event()

        async def handler(req: GenerationRequest):
            await release_event.wait()
            return GenerationResponse(
                request_id=req.request_id,
                response_text="ok",
                provider_name="fake",
                model_name="fake",
                total_latency=0.01,
            )

        provider = FakeModelProvider(generate_handler=handler)
        # 1 in flight, max 2 in queue => total capacity = 3
        config = TrafficManagerConfig(max_concurrency=1, max_queue_size=2)
        manager = TrafficManager(provider=provider, config=config)

        # Submit 1st: enters execution immediately
        t1 = asyncio.create_task(manager.execute(GenerationRequest(prompt="1", request_id="r1")))
        await asyncio.sleep(0.01)

        # Submit 2nd and 3rd: fill queue (size=2)
        t2 = asyncio.create_task(manager.execute(GenerationRequest(prompt="2", request_id="r2")))
        t3 = asyncio.create_task(manager.execute(GenerationRequest(prompt="3", request_id="r3")))
        await asyncio.sleep(0.01)

        metrics = manager.get_metrics()
        assert metrics.current_in_flight == 1
        assert metrics.queue_depth == 2

        # 4th submission must be rejected immediately with QueueFullError
        with pytest.raises(QueueFullError) as exc_info:
            await manager.execute(GenerationRequest(prompt="4", request_id="r4"))

        assert "queue is full" in exc_info.value.message
        metrics_after = manager.get_metrics()
        assert metrics_after.queue_full_rejections == 1

        # Release executing task and allow queued to finish
        release_event.set()
        await asyncio.gather(t1, t2, t3)

    asyncio.run(_test())


# ------------------------------------------------------------------------------
# Test 3: Maximum Concurrency Under Simultaneous Submissions
# ------------------------------------------------------------------------------

def test_maximum_concurrency():
    """Verify provider concurrency ceiling is strictly respected under burst submissions."""
    async def _test():
        async def handler(req: GenerationRequest):
            await asyncio.sleep(0.03)
            return GenerationResponse(
                request_id=req.request_id,
                response_text="ok",
                provider_name="fake",
                model_name="fake",
                total_latency=0.03,
            )

        provider = FakeModelProvider(generate_handler=handler)
        config = TrafficManagerConfig(max_concurrency=3, max_queue_size=20)
        manager = TrafficManager(provider=provider, config=config)

        # Submit 10 concurrent requests
        tasks = [
            manager.execute(GenerationRequest(prompt=f"req-{i}", request_id=f"r-{i}"))
            for i in range(10)
        ]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        assert provider.peak_active_calls <= 3
        metrics = manager.get_metrics()
        assert metrics.peak_in_flight <= 3
        assert metrics.successful_requests == 10

    asyncio.run(_test())


# ------------------------------------------------------------------------------
# Test 4: RPM Admission Under Concurrency
# ------------------------------------------------------------------------------

def test_rpm_admission_under_concurrency():
    """Verify concurrent requests cannot exceed configured local RPM limit."""
    async def _test():
        async def handler(req: GenerationRequest):
            await asyncio.sleep(0.01)
            return GenerationResponse(
                request_id=req.request_id,
                response_text="ok",
                provider_name="fake",
                model_name="fake",
                total_latency=0.01,
            )

        provider = FakeModelProvider(generate_handler=handler)
        # RPM limit 3, max_retries 0 to assert admission rejection
        config = TrafficManagerConfig(
            max_concurrency=5,
            rpm_limit=3,
            max_retries=0,
            max_queue_size=10,
        )
        manager = TrafficManager(provider=provider, config=config)

        tasks = [
            manager.execute(GenerationRequest(prompt=f"req-{i}", request_id=f"r-{i}"))
            for i in range(5)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successes = [r for r in results if isinstance(r, GenerationResponse)]
        failures = [r for r in results if isinstance(r, LocalRateLimitError)]

        assert len(successes) == 3
        assert len(failures) == 2
        for fail in failures:
            assert "RPM limit of 3 exceeded" in fail.message
            assert fail.status_code == 429

        metrics = manager.get_metrics()
        assert metrics.rate_limit_responses == 2
        assert metrics.successful_requests == 3

    asyncio.run(_test())


# ------------------------------------------------------------------------------
# Test 5: TPM Reservation Under Concurrency
# ------------------------------------------------------------------------------

def test_tpm_reservation_under_concurrency():
    """Verify conservative token reservations prevent concurrent requests from exceeding TPM."""
    async def _test():
        async def handler(req: GenerationRequest):
            await asyncio.sleep(0.02)
            return GenerationResponse(
                request_id=req.request_id,
                response_text="ok",
                provider_name="fake",
                model_name="fake",
                total_latency=0.02,
                token_usage=TokenUsage(prompt_tokens=20, completion_tokens=40, total_tokens=60),
            )

        provider = FakeModelProvider(generate_handler=handler)
        # TPM limit 100.
        # Request needs: estimate_prompt_tokens("short prompt" -> ~2 tokens) + max_tokens=60 => 62 tokens reservation.
        # 1st request takes 62 tokens (admitted).
        # 2nd request needs 62 tokens => 62 + 62 = 124 > 100 => rejected!
        config = TrafficManagerConfig(
            max_concurrency=5,
            tpm_limit=100,
            max_retries=0,
        )
        manager = TrafficManager(provider=provider, config=config)

        req1 = GenerationRequest(prompt="alpha prompt", max_tokens=60, request_id="r1")
        req2 = GenerationRequest(prompt="beta prompt", max_tokens=60, request_id="r2")

        results = await asyncio.gather(
            manager.execute(req1),
            manager.execute(req2),
            return_exceptions=True,
        )

        successes = [r for r in results if isinstance(r, GenerationResponse)]
        failures = [r for r in results if isinstance(r, LocalRateLimitError)]

        assert len(successes) == 1
        assert len(failures) == 1
        assert "TPM limit of 100 exceeded" in failures[0].message

    asyncio.run(_test())


# ------------------------------------------------------------------------------
# Test 6: Daily Budget Enforcement
# ------------------------------------------------------------------------------

def test_daily_budget_enforcement():
    """Verify daily request budget prevents submissions once exhausted."""
    async def _test():
        provider = FakeModelProvider()
        config = TrafficManagerConfig(
            max_concurrency=2,
            daily_request_budget=2,
            max_retries=0,
        )
        manager = TrafficManager(provider=provider, config=config)

        # 1st and 2nd should succeed
        res1 = await manager.execute(GenerationRequest(prompt="1", request_id="r1"))
        res2 = await manager.execute(GenerationRequest(prompt="2", request_id="r2"))
        assert res1.response_text is not None
        assert res2.response_text is not None

        # 3rd should be rejected due to daily budget
        with pytest.raises(LocalRateLimitError) as exc_info:
            await manager.execute(GenerationRequest(prompt="3", request_id="r3"))

        assert "Daily request budget of 2 exceeded" in exc_info.value.message
        metrics = manager.get_metrics()
        assert metrics.daily_completed_requests == 2
        assert metrics.rate_limit_responses == 1

    asyncio.run(_test())


# ------------------------------------------------------------------------------
# Test 7: Queue Deadline Expiration Without Provider Invocation
# ------------------------------------------------------------------------------

def test_queue_deadline_expiration_no_provider_call():
    """Verify request expiring in queue raises QueueTimeoutError and is never sent to provider."""
    async def _test():
        hold_event = asyncio.Event()

        async def handler(req: GenerationRequest):
            await hold_event.wait()
            return GenerationResponse(
                request_id=req.request_id,
                response_text="ok",
                provider_name="fake",
                model_name="fake",
                total_latency=0.1,
            )

        provider = FakeModelProvider(generate_handler=handler)
        config = TrafficManagerConfig(max_concurrency=1, max_queue_size=5)
        manager = TrafficManager(provider=provider, config=config)

        # Block provider with task 1
        t1 = asyncio.create_task(manager.execute(GenerationRequest(prompt="blocking", request_id="b1")))
        await asyncio.sleep(0.01)

        # Submit task 2 with short timeout=0.04s
        with pytest.raises(QueueTimeoutError) as exc_info:
            await manager.execute(
                GenerationRequest(prompt="queued", request_id="q1"),
                timeout=0.04,
            )

        assert "expired while waiting in queue" in exc_info.value.message or "expired in queue" in exc_info.value.message
        assert exc_info.value.phase == "queue"

        # Check provider was called ONLY for the blocking request
        assert provider.call_count == 1
        assert provider.call_history[0].request_id == "b1"

        # Release blocking task
        hold_event.set()
        await t1

        metrics = manager.get_metrics()
        assert metrics.queue_expired_requests == 1
        assert metrics.current_in_flight == 0

    asyncio.run(_test())


# ------------------------------------------------------------------------------
# Test 8: Execution Timeout and Cleanup
# ------------------------------------------------------------------------------

def test_execution_timeout_and_cleanup():
    """Verify request timing out during execution raises ExecutionTimeoutError and cleans capacity."""
    async def _test():
        async def hanging_handler(req: GenerationRequest):
            await asyncio.sleep(1.0)
            return GenerationResponse(
                request_id=req.request_id,
                response_text="never",
                provider_name="fake",
                model_name="fake",
                total_latency=1.0,
            )

        provider = FakeModelProvider(generate_handler=hanging_handler)
        config = TrafficManagerConfig(max_concurrency=2)
        manager = TrafficManager(provider=provider, config=config)

        with pytest.raises(ExecutionTimeoutError) as exc_info:
            await manager.execute(
                GenerationRequest(prompt="slow", request_id="s1"),
                timeout=0.05,
            )

        assert exc_info.value.phase == "execution"

        # Capacity and reservations must be completely released
        metrics = manager.get_metrics()
        assert metrics.current_in_flight == 0
        assert metrics.reserved_rpm == 0
        assert metrics.execution_timeouts == 1

        # A subsequent normal request must execute without being blocked
        provider.generate_handler = None
        resp = await manager.execute(GenerationRequest(prompt="fast", request_id="f1"), timeout=1.0)
        assert resp.response_text == "Default fake completion"

    asyncio.run(_test())


# ------------------------------------------------------------------------------
# Test 9: Cancellation While Queued
# ------------------------------------------------------------------------------

def test_cancellation_while_queued():
    """Verify caller cancellation while queued removes item cleanly with no orphaned entry."""
    async def _test():
        hold_event = asyncio.Event()

        async def handler(req: GenerationRequest):
            await hold_event.wait()
            return GenerationResponse(
                request_id=req.request_id,
                response_text="ok",
                provider_name="fake",
                model_name="fake",
                total_latency=0.1,
            )

        provider = FakeModelProvider(generate_handler=handler)
        config = TrafficManagerConfig(max_concurrency=1, max_queue_size=5)
        manager = TrafficManager(provider=provider, config=config)

        t1 = asyncio.create_task(manager.execute(GenerationRequest(prompt="1", request_id="r1")))
        await asyncio.sleep(0.01)

        t2 = asyncio.create_task(manager.execute(GenerationRequest(prompt="2", request_id="r2")))
        await asyncio.sleep(0.01)

        assert manager.get_metrics().queue_depth == 1

        # Cancel t2 while it is waiting in queue
        t2.cancel()
        with pytest.raises(asyncio.CancelledError):
            await t2

        # Verify queue is empty and metrics updated
        metrics = manager.get_metrics()
        assert metrics.queue_depth == 0
        assert metrics.client_cancellations == 1

        # Release t1
        hold_event.set()
        await t1

    asyncio.run(_test())


# ------------------------------------------------------------------------------
# Test 10: Cancellation While Executing
# ------------------------------------------------------------------------------

def test_cancellation_while_executing():
    """Verify caller cancellation while executing releases in-flight concurrency and reservation."""
    async def _test():
        started_event = asyncio.Event()

        async def handler(req: GenerationRequest):
            started_event.set()
            await asyncio.sleep(1.0)
            return GenerationResponse(
                request_id=req.request_id,
                response_text="ok",
                provider_name="fake",
                model_name="fake",
                total_latency=1.0,
            )

        provider = FakeModelProvider(generate_handler=handler)
        config = TrafficManagerConfig(max_concurrency=2)
        manager = TrafficManager(provider=provider, config=config)

        task = asyncio.create_task(manager.execute(GenerationRequest(prompt="c", request_id="c1")))
        await started_event.wait()

        # Task is now in-flight
        assert manager.get_metrics().current_in_flight == 1

        # Cancel task
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        # Capacity must be immediately restored to 0
        metrics = manager.get_metrics()
        assert metrics.current_in_flight == 0
        assert metrics.reserved_rpm == 0
        assert metrics.client_cancellations == 1

    asyncio.run(_test())


# ------------------------------------------------------------------------------
# Test 11: Successful Transient Retry
# ------------------------------------------------------------------------------

def test_successful_transient_retry():
    """Verify that transient server errors trigger bounded retry and eventual success."""
    async def _test():
        attempts = 0

        async def flaky_handler(req: GenerationRequest):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise ProviderServerError("500 Upstream temporary glitch", status_code=500)
            return GenerationResponse(
                request_id=req.request_id,
                response_text="recovered",
                provider_name="fake",
                model_name="fake",
                total_latency=0.02,
            )

        provider = FakeModelProvider(generate_handler=flaky_handler)
        config = TrafficManagerConfig(
            max_retries=2,
            initial_backoff_seconds=0.01,
            max_backoff_seconds=0.05,
        )
        manager = TrafficManager(provider=provider, config=config)

        resp = await manager.execute(GenerationRequest(prompt="hello", request_id="h1"))
        assert resp.response_text == "recovered"
        assert attempts == 2

        metrics = manager.get_metrics()
        assert metrics.provider_attempts == 2
        assert metrics.provider_retries == 1
        assert metrics.successful_requests == 1
        assert metrics.failed_requests == 0

    asyncio.run(_test())


# ------------------------------------------------------------------------------
# Test 12: Retry-After Handling
# ------------------------------------------------------------------------------

def test_retry_after_handling():
    """Verify that provider Retry-After header delay is respected by retry policy."""
    async def _test():
        attempts = 0

        async def rate_limited_handler(req: GenerationRequest):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise RateLimitError("Rate limit exceeded", retry_after=0.06)
            return GenerationResponse(
                request_id=req.request_id,
                response_text="rate limit cleared",
                provider_name="fake",
                model_name="fake",
                total_latency=0.01,
            )

        provider = FakeModelProvider(generate_handler=rate_limited_handler)
        config = TrafficManagerConfig(max_retries=1)
        manager = TrafficManager(provider=provider, config=config)

        start = time.monotonic()
        resp = await manager.execute(GenerationRequest(prompt="r", request_id="r_after"))
        elapsed = time.monotonic() - start

        assert resp.response_text == "rate limit cleared"
        assert attempts == 2
        assert elapsed >= 0.05  # Respected ~0.06s retry_after

    asyncio.run(_test())


# ------------------------------------------------------------------------------
# Test 13: No Retry for Authentication Errors
# ------------------------------------------------------------------------------

def test_no_retry_for_authentication_errors():
    """Verify non-transient authentication errors fail immediately without retrying."""
    async def _test():
        attempts = 0

        async def auth_fail_handler(req: GenerationRequest):
            nonlocal attempts
            attempts += 1
            raise AuthenticationError("Invalid API key", status_code=401)

        provider = FakeModelProvider(generate_handler=auth_fail_handler)
        config = TrafficManagerConfig(max_retries=3, initial_backoff_seconds=0.01)
        manager = TrafficManager(provider=provider, config=config)

        with pytest.raises(AuthenticationError) as exc_info:
            await manager.execute(GenerationRequest(prompt="secret", request_id="s1"))

        assert exc_info.value.status_code == 401
        assert attempts == 1  # Never retried

        metrics = manager.get_metrics()
        assert metrics.provider_attempts == 1
        assert metrics.provider_retries == 0
        assert metrics.failed_requests == 1

    asyncio.run(_test())


# ------------------------------------------------------------------------------
# Test 14: No Retry After Deadline Expiration
# ------------------------------------------------------------------------------

def test_no_retry_after_deadline_expiration():
    """Verify retry is aborted if backoff duration exceeds total request deadline."""
    async def _test():
        attempts = 0

        async def fail_handler(req: GenerationRequest):
            nonlocal attempts
            attempts += 1
            await asyncio.sleep(0.03)
            raise ProviderConnectionError("Connection dropped")

        provider = FakeModelProvider(generate_handler=fail_handler)
        # Backoff = 0.2s, but total timeout = 0.05s
        config = TrafficManagerConfig(
            max_retries=3,
            initial_backoff_seconds=0.2,
        )
        manager = TrafficManager(provider=provider, config=config)

        with pytest.raises(Exception):
            await manager.execute(
                GenerationRequest(prompt="timeout_retry", request_id="tr1"),
                timeout=0.05,
            )

        assert attempts == 1  # Did not retry because backoff exceeded remaining deadline

    asyncio.run(_test())


# ------------------------------------------------------------------------------
# Test 15: Streaming Forwards Chunks Incrementally
# ------------------------------------------------------------------------------

def test_streaming_forwards_chunks_incrementally():
    """Verify streaming chunks are yielded as they arrive, preserving StreamChunk contract."""
    async def _test():
        async def custom_stream(req: GenerationRequest):
            for i, word in enumerate(["Deep", "Mind", " "]):
                await asyncio.sleep(0.02)
                yield StreamChunk(
                    request_id=req.request_id,
                    chunk_index=i,
                    delta_text=word,
                    is_final=(i == 2),
                    token_usage=TokenUsage(prompt_tokens=4, completion_tokens=3, total_tokens=7)
                    if i == 2
                    else None,
                )

        provider = FakeModelProvider(stream_handler=custom_stream)
        manager = TrafficManager(provider=provider)

        received_chunks = []
        timestamps = []

        start = time.monotonic()
        async for chunk in manager.stream(GenerationRequest(prompt="stream me", request_id="str1")):
            timestamps.append(time.monotonic() - start)
            received_chunks.append(chunk)

        assert len(received_chunks) == 3
        assert "".join(c.delta_text for c in received_chunks) == "DeepMind "
        assert received_chunks[-1].is_final is True
        assert received_chunks[-1].token_usage.total_tokens == 7

        # Chunks arrived incrementally over time
        assert timestamps[1] - timestamps[0] >= 0.015
        assert timestamps[2] - timestamps[1] >= 0.015

        metrics = manager.get_metrics()
        assert metrics.successful_requests == 1
        assert metrics.current_in_flight == 0

    asyncio.run(_test())


# ------------------------------------------------------------------------------
# Test 16: Streaming Early Closure Releases Capacity
# ------------------------------------------------------------------------------

def test_streaming_early_closure_releases_capacity():
    """Verify breaking early from stream releases concurrency slot and reservation cleanly."""
    async def _test():
        async def infinite_stream(req: GenerationRequest):
            idx = 0
            while True:
                await asyncio.sleep(0.02)
                yield StreamChunk(
                    request_id=req.request_id,
                    chunk_index=idx,
                    delta_text=f"tok_{idx} ",
                )
                idx += 1

        provider = FakeModelProvider(stream_handler=infinite_stream)
        config = TrafficManagerConfig(max_concurrency=1)
        manager = TrafficManager(provider=provider, config=config)

        # Read only 2 chunks and break early
        chunks = []
        async for chunk in manager.stream(GenerationRequest(prompt="loop", request_id="inf1")):
            chunks.append(chunk)
            if len(chunks) == 2:
                break

        assert len(chunks) == 2

        # Yield a tick to allow the event loop to execute the asyncgen finalizer
        await asyncio.sleep(0.01)

        # Concurrency must be restored to 0
        metrics = manager.get_metrics()
        assert metrics.current_in_flight == 0
        assert metrics.reserved_rpm == 0
        assert metrics.client_cancellations == 1

        # A subsequent request must execute without being blocked
        provider.stream_handler = None
        normal_resp = await manager.execute(GenerationRequest(prompt="next", request_id="n1"))
        assert normal_resp.response_text == "Default fake completion"

        # Also verify explicit generator aclose() releases capacity immediately
        stream_gen = manager.stream(GenerationRequest(prompt="aclose_test", request_id="ac1"))
        c1 = await anext(stream_gen)
        assert c1.delta_text == "Hello"
        assert manager.get_metrics().current_in_flight == 1

        await stream_gen.aclose()
        assert manager.get_metrics().current_in_flight == 0

    asyncio.run(_test())


# ------------------------------------------------------------------------------
# Test 17: Streaming Does Not Restart After Content Emitted
# ------------------------------------------------------------------------------

def test_streaming_does_not_restart_after_content_emitted():
    """Verify that a stream error occurring after initial tokens does NOT restart the stream."""
    async def _test():
        stream_attempts = 0

        async def failing_stream(req: GenerationRequest):
            nonlocal stream_attempts
            stream_attempts += 1
            yield StreamChunk(
                request_id=req.request_id,
                chunk_index=0,
                delta_text="Initial partial text",
            )
            await asyncio.sleep(0.01)
            raise ProviderConnectionError("Stream pipe broken")

        provider = FakeModelProvider(stream_handler=failing_stream)
        config = TrafficManagerConfig(max_retries=3)
        manager = TrafficManager(provider=provider, config=config)

        received_chunks = []
        with pytest.raises(StreamAlreadyStartedError) as exc_info:
            async for chunk in manager.stream(GenerationRequest(prompt="fail_stream", request_id="fs1")):
                received_chunks.append(chunk)

        assert len(received_chunks) == 1
        assert received_chunks[0].delta_text == "Initial partial text"
        assert "after tokens were emitted" in exc_info.value.message or "partial content" in exc_info.value.message

        # Stream was NOT retried
        assert stream_attempts == 1
        metrics = manager.get_metrics()
        assert metrics.provider_attempts == 1
        assert metrics.provider_retries == 0
        assert metrics.current_in_flight == 0

    asyncio.run(_test())


# ------------------------------------------------------------------------------
# Test 18: Metrics Accurately Reflect Request Outcomes
# ------------------------------------------------------------------------------

def test_metrics_accurately_reflect_outcomes():
    """Verify that get_metrics returns an exact snapshot across heterogeneous outcomes."""
    async def _test():
        provider = FakeModelProvider()
        config = TrafficManagerConfig(
            max_concurrency=2,
            max_queue_size=2,
            rpm_limit=10,
            daily_request_budget=10,
        )
        manager = TrafficManager(provider=provider, config=config)

        # 1. Success
        r1 = await manager.execute(GenerationRequest(prompt="ok1", request_id="m1"))
        assert r1.response_text is not None

        # 2. Queue full rejection
        hold = asyncio.Event()

        async def blocking(req: GenerationRequest):
            await hold.wait()
            return GenerationResponse(
                request_id=req.request_id,
                response_text="ok",
                provider_name="fake",
                model_name="fake",
                total_latency=0.01,
            )

        provider.generate_handler = blocking
        # Fill 2 concurrency + 2 queue
        t_c1 = asyncio.create_task(manager.execute(GenerationRequest(prompt="c1", request_id="c1")))
        t_c2 = asyncio.create_task(manager.execute(GenerationRequest(prompt="c2", request_id="c2")))
        await asyncio.sleep(0.01)
        t_q1 = asyncio.create_task(manager.execute(GenerationRequest(prompt="q1", request_id="q1")))
        t_q2 = asyncio.create_task(manager.execute(GenerationRequest(prompt="q2", request_id="q2")))
        await asyncio.sleep(0.01)

        # 5th submission should reject with QueueFullError
        with pytest.raises(QueueFullError):
            await manager.execute(GenerationRequest(prompt="extra", request_id="extra"))

        # Release hold
        hold.set()
        await asyncio.gather(t_c1, t_c2, t_q1, t_q2)

        # Snapshot evaluation
        snap = manager.get_metrics()
        assert snap.total_accepted == 5
        assert snap.queue_full_rejections == 1
        assert snap.successful_requests == 5  # m1 + c1 + c2 + q1 + q2
        assert snap.queue_capacity == 2
        assert snap.queue_depth == 0
        assert snap.current_in_flight == 0

    asyncio.run(_test())


# ------------------------------------------------------------------------------
# Test 19: Dynamic Reconfiguration
# ------------------------------------------------------------------------------

def test_dynamic_reconfiguration():
    """Verify runtime configuration adjustments (e.g. halving RPM) take immediate effect."""
    async def _test():
        provider = FakeModelProvider()
        config = TrafficManagerConfig(rpm_limit=10, max_concurrency=5)
        manager = TrafficManager(provider=provider, config=config)

        assert manager.config.rpm_limit == 10
        updated = manager.configure({"rpm_limit": 5, "daily_request_budget": 50})
        assert updated.rpm_limit == 5
        assert manager.config.daily_request_budget == 50

    asyncio.run(_test())


# ------------------------------------------------------------------------------
# Test 20: Closed Manager Rejection
# ------------------------------------------------------------------------------

def test_closed_traffic_manager_rejection():
    """Verify that requests submitted after manager closure are rejected."""
    async def _test():
        provider = FakeModelProvider()
        manager = TrafficManager(provider=provider)
        await manager.close()

        with pytest.raises(TrafficManagerClosedError):
            await manager.execute(GenerationRequest(prompt="closed", request_id="cl1"))

    asyncio.run(_test())


# ------------------------------------------------------------------------------
# Test 21: Token Estimation Heuristic
# ------------------------------------------------------------------------------

def test_token_estimation_heuristic():
    """Verify estimate_prompt_tokens produces documented ~1.33 tokens/word with proper floors."""
    req1 = GenerationRequest(prompt="Hello world")
    # 2 words * 4 // 3 = 2 tokens
    assert estimate_prompt_tokens(req1) == 2

    # 10 words -> 10 * 4 // 3 = 13 tokens
    req2 = GenerationRequest(prompt="one two three four five six seven eight nine ten")
    assert estimate_prompt_tokens(req2) == 13

    # Multi-message request
    req3 = GenerationRequest(
        messages=[
            ChatMessage(role="system", content="You are a helpful assistant."),  # 5 words -> 6 tokens
            ChatMessage(role="user", content="Explain attention mechanism."),  # 3 words -> 4 tokens
        ]
    )
    # Total words: 5 + 3 = 8 words * 4 // 3 = 10 tokens
    assert estimate_prompt_tokens(req3) == 10


# ------------------------------------------------------------------------------
# Test 22: TrafficManager Interoperability with GroqProvider (Mocked)
# ------------------------------------------------------------------------------

def test_traffic_manager_with_groq_provider():
    """Verify TrafficManager works seamlessly with GroqProvider adapter."""
    import groq
    from app.providers.groq_provider import GroqProvider

    async def _test():
        client = MagicMock(spec=groq.AsyncGroq)
        client.chat = MagicMock()
        client.chat.completions = MagicMock()

        mock_choice = MagicMock()
        mock_choice.message.content = "Groq generated content"
        mock_choice.finish_reason = "stop"

        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 15
        mock_usage.completion_tokens = 25
        mock_usage.total_tokens = 40

        mock_completion = MagicMock()
        mock_completion.id = "chatcmpl-mock-groq"
        mock_completion.choices = [mock_choice]
        mock_completion.usage = mock_usage

        client.chat.completions.create = AsyncMock(return_value=mock_completion)

        provider = GroqProvider(api_key="gsk_mock_test_key", client=client)
        manager = TrafficManager(provider=provider, config=TrafficManagerConfig(max_concurrency=2))

        req = GenerationRequest(prompt="Tell me about Transformers")
        resp = await manager.execute(req)

        assert resp.response_text == "Groq generated content"
        assert resp.provider_name == "groq"
        assert resp.token_usage.total_tokens == 40
        assert manager.get_metrics().successful_requests == 1

    asyncio.run(_test())



# ------------------------------------------------------------------------------
# Test 23: TrafficManager Interoperability with SimulatorProvider
# ------------------------------------------------------------------------------

def test_traffic_manager_with_simulator_provider():
    """Verify TrafficManager works seamlessly with SimulatorProvider adapter."""
    import httpx
    from app.providers.simulator_provider import SimulatorProvider

    async def _test():
        mock_http_client = MagicMock(spec=httpx.AsyncClient)

        mock_response_data = {
            "request_id": "sim-req-123",
            "response_text": "Simulator generated response text",
            "provider_name": "simulator",
            "model_name": "custom-standin-v1",
            "time_to_first_token": None,
            "total_latency": 0.05,
            "token_usage": {
                "prompt_tokens": 12,
                "completion_tokens": 18,
                "total_tokens": 30,
                "is_estimated": True,
            },
            "http_status": 200,
        }

        mock_http_response = MagicMock(spec=httpx.Response)
        mock_http_response.status_code = 200
        mock_http_response.is_error = False
        mock_http_response.json = MagicMock(return_value=mock_response_data)
        mock_http_response.raise_for_status = MagicMock()

        mock_http_client.post = AsyncMock(return_value=mock_http_response)

        provider = SimulatorProvider(client=mock_http_client)
        manager = TrafficManager(provider=provider, config=TrafficManagerConfig(max_concurrency=2))

        req = GenerationRequest(prompt="Simulate query")
        resp = await manager.execute(req)

        assert resp.response_text == "Simulator generated response text"
        assert resp.provider_name == "simulator"
        assert resp.token_usage.total_tokens == 30
        assert resp.token_usage.is_estimated is True
        assert manager.get_metrics().successful_requests == 1

    asyncio.run(_test())




# ------------------------------------------------------------------------------
# Test 24: Cancellation While Waiting for Settlement Lock Does Not Leak Capacity
# ------------------------------------------------------------------------------

def test_cancellation_during_settlement_lock_acquisition_does_not_leak():
    """Verify cancellation while waiting to acquire settlement lock releases reservations cleanly."""
    async def _test():
        started_event = asyncio.Event()

        async def slow_handler(req: GenerationRequest):
            started_event.set()
            await asyncio.sleep(1.0)
            return GenerationResponse(
                request_id=req.request_id,
                response_text="ok",
                provider_name="fake",
                model_name="fake",
                total_latency=1.0,
            )

        provider = FakeModelProvider(generate_handler=slow_handler)
        config = TrafficManagerConfig(max_concurrency=2)
        manager = TrafficManager(provider=provider, config=config)

        task = asyncio.create_task(manager.execute(GenerationRequest(prompt="c_lock", request_id="cl1")))
        await started_event.wait()

        # Task is actively in-flight
        assert manager.get_metrics().current_in_flight == 1
        assert manager.get_metrics().reserved_rpm == 1

        # Simulate lock contention by acquiring manager._lock externally
        await manager._lock.acquire()

        # Cancel the task while lock is held externally
        task.cancel()
        await asyncio.sleep(0.01)

        # Release the lock so task's shielded settlement can complete
        manager._lock.release()

        with pytest.raises(asyncio.CancelledError):
            await task

        # Concurrency and reservation must be 0 with no leaked slots
        metrics = manager.get_metrics()
        assert metrics.current_in_flight == 0
        assert metrics.reserved_rpm == 0
        assert metrics.client_cancellations == 1

        # A subsequent request must execute without impediment
        provider.generate_handler = None
        resp = await manager.execute(GenerationRequest(prompt="subsequent", request_id="sub1"))
        assert resp.response_text == "Default fake completion"

    asyncio.run(_test())


# ------------------------------------------------------------------------------
# Test 25: Provider Stalling on Later Chunk Triggers Stream Deadline
# ------------------------------------------------------------------------------

def test_stream_stalling_on_later_chunk_triggers_deadline():
    """Verify that a provider stalling on chunk 2 or later triggers ExecutionTimeoutError."""
    async def _test():
        async def stalling_stream(req: GenerationRequest):
            yield StreamChunk(
                request_id=req.request_id,
                chunk_index=0,
                delta_text="Chunk 1",
            )
            # Stall indefinitely before yielding chunk 2
            await asyncio.sleep(2.0)
            yield StreamChunk(
                request_id=req.request_id,
                chunk_index=1,
                delta_text="Chunk 2",
            )

        provider = FakeModelProvider(stream_handler=stalling_stream)
        manager = TrafficManager(provider=provider)

        received_chunks = []
        # Total deadline 0.08s
        with pytest.raises(ExecutionTimeoutError) as exc_info:
            async for chunk in manager.stream(
                GenerationRequest(prompt="stall", request_id="st1"),
                timeout=0.08,
            ):
                received_chunks.append(chunk)

        assert len(received_chunks) == 1
        assert received_chunks[0].delta_text == "Chunk 1"
        assert exc_info.value.phase == "execution"

        metrics = manager.get_metrics()
        assert metrics.current_in_flight == 0
        assert metrics.reserved_rpm == 0
        assert metrics.execution_timeouts == 1

    asyncio.run(_test())


# ------------------------------------------------------------------------------
# Test 26: Provider Iterator Cleanup on Every Termination Path
# ------------------------------------------------------------------------------

def test_provider_iterator_cleanup_on_all_termination_paths():
    """Verify provider stream iterator aclose() is invoked across all termination modes."""
    class TrackedStream:
        def __init__(self, chunks: List[StreamChunk], error: Optional[Exception] = None, stall_at: Optional[int] = None):
            self.chunks = chunks
            self.error = error
            self.stall_at = stall_at
            self.idx = 0
            self.closed = False
            self.close_count = 0

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.stall_at is not None and self.idx == self.stall_at:
                await asyncio.sleep(5.0)
            if self.idx >= len(self.chunks):
                if self.error:
                    raise self.error
                raise StopAsyncIteration
            item = self.chunks[self.idx]
            self.idx += 1
            return item

        async def aclose(self):
            self.closed = True
            self.close_count += 1

    class DirectStreamProvider(BaseModelProvider):
        def __init__(self, stream_obj):
            self.stream_obj = stream_obj

        @property
        def provider_name(self) -> str:
            return "direct"

        @property
        def model_name(self) -> str:
            return "direct"

        async def generate(self, request: GenerationRequest) -> GenerationResponse:
            raise NotImplementedError

        async def stream(self, request: GenerationRequest) -> AsyncIterator[StreamChunk]:
            return self.stream_obj

    async def _test():
        # Case A: Normal completion
        s_norm = TrackedStream([StreamChunk(request_id="1", chunk_index=0, delta_text="A")])
        p1 = DirectStreamProvider(s_norm)
        m1 = TrafficManager(provider=p1)
        async for _ in m1.stream(GenerationRequest(prompt="norm")):
            pass
        assert s_norm.closed is True
        assert s_norm.close_count == 1

        # Case B: Early break
        s_break = TrackedStream([
            StreamChunk(request_id="2", chunk_index=0, delta_text="A"),
            StreamChunk(request_id="2", chunk_index=1, delta_text="B"),
        ])
        p2 = DirectStreamProvider(s_break)
        m2 = TrafficManager(provider=p2)
        async for _ in m2.stream(GenerationRequest(prompt="break")):
            break
        await asyncio.sleep(0.01)
        assert s_break.closed is True
        assert s_break.close_count == 1

        # Case C: Task cancellation
        s_cancel = TrackedStream([
            StreamChunk(request_id="3", chunk_index=0, delta_text="A"),
        ], stall_at=1)
        p3 = DirectStreamProvider(s_cancel)
        m3 = TrafficManager(provider=p3)

        async def stream_consumer():
            async for _ in m3.stream(GenerationRequest(prompt="cancel")):
                pass

        t_cancel = asyncio.create_task(stream_consumer())
        await asyncio.sleep(0.01)
        t_cancel.cancel()
        with pytest.raises(asyncio.CancelledError):
            await t_cancel
        assert s_cancel.closed is True
        assert s_cancel.close_count == 1

        # Case D: Provider error
        s_err = TrackedStream(
            [StreamChunk(request_id="4", chunk_index=0, delta_text="A")],
            error=ProviderServerError("Upstream stream crash"),
        )
        p4 = DirectStreamProvider(s_err)
        m4 = TrafficManager(provider=p4)
        with pytest.raises(StreamAlreadyStartedError):
            async for _ in m4.stream(GenerationRequest(prompt="err")):
                pass
        assert s_err.closed is True
        assert s_err.close_count == 1

        # Case E: Execution timeout
        s_timeout = TrackedStream(
            [StreamChunk(request_id="5", chunk_index=0, delta_text="A")],
            stall_at=1,
        )
        p5 = DirectStreamProvider(s_timeout)
        m5 = TrafficManager(provider=p5)
        with pytest.raises(ExecutionTimeoutError):
            async for _ in m5.stream(GenerationRequest(prompt="timeout"), timeout=0.04):
                pass
        assert s_timeout.closed is True
        assert s_timeout.close_count == 1

    asyncio.run(_test())


# ------------------------------------------------------------------------------
# Test 27: Empty First Chunk Allows Pre-Content Retry
# ------------------------------------------------------------------------------

def test_empty_first_chunk_allows_retry_on_failure():
    """Verify metadata/empty delta chunk does not disable pre-content retries on transient error."""
    async def _test():
        attempts = 0

        async def stream_flaky(req: GenerationRequest):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                # Emit empty/metadata chunk first
                yield StreamChunk(
                    request_id=req.request_id,
                    chunk_index=0,
                    delta_text="",
                )
                await asyncio.sleep(0.01)
                raise ProviderConnectionError("Dropped before actual content")
            else:
                yield StreamChunk(
                    request_id=req.request_id,
                    chunk_index=0,
                    delta_text="Recovered text content",
                    is_final=True,
                )

        provider = FakeModelProvider(stream_handler=stream_flaky)
        config = TrafficManagerConfig(max_retries=2, initial_backoff_seconds=0.01)
        manager = TrafficManager(provider=provider, config=config)

        collected = []
        async for chunk in manager.stream(GenerationRequest(prompt="retry_empty", request_id="re1")):
            if chunk.delta_text:
                collected.append(chunk.delta_text)

        assert collected == ["Recovered text content"]
        assert attempts == 2

        metrics = manager.get_metrics()
        assert metrics.provider_attempts == 2
        assert metrics.provider_retries == 1
        assert metrics.successful_requests == 1

    asyncio.run(_test())


# ------------------------------------------------------------------------------
# Test 28: Non-Empty First Chunk Disables Retries
# ------------------------------------------------------------------------------

def test_non_empty_first_chunk_disables_retries():
    """Verify that delivering a non-empty delta chunk strictly forbids transparent restarts."""
    async def _test():
        attempts = 0

        async def stream_partial(req: GenerationRequest):
            nonlocal attempts
            attempts += 1
            yield StreamChunk(
                request_id=req.request_id,
                chunk_index=0,
                delta_text="First real words",
            )
            await asyncio.sleep(0.01)
            raise ProviderConnectionError("Socket disconnected mid-stream")

        provider = FakeModelProvider(stream_handler=stream_partial)
        config = TrafficManagerConfig(max_retries=3, initial_backoff_seconds=0.01)
        manager = TrafficManager(provider=provider, config=config)

        collected = []
        with pytest.raises(StreamAlreadyStartedError) as exc_info:
            async for chunk in manager.stream(GenerationRequest(prompt="no_restart", request_id="nr1")):
                collected.append(chunk.delta_text)

        assert collected == ["First real words"]
        assert "after tokens were emitted" in exc_info.value.message or "partial content" in exc_info.value.message

        # Must not retry after non-empty text was emitted
        assert attempts == 1
        metrics = manager.get_metrics()
        assert metrics.provider_attempts == 1
        assert metrics.provider_retries == 0
        assert metrics.current_in_flight == 0

    asyncio.run(_test())
