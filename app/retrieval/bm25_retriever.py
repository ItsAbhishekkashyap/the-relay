"""
BM25 Keyword Retrieval Engine using rank-bm25.

Provides lexical and exact keyword matching over research paper chunks,
supporting paper-level filtering, persistence, and complete provenance tracking.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)

DEFAULT_BM25_INDEX_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "indexes" / "bm25"
DEFAULT_BM25_FILE = DEFAULT_BM25_INDEX_DIR / "bm25_index.json"

# Word tokenizer that preserves alphanumeric terms, underscores, hyphenated words, and arXiv identifiers (e.g. 1706.03762v7)
TOKEN_PATTERN = re.compile(r"\b[a-zA-Z0-9]+(?:[._-][a-zA-Z0-9]+)*\b")


def bm25_tokenize(text: str) -> List[str]:
    """Tokenize text into lowercased lexical tokens for BM25 indexing and querying."""
    if not text:
        return []
    return [tok.lower() for tok in TOKEN_PATTERN.findall(text)]


class BM25Retriever:
    """
    In-memory BM25 index with persistence, paper filtering, and provenance preservation.
    """

    def __init__(self, index_file: Optional[Path | str] = None) -> None:
        self.index_file = Path(index_file) if index_file else None
        self.chunks: List[Dict[str, Any]] = []
        self.chunk_ids: List[str] = []
        self.tokenized_corpus: List[List[str]] = []
        self._bm25: Optional[BM25Okapi] = None

        if self.index_file and self.index_file.exists():
            self.load(self.index_file)

    def count(self) -> int:
        """Return number of documents indexed."""
        return len(self.chunks)

    def index_chunks(self, chunks: Sequence[Dict[str, Any]]) -> int:
        """
        Index chunk records into the BM25 model.

        Ensures idempotency by deduplicating on chunk_id (replaces existing records).

        Args:
            chunks: List of chunk dictionaries containing chunk_id, chunk_text, and metadata.

        Returns:
            Total count of indexed chunks.
        """
        if not chunks:
            return len(self.chunks)

        # Build / update dictionary of chunks by chunk_id
        chunk_map: Dict[str, Dict[str, Any]] = {c["chunk_id"]: c for c in self.chunks}
        for c in chunks:
            cid = c.get("chunk_id")
            text = c.get("chunk_text") or c.get("content") or ""
            if not cid or not text.strip():
                continue
            chunk_map[cid] = dict(c)

        # Rebuild ordered lists
        self.chunks = list(chunk_map.values())
        self.chunk_ids = [c["chunk_id"] for c in self.chunks]
        self.tokenized_corpus = [
            bm25_tokenize(f"{c.get('paper_id', '')} {c.get('arxiv_id', '')} {c.get('chunk_text') or c.get('content') or ''}".strip())
            for c in self.chunks
        ]

        if self.tokenized_corpus:
            self._bm25 = BM25Okapi(self.tokenized_corpus)
        else:
            self._bm25 = None

        return len(self.chunks)

    def query(
        self,
        query_text: str,
        top_k: int = 5,
        paper_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Execute BM25 keyword search.

        Args:
            query_text: Keyword or natural query string.
            top_k: Maximum ranked results to return.
            paper_filter: Optional paper_id to restrict search.

        Returns:
            Ranked list of matching chunk records with scores > 0.
        """
        clean_query = query_text.strip()
        if not clean_query or self._bm25 is None or not self.chunks:
            return []

        query_tokens = bm25_tokenize(clean_query)
        if not query_tokens:
            return []

        # Compute BM25 scores for all corpus items
        raw_scores = self._bm25.get_scores(query_tokens)

        # Filter by paper_id and score > 0
        candidates = []
        for idx, (chunk, score) in enumerate(zip(self.chunks, raw_scores)):
            if score <= 0.0:
                continue
            if paper_filter and chunk.get("paper_id") != paper_filter:
                continue

            candidates.append((idx, chunk, float(score)))

        # Sort descending by BM25 score
        candidates.sort(key=lambda x: x[2], reverse=True)
        top_candidates = candidates[:top_k]

        ranked_results: List[Dict[str, Any]] = []
        for rank, (idx, chunk, score) in enumerate(top_candidates, start=1):
            text = chunk.get("chunk_text") or chunk.get("content") or ""
            record = {
                "chunk_id": chunk.get("chunk_id"),
                "content": text,
                "metadata": dict(chunk),
                "paper_id": chunk.get("paper_id"),
                "paper_title": chunk.get("paper_title"),
                "arxiv_id": chunk.get("arxiv_id"),
                "paper_version": chunk.get("paper_version"),
                "page_number": chunk.get("page_number"),
                "page_numbers": chunk.get("page_numbers", [chunk.get("page_number", 1)]),
                "section": chunk.get("section"),
                "element_type": chunk.get("element_type", "prose"),
                "score": round(score, 6),
                "rank": rank,
                "retrieval_method": "bm25",
            }
            ranked_results.append(record)

        return ranked_results

    def save(self, filepath: Optional[Path | str] = None) -> Path:
        """Serialize BM25 indexed corpus to disk."""
        target = Path(filepath) if filepath else self.index_file
        if not target:
            target = DEFAULT_BM25_FILE

        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "total_chunks": len(self.chunks),
            "chunks": self.chunks,
        }
        with open(target, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved BM25 index with {len(self.chunks)} chunks to {target}")
        return target

    def load(self, filepath: Path | str) -> None:
        """Load BM25 index and reconstruct BM25Okapi model."""
        target = Path(filepath)
        if not target.exists():
            raise FileNotFoundError(f"BM25 index file not found: {target}")

        with open(target, "r", encoding="utf-8") as f:
            payload = json.load(f)

        chunks = payload.get("chunks", [])
        self.chunks = []
        self.chunk_ids = []
        self.tokenized_corpus = []
        self._bm25 = None

        self.index_chunks(chunks)
        self.index_file = target
        logger.info(f"Loaded BM25 index with {len(self.chunks)} chunks from {target}")

    def get_chunk(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a specific chunk by chunk_id."""
        for c in self.chunks:
            if c.get("chunk_id") == chunk_id:
                return dict(c)
        return None

