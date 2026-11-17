"""
Structured Fact Store using SQLite.

Preserves exact source content from structured table chunks, formulas,
numeric parameters, and fact-bearing records with exact provenance.
Supports exact substring, numeric-string, identifier, and full-text searches.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

DEFAULT_FACT_STORE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "indexes"
DEFAULT_FACT_STORE_DB = DEFAULT_FACT_STORE_DIR / "fact_store.db"

# Types of chunks classified as structured or fact-bearing by default
FACT_ELEMENT_TYPES = {"table", "table_unstructured"}


class FactStore:
    """
    SQLite-backed structured fact store.

    Stores verbatim table markdown and fact-bearing elements without alteration.
    Guarantees idempotency via UNIQUE constraint on chunk_id.
    """

    def __init__(self, db_path: Optional[Path | str] = DEFAULT_FACT_STORE_DB) -> None:
        self.db_path = str(db_path) if db_path else ":memory:"
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    @property
    def conn(self) -> sqlite3.Connection:
        """Return active database connection, creating it if needed."""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_db(self) -> None:
        """Create tables, indexes, and full-text search structures."""
        with self.conn:
            # Main structured facts table
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS facts (
                    fact_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chunk_id TEXT UNIQUE NOT NULL,
                    paper_id TEXT NOT NULL,
                    arxiv_id TEXT,
                    paper_version TEXT,
                    paper_title TEXT,
                    page_number INTEGER NOT NULL,
                    page_numbers_json TEXT,
                    section TEXT,
                    element_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    token_count INTEGER,
                    character_count INTEGER,
                    metadata_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Fast lookup indexes
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_facts_paper ON facts(paper_id);")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_facts_page ON facts(page_number);")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_facts_type ON facts(element_type);")

            # Create FTS5 virtual table for full-text search if supported
            try:
                self.conn.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(
                        content,
                        chunk_id UNINDEXED,
                        paper_id UNINDEXED,
                        section UNINDEXED,
                        tokenize = 'porter unicode61'
                    );
                """)
                self._has_fts = True
            except sqlite3.OperationalError:
                logger.warning("SQLite FTS5 extension unavailable. Falling back to SQL LIKE search.")
                self._has_fts = False

    def count(self, paper_filter: Optional[str] = None) -> int:
        """Return total number of fact records in store, optionally filtered by paper."""
        cur = self.conn.cursor()
        if paper_filter:
            cur.execute("SELECT COUNT(*) FROM facts WHERE paper_id = ?;", (paper_filter,))
        else:
            cur.execute("SELECT COUNT(*) FROM facts;")
        return cur.fetchone()[0]

    def index_chunks(
        self,
        chunks: Sequence[Dict[str, Any]],
        filter_fact_elements_only: bool = True,
    ) -> int:
        """
        Index chunk records into the fact store.

        Args:
            chunks: Sequence of chunk dictionaries.
            filter_fact_elements_only: If True, only indexes 'table' and 'table_unstructured'
                                      elements. If False, indexes all provided chunks.

        Returns:
            Number of fact records stored in the database.
        """
        if not chunks:
            return self.count()

        records_to_insert = []
        fts_records = []

        for c in chunks:
            etype = c.get("element_type", "prose")
            if filter_fact_elements_only and etype not in FACT_ELEMENT_TYPES:
                continue

            cid = c.get("chunk_id")
            text = c.get("chunk_text") or c.get("content") or ""
            if not cid or not text.strip():
                continue

            paper_id = c.get("paper_id", "")
            arxiv_id = c.get("arxiv_id", "")
            version = c.get("paper_version", "")
            title = c.get("paper_title", "")
            page_num = c.get("page_number", 1)
            page_nums = c.get("page_numbers", [page_num])
            section = c.get("section")
            token_count = c.get("token_count", 0)
            char_count = c.get("character_count", len(text))
            meta_json = json.dumps(dict(c), ensure_ascii=False)

            records_to_insert.append((
                cid,
                paper_id,
                arxiv_id,
                version,
                title,
                page_num,
                json.dumps(page_nums),
                section,
                etype,
                text,
                token_count,
                char_count,
                meta_json,
            ))

            if self._has_fts:
                fts_records.append((text, cid, paper_id, section or ""))

        with self.conn:
            # Idempotent upsert via ON CONFLICT DO UPDATE
            self.conn.executemany("""
                INSERT INTO facts (
                    chunk_id, paper_id, arxiv_id, paper_version, paper_title,
                    page_number, page_numbers_json, section, element_type,
                    content, token_count, character_count, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chunk_id) DO UPDATE SET
                    content = excluded.content,
                    section = excluded.section,
                    page_number = excluded.page_number,
                    page_numbers_json = excluded.page_numbers_json,
                    metadata_json = excluded.metadata_json,
                    token_count = excluded.token_count,
                    character_count = excluded.character_count;
            """, records_to_insert)

            if self._has_fts and fts_records:
                # Clear and re-populate FTS for idempotency
                for text, cid, pid, sec in fts_records:
                    self.conn.execute("DELETE FROM facts_fts WHERE chunk_id = ?;", (cid,))
                    self.conn.execute(
                        "INSERT INTO facts_fts (content, chunk_id, paper_id, section) VALUES (?, ?, ?, ?);",
                        (text, cid, pid, sec),
                    )

        return self.count()

    def search(
        self,
        query: str,
        paper_filter: Optional[str] = None,
        top_k: int = 5,
        exact_match_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Search structured facts using exact substring, identifier, numeric, and full-text queries.

        Args:
            query: Search string (e.g., 'Table 1', '32.5', 'BLEU', 'd_model', 'Moshi').
            paper_filter: Optional paper_id to restrict search.
            top_k: Maximum number of ranked results.
            exact_match_only: If True, only return verbatim substring matches.

        Returns:
            Ranked list of fact records with original table content and provenance.
        """
        clean_query = query.strip()
        if not clean_query or self.count() == 0:
            return []

        results: Dict[str, Dict[str, Any]] = {}

        # 1. Exact substring match (highest precision for numbers, identifiers, exact headers)
        exact_sql = """
            SELECT chunk_id, paper_id, paper_title, arxiv_id, paper_version,
                   page_number, page_numbers_json, section, element_type,
                   content, token_count, metadata_json
            FROM facts
            WHERE content LIKE ?
        """
        params: List[Any] = [f"%{clean_query}%"]
        if paper_filter:
            exact_sql += " AND paper_id = ?"
            params.append(paper_filter)

        cur = self.conn.cursor()
        cur.execute(exact_sql, params)
        for row in cur.fetchall():
            cid = row["chunk_id"]
            # Base exact match score
            score = 1.0
            # Higher score if case-sensitive or exact occurrence count
            occurrences = row["content"].lower().count(clean_query.lower())
            score += min(1.0, occurrences * 0.2)

            page_nums = [row["page_number"]]
            if row["page_numbers_json"]:
                try:
                    page_nums = json.loads(row["page_numbers_json"])
                except Exception:
                    pass

            meta = json.loads(row["metadata_json"]) if row["metadata_json"] else {}

            results[cid] = {
                "chunk_id": cid,
                "content": row["content"],
                "metadata": meta,
                "paper_id": row["paper_id"],
                "paper_title": row["paper_title"],
                "arxiv_id": row["arxiv_id"],
                "paper_version": row["paper_version"],
                "page_number": row["page_number"],
                "page_numbers": page_nums,
                "section": row["section"],
                "element_type": row["element_type"],
                "score": round(score, 6),
                "retrieval_method": "fact_store",
                "match_type": "exact_substring",
            }

        # 2. FTS5 full-text search (if not exact_match_only and we have capacity)
        if not exact_match_only and self._has_fts and len(results) < top_k * 2:
            # Clean search query for FTS syntax
            sanitized_fts = " ".join([re.sub(r"[^\w\.-]", "", tok) for tok in clean_query.split() if tok.strip()])
            if sanitized_fts:
                fts_sql = """
                    SELECT f.chunk_id, f.paper_id, f.paper_title, f.arxiv_id, f.paper_version,
                           f.page_number, f.page_numbers_json, f.section, f.element_type,
                           f.content, f.metadata_json,
                           bm25(facts_fts) as rank_score
                    FROM facts_fts
                    JOIN facts f ON facts_fts.chunk_id = f.chunk_id
                    WHERE facts_fts MATCH ?
                """
                fts_params: List[Any] = [sanitized_fts]
                if paper_filter:
                    fts_sql += " AND f.paper_id = ?"
                    fts_params.append(paper_filter)

                fts_sql += " ORDER BY rank_score ASC LIMIT ?"
                fts_params.append(top_k * 2)

                try:
                    cur.execute(fts_sql, fts_params)
                    for row in cur.fetchall():
                        cid = row["chunk_id"]
                        if cid in results:
                            # Already found via exact match; boost score
                            results[cid]["score"] += 0.5
                            continue

                        # SQLite bm25 returns negative values where lower (more negative) is better
                        raw_rank = float(row["rank_score"])
                        score = max(0.1, 1.0 / (1.0 + abs(raw_rank)))

                        page_nums = [row["page_number"]]
                        if row["page_numbers_json"]:
                            try:
                                page_nums = json.loads(row["page_numbers_json"])
                            except Exception:
                                pass

                        meta = json.loads(row["metadata_json"]) if row["metadata_json"] else {}

                        results[cid] = {
                            "chunk_id": cid,
                            "content": row["content"],
                            "metadata": meta,
                            "paper_id": row["paper_id"],
                            "paper_title": row["paper_title"],
                            "arxiv_id": row["arxiv_id"],
                            "paper_version": row["paper_version"],
                            "page_number": row["page_number"],
                            "page_numbers": page_nums,
                            "section": row["section"],
                            "element_type": row["element_type"],
                            "score": round(score, 6),
                            "retrieval_method": "fact_store",
                            "match_type": "fts5",
                        }
                except sqlite3.OperationalError:
                    # Invalid FTS token sequence (e.g. operators); ignore and rely on exact match
                    pass

        # Sort descending by score
        sorted_results = sorted(results.values(), key=lambda x: x["score"], reverse=True)
        top_results = sorted_results[:top_k]

        # Assign 1-based rank
        for rank, item in enumerate(top_results, start=1):
            item["rank"] = rank

        return top_results

    def get_fact(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a specific fact record by chunk_id."""
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM facts WHERE chunk_id = ?;", (chunk_id,))
        row = cur.fetchone()
        if not row:
            return None

        page_nums = [row["page_number"]]
        if row["page_numbers_json"]:
            try:
                page_nums = json.loads(row["page_numbers_json"])
            except Exception:
                pass

        meta = json.loads(row["metadata_json"]) if row["metadata_json"] else {}

        return {
            "chunk_id": row["chunk_id"],
            "content": row["content"],
            "metadata": meta,
            "paper_id": row["paper_id"],
            "paper_title": row["paper_title"],
            "arxiv_id": row["arxiv_id"],
            "paper_version": row["paper_version"],
            "page_number": row["page_number"],
            "page_numbers": page_nums,
            "section": row["section"],
            "element_type": row["element_type"],
        }

    def close(self) -> None:
        """Close database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
