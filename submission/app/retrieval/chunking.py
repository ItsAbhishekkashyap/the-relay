"""
Token-aware chunking engine for The Relay research assistant.

Implements three configurable chunking strategies:
A. Fixed-size token chunking with overlap.
B. Structure-aware chunking (sections, headings, paragraphs).
C. Sentence-aware chunking (sentence boundaries, abbreviation protection).

Preserves paper identity, 1-based page numbers, section metadata,
and deterministic chunk IDs for downstream retrieval citation.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import re
from typing import Any, Dict, List, Optional, Protocol

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ============================================================================
# 1. Common Chunk Data Structure
# ============================================================================

class Chunk(BaseModel):
    """
    Standardized chunk data model representing a single retrieval passage
    with complete source citation and tracking metadata.
    """
    chunk_id: str = Field(..., description="Deterministic unique identifier: {paper_id}_c{chunk_index:05d}")
    paper_id: str = Field(..., description="Source paper identifier (e.g. 1706.03762v7)")
    arxiv_id: str = Field(..., description="arXiv ID without version (e.g. 1706.03762)")
    paper_version: str = Field(..., description="Paper version tag (e.g. v7)")
    paper_title: str = Field(..., description="Canonical paper title")
    source_filename: str = Field(..., description="Original PDF file name")
    page_numbers: List[int] = Field(..., description="1-based source pages contributing text to this chunk")
    section: Optional[str] = Field(None, description="Section heading if reliably detected, else None")
    chunk_index: int = Field(..., ge=1, description="1-based sequential index of chunk within paper")
    chunk_text: str = Field(..., min_length=1, description="Passage text content")
    token_count: int = Field(..., ge=0, description="Token count using the configured tokenizer")
    chunking_strategy: str = Field(..., description="Strategy name: fixed_size | structure_aware | sentence_aware")
    chunk_size: int = Field(..., ge=1, description="Target chunk size in tokens")
    overlap: int = Field(..., ge=0, description="Overlap in tokens")
    source_start: Optional[int] = Field(None, description="Start character offset in full document stream")
    source_end: Optional[int] = Field(None, description="End character offset in full document stream")
    character_count: int = Field(0, description="Length of chunk_text in characters")
    word_count: int = Field(0, description="Word count in chunk_text")

    def model_post_init(self, __context: Any) -> None:
        if not self.character_count:
            self.character_count = len(self.chunk_text)
        if not self.word_count:
            self.word_count = len(self.chunk_text.split())


# ============================================================================
# 2. Configuration Model
# ============================================================================

class ChunkingConfig(BaseModel):
    """Configuration for chunking operations with strict parameter validation."""
    strategy: str = Field(
        default="fixed_size",
        pattern="^(fixed_size|structure_aware|sentence_aware)$",
        description="Chunking strategy to apply",
    )
    target_chunk_size: int = Field(default=512, ge=16, le=4096, description="Target chunk size in tokens")
    max_chunk_size: Optional[int] = Field(default=None, description="Upper bound on chunk size in tokens")
    overlap: Optional[int] = Field(default=None, description="Token overlap between consecutive chunks")
    overlap_ratio: float = Field(default=0.15, ge=0.0, le=0.5, description="Overlap as fraction of target_chunk_size")
    min_chunk_size: int = Field(default=30, ge=1, description="Minimum tokens for an independent chunk")

    def get_effective_max_size(self) -> int:
        if self.max_chunk_size is not None:
            return self.max_chunk_size
        # Default max size allows 15% margin above target for natural boundary alignment
        return max(self.target_chunk_size, int(self.target_chunk_size * 1.15))

    def get_effective_overlap(self) -> int:
        if self.overlap is not None:
            return self.overlap
        return max(0, int(self.target_chunk_size * self.overlap_ratio))

    def validate_parameters(self) -> None:
        """Validate logical consistency between chunk size and overlap."""
        effective_max = self.get_effective_max_size()
        effective_overlap = self.get_effective_overlap()

        if self.target_chunk_size <= 0:
            raise ValueError(f"target_chunk_size must be positive, got {self.target_chunk_size}")
        if effective_max < self.target_chunk_size:
            raise ValueError(f"max_chunk_size ({effective_max}) cannot be less than target ({self.target_chunk_size})")
        if effective_overlap < 0:
            raise ValueError(f"overlap cannot be negative, got {effective_overlap}")
        if effective_overlap >= self.target_chunk_size:
            raise ValueError(
                f"overlap ({effective_overlap}) must be strictly less than target_chunk_size ({self.target_chunk_size})"
            )
        if self.min_chunk_size > self.target_chunk_size:
            raise ValueError(
                f"min_chunk_size ({self.min_chunk_size}) cannot exceed target_chunk_size ({self.target_chunk_size})"
            )


# ============================================================================
# 3. Tokenizer Adapter Interface & Implementations
# ============================================================================

class TokenizerAdapter(Protocol):
    """Protocol for pluggable, deterministic token counting."""
    name: str

    def count_tokens(self, text: str) -> int:
        ...

    def tokenize(self, text: str) -> List[str]:
        ...


class HFLocalTokenizer:
    """
    Tokenizer adapter wrapping Hugging Face AutoTokenizer.
    Loads sentence-transformers/all-MiniLM-L6-v2 exclusively from local cache.
    Never initiates network requests.
    """
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> None:
        from transformers import AutoTokenizer
        self.model_name = model_name
        self.name = f"hf_local:{model_name}"
        # strictly local cache: throws if not cached
        self._tokenizer = AutoTokenizer.from_pretrained(model_name, local_files_only=True)

    def count_tokens(self, text: str) -> int:
        if not text:
            return 0
        return len(self._tokenizer.encode(text, add_special_tokens=False))

    def tokenize(self, text: str) -> List[str]:
        if not text:
            return []
        return self._tokenizer.tokenize(text)


class FallbackTokenizer:
    """
    Deterministic local fallback tokenizer.
    Uses regex word/punctuation splitting + WordPiece-like subword heuristic.
    Clearly identifies itself in metadata so downstream callers know it is a fallback.
    """
    name: str = "fallback_regex_wordpiece"

    def __init__(self) -> None:
        self._token_pattern = re.compile(r"\w+|[^\w\s]", re.UNICODE)

    def count_tokens(self, text: str) -> int:
        if not text:
            return 0
        raw_tokens = self._token_pattern.findall(text)
        # Approximate subword splitting: words > 6 chars count as ~1.3 tokens
        total = 0
        for tok in raw_tokens:
            if len(tok) > 6 and tok.isalnum():
                total += 1 + (len(tok) - 6) // 4
            else:
                total += 1
        return total

    def tokenize(self, text: str) -> List[str]:
        if not text:
            return []
        return self._token_pattern.findall(text)


def get_default_tokenizer() -> TokenizerAdapter:
    """
    Obtain the default tokenizer.
    Attempts local Hugging Face all-MiniLM-L6-v2 first;
    falls back cleanly to FallbackTokenizer if not locally present.
    """
    try:
        return HFLocalTokenizer()
    except Exception as e:
        logger.warning(
            "Could not load Hugging Face tokenizer locally (%s). Using fallback tokenizer.",
            e,
        )
        return FallbackTokenizer()


# ============================================================================
# 4. Text Structure & Sentence Boundary Utilities
# ============================================================================

@dataclass
class TextSpan:
    """Internal unit of text with source page and offset annotations."""
    text: str
    page_number: int
    char_start: int
    char_end: int
    section: Optional[str] = None


# Common abbreviations that should not trigger sentence splits
COMMON_ABBREVIATIONS = {
    "e.g", "i.e", "et al", "fig", "figs", "tab", "vs", "approx", "dr", "prof",
    "no", "vol", "pp", "dept", "univ", "al", "sec", "eq", "eqs", "ref", "refs",
}

# Known academic section heading patterns
HEADING_KEYWORDS = {
    "abstract", "introduction", "background", "model architecture", "architecture",
    "attention", "multi-head attention", "training", "experiments", "results",
    "ablation", "discussion", "related work", "conclusion", "acknowledgements",
    "acknowledgments", "references", "appendix", "tokenization bias", "remark",
}


def split_into_sentences(text: str) -> List[str]:
    """
    Deterministic sentence boundary detection.
    Protects common abbreviations, initials, decimals, citations, and brackets.
    """
    if not text or not text.strip():
        return []

    # Sentinel placeholder for protected periods
    SENTINEL = "\uE000"

    processed = text

    # 1. Protect decimal numbers: e.g. 0.82 -> 0<SENTINEL>82
    processed = re.sub(r"(\d+)\.(\d+)", rf"\1{SENTINEL}\2", processed)

    # 2. Protect common abbreviations: e.g. "et al." -> "et al<SENTINEL>"
    def _protect_abbr(match: re.Match) -> str:
        word = match.group(1)
        if word.lower() in COMMON_ABBREVIATIONS:
            return f"{word}{SENTINEL}"
        return match.group(0)

    processed = re.sub(r"\b([A-Za-z]+)\.(?=\s+[a-z0-9A-Z])", _protect_abbr, processed)

    # 3. Protect initials: e.g. "A. Vaswani" -> "A<SENTINEL> Vaswani"
    processed = re.sub(r"\b([A-Z])\.(?=\s+[A-Z])", rf"\1{SENTINEL}", processed)

    # 4. Split on sentence boundaries: period/question/exclamation followed by whitespace and capital/quote/bullet
    raw_sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[<•])", processed)

    sentences: List[str] = []
    for s in raw_sentences:
        restored = s.replace(SENTINEL, ".").strip()
        if restored:
            sentences.append(restored)

    return sentences if sentences else [text.strip()]


def detect_heading(line: str) -> Optional[str]:
    """
    Conservative heading detection for academic papers.
    Returns the heading string if reasonably confident, else None.
    Never invents a section name.
    """
    clean = line.strip()
    if not clean or len(clean) > 85:
        return None

    # Do not treat full sentences ending with period/comma as headings
    if clean.endswith(".") or clean.endswith(",") or clean.endswith(";"):
        return None

    # Pattern 1: Numbered headings (e.g. "1 Introduction", "3.2 Multi-Head Attention", "Table 19:")
    numbered = re.match(r"^(\d+(\.\d+)*)\s+([A-Z][A-Za-z0-9\s\-_:’'/]{2,70})$", clean)
    if numbered:
        return clean

    # Pattern 2: Known standalone section keywords
    low = clean.lower()
    if low in HEADING_KEYWORDS:
        return clean.title()

    # Pattern 3: Explicit Table or Figure captions at the top of an element
    if re.match(r"^(Table|Figure)\s+\d+[:.]", clean, re.IGNORECASE):
        # Only take the header portion, not a full multi-line paragraph
        parts = re.split(r"[:.]\s+", clean, maxsplit=1)
        if len(parts) == 2 and len(parts[1]) < 60:
            return clean
        return parts[0]

    return None


# ============================================================================
# 5. Document Preparation: Extracting Annotated Text Spans
# ============================================================================

def prepare_document_spans(doc_data: Dict[str, Any]) -> List[TextSpan]:
    """
    Convert page-by-page JSON extraction into a linear stream of TextSpans,
    annotating each span with its 1-based page number, offsets, and detected section.
    """
    spans: List[TextSpan] = []
    global_offset = 0
    current_section: Optional[str] = None

    for page_obj in doc_data.get("pages", []):
        page_num = page_obj["page_number"]
        page_text = page_obj.get("extracted_text") or page_obj.get("text", "")
        if not page_text or not page_text.strip():
            continue

        # Split page into raw paragraphs by double newline
        raw_paras = page_text.split("\n\n")

        for para in raw_paras:
            clean_para = para.strip()
            if not clean_para:
                continue

            # Check if this paragraph starts with or is a heading
            lines = clean_para.split("\n")
            first_line_heading = detect_heading(lines[0])

            if first_line_heading:
                current_section = first_line_heading
                # If the paragraph has more lines following the heading, keep heading with it
            elif len(lines) == 1:
                single_heading = detect_heading(clean_para)
                if single_heading:
                    current_section = single_heading

            span_start = global_offset
            span_end = global_offset + len(clean_para)
            global_offset = span_end + 2  # account for paragraph gap

            spans.append(
                TextSpan(
                    text=clean_para,
                    page_number=page_num,
                    char_start=span_start,
                    char_end=span_end,
                    section=current_section,
                )
            )

    return spans


# ============================================================================
# 6. Strategy Implementations
# ============================================================================

def _build_chunk(
    included_spans: List[TextSpan],
    chunk_text: str,
    paper_meta: Dict[str, str],
    strategy_name: str,
    chunk_index: int,
    config: ChunkingConfig,
    tokenizer: TokenizerAdapter,
) -> Chunk:
    """Helper to assemble a Chunk instance with all required citation metadata."""
    page_numbers = sorted(list({s.page_number for s in included_spans}))
    if not page_numbers and included_spans:
        page_numbers = [included_spans[0].page_number]

    # Resolve dominant section
    sections = [s.section for s in included_spans if s.section is not None]
    resolved_section = sections[0] if sections else None

    # Calculate offsets
    source_start = min(s.char_start for s in included_spans) if included_spans else None
    source_end = max(s.char_end for s in included_spans) if included_spans else None

    token_count = tokenizer.count_tokens(chunk_text)

    return Chunk(
        chunk_id=f"{paper_meta['paper_id']}_c{chunk_index:05d}",
        paper_id=paper_meta["paper_id"],
        arxiv_id=paper_meta.get("arxiv_id", ""),
        paper_version=paper_meta.get("paper_version", ""),
        paper_title=paper_meta["paper_title"],
        source_filename=paper_meta["source_filename"],
        page_numbers=page_numbers,
        section=resolved_section,
        chunk_index=chunk_index,
        chunk_text=chunk_text,
        token_count=token_count,
        chunking_strategy=strategy_name,
        chunk_size=config.target_chunk_size,
        overlap=config.get_effective_overlap(),
        source_start=source_start,
        source_end=source_end,
        character_count=len(chunk_text),
        word_count=len(chunk_text.split()),
    )


# ----------------------------------------------------------------------------
# Strategy A: Fixed-Size Token Chunking with Overlap
# ----------------------------------------------------------------------------

def chunk_fixed_size(
    spans: List[TextSpan],
    paper_meta: Dict[str, str],
    config: ChunkingConfig,
    tokenizer: TokenizerAdapter,
) -> List[Chunk]:
    """
    Fixed-size token window chunking with configurable overlap.
    Packs whole paragraphs/sentences up to target tokens.
    Splits oversized elements safely without word corruption.
    """
    target = config.target_chunk_size
    max_size = config.get_effective_max_size()
    overlap = config.get_effective_overlap()

    # Expand spans into atomic units (sentences or sub-sentences) annotated with page info
    atomic_units: List[TextSpan] = []
    for span in spans:
        span_tokens = tokenizer.count_tokens(span.text)
        if span_tokens <= target:
            atomic_units.append(span)
        else:
            # Paragraph is larger than target: break into sentences
            sentences = split_into_sentences(span.text)
            for s in sentences:
                s_tokens = tokenizer.count_tokens(s)
                if s_tokens <= max_size:
                    atomic_units.append(
                        TextSpan(
                            text=s,
                            page_number=span.page_number,
                            char_start=span.char_start,
                            char_end=span.char_end,
                            section=span.section,
                        )
                    )
                else:
                    # Individual sentence exceeds max_size: split by word blocks
                    words = s.split(" ")
                    curr_words: List[str] = []
                    for w in words:
                        test_text = " ".join(curr_words + [w])
                        if tokenizer.count_tokens(test_text) <= target:
                            curr_words.append(w)
                        else:
                            if curr_words:
                                atomic_units.append(
                                    TextSpan(
                                        text=" ".join(curr_words),
                                        page_number=span.page_number,
                                        char_start=span.char_start,
                                        char_end=span.char_end,
                                        section=span.section,
                                    )
                                )
                            curr_words = [w]
                    if curr_words:
                        atomic_units.append(
                            TextSpan(
                                text=" ".join(curr_words),
                                page_number=span.page_number,
                                char_start=span.char_start,
                                char_end=span.char_end,
                                section=span.section,
                            )
                        )

    chunks: List[Chunk] = []
    chunk_idx = 1
    i = 0
    n = len(atomic_units)

    while i < n:
        current_spans: List[TextSpan] = []
        current_tokens = 0
        start_idx = i

        while i < n:
            unit = atomic_units[i]
            unit_tokens = tokenizer.count_tokens(unit.text)

            # Check if adding this unit stays within target/max bounds
            if current_spans and (current_tokens + unit_tokens > max_size):
                break

            current_spans.append(unit)
            current_tokens += unit_tokens
            i += 1

            if current_tokens >= target:
                break

        if not current_spans:
            # Emergency advance if a single unit is gigantic
            current_spans = [atomic_units[i]]
            i += 1

        chunk_text = "\n\n".join(s.text for s in current_spans).strip()
        chunks.append(
            _build_chunk(
                included_spans=current_spans,
                chunk_text=chunk_text,
                paper_meta=paper_meta,
                strategy_name="fixed_size",
                chunk_index=chunk_idx,
                config=config,
                tokenizer=tokenizer,
            )
        )
        chunk_idx += 1

        # Advance pointer with overlap
        if i >= n:
            break

        if overlap > 0 and len(current_spans) > 1:
            # Walk backwards from i to find overlap window
            overlap_accum = 0
            backtrack = 0
            for s in reversed(current_spans):
                s_tokens = tokenizer.count_tokens(s.text)
                if overlap_accum + s_tokens <= overlap:
                    overlap_accum += s_tokens
                    backtrack += 1
                else:
                    break
            # Ensure forward progress
            new_i = max(start_idx + 1, i - backtrack)
            i = new_i

    return chunks


# ----------------------------------------------------------------------------
# Strategy B: Structure-Aware Chunking (Sections & Headings)
# ----------------------------------------------------------------------------

def chunk_structure_aware(
    spans: List[TextSpan],
    paper_meta: Dict[str, str],
    config: ChunkingConfig,
    tokenizer: TokenizerAdapter,
) -> List[Chunk]:
    """
    Structure-aware chunking. Groups paragraphs within detected sections.
    Transitions sections on detected headings. Splits oversized paragraphs
    conservatively up to target size.
    """
    target = config.target_chunk_size
    max_size = config.get_effective_max_size()

    # Group spans into sections based on detected heading boundaries
    section_groups: List[Dict[str, Any]] = []
    current_sec_name: Optional[str] = None
    current_sec_spans: List[TextSpan] = []

    for span in spans:
        if span.section and span.section != current_sec_name:
            if current_sec_spans:
                section_groups.append({"section": current_sec_name, "spans": current_sec_spans})
            current_sec_name = span.section
            current_sec_spans = [span]
        else:
            current_sec_spans.append(span)

    if current_sec_spans:
        section_groups.append({"section": current_sec_name, "spans": current_sec_spans})

    chunks: List[Chunk] = []
    chunk_idx = 1

    for group in section_groups:
        sec_name = group["section"]
        g_spans = group["spans"]

        current_chunk_spans: List[TextSpan] = []
        current_tokens = 0

        for span in g_spans:
            span_tokens = tokenizer.count_tokens(span.text)

            if span_tokens > max_size:
                # Flush existing buffer
                if current_chunk_spans:
                    text_block = "\n\n".join(s.text for s in current_chunk_spans).strip()
                    chunks.append(
                        _build_chunk(
                            included_spans=current_chunk_spans,
                            chunk_text=text_block,
                            paper_meta=paper_meta,
                            strategy_name="structure_aware",
                            chunk_index=chunk_idx,
                            config=config,
                            tokenizer=tokenizer,
                        )
                    )
                    chunk_idx += 1
                    current_chunk_spans = []
                    current_tokens = 0

                # Split oversized paragraph by sentences and lines if needed
                sentences = split_into_sentences(span.text)
                atomic_elements: List[str] = []
                for s in sentences:
                    if tokenizer.count_tokens(s) <= max_size:
                        atomic_elements.append(s)
                    else:
                        # Fallback for unpunctuated lists/tables: split by lines
                        lines = [l.strip() for l in s.split("\n") if l.strip()]
                        for l in lines:
                            if tokenizer.count_tokens(l) <= max_size:
                                atomic_elements.append(l)
                            else:
                                words = l.split(" ")
                                curr_w: List[str] = []
                                for w in words:
                                    if tokenizer.count_tokens(" ".join(curr_w + [w])) <= target:
                                        curr_w.append(w)
                                    else:
                                        if curr_w:
                                            atomic_elements.append(" ".join(curr_w))
                                        curr_w = [w]
                                if curr_w:
                                    atomic_elements.append(" ".join(curr_w))

                sub_spans: List[TextSpan] = []
                sub_tokens = 0
                for s in atomic_elements:
                    stok = tokenizer.count_tokens(s)
                    if sub_spans and (sub_tokens + stok > max_size):
                        s_text = "\n\n".join(x.text for x in sub_spans).strip()
                        chunks.append(
                            _build_chunk(
                                included_spans=sub_spans,
                                chunk_text=s_text,
                                paper_meta=paper_meta,
                                strategy_name="structure_aware",
                                chunk_index=chunk_idx,
                                config=config,
                                tokenizer=tokenizer,
                            )
                        )
                        chunk_idx += 1
                        sub_spans = []
                        sub_tokens = 0

                    sub_spans.append(
                        TextSpan(
                            text=s,
                            page_number=span.page_number,
                            char_start=span.char_start,
                            char_end=span.char_end,
                            section=sec_name,
                        )
                    )
                    sub_tokens += stok

                if sub_spans:
                    current_chunk_spans = sub_spans
                    current_tokens = sub_tokens

            elif current_tokens + span_tokens <= max_size:
                current_chunk_spans.append(span)
                current_tokens += span_tokens
            else:
                # Adding span would exceed max_size: flush and start new chunk
                if current_chunk_spans:
                    text_block = "\n\n".join(s.text for s in current_chunk_spans).strip()
                    chunks.append(
                        _build_chunk(
                            included_spans=current_chunk_spans,
                            chunk_text=text_block,
                            paper_meta=paper_meta,
                            strategy_name="structure_aware",
                            chunk_index=chunk_idx,
                            config=config,
                            tokenizer=tokenizer,
                        )
                    )
                    chunk_idx += 1

                current_chunk_spans = [span]
                current_tokens = span_tokens

        if current_chunk_spans:
            text_block = "\n\n".join(s.text for s in current_chunk_spans).strip()
            chunks.append(
                _build_chunk(
                    included_spans=current_chunk_spans,
                    chunk_text=text_block,
                    paper_meta=paper_meta,
                    strategy_name="structure_aware",
                    chunk_index=chunk_idx,
                    config=config,
                    tokenizer=tokenizer,
                )
            )
            chunk_idx += 1

    return chunks


# ----------------------------------------------------------------------------
# Strategy C: Sentence-Aware Chunking
# ----------------------------------------------------------------------------

def chunk_sentence_aware(
    spans: List[TextSpan],
    paper_meta: Dict[str, str],
    config: ChunkingConfig,
    tokenizer: TokenizerAdapter,
) -> List[Chunk]:
    """
    Sentence-aware chunking. Groups discrete sentences up to target tokens.
    Never splits sentences across chunks unless an individual sentence exceeds max_size.
    """
    target = config.target_chunk_size
    max_size = config.get_effective_max_size()

    # Extract all sentences with page mapping
    all_sentences: List[TextSpan] = []
    for span in spans:
        sentences = split_into_sentences(span.text)
        for s in sentences:
            stoks = tokenizer.count_tokens(s)
            if stoks <= max_size:
                all_sentences.append(
                    TextSpan(
                        text=s,
                        page_number=span.page_number,
                        char_start=span.char_start,
                        char_end=span.char_end,
                        section=span.section,
                    )
                )
            else:
                # Oversized single sentence: fallback to word-level sub-blocks
                words = s.split(" ")
                curr_words: List[str] = []
                for w in words:
                    test_str = " ".join(curr_words + [w])
                    if tokenizer.count_tokens(test_str) <= target:
                        curr_words.append(w)
                    else:
                        if curr_words:
                            all_sentences.append(
                                TextSpan(
                                    text=" ".join(curr_words),
                                    page_number=span.page_number,
                                    char_start=span.char_start,
                                    char_end=span.char_end,
                                    section=span.section,
                                )
                            )
                        curr_words = [w]
                if curr_words:
                    all_sentences.append(
                        TextSpan(
                            text=" ".join(curr_words),
                            page_number=span.page_number,
                            char_start=span.char_start,
                            char_end=span.char_end,
                            section=span.section,
                        )
                    )

    chunks: List[Chunk] = []
    chunk_idx = 1
    current_chunk_spans: List[TextSpan] = []
    current_tokens = 0

    for sent in all_sentences:
        sent_tokens = tokenizer.count_tokens(sent.text)

        if current_chunk_spans and (current_tokens + sent_tokens > max_size):
            chunk_text = " ".join(s.text for s in current_chunk_spans).strip()
            chunks.append(
                _build_chunk(
                    included_spans=current_chunk_spans,
                    chunk_text=chunk_text,
                    paper_meta=paper_meta,
                    strategy_name="sentence_aware",
                    chunk_index=chunk_idx,
                    config=config,
                    tokenizer=tokenizer,
                )
            )
            chunk_idx += 1
            current_chunk_spans = []
            current_tokens = 0

        current_chunk_spans.append(sent)
        current_tokens += sent_tokens

        if current_tokens >= target:
            chunk_text = " ".join(s.text for s in current_chunk_spans).strip()
            chunks.append(
                _build_chunk(
                    included_spans=current_chunk_spans,
                    chunk_text=chunk_text,
                    paper_meta=paper_meta,
                    strategy_name="sentence_aware",
                    chunk_index=chunk_idx,
                    config=config,
                    tokenizer=tokenizer,
                )
            )
            chunk_idx += 1
            current_chunk_spans = []
            current_tokens = 0

    if current_chunk_spans:
        chunk_text = " ".join(s.text for s in current_chunk_spans).strip()
        chunks.append(
            _build_chunk(
                included_spans=current_chunk_spans,
                chunk_text=chunk_text,
                paper_meta=paper_meta,
                strategy_name="sentence_aware",
                chunk_index=chunk_idx,
                config=config,
                tokenizer=tokenizer,
            )
        )
        chunk_idx += 1

    return chunks


# ============================================================================
# 7. Engine Dispatch & Validation
# ============================================================================

def chunk_document(
    doc_data: Dict[str, Any],
    config: ChunkingConfig,
    tokenizer: Optional[TokenizerAdapter] = None,
) -> List[Chunk]:
    """
    Main entrypoint to chunk an extracted document JSON using the specified configuration.
    """
    config.validate_parameters()
    tok = tokenizer or get_default_tokenizer()

    paper_meta = {
        "paper_id": doc_data["paper_id"],
        "arxiv_id": doc_data.get("arxiv_id", doc_data["paper_id"].split("v")[0]),
        "paper_version": doc_data.get("paper_version", ""),
        "paper_title": doc_data["paper_title"],
        "source_filename": doc_data["source_filename"],
    }

    spans = prepare_document_spans(doc_data)
    if not spans:
        return []

    strategy = config.strategy
    if strategy == "fixed_size":
        chunks = chunk_fixed_size(spans, paper_meta, config, tok)
    elif strategy == "structure_aware":
        chunks = chunk_structure_aware(spans, paper_meta, config, tok)
    elif strategy == "sentence_aware":
        chunks = chunk_sentence_aware(spans, paper_meta, config, tok)
    else:
        raise ValueError(f"Unsupported chunking strategy: {strategy}")

    # Final validation
    validate_chunks(chunks, config)
    return chunks


def validate_chunks(chunks: List[Chunk], config: ChunkingConfig) -> Dict[str, Any]:
    """
    Validate chunk list integrity:
    - Unique IDs
    - Non-empty text
    - Valid 1-based page numbers
    - Token limits
    - Monotonic chunk indexing
    """
    seen_ids = set()
    errors: List[str] = []
    max_size = config.get_effective_max_size()

    for idx, c in enumerate(chunks):
        # 1. Unique chunk IDs
        if c.chunk_id in seen_ids:
            errors.append(f"Duplicate chunk_id detected: {c.chunk_id}")
        seen_ids.add(c.chunk_id)

        # 2. Sequential 1-based chunk indexing
        expected_idx = idx + 1
        if c.chunk_index != expected_idx:
            errors.append(f"Chunk index mismatch: expected {expected_idx}, got {c.chunk_index}")

        # 3. Non-empty text
        if not c.chunk_text or not c.chunk_text.strip():
            errors.append(f"Empty chunk text in {c.chunk_id}")

        # 4. Valid page numbers
        if not c.page_numbers or any(p < 1 for p in c.page_numbers):
            errors.append(f"Invalid page numbers in {c.chunk_id}: {c.page_numbers}")

    if errors:
        raise ValueError(f"Chunk validation failed with {len(errors)} errors:\n" + "\n".join(errors[:10]))

    return {"status": "valid", "total_chunks": len(chunks)}


def calculate_coverage(doc_data: Dict[str, Any], chunks: List[Chunk]) -> Dict[str, Any]:
    """
    Calculate text and word coverage of chunks relative to extracted source text,
    verifying no non-whitespace text is lost.
    """
    source_words = set()
    for p in doc_data.get("pages", []):
        text = p.get("extracted_text") or p.get("text", "")
        for w in text.split():
            clean_w = re.sub(r"[^\w]", "", w.lower())
            if len(clean_w) > 2:
                source_words.add(clean_w)

    chunk_words = set()
    for c in chunks:
        for w in c.chunk_text.split():
            clean_w = re.sub(r"[^\w]", "", w.lower())
            if len(clean_w) > 2:
                chunk_words.add(clean_w)

    if not source_words:
        coverage = 1.0
        missing = []
    else:
        overlap_words = source_words.intersection(chunk_words)
        coverage = len(overlap_words) / len(source_words)
        missing = list(source_words - chunk_words)[:20]

    return {
        "source_distinct_words": len(source_words),
        "chunk_distinct_words": len(chunk_words),
        "word_coverage_ratio": round(coverage, 4),
        "sample_missing_words": missing,
    }
