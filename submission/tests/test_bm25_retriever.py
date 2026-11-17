"""
Unit Tests for BM25 Keyword Retriever.
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

from app.retrieval.bm25_retriever import BM25Retriever, bm25_tokenize


@pytest.fixture
def sample_corpus() -> List[Dict[str, Any]]:
    return [
        {
            "chunk_id": "attn_01",
            "chunk_text": "The Transformer uses multi-head attention where d_model is 512 and num_heads is 8.",
            "paper_id": "1706.03762v7",
            "paper_title": "Attention Is All You Need",
            "page_number": 3,
            "page_numbers": [3],
            "section": "3.2 Attention",
            "element_type": "prose",
        },
        {
            "chunk_id": "attn_02",
            "chunk_text": "On English-to-German translation task, the big Transformer model achieves BLEU score of 28.4.",
            "paper_id": "1706.03762v7",
            "paper_title": "Attention Is All You Need",
            "page_number": 8,
            "page_numbers": [8],
            "section": "5.1 Machine Translation",
            "element_type": "prose",
        },
        {
            "chunk_id": "moshi_01",
            "chunk_text": "Moshi achieves a theoretical latency of 160ms and an overall operational latency of 200ms.",
            "paper_id": "2410.00037v1",
            "paper_title": "Moshi: A Speech-Text Foundation Model",
            "page_number": 2,
            "page_numbers": [2],
            "section": "1 Introduction",
            "element_type": "prose",
        },
    ]


def test_bm25_tokenize():
    tokens = bm25_tokenize("The d_model = 512 in Attention-is-all-you-need (1706.03762v7)!")
    assert "d_model" in tokens
    assert "512" in tokens
    assert "1706.03762v7" in tokens
    assert "attention-is-all-you-need" in tokens


def test_bm25_arxiv_identifier_complete_token_matching(sample_corpus):
    """Regression test ensuring arXiv IDs are tokenized and retrieved as complete tokens."""
    arxiv_ids = ["1706.03762v7", "2410.00037v1", "2507.07955v2"]
    for aid in arxiv_ids:
        toks = bm25_tokenize(aid)
        assert toks == [aid.lower()], f"Expected single complete token for '{aid}', got {toks}"

    retriever = BM25Retriever()
    retriever.index_chunks(sample_corpus)

    # Search for complete arXiv ID
    res_attn = retriever.query("1706.03762v7", top_k=2)
    assert len(res_attn) >= 1
    for r in res_attn:
        assert r["paper_id"] == "1706.03762v7"

    res_moshi = retriever.query("2410.00037v1", top_k=2)
    assert len(res_moshi) >= 1
    assert res_moshi[0]["paper_id"] == "2410.00037v1"


def test_bm25_indexing_and_exact_term_search(sample_corpus):
    retriever = BM25Retriever()
    indexed = retriever.index_chunks(sample_corpus)
    assert indexed == 3
    assert retriever.count() == 3

    # Exact technical term 'd_model'
    res = retriever.query("d_model", top_k=2)
    assert len(res) >= 1
    assert res[0]["chunk_id"] == "attn_01"
    assert res[0]["score"] > 0.0
    assert res[0]["retrieval_method"] == "bm25"
    assert res[0]["section"] == "3.2 Attention"

    # Search for BLEU score
    res_bleu = retriever.query("BLEU 28.4", top_k=1)
    assert len(res_bleu) == 1
    assert res_bleu[0]["chunk_id"] == "attn_02"


def test_bm25_paper_filtering(sample_corpus):
    retriever = BM25Retriever()
    retriever.index_chunks(sample_corpus)

    # Query term 'latency' appears in Moshi
    res_no_filter = retriever.query("latency", top_k=5)
    assert len(res_no_filter) == 1
    assert res_no_filter[0]["chunk_id"] == "moshi_01"

    # Filter to Attention paper (where latency is absent)
    res_filtered = retriever.query("latency", top_k=5, paper_filter="1706.03762v7")
    assert len(res_filtered) == 0

    # Filter to Moshi paper
    res_moshi = retriever.query("latency", top_k=5, paper_filter="2410.00037v1")
    assert len(res_moshi) == 1
    assert res_moshi[0]["paper_id"] == "2410.00037v1"


def test_bm25_idempotent_indexing(sample_corpus):
    retriever = BM25Retriever()
    first = retriever.index_chunks(sample_corpus)
    assert first == 3

    # Re-index same chunks
    second = retriever.index_chunks(sample_corpus)
    assert second == 3
    assert retriever.count() == 3


def test_bm25_empty_query_and_unknown_terms(sample_corpus):
    retriever = BM25Retriever()
    assert retriever.query("hello") == []

    retriever.index_chunks(sample_corpus)
    assert retriever.query("") == []
    assert retriever.query("   ") == []

    # Non-existent vocabulary
    res = retriever.query("xylophone_quantum_superposition_xyz999")
    assert res == []


def test_bm25_save_and_load(sample_corpus):
    with tempfile.TemporaryDirectory() as tmpdir:
        save_path = Path(tmpdir) / "test_bm25.json"

        retriever1 = BM25Retriever()
        retriever1.index_chunks(sample_corpus)
        retriever1.save(save_path)
        assert save_path.exists()

        retriever2 = BM25Retriever(index_file=save_path)
        assert retriever2.count() == 3

        res = retriever2.query("d_model 512", top_k=1)
        assert len(res) == 1
        assert res[0]["chunk_id"] == "attn_01"
