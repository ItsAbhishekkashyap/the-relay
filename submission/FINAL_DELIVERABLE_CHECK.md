
# Final Deliverable Check

**Project:** The Relay, Vaani Research ML Engineering assignment
**Checked against:** the original 4-page assignment brief (pages 2 to 4)
**Date:** November 14, 2026

## 1. What is in `submission/`

```
submission/
├── final_submission.pdf          # 2-page write-up
├── final_submission.md           # Markdown source: 12 headings, 4 tables
├── results.csv                   # Raw request-level data, 311 rows
├── README.md                     # Setup and reproduction steps (tested in PowerShell)
├── FINAL_DELIVERABLE_CHECK.md    # This report
├── requirements.txt
├── pyproject.toml
├── uv.lock
├── .env.example                  # Defaults to the local simulator, no API key needed
├── .gitignore                    # Ignores .env, node_modules, caches, *.db
│
├── app/                          # Backend
│   ├── api/                      # /health, /ready, /v1/ask, /v1/metrics, /v1/experiments/*
│   ├── providers/                # Groq Cloud and simulator integrations
│   ├── retrieval/                # Ingestion, 512/76 chunking, ChromaDB, BM25, FactStore, RRF
│   ├── traffic/                  # Async TrafficManager: FIFO queue, semaphore N=4, RPM/TPM limiters
│   ├── workflow/                 # LangGraph 8-node workflow with a citation check
│   ├── config.py                 # Pydantic v2 settings
│   └── main.py                   # FastAPI app factory
│
├── simulator/                    # Stand-in model service
│   ├── config.py                 # Lognormal latency (mu=6.94, sigma=0.22) and rate limits
│   ├── service.py                # SSE streaming and error injection
│   └── main.py
│
├── frontend/                     # Dashboard
│   ├── src/pages/                # Research Chat, System Overview, Experiment Analytics, Simulator Controls
│   ├── src/components/
│   └── tests/                    # 54 Vitest tests
│
├── papers/                       # The 3 required papers (120 pages total)
│   ├── 1706.03762v7.pdf          # Attention Is All You Need
│   ├── 2410.00037v1.pdf          # Moshi
│   └── 2507.07955v2.pdf          # Dynamic Chunking for Long-Context Retrieval
│
├── data/
│   ├── extracted/                # PyMuPDF blocks and tables
│   ├── chunks/                   # 512-token chunks, 76 overlap
│   └── indexes/                  # ChromaDB, BM25 index, FactStore SQLite
│
├── experiments/
│   ├── real_service/             # Groq baseline (20 rows in groq_baseline.csv)
│   ├── simulator/                # Calibration runs
│   ├── retrieval/                # Stage 6 (128 rows) and Stage 8B.2 (192 rows)
│   ├── results.csv               # 119 load-test rows
│   └── reports/                  # JSON summaries
│
├── assistant_history/
│   ├── GEMINI_CONVERSATION_HISTORY.md                # Readable log of all 46 user turns
│   ├── gemini_conversation_transcript.jsonl          # Compact raw log, 7,026 steps
│   ├── gemini_conversation_transcript_full.jsonl     # Raw log with full tool payloads
│   ├── gemini_browser_subagent_transcript.jsonl      # Browser subagent log
│   └── README.md
│
├── supporting_reports/           # Audits and stage reports (8B to 8G)
├── scripts/
└── tests/                        # 194 pytest tests
```

## 2. Tables

| Table | Name | Rows | Status | Notes |
| :--- | :--- | :---: | :---: | :--- |
| 1 | Limits found in the real service | 7 | Done | 4 columns, confidence rating per limit, basis stated |
| 2a | Latency | 5 scenarios | Done | 7 columns, ms, p50/p95/p99 from the raw logs |
| 2b | Outcomes | 5 scenarios | Done | 8 columns, percentages to 1 decimal |
| 3 | Retrieval settings | 6 configs | Done | 9 columns, from Stage 8B.2, percentages to 1 decimal |

## 3. Where each table's numbers come from

**Table 1.** `experiments/real_service/raw/groq_baseline.csv` and `groq_baseline_summary.json`. Headers seen in responses: `x-ratelimit-limit-requests: 1000`, `x-ratelimit-limit-tokens: 8000`, plus the matching `remaining` and `reset` headers. The 30 RPM figure for `openai/gpt-oss-120b` comes from Groq's free-tier docs.

**Tables 2a and 2b.** `experiments/results.csv` (119 rows) and `reports/load_experiment_summary.json`.

- A, steady load: 15 requests, 30 RPM offered, 100.0% success.
- B, burst: 12 requests, 60 RPM offered, 100.0% success, peak queue depth 9.
- C, sustained overload: 19 requests, 63.3 RPM offered, 31.6% success, 68.4% timed out or rejected.
- D, per-minute limit halved: 23 requests, 23 RPM offered, 78.3% success, 21.7% rate limited, 0.4 retries per request.
- E, daily budget exhausted: 10 requests, 60 RPM offered, 70.0% success, 30.0% rate limited, 0.3 retries per request.
- Cost uses Groq's published prices: $0.15 per 1M prompt tokens, $0.60 per 1M completion tokens.

**Table 3.** `experiments/retrieval/retrieval_results_stage8b2.csv` (192 evaluations) and `retrieval_summary_stage8b2.json`. I wrote 32 questions (26 answerable, 6 unanswerable) and ran them against 6 setups: dense only (ChromaDB), BM25 only, hybrid (dense + BM25), and full hybrid (plus FactStore) at k=5, 8 and 10.

## 4. `results.csv` schema

Columns, in the required order:

```
request_id,scenario,source,start_time,first_token_ms,total_ms,status,retries,tokens_in,tokens_out,retrieval_setting,answer_grade
```

- All 12 columns are present and in order.
- 311 rows, 311 unique request IDs.
- `source`: `real` 20, `stand-in` 291.
- `status`: `ok` 290, `rate_limited` 8, `timeout` 5, `error` 8.
- `answer_grade`: `correct` 123, `refused_correctly` 36, `wrong` 33, blank 119 (the load-test rows).
- No values outside the allowed sets.

## 5. Row counts

311 rows in total.

Load testing, 119 rows:

- 20 real Groq baseline requests (10 streaming probes, 10 non-streaming)
- 20 simulator baseline requests
- Scenario A 15, B 12, C 19, D 23, E 10

Retrieval benchmark, 192 rows: 32 questions across 6 configurations (dense k=5, BM25 k=5, hybrid k=5, full hybrid k=5, k=8, k=10).

## 6. Fields I could not fill

I did not make up any missing data.

1. `start_time` is blank for retrieval rows. The Stage 8B.2 harness logged per-query duration, TTFT, token counts and grades, but no wall-clock start time.
2. `first_token_ms` is blank for non-streaming load requests. TTFT came from separate SSE streaming probes (10 real Groq, 10 calibration, 13 scenario). Table 2a shows "not measured" for the rest.
3. In Table 1, `tokens_per_day` and `requests_in_flight_at_once` are "not measured" with low confidence. Groq's headers don't return a TPD counter or a concurrency limit.

## 7. PDF page count

`final_submission.pdf` is exactly 2 pages (checked with PyMuPDF).

- Page 1: title and metadata, sections 1 to 7 (including Tables 1, 2a, 2b and 3).
- Page 2: sections 8 to 12.
- Body text is 6.8 pt with 8.6 pt leading, table text 5.8 pt, 26 pt margins, dark text on white. Nothing overlaps or is cut off.

## 8. Headings

All 12 required headings appear in `final_submission.md` and the PDF, in order:

1. What I built and why
2. The real service and my stand-in
3. Results (Tables 1, 2a, 2b)
4. Where the time goes
5. When a limit is hit
6. Retrieval: quality versus cost (Table 3)
7. How this library will mislead a naive retriever
8. Retries
9. What the person sees
10. What I'm unsure about, what I left out, what I learned
11. Your feedback on Vaani (placeholder, see below)
12. How I worked with the assistant (history archived, see below)

## 9. README

- Prerequisites: Python 3.12+, `uv`, Node.js 18+ and npm.
- Commands are written for Windows PowerShell (`Copy-Item`, `$env:MODEL_PROVIDER`, `Invoke-RestMethod`).
- Running with no spend is documented: copy `.env.example` and use the local simulator on port 8001.
- Start commands for the simulator (8001), backend (8000) and frontend (5173) are separate.
- Tests: `uv run pytest` (194 tests) and `npm test --prefix frontend` (54 tests).
- Links to `final_submission.pdf`, `final_submission.md` and `results.csv`.

## 10. Secrets

No API keys or credentials are tracked in `submission/`. `.env` is in `.gitignore`, and `.env.example` only holds the placeholder `mock_key_not_required_for_simulator`. A pattern scan for `gsk_` and `sk-` found nothing in source or committed files.

## 11. Still to do by hand

1. **Section 11, feedback on Vaani.** It still holds the placeholder `[USER_MANUAL_INPUT_REQUIRED: Insert personal reflection on Vaani Research assignment scope, clarity, and relevance.]`. This needs your own words.
2. **Section 12, assistant history.** Done. The Gemini logs (7,026 steps, 46 user turns) and the browser subagent log are in `assistant_history/`, with real API keys redacted.
3. **ChatGPT logs, optional.** If you used ChatGPT for earlier architecture discussions, add those logs to `assistant_history/` or Section 12.

## 12. Status

Ready once Section 11 is filled in. Everything else is finished: code, experiments, tables, PDF, README and conversation history.