"""LangChain tool definitions for research retrieval.

Wraps the existing HybridRetriever into a genuine LangChain BaseTool, preserving
provenance metadata and channel failure diagnostics.
"""

from typing import Any, Dict, List, Optional
from langchain_core.tools import BaseTool, tool
from app.retrieval.hybrid_retriever import HybridRetriever, RetrievalError
from app.workflow.schemas import RetrievedDocument


def create_research_retrieval_tool(retriever: HybridRetriever) -> BaseTool:
    """Create a LangChain tool wrapping the unified HybridRetriever.

    Args:
        retriever: The configured HybridRetriever instance.

    Returns:
        A LangChain BaseTool with signature `(query: str, top_k: int = 5)`.
    """

    @tool
    def search_research_papers(
        query: str,
        top_k: int = 5,
        paper_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Search the three arXiv research papers for relevant evidence passages.

        The corpus covers:
        1. Attention Is All You Need (arXiv:1706.03762v7)
        2. Moshi: Speech-Text Foundation Model for Real-Time Dialogue (arXiv:2410.00037v1)
        3. Dynamic Chunking for End-to-End Hierarchical Sequence Modeling (arXiv:2507.07955v2)

        Args:
            query: The natural language research question or search query.
            top_k: Maximum number of evidence passages to return (default 5).
            paper_filter: Optional paper ID to filter evidence passages.

        Returns:
            Dictionary with 'status', 'documents', 'diagnostics', and 'error' if any.
        """
        try:
            results = retriever.retrieve(query=query, paper_filter=paper_filter, top_k=top_k)
            documents: List[Dict[str, Any]] = []
            for item in results:
                # Handle either dicts or object attributes
                if isinstance(item, dict):
                    doc_dict = {
                        "chunk_id": str(item.get("chunk_id", "")),
                        "paper_id": str(item.get("paper_id", "")),
                        "paper_title": str(item.get("paper_title", "")),
                        "arxiv_id": str(item.get("arxiv_id", "")),
                        "paper_version": str(item.get("paper_version", "")),
                        "page_number": item.get("page_number"),
                        "page_numbers": item.get("page_numbers", []),
                        "section": item.get("section"),
                        "content": str(item.get("content", "")),
                        "score": float(item.get("score", 0.0)),
                        "retrieval_channels": item.get("retrieval_channels", []),
                    }
                else:
                    doc_dict = {
                        "chunk_id": str(getattr(item, "chunk_id", "")),
                        "paper_id": str(getattr(item, "paper_id", "")),
                        "paper_title": str(getattr(item, "paper_title", "")),
                        "arxiv_id": str(getattr(item, "arxiv_id", "")),
                        "paper_version": str(getattr(item, "paper_version", "")),
                        "page_number": getattr(item, "page_number", None),
                        "page_numbers": getattr(item, "page_numbers", []),
                        "section": getattr(item, "section", None),
                        "content": str(getattr(item, "content", "")),
                        "score": float(getattr(item, "score", 0.0)),
                        "retrieval_channels": getattr(item, "retrieval_channels", []),
                    }
                documents.append(doc_dict)

            diagnostics = getattr(results, "diagnostics", {})
            failed_channels = getattr(results, "failed_channels", {})
            successful_channels = getattr(results, "successful_channels", [])

            return {
                "status": "success",
                "documents": documents,
                "diagnostics": diagnostics,
                "failed_channels": failed_channels,
                "successful_channels": successful_channels,
            }
        except RetrievalError as exc:
            return {
                "status": "error",
                "documents": [],
                "diagnostics": {"failed_channels": exc.failed_channels},
                "failed_channels": exc.failed_channels,
                "error": str(exc),
            }
        except Exception as exc:
            return {
                "status": "error",
                "documents": [],
                "diagnostics": {},
                "failed_channels": {},
                "error": f"Unexpected retrieval failure: {exc}",
            }

    return search_research_papers
