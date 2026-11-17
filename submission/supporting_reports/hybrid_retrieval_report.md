# The Relay: Stage 2.4 Hybrid Retrieval Engine Report

**Project:** The Relay — Vaani Research ML Engineering Assignment  
**Stage:** 2.4 — Hybrid Retrieval Engine  
**Status:** Completed & Fully Verified  
**Date:** November 2026  
**Environment:** Python 3.12.0 (Windows 11, local Intel/AMD CPU, no remote GPU/API calls)

---

## 1. Architecture & Multi-Modal Data Flow

The hybrid retrieval engine provides traceable, evidence-grounded information retrieval exclusively from the three approved arXiv research papers:
1. `1706.03762v7.pdf`: *Attention Is All You Need*
2. `2410.00037v1.pdf`: *Moshi: A Speech-Text Foundation Model for Real-Time Dialogue*
3. `2507.07955v2.pdf`: *Dynamic Chunking for End-to-End Hierarchical Sequence Modeling*

### Retrieval Channels

The retrieval layer integrates three distinct search modalities combined via Reciprocal Rank Fusion (RRF):

```
                                  +-----------------------+
                                  |      User Query       |
                                  +-----------+-----------+
                                              |
                   +--------------------------+--------------------------+
                   |                          |                          |
                   v                          v                          v
       +-----------------------+  +-----------------------+  +-----------------------+
       |   Dense Retriever     |  |     BM25 Retriever    |  |  Structured FactStore |
       |  (ChromaDB + MiniLM)  |  |      (rank-bm25)      |  |    (SQLite + FTS5)    |
       +-----------+-----------+  +-----------+-----------+  +-----------+-----------+
                   |                          |                          |
          Top-K Dense Hits           Top-K Keyword Hits          Top-K Fact/Table Hits
          (Cosine Distance)             (BM25 Score)              (Exact / FTS Match)
                   |                          |                          |
                   +--------------------------+--------------------------+
                                              |
                                              v
                              +-------------------------------+
                              | Reciprocal Rank Fusion (RRF)  |
                              |  - Deduplication by chunk_id  |
                              |  - Score accumulation        |
                              |  - Provenance enrichment      |
                              +---------------+---------------+
                                              |
                                              v
                              +-------------------------------+
                              |    Ranked Hybrid Evidence     |
                              +-------------------------------+
```

1. **Dense Vector Retrieval (`DenseRetriever`):** Captures semantic concepts, paraphrases, and high-level architectural relationships using local dense embeddings.
2. **Keyword Retrieval (`BM25Retriever`):** Captures exact technical terminology, abbreviations, and rare tokens (e.g., `d_model`, `RQ-Transformer`, `bleu`, `wer`).
3. **Structured Fact Store (`FactStore`):** Stores verbatim tables, metrics, formulas, and tabular Markdown in SQLite. Enables exact substring matching on numeric parameters (e.g., `"28.4"`, `"160ms"`) and full-text keyword indexing via SQLite FTS5.
4. **Reciprocal Rank Fusion (`HybridRetriever`):** Combines candidate rankings across active channels, naturally boosting chunks supported by multiple retrieval modalities while ensuring complete provenance.

---

## 2. Indexing Statistics & Specifications

### Corpus Counts
- **Total Input Chunks:** 402 chunks (derived from 265 ingested documents across 120 source PDF pages).
- **Approved Dataset Source:** `data/chunks/langchain_recursive/` (`1706.03762v7.json`, `2410.00037v1.json`, `2507.07955v2.json`).

| Paper ID | ArXiv ID | Title | Chunks Indexed | Fact / Table Records |
| :--- | :--- | :--- | :---: | :---: |
| `1706.03762v7` | 1706.03762 | Attention Is All You Need | 50 | 10 (5 table, 5 table_unstructured) |
| `2410.00037v1` | 2410.00037 | Moshi Foundation Model | 220 | 73 (54 table, 19 table_unstructured) |
| `2507.07955v2` | 2507.07955 | Dynamic Chunking (H-Net) | 132 | 27 (19 table, 8 table_unstructured) |
| **Total** | — | — | **402** | **110** |

### Channel Configurations

| Component | Storage Path | Technology / Library | Parameters & Configuration |
| :--- | :--- | :--- | :--- |
| **Dense Retriever** | `data/indexes/chroma/` | ChromaDB (`chromadb`) + SentenceTransformers | Model: `sentence-transformers/all-MiniLM-L6-v2`<br>Embedding Dimension: 384<br>Distance Metric: **Cosine** (`{"hnsw:space": "cosine"}`)<br>Normalization: L2-normalized embeddings<br>Mode: Purely local (`local_files_only=True`) |
| **BM25 Retriever** | `data/indexes/bm25/bm25_index.json` | `rank-bm25` (`BM25Okapi`) | Tokenizer: Alphanumeric + technical symbols (`[a-zA-Z0-9_-]+`)<br>Corpus: 402 lowercased tokenized documents<br>Format: JSON serialized chunk map + inverted corpus |
| **Fact Store** | `data/indexes/fact_store.db` | SQLite (`sqlite3`) | Tables: `facts` (relational table) + `facts_fts` (FTS5 virtual table)<br>Elements Indexed: Verbatim `table` and `table_unstructured` markdown<br>Query Modes: SQL `LIKE %query%` exact substring match + FTS5 BM25 |
| **Hybrid Fusion** | In-memory orchestrator | Pure Python mathematical RRF | Smoothing constant: $k = 60$<br>Channel weights: dense=1.0, bm25=1.0, fact_store=1.0<br>Deduplication: Unique `chunk_id` with additive reciprocal ranks |

### Index Build Benchmarks (Measured on Local CPU)

| Index Phase | Target Location | Records Processed | Measured Time | Idempotency Re-Index Count |
| :--- | :--- | :---: | :---: | :---: |
| **Chunk Dataset Load** | `data/chunks/langchain_recursive/` | 402 chunks | 0.06s | 402 chunks |
| **ChromaDB Dense Vectors** | `data/indexes/chroma/` | 402 vectors | 61.75s | 402 vectors (0 duplicates) |
| **BM25 Inverted Index** | `data/indexes/bm25/` | 402 documents | 0.15s | 402 documents (0 duplicates) |
| **SQLite Fact Store** | `data/indexes/fact_store.db` | 110 tables/facts | 0.17s | 110 records (0 duplicates) |
| **Total Build Time** | — | — | **~62.1s** | Verified idempotent (0 duplicates) |

---

## 3. Reciprocal Rank Fusion (RRF) Formulation

Reciprocal Rank Fusion combines ranked candidate lists from disparate retrieval mechanisms without requiring score calibration or normalization across unbounded score scales (such as cosine similarity vs. BM25 unbounded scores vs. FTS rank).

For a query $q$ and a set of active retrieval channels $M \subseteq \{\text{dense}, \text{bm25}, \text{fact\_store}\}$:

$$\text{RRF\_Score}(d) = \sum_{m \in M} \frac{w_m}{k + r_m(d)}$$

Where:
- $w_m$ is the channel weight (default $w_m = 1.0$).
- $k$ is the smoothing constant (standard $k = 60$). Setting $k = 60$ prevents top-ranked outliers from overpowering items consistently ranked in the top 5 across multiple channels.
- $r_m(d) \in \{1, 2, 3, \dots\}$ is the 1-based rank of document $d$ in the candidate list produced by channel $m$. If document $d$ was not retrieved by channel $m$, its contribution from channel $m$ is $0$.

### Multi-Channel Consensus Example
- Document ranked #1 in Dense only: $\frac{1}{60 + 1} = 0.016393$
- Document ranked #2 in BM25 only: $\frac{1}{60 + 2} = 0.016129$
- Document ranked #1 in Dense AND #2 in BM25: $\frac{1}{61} + \frac{1}{62} = 0.032522$

A document supported by both dense semantic similarity and exact keyword matching receives nearly double the score of a single-channel hit, elevating true consensus evidence to the top.

---

## 4. Query Benchmarks & Empirical Evaluations

### Benchmark Query 1: Cross-Sectional Numerical Fact
- **Query:** `"What is the BLEU score achieved by Transformer on English-to-German?"`
- **Paper Filter:** None (Global search across all 3 papers)

| Channel | Rank | Chunk ID | Raw Score | Page | Content Snippet |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Dense** | 1 | `1706.03762v7_lc_0025` | 0.8244 (cosine sim) | p.8 | *Table 2: The Transformer achieves better BLEU scores than previous state-of-the-art models on English-to-German (28.4)...* |
| **BM25** | 1 | `1706.03762v7_lc_0029` | 18.828 (BM25) | p.8 | *6.1 Machine Translation: On WMT 2014 English-to-German task, big transformer achieves 28.4 BLEU...* |
| **BM25** | 2 | `1706.03762v7_lc_0025` | 17.528 (BM25) | p.8 | *Table 2: The Transformer achieves better BLEU scores...* |
| **Fused (RRF)** | **1** | **`1706.03762v7_lc_0025`** | **0.032522** | **p.8** | **Channels: dense + bm25** *(Table 2 with 28.4 BLEU)* |
| **Fused (RRF)** | **2** | **`1706.03762v7_lc_0029`** | **0.032266** | **p.8** | **Channels: dense + bm25** *(Section 6.1 explanation)* |

*Observation:* RRF successfully elevated `1706.03762v7_lc_0025` to Rank 1 because it appeared at the top of both Dense and BM25 channels.

---

### Benchmark Query 2: Audio Foundation Model Architecture
- **Query:** `"What is the acoustic latency and frame rate of Moshi?"`
- **Paper Filter:** `2410.00037v1` (Moshi paper)

| Channel | Rank | Chunk ID | Raw Score | Page | Content Snippet |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Dense** | 1 | `2410.00037v1_lc_0172` | 0.5334 | p.56 | *Acoustic tokens and semantic tokens in streaming ASR and TTS...* |
| **BM25** | 1 | `2410.00037v1_lc_0071` | 17.933 | p.24 | *Results - Acoustic tokens. Table 3 shows significant improvement in MUSHRA...* |
| **BM25** | 2 | `2410.00037v1_lc_0171` | 17.318 | p.55 | *Delayed text LM as zero-shot streaming ASR and TTS with 160ms/200ms latency...* |
| **Fused (RRF)** | **1** | **`2410.00037v1_lc_0171`** | **0.030835** | **p.55** | **Channels: dense + bm25** *(Exact latency specification)* |

*Observation:* Paper filtering strictly restricted candidate generation to `2410.00037v1`, filtering out non-target papers while preserving high relevance.

---

### Benchmark Query 3: Hierarchical Sequence Modeling
- **Query:** `"How does dynamic chunking perform token boundary prediction in H-Net?"`
- **Paper Filter:** `2507.07955v2` (Dynamic Chunking paper)

| Channel | Rank | Chunk ID | Raw Score | Page | Content Snippet |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Dense** | 1 | `2507.07955v2_lc_0015` | 0.7232 | p.6 | *2.2 Dynamic Chunking (DC): H-Net learns chunking boundaries through end-to-end training...* |
| **BM25** | 1 | `2507.07955v2_lc_0006` | 16.659 | p.3 | *(c) Smoothing Module and chunking / dechunking module...* |
| **BM25** | 2 | `2507.07955v2_lc_0130` | 16.230 | p.39 | *Figure 16: Visualization of boundary positions dynamically drawn by H-Net (1-stage)...* |
| **Fused (RRF)** | **1** | **`2507.07955v2_lc_0130`** | **0.032002** | **p.39** | **Channels: dense + bm25** *(Visual and boundary explanation)* |
| **Fused (RRF)** | **2** | **`2507.07955v2_lc_0108`** | **0.030622** | **p.33** | **Channels: dense + bm25** *(Boundary entropy analysis)* |
| **Fused (RRF)** | **3** | **`2507.07955v2_lc_0015`** | **0.030092** | **p.6** | **Channels: dense + bm25** *(Mathematical formulation of DC)* |

---

## 5. Verification & Test Suite Summary

The complete test suite was executed via `uv run pytest -v`:

73 tests passed in the primary suite (77 tests passed including targeted regression suites for arXiv identifier tokenization and channel failure diagnostics). No coverage percentages are claimed.

```text
tests/test_bm25_retriever.py ......................... [7 passed]
tests/test_chunking.py .............................. [14 passed]
tests/test_dense_retriever.py ........................ [8 passed]
tests/test_extract_papers.py ......................... [8 passed]
tests/test_fact_store.py ............................. [7 passed]
tests/test_hybrid_retriever.py ....................... [9 passed]
tests/test_langchain_chunking.py ..................... [11 passed]
tests/test_pdf_ingestion.py .......................... [13 passed]
======================= 77 passed in 323.48s (0:05:23) =======================
```

### Verified Test Breakdown
1. **Dense Vector Tests (`tests/test_dense_retriever.py`):**
   - In-memory collection creation and query.
   - Idempotent upsert verification (re-indexing produces 0 duplicate records).
   - Cosine distance configuration verified (`{"hnsw:space": "cosine"}`).
   - Metadata serialization/deserialization roundtrip (complex types converted to primitives and restored).
   - Real local `sentence-transformers/all-MiniLM-L6-v2` embedding integration test.
   - Persistence and reload across sessions.
2. **BM25 Tests (`tests/test_bm25_retriever.py`):**
   - Exact term tokenization and ranking (`d_model`, `BLEU 28.4`, `latency`).
   - Paper filtering accuracy.
   - Idempotency and incremental updates.
   - JSON serialization and reload from disk.
   - Zero-match and empty-query safety.
3. **Structured Fact Store Tests (`tests/test_fact_store.py`):**
   - SQLite schema initialization (with FTS5 virtual table).
   - Element filtering (`filter_fact_elements_only=True` selects tables and excludes general prose).
   - Exact substring and numeric string lookups (`"28.4"`, `"160"`).
   - Verbatim preservation of Markdown tables without silent normalization.
   - Persistence across database reconnections.
4. **Hybrid Retriever Tests (`tests/test_hybrid_retriever.py`):**
   - Mathematical precision of RRF formula ($1 / (k + r)$).
   - Deduplication and multi-channel score accumulation.
   - Channel toggles (`enable_dense`, `enable_bm25`, `enable_facts`).
   - Full provenance preservation (paper_id, section, page_number, element_type, chunk_id).
   - Paper filter propagation across all active channels.

---

## 6. Known Limitations & Engineering Boundaries

1. **CPU Embedding Latency:**
   Generating embeddings on CPU for 402 chunks took ~61 seconds during initial index construction. In subsequent retrieval calls, querying a single string takes ~25–50ms on CPU, which is acceptable for interactive queries but highlights the advantage of batching if bulk query workloads arise.
2. **FTS5 Syntax Edge Cases:**
   Raw punctuation in SQLite FTS5 queries (e.g. `d_model*?`) can trigger operational syntax errors if not sanitized. The retriever sanitizes FTS query strings by stripping unescaped operators, falling back to SQL `LIKE` substring matching if an FTS query fails.
3. **Table Row Granularity:**
   Tables extracted from the PDFs are stored at table-level granularity in Markdown format. If a table spans multiple pages, it is preserved as split table chunks according to PDF ingestion rules. Fine-grained cell-by-cell relational querying is not implemented, preserving verbatim table text as required.
4. **Strict Scope Enforcement:**
   No LLM calls (Groq API), simulated model services, or LangGraph stateful graphs were implemented in this stage, strictly keeping the retrieval engine modular and independent.

