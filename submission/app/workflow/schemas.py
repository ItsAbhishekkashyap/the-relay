"""Pydantic schemas and configuration for the LangGraph research assistant workflow."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class Citation(BaseModel):
    """Structured representation of a parsed citation reference."""

    raw_text: str = Field(description="Verbatim citation string extracted from the generated answer.")
    paper_title: Optional[str] = Field(default=None, description="Title of the referenced paper if parsed.")
    paper_id: Optional[str] = Field(default=None, description="ArXiv identifier with version (e.g. '1706.03762v7').")
    page_number: Optional[int] = Field(default=None, description="Specific page number cited if present.")
    section: Optional[str] = Field(default=None, description="Section name or number cited if present.")
    is_verified: bool = Field(default=False, description="True if citation matches retrieved chunk metadata.")
    verification_error: Optional[str] = Field(default=None, description="Diagnostic error if verification failed.")


class CitationVerificationResult(BaseModel):
    """Diagnostic outcome of deterministic citation verification."""

    is_valid: bool = Field(description="True if all claims are cited and every citation matches retrieved sources.")
    verified_citations: List[Citation] = Field(default_factory=list, description="Citations confirmed in evidence.")
    invalid_citations: List[Citation] = Field(default_factory=list, description="Citations failing metadata matching.")
    citation_count: int = Field(default=0, description="Total citations extracted from answer.")
    error_messages: List[str] = Field(default_factory=list, description="Diagnostic error messages.")
    disclaimer: str = Field(
        default=(
            "Deterministic citation verification confirms that cited paper IDs, pages, and sections "
            "exist in the retrieved evidence metadata. It does not constitute full semantic proof of factual accuracy."
        ),
        description="Explicit limitation notice.",
    )


class RetrievedDocument(BaseModel):
    """Standardized representation of an evidence passage retrieved from the hybrid engine."""

    chunk_id: str
    paper_id: str
    paper_title: str
    arxiv_id: str
    paper_version: str
    page_number: Optional[int] = None
    page_numbers: List[int] = Field(default_factory=list)
    section: Optional[str] = None
    content: str
    score: float = 0.0
    retrieval_channels: List[str] = Field(default_factory=list)


class FinalResponse(BaseModel):
    """Complete, structured user-facing response from the research assistant workflow."""

    question: str = Field(description="The original user research question.")
    answer: str = Field(description="The verified grounded answer, or an explicit refusal.")
    is_refusal: bool = Field(default=False, description="True if the question was refused.")
    refusal_reason: Optional[str] = Field(default=None, description="Explanation for refusal if applicable.")
    citations: List[Citation] = Field(default_factory=list, description="Verified citations supporting the answer.")
    retrieved_sources: List[RetrievedDocument] = Field(
        default_factory=list, description="Passages provided as context to generation."
    )
    verification_status: str = Field(description="'verified', 'unverified', or 'refused'.")
    correction_occurred: bool = Field(default=False, description="True if a correction attempt was executed.")
    workflow_metadata: Dict[str, Any] = Field(default_factory=dict, description="Operational workflow statistics.")


class WorkflowConfig(BaseModel):
    """Runtime configuration thresholds and limits for the research assistant workflow."""

    max_question_length: int = Field(default=1000, ge=10, description="Maximum characters allowed in question.")
    top_k_retrieval: int = Field(default=5, ge=1, description="Number of evidence chunks to retrieve.")
    min_chunks_required: int = Field(default=1, ge=1, description="Minimum retrieved chunks for sufficiency.")
    min_total_content_chars: int = Field(default=60, ge=10, description="Minimum combined text characters in chunks.")
    min_top_rrf_score: float = Field(default=0.005, ge=0.0, description="Minimum RRF score for top candidate.")
    max_correction_attempts: int = Field(default=1, ge=1, le=1, description="Strictly bounded to 1 retry attempt.")
    generation_timeout: float = Field(default=30.0, ge=1.0, description="Request timeout for TrafficManager.")
    max_tokens: int = Field(default=1024, ge=50, description="Max tokens for completion generation.")
    temperature: float = Field(default=0.0, ge=0.0, le=1.0, description="Sampling temperature (deterministic).")
