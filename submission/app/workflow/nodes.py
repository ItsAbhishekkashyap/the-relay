"""Workflow node implementations and citation verification logic."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Set

from langchain_core.tools import BaseTool
from app.providers.schemas import GenerationRequest
from app.workflow.schemas import (
    Citation,
    CitationVerificationResult,
    FinalResponse,
    RetrievedDocument,
    WorkflowConfig,
)
from app.workflow.state import WorkflowState

logger = logging.getLogger(__name__)

APPROVED_PAPER_IDS: Set[str] = {
    "1706.03762v7",
    "2410.00037v1",
    "2507.07955v2",
}

CANONICAL_ID_MAP: Dict[str, str] = {
    "1706.03762": "1706.03762v7",
    "2410.00037": "2410.00037v1",
    "2507.07955": "2507.07955v2",
}

TITLE_TO_ID_MAP: Dict[str, str] = {
    "attention is all you need": "1706.03762v7",
    "moshi": "2410.00037v1",
    "dynamic chunking": "2507.07955v2",
}

STOPWORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "cannot", "could", "did", "do",
    "does", "doing", "down", "during", "each", "explain", "few", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here", "hers", "herself",
    "him", "himself", "his", "how", "i", "if", "in", "into", "is", "isn't", "it",
    "its", "itself", "me", "more", "most", "my", "myself", "no", "nor", "not", "of",
    "off", "on", "once", "only", "or", "other", "ought", "our", "ours", "ourselves",
    "out", "over", "own", "same", "she", "should", "so", "some", "such", "tell",
    "than", "that", "the", "their", "theirs", "them", "themselves", "then", "there",
    "these", "they", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "wasn't", "we", "were", "weren't", "what", "when", "where", "which",
    "while", "who", "whom", "why", "with", "won't", "would", "you", "your", "yours",
}


def extract_citations(answer: str) -> List[Citation]:
    """Extract citation candidates matching bracketed references from generated text.

    Excludes standard markdown links [text](url).
    """
    citations: List[Citation] = []
    # Match brackets not immediately followed by (
    raw_matches = re.findall(r"\[([^\]]+)\](?!\()", answer)

    for raw in raw_matches:
        raw_clean = raw.strip()
        if not raw_clean:
            continue

        # Look for arXiv ID
        paper_id: Optional[str] = None
        pid_match = re.search(r"(?:arxiv:\s*)?([0-9]{4}\.[0-9]{4,5}(?:v[0-9]+)?)", raw_clean, re.IGNORECASE)
        if pid_match:
            candidate_id = pid_match.group(1)
            # Normalize to canonical versioned ID if version missing
            paper_id = CANONICAL_ID_MAP.get(candidate_id, candidate_id)
        else:
            # Check title-based fallback
            lower_raw = raw_clean.lower()
            for title_sub, mapped_id in TITLE_TO_ID_MAP.items():
                if title_sub in lower_raw:
                    paper_id = mapped_id
                    break

        # Look for page number
        page_number: Optional[int] = None
        page_match = re.search(r"\b(?:p\.|page|pages)\s*([0-9]+)\b", raw_clean, re.IGNORECASE)
        if page_match:
            try:
                page_number = int(page_match.group(1))
            except ValueError:
                pass

        # Look for section
        section: Optional[str] = None
        sec_match = re.search(r"\b(?:section|sec\.)\s*([^,\]]+)", raw_clean, re.IGNORECASE)
        if sec_match:
            section = sec_match.group(1).strip()

        # Paper title
        paper_title: Optional[str] = None
        if "attention is all you need" in raw_clean.lower():
            paper_title = "Attention Is All You Need"
        elif "moshi" in raw_clean.lower():
            paper_title = "Moshi: A Speech-Text Foundation Model for Real-Time Dialogue"
        elif "dynamic chunking" in raw_clean.lower():
            paper_title = "Dynamic Chunking for End-to-End Hierarchical Sequence Modeling"
        elif "," in raw_clean:
            first_part = raw_clean.split(",")[0].strip()
            if not first_part.lower().startswith("arxiv:"):
                paper_title = first_part

        citations.append(
            Citation(
                raw_text=f"[{raw_clean}]",
                paper_title=paper_title,
                paper_id=paper_id,
                page_number=page_number,
                section=section,
            )
        )

    return citations


def normalize_section_str(section_name: str) -> str:
    """Normalize section strings for robust metadata comparison.

    Strips common prefixes ('section', 'sec.'), punctuation, and excessive whitespace.
    """
    s = section_name.lower().strip()
    s = re.sub(r"^(?:section|sec\.?)\s*", "", s)
    s = s.strip(" .:,;-_")
    s = re.sub(r"\s+", " ", s)
    return s


def sections_match(cited_section: str, evidence_section: str) -> bool:
    """Check if a cited section matches retrieved evidence section metadata.

    Normalizes casing, punctuation, and harmless formatting differences.
    """
    c_norm = normalize_section_str(cited_section)
    e_norm = normalize_section_str(evidence_section)
    if not c_norm or not e_norm:
        return False
    if c_norm == e_norm:
        return True
    pattern = r"(?:\b|_)" + re.escape(c_norm) + r"(?:\b|_)"
    rev_pattern = r"(?:\b|_)" + re.escape(e_norm) + r"(?:\b|_)"
    return bool(re.search(pattern, e_norm) or re.search(rev_pattern, c_norm))


def verify_citations_against_evidence(
    citations: List[Citation],
    retrieved_docs: List[RetrievedDocument],
) -> CitationVerificationResult:
    """Deterministically verify parsed citations against retrieved chunk metadata."""
    if not citations:
        return CitationVerificationResult(
            is_valid=False,
            verified_citations=[],
            invalid_citations=[],
            citation_count=0,
            error_messages=["Answer contains no citations to ground factual claims."],
        )

    verified: List[Citation] = []
    invalid: List[Citation] = []
    error_messages: List[str] = []

    for citation in citations:
        # 1. Must have an identifiable paper ID
        if not citation.paper_id:
            citation.is_verified = False
            citation.verification_error = (
                f"Citation '{citation.raw_text}' is missing a recognized arXiv paper identifier."
            )
            invalid.append(citation)
            error_messages.append(citation.verification_error)
            continue

        # 2. Must belong to the 3 approved research papers
        if citation.paper_id not in APPROVED_PAPER_IDS:
            citation.is_verified = False
            citation.verification_error = (
                f"Paper ID '{citation.paper_id}' is not in the approved 3-paper corpus."
            )
            invalid.append(citation)
            error_messages.append(citation.verification_error)
            continue

        # 3. Must be present in the retrieved evidence set
        matching_docs = [
            doc for doc in retrieved_docs
            if doc.paper_id == citation.paper_id
            or doc.arxiv_id == citation.paper_id
            or (citation.paper_id and doc.paper_id.split("v")[0] == citation.paper_id.split("v")[0])
        ]

        if not matching_docs:
            citation.is_verified = False
            citation.verification_error = (
                f"Paper ID '{citation.paper_id}' was not retrieved in the evidence set."
            )
            invalid.append(citation)
            error_messages.append(citation.verification_error)
            continue

        # 4. Must specify a valid page number
        if citation.page_number is None:
            citation.is_verified = False
            citation.verification_error = (
                f"Citation '{citation.raw_text}' is missing a required page number reference."
            )
            invalid.append(citation)
            error_messages.append(citation.verification_error)
            continue

        # 5. Page number must match retrieved pages for that paper
        available_pages: Set[int] = set()
        for doc in matching_docs:
            if doc.page_number is not None:
                available_pages.add(doc.page_number)
            if doc.page_numbers:
                available_pages.update(doc.page_numbers)

        if citation.page_number not in available_pages:
            citation.is_verified = False
            sorted_pages = sorted(list(available_pages))
            citation.verification_error = (
                f"Page {citation.page_number} for paper '{citation.paper_id}' is not present in "
                f"retrieved chunks (available pages: {sorted_pages or 'none'})."
            )
            invalid.append(citation)
            error_messages.append(citation.verification_error)
            continue

        # 6. If section is provided, verify it against retrieved chunks for that paper AND page
        if citation.section:
            page_docs = [
                doc for doc in matching_docs
                if doc.page_number == citation.page_number
                or (doc.page_numbers and citation.page_number in doc.page_numbers)
            ]
            available_sections = [doc.section for doc in page_docs if doc.section]
            section_matched = any(
                sections_match(citation.section, sec)
                for sec in available_sections
            )
            if not section_matched:
                citation.is_verified = False
                avail_sec_str = (
                    ", ".join(f"'{s}'" for s in available_sections)
                    if available_sections
                    else "none"
                )
                citation.verification_error = (
                    f"Section '{citation.section}' for paper '{citation.paper_id}' (p. {citation.page_number}) "
                    f"does not match retrieved section metadata (available sections on page {citation.page_number}: {avail_sec_str})."
                )
                invalid.append(citation)
                error_messages.append(citation.verification_error)
                continue

        # Citation passed all deterministic checks
        citation.is_verified = True
        citation.verification_error = None
        verified.append(citation)

    is_valid = (len(invalid) == 0 and len(verified) > 0)

    return CitationVerificationResult(
        is_valid=is_valid,
        verified_citations=verified,
        invalid_citations=invalid,
        citation_count=len(citations),
        error_messages=error_messages,
    )


# ============================================================================
# WORKFLOW NODES
# ============================================================================


def validate_question_node(state: WorkflowState, config: WorkflowConfig) -> Dict[str, Any]:
    """Node 1: Validate input question format and length."""
    question = state.get("question")
    if not question or not isinstance(question, str) or not question.strip():
        return {
            "is_refusal": True,
            "refusal_reason": "Question is empty or whitespace-only.",
            "correction_attempts": 0,
            "retrieved_documents": [],
            "retrieval_diagnostics": {},
            "citations": [],
        }

    question_clean = question.strip()
    if len(question_clean) > config.max_question_length:
        return {
            "is_refusal": True,
            "refusal_reason": (
                f"Question length ({len(question_clean)} chars) exceeds configured "
                f"maximum limit ({config.max_question_length} chars)."
            ),
            "correction_attempts": 0,
            "retrieved_documents": [],
            "retrieval_diagnostics": {},
            "citations": [],
        }

    return {
        "question": question_clean,
        "is_refusal": False,
        "refusal_reason": None,
        "correction_attempts": 0,
        "error": None,
    }


async def retrieve_evidence_node(
    state: WorkflowState,
    retriever_tool: BaseTool,
    config: WorkflowConfig,
) -> Dict[str, Any]:
    """Node 2: Retrieve evidence passages by invoking the LangChain retrieval tool."""
    if state.get("is_refusal"):
        return {}

    question = state["question"]
    paper_filter = state.get("paper_filter")
    try:
        tool_args: Dict[str, Any] = {"query": question, "top_k": config.top_k_retrieval}
        if paper_filter:
            tool_args["paper_filter"] = paper_filter

        # Genuine LangChain tool invocation (supports async ainvoke or sync invoke)
        if hasattr(retriever_tool, "ainvoke"):
            tool_output = await retriever_tool.ainvoke(tool_args)
        else:
            tool_output = retriever_tool.invoke(tool_args)
    except Exception as exc:
        return {
            "is_refusal": True,
            "refusal_reason": f"Retrieval tool execution failed: {exc}",
            "error": str(exc),
            "retrieved_documents": [],
            "retrieval_diagnostics": {},
        }

    # Inspect tool output
    if isinstance(tool_output, dict):
        status = tool_output.get("status", "success")
        raw_docs = tool_output.get("documents", [])
        diagnostics = tool_output.get("diagnostics", {})
        failed_channels = tool_output.get("failed_channels", {})
        error_msg = tool_output.get("error")

        if status == "error" or (not raw_docs and failed_channels and len(failed_channels) >= 3):
            return {
                "is_refusal": True,
                "refusal_reason": f"Retrieval failed across all channels: {error_msg or failed_channels}",
                "error": error_msg or "All retrieval channels failed",
                "retrieved_documents": [],
                "retrieval_diagnostics": diagnostics,
            }

        documents: List[RetrievedDocument] = []
        for d in raw_docs:
            if isinstance(d, dict):
                documents.append(RetrievedDocument(**d))
            elif isinstance(d, RetrievedDocument):
                documents.append(d)

        return {
            "retrieved_documents": documents,
            "retrieval_diagnostics": diagnostics,
            "is_refusal": False,
        }

    return {
        "retrieved_documents": [],
        "retrieval_diagnostics": {},
        "is_refusal": True,
        "refusal_reason": "Unexpected retrieval tool response format.",
    }


def evidence_sufficiency_check_node(
    state: WorkflowState,
    config: WorkflowConfig,
) -> Dict[str, Any]:
    """Node 3: Deterministically determine whether evidence is sufficient to proceed."""
    if state.get("is_refusal"):
        return {}

    docs = state.get("retrieved_documents", [])
    question = state.get("question", "")

    # 1. Chunk count gate
    if len(docs) < config.min_chunks_required:
        return {
            "evidence_sufficient": False,
            "is_refusal": True,
            "refusal_reason": "No relevant evidence passages were found in the 3 target papers.",
        }

    # 2. Total content text gate
    total_chars = sum(len(doc.content.strip()) for doc in docs)
    if total_chars < config.min_total_content_chars:
        return {
            "evidence_sufficient": False,
            "is_refusal": True,
            "refusal_reason": (
                f"Retrieved passages contain insufficient text ({total_chars} chars, "
                f"minimum {config.min_total_content_chars} required)."
            ),
        }

    # 3. Top RRF score gate
    top_score = max((doc.score for doc in docs), default=0.0)
    if top_score < config.min_top_rrf_score:
        return {
            "evidence_sufficient": False,
            "is_refusal": True,
            "refusal_reason": (
                f"Top retrieved passage relevance score ({top_score:.4f}) is below "
                f"the sufficiency threshold ({config.min_top_rrf_score})."
            ),
        }

    # 4. Domain keyword match check (out-of-domain filter)
    query_tokens = {
        token.lower()
        for token in re.findall(r"\b[a-zA-Z0-9_\-]{3,}\b", question)
        if token.lower() not in STOPWORDS
    }

    if query_tokens:
        matched_tokens = {
            token for token in query_tokens
            if any(
                token in doc.content.lower() or token in doc.paper_title.lower()
                for doc in docs
            )
        }
        if not matched_tokens:
            return {
                "evidence_sufficient": False,
                "is_refusal": True,
                "refusal_reason": (
                    "Retrieved evidence passages do not contain terms matching the research query. "
                    "The query appears to be out-of-domain for the 3 target papers."
                ),
            }

    return {
        "evidence_sufficient": True,
        "is_refusal": False,
        "refusal_reason": None,
    }


async def generate_answer_node(
    state: WorkflowState,
    traffic_manager: Any,
    config: WorkflowConfig,
) -> Dict[str, Any]:
    """Node 4: Generate grounded answer exclusively using retrieved evidence via TrafficManager."""
    if state.get("is_refusal"):
        return {}

    docs = state.get("retrieved_documents", [])
    context_blocks: List[str] = []
    for idx, doc in enumerate(docs, 1):
        page_info = f"p. {doc.page_number}" if doc.page_number is not None else "p. N/A"
        sec_info = f", Section {doc.section}" if doc.section else ""
        context_blocks.append(
            f"[Passage {idx}] [{doc.paper_title}, arXiv:{doc.paper_id}, {page_info}{sec_info}]\n{doc.content}"
        )
    context_str = "\n\n".join(context_blocks)

    system_instructions = (
        "You are an expert research assistant answering questions strictly grounded in the "
        "provided arXiv papers:\n"
        "1. Attention Is All You Need (arXiv:1706.03762v7)\n"
        "2. Moshi: A Speech-Text Foundation Model for Real-Time Dialogue (arXiv:2410.00037v1)\n"
        "3. Dynamic Chunking for End-to-End Hierarchical Sequence Modeling (arXiv:2507.07955v2)\n\n"
        "Mandatory Rules:\n"
        "1. Answer ONLY using the supplied evidence passages.\n"
        "2. Do NOT use outside knowledge or extrapolate beyond the provided text.\n"
        "3. Every factual claim MUST be followed by an exact citation in the format:\n"
        "   [Paper Title, arXiv:<paper_id>, p. <page_number>, Section <section>] or [arXiv:<paper_id>, p. <page_number>].\n"
        "4. Only cite paper IDs, versions, and page numbers that are explicitly present in the supplied passages.\n"
        "5. Never invent page numbers, section names, or paper versions.\n"
        "6. If the supplied passages do not provide the answer, state that the evidence is insufficient."
    )

    prompt = (
        f"{system_instructions}\n\n"
        f"Retrieved Evidence:\n{context_str}\n\n"
        f"Research Question: {state['question']}\n\n"
        "Answer with traceable citations:"
    )

    request = GenerationRequest(
        prompt=prompt,
        max_tokens=config.max_tokens,
        temperature=config.temperature,
    )

    try:
        if hasattr(traffic_manager, "execute"):
            response = await traffic_manager.execute(request, timeout=config.generation_timeout)
        elif hasattr(traffic_manager, "generate"):
            response = await traffic_manager.generate(request)
        else:
            raise TypeError(f"Target {type(traffic_manager)} does not support execute or generate")

        # Safely extract text from GenerationResponse (response_text) or alternative provider response (.text)
        answer_text = getattr(response, "response_text", getattr(response, "text", str(response)))

        return {
            "answer": answer_text.strip(),
            "is_refusal": False,
        }
    except Exception as exc:
        logger.error(f"TrafficManager generation failed: {exc}")
        return {
            "is_refusal": True,
            "refusal_reason": f"Model generation failed: {exc}",
            "error": str(exc),
        }


def verify_citations_node(
    state: WorkflowState,
    config: WorkflowConfig,
) -> Dict[str, Any]:
    """Node 5: Deterministically verify citations in generated answer against retrieved metadata."""
    if state.get("is_refusal"):
        return {}

    answer = state.get("answer", "")
    retrieved_docs = state.get("retrieved_documents", [])

    citations = extract_citations(answer)
    verification = verify_citations_against_evidence(citations, retrieved_docs)

    update: Dict[str, Any] = {
        "citations": verification.verified_citations,
        "citation_verification": verification,
    }

    # If verification failed and we have reached or exceeded max correction attempts, route to refusal
    if not verification.is_valid and state.get("correction_attempts", 0) >= config.max_correction_attempts:
        update["is_refusal"] = True
        update["refusal_reason"] = (
            "Generated answer failed citation verification after maximum allowed correction attempts: "
            + "; ".join(verification.error_messages)
        )

    return update


async def correction_attempt_node(
    state: WorkflowState,
    traffic_manager: Any,
    config: WorkflowConfig,
) -> Dict[str, Any]:
    """Node 6: Single-attempt correction loop when citation verification fails."""
    attempts = state.get("correction_attempts", 0) + 1
    previous_answer = state.get("answer", "")
    verification = state.get("citation_verification")
    errors = verification.error_messages if verification else ["Citation metadata mismatch."]

    docs = state.get("retrieved_documents", [])
    context_blocks: List[str] = []
    for idx, doc in enumerate(docs, 1):
        page_info = f"p. {doc.page_number}" if doc.page_number is not None else "p. N/A"
        sec_info = f", Section {doc.section}" if doc.section else ""
        context_blocks.append(
            f"[Passage {idx}] [{doc.paper_title}, arXiv:{doc.paper_id}, {page_info}{sec_info}]\n{doc.content}"
        )
    context_str = "\n\n".join(context_blocks)

    system_instructions = (
        "You are an expert research assistant revising a previous answer whose citations failed verification.\n"
        "Mandatory Correction Rules:\n"
        "1. Answer the original question using ONLY the supplied retrieved evidence passages below.\n"
        "2. Do NOT use outside knowledge or extrapolate beyond the provided text.\n"
        "3. Every factual claim MUST be followed by an exact citation in the format:\n"
        "   [Paper Title, arXiv:<paper_id>, p. <page_number>, Section <section>] or [arXiv:<paper_id>, p. <page_number>].\n"
        "4. Only cite paper IDs, versions, page numbers, and sections that are explicitly present in the supplied passages.\n"
        "5. Correct all citation verification errors identified below.\n"
        "6. Never invent page numbers, section names, or paper versions."
    )

    correction_prompt = (
        f"{system_instructions}\n\n"
        f"Citation Verification Errors to Correct:\n"
        + "\n".join(f"- {err}" for err in errors)
        + f"\n\nRetrieved Evidence Passages:\n{context_str}\n\n"
        f"Original Question: {state['question']}\n\n"
        f"Previous Answer:\n{previous_answer}\n\n"
        "Revised Answer with Traceable Citations:"
    )

    request = GenerationRequest(
        prompt=correction_prompt,
        max_tokens=config.max_tokens,
        temperature=config.temperature,
    )

    try:
        if hasattr(traffic_manager, "execute"):
            response = await traffic_manager.execute(request, timeout=config.generation_timeout)
        elif hasattr(traffic_manager, "generate"):
            response = await traffic_manager.generate(request)
        else:
            raise TypeError(f"Target {type(traffic_manager)} does not support execute or generate")

        # Safely extract text from GenerationResponse (response_text) or alternative provider response (.text)
        answer_text = getattr(response, "response_text", getattr(response, "text", str(response)))

        return {
            "answer": answer_text.strip(),
            "correction_attempts": attempts,
            "is_refusal": False,
        }
    except Exception as exc:
        logger.error(f"Correction generation failed: {exc}")
        return {
            "is_refusal": True,
            "refusal_reason": f"Model correction failed: {exc}",
            "error": str(exc),
            "correction_attempts": attempts,
        }


def refusal_node(state: WorkflowState, config: WorkflowConfig) -> Dict[str, Any]:
    """Node 7: Formulate explicit polite refusal when evidence is insufficient or citations fail."""
    reason = state.get("refusal_reason") or "The available research evidence is insufficient to answer the question."
    refusal_text = (
        f"I am unable to answer this research question from the three target papers.\n"
        f"Reason: {reason}"
    )
    return {
        "answer": refusal_text,
        "is_refusal": True,
        "refusal_reason": reason,
    }


def final_response_node(state: WorkflowState, config: WorkflowConfig) -> Dict[str, Any]:
    """Node 8: Synthesize the final structured user-facing response contract."""
    is_refusal = state.get("is_refusal", False)
    verification = state.get("citation_verification")

    if is_refusal:
        verification_status = "refused"
    elif verification and verification.is_valid:
        verification_status = "verified"
    else:
        verification_status = "unverified"

    metadata = {
        "correction_attempts": state.get("correction_attempts", 0),
        "retrieved_chunk_count": len(state.get("retrieved_documents", [])),
        "diagnostics": state.get("retrieval_diagnostics", {}),
    }
    if state.get("error"):
        metadata["error"] = state.get("error")

    final_resp = FinalResponse(
        question=state.get("question", ""),
        answer=state.get("answer", ""),
        is_refusal=is_refusal,
        refusal_reason=state.get("refusal_reason"),
        citations=state.get("citations", []),
        retrieved_sources=state.get("retrieved_documents", []),
        verification_status=verification_status,
        correction_occurred=(state.get("correction_attempts", 0) > 0),
        workflow_metadata=metadata,
    )

    return {
        "final_response": final_resp,
    }
