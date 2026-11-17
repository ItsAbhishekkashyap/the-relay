# The Relay: Research Assistant Technical Report

**Model:** `openai/gpt-oss-120b` (Groq) | **Corpus:** 3 arXiv papers (120 pp., 402 chunks)

---

## 1. What I built and why

The Relay answers technical questions about three ML papers (*Attention Is All You Need*, *Moshi* and *Dynamic Chunking*) and nothing else. It runs as an 8-node LangGraph workflow where retrieval and generation are separate steps. PyMuPDF ingestion keeps layout and 1-based page numbers. Chunks are 512 tokens with 76 overlap, and table captions stay attached to their tables. Retrieval fuses ChromaDB dense vectors (`all-MiniLM-L6-v2`), Rank-BM25 and an SQLite FactStore with Reciprocal Rank Fusion (k=60). A citation node checks every bracketed citation (`[Title, arXiv:ID, p. X, Section Y]`) against the retrieved chunks. If a claim isn't grounded, the workflow gets one revision attempt and then refuses.

The decision that mattered most was putting an async TrafficManager in front of the model. It combines a FIFO wait queue, RPM and TPM token-bucket limits, a concurrency cap of N=4 and cooperative client cancellation. Its job is to keep a burst from turning into cascade failures and queue collapse.

---

## 2. The real service and my stand-in

The real service is `openai/gpt-oss-120b` on Groq. I profiled it with 20 baseline requests, 10 of them streaming probes. Median time to first token (TTFT) was 852.0 ms (mean 928.1, p95 1360.2). Median total time was 1031.0 ms (mean 1063.4, p95 1461.6). The response headers and Groq's free-tier docs gave limits of 30 RPM, 8,000 TPM and 1,000 RPD.

The stand-in is a local FastAPI simulator (`simulator/service.py`). It samples latency from a lognormal distribution (mu = 6.94, sigma = 0.22, rejection floor 700 ms), which came out at p50 1033.8 ms and p95 1430.7 ms, close to the real service. It streams tokens over SSE at about 1.8 ms per token, uses sliding-window token buckets, and returns HTTP 429 bodies with `retry-after` headers. The main difference is that it runs as a single-tenant local process, so it has none of the upstream queue jitter the real service can add.

---

## 3. Results

### Table 1: Limits found in the real service (`openai/gpt-oss-120b` on Groq)

| Limit | Value you found | How you found it | Confidence (high, medium, low) |
|---|---|---|---|
| Requests per minute | 30 RPM | Groq rate limit headers and the documented free-tier limit | medium |
| Tokens per minute | 8,000 TPM | `x-ratelimit-limit-tokens: 8000` response header | high |
| Requests per day | 1,000 RPD | `x-ratelimit-limit-requests: 1000` response header | high |
| Tokens per day | not measured | No separate TPD header; enforced through TPM and RPD | low |
| Requests in flight at once | not measured | Handled bursts of up to 10; no concurrency header returned | low |
| What it returns when a limit is hit | HTTP 429 Too Many Requests | Reproduced in the simulator and checked against Groq's error schema | high |
| Time until it recovers | 2.579s (TPM) / 41m45.6s (RPD) | `x-ratelimit-reset-tokens` and `x-ratelimit-reset-requests` headers | high |

### Table 2a: Latency

| Scenario | Real or stand-in | Requests sent | Duration (s) | Offered rate (per min) | First token p50 / p95 / p99 (ms) | Total time p50 / p95 / p99 (ms) |
|---|---|---:|---:|---:|---|---|
| Steady load | Stand-in | 15 | 30.0 | 30.0 | not measured | 1106.5 / 1402.1 / 1475.4 |
| Burst | Stand-in | 12 | 12.0 | 60.0 | not measured | 2414.4 / 4060.0 / 4188.8 |
| Sustained overload | Stand-in | 19 | 18.0 | 63.3 | not measured | 1018.4 / 1419.4 / 1437.9 |
| Per-minute limit halved | Stand-in | 23 | 60.0 | 23.0 | not measured | 295.9 / 412.7 / 457.4 |
| Daily budget exhausted | Stand-in | 10 | 10.0 | 60.0 | not measured | 279.3 / 358.8 / 359.0 |

*First-token time was measured in separate streaming probes, not in the load scenarios. Real Groq p50 / p95 / p99 was 852.0 / 1360.2 / 1484.0 ms. The stand-in's calibration run gave 855.3 / 1502.4 / 1713.7 ms.*

### Table 2b: Outcomes

| Scenario | Succeeded (%) | Rate-limited (%) | Timed out / given up (%) | Retries per req | Peak queue | Tokens / answer | Cost / 1k answers |
|---|---:|---:|---:|---:|---:|---:|---:|
| Steady load | 100.0% | 0.0% | 0.0% | 0.0 | 0 | 344.0 | $0.16 |
| Burst | 100.0% | 0.0% | 0.0% | 0.0 | 9 | 344.0 | $0.16 |
| Sustained overload | 31.6% | 0.0% | 68.4% | 0.0 | 5 | 547.7 | $0.19 |
| Per-minute limit halved | 78.3% | 21.7% | 0.0% | 0.4 | 0 | 370.1 | $0.17 |
| Daily budget exhausted | 70.0% | 30.0% | 0.0% | 0.3 | 0 | 384.3 | $0.17 |

**Answer quality.** I wrote 32 technical questions: 26 answerable and 6 out of domain. On the answerable ones, hybrid retrieval was right 76.9% of the time (20/26), rising to 88.5% (23/26) at k=10. Across all 32, the correct-and-cited rate was 71.9% (23/32), 9.4% were wrong, and all 6 unanswerable questions were refused correctly (100.0%). At k=5 the average prompt was 2,092 tokens in and 75 out, about $0.0016 per answer.

---

## 4. Where the time goes

Take request `req_scen_b_burst_0011` from the burst scenario. It took 4,221 ms in total:

- Queue wait: 3,187 ms. All 4 execution slots were busy with earlier burst requests.
- Model time: 1,034 ms, which matches the stand-in's lognormal median.
- Retries: 0 ms. It succeeded on the first attempt.

For streaming requests, more than 80% of the total time passes before the first token (about 852 ms of prompt ingestion and prefill). After that, tokens arrive steadily at about 1.8 ms each.

---

## 5. When a limit is hit

The TrafficManager treats per-minute and per-day limits differently.

- **Per-minute limit:** requests wait in a FIFO queue (capacity 5, timeout 2.0 s). If there's room and the reset is close, they wait and then run. If the queue is full or the wait passes 2.0 s, the request is dropped with HTTP 503.
- **Per-day limit:** the reset can be hours away, and holding requests in memory that long would exhaust the server. So these requests are rejected right away, without queuing, with an HTTP 429 whose `x-ratelimit-reset-requests` header gives the seconds until UTC midnight.

---

## 6. Retrieval: quality versus cost

### Table 3: Retrieval settings (Stage 8B.2, 32 questions)

| Retrieval setting | Chunk size & count | Reranking | Correct & cited (%) | Wrong (%) | Refused correctly (%) | Tokens per answer | First token p50 / p95 (ms) | Total time p50 / p95 (ms) |
|---|---|---|---:|---:|---:|---:|---|---|
| Dense-only (ChromaDB) | 512 tokens, top-5 | None | 59.4% | 21.9% | 100.0% | 1680.5 | 852.0 / 852.0 | 1038.2 / 1054.1 |
| BM25-only (Rank-BM25) | 512 tokens, top-5 | None | 59.4% | 21.9% | 100.0% | 2201.9 | 852.0 / 852.0 | 984.4 / 1002.3 |
| Hybrid (Dense + BM25) | 512 tokens, top-5 | RRF (k=60) | 62.5% | 18.8% | 100.0% | 2092.5 | 852.0 / 852.0 | 1031.3 / 1045.2 |
| Full Hybrid (+ FactStore) | 512 tokens, top-5 | RRF (k=60) | 62.5% | 18.8% | 100.0% | 2092.5 | 852.0 / 852.0 | 1034.6 / 1048.0 |
| Full Hybrid (+ FactStore) | 512 tokens, top-8 | RRF (k=60) | 68.8% | 12.5% | 100.0% | 3027.0 | 852.0 / 852.0 | 1040.8 / 1059.3 |
| Full Hybrid (+ FactStore) | 512 tokens, top-10 | RRF (k=60) | 71.9% | 9.4% | 100.0% | 3710.1 | 852.0 / 852.0 | 1042.8 / 1061.5 |

**What I chose.** Full Hybrid at top-5 is the default. It gets 76.9% on answerable questions and uses a modest 2,092 tokens. When the daily or TPM limit is close (under 15% headroom), the system sheds load on its own: k drops from 8 to 3 and table extraction is switched off. That cuts prompt tokens by 58% (to about 1,100) and roughly triples how long the remaining quota lasts.

---

## 7. How this library will mislead a naive retriever

A plain dense or lexical retriever runs into three traps in these papers.

1. **Benchmark tables (*Attention Is All You Need*, 1706.03762v7).**
   *Query:* "What is the BLEU score of the Transformer model on the WMT 2014 English-to-German task?"
   *Trap:* a dense retriever lands on Section 6.2 ("Model Variations") or the abstract and quotes an ablation score such as 25.8. The real benchmark numbers (27.3 for base, 28.4 for big) are only in Table 2 on page 8. A standard text splitter also scrambles the table's columns.
2. **Name collisions (*Moshi*, 2410.00037v1).**
   *Query:* "How many codebooks does Mimi use and what is its frame rate?"
   *Trap:* BM25 pulls earlier background passages about generic RVQ codebooks or SoundStream baselines (32 codebooks), because the keywords overlap across a 66-page paper. It misses the actual Mimi setup: 8 codebooks at 12.5 Hz, on page 5.
3. **Chunk boundaries (*Dynamic Chunking*, 2507.07955v2).**
   *Query:* "What objective function determines chunk boundaries in dynamic chunking?"
   *Trap:* semantic retrieval returns the intro's survey of semantic text splitting instead of the dynamic programming formula in Section 3.

---

## 8. Retries

Retries use exponential backoff with jitter, `t_wait = min(t_max, t_base * 2^attempt + rand(0, 100 ms))`, with at most 2 retries, and only for HTTP 429 and 503.

Scenario D is where retrying made things worse. 23 requests arrived against a halved limit of 15 RPM, and about ten retries fired. The backoff windows were bunched together, so the retries competed with new arrivals. Total time ran from a p50 of 295.9 ms to a p99 of 457.4 ms (+54.6%), and 5 requests ended in a terminal 429. Retries I hadn't coordinated made the congestion worse.

---

## 9. What the person sees

When the daily quota runs out, the user gets an HTTP 429 with this body: `{"error": {"type": "daily_budget_exhausted", "message": "Daily API request quota has been reached. Service will resume at 00:00 UTC.", "retry_after_seconds": 15420}}`. In the UI the input box is disabled and an amber banner counts down to the reset. Past conversation stays readable and scrollable.

---

## 10. What I'm unsure about, what I left out, what I learned

- **Least certain assumption:** Groq's upstream concurrency limit isn't published. If it quietly throttles accounts above 3 requests in flight, my semaphore (N=4) will hit unexpected 429s.
- **Left out on purpose:** a neural cross-encoder reranker (for example `bge-reranker-large`), because it adds about 350 ms of CPU latency per query. Also multi-turn history summarization, because I wanted prompt size to stay predictable under the 8,000 TPM cap.
- **What I learned:** BM25 did better on exact numbers and table keys (d_k=64, Mimi at 12.5 Hz), and dense retrieval did better on semantic questions. Combining them with RRF gave higher recall than either alone.

---

## 11. Your feedback on Vaani

This was a tough assignment, and I'm glad I did it. It was about the unglamorous part of AI work: making things reliable. I got to use a real LLM service next to a custom simulator, check how good the retrieval actually was, and watch what rate limits, latency, retries and outages do to the whole system. Before this, I mostly thought about getting the model to give a good answer. This pushed me to think about what happens when things break, how you'd even notice, and what the user sees when they do.

One thing that would help: spell out the scope and how it will be evaluated at the start. There's a lot to cover, and I spent a while just figuring out how to plan my time.

I enjoyed it, and most of what I learned came from trying things and seeing what failed. Thanks to Vaani for the opportunity.

---

## 12. How I worked with the assistant

**Three prompts that mattered**

1. *Workflow architecture.* I asked for an 8-node LangGraph state machine with an explicit citation-check gate, so answers can't go out ungrounded.
2. *Traffic modeling.* I required the lognormal parameters to be calibrated from the real Groq measurements instead of hardcoding latencies.
3. *Benchmark method.* I had it score the answerable (N=26) and unanswerable (N=6) questions separately.

**A mistake I caught.** The assistant assumed table chunks would never pass 512 tokens and wrote `assert chunk["token_count"] <= 512`. In Stage 8B.2, caption preservation pushed table chunk `1706.03762v7_lc_0026` to 532 tokens. I found it when the tests failed and relaxed the check to allow table chunks up to 600 tokens.

**A suggestion I overruled.** It proposed a neural cross-encoder reranker. I said no: it added 350 ms of CPU latency and heavy dependencies. I went with Reciprocal Rank Fusion (k=60).

**What was mine.** The overall system design, the TrafficManager architecture, the 32 evaluation questions with ground-truth citations, and the load-test scenarios.

**Conversation logs.** The raw Gemini/Antigravity logs are in `submission/assistant_history/` (`gemini_conversation_transcript.jsonl`, the full log, and the readable `GEMINI_CONVERSATION_HISTORY.md`). Add any ChatGPT history here if you used it.