"""
Unit and integration tests for Task 2.2: Token-aware Chunking Engine.

Tests:
- Parameter validation (invalid size, negative overlap, overlap >= size)
- Fixed-size chunking limits and token overlap
- Sentence-aware boundary detection with abbreviation and decimal protection
- Structure-aware heading detection and section grouping
- Multi-page spanning chunk page_numbers tracking
- Strict isolation (no cross-paper chunk mixing)
- Deterministic chunk IDs across repeated runs
- Empty document handling
- Oversized sentence and paragraph safe windowing
- Preservation of technical tokens (<EOS>, <pad>, hex bytes, math symbols, Unicode)
- Text coverage verification (no silent text loss)
- Chunk metadata integrity validation function
"""

from pathlib import Path
import sys
import pytest

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.retrieval.chunking import (
    Chunk,
    ChunkingConfig,
    FallbackTokenizer,
    calculate_coverage,
    chunk_document,
    chunk_fixed_size,
    chunk_sentence_aware,
    chunk_structure_aware,
    detect_heading,
    get_default_tokenizer,
    prepare_document_spans,
    split_into_sentences,
    validate_chunks,
)


@pytest.fixture
def tokenizer():
    """Deterministic local tokenizer for testing."""
    return get_default_tokenizer()


@pytest.fixture
def sample_doc_data():
    """Synthetic multi-page research document fixture."""
    return {
        "paper_id": "test.001v1",
        "arxiv_id": "test.001",
        "paper_version": "v1",
        "paper_title": "Synthetic Attention and Dynamic Chunking",
        "source_filename": "test.001v1.pdf",
        "total_pages": 3,
        "pages": [
            {
                "page_number": 1,
                "extracted_text": (
                    "Abstract\n"
                    "We introduce a novel transformer sequence model. The architecture uses self-attention.\n\n"
                    "1 Introduction\n"
                    "Recent advancements in deep learning, e.g. language modeling, show great promise. "
                    "Ashish Vaswani et al. 2017 established the Transformer foundation. "
                    "We train on 40B tokens at 0.82 bits-per-byte with learning rate 3.5e-4.\n\n"
                    "The model uses special tokens <EOS> and <pad> for sequence termination."
                ),
            },
            {
                "page_number": 2,
                "extracted_text": (
                    "2 Model Architecture\n"
                    "The model contains an encoder and a decoder stack. "
                    "We evaluate configurations: T2-T2, M4-M4, and T1M2-M2T1. "
                    "Mathematical parameter budget scales as 12D^2 vs. ≈6D^2.\n\n"
                    "Hexadecimal byte sequence visualization: 28 69 69 29 20 46 61 73 74 20. "
                    "Moshi dialogue supports café, naïve accents and résumé styles."
                ),
            },
            {
                "page_number": 3,
                "extracted_text": (
                    "3 Results and Conclusion\n"
                    "Our experimental results show superior performance over baselines. "
                    "We thank the team for valuable feedback.\n\n"
                    "References\n"
                    "[1] Vaswani et al. Attention Is All You Need. NIPS 2017.\n"
                    "[2] Defossez et al. Moshi Speech-Text Foundation Model. 2024."
                ),
            },
        ],
    }


# ============================================================================
# 1. Parameter Validation Tests
# ============================================================================

def test_invalid_configuration_parameters():
    """Verify that invalid chunking parameters are rejected with clear ValueErrors."""
    # Target chunk size <= 0
    with pytest.raises(ValueError):
        c = ChunkingConfig(target_chunk_size=0)
        c.validate_parameters()

    # Overlap >= target_chunk_size
    with pytest.raises(ValueError, match="strictly less than"):
        c = ChunkingConfig(target_chunk_size=100, overlap=100)
        c.validate_parameters()

    # Negative overlap
    with pytest.raises(ValueError, match="cannot be negative"):
        c = ChunkingConfig(target_chunk_size=100, overlap=-10)
        c.validate_parameters()

    # Max size < target size
    with pytest.raises(ValueError, match="cannot be less than target"):
        c = ChunkingConfig(target_chunk_size=200, max_chunk_size=150)
        c.validate_parameters()

    # Min size > target size
    with pytest.raises(ValueError, match="cannot exceed target_chunk_size"):
        c = ChunkingConfig(target_chunk_size=100, min_chunk_size=150)
        c.validate_parameters()


# ============================================================================
# 2. Fixed-Size Strategy Tests
# ============================================================================

def test_fixed_size_chunk_limits_and_overlap(sample_doc_data, tokenizer):
    """Verify fixed-size chunking respects target limits and produces token overlap."""
    config = ChunkingConfig(
        strategy="fixed_size",
        target_chunk_size=50,
        max_chunk_size=65,
        overlap=15,
        min_chunk_size=10,
    )
    chunks = chunk_document(sample_doc_data, config, tokenizer=tokenizer)

    assert len(chunks) > 1
    for c in chunks:
        assert c.chunking_strategy == "fixed_size"
        assert c.token_count <= config.get_effective_max_size()
        assert c.token_count > 0

    # Verify consecutive chunks share overlap tokens
    found_overlap = False
    for i in range(len(chunks) - 1):
        words_curr = set(chunks[i].chunk_text.split()[-10:])
        words_next = set(chunks[i + 1].chunk_text.split()[:10])
        if words_curr.intersection(words_next):
            found_overlap = True
            break
    assert found_overlap, "Consecutive fixed-size chunks must share boundary words/tokens"


# ============================================================================
# 3. Sentence Boundary & Abbreviation Handling Tests
# ============================================================================

def test_sentence_splitting_and_abbreviations():
    """Verify sentence boundary detection protects abbreviations, decimals, and initials."""
    sample = (
        "Ashish Vaswani et al. introduced the Transformer. "
        "The model achieves 28.4 BLEU on English-to-German, e.g. surpassing ConvS2S. "
        "We also evaluated Fig. 3 and Tab. 10 at 0.82 bits-per-byte! "
        "Does H-Net work without spaces? Yes, it does."
    )
    sentences = split_into_sentences(sample)

    # Must split into exactly 5 sentences
    assert len(sentences) == 5
    assert "et al." in sentences[0]
    assert "28.4 BLEU" in sentences[1]
    assert "e.g." in sentences[1]
    assert "Fig. 3" in sentences[2]
    assert "0.82 bits-per-byte" in sentences[2]
    assert "Does H-Net work without spaces?" in sentences[3]
    assert "Yes, it does." in sentences[4]


def test_sentence_aware_chunking(sample_doc_data, tokenizer):
    """Verify sentence-aware strategy preserves full sentences."""
    config = ChunkingConfig(
        strategy="sentence_aware",
        target_chunk_size=60,
        max_chunk_size=75,
    )
    chunks = chunk_document(sample_doc_data, config, tokenizer=tokenizer)

    assert len(chunks) > 0
    for c in chunks:
        assert c.chunking_strategy == "sentence_aware"
        assert c.token_count <= config.get_effective_max_size()
        # Verify text ends in sentence punctuation or natural block boundary
        assert c.chunk_text[-1] in ".!?:)\"\']>" or c.chunk_text.endswith("2024.")


# ============================================================================
# 4. Structure-Aware Heading & Section Detection Tests
# ============================================================================

def test_heading_detection():
    """Verify conservative heading detector recognizes sections without false positives."""
    # Positive headings
    assert detect_heading("1 Introduction") == "1 Introduction"
    assert detect_heading("3.2 Multi-Head Attention") == "3.2 Multi-Head Attention"
    assert detect_heading("Abstract") == "Abstract"
    assert detect_heading("References") == "References"
    assert detect_heading("Table 19: Speaking styles") == "Table 19: Speaking styles"

    # Negative non-headings (prose sentences)
    assert detect_heading("This is an ordinary sentence describing the method.") is None
    assert detect_heading("We evaluate four encoder-decoder configurations.") is None
    assert detect_heading("A" * 120) is None  # Too long


def test_structure_aware_chunking(sample_doc_data, tokenizer):
    """Verify structure-aware strategy assigns detected headings to chunks."""
    config = ChunkingConfig(
        strategy="structure_aware",
        target_chunk_size=100,
        max_chunk_size=120,
    )
    chunks = chunk_document(sample_doc_data, config, tokenizer=tokenizer)

    assert len(chunks) > 0
    sections_found = {c.section for c in chunks if c.section is not None}
    assert "Abstract" in sections_found or "1 Introduction" in sections_found
    for c in chunks:
        assert c.chunking_strategy == "structure_aware"


# ============================================================================
# 5. Page Boundaries, Spanning, and Isolation Tests
# ============================================================================

def test_page_spanning_chunk_page_numbers(tokenizer):
    """Verify that chunks spanning adjacent pages accurately record all source pages."""
    doc = {
        "paper_id": "span.doc",
        "arxiv_id": "span.001",
        "paper_version": "v1",
        "paper_title": "Page Spanning Test",
        "source_filename": "span.pdf",
        "total_pages": 2,
        "pages": [
            {"page_number": 1, "extracted_text": "Short page one text."},
            {"page_number": 2, "extracted_text": "Short page two text continuing the topic."},
        ],
    }
    # Large chunk size so text from both page 1 and page 2 fits into one chunk
    config = ChunkingConfig(strategy="fixed_size", target_chunk_size=200)
    chunks = chunk_document(doc, config, tokenizer=tokenizer)

    assert len(chunks) == 1
    # Chunk must represent both pages
    assert chunks[0].page_numbers == [1, 2]


def test_no_cross_paper_chunk_mixing(sample_doc_data, tokenizer):
    """Verify that chunking strictly prevents mixing passages across different papers."""
    doc_b = dict(sample_doc_data)
    doc_b["paper_id"] = "paper_B_v1"
    doc_b["source_filename"] = "paper_B.pdf"

    config = ChunkingConfig(strategy="sentence_aware", target_chunk_size=80)

    chunks_a = chunk_document(sample_doc_data, config, tokenizer=tokenizer)
    chunks_b = chunk_document(doc_b, config, tokenizer=tokenizer)

    for c in chunks_a:
        assert c.paper_id == "test.001v1"
        assert c.source_filename == "test.001v1.pdf"

    for c in chunks_b:
        assert c.paper_id == "paper_B_v1"
        assert c.source_filename == "paper_B.pdf"


# ============================================================================
# 6. Determinism, Empty Inputs & Oversized Handling
# ============================================================================

def test_deterministic_chunk_ids_across_repeated_runs(sample_doc_data, tokenizer):
    """Verify chunk IDs and text are 100% deterministic across repeated invocations."""
    config = ChunkingConfig(strategy="fixed_size", target_chunk_size=80, overlap=10)

    run_1 = chunk_document(sample_doc_data, config, tokenizer=tokenizer)
    run_2 = chunk_document(sample_doc_data, config, tokenizer=tokenizer)

    assert len(run_1) == len(run_2)
    for c1, c2 in zip(run_1, run_2):
        assert c1.chunk_id == c2.chunk_id
        assert c1.chunk_text == c2.chunk_text
        assert c1.token_count == c2.token_count
        assert c1.page_numbers == c2.page_numbers


def test_empty_input_handling(tokenizer):
    """Verify empty pages or document produces empty chunk list without crashing."""
    empty_doc = {
        "paper_id": "empty.doc",
        "arxiv_id": "empty",
        "paper_version": "v1",
        "paper_title": "Empty Document",
        "source_filename": "empty.pdf",
        "total_pages": 1,
        "pages": [{"page_number": 1, "extracted_text": ""}],
    }
    config = ChunkingConfig(strategy="structure_aware", target_chunk_size=100)
    chunks = chunk_document(empty_doc, config, tokenizer=tokenizer)
    assert chunks == []


def test_oversized_sentence_handling(tokenizer):
    """Verify that a gigantic sentence exceeding max_size is safely windowed without token loss."""
    giant_sentence = " ".join([f"word{i}" for i in range(400)]) + "."
    doc = {
        "paper_id": "giant.doc",
        "arxiv_id": "giant",
        "paper_version": "v1",
        "paper_title": "Giant Sentence Document",
        "source_filename": "giant.pdf",
        "total_pages": 1,
        "pages": [{"page_number": 1, "extracted_text": giant_sentence}],
    }
    config = ChunkingConfig(
        strategy="sentence_aware",
        target_chunk_size=100,
        max_chunk_size=120,
    )
    chunks = chunk_document(doc, config, tokenizer=tokenizer)

    assert len(chunks) > 1
    for c in chunks:
        assert c.token_count <= config.get_effective_max_size()

    # Verify coverage
    all_words = set(giant_sentence.replace(".", "").split())
    chunked_words = set(" ".join(c.chunk_text for c in chunks).replace(".", "").split())
    assert all_words == chunked_words


# ============================================================================
# 7. Preservation of Technical Notation, Hex Bytes, and Unicode
# ============================================================================

def test_preservation_of_technical_notation_and_unicode(tokenizer):
    """Verify that mathematical expressions, hex bytes, and special tokens are intact."""
    technical_text = (
        "Special tokens: <EOS> and <pad>.\n\n"
        "Hex bytes: 28 69 69 29 20 46 61 73 74 20.\n\n"
        "Math: 12D^2 vs. ≈6D^2 and E0 − D0.\n\n"
        "Unicode: café, naïve, résumé, and model: SpaceByte++."
    )
    doc = {
        "paper_id": "tech.doc",
        "arxiv_id": "tech",
        "paper_version": "v1",
        "paper_title": "Technical Preservation Document",
        "source_filename": "tech.pdf",
        "total_pages": 1,
        "pages": [{"page_number": 1, "extracted_text": technical_text}],
    }
    config = ChunkingConfig(strategy="structure_aware", target_chunk_size=200)
    chunks = chunk_document(doc, config, tokenizer=tokenizer)

    combined_output = "\n".join(c.chunk_text for c in chunks)
    assert "<EOS>" in combined_output
    assert "<pad>" in combined_output
    assert "28 69 69 29" in combined_output
    assert "12D^2" in combined_output
    assert "≈6D^2" in combined_output
    assert "café" in combined_output
    assert "naïve" in combined_output
    assert "résumé" in combined_output
    assert "SpaceByte++" in combined_output


# ============================================================================
# 8. Text Coverage & Quality Validation Function Tests
# ============================================================================

def test_coverage_and_no_silent_loss(sample_doc_data, tokenizer):
    """Verify calculate_coverage confirms all distinct words are preserved."""
    config = ChunkingConfig(strategy="fixed_size", target_chunk_size=100, overlap=15)
    chunks = chunk_document(sample_doc_data, config, tokenizer=tokenizer)

    coverage = calculate_coverage(sample_doc_data, chunks)
    assert coverage["word_coverage_ratio"] == 1.0
    assert len(coverage["sample_missing_words"]) == 0


def test_chunk_validation_catches_integrity_errors(sample_doc_data, tokenizer):
    """Verify validate_chunks detects duplicate IDs or invalid metadata."""
    config = ChunkingConfig(strategy="sentence_aware", target_chunk_size=100)
    chunks = chunk_document(sample_doc_data, config, tokenizer=tokenizer)

    # Valid chunks pass
    report = validate_chunks(chunks, config)
    assert report["status"] == "valid"

    # Corrupt chunk_id (duplicate)
    corrupted_dup = [c.model_copy() for c in chunks]
    corrupted_dup[1].chunk_id = corrupted_dup[0].chunk_id
    with pytest.raises(ValueError, match="Duplicate chunk_id"):
        validate_chunks(corrupted_dup, config)

    # Corrupt page number (invalid 0)
    corrupted_page = [c.model_copy() for c in chunks]
    corrupted_page[0].page_numbers = [0]
    with pytest.raises(ValueError, match="Invalid page numbers"):
        validate_chunks(corrupted_page, config)
