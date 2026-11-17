# Final Documentation Reconciliation Report

**Project:** The Relay — Vaani Research ML Engineering Technical Assignment  
**Document:** Final Documentation Reconciliation  
**Date:** November 14, 2026  
**Status:** All Documentation Reconciled & Synchronized across Root and Submission Packages  

---

## 1. Executive Summary

This reconciliation report resolves all documentation inconsistencies identified in the pre-delivery audit. All corrections are backed by direct source-code inspection, raw experimental data artifacts, and automated verification.

No functional source code was modified, no new experiments were run, and zero historical datasets were altered.

---

## 2. Reconciled Items & Evidence

### Item 1: Chunking Implementation Parameters
- **Audit Discrepancy:** The earlier compliance audit referenced generic character-based chunking ("1,000 characters, 150 overlap").
- **Actual Implementation (`app/retrieval/langchain_chunking.py`):**
  - Chunking Engine: LangChain `RecursiveCharacterTextSplitter` configured with token-aware counting via `sentence-transformers/all-MiniLM-L6-v2` (`AutoTokenizer`).
  - `DEFAULT_CHUNK_SIZE`: **512 tokens**
  - `DEFAULT_CHUNK_OVERLAP`: **76 tokens** (~15% token overlap)
  - `length_function`: `count_tokens` (MiniLM BPE tokenizer)
  - Total chunks generated across the 3 arXiv papers: **402 chunks**
  - Stage 8B.2 enhancement: Table caption preservation prepends table context metadata to table chunks while maintaining token boundaries.
- **Correction Applied:** Updated `reports/FINAL_SUBMISSION_AUDIT.md` (Requirement 3) to reflect the exact 512-token size and 76-token overlap.

---

### Item 2: PDF Extraction Script Path
- **Audit Discrepancy:** Earlier matrix listed non-existent file `app/retrieval/extract_papers.py`.
- **Actual Implementation:**
  - Library Module: `app/retrieval/pdf_ingestion.py` (PyMuPDF document extraction engine, bounding boxes, and table detection).
  - CLI Extraction Script: `scripts/extract_papers.py` (CLI runner that executes extraction across all 3 PDFs in `papers/`).
- **Correction Applied:** Corrected the file path in `reports/FINAL_SUBMISSION_AUDIT.md` (Requirement 2) to `app/retrieval/pdf_ingestion.py` and `scripts/extract_papers.py`.

---

### Item 3: Retrieval Improvement Percentages Reconciliation
All retrieval improvement figures reported across Stages 6, 8B.2, and 8E were reconciled against the authoritative JSON summaries (`retrieval_summary.json` and `retrieval_summary_stage8b2.json`):

#### Mathematical Denominators Enforced:
1. **Recall@$k$ and MRR Denominator ($N_{\text{ans}} = 26$):** Evaluated strictly over the 26 answerable questions that possess ground-truth passages in the corpus.
2. **System-wide Accuracy & Refusal Denominator ($N_{\text{total}} = 32$):** Evaluated across all 32 questions (26 answerable + 6 unanswerable / out-of-domain queries).

#### Reconciled Metrics Matrix:

| Retrieval Configuration | Stage 6 Baseline ($k=5$) | Stage 8B.2 Table Context ($k=5$) | Absolute Delta (pp) | Relative Delta (%) | Denominator & Scope |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Config A: Dense-only (ChromaDB)** | 61.54% (16/26) | **73.08%** (19/26) | **+11.54 pp** | +18.75% | $N_{\text{ans}}=26$ (Recall@5) |
| **Config B: BM25-only (Rank-BM25)** | 65.38% (17/26) | **73.08%** (19/26) | **+7.70 pp** | +11.77% | $N_{\text{ans}}=26$ (Recall@5) |
| **Config C: Hybrid (Dense + BM25)** | 73.08% (19/26) | **76.92%** (20/26) | **+3.84 pp** | +5.25% | $N_{\text{ans}}=26$ (Recall@5) |
| **Config D: Full Hybrid (+ FactStore)**| 73.08% (19/26) | **76.92%** (20/26) | **+3.84 pp** | +5.25% | $N_{\text{ans}}=26$ (Recall@5) |
| **Correct & Cited % (All Qs)** | 59.38% (19/32) | **62.50%** (20/32) | **+3.12 pp** | +5.25% | $N_{\text{total}}=32$ (Accuracy) |
| **Wrong Answer % (All Qs)** | 21.88% (7/32) | **18.75%** (6/32) | **-3.13 pp** | -14.30% | $N_{\text{total}}=32$ (Error Rate) |

#### Reconciled Top-$k$ Scaling Frontier (Stage 8B.2 Full Hybrid):
- **$k=5$:** Recall@5 = **76.92%** (20/26), Correct & Cited = **62.50%** (20/32), Avg Context = 1,415.8 tokens, Cost/1k = \$0.3474
- **$k=8$:** Recall@8 = **84.62%** (22/26), Correct & Cited = **68.75%** (22/32), Avg Context = 2,207.2 tokens, Cost/1k = \$0.4876 (**+7.70 pp** recall gain over $k=5$)
- **$k=10$:** Recall@10 = **88.46%** (23/26), Correct & Cited = **71.88%** (23/32), Avg Context = 2,762.0 tokens, Cost/1k = \$0.5901 (**+11.54 pp** recall gain over $k=5$)
- **Cumulative Scaling Gain:** From Stage 6 Baseline ($k=5$, 73.08%) to Stage 8B.2 ($k=10$, 88.46%), the cumulative Recall gain is **+15.38 percentage points** (+4 additional questions answered correctly out of 26).

---

### Item 4: Verification of `reports/final_submission.md`
- **Rendered Page Count & Word Count:**
  - Total Words: **3,999 words** (223 markdown lines).
  - Estimated Rendered Pages: Approximately 4–5 standard printed pages at 10pt typography.
  - Page Limit Policy: In accordance with assignment instructions (*"Do not silently omit required content to force a page limit"*), all mandatory technical details, derivations, and tables are preserved in full.
- **Mandatory Headings & Tables Verified:**
  - `1. What I built and why` (Present)
  - `2. The real service and my stand-in` (Present)
    - **Table 1** — Real service limits and observed behavior (Present)
  - `3. Results` (Present)
    - **Table 2a** — Latency and throughput by scenario (Present)
    - **Table 2b** — Reliability and cost by scenario (Present)
  - `4. Where the time goes` (Present)
  - `5. When a limit is hit` (Present)
  - `Retrieval: quality versus cost` (Present)
    - **Table 3** — Retrieval configuration comparison (Present)
  - `How this library will mislead a naive retriever` (Present)
  - `Retries` (Present)
  - `What the person sees` (Present)
  - `What I'm unsure about, what I left out, what I learned` (Present)
  - `Your feedback on Vaani` (Present)
  - `How I worked with the assistant` (Present: Division of labor, 3 prompts, 1 error caught, 1 decision overruled)

---

### Item 5: Submission Directory Synchronization
- Synchronized all updated files to `submission/`:
  - `submission/pyproject.toml` (includes pytest `testpaths = ["tests"]` and `norecursedirs`)
  - `submission/README.md` (synchronized with root `README.md`)
  - `submission/reports/FINAL_SUBMISSION_AUDIT.md` (synchronized with updated audit report)
  - `submission/reports/FINAL_RECONCILIATION.md` (this report)
- Verified exclusion of `.venv/`, `.venv_docling/`, `node_modules/`, `dist/`, `.env`, and `__pycache__/`.

---

### Item 6: PowerShell Command Consistency across READMEs
Verified that both `README.md` and `submission/README.md` provide identical, robust Windows PowerShell commands:

```powershell
# 1. Start Stand-in Simulator (Terminal 1)
uv run uvicorn simulator.main:app --port 8001

# 2. Start FastAPI Backend (Terminal 2)
$env:MODEL_PROVIDER="simulator"
uv run uvicorn app.main:app --port 8000

# 3. Start React Frontend (Terminal 3)
cd frontend
npm install
npm run dev

# 4. Execute Backend Tests
uv run pytest

# 5. Execute Frontend Tests
npm test --prefix frontend
```

---

### Item 7: Update of `reports/FINAL_SUBMISSION_AUDIT.md`
- Updated Requirement 2: Corrected script path to `scripts/extract_papers.py`.
- Updated Requirement 3: Corrected chunk size to 512 tokens and overlap to 76 tokens.
- Updated Requirement 17: Added comprehensive metric breakdown (+3.84 pp at $k=5$, +15.38 pp cumulative at $k=10$, $N_{\text{ans}}=26$).
- Updated Section 4: Documented exact 3,999-word length and verified inclusion of all 12 mandatory sections and 4 tables.

---

## 3. Final Verification Status

| Step | Target | Result |
| :--- | :--- | :--- |
| **Backend Tests** | `uv run pytest` | **194 passed, 0 failed, 1 warning** (Exit code: 0) |
| **Frontend Tests** | `npm test --prefix frontend` | **54 passed, 0 failed** (Exit code: 0) |
| **Frontend Lint** | `npm run lint --prefix frontend` | **0 errors, 0 warnings** (Exit code: 0) |
| **Frontend Build** | `npm run build --prefix frontend` | **Clean bundle** (Exit code: 0) |
| **Package Check** | `uv pip check` | **144 packages compatible** (Exit code: 0) |
| **Submission Sync** | `submission/` | **Verified 100% synchronized** |

The documentation reconciliation is complete. The repository and `submission/` package are in an authoritative, fully consistent state.
