# Stage 8D Implementation Report: Interactive Simulator Control Center

**Project:** The Relay — Vaani Research ML Engineering Assignment  
**Stage:** 8D — Interactive Simulator Control Center  
**Role:** Frontend & Backend Integration Engineer  
**Date:** November 14, 2026  
**Status:** Complete & Fully Validated against Local Simulator  

---

## 1. Executive Summary

Stage 8D transforms the frontend settings interface (`frontend/src/pages/SettingsPage.tsx`) from a static placeholder into a professional, data-driven **Simulator Control Center**. The control plane enables users to inspect and configure the local stand-in model service (`simulator/main.py`) via its administrative endpoints.

All controls operate strictly on empirically supported parameters defined in `SimulatorConfig` (calibrated during Stage 4 against real Groq characterization). The implementation enforces **ironclad provider safety guardrails**: simulator controls are active exclusively when `MODEL_PROVIDER=simulator`. Under Groq cloud mode, controls are disabled with clear architectural explanations, and configuration requests are prevented from ever reaching external cloud providers.

Every test and live stack verification ran **strictly against the local simulator (`http://127.0.0.1:8001`) with zero Groq API calls** and zero financial expenditure.

---

## 2. Files Changed and Created

| File | Status | Description |
| :--- | :--- | :--- |
| `simulator/service.py` | Modified | Added `reset_config()` to restore baseline calibrated configuration. Added complete configuration object export (`config: self.config.model_dump()`) to `get_status()`. |
| `simulator/main.py` | Modified | Added `CORSMiddleware`. Implemented `GET /admin/config` (returns complete configuration) and `POST /admin/reset-config` (restores baseline defaults). |
| `frontend/vite.config.ts` | Modified | Configured proxy routes `/admin` and `/simulator/*` forwarding to the simulator target (`http://127.0.0.1:8001`). |
| `frontend/src/types/api.ts` | Modified | Defined TypeScript schemas: `SimulatorConfigData`, `SimulatorStatusResponse`, `SimulatorConfigureResponse`, and `SimulatorResetResponse`. |
| `frontend/src/services/api.ts` | Modified | Added `getSimulatorStatus()`, `getSimulatorConfig()`, `configureSimulator()`, `resetSimulator()`, and `resetSimulatorConfig()` with client-side provider safety guards. |
| `frontend/src/pages/SettingsPage.tsx` | Created | Built full Interactive Simulator Control Center with live status badges, latency sliders, fault injection controls, rate-limit inputs, unsaved change tracking, and confirmation dialogs. |
| `frontend/tests/client.test.ts` | Modified | Added mock handlers and Tests 19–26 validating simulator status reading, configuration updates, 400 rejection, Groq provider guards, and reset operations. |
| `frontend/tests/e2e_live_stack.test.ts` | Modified | Added Tests 8–14 testing live stack proxy resolution, status polling, dynamic configuration updates, invalid parameter rejection, baseline restoration, state clearing, and live fault injection recovery. |
| `reports/stage_8d_simulator_controls.md` | Created | This deliverable implementation report. |

---

## 3. Simulator Endpoints Used and Exposed

The frontend communicates with the simulator service via the Vite proxy (`/simulator/*` $\to$ `http://127.0.0.1:8001/*`):

| Endpoint | HTTP Method | Scope | Description |
| :--- | :--- | :--- | :--- |
| `/simulator/health` | `GET` | Monitoring | Lightweight health check returning service name and status. |
| `/simulator/status` | `GET` | Observability | Live status, in-flight reservations, sliding-window RPM/TPM usage, daily request/token budgets, and lifetime counters. |
| `/simulator/admin/config` | `GET` | Admin | Returns the complete current 17-parameter configuration object. |
| `/simulator/admin/configure` | `POST` | Admin | Dynamically updates runtime parameters (latencies, quotas, failure modes) without requiring server restart. |
| `/simulator/admin/reset` | `POST` | Admin | Clears runtime counters, sliding-window rate tracking deques, and in-flight reservations. |
| `/simulator/admin/reset-config` | `POST` | Admin | Restores configuration parameters to the Stage 4 calibrated baseline defaults. |

---

## 4. Supported Simulator Configuration Fields

The control center exposes controls exclusively for supported fields in `SimulatorConfig`:

### A. Response Latency & Streaming Parameters
- **Base Artificial Delay (`base_delay_ms`):** Slider + number input (0 to 4,000 ms, calibrated: 976.5 ms).
- **Latency Jitter / StdDev (`jitter_ms`):** Slider + number input (0 to 800 ms, calibrated: 174.0 ms).
- **Streaming TTFT (`ttft_ms`):** Slider + number input (0 to 3,000 ms, calibrated: 852.0 ms).
- **TTFT Jitter (`ttft_stddev_ms`):** Calibrated standard deviation (234.55 ms).
- **Streaming Inter-Chunk Delay (`inter_chunk_delay_ms`):** Slider + number input (0 to 100 ms, calibrated: 20.0 ms).
- **Number of Stream Chunks (`num_stream_chunks`):** Number input (1 to 32, calibrated: 8).
- **Latency Distribution (`latency_distribution`):** Dropdown selector (`lognormal`, `normal`, `uniform`).
- **Load Slowdown Factor (`load_slowdown_factor`):** Slider (0.00 to 0.25, calibrated: +5% per in-flight request).

### B. Fault Injection & Resilience Testing
- **Transient Failure Rate (`failure_rate`):** Slider from 0.0% to 100.0% (probability of simulated HTTP 500 error).
- **Deterministic Forced Failure Mode (`deterministic_failure`):** Dropdown selector:
  - `None` (Normal execution)
  - `rate_limit` (Forced HTTP 429 Rate Limit Exceeded)
  - `server_error` (Forced HTTP 500 Server Error)
  - `timeout` (Forced HTTP 504 Gateway Timeout)
  - `auth_error` (Forced HTTP 401 Authentication Error)
  - `overload` (Forced HTTP 429 Concurrency Overload)

### C. Rate Limits & Concurrency Quotas
- **Sliding-Window RPM Limit (`rpm_limit`):** Number input (1 to 1,000, calibrated: 30 RPM).
- **Sliding-Window TPM Limit (`tpm_limit`):** Number input (100 to 100,000, calibrated: 8,000 TPM).
- **Max Concurrent Requests (`max_concurrent_requests`):** Number input (1 to 50, calibrated: 10).
- **Daily Request Budget (`daily_budget`):** Number input (10 to 50,000, standard: 1,000 RPD).
- **Daily Token Budget (`daily_token_budget`):** Number input (1,000 to 2,000,000, standard: 200,000 TPD).
- **Retry-After Override (`retry_after_seconds`):** Optional number input (empty = dynamically computed from window).

---

## 5. Safety and Provider Protection Guardrails

To prevent accidental modification of production environments or leaking credentials:

1. **Provider Isolation:**
   - Active provider is determined authoritatively via the backend `/ready` probe (`ready?.provider`).
   - If `ready?.provider !== 'simulator'` (e.g. `groq`), the entire fieldset is locked (`disabled={true}`).
   - An alert banner is displayed:
     > *"Simulator Controls Disabled: Active Provider is GROQ (Cloud LLM API). Live cloud LLM endpoints enforce upstream rate limits and latencies that cannot be configured via local simulator admin endpoints. To test mock latencies, deterministic faults, and simulated rate-limiting, stop the backend and restart with MODEL_PROVIDER=simulator."*
2. **Client-Side Defense in Depth:**
   - Methods `api.configureSimulator()`, `api.resetSimulator()`, and `api.resetSimulatorConfig()` take `activeProvider` as a parameter.
   - If `activeProvider !== 'simulator'`, the client throws an `ApiError` (HTTP 403) before any network request can be dispatched.
3. **Zero Secrets in Browser:**
   - No API keys (`GROQ_API_KEY`) are ever transmitted, inspected, or displayed on the frontend.
4. **Non-Destructive Execution History:**
   - Admin reset operations clear only volatile in-memory sliding windows and daily counters in the simulator process; they do not touch disk experiments or CSV benchmark files.

---

## 6. User Experience & Validation Features

- **Real-Time Input Validation:** Client-side range checking prevents negative delays, invalid failure probabilities ($> 1.0$), or RPM $< 1$.
- **Dirty State Tracking:** An amber badge displays the exact count of unsaved configuration changes (e.g., `2 unsaved configuration change(s)`).
- **Confirmation Modals:**
  - **Reset to Defaults:** Requires explicit confirmation before restoring Stage 4 baseline parameters.
  - **Reset Counters / State:** Destructive warning modal before clearing in-flight requests and sliding-window rate limit deques.
- **Live Observability Dashboard:**
  - Hero gauges for service health (`HEALTHY (:8001)` vs `OFFLINE`), in-flight slots, current 60s RPM/TPM window, and daily request usage.
  - Lifetime observability table reporting total requests, successes, 500 failures, 429 rate limits, overload hits, and client cancellations.

---

## 7. Verification and Test Results

### A. Frontend Client & Contract Unit Tests (`tests/client.test.ts`)
```bash
node --experimental-strip-types tests/client.test.ts
```
**Results:** All 26 tests PASSED (duration: 221ms).
- **Test 19:** `getSimulatorStatus()` parses healthy status, limits, and usage.
- **Test 20:** `getSimulatorConfig()` parses all configuration parameters.
- **Test 21:** `configureSimulator()` applies valid configuration updates.
- **Test 22:** `configureSimulator()` rejects invalid parameters with HTTP 400.
- **Test 23:** Provider guard rejects configuration when active provider is Groq (HTTP 403).
- **Test 24:** Provider guard rejects simulator reset when active provider is Groq (HTTP 403).
- **Test 25:** `resetSimulator()` resets runtime counters and state.
- **Test 26:** `resetSimulatorConfig()` resets configuration to baseline defaults.

### B. End-to-End Live Stack Integration Tests (`tests/e2e_live_stack.test.ts`)
```bash
node --experimental-strip-types tests/e2e_live_stack.test.ts
```
**Results:** All 14 tests PASSED (duration: 5.21s).
- **Test 8:** `GET /simulator/status` returns live status and usage via Vite proxy.
- **Test 9:** `GET /simulator/admin/config` returns full configuration.
- **Test 10:** `POST /simulator/admin/configure` dynamically updates configuration.
- **Test 11:** `POST /simulator/admin/configure` rejects invalid values with HTTP 400.
- **Test 12:** `POST /simulator/admin/reset-config` restores calibrated baseline defaults.
- **Test 13:** `POST /simulator/admin/reset` resets runtime counters.
- **Test 14:** **Dynamic Fault Injection:**
  1. Injected `deterministic_failure: 'rate_limit'` into simulator.
  2. Queried `/v1/ask` $\to$ verified backend LangGraph workflow catches model error and returns clean refusal status.
  3. Reset configuration via `/simulator/admin/reset-config`.
  4. Queried `/v1/ask` $\to$ verified immediate recovery with verified answer containing `27.3 BLEU`.

### C. Backend API, Simulator & TrafficManager Tests (`pytest`)
```bash
uv run pytest tests/test_simulator.py tests/test_api.py tests/test_traffic_manager.py -q
```
**Results:** 65 passed in 45.65s.
- 20 simulator unit tests: PASSED.
- 17 API route and metrics tests: PASSED.
- 28 TrafficManager concurrency, queue, and rate limiting tests: PASSED.

### D. Frontend Code Quality & Build
```bash
npm run lint --prefix frontend # oxlint
npm run build --prefix frontend # tsc -b && vite build
```
- **Linting:** 0 warnings, 0 errors across 26 files.
- **Production Build:** Built cleanly in 5.00s (`index.html`, `index.css` 46.7 kB, `index.js` 344.7 kB).

---

## 8. Operational Limitations

1. **In-Memory Volatility:** Simulator configuration and sliding-window deques reside in the process memory of `simulator/main.py`. Restarting the simulator process restores the hardcoded Stage 4 calibrated baseline.
2. **Local Simulation Scope:** The simulator accurately emulates rate-limiting equations, token estimation, and lognormal latency distributions of `openai/gpt-oss-120b`, but does not attempt to replicate cloud provider internal cluster scheduling.
3. **Stateless Workflow Refusal:** When deterministic faults are injected, the LangGraph research workflow surfaces provider errors as grounded refusals (`status: 'refused'`) rather than crashing the HTTP server, ensuring high gateway availability.
