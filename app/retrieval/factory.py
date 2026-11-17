"""Factory for initializing the unified HybridRetriever with persistent indexes."""

from typing import Optional
from app.config import AppSettings
from app.retrieval.bm25_retriever import BM25Retriever
from app.retrieval.dense_retriever import (
    DenseRetriever,
    LocalSentenceTransformerEmbeddingFunction,
)
from app.retrieval.fact_store import FactStore
from app.retrieval.hybrid_retriever import HybridRetriever


def create_hybrid_retriever(settings: Optional[AppSettings] = None) -> HybridRetriever:
    """Instantiate the unified HybridRetriever using configured persistent index paths.

    Args:
        settings: Application settings. If None, loaded from environment/.env.

    Returns:
        Configured HybridRetriever instance.
    """
    cfg = settings or AppSettings()

    chroma_dir = cfg.get_chroma_dir()
    bm25_file = cfg.get_bm25_file()
    fact_db = cfg.get_fact_db_path()

    embedding_fn = LocalSentenceTransformerEmbeddingFunction()
    dense_retriever = DenseRetriever(
        persist_dir=chroma_dir,
        collection_name="relay_papers",
        embedding_function=embedding_fn,
    )
    bm25_retriever = BM25Retriever(index_file=bm25_file)
    fact_store = FactStore(db_path=fact_db)

    return HybridRetriever(
        dense_retriever=dense_retriever,
        bm25_retriever=bm25_retriever,
        fact_store=fact_store,
        rrf_k=60,
    )
