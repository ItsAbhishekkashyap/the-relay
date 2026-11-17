"""Tests for the local custom stand-in model simulator and its client adapter."""

import asyncio
import time
import pytest
from httpx import AsyncClient, ASGITransport

from app.providers.schemas import GenerationRequest, ChatMessage
from app.providers.simulator_provider import SimulatorProvider
from app.providers.base import (
    RateLimitError,
    AuthenticationError,
    TimeoutError,
    ProviderServerError,
)
from simulator.main import app, simulator_service


@pytest.fixture(autouse=True)
def reset_service():
    """Reset simulator service before each test."""
    simulator_service.reset()
    simulator_service.configure({
        "base_delay_ms": 0.0,
        "jitter_ms": 0.0,
        "ttft_ms": 0.0,
        "ttft_stddev_ms": 0.0,
        "inter_chunk_delay_ms": 0.0,
        "failure_rate": 0.0,
        "deterministic_failure": None,
        "rpm_limit": 60,
        "tpm_limit": 40000,
        "daily_budget": 1000,
        "max_concurrent_requests": 10,
        "model_name": "simulator/mock-model-v1",
    })
    yield
    simulator_service.reset()


def test_simulator_health_and_status():
    """Health check and status observability endpoints must return valid metrics."""
    async def _test():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Health check
            resp = await client.get("/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert data["service"] == "custom-model-simulator"

            # Status check
            resp = await client.get("/status")
            assert resp.status_code == 200
            status = resp.json()
            assert status["status"] == "healthy"
            assert status["in_flight_requests"] == 0
            assert "configured_limits" in status
            assert "current_window" in status
            assert "daily_request_usage" in status
            assert "lifetime_metrics" in status
            assert status["lifetime_metrics"]["total_handled"] == 0

    asyncio.run(_test())


def test_simulator_normal_completion_contract():
    """Simulator and SimulatorProvider must fulfill GenerationResponse contract."""
    async def _test():
        provider = SimulatorProvider(app=app)
        try:
            req = GenerationRequest(
                request_id="sim-test-001",
                messages=[ChatMessage(role="user", content="What is Transformer architecture?")],
            )
            resp = await provider.generate(req)

            assert resp.request_id == "sim-test-001"
            assert "[Simulated Response]" in resp.response_text
            assert resp.provider_name == "simulator"
            assert resp.model_name == "simulator/mock-model-v1"
            assert resp.http_status == 200
            assert resp.total_latency >= 0.0
            assert resp.time_to_first_token is None  # Non-streaming cannot measure TTFT
            assert resp.token_usage is not None
            assert resp.token_usage.prompt_tokens > 0
            assert resp.token_usage.completion_tokens > 0
            assert resp.token_usage.total_tokens == resp.token_usage.prompt_tokens + resp.token_usage.completion_tokens
            assert resp.token_usage.is_estimated is True
        finally:
            await provider.aclose()

    asyncio.run(_test())


def test_simulator_configurable_latency():
    """Simulator must respect configured base delay and jitter."""
    async def _test():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Configure 100ms base delay
            cfg_resp = await client.post("/admin/configure", json={"base_delay_ms": 100.0, "jitter_ms": 0.0})
            assert cfg_resp.status_code == 200

            t0 = time.perf_counter()
            resp = await client.post(
                "/v1/chat/completions",
                json={"messages": [{"role": "user", "content": "Measure latency"}]},
            )
            elapsed = time.perf_counter() - t0

            assert resp.status_code == 200
            assert elapsed >= 0.095  # within margin of 100ms

    asyncio.run(_test())


def test_simulator_rate_limit_rpm():
    """Simulator must return 429 when RPM limit is reached, and provider must raise RateLimitError."""
    async def _test():
        simulator_service.configure({"rpm_limit": 3})
        provider = SimulatorProvider(app=app)

        try:
            for i in range(3):
                req = GenerationRequest(prompt=f"Query {i}")
                resp = await provider.generate(req)
                assert resp.http_status == 200

            # 4th request must be rate limited
            with pytest.raises(RateLimitError) as exc_info:
                await provider.generate(GenerationRequest(prompt="Query 4 (should exceed)"))

            err = exc_info.value
            assert err.status_code == 429
            assert err.error_category.value == "rate_limited"
            assert "RPM limit of 3 exceeded" in err.message
            assert err.retry_after is not None
            assert err.retry_after > 0
        finally:
            await provider.aclose()

    asyncio.run(_test())


def test_simulator_rate_limit_tpm():
    """Simulator must return 429 when TPM limit is reached."""
    async def _test():
        simulator_service.configure({"tpm_limit": 20})
        provider = SimulatorProvider(app=app)

        try:
            # Send a prompt that requires more than 20 tokens
            long_prompt = "word " * 30  # approx 40 tokens
            with pytest.raises(RateLimitError) as exc_info:
                await provider.generate(GenerationRequest(prompt=long_prompt))

            assert exc_info.value.status_code == 429
            assert "TPM limit of 20 exceeded" in exc_info.value.message
        finally:
            await provider.aclose()

    asyncio.run(_test())


def test_simulator_daily_budget_exhaustion():
    """Simulator must return 429 when daily budget is reached."""
    async def _test():
        simulator_service.configure({"daily_budget": 2})
        provider = SimulatorProvider(app=app)

        try:
            # 2 successful requests
            await provider.generate(GenerationRequest(prompt="Req 1"))
            await provider.generate(GenerationRequest(prompt="Req 2"))

            # 3rd request exhausts budget
            with pytest.raises(RateLimitError) as exc_info:
                await provider.generate(GenerationRequest(prompt="Req 3"))

            err = exc_info.value
            assert err.status_code == 429
            assert "Daily budget of 2 requests exhausted" in err.message
        finally:
            await provider.aclose()

    asyncio.run(_test())


def test_simulator_concurrency_limit():
    """Simulator must return overload error when max concurrent requests are exceeded."""
    async def _test():
        # Set max_concurrent = 1 and base delay = 150ms
        simulator_service.configure({"max_concurrent_requests": 1, "base_delay_ms": 150.0})
        provider = SimulatorProvider(app=app)

        try:
            req1 = GenerationRequest(prompt="Slow req 1")
            req2 = GenerationRequest(prompt="Concurrent req 2")

            task1 = asyncio.create_task(provider.generate(req1))
            # Yield control so task1 acquires slot and starts sleeping
            await asyncio.sleep(0.02)

            # Task 2 should immediately be rejected due to concurrency limit
            with pytest.raises(RateLimitError) as exc_info:
                await provider.generate(req2)

            assert exc_info.value.status_code == 429
            assert "concurrent requests reached" in exc_info.value.message

            # Wait for task1 to finish successfully
            resp1 = await task1
            assert resp1.http_status == 200
        finally:
            await provider.aclose()

    asyncio.run(_test())


def test_simulator_streaming_multiple_chunks():
    """Simulator must stream multiple SSE chunks with TTFT and inter-chunk delays."""
    async def _test():
        simulator_service.configure({"ttft_ms": 20.0, "inter_chunk_delay_ms": 10.0})
        provider = SimulatorProvider(app=app)

        try:
            req = GenerationRequest(
                request_id="stream-sim-99",
                prompt="Explain multi-head attention",
                stream=True,
            )

            chunks = []
            async for chunk in provider.stream(req):
                chunks.append(chunk)

            assert len(chunks) >= 2
            assert chunks[0].chunk_index == 0
            assert len(chunks[0].delta_text) > 0
            assert chunks[0].is_final is False
            assert chunks[0].time_offset >= 0.015

            # Final chunk
            final_chunk = chunks[-1]
            assert final_chunk.is_final is True
            assert final_chunk.token_usage is not None
            assert final_chunk.token_usage.is_estimated is True
        finally:
            await provider.aclose()

    asyncio.run(_test())


def test_simulator_deterministic_failures():
    """Deterministic failure modes must map to appropriate ModelProviderErrors."""
    async def _test():
        provider = SimulatorProvider(app=app)

        try:
            # 1. Server error
            simulator_service.configure({"deterministic_failure": "server_error"})
            with pytest.raises(ProviderServerError) as exc1:
                await provider.generate(GenerationRequest(prompt="fail test"))
            assert exc1.value.status_code == 500

            # 2. Auth error
            simulator_service.configure({"deterministic_failure": "auth_error"})
            with pytest.raises(AuthenticationError) as exc2:
                await provider.generate(GenerationRequest(prompt="fail test"))
            assert exc2.value.status_code == 401

            # 3. Rate limit
            simulator_service.configure({"deterministic_failure": "rate_limit"})
            with pytest.raises(RateLimitError) as exc3:
                await provider.generate(GenerationRequest(prompt="fail test"))
            assert exc3.value.status_code == 429
            assert exc3.value.retry_after == 30.0

            # 4. Timeout
            simulator_service.configure({"deterministic_failure": "timeout"})
            with pytest.raises(TimeoutError) as exc4:
                await provider.generate(GenerationRequest(prompt="fail test"))
            assert exc4.value.status_code == 504
        finally:
            await provider.aclose()

    asyncio.run(_test())


def test_simulator_client_cancellation():
    """Simulator must detect client cancellation and update metrics."""
    async def _test():
        simulator_service.configure({"ttft_ms": 200.0, "inter_chunk_delay_ms": 100.0})

        # Directly invoke stream with a mock disconnected callable
        disconnected = False

        async def check_disconnected():
            return disconnected

        req = GenerationRequest(prompt="Cancellation test", stream=True)
        stream_iter = simulator_service.stream(req, is_disconnected=check_disconnected)

        # Disconnect client before consuming
        disconnected = True
        chunks = []
        async for chunk in stream_iter:
            chunks.append(chunk)

        # Stream should terminate early
        assert len(chunks) == 0
        status = simulator_service.get_status()
        assert status["in_flight_requests"] == 0
        assert status["lifetime_metrics"]["client_cancellations"] >= 1

    asyncio.run(_test())


def test_simulator_admin_reset():
    """Admin reset endpoint must reset usage counters and metrics."""
    async def _test():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Make a call
            await client.post(
                "/v1/chat/completions",
                json={"messages": [{"role": "user", "content": "Before reset"}]},
            )

            status_before = (await client.get("/status")).json()
            assert status_before["lifetime_metrics"]["total_handled"] >= 1

            # Call reset
            reset_resp = await client.post("/admin/reset")
            assert reset_resp.status_code == 200

            status_after = (await client.get("/status")).json()
            assert status_after["lifetime_metrics"]["total_handled"] == 0
            assert status_after["in_flight_requests"] == 0

    asyncio.run(_test())


# =========================================================================
# Targeted Correctness Regression Tests (Admission Accounting & Cleanup)
# =========================================================================


def test_concurrent_rpm_admission_accounting():
    """Concurrent requests must atomically reserve RPM slots at admission time."""
    async def _test():
        # rpm_limit = 2, base_delay_ms = 100ms so requests stay in-flight
        simulator_service.configure({"rpm_limit": 2, "base_delay_ms": 100.0, "jitter_ms": 0.0})
        provider = SimulatorProvider(app=app)

        try:
            task1 = asyncio.create_task(provider.generate(GenerationRequest(prompt="Req 1")))
            task2 = asyncio.create_task(provider.generate(GenerationRequest(prompt="Req 2")))

            # Yield briefly so both tasks acquire slots and are currently in flight
            await asyncio.sleep(0.02)

            status = simulator_service.get_status()
            assert status["in_flight_requests"] == 2
            assert status["current_window"]["reserved_rpm"] == 2
            assert status["current_window"]["rpm_usage"] == 2

            # 3rd request launched while 1 & 2 are in-flight must be rejected immediately
            with pytest.raises(RateLimitError) as exc_info:
                await provider.generate(GenerationRequest(prompt="Req 3 (should be blocked by reserved RPM)"))

            assert exc_info.value.status_code == 429
            assert "RPM limit of 2 exceeded" in exc_info.value.message

            # Ensure the first two complete successfully
            res1 = await task1
            res2 = await task2
            assert res1.http_status == 200
            assert res2.http_status == 200

            # After completion, reserved_rpm is 0, completed_rpm is 2
            final_status = simulator_service.get_status()
            assert final_status["in_flight_requests"] == 0
            assert final_status["current_window"]["reserved_rpm"] == 0
            assert final_status["current_window"]["completed_rpm"] == 2
        finally:
            await provider.aclose()

    asyncio.run(_test())


def test_concurrent_daily_budget_admission_accounting():
    """Concurrent requests must atomically reserve daily budget at admission time."""
    async def _test():
        # daily_budget = 2, base_delay_ms = 100ms
        simulator_service.configure({"daily_budget": 2, "base_delay_ms": 100.0, "jitter_ms": 0.0})
        provider = SimulatorProvider(app=app)

        try:
            task1 = asyncio.create_task(provider.generate(GenerationRequest(prompt="Req 1")))
            task2 = asyncio.create_task(provider.generate(GenerationRequest(prompt="Req 2")))

            await asyncio.sleep(0.02)

            status = simulator_service.get_status()
            assert status["in_flight_requests"] == 2
            assert status["daily_request_usage"]["requests_used"] == 2

            # 3rd request launched concurrently must be rejected immediately by daily budget
            with pytest.raises(RateLimitError) as exc_info:
                await provider.generate(GenerationRequest(prompt="Req 3"))

            assert exc_info.value.status_code == 429
            assert "Daily budget of 2 requests exhausted" in exc_info.value.message

            res1 = await task1
            res2 = await task2
            assert res1.http_status == 200
            assert res2.http_status == 200
        finally:
            await provider.aclose()

    asyncio.run(_test())


def test_non_streaming_cancellation_releases_reservation():
    """Cancelling generate() must release in-flight slot and reservation exactly once."""
    async def _test():
        simulator_service.configure({"base_delay_ms": 250.0, "jitter_ms": 0.0, "rpm_limit": 1})
        req = GenerationRequest(request_id="cancel-test-1", prompt="Long request")

        task = asyncio.create_task(simulator_service.generate(req))
        await asyncio.sleep(0.02)

        # Slot acquired and reserved
        assert simulator_service.get_status()["in_flight_requests"] == 1
        assert simulator_service.get_status()["current_window"]["reserved_rpm"] == 1

        # Cancel the task
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        # Status must immediately show slot and reservation released exactly once
        status = simulator_service.get_status()
        assert status["in_flight_requests"] == 0
        assert status["current_window"]["reserved_rpm"] == 0
        assert status["current_window"]["completed_rpm"] == 0
        assert status["lifetime_metrics"]["client_cancellations"] == 1

        # Because the reservation was freed, a subsequent request with rpm_limit=1 can succeed
        next_resp = await simulator_service.generate(GenerationRequest(prompt="New request"))
        assert next_resp.http_status == 200
        assert simulator_service.get_status()["current_window"]["completed_rpm"] == 1

    asyncio.run(_test())


def test_non_streaming_error_releases_reservation():
    """Ordinary errors during generate() must release reservations without consuming quota."""
    async def _test():
        simulator_service.configure({"deterministic_failure": "server_error", "rpm_limit": 1})

        with pytest.raises(Exception):
            await simulator_service.generate(GenerationRequest(prompt="Failing request"))

        status = simulator_service.get_status()
        assert status["in_flight_requests"] == 0
        assert status["current_window"]["reserved_rpm"] == 0
        assert status["current_window"]["completed_rpm"] == 0
        assert status["lifetime_metrics"]["failures"] == 1

        # Capacity was not consumed by failed request
        simulator_service.configure({"deterministic_failure": None})
        resp = await simulator_service.generate(GenerationRequest(prompt="Follow-up request"))
        assert resp.http_status == 200

    asyncio.run(_test())


def test_streaming_generator_exit_cleanup():
    """Closing a stream generator early (client disconnect) must release reservations exactly once."""
    async def _test():
        simulator_service.configure({"ttft_ms": 20.0, "inter_chunk_delay_ms": 20.0, "rpm_limit": 1})
        req = GenerationRequest(prompt="Stream cancellation", stream=True)

        stream_gen = simulator_service.stream(req)

        # Consume only the first chunk
        first_chunk = await stream_gen.__anext__()
        assert "data:" in first_chunk

        # Verify active reservation while streaming
        assert simulator_service.get_status()["in_flight_requests"] == 1

        # Close generator early (triggers GeneratorExit)
        await stream_gen.aclose()

        # Slot and reservation must be cleanly released
        status = simulator_service.get_status()
        assert status["in_flight_requests"] == 0
        assert status["current_window"]["reserved_rpm"] == 0
        assert status["lifetime_metrics"]["client_cancellations"] == 1

    asyncio.run(_test())


def test_concurrent_tpm_reservation_accounting():
    """Concurrent requests must reserve prompt + output allowance and reject if TPM limit exceeded."""
    async def _test():
        # Set TPM limit = 60, base_delay = 100ms
        simulator_service.configure({"tpm_limit": 60, "base_delay_ms": 100.0, "jitter_ms": 0.0})
        provider = SimulatorProvider(app=app)

        try:
            # Each prompt has 5 words (~6 prompt tokens). With max_tokens=20, each reserves 26 tokens.
            # 2 concurrent requests reserve 26 * 2 = 52 tokens (<= 60 limit).
            task1 = asyncio.create_task(provider.generate(GenerationRequest(prompt="one two three four five", max_tokens=20)))
            task2 = asyncio.create_task(provider.generate(GenerationRequest(prompt="one two three four five", max_tokens=20)))

            await asyncio.sleep(0.02)

            status = simulator_service.get_status()
            assert status["in_flight_requests"] == 2
            assert status["current_window"]["reserved_tpm"] == 52

            # 3rd request also requiring 26 tokens (52 + 26 = 78 > 60) must be rejected immediately
            with pytest.raises(RateLimitError) as exc_info:
                await provider.generate(GenerationRequest(prompt="one two three four five", max_tokens=20))

            assert exc_info.value.status_code == 429
            assert "TPM limit of 60 exceeded" in exc_info.value.message

            # Ensure initial two tasks complete successfully
            res1 = await task1
            res2 = await task2
            assert res1.http_status == 200
            assert res2.http_status == 200

            # After completion, reserved_tpm is 0, and actual total tokens are in completed_tpm
            final_status = simulator_service.get_status()
            assert final_status["in_flight_requests"] == 0
            assert final_status["current_window"]["reserved_tpm"] == 0
            assert final_status["current_window"]["completed_tpm"] > 0
        finally:
            await provider.aclose()

    asyncio.run(_test())


def test_simulator_non_streaming_ttft_is_none():
    """Non-streaming simulator responses cannot measure TTFT and must represent it as None."""
    async def _test():
        provider = SimulatorProvider(app=app)
        try:
            resp = await provider.generate(GenerationRequest(prompt="Hello"))
            assert resp.time_to_first_token is None
            assert resp.total_latency >= 0.0
        finally:
            await provider.aclose()

    asyncio.run(_test())


def test_exact_lognormal_parameterization():
    """Verify calculate_lognormal_params achieves exact theoretical median and stddev to machine precision."""
    import math
    from simulator.service import calculate_lognormal_params

    # Representative configuration 1: Non-streaming latency baseline (M = 976.5 ms, S = 174.0 ms)
    m1, s1 = 976.5, 174.0
    mu1, sigma1 = calculate_lognormal_params(m1, s1)
    theo_median1 = math.exp(mu1)
    theo_var1 = (math.exp(sigma1**2) - 1.0) * math.exp(2.0 * mu1 + sigma1**2)
    theo_std1 = math.sqrt(theo_var1)

    assert math.isclose(theo_median1, m1, rel_tol=1e-12), f"Median mismatch: {theo_median1} vs {m1}"
    assert math.isclose(theo_std1, s1, rel_tol=1e-12), f"Stddev mismatch: {theo_std1} vs {s1}"

    # Representative configuration 2: Streaming TTFT baseline (M = 852.0 ms, S = 234.55 ms)
    m2, s2 = 852.0, 234.55
    mu2, sigma2 = calculate_lognormal_params(m2, s2)
    theo_median2 = math.exp(mu2)
    theo_var2 = (math.exp(sigma2**2) - 1.0) * math.exp(2.0 * mu2 + sigma2**2)
    theo_std2 = math.sqrt(theo_var2)

    assert math.isclose(theo_median2, m2, rel_tol=1e-12), f"TTFT Median mismatch: {theo_median2} vs {m2}"
    assert math.isclose(theo_std2, s2, rel_tol=1e-12), f"TTFT Stddev mismatch: {theo_std2} vs {s2}"

    # Representative configuration 3: Fast test configuration (M = 300.0 ms, S = 50.0 ms)
    m3, s3 = 300.0, 50.0
    mu3, sigma3 = calculate_lognormal_params(m3, s3)
    theo_median3 = math.exp(mu3)
    theo_var3 = (math.exp(sigma3**2) - 1.0) * math.exp(2.0 * mu3 + sigma3**2)
    theo_std3 = math.sqrt(theo_var3)

    assert math.isclose(theo_median3, m3, rel_tol=1e-12)
    assert math.isclose(theo_std3, s3, rel_tol=1e-12)

    # Edge case: zero standard deviation (deterministic delay)
    mu_zero, sigma_zero = calculate_lognormal_params(500.0, 0.0)
    assert math.isclose(math.exp(mu_zero), 500.0, rel_tol=1e-12)
    assert sigma_zero == 0.0


def test_lognormal_empirical_sampling_convergence():
    """Verify empirical random draws converge to theoretical median M and stddev S."""
    import random
    import numpy as np
    from simulator.service import calculate_lognormal_params

    # Target: Stage 4 real Groq characterization values
    target_m = 976.5
    target_s = 174.0
    mu, sigma = calculate_lognormal_params(target_m, target_s)

    # Deterministic seed for reproducible testing
    random.seed(42)
    sample_size = 100_000
    samples = [random.lognormvariate(mu, sigma) for _ in range(sample_size)]

    empirical_median = float(np.percentile(samples, 50))
    empirical_std = float(np.std(samples))

    # Empirical sample median should match target M within 0.5%
    median_rel_err = abs(empirical_median - target_m) / target_m
    assert median_rel_err < 0.005, f"Empirical median {empirical_median} differs from target {target_m} by {median_rel_err:.4%}"

    # Empirical sample stddev should match target S within 1.0%
    std_rel_err = abs(empirical_std - target_s) / target_s
    assert std_rel_err < 0.01, f"Empirical stddev {empirical_std} differs from target {target_s} by {std_rel_err:.4%}"

