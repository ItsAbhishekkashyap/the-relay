# Stage 8C Implementation Report: Live System Monitoring Dashboard

**Project:** The Relay — Vaani Research ML Engineering Assignment  
**Stage:** 8C — Live System Monitoring Dashboard  
**Role:** Frontend & Backend Integration Engineer  
**Date:** November 14, 2026  
**Status:** Complete & Fully Validated against Local Simulator  

---

## 1. Executive Summary

Stage 8C extends **The Relay Research Assistant** with a production-grade, data-driven live system monitoring dashboard. The dashboard provides complete operational visibility into request volume, queue depth, concurrency utilization, rate-limiting quotas, and live provider execution latency percentiles ($p_{50}$, $p_{95}$, $p_{99}$).

To preserve architectural integrity, no existing API contracts (`/v1/ask`, `/health`, `/ready`) were altered. A minimal, dedicated read-only backend endpoint—`GET /v1/metrics`—was added to expose telemetry maintained by `TrafficManager` and `TrafficMetricsTracker`. On the frontend, `frontend/src/pages/OverviewPage.tsx` was transformed into an interactive live monitoring control plane featuring automatic 5-second polling, in-flight request deduplication, stale data preservation with warning alerts, and real-time seconds-elapsed telemetry.

All development, verification, and end-to-end testing were conducted **strictly against the local stand-in model simulator (`MODEL_PROVIDER=simulator`)** on `http://127.0.0.1:8001`, ensuring **zero Groq API requests** and zero financial expenditure.

---

## 2. Files Created and Modified

| File | Status | Description |
| :--- | :--- | :--- |
| `app/traffic/metrics.py` | Modified | Added a thread-safe rolling latency buffer (`collections.deque(maxlen=1000)`), `record_latency(latency_ms)`, and `_get_latency_stats_unlocked()`. Extended `TrafficMetricsSnapshot` with optional `latency_stats` dictionary. |
| `app/traffic/manager.py` | Modified | Instrumented `_execute_request` and `stream` to measure actual provider execution durations and record them into `TrafficMetricsTracker`. |
| `app/api/schemas.py` | Modified | Defined Pydantic models for the metrics contract: `MetricsResponse`, `RequestStats`, `QueueStats`, `ConcurrencyStats`, `RateLimitStats`, `LatencyStats`, and `ProviderInfo`. |
| `app/api/routes.py` | Modified | Implemented `GET /v1/metrics`: read-only endpoint extracting runtime metrics snapshots from `TrafficManager`, calculating queue utilization percentage, and packaging latency percentiles. |
| `tests/test_api.py` | Modified | Added 3 unit tests (`test_metrics_endpoint_contract`, `test_metrics_endpoint_unavailable_latency`, `test_metrics_endpoint_read_only_idempotence`) validating the `/v1/metrics` schema, empty-state behavior, and idempotence. |
| `frontend/src/types/api.ts` | Modified | Added TypeScript interfaces matching backend metrics schemas: `MetricsResponse`, `RequestStats`, `QueueStats`, `ConcurrencyStats`, `RateLimitStats`, and `LatencyStats`. |
| `frontend/src/services/api.ts` | Modified | Added `api.getMetrics(externalSignal?: AbortSignal): Promise<MetricsResponse>` querying `/v1/metrics` with JSON parsing and error handling. |
| `frontend/src/pages/OverviewPage.tsx` | Modified | Transformed into a live telemetry dashboard featuring 5s auto-polling, stale data banners, System Status hero, Request Stats KPIs, Traffic & Queue gauges, Latency percentiles, and Rate Quota cards. |
| `frontend/tests/client.test.ts` | Modified | Added mock handler for `/v1/metrics` and Tests 17–18 verifying frontend schema parsing, queue utilization calculations, and connection failure handling. |
| `frontend/tests/e2e_live_stack.test.ts` | Modified | Added Test 7 verifying live proxy resolution (`:5173/v1/metrics` $\to$ `:8000/v1/metrics`), simulator provider verification, queue capacity, concurrency limits, and latency object structure. |
| `reports/stage_8c_monitoring_dashboard.md` | Created | This deliverable implementation report. |

---

## 3. Metrics Exposed by the Backend (`GET /v1/metrics`)

The endpoint `GET /v1/metrics` returns a structured JSON payload conforming to `MetricsResponse`:

```json
{
  "timestamp": "2026-11-14T05:42:15.289548+00:00",
  "provider": {
    "provider_name": "simulator",
    "model_name": "simulator/mock-model-v1"
  },
  "requests": {
    "total_submitted": 3,
    "successful": 3,
    "failed": 0,
    "rate_limited": 0,
    "timed_out": 0,
    "retried": 0,
    "queue_rejections": 0,
    "client_cancellations": 0
  },
  "queue": {
    "current_depth": 0,
    "capacity": 50,
    "utilization_pct": 0.0
  },
  "concurrency": {
    "active_in_flight": 0,
    "peak_in_flight": 1,
    "max_concurrency": 5
  },
  "rate_limits": {
    "rpm_limit": null,
    "tpm_limit": null,
    "completed_rpm": 3,
    "reserved_rpm": 0,
    "completed_tpm": 3173,
    "reserved_tpm": 0
  },
  "latency": {
    "available": true,
    "sample_count": 3,
    "measurement_scope": "Provider execution duration via TrafficManager (rolling 1,000 requests)",
    "p50_ms": 1110.0,
    "p95_ms": 1110.0,
    "p99_ms": 1110.0,
    "avg_ms": 1078.0,
    "min_ms": 859.0,
    "max_ms": 1265.0
  }
}
```

---

## 4. Source of Each Displayed Metric

Every metric displayed on the dashboard is grounded in live runtime measurements. No values are fabricated or derived from offline experiment CSV files:

| Metric Group | Field | Runtime Source |
| :--- | :--- | :--- |
| **System Info** | `provider_name`, `model_name` | `app.state.traffic_manager.provider.provider_name` / `model_name` |
| **System Info** | `timestamp` | ISO 8601 UTC timestamp generated dynamically at response time |
| **Requests** | `total_submitted` | `TrafficMetricsTracker.requests_total` counter |
| **Requests** | `successful` | `TrafficMetricsTracker.requests_success` counter |
| **Requests** | `failed` | `TrafficMetricsTracker.requests_failed` counter |
| **Requests** | `rate_limited` | `TrafficMetricsTracker.rate_limited_429` counter |
| **Requests** | `timed_out` | `TrafficMetricsTracker.timed_out_504` counter |
| **Requests** | `retried` | `TrafficMetricsTracker.retries_total` counter |
| **Requests** | `queue_rejections` | `TrafficMetricsTracker.queue_rejections` counter |
| **Requests** | `client_cancellations` | `TrafficMetricsTracker.client_cancellations` counter |
| **Queue** | `current_depth` | `TrafficManager.queue.qsize()` via snapshot |
| **Queue** | `capacity` | `TrafficManager.config.max_queue_depth` (configured: 50) |
| **Queue** | `utilization_pct` | Derived in route: `round((current_depth / capacity) * 100.0, 2)` |
| **Concurrency** | `active_in_flight` | `TrafficMetricsTracker.active_in_flight` gauge |
| **Concurrency** | `peak_in_flight` | `TrafficMetricsTracker.peak_in_flight` gauge |
| **Concurrency** | `max_concurrency` | `TrafficManager.config.max_concurrency` (configured: 5) |
| **Rate Limits** | `rpm_limit`, `tpm_limit` | `TrafficManager.config.rpm_limit` / `tpm_limit` (`null` when unthrottled) |
| **Rate Limits** | `completed_rpm`, `reserved_rpm` | `RateLimiter._completed_rpm_unlocked()`, `_reserved_rpm_unlocked()` (60s sliding window) |
| **Rate Limits** | `completed_tpm`, `reserved_tpm` | `RateLimiter._completed_tpm_unlocked()`, `_reserved_tpm_unlocked()` (60s sliding window) |
| **Latency** | `available`, `sample_count` | `TrafficMetricsTracker._latency_window` sample count ($N \ge 1$) |
| **Latency** | $p_{50}$, $p_{95}$, $p_{99}$, avg, min, max | Computed via `numpy.percentile` over thread-safe `deque(maxlen=1000)` of provider call durations |

---

## 5. Metrics That Remain Unavailable and Why

The following metrics are intentionally marked as unavailable or omitted, rather than mocked:

1. **Live Latency Percentiles at Startup (`sample_count == 0`):**
   - **Status:** `latency.available: false`, all percentile fields `null`.
   - **Reason:** Prior to processing requests through `TrafficManager`, no provider execution durations exist. Calculating percentiles on an empty set is mathematically undefined. The dashboard displays an informative "Awaiting traffic samples" message instead of fabricating zero or arbitrary values.
2. **Provider RPM/TPM Caps (`rpm_limit: null`, `tpm_limit: null` under Simulator):**
   - **Status:** Rendered as `Unrestricted` with infinity symbol ($\infty$).
   - **Reason:** The stand-in simulator has no upstream quota restrictions. Only Groq-configured deployments apply explicit RPM/TPM ceilings.
3. **GPU Memory and Host Hardware Utilization:**
   - **Status:** Not included in `/v1/metrics`.
   - **Reason:** The relay application executes remotely against cloud LLM APIs or the HTTP simulator; it does not host local weights on an accelerator. Instrumenting host OS metrics is outside the scope of `TrafficManager`.
4. **Upstream Provider Cluster Queue Depths:**
   - **Status:** Not included.
   - **Reason:** External providers (such as Groq or OpenAI) do not expose internal queuing telemetry. Only the local client-side queue managed by `TrafficManager` can be authoritatively measured.

---

## 6. Frontend Refresh Behavior

`frontend/src/pages/OverviewPage.tsx` implements robust telemetry polling:

- **5-Second Polling Loop:** Uses a `setInterval` timer (5,000ms) with immediate invocation on initial mount.
- **In-Flight Concurrency Lock:** Prevents overlapping asynchronous requests. A `fetchingRef` lock drops new timer ticks if a prior poll is still awaiting response.
- **Unmount Cleanup:** Clears active intervals and cancels pending HTTP requests via `AbortController` when navigating away from the page.
- **Stateless Stale Snapshot Preservation:** If a transient network glitch or gateway timeout occurs:
  - The previously loaded `metrics` snapshot is retained on screen.
  - A prominent amber alert banner appears: *"Telemetry Stale: Unable to reach /v1/metrics. Displaying last valid snapshot from HH:MM:SS."*
  - The dashboard is never wiped to zero, preventing UI flicker.
- **Seconds-Elapsed Counter:** A 1-second secondary timer increments a `secondsAgo` counter, providing immediate visual feedback on telemetry freshness.
- **Manual "Refresh Now" Action:** Users can trigger an instant out-of-cycle poll at any time.

---

## 7. Verification and Test Results

### A. Frontend Unit & Contract Tests (`tests/client.test.ts`)
```bash
node --experimental-strip-types tests/client.test.ts
```
**Results:** All 18 tests PASSED (duration: 126ms).
- Validated `GET /v1/metrics` contract parsing.
- Validated queue utilization calculation and latency percentiles.
- Validated graceful handling of unreachable endpoints and error states.

### B. End-to-End Live Stack Integration Tests (`tests/e2e_live_stack.test.ts`)
```bash
node --experimental-strip-types tests/e2e_live_stack.test.ts
```
**Results:** All 7 tests PASSED (duration: 4.58s).
- **Test 1:** Live readiness probe confirms simulator provider and initialized components.
- **Test 2:** Transformer base BLEU on English-to-German returns 27.3 with verified citation.
- **Test 3:** Out-of-domain query returns grounded refusal.
- **Test 4:** Paper filter validation restricts retrieval to target paper.
- **Test 5:** Empty question rejected with HTTP 422.
- **Test 6:** Invalid paper filter rejected with HTTP 422.
- **Test 7:** Stage 8C `GET /v1/metrics` verified through Vite proxy (`:5173/v1/metrics`):
  - `provider.provider_name === 'simulator'`
  - `queue.capacity === 50`, `current_depth >= 0`
  - `concurrency.max_concurrency === 5`
  - Latency object structure validated.

### C. Backend API & TrafficManager Unit Tests (`pytest`)
```bash
uv run pytest tests/test_api.py tests/test_traffic_manager.py -q
```
**Results:** 45 passed in 21.15s.
- `test_metrics_endpoint_contract`: PASSED.
- `test_metrics_endpoint_unavailable_latency`: PASSED.
- `test_metrics_endpoint_read_only_idempotence`: PASSED.
- 28 `TrafficManager` queue, concurrency, and rate-limiting tests: PASSED.

### D. Frontend Code Quality & Build
```bash
npm run lint --prefix frontend # oxlint
npm run build --prefix frontend # tsc -b && vite build
```
- **Linting:** 0 warnings, 0 errors across 26 files.
- **Production Build:** Successfully bundled client assets (`index.html`, `index.css` 44.5 kB, `index.js` 315.3 kB) in 1.65s.

---

## 8. Confirmation of Simulator Mode (Zero Groq API Requests)

All tests and live runs were performed with `MODEL_PROVIDER=simulator`:

1. **Environment Verification:** `.env` and backend process set `MODEL_PROVIDER=simulator`.
2. **API Verification:** `GET /ready` confirms `provider: "simulator"` and `model: "simulator/mock-model-v1"`.
3. **Metrics Verification:** `GET /v1/metrics` returns `provider.provider_name: "simulator"`.
4. **Simulator Counters:** All requests were routed to `http://127.0.0.1:8001`, with zero external network traffic or Groq API charges.

---

## 9. Visual Layout and Dashboard Sections

The updated `OverviewPage.tsx` is organized into a modular grid:

1. **Header & Freshness Bar:**
   - Displays page title, live connection status pill (`Live Telemetry (5s)`), "last updated $N$s ago", and manual "Refresh Now" button.
   - Shows amber stale alert banner when background polling encounters errors.
2. **System Status Hero Card:**
   - Visual status badge (`Operational` / `Degraded`), provider name (`simulator`), active model (`simulator/mock-model-v1`), and gateway ping round-trip latency.
3. **Request Statistics KPI Grid (6 Cards):**
   - **Total Submitted:** Total lifetime requests received by `TrafficManager`.
   - **Successful:** Successfully completed requests with percentage success rate.
   - **Failed:** Failed requests with error rate percentage.
   - **Rate Limited (429):** Total requests throttled by provider or local quotas.
   - **Timed Out (504):** Total requests aborted by queue or execution deadlines.
   - **Retries Triggered:** Automatic recovery attempts performed by `TrafficManager`.
4. **Traffic & Queue Monitoring:**
   - **Queue Depth Gauge:** Current waiting requests vs. capacity (50) with animated progress bar and utilization percentage.
   - **Concurrency Gauge:** Active in-flight executions vs. concurrency ceiling (5), plus lifetime peak in-flight requests.
5. **Live Latency Telemetry:**
   - Displays rolling percentiles: $p_{50}$ (median), $p_{95}$, $p_{99}$, and minimum / maximum / average execution durations in milliseconds.
   - Clarifies measurement scope: *"Provider execution duration via TrafficManager (rolling 1,000 requests)"*.
6. **Local Rate Admission Quotas:**
   - Sliding 60-second window consumption: Completed RPM vs. limit, Reserved RPM, Completed TPM vs. limit, and Reserved TPM.
7. **Discovered Endpoints Reference:**
   - Direct interactive reference table displaying all active backend routes (`/v1/ask`, `/v1/metrics`, `/health`, `/ready`), methods, and operational descriptions.
