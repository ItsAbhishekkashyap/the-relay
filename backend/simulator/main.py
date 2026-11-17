"""FastAPI application for the local custom stand-in model simulator."""

from typing import Dict, Any
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from app.providers.schemas import GenerationRequest, GenerationResponse
from simulator.config import SimulatorConfig
from simulator.service import SimulatorService

app = FastAPI(
    title="Custom Model Stand-in Simulator",
    description="Deterministic mock model service with configurable latency, rate limits, failures, and concurrency.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global singleton service instance
simulator_service = SimulatorService()


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Lightweight health check endpoint."""
    return {"status": "ok", "service": "custom-model-simulator"}


@app.get("/status")
async def status_endpoint() -> Dict[str, Any]:
    """Observability endpoint returning in-flight requests, limits, usage, and metrics."""
    return simulator_service.get_status()


@app.get("/admin/config")
async def get_config() -> Dict[str, Any]:
    """Return the complete current simulator configuration."""
    return simulator_service.config.model_dump()


@app.post("/admin/configure")
async def configure_simulator(updates: Dict[str, Any]) -> Dict[str, Any]:
    """Dynamically update simulator behavior (latencies, limits, failure modes)."""
    try:
        new_config = simulator_service.configure(updates)
        return {
            "status": "updated",
            "config": new_config.model_dump(),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid configuration update: {str(e)}")


@app.post("/admin/reset")
async def reset_simulator() -> Dict[str, Any]:
    """Reset simulator counters and in-flight state."""
    simulator_service.reset()
    return {"status": "reset_successful", "current_state": simulator_service.get_status()}


@app.post("/admin/reset-config")
async def reset_config_endpoint() -> Dict[str, Any]:
    """Reset configuration parameters to default calibrated values."""
    new_config = simulator_service.reset_config()
    return {"status": "config_reset", "config": new_config.model_dump()}


@app.post(
    "/v1/chat/completions",
    response_model=GenerationResponse,
    responses={
        429: {"description": "Rate limit, budget, or concurrency exceeded"},
        500: {"description": "Simulated server failure"},
    },
)
async def chat_completions(
    gen_request: GenerationRequest,
    raw_request: Request,
):
    """Handle chat completion requests in either standard or streaming mode."""
    if gen_request.stream:
        # Return HTTP Server-Sent Events stream
        return StreamingResponse(
            simulator_service.stream(
                request=gen_request,
                is_disconnected=raw_request.is_disconnected,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        # Standard non-streaming generation
        response = await simulator_service.generate(gen_request)
        return response


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("simulator.main:app", host="127.0.0.1", port=8001, reload=False)

