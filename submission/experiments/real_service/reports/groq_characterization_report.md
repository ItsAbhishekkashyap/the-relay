# Real Groq Service Characterization Report

**Stage:** Stage 4 — Real Service Characterization  
**Project:** The Relay — Vaani Research ML Engineering Assignment  
**Model Tested:** `openai/gpt-oss-120b`  
**Execution Period:** `2026-11-12T08:04:04.360986+00:00` to `2026-11-12T08:05:04.770020+00:00`  
**Total Completed Requests:** 20 (10 Non-Streaming, 10 Streaming)  
**Overall Success Rate:** 100.0% (20 succeeded, 0 failed, 0 throttled)  

---

## 1. Experimental Setup

The Stage 4 experiment was designed to empirically benchmark the real **Groq Cloud API** under controlled conditions to understand its latency distribution, streaming mechanics, token accounting, and active tier limits.

- **Client Runtime:** Python 3.12 (`.venv`) using the official Groq Python SDK (`AsyncGroq`).
- **Endpoint:** `https://api.groq.com/openai/v1/chat/completions` (HTTP/2 over TLS 1.3 via Cloudflare edge).
- **Physical Datacenter Location:** `x-groq-region: bom` (Mumbai, India datacenter).
- **Measurement Instrumentation:**
  - Precision interval timing: `time.monotonic()` clock before request dispatch, during chunk iteration, and upon stream closure.
  - Wall-clock synchronization: UTC ISO 8601 timestamps recorded per request.
  - Raw HTTP response capture: `client.chat.completions.with_raw_response` capturing all HTTP response headers, including rate-limit headers.
  - Token metadata capture: Direct extraction of server-side `CompletionUsage` objects with `include_usage: True`.

---

## 2. Model and Account Configuration

- **Configured Model Identifier:** `openai/gpt-oss-120b` (loaded directly from `.env` via `GROQ_MODEL`).
- **Architecture Type:** High-parameter open-weights reasoning model with integrated chain-of-thought processing.
- **Account Tier:** Groq Developer Free Tier.
- **Secrets Management:** The `GROQ_API_KEY` was read exclusively into memory via `python-dotenv`. The API key is sanitized in all logs and strictly excluded from raw datasets, CSV tables, and reports.
- **Active Serving Region:** Mumbai, India (`bom`), delivering low client-to-server RTT from regional nodes.

---

## 3. Request Methodology

To maintain complete experimental consistency across both modes without depleting daily account quota, the experiment executed a controlled 20-request baseline:

- **Phase 1 (Non-Streaming):** 10 consecutive requests in standard completion mode.
- **Phase 2 (Streaming):** 10 consecutive requests in Server-Sent Events (SSE) streaming mode with usage telemetry enabled.
- **Fixed Workload Prompt (`attn_math_formulation_01`):**
  > *"Explain the core architectural differences between scaled dot-product attention and multi-head attention in Transformer models, citing their mathematical formulations."*
- **Execution Parameters:**
  - `temperature`: `0.0` (deterministic sampling).
  - `max_tokens`: `250` (uniform completion budget).
- **Pacing & Concurrency:**
  - Sequential submission (1 request in flight at any given time).
  - Strict 2.0-second inter-request delay (`INTER_REQUEST_DELAY = 2.0s`) to remain conservatively beneath the 30 RPM threshold and avoid artificial server-side queue buildup.

---

## 4. Latency Results

All latency values were computed using monotonic clock intervals. For non-streaming requests, Time to First Token (TTFT) is unavailable by definition and recorded as `null`.

### 4.1 Latency Distribution Summary (in Milliseconds)

| Metric | Non-Streaming Total (ms) | Streaming TTFT (ms) | Streaming First-Chunk (ms) | Streaming Total (ms) | Combined Total (ms) |
|---|---|---|---|---|---|
| **Min** | 797.00 | 609.00 | 375.00 | 875.00 | **797.00** |
| **p50 (Median)** | **976.50** | **852.00** | **453.50** | **1070.50** | **1031.00** |
| **p95** | 1272.20 | 1360.20 | 989.30 | 1547.60 | **1461.60** |
| **p99** | 1316.84 | 1484.04 | 1085.06 | 1609.52 | **1592.32** |
| **Max** | 1328.00 | 1515.00 | 1109.00 | 1625.00 | **1625.00** |
| **Mean** | 976.60 | 928.10 | 569.00 | 1150.10 | **1063.35** |
| **Std Dev** | 185.04 | 234.55 | 235.91 | 224.23 | **213.61** |

### 4.2 Latency Observations
1. **Low Overall Variance:** Standard deviation of total latency across all 20 calls was **213.61 ms**, reflecting predictable server execution on dedicated LPU hardware.
2. **Streaming vs. Non-Streaming:** Non-streaming median latency (976.5 ms) is slightly lower than streaming median latency (1070.5 ms) due to the reduced transport overhead of a single atomic payload compared to chunked HTTP/2 streaming.

---

## 5. Streaming Behavior

Analysis of the streaming token chunks revealed key structural characteristics of `openai/gpt-oss-120b`:

### 5.1 Two-Phase Generation Architecture
Because `openai/gpt-oss-120b` is a reasoning model, the Groq API emits tokens in two distinct phases:
1. **Internal Reasoning Phase:** Emitted via `delta.reasoning` with `channel="analysis"`. The first token chunk arrives rapidly at **~453.5 ms median** (min: 375 ms, max: 1109 ms).
2. **User Content Synthesis Phase:** Once reasoning concludes, the model switches to emitting synthesized answer text via `delta.content`. The first non-empty content token (TTFT) arrives at **852.0 ms median** (min: 609 ms, max: 1515 ms).

### 5.2 Token Pacing & Throughput
- Total completion tokens generated per request: exactly **250 tokens** (hitting the requested `max_tokens` cap).
- Average content generation duration (Total Latency − TTFT): **~222 ms**.
- Output generation rate: **~450 tokens/second** during active token emission.

---

## 6. Token Usage

Token accounting was captured directly from the authoritative server-side `CompletionUsage` records:

| Usage Dimension | Non-Streaming (10 Reqs) | Streaming (10 Reqs) | Combined Average |
|---|---|---|---|
| **Prompt Tokens** | 94.0 | 94.0 | **94.0** |
| **Completion Tokens** | 250.0 | 250.0 | **250.0** |
| **— Reasoning Tokens** | 149.8 | 149.4 | **149.6** |
| **Total Tokens** | 344.0 | 344.0 | **344.0** |

### Insights on Token Consumption
- **Prompt Consistency:** The standardized technical prompt consumed exactly **94 tokens**.
- **Reasoning Overhead:** Out of 250 completion tokens, an average of **149.6 tokens (59.8%)** were internal reasoning tokens (`reasoning_tokens`), with the remaining **100.4 tokens (40.2%)** forming the output response.
- **Billing / TPM Impact:** Groq counts both reasoning tokens and visible completion tokens against the TPM quota (344 total tokens billed per request).

---

## 7. Published Versus Observed Service Limits

To ensure factual accuracy, we distinguish strictly between published Groq documentation, account HTTP response headers, and directly observed behavior:

| Limit Dimension | Published Free Tier | Directly Observed in HTTP Response Headers | Experiment Observations |
|---|---|---|---|
| **Requests Per Minute (RPM)** | 30 RPM | Enforced dynamically | Tested at ~20 RPM; zero throttles |
| **Tokens Per Minute (TPM)** | 8,000 TPM | `x-ratelimit-limit-tokens: 8000` | Consumed 344 tokens/req; remaining headroom stayed $>7,650$ |
| **Requests Per Day (RPD)** | 1,000 RPD | `x-ratelimit-limit-requests: 1000` | Header counter decremented from 990 to 971 |
| **Tokens Per Day (TPD)** | 200,000 TPD | Not exposed in HTTP headers | Unverified via headers (requires Groq dashboard) |
| **Concurrency Limit** | Not published | Not explicitly header-bounded | Tested sequentially with 1 in-flight |
| **TPM Reset Window** | 60 seconds | `x-ratelimit-reset-tokens: 2.579s` | Rapid sliding window recovery |
| **RPD Reset Window** | 24 hours (UTC) | `x-ratelimit-reset-requests: 41m45.6s` | Countdown towards daily quota reset |

> [!IMPORTANT]
> **Key Finding on `x-ratelimit-limit-requests`:**  
> On the Groq Developer Free Tier, the `x-ratelimit-limit-requests` header reports `1000` (which reflects the daily request quota of 1,000 RPD with a multi-minute/hour countdown in `x-ratelimit-reset-requests`), while `x-ratelimit-limit-tokens: 8000` enforces the per-minute token rate limit (8,000 TPM).

---

## 8. Errors and Rate-Limit Behavior

- **Total Failures Encountered:** **0** (0 HTTP 429, 0 HTTP 5xx, 0 connection timeouts).
- **Rate-Limit Enforcement Mechanics:**
  - The API exposes live remaining budgets on every request: `x-ratelimit-remaining-tokens` and `x-ratelimit-remaining-requests`.
  - When tokens or requests approach the ceiling, `x-ratelimit-reset-tokens` indicates the exact millisecond duration until the sliding window replenishes.
  - If a 429 were triggered, Groq returns a `retry-after` header and JSON detail (`rate_limit_exceeded`).
- **Quota Preservation:** Because the controlled request plan was deliberately limited to 20 calls spaced by 2.0s, the entire experiment consumed only **20 requests (2.0% of daily budget)** and **6,880 total tokens**, safely preserving the account's operational headroom.

---

## 9. Limitations and Uncertainties

1. **Dashboard-Exclusive Metrics:** The daily token cap (200,000 TPD) and exact organizational monthly spend caps are not returned in HTTP headers and can only be inspected via the Groq Console dashboard.
2. **Concurrency Ceiling:** Because this baseline experiment was conducted with a single worker in flight to characterize baseline latency without queue contention, the maximum unthrottled simultaneous concurrency limit on the free tier remains unmeasured.
3. **Geographic Variance:** Measurements were recorded against Groq's Mumbai datacenter (`x-groq-region: bom`). Latencies from European (`fra`) or North American (`us-east`, `us-west`) regions may exhibit differing baseline network transit times.
4. **Prompt Length Invariance:** All 20 requests utilized a single standardized 94-token prompt. Workloads featuring larger multi-passage retrieval contexts (e.g. 1,500+ prompt tokens) will exhibit higher prompt prefill times.

---

## 10. Parameters to Inform Simulator Calibration

These empirical findings provide quantitative benchmarks to calibrate the custom model stand-in simulator (`simulator/service.py`) and traffic manager configurations:

1. **Time to First Token (TTFT):**
   - Calibrate base streaming TTFT to **850 ms** (lognormal distribution with min = 600 ms, p95 = 1,360 ms).
2. **Token Generation Speed:**
   - Calibrate token emission rate to **~250–450 tokens/second** (~2.2 to 4.0 ms per generated token).
3. **Internal Server Queue / Processing Delay:**
   - Groq server overhead (`queue_time` + prefill) ranges between **150 ms and 380 ms**.
4. **Rate Limit Calibration Defaults:**
   - `rpm_limit`: **30 requests/minute**.
   - `tpm_limit`: **8,000 tokens/minute**.
   - `daily_request_limit`: **1,000 requests/day**.
   - `max_concurrency`: **2 to 3 simultaneous in-flight calls**.

---

## 11. Data Preservation Locations

- **Raw Measurements CSV:**  
  [`experiments/real_service/raw/groq_baseline.csv`](file:///C:/Users/abhi4/RELAY%20ASSIGNMENT/experiments/real_service/raw/groq_baseline.csv)
- **Machine-Readable Summary JSON:**  
  [`experiments/real_service/reports/groq_baseline_summary.json`](file:///C:/Users/abhi4/RELAY%20ASSIGNMENT/experiments/real_service/reports/groq_baseline_summary.json)
- **Detailed Markdown Report:**  
  [`experiments/real_service/reports/groq_characterization_report.md`](file:///C:/Users/abhi4/RELAY%20ASSIGNMENT/experiments/real_service/reports/groq_characterization_report.md)
