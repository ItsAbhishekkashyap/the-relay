"""
Unit Tests for Hybrid Retriever and Reciprocal Rank Fusion (RRF).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest

from app.retrieval.bm25_retriever import BM25Retriever
from app.retrieval.dense_retriever import DenseRetriever
from app.retrieval.fact_store import FactStore
from app.retrieval.hybrid_retriever import (
    HybridRetrievalResult,
    HybridRetriever,
    RetrievalError,
    compute_rrf_score,
)
from tests.test_dense_retriever import MockEmbeddingFunction


@pytest.fixture
def hybrid_setup():
    """Setup in-memory Dense, BM25, and FactStore instances populated with test corpus."""
    mock_emb = MockEmbeddingFunction()
    dense = DenseRetriever(embedding_function=mock_emb, in_memory=True)
    bm25 = BM25Retriever()
    facts = FactStore(db_path=":memory:")

    corpus = [
        {
            "chunk_id": "c1",
            "paper_id": "1706.03762v7",
            "paper_title": "Attention Is All You Need",
            "page_number": 3,
            "section": "3.2 Attention",
            "element_type": "prose",
            "chunk_text": "The Transformer uses multi-head self-attention with d_model=512.",
        },
        {
            "chunk_id": "c2",
            "paper_id": "1706.03762v7",
            "paper_title": "Attention Is All You Need",
            "page_number": 6,
            "section": "3.4 Embeddings and Softmax",
            "element_type": "table",
            "chunk_text": "| Model | BLEU |\n| --- | --- |\n| Base | 27.3 |\n| Big | 28.4 |",
        },
        {
            "chunk_id": "c3",
            "paper_id": "2410.00037v1",
            "paper_title": "Moshi Foundation Model",
            "page_number": 2,
            "section": "1 Introduction",
            "element_type": "prose",
            "chunk_text": "Moshi operates with an overall acoustic latency of 200ms.",
        },
    ]

    dense.index_chunks(corpus)
    bm25.index_chunks(corpus)
    facts.index_chunks(corpus, filter_fact_elements_only=True)  # only c2 (table) indexed in facts

    hybrid = HybridRetriever(
        dense_retriever=dense,
        bm25_retriever=bm25,
        fact_store=facts,
        rrf_k=60,
    )

    return hybrid, corpus


def test_rrf_formula_mathematical_precision():
    # Verify exact arithmetic: 1.0 / (60 + rank)
    score_rank1 = compute_rrf_score(1, k=60, weight=1.0)
    assert abs(score_rank1 - (1.0 / 61.0)) < 1e-9

    score_rank2 = compute_rrf_score(2, k=60, weight=1.0)
    assert abs(score_rank2 - (1.0 / 62.0)) < 1e-9

    # Weight multiplier
    score_weighted = compute_rrf_score(1, k=60, weight=2.0)
    assert abs(score_weighted - (2.0 / 61.0)) < 1e-9

    # Invalid rank check
    with pytest.raises(ValueError):
        compute_rrf_score(0)
    with pytest.raises(ValueError):
        compute_rrf_score(-1)


def test_hybrid_retrieval_fuses_and_deduplicates(hybrid_setup):
    hybrid, _ = hybrid_setup

    # Query for BLEU which appears in BM25, Dense, and FactStore for c2
    results = hybrid.retrieve("BLEU 28.4", top_k=3)
    assert len(results) >= 1

    # Chunk IDs in results must be strictly unique
    chunk_ids = [r["chunk_id"] for r in results]
    assert len(chunk_ids) == len(set(chunk_ids))

    # c2 should have contributions from multiple channels
    top_hit = results[0]
    if top_hit["chunk_id"] == "c2":
        assert len(top_hit["retrieval_channels"]) >= 2
        # Score must be greater than single channel rank 1 score (1/61 ~ 0.01639)
        assert top_hit["score"] > (1.0 / 61.0)


def test_hybrid_provenance_preservation(hybrid_setup):
    hybrid, _ = hybrid_setup

    results = hybrid.retrieve("d_model 512", top_k=2)
    assert len(results) >= 1
    hit = results[0]

    assert "chunk_id" in hit
    assert "paper_id" in hit
    assert "paper_title" in hit
    assert "page_number" in hit
    assert "content" in hit
    assert "element_type" in hit
    assert "retrieval_channels" in hit
    assert "channel_ranks" in hit
    assert "channel_scores" in hit


def test_hybrid_paper_filter(hybrid_setup):
    hybrid, _ = hybrid_setup

    # Search with filter for Attention paper
    results_attn = hybrid.retrieve("latency", paper_filter="1706.03762v7", top_k=3)
    for r in results_attn:
        assert r["paper_id"] == "1706.03762v7"

    # Search with filter for Moshi paper
    results_moshi = hybrid.retrieve("latency", paper_filter="2410.00037v1", top_k=3)
    assert len(results_moshi) >= 1
    for r in results_moshi:
        assert r["paper_id"] == "2410.00037v1"


def test_hybrid_channel_toggles(hybrid_setup):
    hybrid, _ = hybrid_setup

    # BM25 only
    res_bm25 = hybrid.retrieve("latency", enable_dense=False, enable_bm25=True, enable_facts=False)
    assert len(res_bm25) >= 1
    for r in res_bm25:
        assert r["retrieval_channels"] == ["bm25"]

    # Dense only
    res_dense = hybrid.retrieve("Transformer", enable_dense=True, enable_bm25=False, enable_facts=False)
    assert len(res_dense) >= 1
    for r in res_dense:
        assert r["retrieval_channels"] == ["dense"]


def test_hybrid_empty_and_no_result_handling(hybrid_setup):
    hybrid, _ = hybrid_setup

    res_empty = hybrid.retrieve("")
    assert len(res_empty) == 0
    assert isinstance(res_empty, HybridRetrievalResult)

    res_whitespace = hybrid.retrieve("   ")
    assert len(res_whitespace) == 0

    res = hybrid.retrieve("zzzz_nonexistent_vocabulary_99999")
    assert isinstance(res, HybridRetrievalResult)


def test_hybrid_one_channel_failure_returns_partial_success(hybrid_setup):
    """Graceful degradation: When one channel fails, return results from surviving channels with diagnostics."""
    hybrid, _ = hybrid_setup

    # Simulate dense retriever failure
    class BrokenDenseRetriever:
        def query(self, *args, **kwargs):
            raise RuntimeError("Dense vector store connection timed out")

    hybrid.dense = BrokenDenseRetriever()

    # Query matching BLEU should still be retrieved by BM25 and FactStore
    results = hybrid.retrieve("BLEU 28.4", top_k=3)
    assert len(results) >= 1
    assert isinstance(results, HybridRetrievalResult)

    # Diagnostic verification
    assert results.has_failures is True
    assert "dense" in results.failed_channels
    assert "Dense vector store connection timed out" in results.failed_channels["dense"]
    assert "bm25" in results.successful_channels

    # Provenance record also contains diagnostics
    assert results[0]["diagnostics"]["failed_channels"]["dense"] == "Dense vector store connection timed out"
    assert "bm25" in results[0]["diagnostics"]["successful_channels"]


def test_hybrid_partial_success_with_fact_store_failure(hybrid_setup):
    """Graceful degradation: When fact store fails, Dense and BM25 continue serving."""
    hybrid, _ = hybrid_setup

    class BrokenFactStore:
        def search(self, *args, **kwargs):
            raise RuntimeError("FactStore SQLite locked")

    hybrid.facts = BrokenFactStore()

    results = hybrid.retrieve("Transformer", top_k=2)
    assert len(results) >= 1
    assert results.has_failures is True
    assert "fact_store" in results.failed_channels
    assert "FactStore SQLite locked" in results.failed_channels["fact_store"]
    assert "dense" in results.successful_channels
    assert "bm25" in results.successful_channels


def test_hybrid_all_channels_failure_raises_retrieval_error(hybrid_setup):
    """Hard failure: When all enabled channels fail, raise a clear RetrievalError."""
    hybrid, _ = hybrid_setup

    class FailingChannel:
        def __init__(self, name: str):
            self.name = name

        def query(self, *args, **kwargs):
            raise RuntimeError(f"{self.name} failed")

        def search(self, *args, **kwargs):
            raise RuntimeError(f"{self.name} failed")

    hybrid.dense = FailingChannel("Dense")
    hybrid.bm25 = FailingChannel("BM25")
    hybrid.facts = FailingChannel("FactStore")

    with pytest.raises(RetrievalError) as exc_info:
        hybrid.retrieve("any query")

    err = exc_info.value
    assert "All configured retrieval channels failed" in str(err)
    assert "dense" in err.failed_channels
    assert "bm25" in err.failed_channels
    assert "fact_store" in err.failed_channels

