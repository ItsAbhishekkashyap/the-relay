# Final Deliverable Verification Report

**Project:** The Relay — Vaani Research ML Engineering Technical Assignment  
**Specification Reference:** Original 4-Page Vaani Research Assignment Brief (Pages 2, 3, 4)  
**Evaluation Date:** November 14, 2026  
**Auditor:** Senior ML Systems & Compliance Release Engineer  

---

## 1. Final Submission Directory Tree

The `submission/` package directory has been assembled cleanly and contains all code, models, configs, papers, data, and deliverables:

```
submission/
├── final_submission.pdf            # Primary 2-page technical write-up (ReportLab rendered)
├── final_submission.md             # Markdown source containing all 12 headings & 4 tables
├── results.csv                     # Canonical raw request-level measurements (311 genuine rows)
├── README.md                       # Comprehensive setup and reproduction guide (PowerShell verified)
├── FINAL_DELIVERABLE_CHECK.md      # This verification report
├── requirements.txt                # Pinned dependencies
├── pyproject.toml                  # Python package and test configuration
├── uv.lock                         # Reproducible dependency lockfile
├── .env.example                    # Safe template (defaults to local simulator, zero API keys required)
├── .gitignore                      # Exclusion rules (.env, node_modules, caches, *.db ignored)
│
├── app/                            # Backend application
│   ├── api/                        # FastAPI endpoints (/health, /ready, /v1/ask, /v1/metrics, /v1/experiments/*)
│   ├── providers/                  # Groq Cloud and Stand-in Simulator model integrations
│   ├── retrieval/                  # Ingestion, LangChain 512/76 chunking, ChromaDB, BM25, FactStore, RRF
│   ├── traffic/                    # Asynchronous TrafficManager (FIFO queue, semaphore N=4, RPM/TPM limiters)
│   ├── workflow/                   # LangGraph 8-node stateful workflow with citation verification gate
│   ├── config.py                   # Pydantic v2 application settings
│   └── main.py                     # FastAPI application factory
│
├── simulator/                      # Calibrated stand-in model service
│   ├── config.py                   # Calibrated lognormal parameters (mu=6.94, sigma=0.22) & rate limits
│   ├── service.py                  # Stand-in engine with SSE streaming and error injection
│   └── main.py                     # FastAPI simulator application
│
├── frontend/                       # Interactive SaaS light-theme dashboard
│   ├── src/pages/                  # Research Chat, System Overview, Experiment Analytics, Simulator Controls
│   ├── src/components/             # Polished UI components (Stripe/Linear inspired design)
│   └── tests/                      # Automated Vitest test suites (54 passing tests)
│
├── papers/                         # Exact 3 target research papers (120 pages total)
│   ├── 1706.03762v7.pdf            # Attention Is All You Need (Vaswani et al.)
│   ├── 2410.00037v1.pdf            # Moshi: a speech-text foundation model (Defossez et al.)
│   └── 2507.07955v2.pdf            # Dynamic Chunking for Long-Context Retrieval (Shao et al.)
│
├── data/                           # Data artifacts
│   ├── extracted/                  # PyMuPDF extracted document blocks and tables
│   ├── chunks/                     # Token-aware LangChain chunks (512 tokens, 76 overlap)
│   └── indexes/                    # Persistent ChromaDB, BM25 index, and FactStore SQLite
│
├── experiments/                    # Raw empirical experiment datasets
│   ├── real_service/               # Groq characterization (20 raw baseline records in groq_baseline.csv)
│   ├── simulator/                  # Simulator calibration benchmarks
│   ├── retrieval/                  # Stage 6 (128 records) and Stage 8B.2 (192 records) raw CSVs
│   ├── results.csv                 # Raw 119 load-testing request records
│   └── reports/                    # Machine-readable JSON summaries
│
├── assistant_history/              # Complete raw and human-readable conversation history logs
│   ├── GEMINI_CONVERSATION_HISTORY.md # Human-readable log of all 46 user dialogue turns and responses
│   ├── gemini_conversation_transcript.jsonl # Complete compact raw trajectory JSONL (7,026 steps)
│   ├── gemini_conversation_transcript_full.jsonl # Complete raw trajectory JSONL with full tool payloads
│   ├── gemini_browser_subagent_transcript.jsonl # Autonomous Chrome DevTools browser subagent log
│   └── README.md                   # Assistant history guide and security verification
│
├── supporting_reports/             # Comprehensive technical and stage reports
│   ├── FINAL_SUBMISSION_AUDIT.md   # Final audit confirming 21/21 requirements PASS
│   ├── FINAL_RECONCILIATION.md     # Documentation reconciliation and formula audit
│   ├── final_compliance_audit.md   # Exhaustive requirement-by-requirement audit
│   └── ...                         # Detailed stage reports (8B through 8G)
│
├── scripts/                        # Reproducible automation scripts
└── tests/                          # Automated backend pytest test suites (194 tests)
```

---

## 2. Table Completion Status

| Table | Name | Required Rows | Status | Format Compliance |
| :--- | :--- | :---: | :---: | :--- |
| **Table 1** | Limits Found in the Real Service | 7 limits | **COMPLETE** | Exact 4 columns, explicit confidence ratings, empirical basis documented. |
| **Table 2a** | Latency | 5 scenarios | **COMPLETE** | Exact 7 columns, ms units, p50/p95/p99 percentiles calculated from raw logs. |
| **Table 2b** | Outcomes | 5 scenarios | **COMPLETE** | Exact 8 columns, all percentages formatted to exactly 1 decimal place. |
| **Table 3** | Retrieval Settings | 6 configurations | **COMPLETE** | Exact 9 columns, Stage 8B.2 empirical records, 1 decimal place percentages. |

---

## 3. Exact Source Datasets Used for Every Table

1. **Table 1 (Limits Found in the Real Service):**
   - Source data: `experiments/real_service/raw/groq_baseline.csv` and `experiments/real_service/reports/groq_baseline_summary.json`.
   - Empirically observed response headers: `x-ratelimit-limit-requests: 1000`, `x-ratelimit-limit-tokens: 8000`, `x-ratelimit-remaining-requests`, `x-ratelimit-remaining-tokens`, `x-ratelimit-reset-requests`, `x-ratelimit-reset-tokens`.
   - Documented references: Groq Developer Free Tier documentation for `openai/gpt-oss-120b` (30 RPM).

2. **Table 2a & Table 2b (Load Scenarios A–E Latency and Outcomes):**
   - Source data: `experiments/results.csv` (119 genuine request-level rows) and `experiments/reports/load_experiment_summary.json`.
   - Scenario A: Steady load (15 requests, 30 RPM offered, 100.0% success).
   - Scenario B: Burst (12 requests, 60 RPM offered, 100.0% success, peak queue depth 9).
   - Scenario C: Sustained overload (19 requests, 63.3 RPM offered, 31.6% success, 68.4% timed out/rejected).
   - Scenario D: Per-minute limit halved (23 requests, 23 RPM offered, 78.3% success, 21.7% rate limited, 0.4 retries/req).
   - Scenario E: Daily budget exhausted (10 requests, 60 RPM offered, 70.0% success, 30.0% rate limited, 0.3 retries/req).
   - Pricing basis: Groq official pricing ($0.15 / 1M prompt tokens, $0.60 / 1M completion tokens).

3. **Table 3 (Retrieval Settings):**
   - Source data: `experiments/retrieval/retrieval_results_stage8b2.csv` (192 genuine question evaluations) and `experiments/retrieval/retrieval_summary_stage8b2.json`.
   - Evaluated across 32 self-authored technical questions (26 answerable, 6 unanswerable) across 6 configurations: Dense-only (ChromaDB), BM25-only (Rank-BM25), Hybrid (Dense + BM25), and Full Hybrid (+ FactStore) at $k=5, 8, 10$.

---

## 4. Raw Results CSV Schema Validation

The canonical results file `submission/results.csv` strictly adheres to the required column order and allowed enum definitions:

```csv
request_id,scenario,source,start_time,first_token_ms,total_ms,status,retries,tokens_in,tokens_out,retrieval_setting,answer_grade
```

### Schema & Constraint Validation Results:
- **Column Order:** Verified exact match (12/12 columns in specified order).
- **Request ID Uniqueness:** **311 unique IDs out of 311 total rows (100% unique)**.
- **Allowed `source` Enums:** `real` (20 rows), `stand-in` (291 rows). Zero invalid values.
- **Allowed `status` Enums:** `ok` (290 rows), `rate_limited` (8 rows), `timeout` (5 rows), `error` (8 rows). Zero invalid values.
- **Allowed `answer_grade` Enums:** `correct` (123 rows), `refused_correctly` (36 rows), `wrong` (33 rows), empty/NaN (119 pure load-test rows). Zero invalid values.

---

## 5. Number of Genuine Request-Level Rows Included

- **Total Rows in `submission/results.csv`:** **311 genuine request-level rows**
  - **119 Load-Testing Rows:**
    - 20 real Groq baseline requests (10 streaming probes, 10 non-streaming).
    - 20 calibrated simulator baseline requests.
    - 15 Scenario A requests (Steady load).
    - 12 Scenario B requests (Burst traffic).
    - 19 Scenario C requests (Sustained overload).
    - 23 Scenario D requests (Halved RPM).
    - 10 Scenario E requests (Daily budget exhaustion).
  - **192 Retrieval Benchmark Rows:**
    - 32 questions $\times$ 6 configurations (Dense $k=5$, BM25 $k=5$, Hybrid $k=5$, Full Hybrid $k=5$, Full Hybrid $k=8$, Full Hybrid $k=10$).

---

## 6. Unavailable Raw Fields (Honest Disclosure)

In strict adherence to the **Data Integrity Rule**, no missing data was manufactured:
1. **`start_time` for Retrieval Requests:** The Stage 8B.2 batch evaluation harness recorded per-query elapsed execution durations (`total_latency_ms`), TTFT (`ttft_ms`), token counts, and answer grades, but did not log wall-clock ISO start timestamps. These fields are left blank in `results.csv`.
2. **`first_token_ms` for Non-Streaming Load Requests:** TTFT was measured directly via dedicated Server-Sent Events (SSE) streaming probes (10 real Groq probes, 10 calibration probes, and 13 scenario probes). Non-streaming request rows leave `first_token_ms` blank and are marked as `not measured` in Table 2a.
3. **`tokens_per_day` and `requests_in_flight_at_once` in Table 1:** The Groq API response headers do not return separate TPD counters or explicit concurrency quotas. These cells are marked as `not measured` with confidence `low`.

---

## 7. Actual Two-Page PDF Page Count

- **Rendered PDF Deliverable:** `submission/final_submission.pdf`
- **Verification Engine:** PyMuPDF (`fitz.open("submission/final_submission.pdf")`)
- **Actual Page Count:** **EXACTLY 2 PAGES**
  - **Page 1 Content:** Title block, metadata, Section 1 (What I built and why), Section 2 (The real service and my stand-in), Section 3 (Results with Tables 1, 2a, 2b), Section 4 (Where the time goes), Section 5 (When a limit is hit), Section 6 (Retrieval: quality versus cost with Table 3), and Section 7 (How this library will mislead a naive retriever).
  - **Page 2 Content:** Section 8 (Retries), Section 9 (What the person sees), Section 10 (What I'm unsure about, what I left out, what I learned), Section 11 (Your feedback on Vaani), and Section 12 (How I worked with the assistant).
- **Legibility & Formatting:** Professional Helvetica hierarchy, 6.8 pt body text with 8.6 pt leading, 5.8 pt table text with 0.4 pt borders, high contrast (#0F172A text on white), 26 pt margins. Zero text overlapping or truncation.

---

## 8. Required Heading Verification

All 12 mandatory headings from the original assignment specification are present in `submission/final_submission.md` and `submission/final_submission.pdf` in the exact required sequence:

1. `1. What I built and why` — **PASS**
2. `2. The real service and my stand-in` — **PASS**
3. `3. Results` (includes Tables 1, 2a, 2b) — **PASS**
4. `4. Where the time goes` — **PASS**
5. `5. When a limit is hit` — **PASS**
6. `6. Retrieval: quality versus cost` (includes Table 3) — **PASS**
7. `7. How this library will mislead a naive retriever` — **PASS**
8. `8. Retries` — **PASS**
9. `9. What the person sees` — **PASS**
10. `10. What I'm unsure about, what I left out, what I learned` — **PASS**
11. `11. Your feedback on Vaani` — **PASS** (Clear manual placeholder preserved)
12. `12. How I worked with the assistant` — **PASS** (Clear conversation history placeholder preserved)

---

## 9. README Verification

- **File Path:** `submission/README.md`
- **Prerequisites Covered:** Python 3.12+, `uv`, Node.js 18+ & npm.
- **Windows PowerShell Verification:** All commands formatted and verified for Windows PowerShell (`Copy-Item`, `$env:MODEL_PROVIDER`, `Invoke-RestMethod`, etc.).
- **Zero-Spend Safe Mode:** Fully documented using `.env.example` with local stand-in simulator on port 8001.
- **Service Commands:** Separate step-by-step commands to launch simulator (port 8001), backend (port 8000), and frontend (port 5173).
- **Test Commands:** Documented commands for `uv run pytest` (194 tests) and `npm test --prefix frontend` (54 tests).
- **Deliverable Links:** Explicit clickable links to `final_submission.pdf`, `final_submission.md`, and `results.csv`.

---

## 10. Security & Secret Check

- **Scan Results:** Verified zero active API keys or credentials tracked in `submission/`.
- `.env` is explicitly ignored by `.gitignore`.
- `.env.example` contains safe mock placeholder strings (`mock_key_not_required_for_simulator`).
- Automated codebase pattern scan for `gsk_` and `sk-` confirmed no live API keys exist in source code or committed artifacts.

---

## 11. Missing Items & Status of Manual Inclusions

1. **Gemini / Antigravity Conversation History:** **COMPLETED & ARCHIVED**
   - Full raw trajectory JSONL logs (`gemini_conversation_transcript.jsonl` and `gemini_conversation_transcript_full.jsonl`, 7,026 steps total) and a human-readable Markdown log (`GEMINI_CONVERSATION_HISTORY.md`) covering all 46 user turns and milestone outputs have been sanitized (all real API keys safely redacted) and integrated into `submission/assistant_history/`.
   - Browser subagent trajectory logs (`gemini_browser_subagent_transcript.jsonl`) are also included.

2. **Your Feedback on Vaani (Section 11 of `final_submission.md` / `final_submission.pdf`):**
   - Location: Section 11 placeholder marked `[USER_MANUAL_INPUT_REQUIRED: Insert personal reflection on Vaani Research assignment scope, clarity, and relevance.]`.
   - Action required: Write your authentic personal assessment of the assignment.

3. **External ChatGPT Logs (Optional):**
   - If you also used ChatGPT in earlier architectural discussions, you may append those chat logs into `submission/assistant_history/` or Section 12.

---

## 12. Final Verdict

### **VERDICT: READY AFTER MANUAL ITEMS**

Every technical, experimental, architectural, code, conversation history, and document requirement of the Vaani Research ML Engineering Assignment is **100% complete, verified with empirical evidence, and fully operational**. The deliverable package in `submission/` is ready for final delivery immediately upon the user inserting their personal feedback in Section 11.
