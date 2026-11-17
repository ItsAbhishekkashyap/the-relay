"""
Unit tests for PDF ingestion and LangChain Document representation.

Tests PyMuPDF extraction, 1-based page representation, metadata preservation,
strict section grouping, multi-table detection, uncaptioned tables, and reading order.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pymupdf
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.retrieval.pdf_ingestion import (
    PAPERS_CATALOG,
    detect_heading,
    extract_page_elements,
    get_paper_metadata_for_path,
    ingest_pdf_to_documents,
    is_running_header_footer,
    should_scan_for_tables,
)


@pytest.fixture(scope="module")
def papers_dir() -> Path:
    return REPO_ROOT / "papers"


@pytest.fixture(scope="module")
def ingested_all_papers(papers_dir: Path) -> Dict[str, list]:
    """Cache ingested documents across tests in this module to avoid redundant parsing."""
    corpus = {}
    for paper_info in PAPERS_CATALOG:
        pdf_path = papers_dir / paper_info["source_filename"]
        corpus[paper_info["paper_id"]] = ingest_pdf_to_documents(pdf_path, paper_meta=paper_info)
    return corpus


def test_papers_catalog_metadata():
    assert len(PAPERS_CATALOG) == 3
    ids = {p["paper_id"] for p in PAPERS_CATALOG}
    assert ids == {"1706.03762v7", "2410.00037v1", "2507.07955v2"}


def test_all_three_pdfs_ingested(ingested_all_papers):
    for paper_info in PAPERS_CATALOG:
        docs = ingested_all_papers[paper_info["paper_id"]]
        assert len(docs) > 0, f"No documents ingested for {paper_info['paper_id']}"


def test_every_original_page_represented_1based(ingested_all_papers):
    expected_page_counts = {
        "1706.03762v7": 15,
        "2410.00037v1": 66,
        "2507.07955v2": 39,
    }

    for paper_info in PAPERS_CATALOG:
        paper_id = paper_info["paper_id"]
        expected_total = expected_page_counts[paper_id]

        docs = ingested_all_papers[paper_id]
        found_pages = set()
        for d in docs:
            found_pages.update(d.metadata.get("page_numbers", [d.metadata["page_number"]]))

        # Check 1-based page representation
        assert min(found_pages) == 1
        assert max(found_pages) == expected_total
        assert len(found_pages) == expected_total, f"Missing pages in {paper_id}: {set(range(1, expected_total+1)) - found_pages}"


def test_metadata_correctness_and_json_serializability(ingested_all_papers):
    docs = ingested_all_papers["1706.03762v7"]

    for d in docs:
        meta = d.metadata
        assert meta["paper_id"] == "1706.03762v7"
        assert meta["arxiv_id"] == "1706.03762"
        assert meta["paper_version"] == "v7"
        assert meta["paper_title"] == "Attention Is All You Need"
        assert meta["source_filename"] == "1706.03762v7.pdf"
        assert isinstance(meta["page_number"], int)
        assert meta["page_number"] >= 1
        assert isinstance(meta["bbox"], list)
        assert len(meta["bbox"]) == 4
        assert "element_type" in meta
        assert "source_block_id" in meta

        # Metadata must be strictly JSON-serializable
        serialized = json.dumps(meta)
        assert len(serialized) > 0


def test_section_level_grouping_prevents_cross_section_mixing(papers_dir: Path):
    """
    Regression test for section grouping:
    Attention Page 2 contains at least three distinct section headings:
    1 Introduction, 2 Background, 3 Model Architecture.
    Verify that:
    1. Page 2 produces 3 separate documents.
    2. No document contains content belonging to multiple sections.
    3. Every document has the correct section metadata.
    4. Page 3 correctly continues section '3 Model Architecture' before heading 3.1.
    """
    pdf_path = papers_dir / "1706.03762v7.pdf"
    docs = ingest_pdf_to_documents(pdf_path)

    p2_docs = [d for d in docs if d.metadata["page_number"] == 2]
    assert len(p2_docs) == 3, f"Expected exactly 3 documents on page 2, got {len(p2_docs)}"

    doc1, doc2, doc3 = p2_docs

    # Doc 1: Section 1
    assert doc1.metadata["section"] == "1 Introduction"
    assert "1 Introduction" in doc1.page_content or "1\nIntroduction" in doc1.page_content
    assert "2 Background" not in doc1.page_content
    assert "3 Model Architecture" not in doc1.page_content

    # Doc 2: Section 2
    assert doc2.metadata["section"] == "2 Background"
    assert "2 Background" in doc2.page_content or "2\nBackground" in doc2.page_content
    assert "1 Introduction" not in doc2.page_content
    assert "3 Model Architecture" not in doc2.page_content

    # Doc 3: Section 3
    assert doc3.metadata["section"] == "3 Model Architecture"
    assert "3 Model Architecture" in doc3.page_content or "3\nModel Architecture" in doc3.page_content
    assert "1 Introduction" not in doc3.page_content
    assert "2 Background" not in doc3.page_content

    # Page 3 continuation verification
    p3_docs = [d for d in docs if d.metadata["page_number"] == 3]
    assert len(p3_docs) >= 2
    assert p3_docs[0].metadata["section"] == "3 Model Architecture", "Section 3 state did not carry over to page 3"


def test_table_elements_detected_and_classified(papers_dir: Path):
    # Attention has known tables on pages 6, 8, 9, 10
    pdf_path = papers_dir / "1706.03762v7.pdf"
    docs = ingest_pdf_to_documents(pdf_path)

    table_docs = [d for d in docs if d.metadata.get("element_type") in ("table", "table_unstructured")]
    assert len(table_docs) >= 3

    table_pages = {d.metadata["page_number"] for d in table_docs}
    assert 6 in table_pages
    assert 8 in table_pages or 9 in table_pages


def test_structured_and_unstructured_tables_coexist_without_suppression(papers_dir: Path):
    """
    Regression test:
    Verify that an unstructured table element (e.g. Table 1 caption) is NOT
    misclassified as prose when a structured table exists on the same page.
    """
    pdf_path = papers_dir / "1706.03762v7.pdf"
    docs = ingest_pdf_to_documents(pdf_path)

    p6_docs = [d for d in docs if d.metadata["page_number"] == 6]
    structured = [d for d in p6_docs if d.metadata["element_type"] == "table"]
    unstructured = [d for d in p6_docs if d.metadata["element_type"] == "table_unstructured"]

    assert len(structured) >= 1, "Structured Table 1 on page 6 missing"
    assert len(unstructured) >= 1, "Unstructured table element on page 6 was suppressed"
    assert "|LayerType|" in structured[0].page_content


def test_table_without_recognizable_caption_synthetic_fixture(tmp_path: Path):
    """
    Regression test:
    Verify table extraction operates on a bordered table that does NOT have
    a recognizable 'Table N' caption.
    """
    pdf_path = tmp_path / "uncaptioned_table.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)

    # Narrative text without any "Table" keyword
    page.insert_text((72, 100), "Hyperparameter Overview and Configuration Matrix", fontsize=14)

    # Draw horizontal ruling lines resembling a table grid
    shape = page.new_shape()
    shape.draw_line((72, 130), (540, 130))
    shape.draw_line((72, 160), (540, 160))
    shape.draw_line((72, 190), (540, 190))
    shape.finish(width=1, color=(0, 0, 0))
    shape.commit()

    # Insert cell text
    page.insert_text((80, 150), "Parameter | Value | Description", fontsize=10)
    page.insert_text((80, 180), "Batch Size | 128 | Training samples", fontsize=10)
    page.insert_text((72, 230), "Subsequent prose narrative continuing after the table.", fontsize=11)

    doc.save(pdf_path)
    doc.close()

    assert should_scan_for_tables(pymupdf.open(pdf_path)[0], "Parameter | Value | Description") is True
    ingested = ingest_pdf_to_documents(pdf_path)
    assert len(ingested) >= 1


def test_page_with_multiple_tables_synthetic_fixture(tmp_path: Path):
    """
    Regression test:
    Verify a page containing multiple tables produces independent Documents for each table.
    """
    pdf_path = tmp_path / "multi_table.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)

    page.insert_text((72, 80), "1 Overview", fontsize=14)

    # Table 1: Boxed grid with dividing lines
    page.draw_rect(pymupdf.Rect(72, 110, 500, 180), color=(0, 0, 0), width=1)
    page.draw_line((72, 140), (500, 140), color=(0, 0, 0), width=1)
    page.draw_line((250, 110), (250, 180), color=(0, 0, 0), width=1)
    page.insert_text((80, 130), "ColA", fontsize=10)
    page.insert_text((260, 130), "ColB", fontsize=10)
    page.insert_text((80, 165), "Val1", fontsize=10)
    page.insert_text((260, 165), "Val2", fontsize=10)

    # Table 2: Boxed grid with dividing lines
    page.draw_rect(pymupdf.Rect(72, 230, 500, 300), color=(0, 0, 0), width=1)
    page.draw_line((72, 260), (500, 260), color=(0, 0, 0), width=1)
    page.draw_line((250, 230), (250, 300), color=(0, 0, 0), width=1)
    page.insert_text((80, 250), "Metric", fontsize=10)
    page.insert_text((260, 250), "Score", fontsize=10)
    page.insert_text((80, 285), "Accuracy", fontsize=10)
    page.insert_text((260, 285), "94.2", fontsize=10)

    doc.save(pdf_path)
    doc.close()

    ingested = ingest_pdf_to_documents(pdf_path)
    table_docs = [d for d in ingested if "table" in d.metadata["element_type"]]
    assert len(table_docs) == 2, f"Expected 2 table documents, got {len(table_docs)}"


def test_multi_column_reading_order_preservation(papers_dir: Path):
    """
    Regression test:
    Verify reading order is preserved on multi-column layouts (Moshi page 34).
    The left-column subfigure (a) caption blocks must not be interleaved line-by-line
    with right-column subfigure (b) caption blocks.
    """
    pdf_path = papers_dir / "2410.00037v1.pdf"
    doc = pymupdf.open(pdf_path)
    page = doc[33]  # Page 34

    meta = {"paper_id": "2410.00037v1", "paper_title": "Moshi"}
    elements, _ = extract_page_elements(page, page_num=34, paper_meta=meta)

    # Locate blocks for subfigure (a) and subfigure (b)
    sub_a_indices = [i for i, elem in enumerate(elements) if "(a) Entropy spectrum" in elem["text"]]
    sub_b_indices = [i for i, elem in enumerate(elements) if "(b) Significant degradations" in elem["text"]]

    assert len(sub_a_indices) == 1, "Subfigure (a) missing from elements"
    assert len(sub_b_indices) == 1, "Subfigure (b) missing from elements"
    assert sub_a_indices[0] < sub_b_indices[0], "Reading order inverted between subfigure (a) and (b)"


def test_heading_detection_heuristics():
    is_head, title = detect_heading("1 Introduction\n")
    assert is_head is True
    assert title == "1 Introduction"

    is_head, title = detect_heading("3.2 Attention")
    assert is_head is True
    assert title == "3.2 Attention"

    # Multi-line numbered headings
    is_head, title = detect_heading("3.1\nEncoder and Decoder Stacks\n")
    assert is_head is True
    assert title == "3.1 Encoder and Decoder Stacks"

    is_head, title = detect_heading("References\n")
    assert is_head is True
    assert title == "References"

    # Regular body prose should not be detected as heading
    is_head, title = detect_heading("The Transformer follows this overall architecture using stacked self-attention...")
    assert is_head is False


def test_running_header_footer_detection():
    meta = {"paper_title": "Moshi: A Speech-Text Foundation Model for Real-Time Dialogue"}
    page_height = 792.0

    # Top running title header
    is_hf = is_running_header_footer(
        text="Moshi: a speech-text foundation model for real-time dialogue",
        bbox=(141.0, 38.0, 466.0, 48.0),
        page_height=page_height,
        paper_meta=meta,
    )
    assert is_hf is True

    # Standalone bottom page number footer
    is_hf = is_running_header_footer(
        text="2\n",
        bbox=(303.0, 742.0, 308.0, 752.0),
        page_height=page_height,
        paper_meta=meta,
    )
    assert is_hf is True

    # Body prose in the middle of page
    is_hf = is_running_header_footer(
        text="This is regular body prose.",
        bbox=(108.0, 200.0, 500.0, 300.0),
        page_height=page_height,
        paper_meta=meta,
    )
    assert is_hf is False


def test_empty_page_handling_safety(tmp_path: Path):
    # Construct an artificial empty single-page PDF
    empty_pdf_path = tmp_path / "empty_test.pdf"
    doc = pymupdf.open()
    doc.new_page(width=612, height=792)
    doc.save(empty_pdf_path)
    doc.close()

    docs = ingest_pdf_to_documents(empty_pdf_path)
    assert len(docs) == 1
    assert docs[0].metadata["element_type"] == "empty_page"
    assert docs[0].metadata["page_number"] == 1
    assert docs[0].page_content == ""
