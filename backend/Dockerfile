# Production Dockerfile for The Relay FastAPI Backend on Render
FROM python:3.12-slim

# Prevent Python from buffering stdout/stderr and writing .pyc files
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000 \
    HOST=0.0.0.0

WORKDIR /app

# Install system runtime & build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install modern uv package installer
RUN pip install --no-cache-dir uv

# Copy dependency specifications first for optimal Docker layer caching
COPY requirements.txt pyproject.toml ./
RUN uv pip install --system --no-cache -r requirements.txt

# Pre-cache the SentenceTransformer embedding model so zero network calls happen on startup
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

# Copy application code, indexes, models, and data
COPY . .

# Expose default port
EXPOSE 8000

# Health check to ensure service readiness
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Launch Uvicorn honoring the dynamic PORT environment variable injected by Render
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
