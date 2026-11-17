"""LangGraph StateGraph workflow construction for research question answering."""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
from typing import Any, Dict, Optional, Union

from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.retrieval.hybrid_retriever import HybridRetriever
from app.workflow.nodes import (
    correction_attempt_node,
    evidence_sufficiency_check_node,
    final_response_node,
    generate_answer_node,
    refusal_node,
    retrieve_evidence_node,
    validate_question_node,
    verify_citations_node,
)
from app.workflow.schemas import WorkflowConfig
from app.workflow.state import WorkflowState
from app.workflow.tools import create_research_retrieval_tool

logger = logging.getLogger(__name__)


class ResearchAssistantWorkflow:
    """Wrapper around compiled LangGraph workflow providing async and sync invocations."""

    def __init__(
        self,
        compiled_graph: CompiledStateGraph,
        config: WorkflowConfig,
        retriever_tool: BaseTool,
    ) -> None:
        self.graph = compiled_graph
        self.config = config
        self.tool = retriever_tool

    async def ainvoke(
        self,
        input_data: Union[str, Dict[str, Any]],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Asynchronously invoke the research assistant workflow."""
        if isinstance(input_data, str):
            initial_state: Dict[str, Any] = {"question": input_data}
        else:
            initial_state = dict(input_data)
        return await self.graph.ainvoke(initial_state, **kwargs)

    def invoke(
        self,
        input_data: Union[str, Dict[str, Any]],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Synchronously invoke the research assistant workflow.

        Safely handles existing running event loops via thread pool delegation.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(lambda: asyncio.run(self.ainvoke(input_data, **kwargs))).result()
        else:
            return asyncio.run(self.ainvoke(input_data, **kwargs))

    def __getattr__(self, name: str) -> Any:
        return getattr(self.graph, name)


def build_research_workflow(
    retriever: HybridRetriever,
    traffic_manager: Any,
    config: Optional[WorkflowConfig] = None,
    retriever_tool: Optional[BaseTool] = None,
) -> ResearchAssistantWorkflow:
    """Construct and compile the LangGraph research assistant StateGraph.

    Args:
        retriever: The unified HybridRetriever instance.
        traffic_manager: The model execution target (TrafficManager or BaseModelProvider).
        config: Optional runtime configuration thresholds.
        retriever_tool: Optional custom LangChain BaseTool (defaults to tool wrapping retriever).

    Returns:
        A compiled ResearchAssistantWorkflow instance.
    """
    cfg = config or WorkflowConfig()
    tool = retriever_tool or create_research_retrieval_tool(retriever)

    # 1. Initialize StateGraph
    builder = StateGraph(WorkflowState)

    # 2. Add Nodes
    def node_validate_question(state: WorkflowState) -> Dict[str, Any]:
        return validate_question_node(state, cfg)

    async def node_retrieve_evidence(state: WorkflowState) -> Dict[str, Any]:
        return await retrieve_evidence_node(state, tool, cfg)

    def node_evidence_sufficiency(state: WorkflowState) -> Dict[str, Any]:
        return evidence_sufficiency_check_node(state, cfg)

    async def node_generate_answer(state: WorkflowState) -> Dict[str, Any]:
        return await generate_answer_node(state, traffic_manager, cfg)

    def node_verify_citations(state: WorkflowState) -> Dict[str, Any]:
        return verify_citations_node(state, cfg)

    async def node_correction_attempt(state: WorkflowState) -> Dict[str, Any]:
        return await correction_attempt_node(state, traffic_manager, cfg)

    def node_refusal(state: WorkflowState) -> Dict[str, Any]:
        return refusal_node(state, cfg)

    def node_final_response(state: WorkflowState) -> Dict[str, Any]:
        return final_response_node(state, cfg)

    builder.add_node("validate_question", node_validate_question)
    builder.add_node("retrieve_evidence", node_retrieve_evidence)
    builder.add_node("evidence_sufficiency_check", node_evidence_sufficiency)
    builder.add_node("generate_answer", node_generate_answer)
    builder.add_node("verify_citations", node_verify_citations)
    builder.add_node("correction_attempt", node_correction_attempt)
    builder.add_node("refusal", node_refusal)
    builder.add_node("final_response", node_final_response)

    # 3. Define Conditional Routing Functions
    def route_after_validate(state: WorkflowState) -> str:
        if state.get("is_refusal"):
            return "refusal"
        return "retrieve_evidence"

    def route_after_retrieve(state: WorkflowState) -> str:
        if state.get("is_refusal"):
            return "refusal"
        return "evidence_sufficiency_check"

    def route_after_sufficiency(state: WorkflowState) -> str:
        if state.get("is_refusal") or not state.get("evidence_sufficient"):
            return "refusal"
        return "generate_answer"

    def route_after_generate(state: WorkflowState) -> str:
        if state.get("is_refusal"):
            return "refusal"
        return "verify_citations"

    def route_after_verify(state: WorkflowState) -> str:
        verification = state.get("citation_verification")
        if verification and verification.is_valid:
            return "final_response"

        attempts = state.get("correction_attempts", 0)
        if attempts < cfg.max_correction_attempts:
            return "correction_attempt"
        return "refusal"

    # 4. Add Edges and Conditional Edges
    builder.add_edge(START, "validate_question")

    builder.add_conditional_edges(
        "validate_question",
        route_after_validate,
        {"refusal": "refusal", "retrieve_evidence": "retrieve_evidence"},
    )

    builder.add_conditional_edges(
        "retrieve_evidence",
        route_after_retrieve,
        {"refusal": "refusal", "evidence_sufficiency_check": "evidence_sufficiency_check"},
    )

    builder.add_conditional_edges(
        "evidence_sufficiency_check",
        route_after_sufficiency,
        {"refusal": "refusal", "generate_answer": "generate_answer"},
    )

    builder.add_conditional_edges(
        "generate_answer",
        route_after_generate,
        {"refusal": "refusal", "verify_citations": "verify_citations"},
    )

    builder.add_conditional_edges(
        "verify_citations",
        route_after_verify,
        {
            "final_response": "final_response",
            "correction_attempt": "correction_attempt",
            "refusal": "refusal",
        },
    )

    # Unconditional loop-back from correction_attempt to verify_citations
    builder.add_edge("correction_attempt", "verify_citations")

    # Unconditional routing from refusal to final_response
    builder.add_edge("refusal", "final_response")

    # Terminal edge from final_response to END
    builder.add_edge("final_response", END)

    # 5. Compile
    compiled = builder.compile()

    return ResearchAssistantWorkflow(compiled, cfg, tool)
