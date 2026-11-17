"""
PDF text extraction pipeline for The Relay research assistant.

Extracts research papers page by page using PyMuPDF (fitz), preserving document
identity, page boundaries, character counts, and metadata for source citation.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

import fitz  # PyMuPDF

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Expected research papers for The Relay assignment
EXPECTED_PAPERS: List[Dict[str, str]] = [
    {
        "filename": "1706.03762v7.pdf",
        "paper_id": "1706.03762v7",
        "arxiv_id": "1706.03762",
        "version": "v7",
        "title": "Attention Is All You Need",
    },
    {
        "filename": "2410.00037v1.pdf",
        "paper_id": "2410.00037v1",
        "arxiv_id": "2410.00037",
        "version": "v1",
        "title": "Moshi: A Speech-Text Foundation Model for Real-Time Dialogue",
    },
    {
        "filename": "2507.07955v2.pdf",
        "paper_id": "2507.07955v2",
        "arxiv_id": "2507.07955",
        "version": "v2",
        "title": "Dynamic Chunking for End-to-End Hierarchical Sequence Modeling",
    },
]

DEFAULT_LOW_TEXT_THRESHOLD = 100


def compute_sha256(filepath: str | Path) -> str:
    """Compute SHA-256 checksum of a file in streaming chunks."""
    path = Path(filepath)
    if not path.is_file():
        raise FileNotFoundError(f"File not found for checksum calculation: {path}")

    sha256_hash = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def extract_pdf(
    pdf_path: str | Path,
    paper_id: Optional[str] = None,
    paper_title: Optional[str] = None,
    paper_version: Optional[str] = None,
    arxiv_id: Optional[str] = None,
    low_text_threshold: int = DEFAULT_LOW_TEXT_THRESHOLD,
) -> Dict[str, Any]:
    """
    Extract a PDF document page by page preserving metadata and page boundaries.

    Args:
        pdf_path: Path to the input PDF file.
        paper_id: Unique paper identifier (e.g. '1706.03762v7').
        paper_title: Canonical title of the paper.
        paper_version: Version identifier (e.g. 'v7').
        arxiv_id: arXiv identifier without version (e.g. '1706.03762').
        low_text_threshold: Character threshold below which a low-text warning is generated.

    Returns:
        Structured dictionary containing document metadata, warnings, and page-level data.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"Source PDF does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"Path is not a regular file: {path}")

    # Calculate SHA-256 of the source PDF
    checksum = compute_sha256(path)

    # Derive identifiers if not explicitly provided
    stem = path.stem
    pid = paper_id or stem
    pversion = paper_version or ("v" + stem.split("v")[-1] if "v" in stem else "")
    aid = arxiv_id or (stem.split("v")[0] if "v" in stem else stem)

    try:
        doc = fitz.open(path)
    except Exception as e:
        raise ValueError(f"Failed to open and parse PDF '{path}': {e}") from e

    doc_warnings: List[str] = []
    pdf_meta = doc.metadata or {}

    # Extract internal PDF metadata safely
    metadata_block = {
        "title": pdf_meta.get("title", "") or "",
        "author": pdf_meta.get("author", "") or "",
        "subject": pdf_meta.get("subject", "") or "",
        "creator": pdf_meta.get("creator", "") or "",
        "producer": pdf_meta.get("producer", "") or "",
        "creation_date": pdf_meta.get("creationDate", "") or "",
        "mod_date": pdf_meta.get("modDate", "") or "",
        "format": pdf_meta.get("format", "") or "",
        "encryption": pdf_meta.get("encryption", None),
    }

    resolved_title = paper_title or metadata_block["title"] or stem

    total_pages = len(doc)
    if total_pages == 0:
        doc_warnings.append("Document has 0 pages.")

    pages_data: List[Dict[str, Any]] = []
    total_characters = 0

    for page_idx in range(total_pages):
        page = doc[page_idx]
        page_num = page_idx + 1  # 1-based human-readable page numbering
        page_warnings: List[str] = []

        # Extract text conservatively using PyMuPDF's default text extraction
        extracted_text = page.get_text("text")
        char_count = len(extracted_text)
        total_characters += char_count

        # Check for empty or low-text pages
        if char_count == 0:
            warn = f"Page {page_num} is empty (0 characters extracted)."
            page_warnings.append(warn)
            doc_warnings.append(warn)
        elif char_count < low_text_threshold:
            warn = (
                f"Page {page_num} has unusually low extracted text "
                f"({char_count} characters, threshold: {low_text_threshold})."
            )
            page_warnings.append(warn)
            doc_warnings.append(warn)

        page_record = {
            "page_number": page_num,
            "character_count": char_count,
            "paper_id": pid,
            "arxiv_id": aid,
            "paper_version": pversion,
            "paper_title": resolved_title,
            "source_filename": path.name,
            "extracted_text": extracted_text,
            "text": extracted_text,  # alias for convenience
            "warnings": page_warnings,
        }
        pages_data.append(page_record)

    doc.close()

    extraction_record = {
        "paper_id": pid,
        "arxiv_id": aid,
        "paper_version": pversion,
        "paper_title": resolved_title,
        "source_filename": path.name,
        "source_filepath": str(path.as_posix()),
        "sha256": checksum,
        "total_pages": total_pages,
        "total_characters": total_characters,
        "extraction_timestamp": datetime.now(timezone.utc).isoformat(),
        "pdf_metadata": metadata_block,
        "warnings": doc_warnings,
        "pages": pages_data,
    }

    return extraction_record


def save_extracted_paper(doc_data: Dict[str, Any], output_path: str | Path) -> Path:
    """Save extracted paper record as a formatted UTF-8 JSON file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc_data, f, ensure_ascii=False, indent=2)
    logger.info("Saved extracted document JSON to: %s", path)
    return path


def generate_extraction_report(
    documents: List[Dict[str, Any]],
    report_path: str | Path,
) -> Dict[str, Any]:
    """Generate and write a combined extraction report summarizing all processed documents."""
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    total_pages = sum(d["total_pages"] for d in documents)
    total_characters = sum(d["total_characters"] for d in documents)

    doc_summaries = []
    for d in documents:
        empty_pages = [
            p["page_number"] for p in d["pages"] if p["character_count"] == 0
        ]
        low_text_pages = [
            p["page_number"]
            for p in d["pages"]
            if 0 < p["character_count"] < DEFAULT_LOW_TEXT_THRESHOLD
        ]
        doc_summaries.append(
            {
                "paper_id": d["paper_id"],
                "arxiv_id": d.get("arxiv_id", ""),
                "paper_version": d.get("paper_version", ""),
                "paper_title": d["paper_title"],
                "source_filename": d["source_filename"],
                "sha256": d["sha256"],
                "total_pages": d["total_pages"],
                "total_characters": d["total_characters"],
                "empty_pages": empty_pages,
                "low_text_pages": low_text_pages,
                "warning_count": len(d.get("warnings", [])),
                "warnings": d.get("warnings", []),
                "status": "success",
            }
        )

    report = {
        "report_timestamp": datetime.now(timezone.utc).isoformat(),
        "total_documents": len(documents),
        "total_pages": total_pages,
        "total_characters": total_characters,
        "status": "success",
        "documents": doc_summaries,
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    logger.info("Saved combined extraction report to: %s", path)
    return report


def generate_preview(
    documents: List[Dict[str, Any]],
    preview_path: str | Path,
    max_preview_length: int = 350,
) -> Path:
    """Generate a readable text preview of key pages from each extracted paper."""
    path = Path(preview_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    lines: List[str] = [
        "=" * 80,
        "THE RELAY — RESEARCH PAPERS EXTRACTION PREVIEW",
        f"Generated at: {datetime.now(timezone.utc).isoformat()}",
        f"Total Documents: {len(documents)}",
        "=" * 80,
        "",
    ]

    for d in documents:
        lines.append(f"PAPER TITLE: {d['paper_title']}")
        lines.append(f"SOURCE FILE: {d['source_filename']}")
        lines.append(f"PAPER ID:    {d['paper_id']} (Version: {d.get('paper_version', 'N/A')})")
        lines.append(f"SHA-256:     {d['sha256']}")
        lines.append(f"TOTAL PAGES: {d['total_pages']} | TOTAL CHARACTERS: {d['total_characters']}")
        lines.append("-" * 80)

        # Select preview pages: Page 1, a middle page, and the final page
        total = d["total_pages"]
        preview_page_nums = sorted(list({1, max(1, total // 2), total}))

        for p_num in preview_page_nums:
            page = d["pages"][p_num - 1]
            text = page["extracted_text"].strip()
            # Clean snippet for readable display
            clean_snippet = " ".join(text[:max_preview_length].split())
            if len(text) > max_preview_length:
                clean_snippet += " ... [truncated]"
            lines.append(f"  [Page {p_num:02d} / {total:02d}] ({page['character_count']} chars):")
            lines.append(f"  \"{clean_snippet}\"")
            lines.append("")

        lines.append("=" * 80)
        lines.append("")

    content = "\n".join(lines)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info("Saved readable extraction preview to: %s", path)
    return path


def extract_all_papers(
    papers_dir: str | Path = "papers",
    output_dir: str | Path = "data/extracted",
    reports_dir: str | Path = "reports",
    low_text_threshold: int = DEFAULT_LOW_TEXT_THRESHOLD,
) -> Dict[str, Any]:
    """
    Extract all expected research papers, write per-paper JSON files,
    and generate the combined report and human-readable preview.
    """
    papers_path = Path(papers_dir)
    out_path = Path(output_dir)
    rep_path = Path(reports_dir)

    if not papers_path.is_dir():
        raise FileNotFoundError(f"Papers directory does not exist: {papers_path}")

    out_path.mkdir(parents=True, exist_ok=True)
    rep_path.mkdir(parents=True, exist_ok=True)

    extracted_documents: List[Dict[str, Any]] = []

    for spec in EXPECTED_PAPERS:
        pdf_file = papers_path / spec["filename"]
        if not pdf_file.exists():
            raise FileNotFoundError(
                f"Expected research paper missing: '{spec['filename']}' at {pdf_file}"
            )

        logger.info(
            "Extracting '%s' (%s) from %s...",
            spec["title"],
            spec["paper_id"],
            pdf_file.name,
        )

        doc_data = extract_pdf(
            pdf_path=pdf_file,
            paper_id=spec["paper_id"],
            paper_title=spec["title"],
            paper_version=spec["version"],
            arxiv_id=spec["arxiv_id"],
            low_text_threshold=low_text_threshold,
        )

        json_out = out_path / f"{spec['paper_id']}.json"
        save_extracted_paper(doc_data, json_out)
        extracted_documents.append(doc_data)

    report_out = rep_path / "extraction_report.json"
    report = generate_extraction_report(extracted_documents, report_out)

    preview_out = rep_path / "extraction_preview.txt"
    generate_preview(extracted_documents, preview_out)

    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract research papers page by page using PyMuPDF."
    )
    parser.add_argument(
        "--papers-dir",
        default="papers",
        help="Directory containing the source PDF papers (default: papers)",
    )
    parser.add_argument(
        "--output-dir",
        default="data/extracted",
        help="Directory to save extracted JSON files (default: data/extracted)",
    )
    parser.add_argument(
        "--reports-dir",
        default="reports",
        help="Directory to save extraction reports (default: reports)",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=DEFAULT_LOW_TEXT_THRESHOLD,
        help="Character count threshold for low-text page warnings (default: 100)",
    )

    args = parser.parse_args()

    try:
        report = extract_all_papers(
            papers_dir=args.papers_dir,
            output_dir=args.output_dir,
            reports_dir=args.reports_dir,
            low_text_threshold=args.threshold,
        )
        print("\n" + "=" * 60)
        print("EXTRACTION SUMMARY:")
        print(f"Total documents processed: {report['total_documents']}")
        print(f"Total pages extracted:     {report['total_pages']}")
        print(f"Total characters:          {report['total_characters']}")
        print(f"Extraction status:         {report['status']}")
        for doc in report["documents"]:
            print(
                f"  - {doc['paper_id']} ({doc['source_filename']}): "
                f"{doc['total_pages']} pages, {doc['total_characters']} chars, "
                f"{doc['warning_count']} warnings"
            )
        print("=" * 60 + "\n")
        return 0
    except Exception as e:
        logger.error("Extraction pipeline failed: %s", e, exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())

