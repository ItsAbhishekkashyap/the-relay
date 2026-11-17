"""Main FastAPI application entry point for The Relay research assistant."""

from contextlib import asynccontextmanager
import logging
from typing import Any, AsyncIterator, Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import AppSettings
from app.providers.base import BaseModelProvider
from app.providers.factory import create_model_provider
from app.retrieval.factory import create_hybrid_retriever
from app.retrieval.hybrid_retriever import HybridRetriever
from app.traffic.config import TrafficManagerConfig
from app.traffic.manager import TrafficManager
from app.workflow.graph import ResearchAssistantWorkflow, build_research_workflow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def create_app(
    settings: Optional[AppSettings] = None,
    workflow: Optional[ResearchAssistantWorkflow] = None,
    traffic_manager: Optional[TrafficManager] = None,
    retriever: Optional[HybridRetriever] = None,
    provider: Optional[BaseModelProvider] = None,
) -> FastAPI:
    """Create and configure the FastAPI research assistant application.

    Supports dependency injection for testing and flexible environment configuration.

    Args:
        settings: Application settings. If None, loaded from environment/.env.
        workflow: Optional pre-configured workflow (overrides startup initialization).
        traffic_manager: Optional pre-configured TrafficManager.
        retriever: Optional pre-configured HybridRetriever.
        provider: Optional pre-configured BaseModelProvider.

    Returns:
        Configured FastAPI application instance.
    """
    app_settings = settings or AppSettings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Manage application startup and shutdown lifecycle resources."""
        logger.info("Initializing The Relay Research Assistant application...")
        app.state.settings = app_settings
        app.state.ready = False

        # 1. Startup: Initialize components if not already injected
        try:
            # Retriever initialization
            if not hasattr(app.state, "retriever") or app.state.retriever is None:
                logger.info("Initializing persistent HybridRetriever indexes...")
                app.state.retriever = retriever or create_hybrid_retriever(app_settings)

            # Provider initialization
            if not hasattr(app.state, "provider") or app.state.provider is None:
                logger.info(f"Configuring model provider: '{app_settings.model_provider}'...")
                app.state.provider = provider or create_model_provider(app_settings)

            # Traffic Manager initialization
            if not hasattr(app.state, "traffic_manager") or app.state.traffic_manager is None:
                logger.info("Initializing TrafficManager...")
                tm_config = TrafficManagerConfig()
                app.state.traffic_manager = traffic_manager or TrafficManager(
                    provider=app.state.provider,
                    config=tm_config,
                )

            # Workflow initialization
            if not hasattr(app.state, "workflow") or app.state.workflow is None:
                logger.info("Compiling LangGraph research assistant workflow...")
                app.state.workflow = workflow or build_research_workflow(
                    retriever=app.state.retriever,
                    traffic_manager=app.state.traffic_manager,
                )

            app.state.ready = True
            logger.info("All application components successfully initialized and ready.")

        except Exception as exc:
            logger.critical(f"Application startup initialization failed: {exc}", exc_info=True)
            app.state.ready = False
            app.state.startup_error = str(exc)
            # Re-raise so FastAPI/Uvicorn reports startup failure
            raise

        yield

        # 2. Shutdown: Clean up resources
        logger.info("Initiating graceful application shutdown...")
        app.state.ready = False

        # Close TrafficManager
        tm = getattr(app.state, "traffic_manager", None)
        if tm is not None and hasattr(tm, "close"):
            try:
                logger.info("Closing TrafficManager...")
                await tm.close()
            except Exception as exc:
                logger.warning(f"Error while closing TrafficManager: {exc}")

        # Close Provider if client owned (e.g. SimulatorProvider)
        prov = getattr(app.state, "provider", None)
        if prov is not None and hasattr(prov, "aclose"):
            try:
                logger.info("Closing model provider HTTP client...")
                await prov.aclose()
            except Exception as exc:
                logger.warning(f"Error while closing provider client: {exc}")

        logger.info("The Relay application shutdown complete.")

    app = FastAPI(
        title="The Relay Research Assistant API",
        description=(
            "Evidence-grounded question answering API powered by LangGraph, "
            "Hybrid Retrieval, and async Traffic Management across 3 arXiv papers."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    # Enable CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Pre-seed state with injected components if provided
    if workflow is not None:
        app.state.workflow = workflow
    if traffic_manager is not None:
        app.state.traffic_manager = traffic_manager
    if retriever is not None:
        app.state.retriever = retriever
    if provider is not None:
        app.state.provider = provider
    app.state.settings = app_settings

    # Include routes
    app.include_router(router)

    return app


# Default application instance for Uvicorn ASGI server
app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = AppSettings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
