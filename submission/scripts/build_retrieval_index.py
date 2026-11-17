"""
Build and Populate Hybrid Retrieval Indexes.

Reads the approved LangChain recursive chunk datasets from data/chunks/langchain_recursive/,
builds and populates:
1. ChromaDB Dense Vector Store (cosine distance, local all-MiniLM-L6-v2)
2. BM25 Keyword Search Index (persisted to data/indexes/bm25/bm25_index.json)
3. Structured SQLite Fact Store (persisted to data/indexes/fact_store.db)

Verifies indexing idempotency and outputs summary statistics.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.retrieval.bm25_retriever import BM25Retriever
from app.retrieval.dense_retriever import DenseRetriever, LocalSentenceTransformerEmbeddingFunction
from app.retrieval.fact_store import FactStore
from app.retrieval.hybrid_retriever import HybridRetriever

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

CHUNKS_DIR = REPO_ROOT / "data" / "chunks" / "langchain_recursive"
INDEX_BASE_DIR = REPO_ROOT / "data" / "indexes"
CHROMA_DIR = INDEX_BASE_DIR / "chroma"
BM25_FILE = INDEX_BASE_DIR / "bm25" / "bm25_index.json"
FACT_DB_PATH = INDEX_BASE_DIR / "fact_store.db"


def load_all_chunks() -> List[Dict[str, Any]]:
    """Load all approved chunks from JSON files in data/chunks/langchain_recursive/."""
    if not CHUNKS_DIR.exists():
        raise FileNotFoundError(f"Chunk dataset directory not found: {CHUNKS_DIR}")

    all_chunks: List[Dict[str, Any]] = []
    chunk_files = sorted(CHUNKS_DIR.glob("*.json"))

    if not chunk_files:
        raise FileNotFoundError(f"No chunk JSON files found in {CHUNKS_DIR}")

    for file_path in chunk_files:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        chunks = data.get("chunks", [])
        all_chunks.extend(chunks)
        print(f"  Loaded {len(chunks)} chunks from {file_path.name} ({data.get('paper_title', 'Unknown')})")

    return all_chunks


def build_indexes() -> Dict[str, Any]:
    """Execute complete index build across Dense, BM25, and Fact Store."""
    print("=" * 80)
    print("THE RELAY: Stage 2.4 Hybrid Retrieval Engine — Index Construction")
    print("=" * 80)

    # 1. Load Chunks
    print("\n[1/5] Loading approved chunk datasets...")
    t0 = time.perf_counter()
    chunks = load_all_chunks()
    load_time = time.perf_counter() - t0
    print(f"Total chunks loaded: {len(chunks)} in {load_time:.2f}s")

    # 2. Build ChromaDB Dense Collection
    print(f"\n[2/5] Building ChromaDB dense vector store at {CHROMA_DIR}...")
    t_dense = time.perf_counter()
    emb_fn = LocalSentenceTransformerEmbeddingFunction()
    dense_retriever = DenseRetriever(
        persist_dir=CHROMA_DIR,
        collection_name="relay_papers",
        embedding_function=emb_fn,
    )
    dense_indexed = dense_retriever.index_chunks(chunks, batch_size=64)
    dense_time = time.perf_counter() - t_dense
    print(f"  ChromaDB indexed {dense_indexed} chunks in {dense_time:.2f}s (Metric: cosine)")

    # 3. Build BM25 Keyword Index
    print(f"\n[3/5] Building BM25 keyword index at {BM25_FILE}...")
    t_bm25 = time.perf_counter()
    bm25_retriever = BM25Retriever()
    bm25_indexed = bm25_retriever.index_chunks(chunks)
    bm25_retriever.save(BM25_FILE)
    bm25_time = time.perf_counter() - t_bm25
    print(f"  BM25 indexed {bm25_indexed} chunks in {bm25_time:.2f}s")

    # 4. Build Structured SQLite Fact Store
    print(f"\n[4/5] Building SQLite Structured Fact Store at {FACT_DB_PATH}...")
    t_fact = time.perf_counter()
    fact_store = FactStore(db_path=FACT_DB_PATH)
    facts_indexed = fact_store.index_chunks(chunks, filter_fact_elements_only=True)
    fact_time = time.perf_counter() - t_fact
    print(f"  Fact Store indexed {facts_indexed} structured table & fact records in {fact_time:.2f}s")

    # 5. Verify Idempotency (Repeat indexing without duplicates)
    print("\n[5/5] Verifying repeatability & idempotency...")
    repeat_dense = dense_retriever.index_chunks(chunks, batch_size=64)
    repeat_bm25 = bm25_retriever.index_chunks(chunks)
    repeat_facts = fact_store.index_chunks(chunks, filter_fact_elements_only=True)

    assert repeat_dense == dense_indexed, f"Chroma count changed on re-index: {repeat_dense} != {dense_indexed}"
    assert repeat_bm25 == bm25_indexed, f"BM25 count changed on re-index: {repeat_bm25} != {bm25_indexed}"
    assert repeat_facts == facts_indexed, f"FactStore count changed on re-index: {repeat_facts} != {facts_indexed}"
    print(f"  Idempotency verified! Counts remain unchanged: Dense={repeat_dense}, BM25={repeat_bm25}, Facts={repeat_facts}")

    # Build hybrid retriever for sample queries
    hybrid = HybridRetriever(
        dense_retriever=dense_retriever,
        bm25_retriever=bm25_retriever,
        fact_store=fact_store,
        rrf_k=60,
    )

    # Test Sample Queries
    sample_queries = [
        ("Attention Is All You Need", "What is the dimensionality d_model of the Transformer?"),
        ("Moshi", "What is the audio latency of Moshi in milliseconds?"),
        ("Dynamic Chunking", "How does dynamic chunking reduce computational complexity?"),
    ]

    print("\n" + "=" * 80)
    print("SAMPLE RETRIEVAL DEMONSTRATIONS (Reciprocal Rank Fusion)")
    print("=" * 80)

    for topic, q in sample_queries:
        print(f"\nQuery: '{q}' [{topic}]")
        results = hybrid.retrieve(q, top_k=3)
        for r in results:
            channels = "+".join(r["retrieval_channels"])
            print(f"  - Rank {r['rank']} | Score: {r['score']:.4f} | Channels: {channels} | Chunk: {r['chunk_id']} | Paper: {r['paper_id']} (p.{r['page_number']})")
            snippet = r["content"].replace("\n", " ")[:120]
            print(f"    Snippet: {snippet}...")

    stats = {
        "total_chunks_loaded": len(chunks),
        "dense_chunks_indexed": dense_indexed,
        "bm25_chunks_indexed": bm25_indexed,
        "facts_indexed": facts_indexed,
        "dense_build_seconds": round(dense_time, 2),
        "bm25_build_seconds": round(bm25_time, 2),
        "fact_store_build_seconds": round(fact_time, 2),
    }

    fact_store.close()
    return stats


if __name__ == "__main__":
    build_indexes()

