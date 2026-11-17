"""LangGraph Research Workflow Integration for The Relay research assistant."""

from app.workflow.graph import ResearchAssistantWorkflow, build_research_workflow
from app.workflow.nodes import (
    APPROVED_PAPER_IDS,
    CANONICAL_ID_MAP,
    extract_citations,
    verify_citations_against_evidence,
)
from app.workflow.schemas import (
    Citation,
    CitationVerificationResult,
    FinalResponse,
    RetrievedDocument,
    WorkflowConfig,
)
from app.workflow.state import WorkflowState
from app.workflow.tools import create_research_retrieval_tool

__all__ = [
    "build_research_workflow",
    "ResearchAssistantWorkflow",
    "WorkflowConfig",
    "WorkflowState",
    "Citation",
    "CitationVerificationResult",
    "RetrievedDocument",
    "FinalResponse",
    "create_research_retrieval_tool",
    "extract_citations",
    "verify_citations_against_evidence",
    "APPROVED_PAPER_IDS",
    "CANONICAL_ID_MAP",
]
