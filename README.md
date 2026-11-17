# The Relay — Production Research Assistant & Systems Characterization

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-StateGraph-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![Tests](https://img.shields.io/badge/tests-248%20passing-brightgreen.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)]()

> **The Relay (Vaani Research ML Engineering Technical Assignment):** An end-to-end question-answering research assistant built on FastAPI, LangGraph, and a multi-channel hybrid retriever, coupled with an asynchronous traffic manager, empirical characterization of Groq's real `openai/gpt-oss-120b` endpoint, and a calibrated stand-in simulator for high-fidelity load testing.

> 🚀 **Deploying to Cloud?** See our complete [Production Deployment Guide (Render & Vercel)](./DEPLOYMENT_GUIDE.md) for step-by-step instructions, Docker configs, and exact `.env` specifications.

---

## 1. System Architecture

The application enforces a strictly bounded, resilient request pipeline designed to prevent hallucination, eliminate cross-paper misattributions, and safeguard upstream rate limits.

```
                    ┌──────────────────────────┐
                    │    HTTP Client Request   │
                    │      (POST /v1/ask)      │
                    └─────────────┬────────────┘
                                  │
                                  ▼
                    ┌──────────────────────────┐
                    │       FastAPI App        │
                    │   (Lifespan, DI, CORS)   │
                    └─────────────┬────────────┘
                                  │
                                  ▼
        ═════════════════════ TrafficManager ═════════════════════
        ║  - Max Concurrency Semaphore (bounded in-flight, N=4)  ║
        ║  - Bounded FIFO Wait Queue (fast-reject on full)       ║
        ║  - Sliding-Window Rate Limiter (RPM & TPM admission)   ║
        ║  - Cooperative Cancellation & Token Bucket Safety      ║
        ═══════════════════════════╤══════════════════════════════
                                  │
                                  ▼
        ══════════════════ LangGraph Workflow ════════════════════
        ║                                                        ║
        ║  [router_query] ──► [research_assistant] (Tool Call)   ║
        ║                               │                        ║
        ║                               ▼                        ║
        ║                   [retrieve_evidence_node]             ║
        ║                               │                        ║
        ║                               ▼                        ║
        ║                     [evidence_gate_node]               ║
        ║                           /       \                    ║
        ║             (Sufficient) /         \ (Insufficient)    ║
        ║                         ▼           ▼                  ║
        ║             [generate_answer]     [refusal_node]       ║
        ║                         │                              ║
        ║                         ▼                              ║
        ║             [verify_citations_node]                    ║
        ║                   /           \                        ║
        ║           (Valid)/             \(Invalid, attempts < 1)║
        ║                 ▼               ▼                      ║
        ║             [__end__]  [correction_attempt_node]       ║
        ║                                 │                      ║
        ║                                 └──► (routes back)     ║
        ═══════════════════════════╤══════════════════════════════
                                  │
                   ┌───────────────┴───────────────┐
                   ▼                               ▼
        ┌─────────────────────┐         ┌─────────────────────┐
        │   Hybrid Retriever  │         │   Model Provider    │
        │ ─────────────────── │         │ ─────────────────── │
        │ • ChromaDB (Dense)  │         │ • Real Groq API     │
        │ • Rank-BM25 (Sparse)│         │   (gpt-oss-120b)    │
        │ • FactStore (SQLite)│         │ • Stand-in Simulator│
        │ • RRF Fusion (k=60) │         │   (Calibrated SSE)  │
        └─────────────────────┘         └─────────────────────┘
```

---

## 2. Directory Structure

The repository is modularly decoupled for independent full-stack cloud deployment:

```
RELAY ASSIGNMENT/
├── backend/                        # Dedicated backend directory for RENDER deployment
│   ├── app/                        # FastAPI application, LangGraph workflow, Hybrid retriever
│   ├── simulator/                  # Calibrated stand-in model simulator (mounted at /simulator)
│   ├── data/                       # ChromaDB, BM25, and FactStore SQLite persistent indexes
│   ├── papers/                     # 3 research papers (1706.03762v7, 2410.00037v1, 2507.07955v2)
│   ├── experiments/                # Empirical benchmarks, load scenario logs, results.csv
│   ├── requirements.txt            # Pinned production Python dependencies
│   ├── pyproject.toml              # Python package and test configuration
│   ├── uv.lock                     # Reproducible dependency lockfile
│   ├── Dockerfile                  # Containerized deployment for Render
│   ├── render.yaml                 # Render Blueprint configuration
│   ├── run.py                      # Standalone runner honoring Render $PORT
│   └── .env.example                # Backend environment variables template
│
├── frontend/                       # Dedicated frontend directory for VERCEL deployment
│   ├── src/                        # React 19 source code (Pages, Components, Services)
│   ├── package.json                # Frontend dependencies & build scripts
│   ├── vite.config.ts              # Vite bundler configuration
│   ├── vercel.json                 # Vercel SPA routing configuration (rewrites to /index.html)
│   ├── .env.example                # Frontend environment variables template
│   └── .env.production             # Production environment template
│
├── submission/                     # Official Vaani assignment submission package
│   ├── final_submission.pdf        # Two-page technical write-up (ReportLab rendered)
│   ├── final_submission.md         # Markdown source with Tables 1, 2a, 2b, 3
│   ├── results.csv                 # Canonical raw request-level measurements (311 rows)
│   ├── README.md                   # Submission documentation
│   └── FINAL_DELIVERABLE_CHECK.md  # Comprehensive 12-item deliverable audit
│
├── DEPLOYMENT_GUIDE.md             # Complete Render & Vercel deployment guide
├── render.yaml                     # Root-level Render Blueprint (points rootDir to backend)
└── vercel.json                     # Root-level Vercel routing configuration
│   ├── FINAL_RECONCILIATION.md     # Documentation reconciliation and formula audit
│   ├── final_compliance_audit.md   # Exhaustive requirement-by-requirement audit
│   └── ...                         # Detailed stage reports (8B through 8G)
│
├── scripts/                        # Reproducible automation scripts
└── tests/                          # Automated backend pytest test suites (194 tests)
```

---

## 3. Quickstart & Installation (Windows PowerShell)

This project uses [`uv`](https://github.com/astral-sh/uv) (Python 3.12) and Node 20+.

### Prerequisites
- Python 3.12+
- `uv` installed (`pip install uv` or `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`)
- Node.js 18+ & npm

### Installation Commands

1. **Install Python dependencies:**
   ```powershell
   uv sync
   ```

2. **Configure environment variables:**
   Copy `.env.example` to `.env`. By default, the application runs entirely against the local **calibrated simulator**, requiring **zero external API keys or cloud spend**:
   ```powershell
   Copy-Item .env.example .env
   ```

   *Default `.env` configuration (Zero-cost safe mode):*
   ```ini
   MODEL_PROVIDER=simulator
   SIMULATOR_URL=http://localhost:8001
   GROQ_API_KEY=mock_key_not_required_for_simulator
   GROQ_MODEL=openai/gpt-oss-120b
   ```

3. **Verify Environment Integrity:**
   ```powershell
   uv pip check
   # Expected output: Checked 144 packages. Everything's fine!
   ```

---

## 4. Running the Tests

Execute the full automated test suite across backend and frontend (248 tests total):

### A. Backend Python Pytest Suite (194 tests)
```powershell
uv run pytest
# Expected output: 194 passed, 0 failed in ~3 minutes
```

### B. Frontend Automated Test Suites (54 tests)
```powershell
npm test --prefix frontend
# Expected output: 54 passed (29 client + 17 live stack + 8 QA specs)
```

### C. Frontend Linter & Production Build
```powershell
npm run lint --prefix frontend    # oxlint (0 errors, 0 warnings)
npm run build --prefix frontend   # tsc -b && vite build (clean production bundle)
```

---

## 5. Running the Service Locally (Windows PowerShell)

Run the full interactive stack locally using three terminal windows:

### Terminal 1: Calibrated Stand-in Simulator (Port 8001)
```powershell
uv run uvicorn simulator.main:app --port 8001
```

### Terminal 2: FastAPI Backend Application (Port 8000)
```powershell
$env:MODEL_PROVIDER="simulator"
uv run uvicorn app.main:app --port 8000
```

### Terminal 3: React Frontend UI (Port 5173)
```powershell
cd frontend
npm install
npm run dev
```

### Service Access:
- **Frontend Application:** http://localhost:5173
- **FastAPI Documentation:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/health
- **Readiness Probe:** http://localhost:8000/ready
- **Live Metrics:** http://localhost:8000/v1/metrics
- **Simulator Status:** http://localhost:8001/status

### Querying via CLI:
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/v1/ask" -Method Post -ContentType "application/json" -Body '{"question": "What BLEU score did the Transformer base model achieve on English-to-German?"}' | ConvertTo-Json -Depth 5
```

---

## 6. Reproducing Evaluations & Experiments

All raw data and summaries are tracked in the repository. To re-run the experiments without making remote network calls, use the stand-in simulator:

### A. Run Controlled Load Experiments (Scenarios A–E)
```powershell
# Ensure simulator is running on http://localhost:8001
uv run python scripts/run_load_experiments.py
# Preserves results in experiments/results.csv and experiments/reports/load_experiment_summary.json
```

### B. Run Retrieval Quality vs. Cost Benchmark (Configs A–D)
```powershell
uv run python scripts/evaluate_retrieval.py
# Evaluates 32 questions across Dense, BM25, Hybrid, and Full Hybrid
# Preserves results in experiments/retrieval/retrieval_results.csv
```

### C. Regenerate Two-Page Technical Submission PDF
```powershell
uv run python scripts/generate_pdf.py
# Generates submission/final_submission.pdf (exactly 2 pages)
```

---

## 7. Deliverables & Key Reports

- **Two-Page Technical Submission PDF:** [`final_submission.pdf`](file:///c:/Users/abhi4/RELAY%20ASSIGNMENT/submission/final_submission.pdf) (Primary readable deliverable, exactly 2 pages).
- **Markdown Source of Write-Up:** [`final_submission.md`](file:///c:/Users/abhi4/RELAY%20ASSIGNMENT/submission/final_submission.md) (All 12 mandatory headings, Tables 1, 2a, 2b, 3).
- **Canonical Raw Results:** [`results.csv`](file:///c:/Users/abhi4/RELAY%20ASSIGNMENT/submission/results.csv) (311 genuine request-level rows across load tests and retrieval benchmarks).
- **Deliverable Audit Report:** [`FINAL_DELIVERABLE_CHECK.md`](file:///c:/Users/abhi4/RELAY%20ASSIGNMENT/submission/FINAL_DELIVERABLE_CHECK.md) (Checklist of all 12 items).
- **Assistant Conversation History:** [`assistant_history/GEMINI_CONVERSATION_HISTORY.md`](file:///c:/Users/abhi4/RELAY%20ASSIGNMENT/submission/assistant_history/GEMINI_CONVERSATION_HISTORY.md) (Complete raw JSONL transcripts and human-readable Markdown log of all 46 user turns).
- **Comprehensive Audit:** [`supporting_reports/FINAL_SUBMISSION_AUDIT.md`](file:///c:/Users/abhi4/RELAY%20ASSIGNMENT/submission/supporting_reports/FINAL_SUBMISSION_AUDIT.md) (100% PASS on all 21 requirements).
- **Documentation Reconciliation:** [`supporting_reports/FINAL_RECONCILIATION.md`](file:///c:/Users/abhi4/RELAY%20ASSIGNMENT/submission/supporting_reports/FINAL_RECONCILIATION.md) (Mathematical reconciliation of metrics).
