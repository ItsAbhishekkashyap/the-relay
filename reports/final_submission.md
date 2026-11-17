# The Relay — Technical Assignment Submission Write-up

**Candidate Project:** The Relay — Vaani Research ML Engineering Assignment  
**Model Under Characterization:** `openai/gpt-oss-120b` (Groq LPU Inference Engine)  
**Corpus:** 3 Target Research Papers (120 pages total, 402 chunks)  
**Workflow Engine:** LangGraph Stateful Research Workflow  
**Web Framework:** FastAPI with Asynchronous Traffic Management  

---

### 1. What I built and why

I built an end-to-end, production-grade question-answering research assistant designed to answer technical inquiries exclusively from three foundational machine learning papers:
1. *Attention Is All You Need* (Vaswani et al., arXiv:1706.03762v7, 15 pages)
2. *Moshi: a speech-text foundation model for real-time dialogue* (Défossez et al., arXiv:2410.00037v1, 66 pages)
3. *Dynamic Chunking for Long-Context Retrieval* (arXiv:2507.07955v2, 39 pages)

General LLMs hallucinate citations, invent page numbers, misattribute findings across papers with similar transformer terminology, and fail ungracefully when remote inference rate limits are saturated. To solve these failure modes, I engineered a layered architecture:
- **Multi-Channel Retrieval Engine:** PyMuPDF document extraction preserving 1-based page indices and section hierarchies, LangChain recursive chunking (1,000 characters, 150 overlap), local Sentence Transformers embeddings (`all-MiniLM-L6-v2`, 384 dimensions) in ChromaDB, sparse lexical Rank-BM25 indexing, and a structured SQLite FactStore for tabular parameters, unified via Reciprocal Rank Fusion (RRF, $k=60$).
- **LangGraph Stateful Research Workflow:** An 8-node cyclic state graph executing genuine tool calls (`search_research_papers`), deterministic evidence sufficiency gates, answer generation, rigorous bracketed citation verification against chunk metadata, a strictly bounded single-attempt self-correction loop, and grounded refusals for out-of-domain queries.
- **Production TrafficManager:** An asynchronous concurrency and token governor implementing FIFO queuing, sliding-window RPM (Requests Per Minute) and TPM (Tokens Per Minute) admission controls, maximum concurrency bounding, and cooperative client cancellation safety.
- **Calibrated Stand-in Simulator:** A high-fidelity FastAPI stand-in simulator calibrated against 20 empirical baseline requests to the real Groq API (`openai/gpt-oss-120b`), replicating streaming Server-Sent Events (SSE), token-bucket rate limits, and mathematically exact lognormal latency distributions.

---

### 2. The real service and my stand-in

I characterized the real Groq endpoint hosting `openai/gpt-oss-120b` across 20 controlled baseline requests (10 streaming, 10 non-streaming; 94 prompt tokens, 250 completion tokens). The real service provides high token generation throughput via Groq LPUs, but operates under strict rate limits on the developer tier: a 30 RPM sliding window, an 8,000 TPM limit (resetting every 60 seconds), and a 1,000 RPD budget (rolling 24-hour reset window, visible via `x-ratelimit-reset-requests`).

To enable exhaustive, zero-cost load testing without exhausting developer quotas, I implemented a local HTTP stand-in simulator (`simulator/service.py`). The simulator enforces identical HTTP status codes (HTTP 429 `rate_limit_exceeded`), provides `Retry-After` headers, and reproduces real latency distributions using a lognormal distribution parameterized by exact closed-form equations: $\mu = \ln(M)$ and $\sigma = \sqrt{\ln((1 + \sqrt{1 + 4(S/M)^2})/2)}$, where target median $M = 852.0\text{ ms}$ and target standard deviation $S = 234.55\text{ ms}$.

#### Table 1 — Real service limits and observed behavior

| Limit / Operational Property | Documented / Stated Limit | Empirically Observed (Real Baseline) | Stand-in Simulator Implementation |
| :--- | :--- | :--- | :--- |
| **Requests Per Minute (RPM)** | 30 RPM (Free Tier default) | Confirmed via `x-ratelimit-remaining-requests` header | Sliding 60-second window bucket; rejects with HTTP 429 when depleted |
| **Tokens Per Minute (TPM)** | 8,000 TPM | Enforced via `x-ratelimit-remaining-tokens: 8000` header | Sliding 60-second token reservation bucket; enforces prompt+completion limits |
| **Requests Per Day (RPD)** | 1,000 RPD | Enforced via `x-ratelimit-limit-requests: 1000`; resets rolling | Rolling 24h / UTC-reset day counter; returns HTTP 429 when exhausted |
| **Tokens Per Day (TPD)** | Not explicitly capped beyond TPM/RPD (~200k est.) | No independent TPD header observed | Configurable daily token budget parameter (`daily_token_budget`) |
| **Requests in Flight (Concurrency)** | Unadvertised internal limit | Handled concurrent bursts up to 10 in-flight safely | Configurable semaphore (`max_concurrency = 5` or `10`) |
| **Response on Exceeded Limit** | HTTP 429 Rate Limit Exceeded | HTTP 429 with JSON body and `retry-after` header | Exact HTTP 429 response structure with JSON error and `retry-after` header |
| **Recovery Behavior** | Token bucket replenish (rolling 60s) | Immediate recovery upon window expiration | Deterministic sliding-window restoration and administrative reset API |
| **Streaming TTFT Latency** | Unspecified by provider | Median: 852.0 ms (p95: 1,360.2 ms, stddev: 234.55 ms) | Calibrated lognormal sampler: median 855.26 ms (stddev: 337.82 ms) |
| **Non-Streaming Total Latency** | Unspecified by provider | Median: 976.5 ms (p95: 1,272.2 ms, stddev: 174.00 ms) | Calibrated lognormal sampler: median 1,033.79 ms (stddev: 269.89 ms) |

---

### 3. Results

Using the calibrated stand-in simulator and the asynchronous `TrafficManager`, I evaluated system behavior under five controlled load scenarios (A through E), alongside the real Groq baseline reference. Raw measurements across all 119 requests are preserved in `experiments/results.csv`.

#### Table 2a — Latency and throughput by scenario

| Scenario ID & Description | Source | Offered Rate | Test Duration | Admitted ($N_{ok}$) | TTFT p50 | TTFT p95 | Total Latency p50 | Total Latency p95 | Peak Queue Depth |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Real Baseline** (Reference) | Real Groq | ~0.33 req/s | ~60.0 s | 20 / 20 | 852.0 ms | 1,360.2 ms | 1,031.0 ms | 1,461.6 ms | 0 |
| **Calibration Baseline** | Stand-in | ~0.33 req/s | ~60.0 s | 20 / 20 | 855.3 ms | 1,502.4 ms | 1,033.8 ms | 1,430.7 ms | 0 |
| **Scenario A** (Steady Traffic) | Stand-in | ~0.50 req/s | ~30.0 s | 15 / 15 | 807.7 ms | 1,141.1 ms | 1,106.5 ms | 1,402.1 ms | 0 |
| **Scenario B** (Burst Traffic) | Stand-in | ~1.00 req/s | ~12.0 s | 12 / 12 | 768.0 ms | 905.5 ms | 2,414.4 ms | 4,060.0 ms | 9 |
| **Scenario C** (Sustained Overload) | Stand-in | ~1.05 req/s | ~18.0 s | 6 / 19 | 1,224.9 ms* | 1,224.9 ms* | 1,018.4 ms | 1,419.4 ms | 5 (saturated) |
| **Scenario D** (Halved RPM Limit) | Stand-in | ~0.38 req/s | ~60.0 s | 18 / 23 | N/A (non-stream) | N/A | 295.9 ms | 412.7 ms | 0 |
| **Scenario E** (Daily Budget Cap) | Stand-in | ~1.00 req/s | ~10.0 s | 7 / 10 | N/A (non-stream) | N/A | 279.3 ms | 358.8 ms | 0 |

*\*Note: In Scenario C, TTFT p50 reflects the single streaming probe executed; non-streaming probes completed at 1,018.4 ms.*

#### Table 2b — Reliability and cost by scenario

| Scenario ID & Description | Source | Total Requests | Success Rate | Rate Limited | Timed Out | Queue Full (Error) | Retries / Req | Tokens / Answer | Cost / 1k Answers |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Real Baseline** (Reference) | Real Groq | 20 | **100.0%** (20/20) | 0.0% | 0.0% | 0.0% | 0.00 | 344 (94 in / 250 out) | \$0.1641 |
| **Calibration Baseline** | Stand-in | 20 | **100.0%** (20/20) | 0.0% | 0.0% | 0.0% | 0.00 | 344 (94 in / 250 out) | \$0.1641 |
| **Scenario A** (Steady Traffic) | Stand-in | 15 | **100.0%** (15/15) | 0.0% | 0.0% | 0.0% | 0.00 | 344 (94 in / 250 out) | \$0.1641 |
| **Scenario B** (Burst Traffic) | Stand-in | 12 | **100.0%** (12/12) | 0.0% | 0.0% | 0.0% | 0.00 | 344 (94 in / 250 out) | \$0.1641 |
| **Scenario C** (Sustained Overload) | Stand-in | 19 | **31.58%** (6/19) | 0.0% | 26.32% (5) | 42.11% (8) | 0.00 | 548 (298 in / 250 out) | \$0.1947 |
| **Scenario D** (Halved RPM Limit) | Stand-in | 23 | **78.26%** (18/23) | 21.74% (5) | 0.0% | 0.0% | 0.43 (10 retries) | 370 (120 in / 250 out) | \$0.1680 |
| **Scenario E** (Daily Budget Cap) | Stand-in | 10 | **70.00%** (7/10) | 30.00% (3) | 0.0% | 0.0% | 0.30 (3 retries) | 384 (134 in / 250 out) | \$0.1701 |

*Pricing Basis: \$0.15 / 1M prompt tokens, \$0.60 / 1M completion tokens.*

---

### 4. Where the time goes

In end-to-end execution, request latency partitions into three primary stages:
1. **Retrieval Phase (~35–50 ms):** ChromaDB dense vector similarity search takes 35–45 ms; Rank-BM25 keyword retrieval executes in 3.0–3.3 ms; FactStore SQLite queries execute in 0.5–1.0 ms; Reciprocal Rank Fusion ($k=60$) deduplication completes in $<0.5\text{ ms}$. Total retrieval overhead is consistently under 50 ms.
2. **Traffic Management & Queuing (0 ms to ~3.2 s):** Under nominal load (Scenario A), queue wait time is 0.0 ms. Under burst concurrency (Scenario B, concurrency limit 3), requests queue in FIFO order, with wait times increasing linearly: batch 1 (0 ms wait, 1.0 s total), batch 2 (1.0 s wait, 2.1 s total), batch 3 (2.1 s wait, 3.2 s total), batch 4 (3.2 s wait, 4.3 s total).
3. **Model Prefill & Generation (~800–1,200 ms, >95% of pipeline latency):** LLM generation completely dominates latency. Real Groq TTFT (time-to-first-token) exhibits a median of 852.0 ms (p95: 1,360.2 ms). Token streaming output delivers ~250 tokens across 150–250 ms at Groq's high LPU throughput.
4. **Citation Verification & Routing (<2 ms):** Deterministic verification of bracketed citation patterns, canonical arXiv strings, and page/section set containment consumes $<2\text{ ms}$ of CPU time.

---

### 5. When a limit is hit

When resource boundaries are reached, the system executes deterministic backpressure policies:
- **Queue Saturation (`max_queue_size = 5`):** Incoming requests are immediately rejected with `QueueFullError` in $<1\text{ ms}$ turnaround time. No worker threads block, and zero upstream tokens are consumed.
- **Queue Timeout (`deadline = 2.2 s`):** Requests delayed beyond the configured deadline are canceled via `QueueTimeoutError` prior to dispatch, preventing expired requests from executing stale LLM work.
- **Provider Rate Limiting (HTTP 429):** The provider returns HTTP 429 with `Retry-After`. The `TrafficManager` catches the exception and executes bounded exponential backoff with jitter. If the retry budget (`max_retries = 2`) expires, it raises `RateLimitError` cleanly.
- **Daily Budget Exhaustion:** When daily request or token quotas are depleted, the simulator returns HTTP 429 (`daily_quota_exceeded`). The system rejects subsequent queries immediately rather than spinning in retries.
- **Client Disconnection / Cancellation:** Requests are wrapped in `asyncio.shield` where appropriate, while monitoring client socket state. Cancellation releases active concurrency semaphore permits in `finally` blocks, preventing resource leakage.

---

### Retrieval: quality versus cost

I benchmarked 4 retrieval configurations across 32 manually verified evaluation questions (26 answerable across all 3 papers, 6 unanswerable / out-of-domain refusals). Ground-truth provenance was established by human inspection of the PDFs. Raw query logs are preserved in `experiments/retrieval/retrieval_results.csv`.

#### Table 3 — Retrieval configuration comparison

| Metric / Parameter | Config A: Dense-only (ChromaDB) | Config B: BM25-only (Rank-BM25) | Config C: Hybrid (Dense + BM25) | Config D: Full Hybrid (+ FactStore) |
| :--- | :---: | :---: | :---: | :---: |
| **Chunk Size / Overlap** | 1,000 / 150 chars | 1,000 / 150 chars | 1,000 / 150 chars | 1,000 / 150 chars |
| **Pieces Fetched ($k$)** | 5 | 5 | 5 | 5 |
| **Reranking / Fusion Algorithm** | None | None | Reciprocal Rank Fusion ($k=60$) | Reciprocal Rank Fusion ($k=60$) |
| **Questions Evaluated ($N_{total}$)** | 32 (26 ans / 6 unans) | 32 (26 ans / 6 unans) | 32 (26 ans / 6 unans) | 32 (26 ans / 6 unans) |
| **Recall@1** | 34.62% (9 / 26) | **46.15%** (12 / 26) | 42.31% (11 / 26) | 42.31% (11 / 26) |
| **Recall@3** | 57.69% (15 / 26) | 57.69% (15 / 26) | **61.54%** (16 / 26) | **61.54%** (16 / 26) |
| **Recall@5** | 61.54% (16 / 26) | 65.38% (17 / 26) | **73.08%** (19 / 26) | **73.08%** (19 / 26) |
| **Mean Reciprocal Rank (MRR)** | 0.4519 | 0.5301 | **0.5353** | **0.5353** |
| **Correct Paper Identification** | 100.0% (26 / 26) | 100.0% (26 / 26) | 100.0% (26 / 26) | 100.0% (26 / 26) |
| **Correct Page Identification** | 65.38% (17 / 26) | 73.08% (19 / 26) | **76.92%** (20 / 26) | **76.92%** (20 / 26) |
| **Correct & Cited % (All Qs, $N=32$)** | 50.00% (16 / 32) | 53.12% (17 / 32) | **59.38%** (19 / 32) | **59.38%** (19 / 32) |
| **Correct & Cited % (Answerable, $N=26$)** | 61.54% (16 / 26) | 65.38% (17 / 26) | **73.08%** (19 / 26) | **73.08%** (19 / 26) |
| **Wrong Answer % (All Qs, $N=32$)** | 31.25% (10 / 32) | 28.12% (9 / 32) | **21.88%** (7 / 32) | **21.88%** (7 / 32) |
| **Correct Refusal % ($N=6$)** | **100.0%** (6 / 6) | **100.0%** (6 / 6) | **100.0%** (6 / 6) | **100.0%** (6 / 6) |
| **Average Context Tokens** | 1,078.4 tokens | 1,507.3 tokens | 1,402.3 tokens | 1,402.3 tokens |
| **Model Input / Output Tokens** | 1,647.7 / 74.0 | 2,102.9 / 74.0 | 1,991.0 / 74.6 | 1,991.0 / 74.6 |
| **Retrieval Latency p50** | 36.19 ms | **3.02 ms** | 35.87 ms | 36.80 ms |
| **Total End-to-End Latency p50 / p95** | 1,014.56 / 1,026.77 ms | **980.36 / 994.44 ms** | 1,013.95 / 1,030.18 ms | 1,014.81 / 1,026.17 ms |
| **Estimated Cost per 1k Answers** | **\$0.2915** | \$0.3599 | \$0.3434 | \$0.3434 |

#### Quality vs. Cost Trade-offs and Negative Findings
- **Lexical BM25 vs. Dense Embeddings:** BM25 achieved substantially higher Recall@1 (46.15% vs. 34.62%) and higher MRR (0.5301 vs. 0.4519) because research queries frequently hinge on unique technical identifiers, model names, and hyperparameter symbols (`Moshi`, `RQ-VAE`, `Mimi`, `WMT 2014`, `bleu`, `d_model`). However, BM25 retrieved longer context spans, consuming 39.8% more context tokens (1,507.3 vs. 1,078.4) and increasing cost per 1,000 answers by 23.5% (\$0.3599 vs. \$0.2915).
- **Hybrid Synergy (Config C):** Fusing Dense and BM25 through Reciprocal Rank Fusion ($k=60$) yielded the highest retrieval accuracy across the benchmark: Recall@5 reached 73.08% (a +7.70 percentage point gain over BM25 and +11.54 over Dense), while wrong answers dropped to 21.88%. RRF combines BM25's exact keyword precision with ChromaDB's semantic generalization.
- **Honest Negative Finding on FactStore (Config D):** Config D produced results identical to Config C across every accuracy, recall, and cost metric. Tracing the retrieval pipeline revealed that `FactStore` contributed 0 hits across all 32 evaluation questions. FactStore was populated with structured markdown tables and parameter records indexed with SQLite FTS5 conjunctive token constraints. Natural language queries ("What BLEU score did Transformer base achieve on EN-DE?") failed to match strict multi-token table column names without query pre-processing or SQL translation. Rather than masking this result or altering benchmark queries to force synthetic hits, I document this as an authentic engineering lesson: structured relational fact stores require dedicated query translation layers to bridge natural language questions to tabular schemas.

---

### How this library will mislead a naive retriever

The 3-paper corpus contains substantial lexical collisions, structural overlaps, and architectural similarities that systematically trap naive semantic retrievers:
1. **Transformer Cross-Attention Collisions:** Both *Attention Is All You Need* (1706.03762v7) and *Moshi* (2410.00037v1) extensively discuss multi-head attention, cross-attention, layer normalization, residual connections, and positional encodings. A naive semantic search for "cross-attention mechanism" retrieves passages from both papers with high cosine similarity, causing LLMs to falsely attribute Moshi's dual-audio streaming cross-attention to Vaswani et al.
2. **"Chunking" Semantic Ambiguity:** *Dynamic Chunking* (2507.07955v2) addresses text document segmentation for RAG systems, whereas *Moshi* (2410.00037v1) uses "temporal chunking" and "audio chunks" to describe the 12.5 Hz (80 ms) discrete token frames of the Mimi neural codec. A lexical or vector query for "chunking window size" will retrieve audio frame quantization specifications from Moshi alongside token boundary algorithms from Dynamic Chunking.
3. **Hyperparameter Table Overlaps:** Both Vaswani et al. (Table 1) and Moshi describe models with $d_{model}=512$, $d_{ff}=2048$, 8 heads, and dropout $0.1$. Without explicit provenance tracking, retrievers conflate text translation hyperparameters with acoustic transformer dimensions.

**Defenses Implemented:**
- Strict chunk metadata binding: Every chunk permanently encapsulates `paper_id`, `page_number`, and `section`.
- Targeted retrieval tool: The `search_research_papers` tool allows optional filtering by canonical `paper_id`.
- Deterministic citation verification: The workflow strictly verifies that the paper title, arXiv ID, page number, and section name match the retrieved chunk provenance before output acceptance.

---

### Retries

The system employs a strict, differentiated retry policy:
- **What is retried:** Transient transport errors (socket timeouts, connection resets), upstream server errors (HTTP 502/503), and rate limit throttles (HTTP 429) where `Retry-After` is short ($\le 5.0\text{ s}$) and within the retry budget.
- **What is NOT retried:** Client errors (HTTP 400, 401, 404, 422), queue capacity exhaustion (`QueueFullError`, which fails fast to protect system health), and permanent quota exhaustion (HTTP 429 with `daily_quota_exceeded` or `Retry-After > 60 s`).
- **Backoff Mechanics:** When retrying, `TrafficManager` applies full-jitter exponential backoff: $T_{\text{wait}} = \min(T_{\text{max}}, T_{\text{base}} \times 2^{\text{attempt}} + \text{uniform}(0, J))$, preventing thundering-herd synchronization.
- **Workflow Citation Retries:** When generated citations fail verification (e.g., hallucinated page numbers or invented sections), the system does not resubmit identical queries to the network. Instead, the `correction_attempt_node` feeds the precise citation verification failure reason back into the model for a single self-correction attempt (`max_correction_attempts = 1`). If correction fails a second time, it routes to a grounded refusal.

---

### What the person sees

- **Correct, Verified Response:** The user receives a concise, factual answer accompanied by strict bracketed provenance citations:
  > "The Transformer base model achieves a BLEU score of 27.3 on the WMT 2014 English-to-German translation task [Attention Is All You Need, arXiv:1706.03762v7, p. 8, Section 5.1]."
- **Grounded Refusal:** When a query falls outside the three papers or cannot be verified from retrieved chunks, the user receives an explicit, transparent refusal rather than an ungrounded hallucination:
  > "I cannot answer this question based on the provided corpus. The available research papers (Attention Is All You Need, Moshi, Dynamic Chunking) do not contain verified evidence regarding the requested topic."
- **Bursty Traffic State:** Under burst loads, the client connection remains cleanly open; the user experiences a slight wait (~1–3 seconds) as the FIFO queue processes the burst, receiving a valid HTTP 200 response.
- **Overload / Capacity Exceeded:** If the queue is saturated, the caller immediately receives an HTTP 503 error with a clean JSON payload: `{"detail": "System is at maximum queue capacity. Please retry shortly."}`. Turnaround is $<1\text{ ms}$, ensuring no hung browser or API connections.
- **Streaming UI:** In streaming mode, tokens render progressively via SSE, with initial tokens visible within ~850 ms (TTFT), followed by inline citations upon completion.

---

### What I'm unsure about, what I left out, what I learned

- **What I'm unsure about:**
  - *Groq Distributed Edge Rate Limiting:* In Stage 4 empirical testing, `x-ratelimit-reset-requests` fluctuated between 15m and 41m. It remains uncertain whether Groq's multi-region routing synchronizes token buckets globally or per-edge point of presence.
  - *Metadata vs. Semantic Entailment Gap:* Verifying that a citation matches a chunk's `paper_id`, page number, and section name guarantees provenance existence, but does not constitute formal mathematical proof of semantic entailment between the generated sentence and the source text.
- **What I left out:**
  - *Multi-Hop Query Reformulation / HyDE:* Left out because issuing 2–3 additional LLM pre-generation calls would triple latency (~3.5 s total) and rapidly exhaust the 30 RPM developer quota under concurrent load.
  - *Neural Cross-Encoder Reranker:* Substituted with Reciprocal Rank Fusion ($k=60$) to maintain sub-40 ms retrieval latencies without requiring dedicated local GPU inference infrastructure.
  - *FactStore Natural Language Query Pre-Processor:* Did not implement a dedicated SQL query synthesis LLM call, choosing instead to measure the out-of-the-box hybrid performance honestly.
- **What I learned:**
  - Sparse lexical search (BM25) remains essential in technical research domains; dense vector embeddings struggle with exact hyperparameter numbers, table indices, and specialized acronyms.
  - Asynchronous backpressure and bounded queues are non-negotiable for LLM services: without hard admission boundaries, burst traffic triggers latency cascades and burns costly upstream quotas on expired client requests.
  - Exact statistical parameterization is vital when modeling latency: computing lognormal $\sigma$ using median vs. mean formulas produced an 18.3% error in synthetic load behavior until corrected.

---

### Your feedback on Vaani

- **Realistic Systems Engineering Scaffolding:** Unlike conventional AI assignments that treat LLM engineering as trivial prompt wrapping, Vaani's assignment mirrors real-world production engineering by enforcing rate limits, concurrency controls, backpressure, empirical characterization, and strict citation provenance.
- **Challenging Multi-Paper Dynamics:** Curating a 3-paper corpus with shared transformer terminology effectively tests whether an architecture can prevent cross-document hallucination.
- **Suggestions for Future Iterations:**
  1. *Standardized Evaluation Schema:* Providing an official evaluation question schema or query harness in earlier stages would streamline benchmark standardization across candidates.
  2. *FactStore Interface Guidance:* Clarify whether the structured table store is intended to be called as a structured SQL tool by the agent or merged via hybrid retrieval, avoiding the natural-language mismatch observed in Stage 6.

---

### How I worked with the assistant

During the development of this project, I collaborated with AI assistants using a clear, disciplined division of labor:

- **Division of Human vs. Assistant Labor:**
  - **ChatGPT (Architecture & Planning Companion):** Used for high-level architectural brainstorming, designing the 8-node LangGraph StateGraph, deriving mathematical equations for lognormal distribution parameterization, and reviewing edge cases in concurrent token bucket accounting.
  - **Google Antigravity (Implementation & Coding Agent):** Served as the primary execution engine. It performed codebase inspections, generated file scaffolding, implemented async classes (`TrafficManager`, `HybridRetriever`), authored unit and integration test suites, and executed background experiment scripts.
  - **Human Engineer (Direction, Audit & Quality Control):** Defined system requirements, reviewed all code implementations, verified mathematical derivations, audited raw CSV experiment logs, caught modeling discrepancies, overruled synthetic workarounds, and authored the technical synthesis.

- **Three Important Prompts / Prompt Types Used:**
  1. *Cancellation Safety & Concurrency Bounding:*  
     `"Inspect app/traffic/manager.py. Ensure that when a client disconnects or an asyncio.CancelledError occurs, active concurrency semaphore permits are guaranteed to release via try...finally blocks, and background provider calls do not leave orphaned tasks or leaked queue slots."`
  2. *Exact Lognormal Parameterization Derivation:*  
     `"In simulator/service.py, audit the lognormal distribution generator. When target median M and standard deviation S are specified, derive and implement the exact mathematical parameterization for sigma and mu, ensuring theoretical median equals M and theoretical standard deviation equals S."`
  3. *Retrieval Evaluation Benchmark & Integrity Enforcement:*  
     `"Execute the retrieval evaluation across all 32 questions for Configs A, B, C, and D without modifying retrieval weights midway or introducing synthetic query tokens. Preserve raw results in experiments/retrieval/retrieval_results.csv."`

- **One Actual Error Caught:**
  - During Stage 5A calibration, the assistant generated synthetic latencies with a median of $696.14\text{ ms}$, despite the target median being $852.0\text{ ms}$ (an 18.3% error). Upon inspection, I discovered the assistant had implemented the textbook formula $\sigma = \sqrt{\ln(1 + (S/M)^2)}$, which assumes $M$ is the distribution *mean*, whereas in our specification $M$ was the *median*. I corrected the mathematical formulation to the exact median-parameterized closed form:
    $$\sigma = \sqrt{\ln\left(\frac{1 + \sqrt{1 + 4(S/M)^2}}{2}\right)}, \quad \mu = \ln(M)$$
    This eliminated the 156 ms skew, bringing the simulated median to $855.26\text{ ms}$ ($<0.4\%$ error from real Groq baseline).

- **One Actual Decision Overruled:**
  - When Config D (Full Hybrid with FactStore) yielded identical recall and accuracy scores to Config C, the assistant suggested rewriting the natural language evaluation queries into structured boolean keyword queries (e.g. injecting `"Table 1 BLEU EN-DE"`) so that FactStore would return hits and make Config D appear superior. I overruled this decision immediately. Falsifying query distributions to flatter an algorithm compromises experimental integrity. I mandated keeping the natural language evaluation queries intact and documenting the authentic negative finding: structured relational fact stores require dedicated query translation layers to contribute effectively to natural language retrieval pipelines.
