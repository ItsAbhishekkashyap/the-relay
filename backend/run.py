"""Convenience entrypoint script for running The Relay backend on Render or locally."""

import os
import uvicorn
from app.config import AppSettings

if __name__ == "__main__":
    settings = AppSettings()
    port = int(os.getenv("PORT", settings.port))
    host = os.getenv("HOST", settings.host)
    
    print(f"Starting The Relay FastAPI Backend on {host}:{port} (provider: {settings.model_provider})...")
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=settings.debug,
    )
