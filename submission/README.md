# The Relay

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-StateGraph-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![Tests](https://img.shields.io/badge/tests-248%20passing-brightgreen.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)]()

My submission for the Vaani Research ML Engineering assignment. It is a question-answering assistant for three research papers, built with FastAPI, LangGraph and a hybrid retriever. It sits behind an async traffic manager. I measured how Groq's `openai/gpt-oss-120b` endpoint behaves under load, then built a simulator calibrated to those measurements so I could run heavier load tests without spending money.

---

## 1. How it works

A request goes through a bounded queue first, then a LangGraph workflow that retrieves evidence, decides whether there is enough of it, answers, and checks its own citations. If the evidence is too thin, it refuses instead of guessing.

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

## 2. What's in the repo

```
submission/
├── final_submission.pdf            # 2-page write-up (Tables 1, 2a, 2b, 3)
├── final_submission.md             # Markdown source of the write-up
├── results.csv                     # Raw request-level measurements (311 rows)
├── README.md                       # This file
├── FINAL_DELIVERABLE_CHECK.md      # Checklist against the assignment brief
├── requirements.txt                # Pinned dependencies
├── pyproject.toml                  # Package and test configuration
├── uv.lock                         # Dependency lockfile
├── .env.example                    # Environment template (defaults to the simulator)
├── .gitignore                      # Ignores .env, node_modules, caches
│
├── app/                            # Backend
│   ├── api/                        # FastAPI routes and schemas
│   ├── providers/                  # Groq and simulator providers
│   ├── retrieval/                  # Dense, BM25, FactStore, hybrid RRF, LangChain chunking
│   ├── traffic/                    # Async TrafficManager (queue, rate limiting)
│   ├── workflow/                   # LangGraph 8-node workflow
│   ├── config.py                   # Pydantic v2 settings
│   └── main.py                     # FastAPI app factory
│
├── simulator/                      # Stand-in model service
│   ├── config.py                   # Lognormal latency and rate-limit parameters
│   ├── service.py                  # SSE streaming and error injection
│   └── main.py                     # FastAPI simulator app
│
├── frontend/                       # React dashboard
│   ├── src/pages/                  # Chat, Overview, Analytics, Simulator Controls
│   ├── src/components/
│   └── tests/                      # Vitest suites
│
├── papers/                         # The 3 target papers (120 pages total)
│   ├── 1706.03762v7.pdf            # Attention Is All You Need (Vaswani et al.)
│   ├── 2410.00037v1.pdf            # Moshi: a speech-text foundation model (Defossez et al.)
│   └── 2507.07955v2.pdf            # Dynamic Chunking for Long-Context Retrieval (Shao et al.)
│
├── data/
│   ├── extracted/                  # Blocks and tables pulled out with PyMuPDF
│   ├── chunks/                     # Token-aware LangChain chunks (512 tokens, 76 overlap)
│   └── indexes/                    # ChromaDB, BM25 index, FactStore SQLite
│
├── experiments/                    # Raw experiment data
│   ├── real_service/               # Groq baseline (20 raw records)
│   ├── simulator/                  # Simulator calibration runs
│   ├── retrieval/                  # Stage 6 (128 records) and Stage 8B.2 (192 records) CSVs
│   ├── results.csv                 # 119 load-test request records
│   └── reports/                    # JSON summaries
│
├── assistant_history/              # Conversation logs with the AI assistant
│   ├── GEMINI_CONVERSATION_HISTORY.md                # Readable log of all 46 user turns
│   ├── gemini_conversation_transcript.jsonl          # Compact raw log (7,026 steps)
│   ├── gemini_conversation_transcript_full.jsonl     # Raw log with full tool payloads
│   ├── gemini_browser_subagent_transcript.jsonl      # Chrome DevTools browser subagent log
│   └── README.md
│
├── supporting_reports/             # Audits and stage reports
│   ├── FINAL_SUBMISSION_AUDIT.md   # Audit of the 21 requirements
│   ├── FINAL_RECONCILIATION.md     # Doc reconciliation and formula check
│   ├── final_compliance_audit.md   # Requirement-by-requirement audit
│   └── ...                         # Stage reports (8B through 8G)
│
├── scripts/                        # Automation scripts
└── tests/                          # Backend pytest suites (194 tests)
```

---

## 3. Setup (Windows PowerShell)

This project uses [`uv`](https://github.com/astral-sh/uv) with Python 3.12, plus Node.js for the frontend.

### Prerequisites

- Python 3.12+
- `uv` (`pip install uv` or `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`)
- Node.js 18+ and npm

### Install

1. Install Python dependencies:
   ```powershell
   uv sync
   ```

2. Copy the environment template:
   ```powershell
   Copy-Item .env.example .env
   ```

   By default the app talks to the local simulator, so you need no API key and spend nothing. The default `.env`:
   ```ini
   MODEL_PROVIDER=simulator
   SIMULATOR_URL=http://localhost:8001
   GROQ_API_KEY=mock_key_not_required_for_simulator
   GROQ_MODEL=openai/gpt-oss-120b
   ```

3. Check the environment:
   ```powershell
   uv pip check
   # Expected output: Checked 144 packages. Everything's fine!
   ```

---

## 4. Tests

There are 248 tests in total: 194 backend and 54 frontend.

### Backend (pytest, 194 tests)
```powershell
uv run pytest
# Expected output: 194 passed, 0 failed in ~3 minutes
```

### Frontend (54 tests)
```powershell
npm test --prefix frontend
# Expected output: 54 passed (29 client + 17 live stack + 8 QA specs)
```

### Lint and production build
```powershell
npm run lint --prefix frontend    # oxlint (0 errors, 0 warnings)
npm run build --prefix frontend   # tsc -b && vite build
```

---

## 5. Running it locally (Windows PowerShell)

Open three terminals.

### Terminal 1: simulator (port 8001)
```powershell
uv run uvicorn simulator.main:app --port 8001
```

### Terminal 2: backend (port 8000)
```powershell
$env:MODEL_PROVIDER="simulator"
uv run uvicorn app.main:app --port 8000
```

### Terminal 3: frontend (port 5173)
```powershell
cd frontend
npm install
npm run dev
```

### Where things are

- Frontend: http://localhost:5173
- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health
- Readiness probe: http://localhost:8000/ready
- Live metrics: http://localhost:8000/v1/metrics
- Simulator status: http://localhost:8001/status

### Asking a question from the command line
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/v1/ask" -Method Post -ContentType "application/json" -Body '{"question": "What BLEU score did the Transformer base model achieve on English-to-German?"}' | ConvertTo-Json -Depth 5
```

---

## 6. Re-running the experiments

All raw data and summaries are in the repo. To re-run without any remote calls, use the simulator.

### Load experiments (scenarios A to E)
```powershell
# Make sure the simulator is running on http://localhost:8001
uv run python scripts/run_load_experiments.py
# Writes experiments/results.csv and experiments/reports/load_experiment_summary.json
```

### Retrieval quality vs. cost (configs A to D)
```powershell
uv run python scripts/evaluate_retrieval.py
# Runs 32 questions across Dense, BM25, Hybrid and Full Hybrid
# Writes experiments/retrieval/retrieval_results.csv
```

### Rebuild the 2-page PDF
```powershell
uv run python scripts/generate_pdf.py
# Writes submission/final_submission.pdf (2 pages)
```

---

## 7. Where to look first

- [`final_submission.pdf`](final_submission.pdf): the 2-page write-up. Start here.
- [`final_submission.md`](final_submission.md): the same write-up as Markdown, with all 12 required headings and Tables 1, 2a, 2b and 3.
- [`results.csv`](results.csv): 311 request-level rows from the load tests and the retrieval benchmark.
- [`FINAL_DELIVERABLE_CHECK.md`](FINAL_DELIVERABLE_CHECK.md): the checklist against the assignment brief.
- [`assistant_history/GEMINI_CONVERSATION_HISTORY.md`](assistant_history/GEMINI_CONVERSATION_HISTORY.md): readable log of all 46 user turns. The raw JSONL transcripts are in the same folder.
- [`supporting_reports/FINAL_SUBMISSION_AUDIT.md`](supporting_reports/FINAL_SUBMISSION_AUDIT.md): audit of the 21 requirements.
- [`supporting_reports/FINAL_RECONCILIATION.md`](supporting_reports/FINAL_RECONCILIATION.md): reconciliation of the reported metrics.