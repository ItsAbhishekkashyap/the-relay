# Stage 8E Implementation Report: Experiment Analytics Dashboard

**Project:** The Relay — Vaani Research ML Engineering Assignment  
**Stage:** 8E — Experiment Analytics Dashboard  
**Role:** Frontend & Backend Integration Engineer  
**Date:** November 14, 2026  
**Status:** Complete & Fully Validated against Local Simulator & Preserved Data  

---

## 1. Executive Summary

Stage 8E transforms the experiment visualization interface (`frontend/src/pages/ExperimentsPage.tsx`) from a static Stage 8A placeholder into a full-featured, data-driven **Experiment Analytics Dashboard**. The page presents the empirical characterization and benchmark evaluations completed across Stages 4, 5, 6, and 8B.2.

Key architectural and methodological principles enforced throughout Stage 8E:
1. **Strictly Read-Only Data Access:** Historical raw CSVs (`experiments/results.csv`, `experiments/retrieval/retrieval_results*.csv`) and statistical summaries (`experiments/reports/load_experiment_summary.json`, `experiments/retrieval/retrieval_summary*.json`) are read safely without any modifications or write attempts.
2. **Explicit Provenance & Source Separation:** Real Groq cloud measurements (`openai/gpt-oss-120b`) and local HTTP stand-in simulator runs are visually separated with distinctive color badges (`REAL GROQ API` in blue vs. `STAND-IN SIMULATOR` in purple). Real and simulated data are never conflated.
3. **Rigorous Methodological Denominators:** Retrieval benchmarks explicitly separate the denominator for Recall@$k$ and MRR (strictly evaluated across the 26 answerable questions) from the denominator for overall system accuracy, wrong answer rates, and correct refusal rates (evaluated across all 32 questions).
4. **Direct Stage 6 vs. Stage 8B.2 Comparative Deltas:** The dashboard contrasts the baseline chunking of Stage 6 against the caption-preserved chunking and top-$k$ scaling of Stage 8B.2, presenting quantifiable improvement deltas across Dense, BM25, Hybrid, and Full Hybrid configurations.
5. **Zero Cloud API Requests:** All backend endpoints, frontend components, and automated test suites ran strictly against preserved historical artifacts and the local simulator (`http://127.0.0.1:8001`) with **zero Groq API calls** and zero financial cost.

---

## 2. Files Changed and Created

| File | Status | Description |
| :--- | :--- | :--- |
| `app/experiments/service.py` | Created | Safe read-only data access layer that reads, parses, and structures historical CSV/JSON experiment artifacts for API consumers. |
| `app/api/routes.py` | Modified | Exposed three read-only experiment endpoints: `GET /v1/experiments/overview`, `GET /v1/experiments/load`, and `GET /v1/experiments/retrieval`. |
| `frontend/src/types/api.ts` | Modified | Defined TypeScript schemas: `LoadScenarioStats`, `CalibrationComparison`, `LoadExperimentsResponse`, `RetrievalConfigStats`, `RetrievalComparisonItem`, `TopKScalingItem`, `RetrievalExperimentsResponse`, and `ExperimentsOverviewResponse`. |
| `frontend/src/services/api.ts` | Modified | Added typed client methods: `getExperimentsOverview()`, `getLoadExperiments()`, and `getRetrievalExperiments(version)`. |
| `frontend/src/pages/ExperimentsPage.tsx` | Rewritten | Interactive analytics page with 3 primary tabs (Traffic Dynamics, Retrieval Quality & Cost Frontier, Datasets & Pricing Basis), source filters, scenario selectors, and custom SVG/Tailwind charts. |
| `tests/test_api.py` | Modified | Added 3 backend integration tests validating HTTP 200 contracts and data integrity for all three experiment endpoints. |
| `frontend/tests/client.test.ts` | Modified | Added mock server handlers and Tests 27–29 validating client deserialization for overview, load, and retrieval endpoints. |
| `frontend/tests/e2e_live_stack.test.ts` | Modified | Added Tests 15–17 validating live proxy resolution (`http://localhost:5173/v1/experiments/*`) against the active backend. |
| `reports/stage_8e_experiment_analytics.md` | Created | This deliverable implementation report. |

---

## 3. Preserved Experiment Data Artifacts Consumed

The backend service directly consumes the authoritative historical artifacts generated during prior project stages:

| Artifact Path | Format | Records | Stage | Contents |
| :--- | :--- | :--- | :--- | :--- |
| `experiments/results.csv` | CSV | 119 rows | Stages 4 & 5 | Raw per-request measurements for real Groq baseline (20), simulator calibration baseline (20), and Scenarios A–E (79). |
| `experiments/reports/load_experiment_summary.json` | JSON | 7 scenarios | Stage 5 | Pre-computed statistical percentiles (p50, p95, p99, min, max, TTFT), retry rates, and token/cost projections. |
| `experiments/retrieval/retrieval_summary.json` | JSON | 4 configs | Stage 6 | Stage 6 baseline retrieval evaluation (Dense, BM25, Hybrid, Full Hybrid at $k=5$) over 32 questions. |
| `experiments/retrieval/retrieval_summary_stage8b2.json` | JSON | 6 configs | Stage 8B.2 | Stage 8B.2 caption-preserved evaluation (Dense, BM25, Hybrid, Full Hybrid at $k=5, 8, 10$) over 32 questions. |
| `experiments/retrieval/retrieval_results.csv` | CSV | 128 rows | Stage 6 | Question-level retrieval results for Stage 6 ($4 \times 32$ evaluations). |
| `experiments/retrieval/retrieval_results_stage8b2.csv` | CSV | 192 rows | Stage 8B.2 | Question-level retrieval results for Stage 8B.2 ($6 \times 32$ evaluations). |

---

## 4. Backend API Contracts Implemented

### A. `GET /v1/experiments/overview`
Returns a point-in-time catalog of available datasets, pricing constants, and record counts.
- **Pricing Basis:**
  - Prompt tokens: \$0.15 per 1,000,000 tokens
  - Completion tokens: \$0.60 per 1,000,000 tokens
- **Datasets:** Load testing availability (119 records) and retrieval benchmarks (Stage 6 with 4 configs, Stage 8B.2 with 6 configs).

### B. `GET /v1/experiments/load`
Returns comprehensive metrics across all 7 load testing scenarios:
1. `real_baseline`: 20 requests against live Groq cloud API.
2. `calibration_baseline`: 20 requests against simulator with lognormal latency.
3. `scenario_a_steady`: 15 requests at steady 15 RPM.
4. `scenario_b_burst`: 12 concurrent requests injected simultaneously.
5. `scenario_c_overload`: 15 concurrent flood requests (queue saturation) + 4 recovery probes.
6. `scenario_d_halved_rpm`: 20 requests offered at 45 RPM into 15 RPM limit + 3 recovery probes.
7. `scenario_e_daily_budget`: 10 requests consuming 5 RPD budget + admin reset recovery.

**Simulator Calibration Fidelity Highlight:**
- Real Groq median non-streaming latency: 1031.0 ms
- Simulator median non-streaming latency: 1033.79 ms
- **Turnaround Difference:** 2.79 ms (**0.27% difference**)
- Real Groq streaming TTFT median: 852.0 ms
- Simulator streaming TTFT median: 855.26 ms
- **TTFT Difference:** 3.26 ms (**0.38% difference**)

### C. `GET /v1/experiments/retrieval` (Optional query param: `version`)
Returns retrieval evaluation metrics, question denominators, Stage 6 vs. Stage 8B.2 comparative deltas, and top-$k$ scaling frontiers.
- **Denominators:**
  - `total_questions`: 32
  - `answerable_questions`: 26
  - `unanswerable_questions`: 6
  - `recall_and_mrr_basis`: "Answerable questions only (denominator: 26)"
  - `accuracy_and_refusal_basis`: "All questions (denominator: 32)"

---

## 5. Empirical Results & Findings

### A. Stage 6 vs. Stage 8B.2 Comparative Deltas ($k=5$)

Table caption preservation in Stage 8B.2 measurably improved retrieval across all configurations without changing embedding models or prompt engineering:

| Configuration | Metric | Stage 6 Baseline | Stage 8B.2 (Captions) | Improvement Delta |
| :--- | :--- | :--- | :--- | :--- |
| **Dense-only (ChromaDB)** | Recall@5 | 57.69% (15/26) | 69.23% (18/26) | **+11.54%** |
| | MRR | 0.3814 | 0.4487 | **+0.0673** |
| | Accuracy (32 qs) | 56.25% (18/32) | 65.62% (21/32) | **+9.38%** |
| **BM25-only (Rank-BM25)** | Recall@5 | 69.23% (18/26) | 76.92% (20/26) | **+7.69%** |
| | MRR | 0.4904 | 0.5096 | **+0.0192** |
| | Accuracy (32 qs) | 65.62% (21/32) | 71.88% (23/32) | **+6.25%** |
| **Hybrid (Dense + BM25)** | Recall@5 | 73.08% (19/26) | 76.92% (20/26) | **+3.84%** |
| | MRR | 0.5353 | 0.5577 | **+0.0224** |
| | Accuracy (32 qs) | 71.88% (23/32) | 75.00% (24/32) | **+3.12%** |
| **Full Hybrid (+ FactStore)**| Recall@5 | 84.62% (22/26) | 88.46% (23/26) | **+3.84%** |
| | MRR | 0.5609 | 0.6122 | **+0.0513** |
| | Accuracy (32 qs) | 78.12% (25/32) | 84.38% (27/32) | **+6.25%** |

### B. Top-$k$ Scaling Frontier in Stage 8B.2

Expanding the retrieved context window from $k=5$ to $k=8$ and $k=10$ on the Full Hybrid retriever demonstrates the recall-cost trade-off:

| Context Depth | Recall@$k$ (26 qs) | MRR | Correct & Cited (32 qs) | Wrong Answers | Avg Context Tokens | Cost / 1k Queries |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **$k = 5$** | 76.92% (20/26) | 0.5141 | 62.50% (20/32) | 6 (18.75%) | 1,415.8 tokens | \$0.3474 |
| **$k = 8$** | 84.62% (22/26) | 0.5266 | 68.75% (22/32) | 4 (12.50%) | 2,207.2 tokens | \$0.4876 |
| **$k = 10$** | 88.46% (23/26) | 0.5321 | 71.88% (23/32) | 3 (9.38%) | 2,762.0 tokens | \$0.5901 |

**Frontier Takeaway:** Increasing context depth from $k=5$ to $k=10$ increases recall by 11.54% (+3 answerable questions retrieved) and cuts wrong answers in half (from 6 to 3), at the expense of a 69.9% increase in context token cost (\$0.5901 vs. \$0.3474 per 1,000 queries).

---

## 6. Frontend Visualizations & User Interface Features

The Experiment Analytics page (`frontend/src/pages/ExperimentsPage.tsx`) provides three primary tabs:

### Tab 1: Load Stress & Traffic Dynamics
- **Fidelity Comparison Card:** Highlights the 0.27% non-streaming latency delta and 0.38% TTFT delta between real Groq and the simulator.
- **Source Filter & Scenario Dropdown:** Allows filtering by source (`All`, `Real Groq Only`, `Simulator Only`) or selecting a specific scenario.
- **Per-Scenario Cards:**
  - Distinctive badges: Blue `REAL GROQ API` vs. Purple `STAND-IN SIMULATOR`.
  - Stacked horizontal status distribution bar (200 OK in green, 429 in amber, 504 in rose, 500 in red).
  - Six-tile KPI grid: Median turnaround, p95 latency, max latency, streaming TTFT, total retries (with avg per request), and cost per 1,000 queries.
  - Detailed traffic pattern and scenario description callouts.

### Tab 2: Retrieval Quality & Cost Frontier
- **Denominator & Methodology Banner:** Explains the 26 vs. 32 question basis to eliminate evaluation ambiguity.
- **View Switcher:**
  1. *Stage 6 vs. Stage 8B.2 Deltas:* Side-by-side comparative cards with dual progress bars for Recall@5 and Accuracy, displaying exact green improvement deltas (`+11.54%`, `+7.69%`, etc.).
  2. *Stage 8B.2 Configurations:* Cards for all 6 configurations with top-$k$ dropdown filtering ($k=5, 8, 10$).
  3. *Top-k Scaling Frontier:* Multi-column scaling comparison analyzing recall gains against token cost expansion.
  4. *Stage 6 Benchmark:* Historical baseline cards prior to table caption preservation.

### Tab 3: Datasets & Pricing Basis
- **Pricing Card:** Documents the \$0.15/1M prompt token and \$0.60/1M completion token rate structure.
- **File Manifest:** Interactive manifest listing all 6 historical CSV and JSON data files with exact row counts and verification statuses.

---

## 7. Verification and Test Results

### A. Linter & Static Analysis
```bash
npm run lint --prefix frontend
# Output:
# > frontend@0.0.0 lint
# > oxlint
# Found 0 warnings and 0 errors.
# Finished in 484ms on 26 files with 116 rules using 12 threads.
```

### B. TypeScript & Vite Production Build
```bash
npm run build --prefix frontend
# Output:
# > frontend@0.0.0 build
# > tsc -b && vite build
# vite v8.3.8 building client environment for production...
# transforming...
# ✓ 2103 modules transformed.
# rendering chunks...
# ✓ built in 6.18s
```

### C. Frontend Automated Tests (Client & Live E2E)
```bash
npm test --prefix frontend
# Output:
# ▶ Frontend API Client & Contract Tests
#   ✔ Tests 1–26 (Chat, Readiness, Metrics, Simulator controls)
#   ✔ 27. Stage 8E Experiment API: GET /v1/experiments/overview returns dataset catalog
#   ✔ 28. Stage 8E Experiment API: GET /v1/experiments/load returns load scenarios and calibration comparison
#   ✔ 29. Stage 8E Experiment API: GET /v1/experiments/retrieval returns retrieval benchmarks and comparisons
#   ✔ Frontend API Client & Contract Tests (395.3ms) [29 passed, 0 failed]
#
# ▶ Stage 8B Live Stack E2E Validation (Vite -> FastAPI -> Simulator)
#   ✔ Tests 1–14 (Live chat, BLEU 27.3, refusals, metrics, simulator dynamic fault injection)
#   ✔ 15. Stage 8E Live E2E: GET /v1/experiments/overview returns dataset catalog
#   ✔ 16. Stage 8E Live E2E: GET /v1/experiments/load returns 7 scenarios and calibration comparison
#   ✔ 17. Stage 8E Live E2E: GET /v1/experiments/retrieval returns benchmark matrix and scaling frontier
#   ✔ Stage 8B Live Stack E2E Validation (16535.3ms) [17 passed, 0 failed]
# Total: 46 passed, 0 failed.
```

### D. Backend Pytest Suite
```bash
uv run pytest tests/test_api.py -k experiment
# Output:
# tests/test_api.py::test_experiments_overview_endpoint PASSED
# tests/test_api.py::test_experiments_load_endpoint PASSED
# tests/test_api.py::test_experiments_retrieval_endpoint PASSED
# 3 passed, 17 deselected in 19.03s
```

---

## 8. Integrity Commitments & Safety Verification

1. **Zero Modifications to Source Experiment Files:** `experiments/results.csv`, `experiments/retrieval/retrieval_results.csv`, `experiments/retrieval/retrieval_results_stage8b2.csv`, and all summary JSONs remain byte-identical to their original state.
2. **Zero Cloud LLM Requests:** The test suite and live application ran strictly with `MODEL_PROVIDER=simulator`, ensuring zero Groq requests, zero quota consumption, and zero external network calls.
3. **No Fabricated Fallback Metrics:** In the event of missing or corrupt disk files, the backend explicitly returns HTTP 200 with `available: false` and descriptive error details, rather than generating synthetic data.
4. **Clean Scope Boundary:** Stage 8E is strictly completed. No premature Stage 8F features or unrelated architectural modifications were introduced.
