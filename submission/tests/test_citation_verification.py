"""Tests for citation extraction and deterministic verification logic."""

import pytest
from app.workflow.nodes import extract_citations, verify_citations_against_evidence
from app.workflow.schemas import Citation, RetrievedDocument


@pytest.fixture
def sample_retrieved_docs() -> list[RetrievedDocument]:
    """Sample retrieved evidence documents for testing."""
    return [
        RetrievedDocument(
            chunk_id="chunk_1",
            paper_id="1706.03762v7",
            paper_title="Attention Is All You Need",
            arxiv_id="1706.03762",
            paper_version="v7",
            page_number=3,
            page_numbers=[3],
            section="3.2",
            content="Scaled dot-product attention computes softmax(QK^T / sqrt(d_k))V.",
            score=0.035,
            retrieval_channels=["dense", "bm25"],
        ),
        RetrievedDocument(
            chunk_id="chunk_2",
            paper_id="2410.00037v1",
            paper_title="Moshi: A Speech-Text Foundation Model for Real-Time Dialogue",
            arxiv_id="2410.00037",
            paper_version="v1",
            page_number=2,
            page_numbers=[2],
            section="2.1",
            content="Moshi operates with an end-to-end theoretical latency of 160ms and 200ms in practice.",
            score=0.028,
            retrieval_channels=["dense"],
        ),
        RetrievedDocument(
            chunk_id="chunk_3",
            paper_id="2507.07955v2",
            paper_title="Dynamic Chunking for End-to-End Hierarchical Sequence Modeling",
            arxiv_id="2507.07955",
            paper_version="v2",
            page_number=5,
            page_numbers=[4, 5],
            section="4.1",
            content="Dynamic Chunking adapts boundary thresholds dynamically during sequence processing.",
            score=0.041,
            retrieval_channels=["dense", "fact_store"],
        ),
    ]


def test_extract_citations_standard_format():
    """Verify parsing of standard citations containing title, arXiv ID, page, and section."""
    text = (
        "The model uses multi-head attention [Attention Is All You Need, arXiv:1706.03762v7, p. 3, Section 3.2] "
        "and low latency dialogue [Moshi: A Speech-Text Foundation Model for Real-Time Dialogue, arXiv:2410.00037v1, p. 2]."
    )
    citations = extract_citations(text)
    assert len(citations) == 2

    c1 = citations[0]
    assert c1.paper_id == "1706.03762v7"
    assert c1.page_number == 3
    assert c1.section == "3.2"
    assert c1.paper_title == "Attention Is All You Need"

    c2 = citations[1]
    assert c2.paper_id == "2410.00037v1"
    assert c2.page_number == 2


def test_extract_citations_concise_format():
    """Verify parsing of concise citations like [arXiv:1706.03762v7, p. 3]."""
    text = "Scaled dot product is defined as [arXiv:1706.03762v7, p. 3]."
    citations = extract_citations(text)
    assert len(citations) == 1
    assert citations[0].paper_id == "1706.03762v7"
    assert citations[0].page_number == 3


def test_extract_citations_ignores_markdown_links():
    """Verify that standard markdown links [text](url) are not treated as citations."""
    text = "Visit [the project repository](https://github.com/relay) for code, or see [arXiv:1706.03762v7, p. 3]."
    citations = extract_citations(text)
    assert len(citations) == 1
    assert citations[0].paper_id == "1706.03762v7"


def test_verify_citations_all_valid(sample_retrieved_docs):
    """Valid citations matching retrieved documents pass deterministic verification."""
    text = (
        "The self-attention mechanism operates on queries and keys [Attention Is All You Need, arXiv:1706.03762v7, p. 3, Section 3.2]. "
        "Moshi achieves real-time speech dialogue [arXiv:2410.00037v1, p. 2]."
    )
    citations = extract_citations(text)
    result = verify_citations_against_evidence(citations, sample_retrieved_docs)

    assert result.is_valid is True
    assert len(result.verified_citations) == 2
    assert len(result.invalid_citations) == 0
    assert result.citation_count == 2
    assert len(result.error_messages) == 0
    assert "limit" in result.disclaimer.lower() or "semantic proof" in result.disclaimer.lower()


def test_verify_citations_invented_paper_id(sample_retrieved_docs):
    """Citation with an unrecognized or non-corpus paper ID must fail verification."""
    text = "BERT uses bidirectional representations [BERT, arXiv:1810.04805v2, p. 1]."
    citations = extract_citations(text)
    result = verify_citations_against_evidence(citations, sample_retrieved_docs)

    assert result.is_valid is False
    assert len(result.invalid_citations) == 1
    assert "approved" in result.error_messages[0] or "not in the approved" in result.error_messages[0]


def test_verify_citations_unretrieved_paper_id():
    """Citation referencing an approved paper that was not in retrieved docs must fail."""
    # Only paper 1706.03762v7 was retrieved
    docs = [
        RetrievedDocument(
            chunk_id="c1",
            paper_id="1706.03762v7",
            paper_title="Attention Is All You Need",
            arxiv_id="1706.03762",
            paper_version="v7",
            page_number=3,
            content="Attention content.",
            score=0.05,
        )
    ]
    text = "Moshi speech model [arXiv:2410.00037v1, p. 2]."
    citations = extract_citations(text)
    result = verify_citations_against_evidence(citations, docs)

    assert result.is_valid is False
    assert len(result.invalid_citations) == 1
    assert "not retrieved" in result.error_messages[0]


def test_verify_citations_invented_page_number(sample_retrieved_docs):
    """Citation referencing an unretrieved page number must fail verification."""
    text = "Attention layers are stacked [Attention Is All You Need, arXiv:1706.03762v7, p. 99]."
    citations = extract_citations(text)
    result = verify_citations_against_evidence(citations, sample_retrieved_docs)

    assert result.is_valid is False
    assert len(result.invalid_citations) == 1
    assert "Page 99" in result.error_messages[0]


def test_verify_citations_missing_citations(sample_retrieved_docs):
    """Answer with no citations must fail verification."""
    text = "The Transformer replaces recurrent layers with multi-head self-attention."
    citations = extract_citations(text)
    result = verify_citations_against_evidence(citations, sample_retrieved_docs)

    assert result.is_valid is False
    assert result.citation_count == 0
    assert len(result.error_messages) == 1
    assert "no citations" in result.error_messages[0].lower()


def test_verify_citations_disclaimer_notice():
    """Verify that citation verification results explicitly include the limitation disclaimer."""
    result = verify_citations_against_evidence([], [])
    assert (
        "Deterministic citation verification confirms that cited paper IDs, pages, and sections "
        "exist in the retrieved evidence metadata. It does not constitute full semantic proof of factual accuracy."
    ) == result.disclaimer


def test_verify_citations_correct_section_passes(sample_retrieved_docs):
    """Regression Test 1.1: Correct section matching evidence metadata passes."""
    text = "Scaled dot-product attention [Attention Is All You Need, arXiv:1706.03762v7, p. 3, Section 3.2]."
    citations = extract_citations(text)
    result = verify_citations_against_evidence(citations, sample_retrieved_docs)
    assert result.is_valid is True
    assert len(result.verified_citations) == 1
    assert result.verified_citations[0].section == "3.2"


def test_verify_citations_normalized_section_formatting_passes(sample_retrieved_docs):
    """Regression Test 1.1b: Harmless formatting differences in section pass verification."""
    # "sec. 3.2." or lowercase "architecture"
    text = (
        "Scaled attention [arXiv:1706.03762v7, p. 3, Section sec. 3.2.] and "
        "Moshi model [arXiv:2410.00037v1, p. 2, Section 2.1]."
    )
    citations = extract_citations(text)
    result = verify_citations_against_evidence(citations, sample_retrieved_docs)
    assert result.is_valid is True
    assert len(result.verified_citations) == 2


def test_verify_citations_invented_section_fails(sample_retrieved_docs):
    """Regression Test 1.2: Invented section name not matching evidence metadata fails."""
    text = "Attention layers [Attention Is All You Need, arXiv:1706.03762v7, p. 3, Section Invented Topic]."
    citations = extract_citations(text)
    result = verify_citations_against_evidence(citations, sample_retrieved_docs)
    assert result.is_valid is False
    assert len(result.invalid_citations) == 1
    assert "does not match retrieved section metadata" in result.error_messages[0]


def test_verify_citations_section_on_different_page_fails(sample_retrieved_docs):
    """Regression Test 1.3: Section belonging to page 2 cited for page 3 fails."""
    # Chunk 2 has page_number=2, section="2.1". If cited for p. 3 of paper 2410.00037v1,
    # or if Section 2.1 is cited on page 3 of paper 1706.03762v7:
    text = "Attention mechanism [Attention Is All You Need, arXiv:1706.03762v7, p. 3, Section 2.1]."
    citations = extract_citations(text)
    result = verify_citations_against_evidence(citations, sample_retrieved_docs)
    assert result.is_valid is False
    assert len(result.invalid_citations) == 1
    assert "Section '2.1'" in result.error_messages[0]
    assert "does not match retrieved section metadata" in result.error_messages[0]


def test_verify_citations_without_section_remains_acceptable(sample_retrieved_docs):
    """Regression Test 1.4: Citation without a section remains acceptable if paper and page are valid."""
    text = "Attention mechanism is defined in [Attention Is All You Need, arXiv:1706.03762v7, p. 3]."
    citations = extract_citations(text)
    assert citations[0].section is None
    result = verify_citations_against_evidence(citations, sample_retrieved_docs)
    assert result.is_valid is True
    assert len(result.verified_citations) == 1


def test_verify_citations_missing_page_number_fails(sample_retrieved_docs):
    """Regression Test 2.1: Citation missing page number fails verification."""
    text = "The Transformer architecture [Attention Is All You Need, arXiv:1706.03762v7]."
    citations = extract_citations(text)
    assert len(citations) == 1
    assert citations[0].page_number is None

    result = verify_citations_against_evidence(citations, sample_retrieved_docs)
    assert result.is_valid is False
    assert len(result.invalid_citations) == 1
    assert "missing a required page number reference" in result.error_messages[0]


def test_verify_citations_valid_retrieved_page_passes(sample_retrieved_docs):
    """Regression Test 2.2: Valid retrieved page reference passes."""
    text = "Dynamic Chunking threshold [Dynamic Chunking, arXiv:2507.07955v2, p. 5]."
    citations = extract_citations(text)
    result = verify_citations_against_evidence(citations, sample_retrieved_docs)
    assert result.is_valid is True
    assert result.verified_citations[0].page_number == 5


def test_verify_citations_unapproved_paper_fails():
    """Regression Test 2.4: Citation to an unapproved paper fails."""
    docs = [
        RetrievedDocument(
            chunk_id="c_bert",
            paper_id="1706.03762v7",
            paper_title="Attention Is All You Need",
            arxiv_id="1706.03762",
            paper_version="v7",
            page_number=1,
            content="Content",
            score=0.05,
        )
    ]
    text = "BERT language model [arXiv:1810.04805v2, p. 1]."
    citations = extract_citations(text)
    result = verify_citations_against_evidence(citations, docs)
    assert result.is_valid is False
    assert "not in the approved 3-paper corpus" in result.error_messages[0]

