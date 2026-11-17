# Stage 7A: Final Assignment Compliance and Submission Readiness Audit

**Project:** The Relay — Vaani Research ML Engineering Assignment  
**Auditor:** Independent Submission Readiness Auditor  
**Date of Audit:** November 12, 2026  
**Audit Scope:** Stages 1 through 6A (Data ingestion, chunking, retrieval, workflow, traffic manager, real service characterization, simulator calibration, load experiments, and retrieval evaluation).

---

## A. Executive Summary

This comprehensive, read-only audit inspects the entire codebase, experimental logs, data indexes, tests, and documentation against the authoritative specifications of **The Relay (Vaani Research ML Engineering Assignment)**.

### Overall Readiness Assessment:
**Verdict: Ready for final write-up.**

The repository contains an approved, fully operational implementation of all core engineering systems:
1. **Multi-Channel Retrieval Engine:** PyMuPDF document extraction, LangChain recursive chunking, Sentence Transformers dense vector embeddings with ChromaDB, Rank-BM25 sparse keyword indexing, SQLite structured FactStore, and Reciprocal Rank Fusion (RRF).
2. **LangGraph Research Workflow:** 8-node state graph implementing genuine LangChain tool calls, multi-channel retrieval, deterministic evidence sufficiency gates, answer generation, rigorous citation verification against chunk metadata, a strictly bounded single-attempt correction loop, and grounded refusals.
3. **Resilient Production Traffic Infrastructure:** Async `TrafficManager` enforcing FIFO queuing, maximum concurrency limits, sliding-window RPM and TPM admission controls, token budget reservations, and cooperative client cancellation safety.
4. **Real Service & Stand-in Simulation:** Characterization of Groq's real `openai/gpt-oss-120b` endpoint (20 raw baseline requests preserved), calibrated stand-in simulator with mathematically exact lognormal latency distributions ($\sigma = \sqrt{\ln((1 + \sqrt{1 + 4(S/M)^2})/2)}, \mu = \ln(M)$), streaming SSE chunk delivery, and five stress/load test scenarios (119 raw records preserved).
5. **Retrieval Quality vs. Cost Benchmark:** 32 manually verified evaluation questions across all three target papers and out-of-domain refusals, 128 raw evaluation records ($32 \times 4$ configurations), and comprehensive statistical and economic analysis.
6. **Regression Verification:** Full test suite passes cleanly with **186 passing tests** across 15 test suites, and 100% package compatibility (`uv pip check`).

**Outstanding Items Prior to Submission:**
- The final two-page assignment write-up with the mandatory headings must be authored (Stage 7B).
- A root `README.md` summarizing setup and CLI invocation should be added to accompany `reports/PROJECT_NOTES.txt`.

---

## B. Requirement-by-Requirement Matrix

Status categories:
- **PASS**: Fully implemented, empirically verified, and covered by automated tests.
- **PARTIAL**: Implemented but incomplete, weakly evidenced, or carrying unresolved trade-offs.
- **MISSING**: Not implemented or deliverable absent.
- **NOT VERIFIED**: Cannot be established from available evidence.

| # | Original Assignment Requirement | Status | Relevant File Path(s) | Evidence / Explanation | Limitations / Notes |
| :-: | :--- | :---: | :--- | :--- | :--- |
| **1** | **Exclusive 3-Paper Corpus Preservation**<br>Must answer questions exclusively from: (1) Attention Is All You Need (1706.03762v7), (2) Moshi (2410.00037v1), (3) Dynamic Chunking (2507.07955v2). | **PASS** | `papers/1706.03762v7.pdf`<br>`papers/2410.00037v1.pdf`<br>`papers/2507.07955v2.pdf`<br>`app/workflow/nodes.py` | All three original PDFs preserved in `papers/`. SHA256 hashes and page counts verified. `APPROVED_PAPER_IDS` and canonical mappings hardcoded in `nodes.py`. | Exact version strings (v7, v1, v2) enforced across extraction, indexing, and citation verification. |
| **2** | **PDF Extraction using PyMuPDF**<br>Preserve page boundaries, 1-based page numbers, structural reading order, and table elements. | **PASS** | `app/retrieval/pdf_ingestion.py`<br>`app/retrieval/extract_papers.py` | PyMuPDF extracts text blocks, bounding boxes, section headings, and table structures across all 120 pages of the 3 PDFs. | Extraction verified across 15 test cases in `tests/test_pdf_ingestion.py`. |
| **3** | **LangChain Document Chunking**<br>Deterministic chunking with provenance metadata (`paper_id`, `page_number`, `section`, `chunk_id`). | **PASS** | `app/retrieval/langchain_chunking.py`<br>`app/retrieval/chunking.py`<br>`data/chunks/langchain_recursive/` | RecursiveCharacterTextSplitter (chunk_size=1000, overlap=150). Preserves 402 chunks across the 3 papers with zero cross-paper mixing. | Evaluated in `tests/test_chunking.py` and `tests/test_langchain_chunking.py`. |
| **4** | **Local Sentence Transformers Embeddings**<br>Dense vector generation using local models without remote external API calls. | **PASS** | `app/retrieval/dense_retriever.py` | Uses `sentence-transformers/all-MiniLM-L6-v2` (384 dims, L2 normalized). Enforces `local_files_only=True` to guarantee no external API network dependencies. | Verified in `tests/test_dense_retriever.py`. |
| **5** | **Persistent ChromaDB Vector Store**<br>Persistent cosine similarity vector index supporting metadata filtering. | **PASS** | `app/retrieval/dense_retriever.py`<br>`data/indexes/chroma/` | Persistent ChromaDB client configured with `'hnsw:space': 'cosine'`. Metadata sanitized to primitive types. Idempotent upserting verified. | Count = 402 indexed chunks. Verified in `tests/test_dense_retriever.py`. |
| **6** | **BM25 Lexical Retrieval**<br>Sparse keyword retrieval with persistence, paper filtering, and tokenization. | **PASS** | `app/retrieval/bm25_retriever.py`<br>`data/indexes/bm25/bm25_index.json` | Uses `rank-bm25` (BM25Okapi). Custom token pattern preserves alphanumeric, hyphenated terms, and arXiv identifiers. | Count = 402 indexed chunks. Verified in `tests/test_bm25_retriever.py`. |
| **7** | **Structured FactStore (SQLite)**<br>Verbatim table markdown, numerical parameters, and structured facts with provenance. | **PASS** | `app/retrieval/fact_store.py`<br>`data/indexes/fact_store.db` | SQLite database with FTS5 virtual table and exact substring indexes. Stores 110 structured table chunks. `check_same_thread=False` configured for async safety. | Zero contribution on natural language queries without query pre-processing (documented negative finding). |
| **8** | **Hybrid Retrieval with Reciprocal Rank Fusion (RRF)**<br>Combine Dense, BM25, and FactStore channels into a unified evidence set. | **PASS** | `app/retrieval/hybrid_retriever.py` | Multi-channel execution with RRF ($k=60$), channel failure diagnostics, and deduplication. Configurable per-channel weights. | Verified in `tests/test_hybrid_retriever.py`. Tested across 4 evaluation configurations. |
| **9** | **LangGraph Research Assistant Workflow**<br>StateGraph orchestrating retrieval, evidence checking, generation, citation verification, and correction. | **PASS** | `app/workflow/graph.py`<br>`app/workflow/nodes.py`<br>`app/workflow/schemas.py` | 8 distinct workflow nodes, genuine LangChain BaseTool call (`search_research_papers`), 4 conditional routing edges, and strict StateGraph state passing. | Verified in `tests/test_workflow.py` and `tests/test_workflow_routing.py`. |
| **10** | **Citation Verification & Grounded Refusals**<br>Strict bracketed citation validation (`[Title, arXiv:..., p. ..., Section ...]`) and refusal on insufficient evidence. | **PASS** | `app/workflow/nodes.py` | Deterministically verifies arXiv ID, paper corpus inclusion, retrieved page presence, and section metadata. Refuses out-of-domain and insufficient queries. | 16 tests in `tests/test_citation_verification.py`. Verified limitation: metadata verification is not proof of semantic entailment. |
| **11** | **Bounded Correction Loop**<br>Single-attempt revision loop when citations fail verification. | **PASS** | `app/workflow/nodes.py`<br>`app/workflow/graph.py` | `correction_attempt_node` feeds back verification errors to model. Bound enforced by `max_correction_attempts=1`; routes to refusal on second failure. | Verified in `tests/test_workflow_routing.py::test_correction_attempts_strictly_bounded_to_one`. |
| **12** | **Real Groq Service Characterization**<br>Characterize real Groq API with configured model `openai/gpt-oss-120b`. | **PASS** | `app/providers/groq_provider.py`<br>`experiments/real_service/` | 20 real baseline requests measured (10 non-streaming, 10 streaming). Preserved in `groq_baseline.csv` and summarized in `groq_baseline_summary.json`. | Measured: TTFT median 852.0ms, non-streaming total latency median 976.5ms. Prompt tokens 94, completion tokens 250. |
| **13** | **Calibrated HTTP-Based Stand-in Simulator**<br>Locally hosted FastAPI simulator replicating Groq latency, limits, and streaming behavior. | **PASS** | `simulator/service.py`<br>`simulator/main.py`<br>`simulator/config.py` | Exact mathematical lognormal latency sampling ($\sigma, \mu$), SSE streaming chunks, RPM/TPM/RPD/TPD limit enforcement, concurrency limits, and failure injection. | Covered by 20 unit tests in `tests/test_simulator.py`. |
| **14** | **Async TrafficManager**<br>Queue management, rate limiting, concurrency bounding, and cancellation safety. | **PASS** | `app/traffic/manager.py`<br>`app/traffic/config.py` | FIFO queue, semaphore concurrency bounding, sliding-window RPM and TPM reservation, cooperative client disconnect handling, deadline enforcement. | Covered by 28 tests in `tests/test_traffic_manager.py`. |
| **15** | **FastAPI Application & Endpoints**<br>`GET /health`, `GET /ready`, and `POST /v1/ask`. | **PASS** | `app/main.py`<br>`app/api/routes.py`<br>`app/api/schemas.py` | Fully integrated FastAPI application with `lifespan` startup/shutdown management. `/v1/ask` executes LangGraph workflow through TrafficManager. | Tested by 14 integration tests in `tests/test_api.py`. |
| **16** | **Controlled Load Experiments (Scenarios A–E)**<br>Steady, burst, sustained overload, halved RPM, and daily budget exhaustion. | **PASS** | `experiments/results.csv`<br>`experiments/reports/` | 119 request-level rows preserved in `experiments/results.csv`. Scenarios A–E fully documented in `load_experiment_report.md` and `load_experiment_summary.json`. | Token accounting reconciled in Stage 5A audit. |
| **17** | **Retrieval Evaluation Benchmark ($\ge 30$ Questions)**<br>Evaluate 4 configurations: Dense-only, BM25-only, Hybrid, and Full Hybrid. | **PASS** | `experiments/retrieval/` | 32 questions across 3 papers + 6 refusals. 128 raw records in `retrieval_results.csv`. Recall@1/3/5, MRR, cost, and latency reported in `retrieval_quality_report.md`. | FactStore zero-contribution root cause honestly disclosed. Metric denominators verified ($N_{\text{ans}}=26, N_{\text{unans}}=6, N_{\text{total}}=32$). |
| **18** | **Security & Secret Handling**<br>No secrets or real API keys tracked in repository. | **PASS** | `.gitignore`<br>`.env.example`<br>Tracked files | `.gitignore` excludes `.env` and `*.db`. `.env.example` has placeholder values. Git tracking check confirmed zero leaked secrets. | Mock keys in unit tests (`test_groq_provider.py`) verify sanitization and masking. |
| **19** | **Full Regression Test Suite**<br>Complete test coverage across all components. | **PASS** | `tests/` | 186 automated unit and integration tests passing cleanly in 2m 11s (`uv run pytest -q`). All 144 packages compatible (`uv pip check`). | Zero test failures, zero errors. |
| **20** | **Final Two-Page Assignment Write-up**<br>Maximum 2-page write-up with prescribed headings and "How I worked with the assistant" section. | **MISSING (Planned Stage 7B)** | Prescribed headings in Section 8 of prompt | Does not exist yet. Not created during this read-only audit, as instructed by Stage 7A guidelines. | Ready to be authored in Stage 7B. |
| **21** | **Root README.md**<br>Quickstart, architecture overview, and setup instructions in root. | **MISSING** | Root directory | `README.md` does not exist in root directory. Comprehensive documentation currently resides in `reports/PROJECT_NOTES.txt`. | A root `README.md` should be authored prior to final submission. |

---

## C. Mandatory Deliverables Inventory

### 1. Source Implementation Files
- [x] `app/retrieval/pdf_ingestion.py` (PyMuPDF document extraction)
- [x] `app/retrieval/extract_papers.py` (Paper extraction runner)
- [x] `app/retrieval/chunking.py` & `langchain_chunking.py` (Document chunking)
- [x] `app/retrieval/dense_retriever.py` (Sentence Transformers + ChromaDB)
- [x] `app/retrieval/bm25_retriever.py` (BM25 lexical search)
- [x] `app/retrieval/fact_store.py` (SQLite structured fact store)
- [x] `app/retrieval/hybrid_retriever.py` (Reciprocal Rank Fusion hybrid engine)
- [x] `app/workflow/graph.py` & `nodes.py` (LangGraph research assistant workflow)
- [x] `app/workflow/schemas.py`, `state.py`, `tools.py` (Workflow schemas and LangChain tool)
- [x] `app/providers/base.py` & `schemas.py` (Provider abstractions and schemas)
- [x] `app/providers/groq_provider.py` (Real Groq client adapter)
- [x] `app/providers/simulator_provider.py` (Simulator client adapter)
- [x] `app/traffic/manager.py` & `config.py` (Async TrafficManager)
- [x] `app/api/routes.py` & `schemas.py` (FastAPI route handlers)
- [x] `app/main.py` (FastAPI application factory and lifecycle)
- [x] `simulator/service.py`, `main.py`, `config.py` (Stand-in simulator service)

### 2. Original Research Papers (PDFs)
- [x] `papers/1706.03762v7.pdf` (Attention Is All You Need, 15 pages, SHA256: `bdfaa68d8984...`)
- [x] `papers/2410.00037v1.pdf` (Moshi, 66 pages, SHA256: `a687144cc77b...`)
- [x] `papers/2507.07955v2.pdf` (Dynamic Chunking, 39 pages, SHA256: `04a2b32e6e82...`)

### 3. Raw Experiment & Evaluation CSV Records
- [x] `experiments/real_service/raw/groq_baseline.csv` (20 rows: real Groq request measurements)
- [x] `experiments/results.csv` (119 rows: 20 real baseline, 20 calibration baseline, 79 load scenario requests across Scenarios A–E)
- [x] `experiments/retrieval/retrieval_results.csv` (128 rows: 32 questions $\times$ 4 retrieval configurations)

### 4. Machine-Readable Summary Files (JSON)
- [x] `experiments/real_service/reports/groq_baseline_summary.json` (Real Groq characterization metrics)
- [x] `experiments/reports/load_experiment_summary.json` (Load experiment scenario metrics)
- [x] `experiments/retrieval/evaluation_questions.json` (32 manually verified evaluation questions)
- [x] `experiments/retrieval/retrieval_summary.json` (Summary metrics across 4 retrieval configurations)

### 5. Markdown Reports & Documentation
- [x] `experiments/real_service/reports/groq_characterization_report.md` (Stage 4 real Groq report)
- [x] `experiments/simulator/reports/calibration_report.md` (Stage 5 simulator calibration report)
- [x] `experiments/reports/load_experiment_report.md` (Stage 5 load experiment report)
- [x] `experiments/retrieval/evaluation_dataset_report.md` (Stage 6 evaluation dataset report)
- [x] `experiments/retrieval/retrieval_quality_report.md` (Stage 6 & 6A retrieval quality vs. cost report)
- [x] `reports/PROJECT_NOTES.txt` (Comprehensive architecture and concept notes)

### 6. Outstanding Submission Deliverables
- [ ] Final two-page submission write-up (Stage 7B)
- [ ] Root `README.md` quickstart guide

---

## D. Experimental Integrity Audit

1. **Groq Baseline vs. Simulator Data Separation:**
   - In `experiments/results.csv`, the `source` column strictly delineates `source=real` (20 records) from `source=stand-in` (99 records).
   - In `experiments/real_service/raw/groq_baseline.csv`, all 20 records represent authentic HTTP responses from the Groq API, complete with Groq server queue times, token usage headers (`x-ratelimit-*`), and HTTP 200 statuses.
2. **Reconciliation of Load Scenario Tokens:**
   - In Scenario C (overload), the Stage 5A audit verified that exactly 6 requests succeeded, generating $6 \times 250 = 1,500$ completion tokens ($1,786$ prompt tokens, \$0.001168 cost). Timed-out requests recorded 0 completion tokens.
3. **Retrieval Evaluation Data Integrity:**
   - In `experiments/retrieval/retrieval_results.csv`, exactly 128 rows exist with zero duplicate `(question_id, configuration)` tuples.
   - All summary metrics in `retrieval_summary.json` were audited with an automated script (`scripts/audit_csv_integrity.py`) and confirmed 100% reproducible from the raw CSV records.
4. **Honest Reporting of Negative Findings (FactStore in Config D):**
   - The Stage 6A audit traced every query and proved that `FactStore` returned 0 hits for all 32 natural language questions due to exact substring and FTS5 conjunctive match constraints.
   - The report explicitly discloses that Config D provides no measurable quality improvement over Config C under natural language queries, resisting the temptation to alter the algorithm or fabricate data.

---

## E. Security and Reproducibility

1. **Credential Hygiene:**
   - `.env` is explicitly ignored by `.gitignore`.
   - `.env.example` provides safe placeholders (`GROQ_API_KEY=your_groq_api_key_here`).
   - A full repository scan confirmed zero real API keys or tokens are tracked in git. Mock strings in unit tests (`gsk_mock_test_key...`) are clearly distinguished and verify that provider classes mask sensitive keys in error representations.
2. **Reproducibility & Dependencies:**
   - Project dependencies are locked via `pyproject.toml` and `uv.lock`.
   - Dependency compatibility confirmed by `uv pip check` (144 packages checked, 100% compatible).
   - Local sentence embeddings (`all-MiniLM-L6-v2`) and ChromaDB vector store are fully self-contained locally, enabling local testing with zero internet access or cloud spending.
3. **Full Regression Health:**
   - 186 unit, provider, traffic manager, workflow, and API tests executed via `uv run pytest -q` pass with zero failures and zero errors.

---

## F. Outstanding Work

Only two concrete tasks remain before final submission:
1. **Stage 7B — Author Final Two-Page Submission Report:**
   Write the final two-page assignment write-up following the prescribed heading sequence:
   1. *What I built and why.*
   2. *The real service and my stand-in.*
   3. *Results.*
   4. *Where the time goes.*
   5. *When a limit is hit.*
   - *Retrieval: quality versus cost.*
   - *How this library will mislead a naive retriever.*
   - *Retries.*
   - *What the person sees.*
   - *What I'm unsure about, what I left out, what I learned.*
   - *Your feedback on Vaani.*
   - **How I worked with the assistant** (honest reflection on prompts, caught errors, overruled decisions, and human vs. AI contribution).
2. **Author Root `README.md`:**
   Provide a concise repository overview, environment setup commands (`uv sync`), test commands (`uv run pytest`), and server launch instructions (`uv run uvicorn app.main:create_app --factory`).

---

## G. Final Audit Verdict

### **Verdict: Ready for final write-up.**

The implementation is functionally complete, empirically verified, mathematically sound, securely configured, and backed by passing automated regression tests. The project is fully prepared to enter Stage 7B for drafting the final submission write-up.
