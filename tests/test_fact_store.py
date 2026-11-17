"""
Unit Tests for SQLite Structured Fact Store.
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

from app.retrieval.fact_store import FactStore


@pytest.fixture
def sample_facts_corpus() -> List[Dict[str, Any]]:
    return [
        {
            "chunk_id": "table_01",
            "paper_id": "1706.03762v7",
            "arxiv_id": "1706.03762",
            "paper_version": "v7",
            "paper_title": "Attention Is All You Need",
            "page_number": 6,
            "page_numbers": [6],
            "section": "3.4 Embeddings and Softmax",
            "element_type": "table",
            "chunk_text": "| Layer Type | Complexity per Layer | Sequential Operations | Maximum Path Length |\n| --- | --- | --- | --- |\n| Self-Attention | O(n^2 * d) | O(1) | O(1) |\n| Recurrent | O(n * d^2) | O(n) | O(n) |\n| Convolutional | O(k * n * d^2) | O(1) | O(log_k(n)) |",
            "token_count": 55,
            "character_count": 250,
        },
        {
            "chunk_id": "table_02",
            "paper_id": "1706.03762v7",
            "arxiv_id": "1706.03762",
            "paper_version": "v7",
            "paper_title": "Attention Is All You Need",
            "page_number": 8,
            "page_numbers": [8],
            "section": "5.1 Machine Translation",
            "element_type": "table_unstructured",
            "chunk_text": "Table 2: The Transformer achieves 28.4 BLEU on WMT 2014 English-to-German and 41.8 BLEU on English-to-French.",
            "token_count": 28,
            "character_count": 115,
        },
        {
            "chunk_id": "prose_01",
            "paper_id": "1706.03762v7",
            "page_number": 1,
            "section": "1 Introduction",
            "element_type": "prose",
            "chunk_text": "Ordinary narrative prose describing general motivation.",
            "token_count": 8,
            "character_count": 55,
        },
        {
            "chunk_id": "table_03_moshi",
            "paper_id": "2410.00037v1",
            "arxiv_id": "2410.00037",
            "paper_version": "v1",
            "paper_title": "Moshi: A Speech-Text Foundation Model",
            "page_number": 14,
            "page_numbers": [14],
            "section": "4 Experiments",
            "element_type": "table",
            "chunk_text": "| Model | Latency (ms) | WER (%) | s-MOS |\n| --- | --- | --- | --- |\n| Moshi-7B | 160 | 12.4 | 4.12 |\n| Baseline | 1200 | 14.8 | 3.65 |",
            "token_count": 45,
            "character_count": 160,
        },
    ]


def test_fact_store_in_memory_initialization():
    store = FactStore(db_path=":memory:")
    assert store.count() == 0
    store.close()


def test_fact_store_filtering_elements_and_indexing(sample_facts_corpus):
    store = FactStore(db_path=":memory:")

    # filter_fact_elements_only=True should index the 3 tables and skip prose_01
    indexed_count = store.index_chunks(sample_facts_corpus, filter_fact_elements_only=True)
    assert indexed_count == 3
    assert store.count() == 3

    # Check paper-level counts
    assert store.count(paper_filter="1706.03762v7") == 2
    assert store.count(paper_filter="2410.00037v1") == 1
    assert store.count(paper_filter="non_existent") == 0


def test_fact_store_idempotency(sample_facts_corpus):
    store = FactStore(db_path=":memory:")
    count1 = store.index_chunks(sample_facts_corpus, filter_fact_elements_only=True)
    assert count1 == 3

    # Re-indexing same records must not duplicate rows
    count2 = store.index_chunks(sample_facts_corpus, filter_fact_elements_only=True)
    assert count2 == 3
    assert store.count() == 3


def test_exact_numeric_and_identifier_search(sample_facts_corpus):
    store = FactStore(db_path=":memory:")
    store.index_chunks(sample_facts_corpus, filter_fact_elements_only=True)

    # Exact numeric string "28.4"
    res_num = store.search("28.4", top_k=2)
    assert len(res_num) >= 1
    assert res_num[0]["chunk_id"] == "table_02"
    assert "28.4" in res_num[0]["content"]
    assert res_num[0]["retrieval_method"] == "fact_store"

    # Exact table header "| Complexity per Layer |"
    res_header = store.search("Complexity per Layer", top_k=2)
    assert len(res_header) >= 1
    assert res_header[0]["chunk_id"] == "table_01"
    assert "| Self-Attention |" in res_header[0]["content"]

    # Search for Moshi latency metric "160"
    res_moshi = store.search("160", top_k=2)
    assert len(res_moshi) >= 1
    assert res_moshi[0]["chunk_id"] == "table_03_moshi"


def test_fact_store_preserves_verbatim_markdown(sample_facts_corpus):
    store = FactStore(db_path=":memory:")
    store.index_chunks(sample_facts_corpus, filter_fact_elements_only=True)

    fact = store.get_fact("table_01")
    assert fact is not None
    assert fact["element_type"] == "table"
    assert fact["page_number"] == 6
    assert fact["section"] == "3.4 Embeddings and Softmax"
    # Content must match original exactly (no whitespace stripped or modified)
    assert fact["content"] == sample_facts_corpus[0]["chunk_text"]


def test_fact_store_paper_filtering(sample_facts_corpus):
    store = FactStore(db_path=":memory:")
    store.index_chunks(sample_facts_corpus, filter_fact_elements_only=True)

    # Query matching term in Attention paper
    res_attn = store.search("BLEU", paper_filter="1706.03762v7")
    assert len(res_attn) >= 1
    for r in res_attn:
        assert r["paper_id"] == "1706.03762v7"

    # Filter to Moshi paper where BLEU does not exist
    res_moshi = store.search("BLEU", paper_filter="2410.00037v1")
    assert len(res_moshi) == 0


def test_fact_store_persistence():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = Path(tmpdir) / "facts.db"
        store1 = FactStore(db_path=db_file)
        store1.index_chunks([
            {
                "chunk_id": "t_persist",
                "paper_id": "test_p",
                "page_number": 2,
                "element_type": "table",
                "chunk_text": "| Col A | Col B |\n| 100 | 200 |",
            }
        ], filter_fact_elements_only=True)
        assert store1.count() == 1
        store1.close()

        # Re-open database from disk
        store2 = FactStore(db_path=db_file)
        assert store2.count() == 1
        fact = store2.get_fact("t_persist")
        assert fact is not None
        assert "| Col A | Col B |" in fact["content"]
        store2.close()
