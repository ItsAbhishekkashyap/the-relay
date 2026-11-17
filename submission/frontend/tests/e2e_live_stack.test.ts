/**
 * End-to-end live stack integration tests.
 * Validates the live Vite proxy (http://localhost:5173) and FastAPI backend (http://127.0.0.1:8000)
 * running with the local simulator provider (MODEL_PROVIDER=simulator).
 */

import { test, describe, before, beforeEach } from 'node:test';
import assert from 'node:assert/strict';

const BASE_URL = 'http://localhost:5173';
const SIMULATOR_URL = 'http://127.0.0.1:8001';

async function resetSimulatorCounters() {
  try {
    await fetch(`${SIMULATOR_URL}/admin/reset`, { method: 'POST' });
    await fetch(`${SIMULATOR_URL}/admin/reset-config`, { method: 'POST' });
  } catch {
    // optional reset if reachable
  }
}

describe('Stage 8B Live Stack E2E Validation (Vite -> FastAPI -> Simulator)', () => {
  before(async () => {
    await resetSimulatorCounters();
  });

  beforeEach(async () => {
    await resetSimulatorCounters();
  });
  test('1. Live readiness probe confirms simulator provider and initialized components', async () => {
    const res = await fetch(`${BASE_URL}/ready`);
    assert.equal(res.status, 200, `Expected 200 OK, got ${res.status}`);
    const data = await res.json();

    assert.equal(data.status, 'ready');
    assert.equal(data.provider, 'simulator', 'Provider MUST be simulator (zero Groq requests)');
    assert.equal(data.components.retriever, 'initialized');
    assert.equal(data.components.traffic_manager, 'initialized');
    assert.equal(data.components.workflow, 'initialized');
  });

  test('2. Critical Target Query: Transformer base BLEU on English-to-German', async () => {
    const query = 'What BLEU score did the Transformer base model achieve on English-to-German?';
    const res = await fetch(`${BASE_URL}/v1/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: query }),
    });

    assert.equal(res.status, 200);
    const data = await res.json();

    // Verify Provider
    assert.equal(data.provider, 'simulator');

    // Verify Verification Status
    assert.equal(data.status, 'verified');

    // Verify Answer content: Must contain 27.3
    assert.match(data.answer, /27\.3/, 'Answer must state 27.3 BLEU');
    assert.match(data.answer, /base model/i);

    // Verify Citation
    assert.ok(data.citations.length >= 1, 'Expected at least 1 citation');
    const citation = data.citations[0];
    assert.equal(citation.is_verified, true, 'Citation must be verified');
    assert.equal(citation.paper_id, '1706.03762v7');
    assert.equal(citation.page_number, 8);
    assert.equal(citation.section, '6.1 Machine Translation');

    // Verify Retrieved Evidence
    assert.ok(data.retrieved_passages.length >= 1);
    const tableChunk = data.retrieved_passages.find(
      (p: any) => p.chunk_id === '1706.03762v7_lc_0026' || p.content.includes('27.3')
    );
    assert.ok(tableChunk, 'Chunk with 27.3 and Table 2 must be present in retrieved passages');
    assert.match(tableChunk.content, /27\.3/);
    assert.match(tableChunk.content, /Table 2/);
    assert.match(tableChunk.content, /Transformer \(base model\)/);
  });

  test('3. Out-of-Domain Query: Grounded refusal verification', async () => {
    const query = 'What was the quantum volume of the Sycamore processor in 2019?';
    const res = await fetch(`${BASE_URL}/v1/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: query }),
    });

    assert.equal(res.status, 200);
    const data = await res.json();

    assert.equal(data.provider, 'simulator');
    assert.equal(data.status, 'refused', 'Status must be refused');
    assert.match(data.answer, /unable to answer/i);
    assert.ok(data.refusal_reason && data.refusal_reason.length > 0);
    assert.equal(data.citations.length, 0, 'Refused responses must have 0 citations');
  });

  test('4. Paper Filter Validation: Supported filter works as expected', async () => {
    const query = 'What is the attention formula?';
    const res = await fetch(`${BASE_URL}/v1/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question: query,
        paper_filter: '1706.03762v7',
      }),
    });

    assert.equal(res.status, 200);
    const data = await res.json();
    assert.equal(data.provider, 'simulator');
    // All retrieved passages must be from the filtered paper
    for (const doc of data.retrieved_passages) {
      assert.equal(doc.paper_id, '1706.03762v7');
    }
  });

  test('5. Error Handling: Rejects empty question with 422', async () => {
    const res = await fetch(`${BASE_URL}/v1/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: '   ' }),
    });

    assert.equal(res.status, 422, 'Empty question must return HTTP 422');
  });

  test('6. Error Handling: Rejects invalid paper filter with 422', async () => {
    const res = await fetch(`${BASE_URL}/v1/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question: 'Valid question',
        paper_filter: 'unsupported_paper_id',
      }),
    });

    assert.equal(res.status, 422, 'Invalid paper filter must return HTTP 422');
  });

  test('7. Stage 8C Metrics Endpoint: GET /v1/metrics returns live telemetry', async () => {
    const res = await fetch(`${BASE_URL}/v1/metrics`);
    assert.equal(res.status, 200, `Expected 200 OK, got ${res.status}`);
    const data = await res.json();

    // Verify provider info
    assert.equal(data.provider.provider_name, 'simulator');
    assert.ok(data.provider.model_name);
    assert.ok(data.collected_at || data.timestamp);

    // Verify queue stats
    assert.equal(data.queue.capacity, 50);
    assert.ok(data.queue.current_depth >= 0);
    assert.ok(typeof data.queue.utilization_pct === 'number');

    // Verify concurrency stats
    assert.equal(data.concurrency.max_concurrency, 5);
    assert.ok(data.concurrency.active_in_flight >= 0);

    // Verify requests stats
    assert.ok(data.requests.total_submitted >= 0);
    assert.ok(data.requests.successful >= 0);

    // Verify latency stats structure
    assert.ok(typeof data.latency.available === 'boolean');
    if (data.latency.available) {
      assert.ok(typeof data.latency.p50_ms === 'number');
      assert.ok(typeof data.latency.p95_ms === 'number');
      assert.ok(typeof data.latency.p99_ms === 'number');
    }
  });

  test('8. Stage 8D Simulator API: GET /simulator/status returns live status and usage', async () => {
    const res = await fetch(`${BASE_URL}/simulator/status`);
    assert.equal(res.status, 200, `Expected 200 OK, got ${res.status}`);
    const data = await res.json();

    assert.equal(data.status, 'healthy');
    assert.equal(typeof data.in_flight_requests, 'number');
    assert.ok(data.current_window);
    assert.ok(data.daily_request_usage);
    assert.ok(data.lifetime_metrics);
  });

  test('9. Stage 8D Simulator API: GET /simulator/admin/config returns full configuration', async () => {
    const res = await fetch(`${BASE_URL}/simulator/admin/config`);
    assert.equal(res.status, 200, `Expected 200 OK, got ${res.status}`);
    const cfg = await res.json();

    assert.ok(typeof cfg.base_delay_ms === 'number');
    assert.ok(typeof cfg.jitter_ms === 'number');
    assert.ok(typeof cfg.ttft_ms === 'number');
    assert.ok(typeof cfg.rpm_limit === 'number');
    assert.ok(typeof cfg.tpm_limit === 'number');
    assert.ok(typeof cfg.max_concurrent_requests === 'number');
  });

  test('10. Stage 8D Simulator API: POST /simulator/admin/configure dynamically updates config', async () => {
    const updatePayload = {
      base_delay_ms: 150.0,
      jitter_ms: 25.0,
      failure_rate: 0.05,
    };
    const res = await fetch(`${BASE_URL}/simulator/admin/configure`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updatePayload),
    });
    assert.equal(res.status, 200, `Expected 200 OK, got ${res.status}`);
    const data = await res.json();

    assert.equal(data.status, 'updated');
    assert.equal(data.config.base_delay_ms, 150.0);
    assert.equal(data.config.jitter_ms, 25.0);
    assert.equal(data.config.failure_rate, 0.05);

    // Verify GET /simulator/admin/config reflects the update
    const getRes = await fetch(`${BASE_URL}/simulator/admin/config`);
    const getCfg = await getRes.json();
    assert.equal(getCfg.base_delay_ms, 150.0);
  });

  test('11. Stage 8D Simulator API: POST /simulator/admin/configure rejects invalid values with 400', async () => {
    const res = await fetch(`${BASE_URL}/simulator/admin/configure`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ base_delay_ms: -50.0 }),
    });
    assert.equal(res.status, 400, 'Negative delay must be rejected with HTTP 400');
  });

  test('12. Stage 8D Simulator API: POST /simulator/admin/reset-config restores calibrated baseline', async () => {
    const res = await fetch(`${BASE_URL}/simulator/admin/reset-config`, {
      method: 'POST',
    });
    assert.equal(res.status, 200);
    const data = await res.json();

    assert.equal(data.status, 'config_reset');
    assert.equal(data.config.base_delay_ms, 976.5);
    assert.equal(data.config.jitter_ms, 174.0);
    assert.equal(data.config.failure_rate, 0.0);
  });

  test('13. Stage 8D Simulator API: POST /simulator/admin/reset resets runtime counters', async () => {
    const res = await fetch(`${BASE_URL}/simulator/admin/reset`, {
      method: 'POST',
    });
    assert.equal(res.status, 200);
    const data = await res.json();
    assert.equal(data.status, 'reset_successful');
  });

  test('14. Stage 8D Dynamic Fault Injection: Injected rate limit alters live system behavior and recovers', async () => {
    // 1. Inject deterministic rate limit into simulator
    const injectRes = await fetch(`${BASE_URL}/simulator/admin/configure`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ deterministic_failure: 'rate_limit' }),
    });
    assert.equal(injectRes.status, 200);

    // 2. Query /v1/ask - LangGraph workflow catches model failure and returns refusal status
    const askRes = await fetch(`${BASE_URL}/v1/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: 'What BLEU score did the Transformer base model achieve on English-to-German?' }),
    });
    assert.equal(askRes.status, 200);
    const askData = await askRes.json();
    assert.equal(askData.status, 'refused');
    assert.match(askData.refusal_reason, /Model generation failed|rate_limit/i);

    // 3. Reset simulator configuration to restore normal execution
    const resetRes = await fetch(`${BASE_URL}/simulator/admin/reset-config`, {
      method: 'POST',
    });
    assert.equal(resetRes.status, 200);

    // 4. Query /v1/ask again - should now succeed normally with verified status and 27.3
    const recoverRes = await fetch(`${BASE_URL}/v1/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: 'What BLEU score did the Transformer base model achieve on English-to-German?' }),
    });
    assert.equal(recoverRes.status, 200);
    const recoverData = await recoverRes.json();
    assert.equal(recoverData.status, 'verified');
    assert.match(recoverData.answer, /27\.3/);
  });

  test('15. Stage 8E Live E2E: GET /v1/experiments/overview returns dataset catalog', async () => {
    const res = await fetch(`${BASE_URL}/v1/experiments/overview`);
    assert.equal(res.status, 200);
    const data = await res.json();
    assert.equal(data.status, 'available');
    assert.equal(data.pricing_basis.prompt_tokens_per_million_usd, 0.15);
    assert.equal(data.pricing_basis.completion_tokens_per_million_usd, 0.60);
    assert.equal(data.datasets.load_testing.total_records, 119);
    assert.equal(data.datasets.retrieval_benchmarks.stage6.questions_count, 32);
    assert.equal(data.datasets.retrieval_benchmarks.stage8b2.configurations_count, 6);
  });

  test('16. Stage 8E Live E2E: GET /v1/experiments/load returns 7 scenarios and calibration comparison', async () => {
    const res = await fetch(`${BASE_URL}/v1/experiments/load`);
    assert.equal(res.status, 200);
    const data = await res.json();
    assert.equal(data.available, true);
    assert.equal(data.total_records, 119);
    assert.equal(data.scenarios.length, 7);

    // Verify Real vs Simulator fidelity comparison
    assert.ok(data.calibration_comparison);
    assert.equal(data.calibration_comparison.difference_pct, 0.27);
    assert.equal(data.calibration_comparison.real_groq_median_ms, 1031.0);
    assert.equal(data.calibration_comparison.simulator_median_ms, 1033.79);

    // Verify Real Baseline scenario label
    const realSc = data.scenarios.find((s: any) => s.scenario_id === 'real_baseline');
    assert.ok(realSc);
    assert.equal(realSc.source, 'real');

    // Verify Scenario C Overload
    const scC = data.scenarios.find((s: any) => s.scenario_id === 'scenario_c_overload');
    assert.ok(scC);
    assert.equal(scC.status_breakdown.timeout_504, 5);
    assert.equal(scC.status_breakdown.ok, 6);
    assert.equal(scC.status_breakdown.server_error_500, 8);
  });

  test('17. Stage 8E Live E2E: GET /v1/experiments/retrieval returns benchmark matrix and scaling frontier', async () => {
    const res = await fetch(`${BASE_URL}/v1/experiments/retrieval`);
    assert.equal(res.status, 200);
    const data = await res.json();
    assert.equal(data.available, true);
    assert.equal(data.denominators.total_questions, 32);
    assert.equal(data.denominators.answerable_questions, 26);
    assert.equal(data.denominators.unanswerable_questions, 6);

    // Verify Stage 6 vs Stage 8B.2 comparison
    assert.ok(data.stage6_vs_stage8b2_comparison.length === 4);
    const hybridComp = data.stage6_vs_stage8b2_comparison.find(
      (c: any) => c.configuration_name.includes('Hybrid (Dense + BM25)')
    );
    assert.ok(hybridComp);
    assert.equal(hybridComp.delta.recall_at_5_improvement, 3.84);

    const fullHybrid = data.stage6_vs_stage8b2_comparison.find(
      (c: any) => c.configuration_name.includes('Full Hybrid')
    );
    assert.ok(fullHybrid);
    assert.equal(fullHybrid.delta.recall_at_5_improvement, 3.84);

    // Verify Top-k scaling frontier
    assert.ok(data.top_k_scaling_stage8b2.length === 3);
    const k10 = data.top_k_scaling_stage8b2.find((k: any) => k.k === 10);
    assert.ok(k10);
    assert.equal(k10.recall, 0.8846);
    assert.equal(k10.cost_per_1000_usd, 0.5901);
  });
});
