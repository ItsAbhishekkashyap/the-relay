"""
Tests for Task 2.1: PDF text extraction pipeline.

Verifies:
- Extraction from temporary synthetic PDFs (using PyMuPDF)
- 1-based page numbering
- Page boundary preservation
- Unicode preservation
- Empty and low-text warning generation
- Error handling for missing/unreadable PDFs
- SHA-256 calculation
- Output JSON serialization and structure integrity
"""

import hashlib
import json
from pathlib import Path
import sys
import pytest
import fitz  # PyMuPDF

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.extract_papers import (
    compute_sha256,
    extract_pdf,
    save_extracted_paper,
    generate_extraction_report,
    generate_preview,
)


@pytest.fixture
def make_pdf(tmp_path):
    """Helper fixture to create temporary multi-page test PDFs with fitz."""
    counter = 0

    def _create(
        pages_text: list[str],
        title: str = "Test Doc",
        filename: str | None = None,
    ) -> Path:
        nonlocal counter
        counter += 1
        name = filename or f"test_doc_{counter}.pdf"
        pdf_path = tmp_path / name
        doc = fitz.open()
        for text in pages_text:
            page = doc.new_page()
            if text:
                rect = fitz.Rect(50, 50, 500, 750)
                page.insert_textbox(rect, text)
        doc.set_metadata({"title": title, "author": "Test Author"})
        doc.save(str(pdf_path))
        doc.close()
        return pdf_path

    return _create


def test_sha256_calculation(tmp_path):
    """Verify SHA-256 calculation against Python hashlib standard."""
    dummy_file = tmp_path / "dummy.bin"
    content = b"The Relay - Research Assistant Assignment Stage 2.1"
    dummy_file.write_bytes(content)

    expected = hashlib.sha256(content).hexdigest()
    actual = compute_sha256(dummy_file)
    assert actual == expected


def test_missing_pdf_produces_clear_error():
    """Verify missing PDF produces FileNotFoundError with clear message."""
    missing_path = Path("papers/non_existent_paper_12345.pdf")
    with pytest.raises(FileNotFoundError, match="Source PDF does not exist"):
        extract_pdf(missing_path)


def test_small_pdf_extraction_and_1based_numbering(make_pdf):
    """Verify extraction from a small temporary PDF and 1-based page numbering."""
    pages = [
        "First page text: Neural networks and Transformers.",
        "Second page text: Multi-head attention mechanisms.",
        "Third page text: Empirical results and conclusions.",
    ]
    pdf_path = make_pdf(pages, title="Attention Mechanism Test")

    result = extract_pdf(
        pdf_path,
        paper_id="test.001v1",
        paper_title="Attention Mechanism Test",
        paper_version="v1",
    )

    assert result["paper_id"] == "test.001v1"
    assert result["paper_title"] == "Attention Mechanism Test"
    assert result["paper_version"] == "v1"
    assert result["total_pages"] == 3
    assert len(result["pages"]) == 3

    # Check 1-based human-readable numbering
    for idx, page in enumerate(result["pages"]):
        assert page["page_number"] == idx + 1
        assert page["paper_id"] == "test.001v1"
        assert page["character_count"] > 0
        assert page["extracted_text"] == page["text"]


def test_page_boundaries_preserved(make_pdf):
    """Verify that page boundaries are strictly preserved across pages."""
    unique_tokens = [
        "UNIQUE_TOKEN_PAGE_ALPHA_111",
        "UNIQUE_TOKEN_PAGE_BETA_222",
        "UNIQUE_TOKEN_PAGE_GAMMA_333",
    ]
    pdf_path = make_pdf(unique_tokens)

    result = extract_pdf(pdf_path)

    # Each unique token must appear ONLY in its respective page
    for i, token in enumerate(unique_tokens):
        page_text = result["pages"][i]["extracted_text"]
        assert token in page_text

        # Verify token does not leak to any other page
        for j, other_page in enumerate(result["pages"]):
            if j != i:
                assert token not in other_page["extracted_text"]


def test_unicode_text_preservation(make_pdf):
    """Verify unicode characters (accents, technical symbols, formulas) are preserved."""
    unicode_text = "Moshi dialogue: café, naïve, résumé — ± 10 dB & formula: x = y + z"
    pdf_path = make_pdf([unicode_text], title="Unicode Test")

    result = extract_pdf(pdf_path)
    extracted = result["pages"][0]["extracted_text"]

    assert "café" in extracted
    assert "naïve" in extracted
    assert "résumé" in extracted
    assert "formula: x = y + z" in extracted


def test_empty_and_low_text_warnings(make_pdf):
    """Verify warnings are recorded for empty and unusually low-text pages."""
    pages = [
        "A" * 300,  # Normal page (300 chars > threshold 100)
        "Short",    # Low text page (5 chars < threshold 100)
        "",         # Empty page (0 chars)
    ]
    pdf_path = make_pdf(pages)

    result = extract_pdf(pdf_path, low_text_threshold=100)

    # Page 1: normal, no warnings
    assert len(result["pages"][0]["warnings"]) == 0

    # Page 2: low text warning
    assert len(result["pages"][1]["warnings"]) == 1
    assert "unusually low extracted text" in result["pages"][1]["warnings"][0]

    # Page 3: empty page warning
    assert len(result["pages"][2]["warnings"]) == 1
    assert "is empty (0 characters extracted)" in result["pages"][2]["warnings"][0]

    # Document-level warnings must capture both
    assert len(result["warnings"]) == 2


def test_output_json_structure_and_readback(make_pdf, tmp_path):
    """Verify output JSON can be saved, read back, and matches the expected schema."""
    pdf_path = make_pdf(["Page 1 content", "Page 2 content"])
    doc_data = extract_pdf(
        pdf_path,
        paper_id="test.123v1",
        paper_title="Sample Test Paper",
        paper_version="v1",
        arxiv_id="test.123",
    )

    out_file = tmp_path / "test.123v1.json"
    saved_path = save_extracted_paper(doc_data, out_file)
    assert saved_path.exists()

    # Read back and validate JSON structure
    with open(saved_path, "r", encoding="utf-8") as f:
        loaded = json.load(f)

    # Document-level fields
    assert loaded["paper_id"] == "test.123v1"
    assert loaded["arxiv_id"] == "test.123"
    assert loaded["paper_version"] == "v1"
    assert loaded["paper_title"] == "Sample Test Paper"
    assert loaded["source_filename"] == pdf_path.name
    assert "sha256" in loaded
    assert loaded["total_pages"] == 2
    assert loaded["total_characters"] > 0
    assert "extraction_timestamp" in loaded
    assert "pdf_metadata" in loaded
    assert isinstance(loaded["warnings"], list)
    assert isinstance(loaded["pages"], list)
    assert len(loaded["pages"]) == 2

    # Page-level fields
    page0 = loaded["pages"][0]
    assert page0["page_number"] == 1
    assert page0["paper_id"] == "test.123v1"
    assert page0["character_count"] > 0
    assert "extracted_text" in page0
    assert "text" in page0
    assert isinstance(page0["warnings"], list)


def test_report_and_preview_generation(make_pdf, tmp_path):
    """Verify combined extraction report and text preview generation."""
    pdf1 = make_pdf(["Doc 1 text"], title="Doc 1")
    pdf2 = make_pdf(["Doc 2 page 1", "Doc 2 page 2"], title="Doc 2")

    doc1_data = extract_pdf(pdf1, paper_id="doc1", paper_title="Doc 1")
    doc2_data = extract_pdf(pdf2, paper_id="doc2", paper_title="Doc 2")

    report_path = tmp_path / "test_report.json"
    preview_path = tmp_path / "test_preview.txt"

    report = generate_extraction_report([doc1_data, doc2_data], report_path)
    assert report_path.exists()
    assert report["total_documents"] == 2
    assert report["total_pages"] == 3
    assert report["status"] == "success"
    assert len(report["documents"]) == 2

    preview = generate_preview([doc1_data, doc2_data], preview_path)
    assert preview.exists()
    preview_content = preview_path.read_text(encoding="utf-8")
    assert "THE RELAY — RESEARCH PAPERS EXTRACTION PREVIEW" in preview_content
    assert "Doc 1" in preview_content
    assert "Doc 2" in preview_content
