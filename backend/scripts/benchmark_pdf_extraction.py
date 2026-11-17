"""
Benchmark PDF Extraction Pipeline: Docling vs PyMuPDF.

This script benchmarks structured document extraction between PyMuPDF (fitz)
and Docling (IBM Document Converter with Heron layout + TableFormer models)
on representative pages from the three target research papers.

Environment: Run inside .venv_docling isolated environment.
"""

from __future__ import annotations

import gc
import json
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import fitz  # PyMuPDF
import psutil

# Docling imports
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.base_models import InputFormat


REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "reports" / "pdf_extraction_benchmark"
SAMPLES_DIR = OUTPUT_DIR / "samples"
TEMP_DIR = OUTPUT_DIR / "temp_pages"

# Representative pages selected across the 3 papers (1-based page numbers)
BENCHMARK_TARGETS = [
    {
        "paper_id": "1706.03762v7",
        "title": "Attention Is All You Need",
        "pdf_path": REPO_ROOT / "papers" / "1706.03762v7.pdf",
        "pages": [
            {
                "page_num": 3,
                "category": "Math & Multi-column",
                "description": "Section 3.2 Attention equations (Scaled Dot-Product & Multi-Head), Fig 2 ref, two-column layout.",
            },
            {
                "page_num": 9,
                "category": "Complex Multi-column Table",
                "description": "Table 3 Variations on Transformer Architecture (8 columns, ablation rows A-E).",
            },
            {
                "page_num": 11,
                "category": "Dense References",
                "description": "References section, dense two-column citations with authors, titles, arXiv links.",
            },
        ],
    },
    {
        "paper_id": "2410.00037v1",
        "title": "Moshi: A Speech-Text Foundation Model for Real-Time Dialogue",
        "pdf_path": REPO_ROOT / "papers" / "2410.00037v1.pdf",
        "pages": [
            {
                "page_num": 7,
                "category": "Math & Formulas",
                "description": "Section 3.2 RVQ codebook equations (1)-(5), multi-stream hierarchy math, continuous prose.",
            },
            {
                "page_num": 33,
                "category": "Ablation Table",
                "description": "Table 10 Quantization ablation with ViSQOL, Mel distance, UTMOS multi-column headers.",
            },
            {
                "page_num": 66,
                "category": "Lexical Listing / Unpunctuated",
                "description": "Table 19 92 speaking styles listing (<whisper>, <fast>, etc.), dense unpunctuated tokens.",
            },
        ],
    },
    {
        "paper_id": "2507.07955v2",
        "title": "Dynamic Chunking for End-to-End Hierarchical Sequence Modeling",
        "pdf_path": REPO_ROOT / "papers" / "2507.07955v2.pdf",
        "pages": [
            {
                "page_num": 6,
                "category": "Algorithmic Math",
                "description": "Section 3 Dynamic Chunking equations (2)-(6), argmax operations, hierarchical tokens.",
            },
            {
                "page_num": 19,
                "category": "Floating Figures & Captions",
                "description": "Floating Figures 9 & 10 ablation curves embedded between split body paragraphs.",
            },
            {
                "page_num": 39,
                "category": "Byte Streams & Monospace",
                "description": "Figure 16 UTF-8 hex byte stream table and tokenization bias analysis.",
            },
        ],
    },
]


def get_process_memory_mb() -> float:
    """Return current process RSS memory in megabytes."""
    return psutil.Process().memory_info().rss / (1024 * 1024)


def extract_pymupdf_structured(doc: fitz.Document, page_num: int) -> Dict[str, Any]:
    """Extract structured information using PyMuPDF (blocks and dict)."""
    # 0-based index
    page = doc.load_page(page_num - 1)
    
    t0 = time.perf_counter()
    raw_text = page.get_text("text")
    blocks = page.get_text("blocks")  # (x0, y0, x1, y1, text, block_no, block_type)
    page_dict = page.get_text("dict")  # structured spans, fonts, flags, bboxes
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    # Summarize blocks
    text_blocks = []
    image_blocks = []
    for b in blocks:
        if len(b) >= 7 and b[6] == 0:  # text block
            text_blocks.append({
                "block_no": b[5],
                "bbox": [round(coord, 2) for coord in b[:4]],
                "text": b[4].strip(),
            })
        else:
            image_blocks.append({
                "block_no": b[5] if len(b) >= 6 else -1,
                "bbox": [round(coord, 2) for coord in b[:4]],
            })

    total_spans = 0
    font_names = set()
    for block in page_dict.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                total_spans += 1
                if "font" in span:
                    font_names.add(span["font"])

    return {
        "execution_time_ms": round(elapsed_ms, 2),
        "char_count": len(raw_text),
        "total_blocks": len(blocks),
        "text_block_count": len(text_blocks),
        "image_block_count": len(image_blocks),
        "span_count": total_spans,
        "unique_fonts": sorted(list(font_names)),
        "raw_text_excerpt": raw_text[:500],
        "structured_blocks": text_blocks,
    }


def extract_docling_structured(
    converter: DocumentConverter,
    source_pdf: Path,
    page_num: int,
    temp_dir: Path,
) -> Dict[str, Any]:
    """Extract structured document using Docling on a single-page slice."""
    # Slice single page
    temp_pdf_path = temp_dir / f"temp_{source_pdf.stem}_p{page_num}.pdf"
    src_doc = fitz.open(source_pdf)
    temp_doc = fitz.open()
    temp_doc.insert_pdf(src_doc, from_page=page_num - 1, to_page=page_num - 1)
    temp_doc.save(temp_pdf_path)
    temp_doc.close()
    src_doc.close()

    mem_before = get_process_memory_mb()
    t0 = time.perf_counter()
    
    conversion_result = converter.convert(temp_pdf_path)
    
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    mem_after = get_process_memory_mb()
    mem_delta = max(0.0, mem_after - mem_before)

    docling_doc = conversion_result.document
    md_content = docling_doc.export_to_markdown()
    dict_content = docling_doc.export_to_dict()

    # Extract high-level structural counts from Docling document
    tables = getattr(docling_doc, "tables", []) or []
    table_count = len(tables)
    pictures = getattr(docling_doc, "pictures", []) or []
    picture_count = len(pictures)

    # Count headings and items
    heading_count = 0
    text_item_count = 0
    for item, _level in docling_doc.iterate_items():
        item_type = type(item).__name__
        if "heading" in item_type.lower() or "title" in item_type.lower() or getattr(item, "label", "") in ("section_header", "title", "heading"):
            heading_count += 1
        else:
            text_item_count += 1

    # Cleanup temp file
    try:
        temp_pdf_path.unlink(missing_ok=True)
    except Exception:
        pass

    return {
        "execution_time_ms": round(elapsed_ms, 2),
        "memory_delta_mb": round(mem_delta, 2),
        "char_count": len(md_content),
        "table_count": table_count,
        "picture_count": picture_count,
        "heading_count": heading_count,
        "text_item_count": text_item_count,
        "markdown_content": md_content,
        "dict_content": dict_content,
    }


def run_benchmark() -> None:
    """Execute complete side-by-side benchmark."""
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("THE RELAY: Task 2.2A PDF Extraction Benchmark (Docling vs PyMuPDF)")
    print(f"Platform: {platform.platform()} | Python: {platform.python_version()}")
    print("=" * 80)

    # Initialize Docling DocumentConverter once to reuse loaded layout & table models
    print("\n[1/3] Initializing Docling DocumentConverter (do_ocr=False, do_table_structure=True)...")
    t_init = time.perf_counter()
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = False
    pipeline_options.do_table_structure = True
    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
    )
    init_duration = time.perf_counter() - t_init
    print(f"Converter initialized in {init_duration:.2f}s. Baseline memory: {get_process_memory_mb():.2f} MB")

    benchmark_results: List[Dict[str, Any]] = []

    print("\n[2/3] Processing benchmark target pages...")
    for target in BENCHMARK_TARGETS:
        paper_id = target["paper_id"]
        pdf_path = target["pdf_path"]
        title = target["title"]

        print(f"\n--- Paper: {paper_id} ({title}) ---")
        src_fitz = fitz.open(pdf_path)

        for page_info in target["pages"]:
            page_num = page_info["page_num"]
            cat = page_info["category"]
            desc = page_info["description"]
            print(f"\n  -> Running Page {page_num} [{cat}]")

            # 1. PyMuPDF Extraction
            pymupdf_res = extract_pymupdf_structured(src_fitz, page_num)
            print(f"     [PyMuPDF] {pymupdf_res['execution_time_ms']:.1f}ms | {pymupdf_res['char_count']} chars | {pymupdf_res['total_blocks']} blocks")

            # Save PyMuPDF structured sample JSON
            pymupdf_sample_path = SAMPLES_DIR / f"pymupdf_{paper_id}_p{page_num}.json"
            with open(pymupdf_sample_path, "w", encoding="utf-8") as f:
                json.dump(pymupdf_res, f, indent=2, ensure_ascii=False)

            # 2. Docling Extraction
            docling_res = extract_docling_structured(converter, pdf_path, page_num, TEMP_DIR)
            print(f"     [Docling] {docling_res['execution_time_ms']:.1f}ms ({docling_res['execution_time_ms']/1000.0:.2f}s) | {docling_res['char_count']} chars | {docling_res['table_count']} tables | {docling_res['heading_count']} headings")

            # Save Docling sample Markdown
            docling_md_path = SAMPLES_DIR / f"docling_{paper_id}_p{page_num}.md"
            with open(docling_md_path, "w", encoding="utf-8") as f:
                f.write(docling_res["markdown_content"])

            # Save Docling sample JSON (compact structure)
            docling_sample_path = SAMPLES_DIR / f"docling_{paper_id}_p{page_num}.json"
            sample_summary = {
                "paper_id": paper_id,
                "page_num": page_num,
                "execution_time_ms": docling_res["execution_time_ms"],
                "table_count": docling_res["table_count"],
                "heading_count": docling_res["heading_count"],
                "char_count": docling_res["char_count"],
                "markdown_excerpt": docling_res["markdown_content"][:1000],
            }
            with open(docling_sample_path, "w", encoding="utf-8") as f:
                json.dump(sample_summary, f, indent=2, ensure_ascii=False)

            # Compute comparative ratios
            speedup = (
                round(docling_res["execution_time_ms"] / max(0.01, pymupdf_res["execution_time_ms"]), 1)
                if pymupdf_res["execution_time_ms"] > 0
                else 0
            )

            benchmark_results.append({
                "paper_id": paper_id,
                "paper_title": title,
                "page_num": page_num,
                "category": cat,
                "description": desc,
                "pymupdf": {
                    "time_ms": pymupdf_res["execution_time_ms"],
                    "char_count": pymupdf_res["char_count"],
                    "block_count": pymupdf_res["total_blocks"],
                    "text_blocks": pymupdf_res["text_block_count"],
                    "spans": pymupdf_res["span_count"],
                },
                "docling": {
                    "time_ms": docling_res["execution_time_ms"],
                    "time_sec": round(docling_res["execution_time_ms"] / 1000.0, 2),
                    "memory_delta_mb": docling_res["memory_delta_mb"],
                    "char_count": docling_res["char_count"],
                    "table_count": docling_res["table_count"],
                    "heading_count": docling_res["heading_count"],
                    "picture_count": docling_res["picture_count"],
                },
                "comparison": {
                    "docling_to_pymupdf_time_ratio": speedup,
                    "char_difference": docling_res["char_count"] - pymupdf_res["char_count"],
                },
            })

            # Force garbage collection between pages to avoid memory creep
            gc.collect()

        src_fitz.close()

    # Clean up temp directory
    try:
        for p in TEMP_DIR.glob("*"):
            p.unlink(missing_ok=True)
        TEMP_DIR.rmdir()
    except Exception:
        pass

    # Save benchmark_report.json
    print("\n[3/3] Generating final benchmark artifacts...")
    import docling
    docling_version = getattr(docling, "__version__", "2.150.0")
    pymupdf_version = getattr(fitz, "__version__", "2.1.0")

    report_data = {
        "metadata": {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "python_version": platform.python_version(),
            "docling_version": docling_version,
            "pymupdf_version": pymupdf_version,
            "os": platform.platform(),
            "cpu_count": os.cpu_count(),
            "system_ram_gb": round(psutil.virtual_memory().total / (1024**3), 2),
            "free_ram_gb": round(psutil.virtual_memory().available / (1024**3), 2),
            "total_benchmark_pages": len(benchmark_results),
        },
        "pages": benchmark_results,
    }

    report_json_path = OUTPUT_DIR / "benchmark_report.json"
    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)
    print(f"Saved machine-readable metrics: {report_json_path}")


if __name__ == "__main__":
    run_benchmark()

