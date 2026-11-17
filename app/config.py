"""Application configuration management for the FastAPI service."""

import os
from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent


def _resolve_default_indexes_dir() -> Path:
    """Resolve data/indexes directory whether running from repo root or backend/."""
    candidates = [
        REPO_ROOT / "data" / "indexes",
        REPO_ROOT.parent / "data" / "indexes",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return REPO_ROOT / "data" / "indexes"


class AppSettings(BaseSettings):
    """Global application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Provider Selection: 'groq' or 'simulator'
    model_provider: str = Field(
        default="groq",
        description="Active model provider: 'groq' or 'simulator'.",
    )

    # Groq Provider Settings
    groq_api_key: Optional[str] = Field(
        default=None,
        description="Groq API key from environment.",
    )
    groq_model: Optional[str] = Field(
        default="openai/gpt-oss-120b",
        description="Groq model identifier.",
    )

    # Simulator Provider Settings
    simulator_base_url: str = Field(
        default="http://127.0.0.1:8001",
        description="HTTP URL for the local stand-in model simulator service.",
    )
    simulator_model: str = Field(
        default="simulator/mock-model-v1",
        description="Model name identifier for the simulator.",
    )
    simulator_timeout: float = Field(
        default=30.0,
        ge=1.0,
        description="Timeout for simulator HTTP requests in seconds.",
    )

    # Retrieval Index Directories
    indexes_base_dir: Path = Field(
        default_factory=_resolve_default_indexes_dir,
        description="Base directory for persistent retrieval indexes.",
    )
    chroma_dir: Optional[Path] = Field(
        default=None,
        description="ChromaDB persistent directory (defaults to indexes_base_dir / 'chroma').",
    )
    bm25_file: Optional[Path] = Field(
        default=None,
        description="BM25 index JSON file (defaults to indexes_base_dir / 'bm25' / 'bm25_index.json').",
    )
    fact_db_path: Optional[Path] = Field(
        default=None,
        description="SQLite Fact Store DB file (defaults to indexes_base_dir / 'fact_store.db').",
    )

    # Service Configuration
    host: str = Field(default="0.0.0.0", description="Host interface to bind.")
    port: int = Field(
        default_factory=lambda: int(os.getenv("PORT", "8000")),
        description="Port to listen on (automatically honors Render $PORT).",
    )
    debug: bool = Field(default=False, description="Enable debug mode.")
    cors_origins: Optional[str] = Field(
        default=None,
        description="Optional comma-separated allowed CORS origins (e.g. 'https://app.vercel.app').",
    )

    def get_chroma_dir(self) -> Path:
        """Resolve path to ChromaDB persistent directory."""
        return self.chroma_dir or (self.indexes_base_dir / "chroma")

    def get_bm25_file(self) -> Path:
        """Resolve path to BM25 index JSON file."""
        return self.bm25_file or (self.indexes_base_dir / "bm25" / "bm25_index.json")

    def get_fact_db_path(self) -> Path:
        """Resolve path to SQLite Fact Store database file."""
        return self.fact_db_path or (self.indexes_base_dir / "fact_store.db")
