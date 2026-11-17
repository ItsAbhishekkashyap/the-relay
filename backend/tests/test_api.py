"""Focused API integration tests for The Relay research assistant FastAPI service."""

import asyncio
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.schemas import ALLOWED_PAPER_IDS, AskResponse
from app.config import AppSettings
from app.main import create_app
from app.providers.base import ModelProviderError
from app.providers.schemas import ErrorCategory
from app.traffic.errors import ExecutionTimeoutError, QueueFullError
from app.workflow.schemas import Citation, FinalResponse, RetrievedDocument


@pytest.fixture
def mock_retriever() -> MagicMock:
    """Mock HybridRetriever to avoid disk I/O and embedding computations in API tests."""
    retriever = MagicMock()
    retriever.retrieve = MagicMock(return_value=[])
    return retriever


@pytest.fixture
def mock_traffic_manager() -> MagicMock:
    """Mock TrafficManager with provider properties and async close."""
    tm = MagicMock()
    tm.provider.provider_name = "simulator"
    tm.provider.model_name = "simulator/mock-model-v1"
    tm.close = AsyncMock()
    return tm


@pytest.fixture
def sample_verified_final_response() -> FinalResponse:
    """Sample verified FinalResponse contract."""
    return FinalResponse(
        question="How does the Transformer architecture use self-attention?",
        answer="The Transformer computes scaled dot-product attention [Attention Is All You Need, arXiv:1706.03762v7, p. 3, Section 3.2].",
        is_refusal=False,
        refusal_reason=None,
        citations=[
            Citation(
                raw_text="[Attention Is All You Need, arXiv:1706.03762v7, p. 3, Section 3.2]",
                paper_title="Attention Is All You Need",
                paper_id="1706.03762v7",
                page_number=3,
                section="3.2",
                is_verified=True,
            )
        ],
        retrieved_sources=[
            RetrievedDocument(
                chunk_id="chunk_1",
                paper_id="1706.03762v7",
                paper_title="Attention Is All You Need",
                arxiv_id="1706.03762",
                paper_version="v7",
                page_number=3,
                page_numbers=[3],
                section="3.2",
                content="Scaled dot-product attention is computed as softmax(QK^T / sqrt(d_k))V.",
                score=0.045,
                retrieval_channels=["dense", "bm25"],
            )
        ],
        verification_status="verified",
        correction_occurred=False,
        workflow_metadata={"correction_attempts": 0, "retrieved_chunk_count": 1},
    )


@pytest.fixture
def sample_refusal_final_response() -> FinalResponse:
    """Sample refusal FinalResponse contract."""
    reason = "The query appears to be out-of-domain for the 3 target papers."
    return FinalResponse(
        question="What is the recipe for baking chocolate brownies?",
        answer=f"I am unable to answer this research question from the three target papers.\nReason: {reason}",
        is_refusal=True,
        refusal_reason=reason,
        citations=[],
        retrieved_sources=[],
        verification_status="refused",
        correction_occurred=False,
        workflow_metadata={"correction_attempts": 0, "retrieved_chunk_count": 0},
    )


@pytest.fixture
def test_app(
    mock_retriever: MagicMock,
    mock_traffic_manager: MagicMock,
    sample_verified_final_response: FinalResponse,
) -> FastAPI:
    """Configured test application with mock workflow, retriever, and traffic manager."""
    mock_workflow = MagicMock()
    mock_workflow.ainvoke = AsyncMock(
        return_value={"final_response": sample_verified_final_response}
    )

    settings = AppSettings(model_provider="simulator")
    return create_app(
        settings=settings,
        workflow=mock_workflow,
        traffic_manager=mock_traffic_manager,
        retriever=mock_retriever,
    )


# --------------------------------------------------------------------------
# Test 1: Health endpoint
# --------------------------------------------------------------------------


def test_health_endpoint(test_app: FastAPI):
    """GET /health must return 200 OK with service identifier."""
    with TestClient(test_app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "relay-research-assistant"


# --------------------------------------------------------------------------
# Test 2: Readiness endpoint
# --------------------------------------------------------------------------


def test_readiness_endpoint_ready(test_app: FastAPI):
    """GET /ready must return 200 OK and component statuses when initialized."""
    with TestClient(test_app) as client:
        resp = client.get("/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
        assert data["provider"] == "simulator"
        assert data["components"]["retriever"] == "initialized"
        assert data["components"]["traffic_manager"] == "initialized"
        assert data["components"]["workflow"] == "initialized"


def test_readiness_endpoint_not_ready():
    """GET /ready must return 503 Service Unavailable when components are not ready."""
    unready_app = create_app()
    # Bypass lifespan so components remain unready
    client = TestClient(unready_app)
    resp = client.get("/ready")
    assert resp.status_code == 503
    data = resp.json()
    assert "detail" in data


# --------------------------------------------------------------------------
# Test 3: Valid research question
# --------------------------------------------------------------------------


def test_valid_research_question(test_app: FastAPI):
    """POST /v1/ask with valid input must return grounded answer with citations."""
    with TestClient(test_app) as client:
        payload = {
            "question": "How does the Transformer architecture use self-attention?",
            "paper_filter": "1706.03762v7",
        }
        resp = client.post("/v1/ask", json=payload)
        assert resp.status_code == 200
        data = resp.json()

        # Validate response contract
        assert data["question"] == payload["question"]
        assert "scaled dot-product" in data["answer"].lower()
        assert data["status"] == "verified"
        assert len(data["citations"]) == 1
        assert data["citations"][0]["paper_id"] == "1706.03762v7"
        assert len(data["retrieved_passages"]) == 1
        assert data["provider"] == "simulator"
        assert "request_id" in data
        assert data["refusal_reason"] is None


# --------------------------------------------------------------------------
# Test 4: Insufficient evidence and refusal response
# --------------------------------------------------------------------------


def test_insufficient_evidence_and_refusal_response(
    mock_retriever: MagicMock,
    mock_traffic_manager: MagicMock,
    sample_refusal_final_response: FinalResponse,
):
    """POST /v1/ask must return 200 with status='refused' when evidence is insufficient."""
    mock_workflow = MagicMock()
    mock_workflow.ainvoke = AsyncMock(
        return_value={"final_response": sample_refusal_final_response}
    )

    app = create_app(
        workflow=mock_workflow,
        traffic_manager=mock_traffic_manager,
        retriever=mock_retriever,
    )

    with TestClient(app) as client:
        payload = {"question": "What is the recipe for baking chocolate brownies?"}
        resp = client.post("/v1/ask", json=payload)
        assert resp.status_code == 200
        data = resp.json()

        assert data["status"] == "refused"
        assert "unable to answer" in data["answer"].lower()
        assert data["refusal_reason"] is not None
        assert "out-of-domain" in data["refusal_reason"].lower()
        assert len(data["citations"]) == 0


# --------------------------------------------------------------------------
# Test 5: Invalid request body
# --------------------------------------------------------------------------


def test_invalid_request_body_empty_question(test_app: FastAPI):
    """POST /v1/ask must reject empty or whitespace-only question."""
    with TestClient(test_app) as client:
        resp = client.post("/v1/ask", json={"question": "   \n\t  "})
        assert resp.status_code == 422
        assert "question" in str(resp.json())


def test_invalid_request_body_missing_question(test_app: FastAPI):
    """POST /v1/ask must reject payload without required question field."""
    with TestClient(test_app) as client:
        resp = client.post("/v1/ask", json={})
        assert resp.status_code == 422


# --------------------------------------------------------------------------
# Test 6: Invalid paper filter
# --------------------------------------------------------------------------


def test_invalid_paper_filter(test_app: FastAPI):
    """POST /v1/ask must reject unsupported or invented paper_filter."""
    with TestClient(test_app) as client:
        payload = {
            "question": "How does attention work?",
            "paper_filter": "invented_paper_9999.0000",
        }
        resp = client.post("/v1/ask", json=payload)
        assert resp.status_code == 422
        data = resp.json()
        assert "paper_filter" in str(data)


def test_valid_paper_filters_accepted(
    mock_retriever: MagicMock,
    mock_traffic_manager: MagicMock,
    sample_verified_final_response: FinalResponse,
):
    """All approved paper IDs must pass request validation."""
    mock_workflow = MagicMock()
    mock_workflow.ainvoke = AsyncMock(
        return_value={"final_response": sample_verified_final_response}
    )
    app = create_app(
        workflow=mock_workflow,
        traffic_manager=mock_traffic_manager,
        retriever=mock_retriever,
    )

    with TestClient(app) as client:
        for pid in ["1706.03762v7", "2410.00037v1", "2507.07955v2"]:
            resp = client.post("/v1/ask", json={"question": "Valid query", "paper_filter": pid})
            assert resp.status_code == 200


# --------------------------------------------------------------------------
# Test 7: Provider error handling
# --------------------------------------------------------------------------


def test_provider_error_handling(
    mock_retriever: MagicMock,
    mock_traffic_manager: MagicMock,
):
    """Upstream ModelProviderError must be mapped to appropriate HTTP error status."""
    mock_workflow = MagicMock()
    mock_workflow.ainvoke = AsyncMock(
        side_effect=ModelProviderError(
            message="Upstream provider connection reset",
            error_category=ErrorCategory.CONNECTION_FAILURE,
            status_code=502,
            provider_name="groq",
        )
    )

    app = create_app(
        workflow=mock_workflow,
        traffic_manager=mock_traffic_manager,
        retriever=mock_retriever,
    )

    with TestClient(app) as client:
        resp = client.post("/v1/ask", json={"question": "Test query"})
        assert resp.status_code == 502
        assert "Model provider error" in resp.json()["detail"]


# --------------------------------------------------------------------------
# Test 8: Workflow timeout or deadline handling
# --------------------------------------------------------------------------


def test_workflow_timeout_handling(
    mock_retriever: MagicMock,
    mock_traffic_manager: MagicMock,
):
    """ExecutionTimeoutError must be mapped to HTTP 504 Gateway Timeout."""
    mock_workflow = MagicMock()
    mock_workflow.ainvoke = AsyncMock(
        side_effect=ExecutionTimeoutError("Execution deadline exceeded after 30.0s")
    )

    app = create_app(
        workflow=mock_workflow,
        traffic_manager=mock_traffic_manager,
        retriever=mock_retriever,
    )

    with TestClient(app) as client:
        resp = client.post("/v1/ask", json={"question": "Test query"})
        assert resp.status_code == 504
        assert "timed out" in resp.json()["detail"].lower()


# --------------------------------------------------------------------------
# Test 9: Application startup and shutdown
# --------------------------------------------------------------------------


def test_application_startup_and_shutdown(
    mock_retriever: MagicMock,
    mock_traffic_manager: MagicMock,
):
    """Lifespan must properly initialize ready flag on start and close resources on exit."""
    mock_workflow = MagicMock()
    app = create_app(
        workflow=mock_workflow,
        traffic_manager=mock_traffic_manager,
        retriever=mock_retriever,
    )

    assert getattr(app.state, "ready", False) is False

    with TestClient(app) as client:
        # After entering context, startup completed
        assert app.state.ready is True
        health_resp = client.get("/health")
        assert health_resp.status_code == 200

    # After exiting context, shutdown completed
    assert app.state.ready is False
    mock_traffic_manager.close.assert_called_once()


# --------------------------------------------------------------------------
# Test 10: Multiple requests reusing initialized application resources
# --------------------------------------------------------------------------


def test_multiple_requests_reusing_resources(
    mock_retriever: MagicMock,
    mock_traffic_manager: MagicMock,
    sample_verified_final_response: FinalResponse,
):
    """Multiple sequential requests must reuse the same initialized workflow and components."""
    mock_workflow = MagicMock()
    mock_workflow.ainvoke = AsyncMock(
        return_value={"final_response": sample_verified_final_response}
    )

    app = create_app(
        workflow=mock_workflow,
        traffic_manager=mock_traffic_manager,
        retriever=mock_retriever,
    )

    with TestClient(app) as client:
        initial_workflow = app.state.workflow
        initial_traffic_manager = app.state.traffic_manager
        initial_retriever = app.state.retriever

        for i in range(5):
            resp = client.post(
                "/v1/ask",
                json={"question": f"Question {i}: How does multi-head attention work?"},
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == "verified"

            # Assert identical component instances remain bound across requests
            assert app.state.workflow is initial_workflow
            assert app.state.traffic_manager is initial_traffic_manager
            assert app.state.retriever is initial_retriever

        # Assert workflow was invoked 5 times on the same instance
        assert mock_workflow.ainvoke.call_count == 5


# --------------------------------------------------------------------------
# Test 11: End-to-end SimulatorProvider integration
# --------------------------------------------------------------------------


def test_end_to_end_simulator_provider_flow():
    """Verify end-to-end flow with real SimulatorProvider connected to in-memory simulator app."""
    from app.providers.simulator_provider import SimulatorProvider
    from app.retrieval.hybrid_retriever import HybridRetrievalResult
    from app.traffic.config import TrafficManagerConfig
    from app.traffic.manager import TrafficManager
    from app.workflow.graph import build_research_workflow
    from simulator.main import app as simulator_app

    retriever = MagicMock()
    chunk = {
        "chunk_id": "c1",
        "paper_id": "1706.03762v7",
        "paper_title": "Attention Is All You Need",
        "arxiv_id": "1706.03762",
        "paper_version": "v7",
        "page_number": 3,
        "page_numbers": [3],
        "section": "3.2",
        "content": "The Transformer model architecture uses self-attention mechanisms to compute representations.",
        "score": 0.05,
        "retrieval_channels": ["dense"],
    }
    retriever.retrieve = MagicMock(
        return_value=HybridRetrievalResult([chunk], diagnostics={"successful_channels": ["dense"]})
    )

    sim_provider = SimulatorProvider(app=simulator_app)
    tm = TrafficManager(provider=sim_provider, config=TrafficManagerConfig())
    wf = build_research_workflow(retriever=retriever, traffic_manager=tm)

    app = create_app(workflow=wf, traffic_manager=tm, retriever=retriever, provider=sim_provider)

    with TestClient(app) as client:
        resp = client.post(
            "/v1/ask",
            json={"question": "How does the Transformer model compute representations?"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["provider"] == "simulator"
        assert "request_id" in data
        assert data["status"] in ("verified", "refused")


def test_metrics_endpoint_contract(mock_retriever, mock_traffic_manager):
    """Verify GET /v1/metrics returns full schema contract and valid initial metrics."""
    from app.traffic.config import TrafficManagerConfig
    from app.traffic.metrics import TrafficMetricsSnapshot

    mock_traffic_manager.config = TrafficManagerConfig(max_queue_size=50, max_concurrency=4)
    mock_traffic_manager.get_metrics.return_value = TrafficMetricsSnapshot(
        queue_capacity=50,
        queue_depth=3,
        total_accepted=15,
        total_rejected=1,
        queue_full_rejections=1,
        queue_expired_requests=0,
        execution_timeouts=0,
        current_in_flight=2,
        peak_in_flight=4,
        completed_rpm=10,
        reserved_rpm=2,
        completed_tpm=4500,
        reserved_tpm=800,
        daily_completed_requests=10,
        daily_reserved_requests=2,
        daily_budget=1000,
        provider_attempts=15,
        provider_retries=1,
        rate_limit_responses=1,
        client_cancellations=0,
        successful_requests=14,
        failed_requests=0,
        latency_stats={
            "sample_count": 14,
            "p50_ms": 950.0,
            "p95_ms": 1150.0,
            "p99_ms": 1280.0,
            "avg_ms": 980.5,
            "min_ms": 820.0,
            "max_ms": 1300.0,
        },
    )

    app = create_app(
        workflow=MagicMock(),
        traffic_manager=mock_traffic_manager,
        retriever=mock_retriever,
        provider=mock_traffic_manager.provider,
    )

    with TestClient(app) as client:
        resp = client.get("/v1/metrics")
        assert resp.status_code == 200
        data = resp.json()

        # Timestamp and provider
        assert "timestamp" in data
        assert data["provider"]["provider_name"] == "simulator"
        assert data["provider"]["model_name"] == "simulator/mock-model-v1"

        # Requests
        reqs = data["requests"]
        assert reqs["total_submitted"] == 16  # 15 accepted + 1 queue full
        assert reqs["successful"] == 14
        assert reqs["failed"] == 0
        assert reqs["rate_limited"] == 1
        assert reqs["retried"] == 1

        # Queue
        q = data["queue"]
        assert q["current_depth"] == 3
        assert q["capacity"] == 50
        assert q["utilization_pct"] == 6.0  # (3/50)*100

        # Concurrency
        conc = data["concurrency"]
        assert conc["active_in_flight"] == 2
        assert conc["peak_in_flight"] == 4
        assert conc["max_concurrency"] == 4

        # Latency
        lat = data["latency"]
        assert lat["available"] is True
        assert lat["sample_count"] == 14
        assert lat["p50_ms"] == 950.0
        assert lat["p95_ms"] == 1150.0
        assert lat["p99_ms"] == 1280.0


def test_metrics_endpoint_unavailable_latency(mock_retriever, mock_traffic_manager):
    """Verify GET /v1/metrics handles zero-sample latency cleanly without crashing."""
    from app.traffic.config import TrafficManagerConfig
    from app.traffic.metrics import TrafficMetricsSnapshot

    mock_traffic_manager.config = TrafficManagerConfig()
    mock_traffic_manager.get_metrics.return_value = TrafficMetricsSnapshot(
        queue_capacity=50,
        queue_depth=0,
        total_accepted=0,
        total_rejected=0,
        queue_full_rejections=0,
        queue_expired_requests=0,
        execution_timeouts=0,
        current_in_flight=0,
        peak_in_flight=0,
        completed_rpm=0,
        reserved_rpm=0,
        completed_tpm=0,
        reserved_tpm=0,
        daily_completed_requests=0,
        daily_reserved_requests=0,
        daily_budget=1000,
        provider_attempts=0,
        provider_retries=0,
        rate_limit_responses=0,
        client_cancellations=0,
        successful_requests=0,
        failed_requests=0,
        latency_stats=None,
    )

    app = create_app(
        workflow=MagicMock(),
        traffic_manager=mock_traffic_manager,
        retriever=mock_retriever,
        provider=mock_traffic_manager.provider,
    )

    with TestClient(app) as client:
        resp = client.get("/v1/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["latency"]["available"] is False
        assert data["latency"]["sample_count"] == 0
        assert data["latency"]["p50_ms"] is None


def test_metrics_endpoint_read_only_idempotence(mock_retriever, mock_traffic_manager):
    """Verify GET /v1/metrics is purely read-only and repeated calls produce identical snapshots."""
    from app.traffic.config import TrafficManagerConfig
    from app.traffic.metrics import TrafficMetricsSnapshot

    mock_traffic_manager.config = TrafficManagerConfig()
    mock_traffic_manager.get_metrics.return_value = TrafficMetricsSnapshot(
        queue_capacity=50,
        queue_depth=0,
        total_accepted=5,
        total_rejected=0,
        queue_full_rejections=0,
        queue_expired_requests=0,
        execution_timeouts=0,
        current_in_flight=0,
        peak_in_flight=1,
        completed_rpm=5,
        reserved_rpm=0,
        completed_tpm=1200,
        reserved_tpm=0,
        daily_completed_requests=5,
        daily_reserved_requests=0,
        daily_budget=1000,
        provider_attempts=5,
        provider_retries=0,
        rate_limit_responses=0,
        client_cancellations=0,
        successful_requests=5,
        failed_requests=0,
    )

    app = create_app(
        workflow=MagicMock(),
        traffic_manager=mock_traffic_manager,
        retriever=mock_retriever,
        provider=mock_traffic_manager.provider,
    )

    with TestClient(app) as client:
        r1 = client.get("/v1/metrics").json()
        r2 = client.get("/v1/metrics").json()
        assert r1["requests"] == r2["requests"]
        assert r1["queue"] == r2["queue"]
        assert r1["concurrency"] == r2["concurrency"]


def test_experiments_overview_endpoint(
    mock_traffic_manager: MagicMock,
    mock_retriever: MagicMock,
) -> None:
    """Test GET /v1/experiments/overview endpoint returns valid empirical catalog."""
    app = create_app(
        workflow=MagicMock(),
        traffic_manager=mock_traffic_manager,
        retriever=mock_retriever,
        provider=mock_traffic_manager.provider,
    )
    with TestClient(app) as client:
        response = client.get("/v1/experiments/overview")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "available"
        assert "pricing_basis" in data
        assert data["datasets"]["load_testing"]["available"] is True
        assert data["datasets"]["load_testing"]["total_records"] == 119
        assert data["datasets"]["retrieval_benchmarks"]["stage6"]["questions_count"] == 32
        assert data["datasets"]["retrieval_benchmarks"]["stage8b2"]["questions_count"] == 32


def test_experiments_load_endpoint(
    mock_traffic_manager: MagicMock,
    mock_retriever: MagicMock,
) -> None:
    """Test GET /v1/experiments/load endpoint returns load scenarios and fidelity comparison."""
    app = create_app(
        workflow=MagicMock(),
        traffic_manager=mock_traffic_manager,
        retriever=mock_retriever,
        provider=mock_traffic_manager.provider,
    )
    with TestClient(app) as client:
        response = client.get("/v1/experiments/load")
        assert response.status_code == 200
        data = response.json()
        assert data["available"] is True
        assert data["total_records"] == 119
        assert len(data["scenarios"]) == 7
        assert data["calibration_comparison"]["difference_pct"] == 0.27
        assert data["calibration_comparison"]["ttft_difference_pct"] == 0.38


def test_experiments_retrieval_endpoint(
    mock_traffic_manager: MagicMock,
    mock_retriever: MagicMock,
) -> None:
    """Test GET /v1/experiments/retrieval returns benchmark evaluations and deltas."""
    app = create_app(
        workflow=MagicMock(),
        traffic_manager=mock_traffic_manager,
        retriever=mock_retriever,
        provider=mock_traffic_manager.provider,
    )
    with TestClient(app) as client:
        response = client.get("/v1/experiments/retrieval")
        assert response.status_code == 200
        data = response.json()
        assert data["available"] is True
        assert data["denominators"]["total_questions"] == 32
        assert data["denominators"]["answerable_questions"] == 26
        assert len(data["stage6_vs_stage8b2_comparison"]) == 4
        assert len(data["top_k_scaling_stage8b2"]) == 3



