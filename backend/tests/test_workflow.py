"""Comprehensive end-to-end tests for the LangGraph research assistant workflow."""

import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest
from langchain_core.tools import BaseTool

from app.providers.schemas import GenerationResponse, TokenUsage
from app.retrieval.hybrid_retriever import HybridRetrievalResult, RetrievalError
from app.traffic.errors import ExecutionTimeoutError
from app.workflow import (
    WorkflowConfig,
    build_research_workflow,
    create_research_retrieval_tool,
)
from app.workflow.schemas import FinalResponse


def make_resp(text: str) -> GenerationResponse:
    """Helper to create GenerationResponse instances."""
    return GenerationResponse(
        request_id="test-req",
        response_text=text,
        provider_name="groq",
        model_name="llama-3.3-70b-versatile",
        total_latency=0.3,
        token_usage=TokenUsage(prompt_tokens=50, completion_tokens=30, total_tokens=80),
    )


@pytest.fixture
def moshi_evidence_chunk() -> dict:
    """Realistic chunk fixture from Moshi paper."""
    return {
        "chunk_id": "moshi_c1",
        "paper_id": "2410.00037v1",
        "paper_title": "Moshi: A Speech-Text Foundation Model for Real-Time Dialogue",
        "arxiv_id": "2410.00037",
        "paper_version": "v1",
        "page_number": 2,
        "page_numbers": [2],
        "section": "2. Architecture",
        "content": (
            "Moshi is a speech-text foundation model capable of full-duplex real-time spoken dialogue. "
            "It achieves a theoretical latency of 160ms and an empirical latency of 200ms on server hardware."
        ),
        "score": 0.052,
        "retrieval_channels": ["dense", "bm25"],
    }


def test_workflow_invokes_genuine_langchain_tool(moshi_evidence_chunk):
    """Verify that the retrieval node invokes a genuine LangChain BaseTool."""
    retriever = MagicMock()
    retriever.retrieve.return_value = HybridRetrievalResult([moshi_evidence_chunk], diagnostics={})

    # Create the genuine LangChain tool
    tool = create_research_retrieval_tool(retriever)
    assert isinstance(tool, BaseTool)
    assert tool.name == "search_research_papers"

    # Spy on tool function execution
    spy = MagicMock(side_effect=tool.func)
    tool.func = spy

    traffic_manager = MagicMock()
    traffic_manager.execute = AsyncMock(
        return_value=make_resp(
            "Moshi achieves 160ms theoretical latency [Moshi: A Speech-Text Foundation Model for Real-Time Dialogue, arXiv:2410.00037v1, p. 2]."
        )
    )

    wf = build_research_workflow(retriever, traffic_manager, retriever_tool=tool)
    result = wf.invoke({"question": "What is the latency of Moshi?"})

    assert spy.called
    assert retriever.retrieve.called
    assert result["final_response"].is_refusal is False
    assert result["final_response"].verification_status == "verified"


def test_full_successful_answer_flow(moshi_evidence_chunk):
    """Verify full end-to-end question answering flow with complete response schema validation."""
    retriever = MagicMock()
    retriever.retrieve.return_value = HybridRetrievalResult(
        [moshi_evidence_chunk],
        diagnostics={"successful_channels": ["dense", "bm25"], "failed_channels": {}},
    )

    traffic_manager = MagicMock()
    traffic_manager.execute = AsyncMock(
        return_value=make_resp(
            "Moshi has a theoretical latency of 160ms [arXiv:2410.00037v1, p. 2]."
        )
    )

    wf = build_research_workflow(retriever, traffic_manager)
    result = wf.invoke({"question": "What latency does Moshi achieve in spoken dialogue?"})

    final: FinalResponse = result["final_response"]
    assert isinstance(final, FinalResponse)
    assert final.question == "What latency does Moshi achieve in spoken dialogue?"
    assert "160ms" in final.answer
    assert final.is_refusal is False
    assert final.refusal_reason is None
    assert final.verification_status == "verified"
    assert final.correction_occurred is False
    assert len(final.citations) == 1
    assert final.citations[0].paper_id == "2410.00037v1"
    assert final.citations[0].page_number == 2
    assert final.citations[0].is_verified is True
    assert len(final.retrieved_sources) == 1
    assert final.retrieved_sources[0].chunk_id == "moshi_c1"
    assert final.workflow_metadata["retrieved_chunk_count"] == 1


def test_complete_retrieval_failure_raises_controlled_refusal():
    """When HybridRetriever raises RetrievalError across all channels, workflow refuses cleanly."""
    retriever = MagicMock()
    retriever.retrieve.side_effect = RetrievalError(
        "All channels failed",
        failed_channels={"dense": "Chroma connection error", "bm25": "Corrupted index"},
    )
    traffic_manager = MagicMock()

    wf = build_research_workflow(retriever, traffic_manager)
    result = wf.invoke({"question": "How does attention work?"})

    final = result["final_response"]
    assert final.is_refusal is True
    assert "retrieval failed across all channels" in final.refusal_reason.lower()
    assert final.verification_status == "refused"
    # TrafficManager must not be called on retrieval failure
    traffic_manager.execute.assert_not_called()


def test_partial_retrieval_failure_gracefully_continues(moshi_evidence_chunk):
    """When one channel fails but another succeeds, workflow proceeds to answer."""
    retriever = MagicMock()
    # BM25 failed, but dense succeeded with evidence
    retriever.retrieve.return_value = HybridRetrievalResult(
        [moshi_evidence_chunk],
        diagnostics={
            "successful_channels": ["dense"],
            "failed_channels": {"bm25": "Tokenization error"},
        },
    )

    traffic_manager = MagicMock()
    traffic_manager.execute = AsyncMock(
        return_value=make_resp("Moshi latency is 160ms [arXiv:2410.00037v1, p. 2].")
    )

    wf = build_research_workflow(retriever, traffic_manager)
    result = wf.invoke({"question": "What is the latency of Moshi?"})

    final = result["final_response"]
    assert final.is_refusal is False
    assert final.verification_status == "verified"
    assert "bm25" in final.workflow_metadata["diagnostics"]["failed_channels"]


def test_traffic_manager_execution_timeout_refuses_without_fabrication(moshi_evidence_chunk):
    """When TrafficManager execution times out, workflow returns controlled refusal."""
    retriever = MagicMock()
    retriever.retrieve.return_value = HybridRetrievalResult([moshi_evidence_chunk], diagnostics={})

    traffic_manager = MagicMock()
    traffic_manager.execute = AsyncMock(side_effect=ExecutionTimeoutError("Execution deadline exceeded"))

    wf = build_research_workflow(retriever, traffic_manager)
    result = wf.invoke({"question": "What is the latency of Moshi?"})

    final = result["final_response"]
    assert final.is_refusal is True
    assert "model generation failed" in final.refusal_reason.lower()
    assert "Execution deadline exceeded" in final.refusal_reason
    assert final.verification_status == "refused"


def test_async_workflow_ainvoke_execution(moshi_evidence_chunk):
    """Verify asynchronous invocation via ainvoke."""
    retriever = MagicMock()
    retriever.retrieve.return_value = HybridRetrievalResult([moshi_evidence_chunk], diagnostics={})

    traffic_manager = MagicMock()
    traffic_manager.execute = AsyncMock(
        return_value=make_resp("Moshi is a speech-text model [arXiv:2410.00037v1, p. 2].")
    )

    wf = build_research_workflow(retriever, traffic_manager)

    async def run_async():
        return await wf.ainvoke({"question": "What is Moshi?"})

    result = asyncio.run(run_async())
    final = result["final_response"]
    assert final.is_refusal is False
    assert final.verification_status == "verified"


def test_custom_workflow_config_top_k():
    """Verify that custom top_k_retrieval in WorkflowConfig is passed to retriever."""
    retriever = MagicMock()
    retriever.retrieve.return_value = HybridRetrievalResult([], diagnostics={})
    traffic_manager = MagicMock()

    cfg = WorkflowConfig(top_k_retrieval=8)
    wf = build_research_workflow(retriever, traffic_manager, config=cfg)
    wf.invoke({"question": "Test query for top_k"})

    retriever.retrieve.assert_called_once()
    assert retriever.retrieve.call_args.kwargs.get("top_k") == 8


def test_correction_prompt_contains_full_evidence_and_context(moshi_evidence_chunk):
    """Regression Test 3: Verify correction prompt includes full evidence content and metadata."""
    retriever = MagicMock()
    retriever.retrieve.return_value = HybridRetrievalResult([moshi_evidence_chunk], diagnostics={})

    initial_bad_answer = "Moshi has low latency [arXiv:2410.00037v1, p. 99]."
    corrected_good_answer = "Moshi has theoretical latency 160ms [arXiv:2410.00037v1, p. 2]."

    bad_resp = make_resp(initial_bad_answer)
    good_resp = make_resp(corrected_good_answer)

    traffic_manager = MagicMock()
    traffic_manager.execute = AsyncMock(side_effect=[bad_resp, good_resp])

    wf = build_research_workflow(retriever, traffic_manager)
    question = "What latency does Moshi achieve in spoken dialogue?"
    result = wf.invoke({"question": question})

    assert traffic_manager.execute.call_count == 2

    # Inspect the GenerationRequest sent to the correction attempt (call 2)
    correction_call_args = traffic_manager.execute.call_args_list[1]
    correction_request = correction_call_args[0][0]  # first positional arg is GenerationRequest
    prompt_text = correction_request.prompt

    # 1. Original question is present
    assert question in prompt_text

    # 2. Retrieved passage content is present
    assert moshi_evidence_chunk["content"] in prompt_text

    # 3. Paper ID and page metadata are present
    assert moshi_evidence_chunk["paper_id"] in prompt_text
    assert f"p. {moshi_evidence_chunk['page_number']}" in prompt_text
    assert moshi_evidence_chunk["section"] in prompt_text

    # 4. Citation verification errors are present
    assert "Page 99" in prompt_text

    # 5. Previous answer is present
    assert initial_bad_answer in prompt_text

    # Verify final result succeeded
    assert result["final_response"].is_refusal is False
    assert result["final_response"].verification_status == "verified"
    assert result["final_response"].correction_occurred is True

