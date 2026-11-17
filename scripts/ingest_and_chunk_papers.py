"""
Ingest and Chunk Research Papers via LangChain Pipeline.

Processes all three target research PDFs using PyMuPDF ingestion and
LangChain's RecursiveCharacterTextSplitter with local MiniLM tokenization.
Outputs datasets to data/chunks/langchain_recursive/ and reports to reports/.
"""

from __future__ import annotations

import json
import logging
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.retrieval.langchain_chunking import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    chunk_langchain_documents,
    chunk_to_dict,
    count_tokens,
    get_local_tokenizer,
)
from app.retrieval.pdf_ingestion import PAPERS_CATALOG, ingest_pdf_to_documents

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
PAPERS_DIR = REPO_ROOT / "papers"
OUTPUT_DIR = REPO_ROOT / "data" / "chunks" / "langchain_recursive"
REPORTS_DIR = REPO_ROOT / "reports"


def run_pipeline() -> Dict[str, Any]:
    """Execute complete ingestion and chunking pipeline across all 3 papers."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("THE RELAY: Task 2.3B LangChain-based Ingestion & Token-Aware Chunking")
    print("=" * 80)

    # 1. Verify tokenizer availability
    print("\n[1/4] Verifying local MiniLM tokenizer...")
    t0 = time.perf_counter()
    tokenizer = get_local_tokenizer()
    print(f"Tokenizer loaded locally in {time.perf_counter() - t0:.2f}s: {type(tokenizer).__name__}")

    all_paper_results: List[Dict[str, Any]] = []
    total_docs_all = 0
    total_chunks_all = 0
    all_token_counts: List[int] = []

    # 2. Process each paper
    print("\n[2/4] Ingesting and chunking papers...")
    for paper_info in PAPERS_CATALOG:
        paper_id = paper_info["paper_id"]
        pdf_path = PAPERS_DIR / paper_info["source_filename"]
        title = paper_info["paper_title"]

        print(f"\n--- Processing: {paper_id} ({title}) ---")
        if not pdf_path.exists():
            raise FileNotFoundError(f"Source PDF missing: {pdf_path}")

        t_ingest = time.perf_counter()
        raw_documents = ingest_pdf_to_documents(pdf_path, paper_meta=paper_info, group_by_page=True)
        ingest_time = time.perf_counter() - t_ingest
        print(f"  Ingested {len(raw_documents)} documents in {ingest_time:.2f}s")

        t_chunk = time.perf_counter()
        chunk_documents = chunk_langchain_documents(
            raw_documents,
            tokenizer=tokenizer,
            chunk_size=DEFAULT_CHUNK_SIZE,
            chunk_overlap=DEFAULT_CHUNK_OVERLAP,
        )
        chunk_time = time.perf_counter() - t_chunk
        print(f"  Generated {len(chunk_documents)} chunks in {chunk_time:.2f}s")

        # Extract metrics
        serialized_chunks = [chunk_to_dict(c) for c in chunk_documents]
        token_counts = [c["token_count"] for c in serialized_chunks]
        all_token_counts.extend(token_counts)

        # Page representation check
        represented_pages = set()
        for c in serialized_chunks:
            represented_pages.update(c.get("page_numbers", [c["page_number"]]))

        # Element type breakdown
        elem_breakdown: Dict[str, int] = {}
        for c in serialized_chunks:
            etype = c.get("element_type", "prose")
            elem_breakdown[etype] = elem_breakdown.get(etype, 0) + 1

        total_docs_all += len(raw_documents)
        total_chunks_all += len(chunk_documents)

        # Save per-paper JSON dataset
        dataset_path = OUTPUT_DIR / f"{paper_id}.json"
        paper_dataset = {
            "paper_id": paper_id,
            "arxiv_id": paper_info["arxiv_id"],
            "paper_version": paper_info["paper_version"],
            "paper_title": title,
            "source_filename": paper_info["source_filename"],
            "chunking_strategy": "langchain_recursive",
            "chunk_size": DEFAULT_CHUNK_SIZE,
            "chunk_overlap": DEFAULT_CHUNK_OVERLAP,
            "total_documents_ingested": len(raw_documents),
            "total_chunks": len(serialized_chunks),
            "token_stats": {
                "min": min(token_counts) if token_counts else 0,
                "max": max(token_counts) if token_counts else 0,
                "mean": round(statistics.mean(token_counts), 2) if token_counts else 0,
                "median": statistics.median(token_counts) if token_counts else 0,
            },
            "element_types": elem_breakdown,
            "chunks": serialized_chunks,
        }

        with open(dataset_path, "w", encoding="utf-8") as f:
            json.dump(paper_dataset, f, indent=2, ensure_ascii=False)
        print(f"  Saved chunk dataset to: {dataset_path.name}")

        all_paper_results.append({
            "paper_id": paper_id,
            "paper_title": title,
            "source_filename": paper_info["source_filename"],
            "documents_ingested": len(raw_documents),
            "chunks_generated": len(serialized_chunks),
            "represented_pages": sorted(list(represented_pages)),
            "token_stats": paper_dataset["token_stats"],
            "element_types": elem_breakdown,
        })

    # 3. Generate summary report
    print("\n[3/4] Generating reports...")
    report_data = {
        "metadata": {
            "pipeline": "LangChain RecursiveCharacterTextSplitter",
            "tokenizer": "sentence-transformers/all-MiniLM-L6-v2",
            "chunk_size": DEFAULT_CHUNK_SIZE,
            "chunk_overlap": DEFAULT_CHUNK_OVERLAP,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        "summary": {
            "total_papers": len(all_paper_results),
            "total_documents_ingested": total_docs_all,
            "total_chunks_generated": total_chunks_all,
            "token_stats": {
                "min": min(all_token_counts) if all_token_counts else 0,
                "max": max(all_token_counts) if all_token_counts else 0,
                "mean": round(statistics.mean(all_token_counts), 2) if all_token_counts else 0,
                "median": statistics.median(all_token_counts) if all_token_counts else 0,
            },
        },
        "papers": all_paper_results,
    }

    report_path = REPORTS_DIR / "langchain_chunking_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)
    print(f"Saved machine-readable report: {report_path.name}")

    # 4. Generate preview text
    preview_lines = [
        "=" * 80,
        "THE RELAY: LangChain Recursive Chunking Preview",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
        f"Configuration: chunk_size={DEFAULT_CHUNK_SIZE}, chunk_overlap={DEFAULT_CHUNK_OVERLAP}",
        "=" * 80,
        "",
    ]

    for p_res in all_paper_results:
        paper_id = p_res["paper_id"]
        preview_lines.append(f"### PAPER: {paper_id} — {p_res['paper_title']}")
        preview_lines.append(f"Source: {p_res['source_filename']}")
        preview_lines.append(f"Docs: {p_res['documents_ingested']} | Chunks: {p_res['chunks_generated']} | Pages: {len(p_res['represented_pages'])}")
        preview_lines.append(f"Token Stats: Min={p_res['token_stats']['min']}, Max={p_res['token_stats']['max']}, Mean={p_res['token_stats']['mean']}, Median={p_res['token_stats']['median']}")
        preview_lines.append(f"Elements: {p_res['element_types']}")
        preview_lines.append("-" * 60)

        # Load saved dataset to preview first 3 chunks and sample table
        with open(OUTPUT_DIR / f"{paper_id}.json", "r", encoding="utf-8") as f:
            ds = json.load(f)

        chunks = ds["chunks"]
        preview_chunks = chunks[:3]
        # Include first table chunk if available and not already in preview
        table_chunks = [c for c in chunks if "table" in c.get("element_type", "") and c not in preview_chunks]
        if table_chunks:
            preview_chunks.append(table_chunks[0])

        for c in preview_chunks:
            preview_lines.append(f"Chunk ID: {c['chunk_id']} (Index: {c['chunk_index']})")
            preview_lines.append(f"Page(s): {c.get('page_numbers', [c['page_number']])} | Section: {c.get('section')} | Type: {c.get('element_type')}")
            preview_lines.append(f"Tokens: {c['token_count']} | Characters: {c['character_count']}")
            preview_lines.append("Content:")
            preview_lines.append(c["chunk_text"][:350] + ("..." if len(c["chunk_text"]) > 350 else ""))
            preview_lines.append("." * 40)

        preview_lines.append("\n")

    preview_path = REPORTS_DIR / "langchain_chunking_preview.txt"
    with open(preview_path, "w", encoding="utf-8") as f:
        f.write("\n".join(preview_lines))
    print(f"Saved human-readable preview: {preview_path.name}")

    print("\n[4/4] Pipeline completed successfully!")
    return report_data


if __name__ == "__main__":
    run_pipeline()
