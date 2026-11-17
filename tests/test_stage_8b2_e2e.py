"""End-to-end research chat validation tests for Stage 8B.2 using local simulator."""

import asyncio
import pytest
from app.providers.simulator_provider import SimulatorProvider
from app.retrieval.bm25_retriever import BM25Retriever
from app.retrieval.dense_retriever import DenseRetriever
from app.retrieval.fact_store import FactStore
from app.retrieval.hybrid_retriever import HybridRetriever
from app.workflow.graph import build_research_workflow
from app.workflow.schemas import WorkflowConfig
from app.workflow.tools import create_research_retrieval_tool
from simulator.main import app as sim_app, simulator_service


@pytest.fixture(scope="module")
def workflow_setup():
    simulator_service.reset()
    dense = DenseRetriever()
    bm25 = BM25Retriever("data/indexes/bm25/bm25_index.json")
    facts = FactStore("data/indexes/fact_store.db")
    retriever = HybridRetriever(
        dense_retriever=dense,
        bm25_retriever=bm25,
        fact_store=facts,
        rrf_k=60,
    )
    sim_provider = SimulatorProvider(app=sim_app)
    retriever_tool = create_research_retrieval_tool(retriever)
    wf_cfg = WorkflowConfig(top_k=5)
    workflow = build_research_workflow(
        retriever=retriever,
        traffic_manager=sim_provider,
        config=wf_cfg,
        retriever_tool=retriever_tool,
    )
    yield workflow, sim_provider
    facts.close()


def test_transformer_base_bleu_retrieval_and_answer(workflow_setup):
    """Verify the Transformer base BLEU query retrieves 27.3, cites Table 2, p.8, sec 6.1, and passes verification."""
    workflow, _ = workflow_setup
    query = "What BLEU score did the Transformer base model achieve on English-to-German?"
    
    result = asyncio.run(workflow.ainvoke({"question": query}))
    final_resp = result["final_response"]

    # 1. Answer must not be a refusal
    assert not final_resp.is_refusal, f"Expected answerable response, got refusal: {final_resp.answer}"

    # 2. Answer must state 27.3
    assert "27.3" in final_resp.answer, f"Expected 27.3 in answer: {final_resp.answer}"

    # 3. Answer must distinguish base model from big model (28.4)
    assert "base" in final_resp.answer.lower()
    if "28.4" in final_resp.answer:
        assert "big" in final_resp.answer.lower(), "If 28.4 is mentioned, it must be attributed to the big model"

    # 4. Citations must be present and verified
    assert final_resp.verification_status == "verified", f"Expected 'verified', got '{final_resp.verification_status}'"
    assert len(final_resp.citations) > 0, "Expected at least one citation"

    # 5. Must cite paper 1706.03762v7, page 8, section 6.1
    c = final_resp.citations[0]
    assert c.paper_id == "1706.03762v7"
    assert c.page_number == 8
    assert c.section is not None and "6.1" in c.section


def test_grounded_refusal_for_unanswerable_question(workflow_setup):
    """Verify that an unanswerable out-of-domain question results in a grounded refusal."""
    workflow, _ = workflow_setup
    query = "What is the quantum supremacy benchmark achieved by Sycamore processor?"
    
    result = asyncio.run(workflow.ainvoke({"question": query}))
    final_resp = result["final_response"]

    # Must be recognized as insufficient evidence / refusal
    assert final_resp.is_refusal, f"Expected refusal for out-of-domain query, got: {final_resp.answer}"
    assert "unable to answer" in final_resp.answer.lower() or "insufficient" in final_resp.answer.lower()
