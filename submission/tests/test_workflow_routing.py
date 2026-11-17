"""Tests for workflow routing, conditional edges, and bounded correction loop."""

from unittest.mock import AsyncMock, MagicMock
import pytest

from app.providers.schemas import GenerationResponse, TokenUsage
from app.retrieval.hybrid_retriever import HybridRetrievalResult
from app.workflow import WorkflowConfig, build_research_workflow


def make_generation_response(text: str) -> GenerationResponse:
    """Helper to construct standard GenerationResponse objects."""
    return GenerationResponse(
        request_id="test-req",
        response_text=text,
        provider_name="groq",
        model_name="llama-3.3-70b-versatile",
        total_latency=0.25,
        token_usage=TokenUsage(prompt_tokens=40, completion_tokens=20, total_tokens=60),
    )


@pytest.fixture
def valid_transformer_chunk() -> dict:
    """Fixture providing a valid chunk from Attention Is All You Need."""
    return {
        "chunk_id": "c_attn_1",
        "paper_id": "1706.03762v7",
        "paper_title": "Attention Is All You Need",
        "arxiv_id": "1706.03762",
        "paper_version": "v7",
        "page_number": 3,
        "page_numbers": [3],
        "section": "3.2",
        "content": "The Transformer model architecture uses self-attention mechanisms to compute representations.",
        "score": 0.045,
        "retrieval_channels": ["dense", "bm25"],
    }


def test_empty_question_routes_to_refusal():
    """Empty or whitespace-only questions must be immediately refused."""
    retriever = MagicMock()
    traffic_manager = MagicMock()
    wf = build_research_workflow(retriever, traffic_manager)

    result = wf.invoke({"question": "   \n\t  "})
    final = result["final_response"]

    assert final.is_refusal is True
    assert "empty" in final.refusal_reason.lower()
    assert final.verification_status == "refused"
    # Retrieval should not be invoked for empty input
    retriever.retrieve.assert_not_called()


def test_excessively_long_question_routes_to_refusal():
    """Questions exceeding configured length limit must be refused."""
    retriever = MagicMock()
    traffic_manager = MagicMock()
    cfg = WorkflowConfig(max_question_length=50)
    wf = build_research_workflow(retriever, traffic_manager, config=cfg)

    long_q = "What is the architecture of the Transformer model in deep learning? " * 5
    result = wf.invoke({"question": long_q})
    final = result["final_response"]

    assert final.is_refusal is True
    assert "exceeds" in final.refusal_reason.lower()
    retriever.retrieve.assert_not_called()


def test_zero_retrieved_chunks_routes_to_refusal():
    """When retriever returns 0 chunks, workflow must route to refusal."""
    retriever = MagicMock()
    retriever.retrieve.return_value = HybridRetrievalResult([], diagnostics={})
    traffic_manager = MagicMock()
    wf = build_research_workflow(retriever, traffic_manager)

    result = wf.invoke({"question": "How does multi-head attention work?"})
    final = result["final_response"]

    assert final.is_refusal is True
    assert "No relevant evidence" in final.refusal_reason
    assert final.verification_status == "refused"
    traffic_manager.execute.assert_not_called()


def test_insufficient_content_chars_routes_to_refusal(valid_transformer_chunk):
    """When chunks have negligible text (< min_total_content_chars), refuse."""
    short_chunk = dict(valid_transformer_chunk)
    short_chunk["content"] = "Too short."  # 10 chars
    retriever = MagicMock()
    retriever.retrieve.return_value = HybridRetrievalResult([short_chunk], diagnostics={})
    traffic_manager = MagicMock()
    cfg = WorkflowConfig(min_total_content_chars=60)
    wf = build_research_workflow(retriever, traffic_manager, config=cfg)

    result = wf.invoke({"question": "How does attention work?"})
    final = result["final_response"]

    assert final.is_refusal is True
    assert "insufficient text" in final.refusal_reason.lower()
    traffic_manager.execute.assert_not_called()


def test_insufficient_rrf_score_routes_to_refusal(valid_transformer_chunk):
    """When top chunk score is below threshold, refuse."""
    low_score_chunk = dict(valid_transformer_chunk)
    low_score_chunk["score"] = 0.001
    retriever = MagicMock()
    retriever.retrieve.return_value = HybridRetrievalResult([low_score_chunk], diagnostics={})
    traffic_manager = MagicMock()
    cfg = WorkflowConfig(min_top_rrf_score=0.01)
    wf = build_research_workflow(retriever, traffic_manager, config=cfg)

    result = wf.invoke({"question": "How does attention work?"})
    final = result["final_response"]

    assert final.is_refusal is True
    assert "below the sufficiency threshold" in final.refusal_reason.lower()
    traffic_manager.execute.assert_not_called()


def test_out_of_domain_question_routes_to_refusal(valid_transformer_chunk):
    """Unrelated out-of-domain questions with 0 token overlap must be refused."""
    retriever = MagicMock()
    retriever.retrieve.return_value = HybridRetrievalResult([valid_transformer_chunk], diagnostics={})
    traffic_manager = MagicMock()
    wf = build_research_workflow(retriever, traffic_manager)

    result = wf.invoke({"question": "What is the recipe for baking chocolate brownies?"})
    final = result["final_response"]

    assert final.is_refusal is True
    assert "out-of-domain" in final.refusal_reason.lower()
    traffic_manager.execute.assert_not_called()


def test_valid_citation_routes_directly_to_final_response(valid_transformer_chunk):
    """Grounded answer with valid citations routes straight to final_response without correction."""
    retriever = MagicMock()
    retriever.retrieve.return_value = HybridRetrievalResult([valid_transformer_chunk], diagnostics={})
    traffic_manager = MagicMock()
    resp = make_generation_response(
        "The Transformer uses self-attention [Attention Is All You Need, arXiv:1706.03762v7, p. 3, Section 3.2]."
    )
    traffic_manager.execute = AsyncMock(return_value=resp)

    wf = build_research_workflow(retriever, traffic_manager)
    result = wf.invoke({"question": "How does the Transformer model compute representations?"})
    final = result["final_response"]

    assert final.is_refusal is False
    assert final.verification_status == "verified"
    assert final.correction_occurred is False
    assert final.workflow_metadata["correction_attempts"] == 0
    assert len(final.citations) == 1
    assert traffic_manager.execute.call_count == 1


def test_failed_citation_triggers_correction_and_succeeds(valid_transformer_chunk):
    """When first generation has invalid citation, correction attempt runs and succeeds."""
    retriever = MagicMock()
    retriever.retrieve.return_value = HybridRetrievalResult([valid_transformer_chunk], diagnostics={})
    traffic_manager = MagicMock()

    # Attempt 1 has invalid page 99, Attempt 2 corrects to valid page 3
    bad_resp = make_generation_response(
        "Self attention computes representations [Attention Is All You Need, arXiv:1706.03762v7, p. 99]."
    )
    good_resp = make_generation_response(
        "Self attention computes representations [Attention Is All You Need, arXiv:1706.03762v7, p. 3]."
    )
    traffic_manager.execute = AsyncMock(side_effect=[bad_resp, good_resp])

    wf = build_research_workflow(retriever, traffic_manager)
    result = wf.invoke({"question": "How does the Transformer model compute representations?"})
    final = result["final_response"]

    assert final.is_refusal is False
    assert final.verification_status == "verified"
    assert final.correction_occurred is True
    assert final.workflow_metadata["correction_attempts"] == 1
    assert len(final.citations) == 1
    assert final.citations[0].page_number == 3
    assert traffic_manager.execute.call_count == 2


def test_failed_citation_correction_fails_second_time_routes_to_refusal(valid_transformer_chunk):
    """When correction attempt also fails verification, workflow routes to refusal."""
    retriever = MagicMock()
    retriever.retrieve.return_value = HybridRetrievalResult([valid_transformer_chunk], diagnostics={})
    traffic_manager = MagicMock()

    # Both attempts produce invalid citations
    bad_resp1 = make_generation_response(
        "First attempt with invalid page [Attention Is All You Need, arXiv:1706.03762v7, p. 99]."
    )
    bad_resp2 = make_generation_response(
        "Second attempt still invalid [Attention Is All You Need, arXiv:1706.03762v7, p. 88]."
    )
    traffic_manager.execute = AsyncMock(side_effect=[bad_resp1, bad_resp2])

    wf = build_research_workflow(retriever, traffic_manager)
    result = wf.invoke({"question": "How does the Transformer model compute representations?"})
    final = result["final_response"]

    assert final.is_refusal is True
    assert final.verification_status == "refused"
    assert final.correction_occurred is True
    assert final.workflow_metadata["correction_attempts"] == 1
    assert "failed citation verification" in final.refusal_reason.lower()
    # Verify that it did not retry a 3rd time
    assert traffic_manager.execute.call_count == 2


def test_correction_attempts_strictly_bounded_to_one(valid_transformer_chunk):
    """Verify that correction loop is hard-capped at 1 attempt."""
    retriever = MagicMock()
    retriever.retrieve.return_value = HybridRetrievalResult([valid_transformer_chunk], diagnostics={})
    traffic_manager = MagicMock()

    bad_resp = make_generation_response("Invalid citation [Invented, arXiv:9999.99999v1, p. 1].")
    traffic_manager.execute = AsyncMock(return_value=bad_resp)

    wf = build_research_workflow(retriever, traffic_manager)
    result = wf.invoke({"question": "How does the Transformer model compute representations?"})

    assert traffic_manager.execute.call_count == 2  # 1 initial + 1 correction retry
    assert result["final_response"].workflow_metadata["correction_attempts"] == 1
