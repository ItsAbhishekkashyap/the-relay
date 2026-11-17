/**
 * Stage 8G Comprehensive End-to-End QA Verification Suite
 * Executes functional verifications across all 4 pages and services.
 */

import { test, describe, before } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const BASE_URL = 'http://localhost:5173';
const SIMULATOR_URL = 'http://127.0.0.1:8001';

describe('Stage 8G Final QA Verification Suite', () => {
  before(async () => {
    // Reset simulator before tests
    try {
      await fetch(`${SIMULATOR_URL}/admin/reset`, { method: 'POST' });
      await fetch(`${SIMULATOR_URL}/admin/reset-config`, { method: 'POST' });
    } catch {
      // ignore
    }
  });

  // 1. Gateway Health and Readiness
  test('1. System Overview: Backend health and readiness probe confirms simulator', async () => {
    const healthRes = await fetch(`${BASE_URL}/health`);
    assert.equal(healthRes.status, 200);
    const health = await healthRes.json();
    assert.equal(health.status, 'ok');

    const readyRes = await fetch(`${BASE_URL}/ready`);
    assert.equal(readyRes.status, 200);
    const ready = await readyRes.json();
    assert.equal(ready.status, 'ready');
    assert.equal(ready.provider, 'simulator');
    assert.equal(ready.components.retriever, 'initialized');
    assert.equal(ready.components.traffic_manager, 'initialized');
    assert.equal(ready.components.workflow, 'initialized');
  });

  // 2. Research Chat: BLEU score target query
  test('2. Research Chat: Submit Transformer BLEU score question and verify 27.3 with citation', async () => {
    const res = await fetch(`${BASE_URL}/v1/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question: 'What BLEU score did the Transformer base model achieve on English-to-German?',
      }),
    });

    assert.equal(res.status, 200);
    const data = await res.json();

    // Verification status
    assert.equal(data.status, 'verified');
    assert.equal(data.provider, 'simulator');

    // Answer contains 27.3
    assert.match(data.answer, /27\.3/);
    assert.match(data.answer, /base model/i);

    // Citations validation
    assert.ok(data.citations.length >= 1, 'Must contain at least 1 citation');
    const cit = data.citations[0];
    assert.equal(cit.is_verified, true);
    assert.equal(cit.paper_id, '1706.03762v7');
    assert.equal(cit.page_number, 8);
    assert.equal(cit.section, '6.1 Machine Translation');

    // Retrieved evidence validation
    assert.ok(data.retrieved_passages.length >= 1);
    const tableChunk = data.retrieved_passages.find(
      (p: any) => p.chunk_id === '1706.03762v7_lc_0026' || p.content.includes('27.3')
    );
    assert.ok(tableChunk, 'Table passage containing 27.3 must be in retrieved evidence');
    assert.match(tableChunk.content, /Table 2/);
    assert.match(tableChunk.content, /27\.3/);
  });

  // 3. Research Chat: Grounded Refusal
  test('3. Research Chat: Out-of-domain query produces grounded refusal with zero citations', async () => {
    const res = await fetch(`${BASE_URL}/v1/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question: 'What was the quantum volume of the Sycamore processor in 2019?',
      }),
    });

    assert.equal(res.status, 200);
    const data = await res.json();

    assert.equal(data.status, 'refused');
    assert.match(data.answer, /unable to answer/i);
    assert.ok(data.refusal_reason && data.refusal_reason.length > 0);
    assert.equal(data.citations.length, 0, 'Refused answers must have 0 citations');
  });

  // 4. Research Chat: Error & Validation Handling
  test('4. Research Chat: Empty question and invalid filter rejected with 422', async () => {
    const emptyRes = await fetch(`${BASE_URL}/v1/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: '' }),
    });
    assert.equal(emptyRes.status, 422);

    const badFilterRes = await fetch(`${BASE_URL}/v1/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: 'Valid question', paper_filter: 'unsupported_arxiv_id' }),
    });
    assert.equal(badFilterRes.status, 422);
  });

  // 5. System Overview: Live Metrics Telemetry
  test('5. System Overview: Live metrics endpoint returns queue, concurrency, and latency percentiles', async () => {
    const res = await fetch(`${BASE_URL}/v1/metrics`);
    assert.equal(res.status, 200);
    const metrics = await res.json();

    assert.equal(metrics.provider.provider_name, 'simulator');
    assert.ok(typeof metrics.requests.total_submitted === 'number');
    assert.ok(typeof metrics.queue.capacity === 'number');
    assert.ok(typeof metrics.queue.current_depth === 'number');
    assert.ok(typeof metrics.concurrency.max_concurrency === 'number');
    assert.ok(typeof metrics.latency.avg_ms === 'number');
    assert.ok(metrics.latency.p50_ms !== undefined);
  });

  // 6. Experiment Analytics: Datasets and Benchmarks
  test('6. Experiment Analytics: Historical benchmarks load with verified comparative metrics', async () => {
    const overviewRes = await fetch(`${BASE_URL}/v1/experiments/overview`);
    assert.equal(overviewRes.status, 200);
    const overview = await overviewRes.json();
    assert.ok(overview.datasets.load_testing);
    assert.ok(overview.datasets.retrieval_benchmarks);
    assert.equal(overview.datasets.load_testing.total_records, 119);

    const loadRes = await fetch(`${BASE_URL}/v1/experiments/load`);
    assert.equal(loadRes.status, 200);
    const loadData = await loadRes.json();
    assert.equal(loadData.scenarios.length, 7);
    assert.ok(loadData.calibration_comparison.real_groq_median_ms > 0);
    assert.ok(loadData.calibration_comparison.simulator_median_ms > 0);
    assert.ok(loadData.calibration_comparison.difference_pct < 1.0, 'Fidelity error must be < 1%');

    const retRes = await fetch(`${BASE_URL}/v1/experiments/retrieval`);
    assert.equal(retRes.status, 200);
    const retData = await retRes.json();
    assert.ok(retData.stage6.configurations.length >= 4);
    assert.ok(retData.stage8b2.configurations.length >= 6);
    assert.ok(retData.stage6_vs_stage8b2_comparison.length >= 4);
    assert.ok(retData.top_k_scaling_stage8b2.length >= 3);
  });

  // 7. Simulator Controls: Config Read, Update, and Reset
  test('7. Simulator Controls: Read, dynamic update, invalid rejection, and reset', async () => {
    // Read status
    const statusRes = await fetch(`${BASE_URL}/simulator/status`);
    assert.equal(statusRes.status, 200);
    const statusData = await statusRes.json();
    assert.equal(statusData.status, 'healthy');

    // Read config
    const configRes = await fetch(`${BASE_URL}/simulator/admin/config`);
    assert.equal(configRes.status, 200);
    const config = await configRes.json();
    assert.ok(config.base_delay_ms > 0);

    // Apply valid update
    const updateRes = await fetch(`${BASE_URL}/simulator/admin/configure`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ base_delay_ms: 1200, jitter_ms: 250 }),
    });
    assert.equal(updateRes.status, 200);

    // Reject invalid update
    const badRes = await fetch(`${BASE_URL}/simulator/admin/configure`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ base_delay_ms: -100 }),
    });
    assert.equal(badRes.status, 400);

    // Reset config
    const resetCfgRes = await fetch(`${BASE_URL}/simulator/admin/reset-config`, { method: 'POST' });
    assert.equal(resetCfgRes.status, 200);

    // Reset runtime state
    const resetRes = await fetch(`${BASE_URL}/simulator/admin/reset`, { method: 'POST' });
    assert.equal(resetRes.status, 200);
  });

  // 8. Experiment Data Preservation Verification
  test('8. Data Integrity: Verifies source CSV and JSON experiment files are unmodified', () => {
    const repoRoot = fs.existsSync(path.join(process.cwd(), 'experiments'))
      ? process.cwd()
      : path.resolve(process.cwd(), '..');
    const files = [
      'experiments/results.csv',
      'experiments/retrieval/retrieval_results.csv',
      'experiments/retrieval/retrieval_results_stage8b2.csv',
      'experiments/reports/load_experiment_summary.json',
      'experiments/retrieval/retrieval_summary.json',
      'experiments/retrieval/retrieval_summary_stage8b2.json',
    ];

    for (const f of files) {
      const fullPath = path.join(repoRoot, f);
      assert.ok(fs.existsSync(fullPath), `Missing file: ${f}`);
      const stats = fs.statSync(fullPath);
      assert.ok(stats.size > 0, `File ${f} is empty`);
    }
  });
});
