"""
PDF Ingestion Engine for The Relay Research Assistant.

Extracts research papers using PyMuPDF (pymupdf) page-by-page, preserves
1-based page numbers, detects headings and sections, identifies structured
and unstructured tables, filters recurring headers/footers, preserves column
reading order, and converts extracted content into standardized LangChain Document objects.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pymupdf  # PyMuPDF 2.x recommended API
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

# Canonical catalog of the three research papers
PAPERS_CATALOG: List[Dict[str, str]] = [
    {
        "paper_id": "1706.03762v7",
        "arxiv_id": "1706.03762",
        "paper_version": "v7",
        "paper_title": "Attention Is All You Need",
        "source_filename": "1706.03762v7.pdf",
    },
    {
        "paper_id": "2410.00037v1",
        "arxiv_id": "2410.00037",
        "paper_version": "v1",
        "paper_title": "Moshi: A Speech-Text Foundation Model for Real-Time Dialogue",
        "source_filename": "2410.00037v1.pdf",
    },
    {
        "paper_id": "2507.07955v2",
        "arxiv_id": "2507.07955",
        "paper_version": "v2",
        "paper_title": "Dynamic Chunking for End-to-End Hierarchical Sequence Modeling",
        "source_filename": "2507.07955v2.pdf",
    },
]

# Section heading regexes
RE_NUMBERED_HEADING = re.compile(
    r"^(\d+(\.\d+)*)\s+([A-Z][A-Za-z0-9\s\-:,()]+)$"
)
RE_HEADING_NUMBER_PREFIX = re.compile(r"^(\d+(\.\d+)*)$")
RE_NAMED_SECTION = re.compile(
    r"^(abstract|introduction|background|model architecture|conclusions?|references|acknowledgments?|broader impact|appendix(\s+[A-Za-z0-9]+.*)?)$",
    re.IGNORECASE,
)
RE_TABLE_LABEL = re.compile(
    r"\bTable\s+([A-Za-z0-9]+)[:.]?", re.IGNORECASE
)
RE_TABLE_CAPTION = re.compile(
    r"^(Table|TABLE|Tab\.)\s+([A-Za-z0-9]+)[:.]?", re.IGNORECASE
)


def get_paper_metadata_for_path(pdf_path: str | Path) -> Dict[str, str]:
    """Resolve paper metadata from filename or catalog."""
    p = Path(pdf_path)
    stem = p.stem
    for entry in PAPERS_CATALOG:
        if entry["source_filename"] == p.name or entry["paper_id"] == stem or entry["arxiv_id"] in stem:
            return entry

    # Fallback heuristic
    return {
        "paper_id": stem,
        "arxiv_id": stem.split("v")[0] if "v" in stem else stem,
        "paper_version": "v" + stem.split("v")[-1] if "v" in stem else "v1",
        "paper_title": stem,
        "source_filename": p.name,
    }


def is_running_header_footer(
    text: str,
    bbox: Tuple[float, float, float, float],
    page_height: float,
    paper_meta: Dict[str, str],
) -> bool:
    """Identify recurring running headers and standalone page number footers."""
    clean = text.strip()
    if not clean:
        return False

    y0, y1 = bbox[1], bbox[3]

    # Running header detection: near top of page (y0 < 55)
    if y0 < 55:
        lower = clean.lower()
        title_lower = paper_meta.get("paper_title", "").lower()
        # Substring of paper title in header
        if len(clean) > 8 and title_lower and clean.lower() in title_lower:
            return True
        if "arxiv:" in lower or "preprint" in lower or "under review" in lower:
            return True
        if lower.startswith("moshi:") or lower.startswith("attention is"):
            return True
        # Lone number near top
        if clean.isdigit():
            return True

    # Running footer detection: near bottom of page (y0 > page_height - 55)
    if y0 > (page_height - 55):
        # Standalone page number
        if clean.isdigit():
            return True
        lower = clean.lower()
        if "arxiv:" in lower and len(clean) < 80:
            return True

    return False


def detect_heading(text: str) -> Tuple[bool, Optional[str]]:
    """
    Determine whether text is a section heading and return the normalized section title.
    Supports single-line headings ('1 Introduction', '3.2 Attention') and
    two-line headings ('1\\nIntroduction', '3.1\\nEncoder and Decoder Stacks').
    """
    clean = text.strip()
    if not clean or len(clean) > 120:
        return False, None

    lines = [line.strip() for line in clean.splitlines() if line.strip()]
    if not lines:
        return False, None

    # Check flattened single line: e.g. "3.1 Encoder and Decoder Stacks"
    flattened = " ".join(lines)
    m_num = RE_NUMBERED_HEADING.match(flattened)
    if m_num:
        return True, flattened

    # Two-line numbered heading where line 1 is number prefix (e.g. "1" or "3.1")
    if len(lines) == 2 and RE_HEADING_NUMBER_PREFIX.match(lines[0]) and len(lines[1]) > 2:
        return True, f"{lines[0]} {lines[1]}"

    # Named standard sections (e.g. Abstract, References)
    if RE_NAMED_SECTION.match(lines[0]) or RE_NAMED_SECTION.match(flattened):
        return True, flattened

    return False, None


def should_scan_for_tables(page: pymupdf.Page, page_text: str) -> bool:
    """
    Determine if a page is a plausible candidate for PyMuPDF table extraction.

    Evaluates candidate status independently of caption regex while preventing
    unnecessary, expensive table searches on pages with dense vector graphics
    (e.g., audio waveforms or spectrograms in Moshi) where find_tables() can stall.

    Trade-off documented:
    - Pages with explicit table captions or tabular delimiters ('\\t', '|') are scanned.
    - Pages with horizontal body ruling lines (>= 2 body lines and <= 150 drawings)
      are scanned to discover uncaptioned bordered tables.
    - Dense vector pages (>150 drawings without explicit table indicators) and
      pure narrative pages without ruling lines are skipped to maintain fast execution.
    """
    # 1. Explicit table caption or label pattern
    if RE_TABLE_LABEL.search(page_text):
        return True

    # 2. Text delimiters indicating tabular layout
    if "\t" in page_text or "|" in page_text:
        return True

    # 3. Horizontal body ruling lines in drawings (for uncaptioned bordered tables)
    drawings = page.get_drawings()
    if 0 < len(drawings) <= 150:
        ph = page.rect.height
        body_lines = [
            d for d in drawings
            if d.get("rect") and d["rect"].width > 80 and d["rect"].height < 6
            and 55 < d["rect"].y0 < (ph - 55)
        ]
        if len(body_lines) >= 2:
            return True

    return False


def is_unstructured_table_block(text: str) -> bool:
    """
    Determine if an unbordered or non-grid block contains table-like tabular content.
    Identifies table captions, unbordered tabular figures, or multi-column data blocks.
    Does NOT falsely trigger on prose that merely mentions 'Table N' mid-sentence.
    """
    clean = text.strip()
    if not clean:
        return False

    # Block begins with a dedicated table caption/label (e.g. "Table 1: Hyperparameters...")
    first_line = clean.splitlines()[0].strip()
    if RE_TABLE_CAPTION.match(first_line):
        return True

    # Multi-line tabular text with tab stops or columnar spacing and numeric data
    lines = [line.strip() for line in clean.splitlines() if line.strip()]
    if len(lines) >= 3:
        columnar_lines = sum(1 for line in lines if "\t" in line or "  " in line)
        if columnar_lines >= len(lines) * 0.7:
            numeric_tokens = len(re.findall(r"\b\d+(\.\d+)?%?\b", clean))
            if numeric_tokens >= 4:
                return True

    return False


def extract_page_elements(
    page: pymupdf.Page,
    page_num: int,
    paper_meta: Dict[str, str],
    current_section: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Extract structured elements from a single PDF page in reading order.

    Preserves PyMuPDF native block sequence (block_no) to prevent multi-column
    interleaving, embeds detected tables at their appropriate positions in the flow,
    and isolates unbordered table elements independently.

    Returns:
        elements: List of dicts representing structured blocks.
        updated_section: The active section at the end of this page.
    """
    page_rect = page.rect
    page_height = page_rect.height
    paper_id = paper_meta["paper_id"]

    page_text = page.get_text("text")
    blocks = page.get_text("blocks")  # (x0, y0, x1, y1, text, block_no, block_type)

    # 1. Identify tables using PyMuPDF find_tables if page is a plausible candidate
    detected_tables: List[Dict[str, Any]] = []
    if should_scan_for_tables(page, page_text):
        try:
            # If drawing count is high, lines strategy avoids exponential polygon analysis
            strategy = "lines" if len(page.get_drawings()) > 100 else "lines"
            tabs = page.find_tables(strategy=strategy)
            for i, tab in enumerate(tabs.tables):
                tb_bbox = list(tab.bbox)
                tb_markdown = tab.to_markdown()
                is_structured = tab.row_count > 1 and tab.col_count > 1 and bool(tb_markdown.strip())
                elem_type = "table" if is_structured else "table_unstructured"
                detected_tables.append({
                    "bbox": [round(float(c), 2) for c in tb_bbox],
                    "markdown": tb_markdown,
                    "row_count": tab.row_count,
                    "col_count": tab.col_count,
                    "element_type": elem_type,
                    "table_id": f"{paper_id}_p{page_num}_tab{i}",
                    "emitted": False,
                })
        except Exception as e:
            logger.warning(f"Table detection skipped on {paper_id} p.{page_num}: {e}")

    def get_overlapping_table(bbox: Tuple[float, float, float, float]) -> Optional[Dict[str, Any]]:
        bx0, by0, bx1, by1 = bbox
        for tab in detected_tables:
            tx0, ty0, tx1, ty1 = tab["bbox"]
            # Check overlap tolerance
            if bx0 >= (tx0 - 10) and bx1 <= (tx1 + 10) and by0 >= (ty0 - 10) and by1 <= (ty1 + 10):
                return tab
        return False

    elements: List[Dict[str, Any]] = []
    active_section = current_section

    # Identify all section headings on the page to accurately resolve table float sections
    page_headings: List[Tuple[float, str]] = []
    for b in blocks:
        if len(b) >= 7 and b[6] == 0:
            btxt = b[4].strip()
            is_h, stitle = detect_heading(btxt)
            if is_h and stitle:
                page_headings.append((b[1], stitle))

    def resolve_section_for_table(tab_label: str, default_sec: Optional[str]) -> Optional[str]:
        """Resolve section for table floats that appear above the section heading discussing them."""
        for b in blocks:
            if len(b) >= 7 and b[6] == 0:
                btxt = b[4].strip()
                if tab_label.lower() in btxt.lower():
                    by0 = b[1]
                    matching_sec = None
                    for hy0, hsec in page_headings:
                        if hy0 <= by0:
                            matching_sec = hsec
                    if matching_sec and matching_sec != default_sec:
                        return matching_sec
        return default_sec

    recent_table_caption: Optional[str] = None
    recent_table_caption_label: Optional[str] = None
    paper_title = paper_meta.get("paper_title", paper_id)

    # 2. Iterate text blocks in PyMuPDF native layout reading order (bno sequence)
    # This prevents interleaving separate columns line-by-line.
    for b in blocks:
        if len(b) < 7:
            continue
        bx0, by0, bx1, by1, btext, bno, btype = b[:7]
        clean_text = btext.strip()
        if not clean_text or btype != 0:
            continue

        bbox_coords = [round(float(c), 2) for c in (bx0, by0, bx1, by1)]
        block_id = f"{paper_id}_p{page_num}_b{bno}"

        # Check running header / footer
        if is_running_header_footer(clean_text, (bx0, by0, bx1, by1), page_height, paper_meta):
            elements.append({
                "element_type": "header_footer",
                "text": clean_text,
                "bbox": bbox_coords,
                "block_id": block_id,
                "section": active_section,
                "page_number": page_num,
            })
            continue

        # Check if block falls inside a detected table
        matched_table = get_overlapping_table((bx0, by0, bx1, by1))
        if matched_table:
            # Emit table at its natural reading order location if not already emitted
            if not matched_table["emitted"]:
                tab_sec = active_section
                if recent_table_caption_label:
                    tab_sec = resolve_section_for_table(f"Table {recent_table_caption_label}", active_section) or active_section
                
                header_prefix = f"[Paper: {paper_title} ({paper_id}) | Page {page_num} | Section: {tab_sec or 'General'}]"
                if recent_table_caption:
                    combined_text = f"{header_prefix}\n{recent_table_caption}\n\n{matched_table['markdown']}"
                else:
                    combined_text = f"{header_prefix}\n{matched_table['markdown']}"

                elements.append({
                    "element_type": matched_table["element_type"],
                    "text": combined_text,
                    "bbox": matched_table["bbox"],
                    "block_id": matched_table["table_id"],
                    "section": tab_sec,
                    "page_number": page_num,
                    "row_count": matched_table["row_count"],
                    "col_count": matched_table["col_count"],
                    "caption": recent_table_caption,
                })
                matched_table["emitted"] = True
            # Skip block to prevent duplicate extraction of table content as prose
            continue

        # Check if block itself is an unbordered table or table caption
        # Evaluated independently for each block; not suppressed if other tables exist
        if is_unstructured_table_block(clean_text):
            cap_m = RE_TABLE_CAPTION.match(clean_text)
            if cap_m:
                recent_table_caption = clean_text
                recent_table_caption_label = cap_m.group(2)
                cap_sec = resolve_section_for_table(f"Table {recent_table_caption_label}", active_section) or active_section
            else:
                cap_sec = active_section

            elements.append({
                "element_type": "table_unstructured",
                "text": clean_text,
                "bbox": bbox_coords,
                "block_id": block_id,
                "section": cap_sec,
                "page_number": page_num,
            })
            continue

        # Check heading
        is_head, sec_title = detect_heading(clean_text)
        if is_head and sec_title:
            active_section = sec_title
            elements.append({
                "element_type": "heading",
                "text": clean_text,
                "bbox": bbox_coords,
                "block_id": block_id,
                "section": active_section,
                "page_number": page_num,
            })
            continue

        # Normal prose / narrative block
        elements.append({
            "element_type": "prose",
            "text": clean_text,
            "bbox": bbox_coords,
            "block_id": block_id,
            "section": active_section,
            "page_number": page_num,
        })

    # 3. If any detected table was not emitted via overlapping blocks, append it
    for t in detected_tables:
        if not t["emitted"]:
            tab_sec = active_section
            if recent_table_caption_label:
                tab_sec = resolve_section_for_table(f"Table {recent_table_caption_label}", active_section) or active_section
            header_prefix = f"[Paper: {paper_title} ({paper_id}) | Page {page_num} | Section: {tab_sec or 'General'}]"
            if recent_table_caption:
                combined_text = f"{header_prefix}\n{recent_table_caption}\n\n{t['markdown']}"
            else:
                combined_text = f"{header_prefix}\n{t['markdown']}"

            elements.append({
                "element_type": t["element_type"],
                "text": combined_text,
                "bbox": t["bbox"],
                "block_id": t["table_id"],
                "section": tab_sec,
                "page_number": page_num,
                "row_count": t["row_count"],
                "col_count": t["col_count"],
                "caption": recent_table_caption,
            })
            t["emitted"] = True

    return elements, active_section


def ingest_pdf_to_documents(
    pdf_path: str | Path,
    paper_meta: Optional[Dict[str, str]] = None,
    filter_headers_footers: bool = True,
    group_by_page: bool = True,
) -> List[Document]:
    """
    Ingest a PDF file and return a list of LangChain Document objects.

    Enforces strict section-level isolation:
    - When a heading is encountered, previous prose is flushed immediately.
    - Headings introduce sections, and subsequent prose blocks inherit that section.
    - No single Document combines content belonging to different sections.
    - Tables are emitted as independent Documents.
    - Section state continues correctly across page boundaries.

    Args:
        pdf_path: Path to the target research PDF.
        paper_meta: Optional metadata dict. If None, resolved from catalog.
        filter_headers_footers: If True, omit repeated header/footer elements.
        group_by_page: If True, aggregates contiguous prose blocks within the same
                       section on the page into cohesive Documents.

    Returns:
        List of LangChain Document objects with complete JSON-serializable metadata.
    """
    p = Path(pdf_path)
    if not p.is_file():
        raise FileNotFoundError(f"PDF file not found at: {p}")

    meta = paper_meta or get_paper_metadata_for_path(p)
    paper_id = meta["paper_id"]
    arxiv_id = meta["arxiv_id"]
    paper_version = meta["paper_version"]
    paper_title = meta["paper_title"]
    source_filename = meta["source_filename"]

    doc = pymupdf.open(p)
    documents: List[Document] = []
    active_section: Optional[str] = None

    for page_idx in range(len(doc)):
        page_num = page_idx + 1  # 1-based page numbering
        page = doc[page_idx]

        elements, active_section = extract_page_elements(
            page=page,
            page_num=page_num,
            paper_meta=meta,
            current_section=active_section,
        )

        if filter_headers_footers:
            elements = [e for e in elements if e["element_type"] != "header_footer"]

        # Handle empty or zero-element page safely
        if not elements:
            empty_doc = Document(
                page_content="",
                metadata={
                    "paper_id": paper_id,
                    "arxiv_id": arxiv_id,
                    "paper_version": paper_version,
                    "paper_title": paper_title,
                    "source_filename": source_filename,
                    "page_number": page_num,
                    "page_numbers": [page_num],
                    "section": active_section,
                    "element_type": "empty_page",
                    "source_block_id": f"{paper_id}_p{page_num}_empty",
                    "source_block_ids": [f"{paper_id}_p{page_num}_empty"],
                    "bbox": [0.0, 0.0, round(page.rect.width, 2), round(page.rect.height, 2)],
                },
            )
            documents.append(empty_doc)
            continue

        if not group_by_page:
            # Emit individual block-level documents
            for elem in elements:
                d = Document(
                    page_content=elem["text"],
                    metadata={
                        "paper_id": paper_id,
                        "arxiv_id": arxiv_id,
                        "paper_version": paper_version,
                        "paper_title": paper_title,
                        "source_filename": source_filename,
                        "page_number": elem["page_number"],
                        "page_numbers": [elem["page_number"]],
                        "section": elem.get("section"),
                        "element_type": elem["element_type"],
                        "source_block_id": elem["block_id"],
                        "source_block_ids": [elem["block_id"]],
                        "bbox": elem["bbox"],
                    },
                )
                documents.append(d)
        else:
            # Group contiguous prose blocks within the SAME section.
            # Flushes when encountering a table, or when a new heading starts a different section.
            current_prose_blocks: List[Dict[str, Any]] = []
            current_prose_section: Optional[str] = None

            def flush_prose_group():
                nonlocal current_prose_section
                if not current_prose_blocks:
                    return
                combined_text = "\n\n".join(b["text"] for b in current_prose_blocks)
                block_ids = [b["block_id"] for b in current_prose_blocks]
                min_x0 = min(b["bbox"][0] for b in current_prose_blocks)
                min_y0 = min(b["bbox"][1] for b in current_prose_blocks)
                max_x1 = max(b["bbox"][2] for b in current_prose_blocks)
                max_y1 = max(b["bbox"][3] for b in current_prose_blocks)
                sec = current_prose_section

                d = Document(
                    page_content=combined_text,
                    metadata={
                        "paper_id": paper_id,
                        "arxiv_id": arxiv_id,
                        "paper_version": paper_version,
                        "paper_title": paper_title,
                        "source_filename": source_filename,
                        "page_number": page_num,
                        "page_numbers": [page_num],
                        "section": sec,
                        "element_type": "prose",
                        "source_block_id": block_ids[0],
                        "source_block_ids": block_ids,
                        "bbox": [round(min_x0, 2), round(min_y0, 2), round(max_x1, 2), round(max_y1, 2)],
                    },
                )
                documents.append(d)
                current_prose_blocks.clear()

            for elem in elements:
                elem_type = elem["element_type"]
                elem_sec = elem.get("section")

                if elem_type in ("table", "table_unstructured"):
                    # Tables are independent Documents: flush preceding prose first
                    flush_prose_group()
                    tb_doc = Document(
                        page_content=elem["text"],
                        metadata={
                            "paper_id": paper_id,
                            "arxiv_id": arxiv_id,
                            "paper_version": paper_version,
                            "paper_title": paper_title,
                            "source_filename": source_filename,
                            "page_number": elem["page_number"],
                            "page_numbers": [elem["page_number"]],
                            "section": elem_sec,
                            "element_type": elem_type,
                            "source_block_id": elem["block_id"],
                            "source_block_ids": [elem["block_id"]],
                            "bbox": elem["bbox"],
                        },
                    )
                    documents.append(tb_doc)
                    # Next prose group continues with the active section
                    current_prose_section = elem_sec
                elif elem_type == "heading":
                    # Heading starts a new section: flush previous section's prose immediately
                    flush_prose_group()
                    current_prose_section = elem_sec
                    current_prose_blocks.append(elem)
                else:
                    # Prose block: belongs to current section
                    if not current_prose_blocks and current_prose_section is None:
                        current_prose_section = elem_sec
                    current_prose_blocks.append(elem)

            flush_prose_group()

    doc.close()
    return documents
