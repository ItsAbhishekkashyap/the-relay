"""
CLI runner for Task 2.2: Document Chunking.

Executes token-aware chunking over extracted research papers using
fixed-size, structure-aware, and sentence-aware strategies.
Saves chunk outputs under data/chunks/ and writes aggregate reports.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sys
from typing import Any, Dict, List

import numpy as np

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.retrieval.chunking import (
    Chunk,
    ChunkingConfig,
    calculate_coverage,
    chunk_document,
    get_default_tokenizer,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

EXPECTED_PAPERS = [
    {"paper_id": "1706.03762v7", "filename": "1706.03762v7.json"},
    {"paper_id": "2410.00037v1", "filename": "2410.00037v1.json"},
    {"paper_id": "2507.07955v2", "filename": "2507.07955v2.json"},
]


def run_chunking_for_strategy(
    strategy: str,
    extracted_dir: Path,
    output_dir: Path,
    target_size: int,
    overlap_ratio: float,
    max_size: int | None,
    min_size: int,
) -> Dict[str, Any]:
    """Execute chunking for a specific strategy across all expected papers."""
    config = ChunkingConfig(
        strategy=strategy,
        target_chunk_size=target_size,
        max_chunk_size=max_size,
        overlap_ratio=overlap_ratio,
        min_chunk_size=min_size,
    )
    tokenizer = get_default_tokenizer()
    strategy_out_dir = output_dir / strategy
    strategy_out_dir.mkdir(parents=True, exist_ok=True)

    strategy_docs = []

    for spec in EXPECTED_PAPERS:
        json_file = extracted_dir / spec["filename"]
        if not json_file.exists():
            raise FileNotFoundError(f"Missing extracted paper: {json_file}")

        with open(json_file, "r", encoding="utf-8") as f:
            doc_data = json.load(f)

        logger.info(
            "Chunking '%s' using strategy '%s' (target=%d)...",
            spec["paper_id"],
            strategy,
            target_size,
        )

        chunks: List[Chunk] = chunk_document(doc_data, config, tokenizer=tokenizer)

        # Calculate statistics
        token_counts = [c.token_count for c in chunks] if chunks else [0]
        char_counts = [c.character_count for c in chunks] if chunks else [0]

        coverage_info = calculate_coverage(doc_data, chunks)

        doc_summary = {
            "paper_id": spec["paper_id"],
            "paper_title": doc_data["paper_title"],
            "source_filename": doc_data["source_filename"],
            "strategy": strategy,
            "total_pages": doc_data.get("total_pages", len(doc_data.get("pages", []))),
            "total_chunks": len(chunks),
            "token_stats": {
                "min": int(np.min(token_counts)),
                "median": float(np.median(token_counts)),
                "mean": round(float(np.mean(token_counts)), 1),
                "max": int(np.max(token_counts)),
            },
            "char_stats": {
                "min": int(np.min(char_counts)),
                "median": float(np.median(char_counts)),
                "mean": round(float(np.mean(char_counts)), 1),
                "max": int(np.max(char_counts)),
            },
            "coverage": coverage_info,
            "page_coverage": {
                "source_pages": doc_data.get("total_pages", len(doc_data.get("pages", []))),
                "chunked_pages": sorted(list({p for c in chunks for p in c.page_numbers})),
            },
            "output_file": str((strategy_out_dir / spec["filename"]).as_posix()),
        }
        strategy_docs.append(doc_summary)

        # Save individual paper chunk JSON
        out_file = strategy_out_dir / spec["filename"]
        chunk_dicts = [c.model_dump() for c in chunks]
        output_payload = {
            "paper_id": spec["paper_id"],
            "paper_title": doc_data["paper_title"],
            "arxiv_id": doc_data.get("arxiv_id", ""),
            "paper_version": doc_data.get("paper_version", ""),
            "source_filename": doc_data["source_filename"],
            "strategy": strategy,
            "tokenizer_name": tokenizer.name,
            "chunking_config": config.model_dump(),
            "total_chunks": len(chunks),
            "summary": doc_summary,
            "chunks": chunk_dicts,
        }

        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(output_payload, f, ensure_ascii=False, indent=2)

    return {
        "strategy": strategy,
        "tokenizer": tokenizer.name,
        "documents": strategy_docs,
        "total_chunks": sum(d["total_chunks"] for d in strategy_docs),
    }


def generate_chunking_preview(
    reports: List[Dict[str, Any]],
    output_dir: Path,
    preview_path: Path,
    max_snippet_chars: int = 300,
) -> Path:
    """Generate a clean human-readable preview of chunks across strategies and papers."""
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = [
        "=" * 80,
        "THE RELAY — TASK 2.2 CHUNKING PREVIEW REPORT",
        f"Generated at: {datetime.now(timezone.utc).isoformat()}",
        "=" * 80,
        "",
    ]

    for rep in reports:
        strategy = rep["strategy"]
        lines.append(f"STRATEGY: {strategy.upper()} (Tokenizer: {rep['tokenizer']})")
        lines.append(f"Total Chunks Across 3 Papers: {rep['total_chunks']}")
        lines.append("-" * 80)

        for doc_info in rep["documents"]:
            pid = doc_info["paper_id"]
            chunk_file = Path(doc_info["output_file"])

            with open(chunk_file, "r", encoding="utf-8") as f:
                payload = json.load(f)
            chunks = payload.get("chunks", [])

            lines.append(f"  PAPER: {doc_info['paper_title']} ({pid})")
            lines.append(
                f"  Chunks: {len(chunks)} | "
                f"Tokens [min: {doc_info['token_stats']['min']}, "
                f"mean: {doc_info['token_stats']['mean']}, "
                f"max: {doc_info['token_stats']['max']}]"
            )

            if chunks:
                # Sample first chunk, a middle chunk, and the last chunk
                indices = sorted(list({0, len(chunks) // 2, len(chunks) - 1}))
                for idx in indices:
                    c = chunks[idx]
                    sec_str = f" [Section: {c['section']}]" if c.get("section") else ""
                    snip = " ".join(c["chunk_text"][:max_snippet_chars].split())
                    if len(c["chunk_text"]) > max_snippet_chars:
                        snip += " ... [truncated]"
                    lines.append(
                        f"    - Chunk {c['chunk_id']}{sec_str} | "
                        f"Pages {c['page_numbers']} | {c['token_count']} tokens | {c['character_count']} chars:"
                    )
                    lines.append(f"      \"{snip}\"")
            lines.append("")
        lines.append("=" * 80)
        lines.append("")

    preview_path.write_text("\n".join(lines), encoding="utf-8")
    return preview_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Chunk research papers with configurable token-aware strategies."
    )
    parser.add_argument(
        "--strategy",
        default="all",
        choices=["all", "fixed_size", "structure_aware", "sentence_aware"],
        help="Chunking strategy to run (default: all)",
    )
    parser.add_argument(
        "--target-size",
        type=int,
        default=512,
        help="Target chunk size in tokens (default: 512)",
    )
    parser.add_argument(
        "--max-size",
        type=int,
        default=None,
        help="Maximum chunk size in tokens (default: 1.15 * target_size)",
    )
    parser.add_argument(
        "--overlap-ratio",
        type=float,
        default=0.15,
        help="Overlap ratio for fixed_size (default: 0.15)",
    )
    parser.add_argument(
        "--min-size",
        type=int,
        default=30,
        help="Minimum chunk size in tokens (default: 30)",
    )
    parser.add_argument(
        "--extracted-dir",
        type=Path,
        default=Path("data/extracted"),
        help="Directory with extracted JSON files (default: data/extracted)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/chunks"),
        help="Directory to save chunk outputs (default: data/chunks)",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=Path("reports"),
        help="Directory to save chunking reports (default: reports)",
    )

    args = parser.parse_args()

    strategies_to_run = (
        ["fixed_size", "structure_aware", "sentence_aware"]
        if args.strategy == "all"
        else [args.strategy]
    )

    all_strategy_reports = []

    for strat in strategies_to_run:
        rep = run_chunking_for_strategy(
            strategy=strat,
            extracted_dir=args.extracted_dir,
            output_dir=args.output_dir,
            target_size=args.target_size,
            overlap_ratio=args.overlap_ratio,
            max_size=args.max_size,
            min_size=args.min_size,
        )
        all_strategy_reports.append(rep)

    # Combined report
    combined_report = {
        "report_timestamp": datetime.now(timezone.utc).isoformat(),
        "target_chunk_size": args.target_size,
        "overlap_ratio": args.overlap_ratio,
        "strategies_evaluated": strategies_to_run,
        "results": all_strategy_reports,
    }

    report_path = args.reports_dir / "chunking_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(combined_report, f, ensure_ascii=False, indent=2)
    logger.info("Saved combined chunking report to: %s", report_path)

    # Preview report
    preview_path = args.reports_dir / "chunking_preview.txt"
    generate_chunking_preview(all_strategy_reports, args.output_dir, preview_path)
    logger.info("Saved chunking preview to: %s", preview_path)

    # Summary table
    print("\n" + "=" * 70)
    print(f"CHUNKING COMPLETE (Target: {args.target_size} tokens, Overlap: {args.overlap_ratio:.0%}):")
    for rep in all_strategy_reports:
        strat = rep["strategy"]
        print(f"\n[Strategy: {strat.upper()}] (Tokenizer: {rep['tokenizer']})")
        print(f"Total Chunks: {rep['total_chunks']}")
        for d in rep["documents"]:
            t = d["token_stats"]
            cov = d["coverage"]["word_coverage_ratio"]
            print(
                f"  - {d['paper_id']} ({d['source_filename']}): "
                f"{d['total_chunks']} chunks | "
                f"Tokens [min={t['min']}, median={t['median']}, mean={t['mean']}, max={t['max']}] | "
                f"Coverage={cov:.1%}"
            )
    print("=" * 70 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
