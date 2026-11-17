"""
Retrieval package for The Relay research assistant.

Provides hybrid retrieval over arXiv research papers combining:
- Dense Vector Retrieval via ChromaDB (cosine distance)
- Keyword Retrieval via BM25
- Structured Fact Store via SQLite
- Reciprocal Rank Fusion (RRF) with channel failure diagnostics
"""

from app.retrieval.bm25_retriever import BM25Retriever, bm25_tokenize
from app.retrieval.dense_retriever import (
    DenseRetriever,
    LocalSentenceTransformerEmbeddingFunction,
)
from app.retrieval.fact_store import FactStore
from app.retrieval.hybrid_retriever import (
    HybridRetrievalResult,
    HybridRetriever,
    RetrievalError,
    compute_rrf_score,
)

__all__ = [
    "DenseRetriever",
    "LocalSentenceTransformerEmbeddingFunction",
    "BM25Retriever",
    "bm25_tokenize",
    "FactStore",
    "HybridRetriever",
    "HybridRetrievalResult",
    "RetrievalError",
    "compute_rrf_score",
]
