"""
Hybrid Retrieval Engine with Reciprocal Rank Fusion (RRF).

Combines dense vector retrieval (ChromaDB), keyword retrieval (BM25),
and structured fact lookups (SQLite FactStore) into a unified,
traceable evidence set with provenance preservation and channel failure diagnostics.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

from app.retrieval.bm25_retriever import BM25Retriever
from app.retrieval.dense_retriever import DenseRetriever
from app.retrieval.fact_store import FactStore

logger = logging.getLogger(__name__)

DEFAULT_RRF_K = 60
DEFAULT_CHANNEL_WEIGHTS = {
    "dense": 1.0,
    "bm25": 1.0,
    "fact_store": 1.0,
}


class RetrievalError(RuntimeError):
    """
    Raised when hybrid retrieval fails across all configured channels.
    """

    def __init__(self, message: str, failed_channels: Optional[Dict[str, str]] = None) -> None:
        super().__init__(message)
        self.failed_channels = failed_channels or {}


class HybridRetrievalResult(list):
    """
    Ranked evidence results from HybridRetriever, augmented with channel diagnostics.

    Inherits from list for backward-compatibility with list operations (len, iteration, indexing),
    while exposing diagnostic properties for channel health and failures.
    """

    def __init__(
        self,
        items: Sequence[Dict[str, Any]] = (),
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(items)
        self.diagnostics: Dict[str, Any] = diagnostics or {}
        self.failed_channels: Dict[str, str] = self.diagnostics.get("failed_channels", {})
        self.successful_channels: List[str] = self.diagnostics.get("successful_channels", [])
        self.active_channels: List[str] = self.diagnostics.get("active_channels", [])
        self.has_failures: bool = bool(self.failed_channels)


def compute_rrf_score(rank: int, k: int = DEFAULT_RRF_K, weight: float = 1.0) -> float:
    """
    Compute Reciprocal Rank Fusion (RRF) contribution for a 1-based rank.

    Formula: weight / (k + rank)
    """
    if rank <= 0:
        raise ValueError(f"Rank must be a positive 1-based integer, got {rank}")
    return float(weight) / float(k + rank)


class HybridRetriever:
    """
    Unified Hybrid Retrieval Engine orchestrating Dense, BM25, and FactStore retrievers.
    """

    def __init__(
        self,
        dense_retriever: Optional[DenseRetriever] = None,
        bm25_retriever: Optional[BM25Retriever] = None,
        fact_store: Optional[FactStore] = None,
        rrf_k: int = DEFAULT_RRF_K,
        weights: Optional[Dict[str, float]] = None,
    ) -> None:
        self.dense = dense_retriever
        self.bm25 = bm25_retriever
        self.facts = fact_store
        self.rrf_k = rrf_k
        self.weights = dict(DEFAULT_CHANNEL_WEIGHTS)
        if weights:
            self.weights.update(weights)
        self.last_diagnostics: Dict[str, Any] = {}

    def retrieve(
        self,
        query: str,
        paper_filter: Optional[str] = None,
        top_k: int = 5,
        candidate_k: int = 20,
        enable_dense: bool = True,
        enable_bm25: bool = True,
        enable_facts: bool = True,
    ) -> HybridRetrievalResult:
        """
        Public retrieval interface executing hybrid multi-channel search and RRF fusion.

        Args:
            query: User natural language question or keyword query.
            paper_filter: Optional paper_id to restrict search to a specific document.
            top_k: Number of final fused results to return.
            candidate_k: Number of candidates to gather from each active channel before fusion.
            enable_dense: Whether to query dense ChromaDB retriever.
            enable_bm25: Whether to query BM25 retriever.
            enable_facts: Whether to query structured fact store.

        Returns:
            HybridRetrievalResult list with complete provenance and channel failure diagnostics.

        Raises:
            RetrievalError: If all enabled and configured channels fail.
        """
        clean_query = query.strip()
        if not clean_query:
            diag = {"warning": "Empty query provided", "failed_channels": {}, "successful_channels": []}
            self.last_diagnostics = diag
            return HybridRetrievalResult([], diagnostics=diag)

        # 1. Identify active configured channels
        active_channels: List[str] = []
        if enable_dense and self.dense is not None:
            active_channels.append("dense")
        if enable_bm25 and self.bm25 is not None:
            active_channels.append("bm25")
        if enable_facts and self.facts is not None:
            active_channels.append("fact_store")

        if not active_channels:
            diag = {"warning": "No retrieval channels enabled or configured", "failed_channels": {}, "successful_channels": []}
            self.last_diagnostics = diag
            return HybridRetrievalResult([], diagnostics=diag)

        # 2. Query active channels and collect diagnostics
        channel_results: Dict[str, List[Dict[str, Any]]] = {}
        failed_channels: Dict[str, str] = {}
        successful_channels: List[str] = []

        if "dense" in active_channels:
            try:
                dense_hits = self.dense.query(
                    clean_query,
                    top_k=candidate_k,
                    paper_filter=paper_filter,
                )
                channel_results["dense"] = dense_hits
                successful_channels.append("dense")
            except Exception as exc:
                err_msg = str(exc)
                logger.error(f"Dense retriever channel failed: {err_msg}")
                failed_channels["dense"] = err_msg

        if "bm25" in active_channels:
            try:
                bm25_hits = self.bm25.query(
                    clean_query,
                    top_k=candidate_k,
                    paper_filter=paper_filter,
                )
                channel_results["bm25"] = bm25_hits
                successful_channels.append("bm25")
            except Exception as exc:
                err_msg = str(exc)
                logger.error(f"BM25 retriever channel failed: {err_msg}")
                failed_channels["bm25"] = err_msg

        if "fact_store" in active_channels:
            try:
                fact_hits = self.facts.search(
                    clean_query,
                    top_k=candidate_k,
                    paper_filter=paper_filter,
                )
                channel_results["fact_store"] = fact_hits
                successful_channels.append("fact_store")
            except Exception as exc:
                err_msg = str(exc)
                logger.error(f"Fact store channel failed: {err_msg}")
                failed_channels["fact_store"] = err_msg

        diagnostics: Dict[str, Any] = {
            "active_channels": active_channels,
            "successful_channels": successful_channels,
            "failed_channels": failed_channels,
            "has_failures": len(failed_channels) > 0,
        }
        self.last_diagnostics = diagnostics

        # 3. If all active channels failed, raise clear RetrievalError
        if len(failed_channels) == len(active_channels):
            raise RetrievalError(
                f"All configured retrieval channels failed for query '{clean_query}': {failed_channels}",
                failed_channels=failed_channels,
            )

        # 4. Check if all successful channels returned zero candidates
        total_candidates = sum(len(hits) for hits in channel_results.values())
        if total_candidates == 0:
            return HybridRetrievalResult([], diagnostics=diagnostics)

        # 5. Reciprocal Rank Fusion (RRF) aggregation & deduplication
        fused_scores: Dict[str, float] = {}
        channel_ranks: Dict[str, Dict[str, int]] = {}
        channel_scores: Dict[str, Dict[str, float]] = {}
        matched_channels: Dict[str, List[str]] = {}
        chunk_registry: Dict[str, Dict[str, Any]] = {}

        for channel_name, hits in channel_results.items():
            weight = self.weights.get(channel_name, 1.0)

            for rank_0indexed, hit in enumerate(hits):
                cid = hit["chunk_id"]
                rank_1based = rank_0indexed + 1

                # Calculate RRF score contribution
                contribution = compute_rrf_score(rank_1based, k=self.rrf_k, weight=weight)
                fused_scores[cid] = fused_scores.get(cid, 0.0) + contribution

                # Track channel membership
                if cid not in matched_channels:
                    matched_channels[cid] = []
                matched_channels[cid].append(channel_name)

                # Track per-channel ranks and raw scores
                if cid not in channel_ranks:
                    channel_ranks[cid] = {}
                channel_ranks[cid][channel_name] = rank_1based

                if cid not in channel_scores:
                    channel_scores[cid] = {}
                channel_scores[cid][channel_name] = hit.get("score", 0.0)

                # Store payload representation (prefer structured fact if available for exact table markdown)
                if cid not in chunk_registry or channel_name == "fact_store":
                    chunk_registry[cid] = hit

        # 6. Sort deduplicated chunks by combined RRF score descending
        sorted_chunk_ids = sorted(
            fused_scores.keys(),
            key=lambda cid: fused_scores[cid],
            reverse=True,
        )

        top_chunk_ids = sorted_chunk_ids[:top_k]

        # 7. Construct final evidence output records with full provenance
        fused_results: List[Dict[str, Any]] = []
        for final_rank, cid in enumerate(top_chunk_ids, start=1):
            base_hit = chunk_registry[cid]
            meta = base_hit.get("metadata", {})

            fused_record = {
                "chunk_id": cid,
                "content": base_hit.get("content", ""),
                "score": round(fused_scores[cid], 6),
                "rank": final_rank,
                "retrieval_channels": matched_channels[cid],
                "channel_ranks": channel_ranks[cid],
                "channel_scores": channel_scores[cid],
                # Core Provenance Fields
                "paper_id": base_hit.get("paper_id") or meta.get("paper_id"),
                "paper_title": base_hit.get("paper_title") or meta.get("paper_title"),
                "arxiv_id": base_hit.get("arxiv_id") or meta.get("arxiv_id"),
                "paper_version": base_hit.get("paper_version") or meta.get("paper_version"),
                "page_number": base_hit.get("page_number") or meta.get("page_number"),
                "page_numbers": base_hit.get("page_numbers") or meta.get("page_numbers", []),
                "section": base_hit.get("section") or meta.get("section"),
                "element_type": base_hit.get("element_type") or meta.get("element_type", "prose"),
                "metadata": meta,
                "diagnostics": {
                    "failed_channels": failed_channels,
                    "successful_channels": successful_channels,
                },
            }
            fused_results.append(fused_record)

        return HybridRetrievalResult(fused_results, diagnostics=diagnostics)
