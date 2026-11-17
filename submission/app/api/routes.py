"""FastAPI route definitions for health, readiness, and research question answering."""

from datetime import datetime, timezone
import logging
import uuid
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.schemas import (
    AskRequest,
    AskResponse,
    ConcurrencyStats,
    HealthResponse,
    LatencyStats,
    MetricsResponse,
    ProviderInfo,
    QueueStats,
    RateLimitStats,
    ReadyResponse,
    RequestStats,
)
from app.config import AppSettings
from app.providers.base import ModelProviderError
from app.traffic.errors import (
    ExecutionTimeoutError,
    QueueFullError,
    QueueTimeoutError,
    RequestTimeoutError,
    TrafficManagerError,
)
from app.traffic.manager import TrafficManager
from app.workflow.graph import ResearchAssistantWorkflow
from app.workflow.schemas import FinalResponse
from app.experiments.service import (
    get_experiments_overview,
    get_load_experiments,
    get_retrieval_experiments,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# --------------------------------------------------------------------------
# Dependency Providers
# --------------------------------------------------------------------------


def get_workflow(request: Request) -> ResearchAssistantWorkflow:
    """Retrieve initialized research assistant workflow from application state."""
    workflow = getattr(request.app.state, "workflow", None)
    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Research assistant workflow is not initialized.",
        )
    return workflow


def get_traffic_manager(request: Request) -> TrafficManager:
    """Retrieve initialized traffic manager from application state."""
    traffic_manager = getattr(request.app.state, "traffic_manager", None)
    if traffic_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Traffic manager is not initialized.",
        )
    return traffic_manager


def get_settings(request: Request) -> AppSettings:
    """Retrieve application settings from application state."""
    return getattr(request.app.state, "settings", AppSettings())


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Basic health check",
    tags=["System"],
)
async def health_check() -> HealthResponse:
    """Return basic service health status."""
    return HealthResponse(status="ok", service="relay-research-assistant")


@router.get(
    "/ready",
    response_model=ReadyResponse,
    summary="Readiness probe",
    tags=["System"],
)
async def readiness_check(request: Request) -> ReadyResponse:
    """Check whether required application components have initialized successfully.

    Does not trigger expensive model generation.
    """
    is_ready = getattr(request.app.state, "ready", False)
    traffic_manager = getattr(request.app.state, "traffic_manager", None)
    workflow = getattr(request.app.state, "workflow", None)
    retriever = getattr(request.app.state, "retriever", None)

    if not is_ready or traffic_manager is None or workflow is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "not_ready",
                "components": {
                    "retriever": "initialized" if retriever else "uninitialized",
                    "traffic_manager": "initialized" if traffic_manager else "uninitialized",
                    "workflow": "initialized" if workflow else "uninitialized",
                },
            },
        )

    provider = traffic_manager.provider
    return ReadyResponse(
        status="ready",
        provider=provider.provider_name,
        model=provider.model_name,
        components={
            "retriever": "initialized",
            "traffic_manager": "initialized",
            "workflow": "initialized",
        },
    )


@router.get(
    "/v1/metrics",
    response_model=MetricsResponse,
    summary="Operational system and traffic metrics",
    tags=["Observability"],
)
async def get_metrics(
    traffic_manager: TrafficManager = Depends(get_traffic_manager),
) -> MetricsResponse:
    """Return point-in-time runtime metrics from the TrafficManager and operational state.

    Read-only endpoint that does not alter traffic manager state or issue upstream calls.
    """
    snapshot = traffic_manager.get_metrics()
    provider = traffic_manager.provider
    config = traffic_manager.config

    utilization = (
        round((snapshot.queue_depth / snapshot.queue_capacity) * 100.0, 2)
        if snapshot.queue_capacity > 0
        else 0.0
    )

    lat_stats = snapshot.latency_stats
    if lat_stats and lat_stats.get("sample_count", 0) > 0:
        latency = LatencyStats(
            available=True,
            sample_count=lat_stats["sample_count"],
            measurement_scope="Provider execution duration via TrafficManager (rolling 1,000 requests)",
            p50_ms=lat_stats.get("p50_ms"),
            p95_ms=lat_stats.get("p95_ms"),
            p99_ms=lat_stats.get("p99_ms"),
            avg_ms=lat_stats.get("avg_ms"),
            min_ms=lat_stats.get("min_ms"),
            max_ms=lat_stats.get("max_ms"),
        )
    else:
        latency = LatencyStats(
            available=False,
            sample_count=0,
            measurement_scope="Provider execution duration via TrafficManager (rolling 1,000 requests)",
            p50_ms=None,
            p95_ms=None,
            p99_ms=None,
        )

    return MetricsResponse(
        timestamp=datetime.now(timezone.utc).isoformat(),
        provider=ProviderInfo(
            provider_name=provider.provider_name,
            model_name=provider.model_name,
        ),
        requests=RequestStats(
            total_submitted=snapshot.total_accepted + snapshot.queue_full_rejections,
            successful=snapshot.successful_requests,
            failed=snapshot.failed_requests,
            rate_limited=snapshot.rate_limit_responses,
            timed_out=snapshot.execution_timeouts + snapshot.queue_expired_requests,
            retried=snapshot.provider_retries,
            queue_rejections=snapshot.queue_full_rejections,
            client_cancellations=snapshot.client_cancellations,
        ),
        queue=QueueStats(
            current_depth=snapshot.queue_depth,
            capacity=snapshot.queue_capacity,
            utilization_pct=utilization,
        ),
        concurrency=ConcurrencyStats(
            active_in_flight=snapshot.current_in_flight,
            peak_in_flight=snapshot.peak_in_flight,
            max_concurrency=config.max_concurrency,
        ),
        rate_limits=RateLimitStats(
            rpm_limit=config.rpm_limit,
            tpm_limit=config.tpm_limit,
            completed_rpm=snapshot.completed_rpm,
            reserved_rpm=snapshot.reserved_rpm,
            completed_tpm=snapshot.completed_tpm,
            reserved_tpm=snapshot.reserved_tpm,
        ),
        latency=latency,
    )


@router.get(
    "/v1/experiments/overview",
    summary="Overview of available empirical experiment datasets",
    tags=["Experiments"],
)
async def experiments_overview() -> Dict[str, Any]:
    """Return catalog and metadata of completed empirical experiment runs."""
    return get_experiments_overview()


@router.get(
    "/v1/experiments/load",
    summary="Empirical load testing benchmarks across scenarios A through E",
    tags=["Experiments"],
)
async def load_experiments() -> Dict[str, Any]:
    """Return parsed results for load scenarios (steady, burst, overload, rate limit, budget).

    Includes real Groq characterization baseline vs simulator calibration comparison.
    """
    data = get_load_experiments()
    if not data.get("available", False):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=data.get("error", "Load experiment data unavailable."),
        )
    return data


@router.get(
    "/v1/experiments/retrieval",
    summary="Retrieval quality vs cost benchmark evaluations (Stage 6 and Stage 8B.2)",
    tags=["Experiments"],
)
async def retrieval_experiments(
    version: Optional[str] = None,
) -> Dict[str, Any]:
    """Return retrieval benchmarks across Dense, BM25, Hybrid RRF, and Full Hybrid.

    Supports filtering by version: 'stage6', 'stage8b2', or 'all' (default).
    """
    data = get_retrieval_experiments(version=version)
    if not data.get("available", False):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=data.get("error", "Retrieval experiment data unavailable."),
        )
    return data


@router.post(
    "/v1/ask",
    response_model=AskResponse,
    summary="Ask research question",
    tags=["Research"],
    responses={
        200: {"description": "Grounded answer or explicit refusal from target papers."},
        400: {"description": "Invalid question format or unsupported paper filter."},
        422: {"description": "Validation error for request payload."},
        502: {"description": "Upstream model provider failure."},
        503: {"description": "Traffic manager queue full or service unavailable."},
        504: {"description": "Request processing deadline or execution timeout exceeded."},
    },
)
async def ask_question(
    ask_req: AskRequest,
    workflow: ResearchAssistantWorkflow = Depends(get_workflow),
    traffic_manager: TrafficManager = Depends(get_traffic_manager),
) -> AskResponse:
    """Submit a natural language question to the research assistant workflow.

    Answers are grounded exclusively in the three approved arXiv papers:
    - 1706.03762v7 (Attention Is All You Need)
    - 2410.00037v1 (Moshi)
    - 2507.07955v2 (Dynamic Chunking)
    """
    request_id = str(uuid.uuid4())
    logger.info(f"Processing /v1/ask request {request_id}: query={ask_req.question[:80]!r}")

    workflow_input: Dict[str, Any] = {"question": ask_req.question}
    if ask_req.paper_filter:
        workflow_input["paper_filter"] = ask_req.paper_filter

    try:
        # Asynchronously invoke the LangGraph research assistant workflow
        result = await workflow.ainvoke(workflow_input)
        final: FinalResponse = result["final_response"]

        return AskResponse(
            request_id=request_id,
            question=final.question,
            answer=final.answer,
            status=final.verification_status,
            citations=final.citations,
            retrieved_passages=final.retrieved_sources,
            provider=traffic_manager.provider.provider_name,
            refusal_reason=final.refusal_reason,
            correction_occurred=final.correction_occurred,
            workflow_metadata=final.workflow_metadata,
        )

    except (ExecutionTimeoutError, QueueTimeoutError, RequestTimeoutError) as exc:
        logger.error(f"Request {request_id} timed out: {exc}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Request processing timed out: {exc}",
        )
    except QueueFullError as exc:
        logger.warning(f"Request {request_id} rejected due to full queue: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Request queue is currently at capacity: {exc}",
        )
    except ModelProviderError as exc:
        logger.error(f"Request {request_id} provider error: {exc.message}")
        raise HTTPException(
            status_code=exc.status_code or status.HTTP_502_BAD_GATEWAY,
            detail=f"Model provider error: {exc.message}",
        )
    except TrafficManagerError as exc:
        logger.error(f"Request {request_id} traffic manager error: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Traffic management error: {exc}",
        )
    except Exception as exc:
        logger.exception(f"Unexpected failure handling request {request_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal research assistant processing error: {exc}",
        )
