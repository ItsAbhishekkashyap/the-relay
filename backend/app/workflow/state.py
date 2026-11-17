"""Workflow state definition for the LangGraph research assistant."""

from typing import Any, Dict, List, Optional, TypedDict
from app.workflow.schemas import (
    Citation,
    CitationVerificationResult,
    FinalResponse,
    RetrievedDocument,
)


class WorkflowState(TypedDict, total=False):
    """Execution state container for the LangGraph research workflow.

    Maintains the question, retrieved evidence, verification results,
    correction attempt counter, and the final structured response.
    """

    question: str
    paper_filter: Optional[str]
    retrieved_documents: List[RetrievedDocument]
    retrieval_diagnostics: Dict[str, Any]
    evidence_sufficient: bool
    answer: str
    citations: List[Citation]
    citation_verification: Optional[CitationVerificationResult]
    correction_attempts: int
    refusal_reason: Optional[str]
    final_response: Optional[FinalResponse]
    error: Optional[str]
    is_refusal: bool
