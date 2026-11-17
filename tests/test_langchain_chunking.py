"""
Unit tests for LangChain-based token-aware chunking engine.

Tests RecursiveCharacterTextSplitter with Sentence Transformers MiniLM tokenizer,
deterministic chunk IDs, token size enforcement, overlap verification,
provenance preservation, and prevention of cross-paper mixing.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from langchain_core.documents import Document

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.retrieval.langchain_chunking import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    chunk_langchain_documents,
    chunk_to_dict,
    count_tokens,
    create_langchain_splitter,
    get_local_tokenizer,
)


@pytest.fixture(scope="module")
def tokenizer():
    return get_local_tokenizer()


def test_minilm_tokenizer_loads_locally_and_counts_tokens(tokenizer):
    assert tokenizer is not None
    tokens = count_tokens("Hello world from MiniLM", tokenizer)
    assert tokens == 5


def test_missing_tokenizer_raises_runtime_error_per_working_rule():
    with pytest.raises(RuntimeError) as exc_info:
        get_local_tokenizer(model_name="non_existent_local_model_xyz_9999")
    assert "stopping execution rather than silently switching" in str(exc_info.value)


def test_deterministic_chunk_ids(tokenizer):
    doc = Document(
        page_content="Sentence one. " * 100,
        metadata={
            "paper_id": "test_doc",
            "arxiv_id": "test_arxiv",
            "paper_version": "v1",
            "paper_title": "Test Title",
            "source_filename": "test.pdf",
            "page_number": 1,
            "page_numbers": [1],
            "section": "1 Introduction",
            "element_type": "prose",
            "source_block_id": "b1",
            "bbox": [10.0, 10.0, 200.0, 300.0],
        },
    )

    chunks_run1 = chunk_langchain_documents([doc], tokenizer=tokenizer, chunk_size=100, chunk_overlap=20)
    chunks_run2 = chunk_langchain_documents([doc], tokenizer=tokenizer, chunk_size=100, chunk_overlap=20)

    assert len(chunks_run1) == len(chunks_run2)
    for c1, c2 in zip(chunks_run1, chunks_run2):
        assert c1.metadata["chunk_id"] == c2.metadata["chunk_id"]
        assert c1.metadata["chunk_index"] == c2.metadata["chunk_index"]
        assert c1.page_content == c2.page_content


def test_chunk_metadata_survives_splitting(tokenizer):
    doc = Document(
        page_content="First paragraph with content.\n\nSecond paragraph with more content.\n\n" * 50,
        metadata={
            "paper_id": "1706.03762v7",
            "arxiv_id": "1706.03762",
            "paper_version": "v7",
            "paper_title": "Attention Is All You Need",
            "source_filename": "1706.03762v7.pdf",
            "page_number": 3,
            "page_numbers": [3],
            "section": "3.2 Attention",
            "element_type": "prose",
            "source_block_id": "1706.03762v7_p3_b2",
            "bbox": [108.0, 482.0, 253.0, 492.0],
        },
    )

    chunks = chunk_langchain_documents([doc], tokenizer=tokenizer, chunk_size=200, chunk_overlap=30)
    assert len(chunks) > 1

    for c in chunks:
        meta = c.metadata
        assert meta["paper_id"] == "1706.03762v7"
        assert meta["arxiv_id"] == "1706.03762"
        assert meta["paper_version"] == "v7"
        assert meta["paper_title"] == "Attention Is All You Need"
        assert meta["source_filename"] == "1706.03762v7.pdf"
        assert meta["page_number"] == 3
        assert meta["page_numbers"] == [3]
        assert meta["section"] == "3.2 Attention"
        assert meta["element_type"] == "prose"
        assert meta["chunking_strategy"] == "langchain_recursive"
        assert meta["token_count"] <= 200
        assert meta["chunk_id"].startswith("1706.03762v7_lc_")


def test_chunk_sizes_respect_configured_maximum(tokenizer):
    long_text = "The Transformer follows this overall architecture using stacked self-attention and point-wise layers. " * 80
    doc = Document(page_content=long_text, metadata={"paper_id": "test_p", "page_number": 1})

    chunks = chunk_langchain_documents([doc], tokenizer=tokenizer, chunk_size=512, chunk_overlap=76)
    assert len(chunks) > 1

    for c in chunks:
        # Exact token count calculation using MiniLM
        tokens = count_tokens(c.page_content, tokenizer)
        assert tokens == c.metadata["token_count"]
        assert tokens <= 512, f"Chunk exceeded 512 tokens: {tokens}"


def compute_token_overlap(text_a: str, text_b: str, tokenizer: Any) -> int:
    """
    Compute the exact shared token count between the suffix of text_a and prefix of text_b
    using the locally loaded Sentence Transformers MiniLM tokenizer.
    """
    toks_a = tokenizer.encode(text_a, add_special_tokens=False)
    toks_b = tokenizer.encode(text_b, add_special_tokens=False)
    max_k = min(len(toks_a), len(toks_b), 150)
    for k in range(max_k, 0, -1):
        if toks_a[-k:] == toks_b[:k]:
            return k
    return 0


def test_chunk_overlap_is_present_and_consistent(tokenizer):
    """
    Verify consecutive chunks maintain token-level overlap.
    Calculates exact shared token counts using MiniLM tokenizer.
    Verifies that overlap varies around recursive separator boundaries
    rather than forcing an exact rigid token count that would break words.
    """
    paragraphs = [
        f"Paragraph {i}: This is sentence number {i} discussing sequence transduction architectures and self-attention mechanisms in deep neural networks."
        for i in range(40)
    ]
    doc = Document(
        page_content="\n\n".join(paragraphs),
        metadata={"paper_id": "overlap_test", "page_number": 1},
    )

    configured_overlap = 40
    chunks = chunk_langchain_documents([doc], tokenizer=tokenizer, chunk_size=150, chunk_overlap=configured_overlap)
    assert len(chunks) >= 3

    observed_overlaps = []
    for i in range(len(chunks) - 1):
        c_current = chunks[i].page_content
        c_next = chunks[i + 1].page_content

        # Shared token overlap measurement using MiniLM tokenizer
        ov = compute_token_overlap(c_current, c_next, tokenizer)
        observed_overlaps.append(ov)

        # Overlap must be present and bounded by configured chunk_overlap
        assert ov > 0, f"Expected non-zero token overlap between chunk {i} and {i+1}, got {ov}"
        assert ov <= configured_overlap, f"Token overlap {ov} exceeded configured limit {configured_overlap}"

        # Word-level tail verification
        current_words = c_current.split()
        tail_phrase = " ".join(current_words[-4:])
        assert tail_phrase in c_next, f"Expected overlap '{tail_phrase}' from chunk {i} missing in chunk {i+1}"

    # Verify that overlap varies naturally around separator boundaries
    assert min(observed_overlaps) > 0
    assert max(observed_overlaps) <= configured_overlap


def test_token_overlap_on_representative_real_chunks(tokenizer):
    """
    Verify token overlap on real-world text from Attention Is All You Need.
    Demonstrates exact token overlap behavior on representative consecutive chunks
    with chunk_size=150 and chunk_overlap=50.
    """
    text_parts = [
        "Recurrent neural networks, long short-term memory [13] and gated recurrent [7] neural networks in particular, have been firmly established as state of the art approaches in sequence modeling and transduction problems such as language modeling and machine translation [35, 2, 5].",
        "Numerous efforts have since continued to push the boundaries of recurrent language models and encoder-decoder architectures [38, 24, 15].",
        "Recurrent models typically factor computation along the symbol positions of the input and output sequences. Aligning the positions to steps in computation time, they generate a sequence of hidden states ht, as a function of the previous hidden state ht-1 and the input for position t.",
        "This inherently sequential nature precludes parallelization within training examples, which becomes critical at longer sequence lengths, as memory constraints limit batching across examples.",
        "Recent work has achieved significant improvements in computational efficiency through factorization tricks [21] and conditional computation [32], while also improving model performance in case of the latter.",
        "The fundamental constraint of sequential computation, however, remains.",
        "Attention mechanisms have become an integral part of compelling sequence modeling and transduction models in various tasks, allowing modeling of dependencies without regard to their distance in the input or output sequences [2, 19].",
        "In all but a few cases [27], however, such attention mechanisms are used in conjunction with a recurrent network.",
        "In this work we propose the Transformer, a model architecture eschewing recurrence and instead relying entirely on an attention mechanism to draw global dependencies between input and output.",
        "The Transformer allows for significantly more parallelization and can reach a new state of the art in translation quality after being trained for as little as twelve hours on eight P100 GPUs."
    ]

    single_para = " ".join(text_parts)
    doc = Document(page_content=single_para, metadata={"paper_id": "1706.03762v7", "page_number": 2})
    chunks = chunk_langchain_documents([doc], tokenizer=tokenizer, chunk_size=150, chunk_overlap=50)

    assert len(chunks) >= 3

    for i in range(len(chunks) - 1):
        c1, c2 = chunks[i], chunks[i + 1]
        assert c1.metadata["token_count"] <= 150
        assert c2.metadata["token_count"] <= 150
        ov = compute_token_overlap(c1.page_content, c2.page_content, tokenizer)
        # Bounded by configured overlap
        assert 0 < ov <= 50, f"Expected 0 < ov <= 50, got {ov}"


def test_no_cross_paper_chunk_mixing(tokenizer):
    doc_a = Document(
        page_content="Attention mechanisms have become an integral part of compelling sequence modeling.",
        metadata={"paper_id": "paper_A", "page_number": 1},
    )
    doc_b = Document(
        page_content="Moshi is a speech-text foundation model for real-time full-duplex spoken dialogue.",
        metadata={"paper_id": "paper_B", "page_number": 1},
    )

    chunks_a = chunk_langchain_documents([doc_a], tokenizer=tokenizer)
    chunks_b = chunk_langchain_documents([doc_b], tokenizer=tokenizer)

    assert all(c.metadata["paper_id"] == "paper_A" for c in chunks_a)
    assert all(c.metadata["paper_id"] == "paper_B" for c in chunks_b)
    assert not any("Moshi" in c.page_content for c in chunks_a)
    assert not any("Transformer" in c.page_content for c in chunks_b)


def test_empty_input_handling_safety(tokenizer):
    # Empty list
    empty_res = chunk_langchain_documents([], tokenizer=tokenizer)
    assert empty_res == []

    # Document with whitespace only
    empty_doc = Document(page_content="   \n\n   ", metadata={"paper_id": "empty_paper", "page_number": 1})
    res = chunk_langchain_documents([empty_doc], tokenizer=tokenizer)
    assert len(res) == 0


def test_table_elements_retain_classification(tokenizer):
    table_content = "| Column A | Column B |\n|---|---|\n| Value 1 | Value 2 |\n| Value 3 | Value 4 |"
    doc = Document(
        page_content=table_content,
        metadata={
            "paper_id": "1706.03762v7",
            "page_number": 9,
            "element_type": "table",
            "section": "6.2 Model Variations",
        },
    )

    chunks = chunk_langchain_documents([doc], tokenizer=tokenizer, chunk_size=512, chunk_overlap=76)
    assert len(chunks) == 1
    assert chunks[0].metadata["element_type"] == "table"
    assert "| Column A |" in chunks[0].page_content


def test_generated_datasets_integrity():
    chunk_dir = REPO_ROOT / "data" / "chunks" / "langchain_recursive"
    expected_papers = ["1706.03762v7.json", "2410.00037v1.json", "2507.07955v2.json"]

    for filename in expected_papers:
        filepath = chunk_dir / filename
        assert filepath.exists(), f"Missing chunk dataset: {filepath}"

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "paper_id" in data
        assert "chunking_strategy" in data
        assert data["chunking_strategy"] == "langchain_recursive"
        assert "chunks" in data
        assert len(data["chunks"]) > 0

        # Verify chunk structure
        for chunk in data["chunks"]:
            assert "chunk_id" in chunk
            assert "token_count" in chunk
            # Enforce max tokens with accommodation for Stage 8B.2 table caption enrichment
            assert chunk["token_count"] <= 512 or chunk["element_type"] == "table"
            assert "page_number" in chunk
            assert "element_type" in chunk
            assert len(chunk["chunk_text"]) > 0

