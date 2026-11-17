# Stage 6: Retrieval Quality vs Cost Evaluation Report

## 1. Executive Summary

This report documents the empirical evaluation of retrieval quality versus computational and inference cost for **Stage 6** and the subsequent **Stage 6A Retrieval Integrity Audit** of *The Relay (Vaani Research ML Engineering Assignment)*.

We evaluated four retrieval configurations over a manually verified, 32-question evaluation dataset spanning three assigned arXiv research papers:
1. **Vaswani et al. (2017)** — *Attention Is All You Need* (`1706.03762v7`)
2. **Défossez et al. (2024)** — *Moshi: A Speech-Text Foundation Model for Real-Time Dialogue* (`2410.00037v1`)
3. **Hwang, Wang, & Gu (2025)** — *Dynamic Chunking for End-to-End Hierarchical Sequence Modeling* (`2507.07955v2`)
4. **Out-of-Domain Refusals** (6 adversarial ML topics outside the corpus: LLaMA-3, BERT, DDPM, FlashAttention, DeepSeek-R1, AlphaFold)

The evaluation evaluated two distinct layers:
- **Retrieval Performance:** Recall@1, Recall@3, Recall@5, Mean Reciprocal Rank (MRR), Paper and Page identification accuracy, retrieval latency (p50/p95), and retrieved context tokens.
- **End-to-End Workflow Performance:** Full execution through the LangGraph research assistant workflow backed by the calibrated `SimulatorProvider` (calibrated against Groq `openai/gpt-oss-120b`), measuring citation verification, correction loops, response TTFT, total latency, and economic inference cost per 1,000 queries.

---

## 2. Experimental Configurations

All configurations operated over the standard corpus of 402 chunks and 110 structured FactStore records with consistent top-$k=5$ and candidate-$k=20$:

- **Configuration A: Dense-only (ChromaDB)**
  - *Embedding Model:* `sentence-transformers/all-MiniLM-L6-v2` (384-dimensional dense vectors, normalized L2, cosine distance).
  - *Retrieval Channel:* Dense vector similarity search only (`enable_dense=True`, `enable_bm25=False`, `enable_facts=False`).
  - *Reranking:* None (ranked strictly by cosine similarity score).

- **Configuration B: BM25-only (Rank-BM25)**
  - *Index:* Tokenized lexical index with arXiv-aware alphanumeric pattern.
  - *Retrieval Channel:* Sparse keyword search only (`enable_dense=False`, `enable_bm25=True`, `enable_facts=False`).
  - *Reranking:* None (ranked strictly by BM25 score).

- **Configuration C: Hybrid (Dense + BM25)**
  - *Channels:* Dense ChromaDB + Sparse BM25 (`enable_dense=True`, `enable_bm25=True`, `enable_facts=False`).
  - *Fusion Algorithm:* Reciprocal Rank Fusion (RRF) with constant $k=60$ and channel weights $w_{\text{dense}}=1.0, w_{\text{bm25}}=1.0$.

- **Configuration D: Full Hybrid (Dense + BM25 + Structured FactStore)**
  - *Channels:* Dense ChromaDB + Sparse BM25 + SQLite FTS5/exact-substring FactStore (`enable_dense=True`, `enable_bm25=True`, `enable_facts=True`).
  - *Fusion Algorithm:* Multi-channel RRF with constant $k=60$ and equal weights $w=1.0$ across all 3 channels.

---

## 3. Master Comparison Table

**Pricing Basis:** Model Prompt tokens at **\$0.15 / 1M tokens**; Model Completion tokens at **\$0.60 / 1M tokens** (calibrated against standard serverless pricing). Hosted inference cost is decoupled from local CPU retrieval computation.

| Metric | Config A: Dense-only | Config B: BM25-only | Config C: Hybrid (Dense+BM25) | Config D: Full Hybrid |
| :--- | :---: | :---: | :---: | :---: |
| **Chunk Size / Strategy** | 1,000 chars (Recursive) | 1,000 chars (Recursive) | 1,000 chars (Recursive) | 1,000 chars (Recursive) |
| **Pieces Fetched (Top-$k$)** | 5 | 5 | 5 | 5 |
| **Candidate $k$ per Channel** | 20 | 20 | 20 | 20 |
| **Reranking / Fusion Enabled** | False | False | True (RRF $k=60$) | True (RRF $k=60$) |
| **Total Questions Evaluated** | 32 | 32 | 32 | 32 |
| **Answerable Questions ($N_{\text{ans}}$)** | 26 | 26 | 26 | 26 |
| **Unanswerable Questions ($N_{\text{unans}}$)**| 6 | 6 | 6 | 6 |
| **Recall@1** ($/ N_{\text{ans}}$) | 34.62% | **46.15%** | 42.31% | 42.31% |
| **Recall@3** ($/ N_{\text{ans}}$) | 57.69% | 57.69% | **61.54%** | **61.54%** |
| **Recall@5** ($/ N_{\text{ans}}$) | 61.54% | 65.38% | **73.08%** | **73.08%** |
| **Mean Reciprocal Rank (MRR)** | 0.4519 | 0.5301 | **0.5353** | **0.5353** |
| **Correct Paper %** ($/ N_{\text{ans}}$) | 100.0% | 100.0% | 100.0% | 100.0% |
| **Correct Page %** ($/ N_{\text{ans}}$) | 65.38% | 73.08% | **76.92%** | **76.92%** |
| **Retrieval Latency (Mean)** | 50.29 ms | **3.34 ms** | 38.13 ms | 37.50 ms |
| **Retrieval Latency (p50 / p95)**| 36.19 / 46.98 ms | **3.02 / 4.76 ms** | 35.87 / 40.16 ms | 36.80 / 44.72 ms |
| **Avg Retrieved Context Tokens**| **1,078.4** | 1,507.3 | 1,402.3 | 1,402.3 |
| **Correct & Cited % (All $N=32$)**| 50.00% (16/32) | 53.12% (17/32) | **59.38% (19/32)** | **59.38% (19/32)** |
| **Correct & Cited % ($N_{\text{ans}}=26$)**| 61.54% (16/26) | 65.38% (17/26) | **73.08% (19/26)** | **73.08% (19/26)** |
| **Wrong % (All $N=32$)** | 31.25% (10/32) | 28.12% (9/32) | **21.88% (7/32)** | **21.88% (7/32)** |
| **Correct Refusal % ($/ N_{\text{unans}}$)**| **100.0% (6/6)** | **100.0% (6/6)** | **100.0% (6/6)** | **100.0% (6/6)** |
| **Incorrect Refusal % ($/ N_{\text{unans}}$)**| **0.0% (0/6)** | **0.0% (0/6)** | **0.0% (0/6)** | **0.0% (0/6)** |
| **Citation Verification Success**| 100.0% | 100.0% | 100.0% | 100.0% |
| **Total Correction Attempts** | 6 | 6 | 6 | 6 |
| **Response TTFT (p50 / p95)** | 852.0 / 852.0 ms | 852.0 / 852.0 ms | 852.0 / 852.0 ms | 852.0 / 852.0 ms |
| **Total Response Latency (p50)**| 1,014.56 ms | **980.36 ms** | 1,013.95 ms | 1,014.81 ms |
| **Avg Model Input / Output Tokens**| **1,647.7** / 74.0 | 2,102.9 / 74.0 | 1,991.0 / 74.6 | 1,991.0 / 74.6 |
| **Cost / 1,000 Answers** | **\$0.2915** | \$0.3599 | \$0.3434 | \$0.3434 |

---

## 4. Stage 6A Audit: Investigation of Config C vs Config D

A primary focus of the Stage 6A audit was investigating why **Config C (Hybrid Dense + BM25)** and **Config D (Full Hybrid Dense + BM25 + FactStore)** yielded identical results across all quality and token metrics.

### 4.1 Empirical Findings on FactStore Channel Contributions
Tracing the execution of `FactStore.search(query)` across all 32 evaluation questions revealed the following exact metrics:

1. **Questions where FactStore returned $\ge 1$ result:** **0 / 32** (0.0%).
2. **Number of unique FactStore results returned:** **0**.
3. **Number of unique relevant results contributed by FactStore:** **0**.
4. **Number of questions where FactStore changed the final top-5:** **0**.
5. **Number of questions where FactStore improved the rank of a relevant passage:** **0**.
6. **Number of questions where FactStore introduced irrelevant results:** **0**.
7. **Number of questions where Config D performed differently from Config C:** **0**.

### 4.2 Root Cause Analysis
The mathematical identity between Config C and Config D is a direct consequence of how `FactStore.search()` is implemented:
- **Exact Substring Search (`content LIKE ?`):** Line 227 of `app/retrieval/fact_store.py` checks `WHERE content LIKE '%<query>%'`. When user queries are full natural language questions (e.g. `"In Table 2, what BLEU scores did the Transformer (big) achieve on the WMT 2014 English-to-German and English-to-French translation tasks?"`), the entire sentence is checked as a verbatim substring against markdown table text. This naturally returns zero matches.
- **FTS5 Full-Text Search (`facts_fts MATCH ?`):** Line 282 executes `WHERE facts_fts MATCH sanitized_fts`. In SQLite FTS5, space-separated tokens without explicit boolean operators default to a strict **conjunctive (`AND`) match**. Every word in the query must appear in the indexed record. Natural language phrasing contains conversational words ("what", "did", "achieve", "how", "tasks") that never occur inside structured markdown table rows. As a result, the FTS5 query returned zero candidates for all 32 questions.

Because `FactStore` returned zero candidates for all questions, its RRF contribution was empty, leaving the fusion pool identical to Dense + BM25.

### 4.3 Conclusion & Architectural Implication
In accordance with Stage 6A instructions, we **did not modify the FactStore or hybrid retrieval algorithm merely to force a difference**. 
This is documented as a **valid empirical negative finding**:
> A structured fact store operating on exact substring or conjunctive full-text search cannot serve conversational natural language questions directly without a prior query pre-processing or keyword extraction step (e.g., using an LLM or regex to extract `"Table 2"` or `"BLEU"`). When invoked with raw user questions, Full Hybrid degenerates to standard Hybrid (Dense + BM25). Therefore, **Config D provides no measurable quality improvement over Config C**.

---

## 5. Metric Denominators and Grading Methodology

To ensure statistical integrity, every evaluation metric is defined with its explicit denominator:

1. **Recall@k (Recall@1, @3, @5) and MRR:**
   - Evaluated strictly over the **26 answerable questions** ($N_{\text{ans}}=26$). Unanswerable questions are excluded because they have no supporting passages in the corpus.
2. **Correct Refusal % and Incorrect Refusal %:**
   - Evaluated strictly over the **6 unanswerable questions** ($N_{\text{unans}}=6$). All 6 were correctly rejected by the workflow sufficiency check (100% correct refusal rate).
3. **Correct-and-Cited Percentage:**
   - Reported over **all 32 questions** ($N=32$): **59.38%** (19/32).
   - When restricted to the **26 answerable questions** ($N_{\text{ans}}=26$): **73.08%** (19/26).
4. **Citation Verification vs Semantic Entailment:**
   - The deterministic `verify_citations` node validates metadata provenance: verifying that the cited arXiv ID, paper title, page number, and section exist in the retrieved evidence set.
   - **Crucial Limitation:** Citation verification guarantees metadata traceability; it does **not** constitute mathematical proof of semantic entailment between the generated answer text and the cited source passage.
5. **Grading Rubric & Automated Verification:**
   - Answer grades were assigned using a deterministic rubric cross-referencing manually verified chunk IDs (`expected_chunk_ids`), paper IDs, page numbers, and key answer terms. Ambiguous or borderline answers were not awarded correctness without verifying supporting chunk presence.

---

## 6. Corrected Economic and Latency Interpretation

1. **Quality Gain Clarification:**
   - The difference in Recall@5 between Dense-only (61.54%) and Hybrid (73.08%) is **11.54 percentage points** (not percent).
   - The difference in overall Correct-and-Cited percentage between Dense-only (50.00%) and Hybrid (59.38%) is **9.38 percentage points** (or **11.54 percentage points** when measured over answerable questions: 61.54% vs 73.08%).
2. **Computational vs Inference Cost:**
   - **Retrieval Latency (Local CPU):** BM25 is fastest (3.02 ms p50), while Dense adds ~35 ms due to local embedding inference. Combining BM25 with Dense in Hybrid adds under 1 ms of CPU overhead relative to Dense-only.
   - **Model Generation Latency (Hosted Service):** Model generation (~976 ms non-streaming median, ~852 ms TTFT) dominates overall response time (~1,014 ms). Retrieval represents less than **3.7%** of total end-to-end user latency.
   - **Token Economics:** Dense-only costs \$0.2915 / 1,000 queries. Hybrid costs \$0.3434 / 1,000 queries (+17.8% relative cost, or +\$0.052 per 1,000 queries). For an additional **5.2 cents per 1,000 queries**, Hybrid retrieval delivers an **11.54 percentage point gain in Recall@5** and a **9.38 percentage point gain in verified answers**, making Hybrid overwhelmingly cost-effective.

---

## 7. Raw Result Integrity & Artifact Verification

The raw evaluation results at `experiments/retrieval/retrieval_results.csv` were audited and confirmed:
- Exactly **128 records** ($32 \text{ questions} \times 4 \text{ configurations}$).
- Zero duplicate `(question_id, configuration)` combinations.
- All summary metrics in `experiments/retrieval/retrieval_summary.json` are **100% reproducible** from the raw CSV records.

All Stage 6 / 6A deliverables are committed:
1. `experiments/retrieval/evaluation_questions.json` (32 verified questions)
2. `experiments/retrieval/evaluation_dataset_report.md` (Dataset specification & schema)
3. `experiments/retrieval/retrieval_results.csv` (128 raw records)
4. `experiments/retrieval/retrieval_summary.json` (Summary metrics)
5. `experiments/retrieval/retrieval_quality_report.md` (This report)

---

## 8. Full Regression Suite Verification

The full regression test suite was executed:

```powershell
uv run pytest -q
```
**Result:** `186 passed, 1 warning in 131.66s` (all 186 baseline unit and integration tests passing).

```powershell
uv pip check
```
**Result:** `Checked 144 packages in 14ms. All installed packages are compatible.`
