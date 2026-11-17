"""
Unit and Integration Tests for Dense Retriever (ChromaDB + Sentence Transformers).
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

from app.retrieval.dense_retriever import (
    DenseRetriever,
    LocalSentenceTransformerEmbeddingFunction,
    sanitize_metadata_for_chroma,
    unpack_metadata_from_chroma,
)


class MockEmbeddingFunction(EmbeddingFunction[Documents]):
    """Deterministic, zero-download embedding function for fast unit testing."""

    def __init__(self, dim: int = 16) -> None:
        self.dim = dim

    @staticmethod
    def name() -> str:
        return "mock_embedding"

    def get_config(self) -> Dict[str, Any]:
        return {"dim": self.dim}

    @staticmethod
    def build_from_config(config: Dict[str, Any]) -> MockEmbeddingFunction:
        return MockEmbeddingFunction(dim=config.get("dim", 16))

    def __call__(self, input: Documents) -> Embeddings:
        results = []
        for doc in input:
            # Deterministic pseudo-embedding based on document length and characters
            val = float(len(doc))
            vec = [float(hash(f"{doc}_{i}")) % 10.0 for i in range(self.dim)]
            # Normalize vector
            norm = sum(x**2 for x in vec) ** 0.5 or 1.0
            norm_vec = [x / norm for x in vec]
            results.append(norm_vec)
        return results


@pytest.fixture
def mock_embedding_fn():
    return MockEmbeddingFunction()


@pytest.fixture
def sample_chunks() -> List[Dict[str, Any]]:
    return [
        {
            "chunk_id": "1706.03762v7_lc_0001",
            "chunk_index": 1,
            "paper_id": "1706.03762v7",
            "arxiv_id": "1706.03762",
            "paper_version": "v7",
            "paper_title": "Attention Is All You Need",
            "source_filename": "1706.03762v7.pdf",
            "page_number": 1,
            "page_numbers": [1],
            "section": "Abstract",
            "element_type": "prose",
            "chunk_text": "We propose a new simple network architecture, the Transformer, based solely on attention mechanisms.",
            "token_count": 18,
            "character_count": 101,
        },
        {
            "chunk_id": "1706.03762v7_lc_0002",
            "chunk_index": 2,
            "paper_id": "1706.03762v7",
            "arxiv_id": "1706.03762",
            "paper_version": "v7",
            "paper_title": "Attention Is All You Need",
            "source_filename": "1706.03762v7.pdf",
            "page_number": 2,
            "page_numbers": [2],
            "section": "3 Model Architecture",
            "element_type": "prose",
            "chunk_text": "The Transformer follows this overall architecture using stacked self-attention and point-wise layers.",
            "token_count": 16,
            "character_count": 100,
        },
        {
            "chunk_id": "2410.00037v1_lc_0001",
            "chunk_index": 1,
            "paper_id": "2410.00037v1",
            "arxiv_id": "2410.00037",
            "paper_version": "v1",
            "paper_title": "Moshi: A Speech-Text Foundation Model for Real-Time Dialogue",
            "source_filename": "2410.00037v1.pdf",
            "page_number": 1,
            "page_numbers": [1],
            "section": "Abstract",
            "element_type": "prose",
            "chunk_text": "Moshi is a speech-text foundation model capable of real-time full-duplex spoken dialogue with low latency.",
            "token_count": 19,
            "character_count": 107,
        },
    ]


def test_sanitize_and_unpack_metadata_roundtrip():
    original = {
        "chunk_id": "test_001",
        "chunk_index": 5,
        "paper_id": "1706.03762v7",
        "arxiv_id": "1706.03762",
        "paper_version": "v7",
        "paper_title": "Attention Is All You Need",
        "source_filename": "1706.03762v7.pdf",
        "page_number": 3,
        "page_numbers": [3, 4],
        "section": None,
        "element_type": "table",
        "token_count": 42,
        "character_count": 210,
        "source_block_id": "b_1",
        "source_block_ids": ["b_1", "b_2"],
        "bbox": [10.5, 20.5, 30.5, 40.5],
    }

    sanitized = sanitize_metadata_for_chroma(original)
    # Check that complex structures became strings
    assert isinstance(sanitized["page_numbers_json"], str)
    assert isinstance(sanitized["source_block_ids_json"], str)
    assert isinstance(sanitized["bbox_json"], str)
    assert sanitized["section"] == ""

    unpacked = unpack_metadata_from_chroma(sanitized)
    assert unpacked["page_numbers"] == [3, 4]
    assert unpacked["source_block_ids"] == ["b_1", "b_2"]
    assert unpacked["bbox"] == [10.5, 20.5, 30.5, 40.5]
    assert unpacked["section"] is None
    assert unpacked["element_type"] == "table"


def test_dense_retriever_in_memory_indexing_and_query(mock_embedding_fn, sample_chunks):
    retriever = DenseRetriever(
        collection_name="test_in_memory",
        embedding_function=mock_embedding_fn,
        in_memory=True,
    )

    indexed = retriever.index_chunks(sample_chunks)
    assert indexed == 3
    assert retriever.count() == 3

    # Query without filter
    results = retriever.query("Transformer attention architecture", top_k=2)
    assert len(results) == 2
    for r in results:
        assert r["retrieval_method"] == "dense"
        assert "score" in r
        assert "distance" in r
        assert r["score"] >= 0.0
        assert r["chunk_id"] is not None
        assert r["content"] != ""


def test_dense_retriever_idempotent_indexing(mock_embedding_fn, sample_chunks):
    retriever = DenseRetriever(
        collection_name="test_idempotent",
        embedding_function=mock_embedding_fn,
        in_memory=True,
    )

    first_indexed = retriever.index_chunks(sample_chunks)
    assert first_indexed == 3
    assert retriever.count() == 3

    # Index again with identical IDs - must not create duplicate records
    second_indexed = retriever.index_chunks(sample_chunks)
    assert second_indexed == 3
    assert retriever.count() == 3


def test_dense_retriever_paper_filtering(mock_embedding_fn, sample_chunks):
    retriever = DenseRetriever(
        collection_name="test_filtering",
        embedding_function=mock_embedding_fn,
        in_memory=True,
    )
    retriever.index_chunks(sample_chunks)

    # Filter to 1706.03762v7
    results_attn = retriever.query("Moshi speech", top_k=5, paper_filter="1706.03762v7")
    for r in results_attn:
        assert r["paper_id"] == "1706.03762v7"
        assert r["paper_id"] != "2410.00037v1"

    # Filter to 2410.00037v1
    results_moshi = retriever.query("Transformer", top_k=5, paper_filter="2410.00037v1")
    for r in results_moshi:
        assert r["paper_id"] == "2410.00037v1"
        assert r["paper_id"] != "1706.03762v7"


def test_dense_retriever_empty_query_and_bounds(mock_embedding_fn, sample_chunks):
    retriever = DenseRetriever(
        collection_name="test_empty",
        embedding_function=mock_embedding_fn,
        in_memory=True,
    )

    # Query before indexing
    assert retriever.query("hello") == []

    retriever.index_chunks(sample_chunks)
    assert retriever.query("") == []
    assert retriever.query("   ") == []

    # top_k larger than collection
    res = retriever.query("Transformer", top_k=50)
    assert len(res) == 3


def test_dense_retriever_persistence():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        mock_fn = MockEmbeddingFunction()
        retriever1 = DenseRetriever(
            persist_dir=tmpdir,
            collection_name="test_persist",
            embedding_function=mock_fn,
            in_memory=False,
        )
        retriever1.index_chunks([
            {
                "chunk_id": "c1",
                "chunk_text": "Sample text for persistent storage test",
                "paper_id": "paper_1",
                "page_number": 1,
            }
        ])
        assert retriever1.count() == 1

        # Reopen collection from same directory
        retriever2 = DenseRetriever(
            persist_dir=tmpdir,
            collection_name="test_persist",
            embedding_function=mock_fn,
            in_memory=False,
        )
        assert retriever2.count() == 1
        fetched = retriever2.get_chunk("c1")
        assert fetched is not None
        assert fetched["chunk_id"] == "c1"
        assert fetched["content"] == "Sample text for persistent storage test"


def test_dense_retriever_cosine_metric_specification(mock_embedding_fn):
    retriever = DenseRetriever(
        collection_name="test_cosine_metric",
        embedding_function=mock_embedding_fn,
        in_memory=True,
    )
    # Collection metadata must explicitly specify cosine
    assert retriever.collection.metadata.get("hnsw:space") == "cosine"


def test_real_local_sentence_transformers_embedding_integration():
    """Integration test verifying real all-MiniLM-L6-v2 local model with ChromaDB."""
    emb_fn = LocalSentenceTransformerEmbeddingFunction()
    retriever = DenseRetriever(
        collection_name="test_real_embed_integration",
        embedding_function=emb_fn,
        in_memory=True,
    )

    chunks = [
        {
            "chunk_id": "real_1",
            "chunk_text": "The Transformer uses scaled dot-product attention and multi-head attention.",
            "paper_id": "1706.03762v7",
            "page_number": 3,
        },
        {
            "chunk_id": "real_2",
            "chunk_text": "Moshi features an acoustic tokenizer called Mimi and a 7B parameter language model.",
            "paper_id": "2410.00037v1",
            "page_number": 5,
        },
    ]

    retriever.index_chunks(chunks)
    assert retriever.count() == 2

    # Query for Transformer should rank real_1 highest
    query_results = retriever.query("attention mechanism in transformer", top_k=1)
    assert len(query_results) == 1
    assert query_results[0]["chunk_id"] == "real_1"
    assert query_results[0]["score"] > 0.0
