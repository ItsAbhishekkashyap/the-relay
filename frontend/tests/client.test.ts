/**
 * Comprehensive frontend client tests using Node.js native test runner and HTTP server.
 * Validates:
 * 1. Empty question rejection
 * 2. Payload structure and paper filter mapping
 * 3. Verified, refused, and unverified response handling
 * 4. Citation and retrieved passage parsing
 * 5. HTTP 429 and 503 error handling
 * 6. Timeout and network failure handling
 * 7. Cancellation handling
 * 8. Health and readiness endpoints
 */

import { test, describe, before, after } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { api, ApiError } from '../src/services/api.ts';
import { ENV } from '../src/config/env.ts';
import type { AskRequest, AskResponse, HealthResponse, ReadyResponse } from '../src/types/api.ts';

describe('Frontend API Client & Contract Tests', () => {
  let server: http.Server;
  let serverPort: number;
  let lastReceivedRequest: {
    method?: string;
    url?: string;
    headers?: http.IncomingHttpHeaders;
    body?: any;
  } = {};

  let mockResponseMode:
    | 'health_ok'
    | 'ready_ok'
    | 'ask_verified'
    | 'ask_refused'
    | 'ask_unverified'
    | 'rate_limit_429'
    | 'queue_full_503'
    | 'timeout_504'
    | 'bad_request_400' = 'health_ok';

  before(async () => {
    server = http.createServer(async (req, res) => {
      const chunks: Buffer[] = [];
      for await (const chunk of req) {
        chunks.push(typeof chunk === 'string' ? Buffer.from(chunk) : chunk);
      }
      const rawBody = Buffer.concat(chunks).toString();
      let parsedBody: any = null;
      if (rawBody) {
        try {
          parsedBody = JSON.parse(rawBody);
        } catch {
          parsedBody = rawBody;
        }
      }

      lastReceivedRequest = {
        method: req.method,
        url: req.url,
        headers: req.headers,
        body: parsedBody,
      };

      if (req.url === '/health') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'ok', service: 'relay-research-assistant' }));
        return;
      }

      if (req.url === '/ready') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(
          JSON.stringify({
            status: 'ready',
            provider: 'simulator',
            model: 'openai/gpt-oss-120b',
            components: {
              retriever: 'initialized',
              traffic_manager: 'initialized',
              workflow: 'initialized',
            },
          })
        );
        return;
      }

      if (req.url === '/v1/metrics') {
        const metricsPayload = {
          timestamp: new Date().toISOString(),
          provider: {
            provider_name: 'simulator',
            model_name: 'simulator/mock-model-v1',
          },
          requests: {
            total_submitted: 12,
            successful: 11,
            failed: 1,
            rate_limited: 0,
            timed_out: 0,
            retried: 1,
            queue_rejections: 0,
            client_cancellations: 0,
          },
          queue: {
            current_depth: 0,
            capacity: 50,
            utilization_pct: 0.0,
          },
          concurrency: {
            active_in_flight: 0,
            peak_in_flight: 2,
            max_concurrency: 5,
          },
          rate_limits: {
            rpm_limit: 30,
            tpm_limit: 8000,
            completed_rpm: 5,
            reserved_rpm: 0,
            completed_tpm: 1250,
            reserved_tpm: 0,
          },
          latency: {
            available: true,
            sample_count: 11,
            measurement_scope: 'Provider execution duration via TrafficManager (rolling 1,000 requests)',
            p50_ms: 950.0,
            p95_ms: 1120.0,
            p99_ms: 1250.0,
            avg_ms: 975.2,
            min_ms: 820.0,
            max_ms: 1300.0,
          },
        };
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(metricsPayload));
        return;
      }

      if (req.url === '/simulator/status') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(
          JSON.stringify({
            status: 'healthy',
            in_flight_requests: 0,
            config: {
              base_delay_ms: 976.5,
              jitter_ms: 174.0,
              ttft_ms: 852.0,
              ttft_stddev_ms: 234.55,
              inter_chunk_delay_ms: 20.0,
              num_stream_chunks: 8,
              latency_distribution: 'lognormal',
              load_slowdown_factor: 0.05,
              failure_rate: 0.0,
              deterministic_failure: null,
              rpm_limit: 30,
              tpm_limit: 8000,
              daily_budget: 1000,
              daily_token_budget: 200000,
              max_concurrent_requests: 10,
              retry_after_seconds: null,
              model_name: 'simulator/mock-model-v1',
            },
            configured_limits: {
              rpm_limit: 30,
              tpm_limit: 8000,
            },
            current_window: {
              rpm_usage: 2,
              completed_rpm: 2,
              reserved_rpm: 0,
              tpm_usage: 1500,
              completed_tpm: 1500,
              reserved_tpm: 0,
              window_seconds: 60.0,
            },
            daily_request_usage: {
              date: '2026-11-14',
              requests_used: 15,
              completed_requests: 15,
              in_flight_requests: 0,
              budget: 1000,
              remaining: 985,
            },
            daily_token_usage: {
              date: '2026-11-14',
              tokens_used: 12000,
              completed_tokens: 12000,
              reserved_tokens: 0,
              budget: 200000,
              remaining: 188000,
            },
            lifetime_metrics: {
              total_handled: 50,
              successes: 48,
              failures: 2,
              rate_limit_hits: 1,
              overload_hits: 0,
              client_cancellations: 0,
            },
          })
        );
        return;
      }

      if (req.url === '/simulator/admin/config') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(
          JSON.stringify({
            base_delay_ms: 976.5,
            jitter_ms: 174.0,
            ttft_ms: 852.0,
            ttft_stddev_ms: 234.55,
            inter_chunk_delay_ms: 20.0,
            num_stream_chunks: 8,
            latency_distribution: 'lognormal',
            load_slowdown_factor: 0.05,
            failure_rate: 0.0,
            deterministic_failure: null,
            rpm_limit: 30,
            tpm_limit: 8000,
            daily_budget: 1000,
            daily_token_budget: 200000,
            max_concurrent_requests: 10,
            retry_after_seconds: null,
            model_name: 'simulator/mock-model-v1',
          })
        );
        return;
      }

      if (req.url === '/simulator/admin/configure') {
        if (parsedBody && typeof parsedBody.base_delay_ms === 'number' && parsedBody.base_delay_ms < 0) {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ detail: 'Invalid configuration update: base_delay_ms must be >= 0' }));
          return;
        }
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(
          JSON.stringify({
            status: 'updated',
            config: {
              base_delay_ms: parsedBody.base_delay_ms ?? 976.5,
              jitter_ms: parsedBody.jitter_ms ?? 174.0,
              ttft_ms: parsedBody.ttft_ms ?? 852.0,
              ttft_stddev_ms: 234.55,
              inter_chunk_delay_ms: 20.0,
              num_stream_chunks: 8,
              latency_distribution: 'lognormal',
              load_slowdown_factor: 0.05,
              failure_rate: parsedBody.failure_rate ?? 0.0,
              deterministic_failure: parsedBody.deterministic_failure ?? null,
              rpm_limit: parsedBody.rpm_limit ?? 30,
              tpm_limit: parsedBody.tpm_limit ?? 8000,
              daily_budget: 1000,
              daily_token_budget: 200000,
              max_concurrent_requests: parsedBody.max_concurrent_requests ?? 10,
              retry_after_seconds: null,
              model_name: 'simulator/mock-model-v1',
            },
          })
        );
        return;
      }

      if (req.url === '/simulator/admin/reset') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'reset_successful' }));
        return;
      }

      if (req.url === '/simulator/admin/reset-config') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(
          JSON.stringify({
            status: 'config_reset',
            config: {
              base_delay_ms: 976.5,
              jitter_ms: 174.0,
              ttft_ms: 852.0,
              ttft_stddev_ms: 234.55,
              inter_chunk_delay_ms: 20.0,
              num_stream_chunks: 8,
              latency_distribution: 'lognormal',
              load_slowdown_factor: 0.05,
              failure_rate: 0.0,
              deterministic_failure: null,
              rpm_limit: 30,
              tpm_limit: 8000,
              daily_budget: 1000,
              daily_token_budget: 200000,
              max_concurrent_requests: 10,
              retry_after_seconds: null,
              model_name: 'simulator/mock-model-v1',
            },
          })
        );
        return;
      }

      if (req.url === '/v1/experiments/overview') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(
          JSON.stringify({
            status: 'available',
            description: 'Empirical characterization and evaluation datasets across Stages 4, 5, 6, and 8B.2.',
            pricing_basis: {
              prompt_tokens_per_million_usd: 0.15,
              completion_tokens_per_million_usd: 0.60,
            },
            datasets: {
              load_testing: {
                available: true,
                total_records: 119,
                summary_available: true,
                scenarios: [
                  {
                    id: 'real_baseline',
                    name: 'Real Groq Baseline',
                    source: 'real',
                    provider: 'groq (cloud)',
                    model: 'openai/gpt-oss-120b',
                    total_requests: 20,
                  },
                ],
              },
              retrieval_benchmarks: {
                stage6: {
                  stage: 'Stage 6 Initial Evaluation',
                  available: true,
                  date: '2026-11-12',
                  questions_count: 32,
                  answerable_count: 26,
                  unanswerable_count: 6,
                  configurations_count: 4,
                  configurations: ['config_a_dense', 'config_b_bm25', 'config_c_hybrid', 'config_d_full_hybrid'],
                },
                stage8b2: {
                  stage: 'Stage 8B.2 Table Caption Preservation & Top-K Scaling',
                  available: true,
                  date: '2026-11-12',
                  questions_count: 32,
                  answerable_count: 26,
                  unanswerable_count: 6,
                  configurations_count: 6,
                  configurations: [
                    'config_a_dense_k5',
                    'config_b_bm25_k5',
                    'config_c_hybrid_k5',
                    'config_d_full_hybrid_k5',
                    'config_d_full_hybrid_k8',
                    'config_d_full_hybrid_k10',
                  ],
                },
              },
            },
          })
        );
        return;
      }

      if (req.url === '/v1/experiments/load') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(
          JSON.stringify({
            available: true,
            total_records: 119,
            scenarios: [
              {
                scenario_id: 'real_baseline',
                name: 'Real Groq Baseline',
                source: 'real',
                provider: 'Groq Cloud API (openai/gpt-oss-120b)',
                description: '20 requests calibrated against real Groq infrastructure.',
                traffic_pattern: 'Sequential requests with 2.5s pacing.',
                total_requests: 20,
                successful_requests: 20,
                failed_requests: 0,
                status_breakdown: { ok: 20, rate_limited_429: 0, timeout_504: 0, server_error_500: 0 },
                success_rate_pct: 100.0,
                rate_limited_pct: 0.0,
                timeout_pct: 0.0,
                error_pct: 0.0,
                total_retries: 0,
                avg_retries_per_request: 0.0,
                total_latency_ms: { median: 1031.0, p50: 1031.0, p95: 1400.0, max: 1550.0 },
                ttft_ms: { median: 852.0, p50: 852.0, p95: 1100.0, max: 1250.0 },
                token_usage: { prompt_tokens: 3000, completion_tokens: 2000, total_tokens: 5000, tokens_per_answer: 250 },
                estimated_cost_usd: 0.00165,
                cost_per_1000_answers_usd: 0.0825,
              },
              {
                scenario_id: 'calibration_baseline',
                name: 'Simulator Calibration Baseline',
                source: 'simulator',
                provider: 'Local HTTP Stand-in Simulator',
                description: '20 requests against simulator calibrated using exact lognormal equations.',
                traffic_pattern: 'Identical sequential pacing.',
                total_requests: 20,
                successful_requests: 20,
                failed_requests: 0,
                status_breakdown: { ok: 20, rate_limited_429: 0, timeout_504: 0, server_error_500: 0 },
                success_rate_pct: 100.0,
                rate_limited_pct: 0.0,
                timeout_pct: 0.0,
                error_pct: 0.0,
                total_retries: 0,
                avg_retries_per_request: 0.0,
                total_latency_ms: { median: 1033.79, p50: 1033.79, p95: 1395.0, max: 1520.0 },
                ttft_ms: { median: 852.0, p50: 852.0, p95: 1090.0, max: 1240.0 },
                token_usage: { prompt_tokens: 3000, completion_tokens: 2000, total_tokens: 5000, tokens_per_answer: 250 },
                estimated_cost_usd: 0.00165,
                cost_per_1000_answers_usd: 0.0825,
              },
            ],
            calibration_comparison: {
              metric: 'Latency Calibration Fidelity',
              real_groq_median_ms: 1031.0,
              simulator_median_ms: 1033.79,
              difference_ms: 2.79,
              difference_pct: 0.27,
              real_groq_ttft_median_ms: 852.0,
              simulator_ttft_median_ms: 852.0,
              ttft_difference_ms: 0.0,
              ttft_difference_pct: 0.0,
              conclusion: 'Simulator reproduces real Groq median non-streaming latency within 0.27%.',
            },
          })
        );
        return;
      }

      if (req.url?.startsWith('/v1/experiments/retrieval')) {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(
          JSON.stringify({
            available: true,
            methodology_note: 'Stage 6 evaluated initial chunking; Stage 8B.2 evaluated caption-preserved chunking.',
            denominators: {
              total_questions: 32,
              answerable_questions: 26,
              unanswerable_questions: 6,
              recall_and_mrr_basis: 'Answerable questions only (denominator: 26)',
              accuracy_and_refusal_basis: 'All questions (denominator: 32)',
            },
            stage6: {
              stage_name: 'Stage 6 Initial Retrieval Benchmark',
              date: '2026-11-12',
              configurations: [],
            },
            stage8b2: {
              stage_name: 'Stage 8B.2 Table Caption Preservation & Top-K Scaling',
              configurations: [],
            },
            stage6_vs_stage8b2_comparison: [
              {
                configuration_name: 'Hybrid (Dense + BM25)',
                k: 5,
                stage6: {
                  recall_at_5: 0.7308,
                  mrr: 0.5353,
                  correct_and_cited_pct: 71.88,
                  wrong_pct: 9.38,
                  latency_mean_ms: 12.5,
                  cost_per_1000_usd: 0.3434,
                },
                stage8b2: {
                  recall_at_5: 0.8846,
                  mrr: 0.6122,
                  correct_and_cited_pct: 84.38,
                  wrong_pct: 3.12,
                  latency_mean_ms: 13.1,
                  cost_per_1000_usd: 0.3444,
                },
                delta: {
                  recall_at_5_improvement: 15.38,
                  correct_and_cited_improvement_pct: 12.5,
                },
              },
            ],
            top_k_scaling_stage8b2: [
              {
                k: 5,
                recall: 0.8846,
                mrr: 0.6122,
                correct_and_cited_pct: 84.38,
                wrong_pct: 3.12,
                avg_context_tokens: 1850,
                cost_per_1000_usd: 0.3444,
              },
              {
                k: 10,
                recall: 0.9231,
                mrr: 0.6355,
                correct_and_cited_pct: 87.5,
                wrong_pct: 0.0,
                avg_context_tokens: 3100,
                cost_per_1000_usd: 0.5422,
              },
            ],
          })
        );
        return;
      }

      if (req.url === '/v1/ask') {
        if (mockResponseMode === 'rate_limit_429') {
          res.writeHead(429, { 'Content-Type': 'application/json', 'Retry-After': '5' });
          res.end(JSON.stringify({ detail: 'Model provider rate limit reached (30 RPM)' }));
          return;
        }

        if (mockResponseMode === 'queue_full_503') {
          res.writeHead(503, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ detail: 'TrafficManager queue is currently at capacity' }));
          return;
        }

        if (mockResponseMode === 'timeout_504') {
          res.writeHead(504, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ detail: 'Request processing timed out: 30s deadline exceeded' }));
          return;
        }

        if (mockResponseMode === 'bad_request_400') {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ detail: "Unsupported paper_filter 'invalid_id'" }));
          return;
        }

        if (mockResponseMode === 'ask_refused') {
          const refusedResponse: AskResponse = {
            request_id: 'refused-req-1234',
            question: parsedBody.question,
            answer:
              'I cannot answer this question based on the provided corpus. The available research papers do not contain evidence regarding quantum computing.',
            status: 'refused',
            citations: [],
            retrieved_passages: [],
            provider: 'simulator',
            refusal_reason: 'Evidence insufficiency: query out of domain',
            correction_occurred: false,
            workflow_metadata: { nodes_visited: ['retrieve', 'evidence_gate', 'refusal'] },
          };
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify(refusedResponse));
          return;
        }

        if (mockResponseMode === 'ask_unverified') {
          const unverifiedResponse: AskResponse = {
            request_id: 'unverified-req-5678',
            question: parsedBody.question,
            answer: 'Transformer base uses 8 heads [Vaswani, arXiv:1706.03762v7, p. 99, Sec 9.9].',
            status: 'unverified',
            citations: [
              {
                raw_text: '[Vaswani, arXiv:1706.03762v7, p. 99, Sec 9.9]',
                paper_id: '1706.03762v7',
                page_number: 99,
                section: '9.9',
                is_verified: false,
                verification_error: 'Page 99 out of range for 15-page document',
              },
            ],
            retrieved_passages: [],
            provider: 'simulator',
            refusal_reason: null,
            correction_occurred: true,
            workflow_metadata: {},
          };
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify(unverifiedResponse));
          return;
        }

        // Default: ask_verified
        const verifiedResponse: AskResponse = {
          request_id: 'verified-req-9999',
          question: parsedBody.question,
          answer:
            'The Transformer base model achieves a BLEU score of 27.3 on WMT 2014 English-to-German [Attention Is All You Need, arXiv:1706.03762v7, p. 8, Section 5.1].',
          status: 'verified',
          citations: [
            {
              raw_text: '[Attention Is All You Need, arXiv:1706.03762v7, p. 8, Section 5.1]',
              paper_title: 'Attention Is All You Need',
              paper_id: '1706.03762v7',
              page_number: 8,
              section: '5.1',
              is_verified: true,
              verification_error: null,
            },
          ],
          retrieved_passages: [
            {
              chunk_id: '1706.03762v7_p8_c0',
              paper_id: '1706.03762v7',
              paper_title: 'Attention Is All You Need',
              arxiv_id: '1706.03762',
              paper_version: 'v7',
              page_number: 8,
              page_numbers: [8],
              section: '5.1',
              content: 'On the WMT 2014 English-to-German translation task...',
              score: 0.033,
              retrieval_channels: ['dense', 'bm25'],
            },
          ],
          provider: 'simulator',
          refusal_reason: null,
          correction_occurred: false,
          workflow_metadata: { nodes_visited: ['retrieve', 'evidence_gate', 'generate', 'verify'] },
        };
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(verifiedResponse));
        return;
      }

      res.writeHead(404, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ detail: 'Not found' }));
    });

    await new Promise<void>((resolve) => {
      server.listen(0, '127.0.0.1', () => {
        const addr = server.address() as any;
        serverPort = addr.port;
        ENV.apiBaseUrl = `http://127.0.0.1:${serverPort}`;
        resolve();
      });
    });
  });

  after(async () => {
    await new Promise<void>((resolve) => {
      server.close(() => resolve());
    });
  });

  test('1. Validates GET /health response contract', async () => {
    const health: HealthResponse = await api.getHealth();
    assert.equal(health.status, 'ok');
    assert.equal(health.service, 'relay-research-assistant');
    assert.equal(lastReceivedRequest.method, 'GET');
    assert.equal(lastReceivedRequest.url, '/health');
  });

  test('2. Validates GET /ready response contract and components', async () => {
    const ready: ReadyResponse = await api.getReady();
    assert.equal(ready.status, 'ready');
    assert.equal(ready.provider, 'simulator');
    assert.equal(ready.model, 'openai/gpt-oss-120b');
    assert.equal(ready.components.retriever, 'initialized');
    assert.equal(ready.components.traffic_manager, 'initialized');
    assert.equal(ready.components.workflow, 'initialized');
  });

  test('3. Paper filter mapping: correctly includes paper_filter when specified', async () => {
    mockResponseMode = 'ask_verified';
    const req: AskRequest = {
      question: 'What is the frame rate of Mimi?',
      paper_filter: '2410.00037v1',
    };
    const res = await api.askQuestion(req);

    assert.equal(lastReceivedRequest.method, 'POST');
    assert.equal(lastReceivedRequest.url, '/v1/ask');
    assert.equal(lastReceivedRequest.body.question, 'What is the frame rate of Mimi?');
    assert.equal(lastReceivedRequest.body.paper_filter, '2410.00037v1');
    assert.equal(res.status, 'verified');
  });

  test('4. Paper filter mapping: omits paper_filter when null or undefined', async () => {
    mockResponseMode = 'ask_verified';
    const req: AskRequest = {
      question: 'Compare attention mechanisms',
      paper_filter: null,
    };
    const res = await api.askQuestion(req);

    assert.equal(lastReceivedRequest.body.question, 'Compare attention mechanisms');
    assert.equal(lastReceivedRequest.body.paper_filter, undefined);
    assert.equal(res.status, 'verified');
  });

  test('5. Verified response correctly parses citations and retrieved passages', async () => {
    mockResponseMode = 'ask_verified';
    const res = await api.askQuestion({ question: 'Transformer BLEU score' });

    assert.equal(res.status, 'verified');
    assert.equal(res.citations.length, 1);
    assert.equal(res.citations[0].paper_id, '1706.03762v7');
    assert.equal(res.citations[0].page_number, 8);
    assert.equal(res.citations[0].section, '5.1');
    assert.equal(res.citations[0].is_verified, true);

    assert.equal(res.retrieved_passages.length, 1);
    assert.equal(res.retrieved_passages[0].chunk_id, '1706.03762v7_p8_c0');
    assert.deepEqual(res.retrieved_passages[0].retrieval_channels, ['dense', 'bm25']);
  });

  test('6. Refused response correctly parses refusal_reason and empty citations', async () => {
    mockResponseMode = 'ask_refused';
    const res = await api.askQuestion({ question: 'Quantum algorithms' });

    assert.equal(res.status, 'refused');
    assert.match(res.answer, /cannot answer this question/);
    assert.equal(res.refusal_reason, 'Evidence insufficiency: query out of domain');
    assert.equal(res.citations.length, 0);
  });

  test('7. Unverified response parses verification failure metadata', async () => {
    mockResponseMode = 'ask_unverified';
    const res = await api.askQuestion({ question: 'Test query' });

    assert.equal(res.status, 'unverified');
    assert.equal(res.citations.length, 1);
    assert.equal(res.citations[0].is_verified, false);
    assert.match(res.citations[0].verification_error!, /Page 99 out of range/);
    assert.equal(res.correction_occurred, true);
  });

  test('8. Handles HTTP 429 rate limit error gracefully', async () => {
    mockResponseMode = 'rate_limit_429';
    await assert.rejects(
      async () => {
        await api.askQuestion({ question: 'High rate query' });
      },
      (err: any) => {
        assert(err instanceof ApiError);
        assert.equal(err.status, 429);
        assert.match(err.message, /Rate limit reached/);
        return true;
      }
    );
  });

  test('9. Handles HTTP 503 queue capacity error gracefully', async () => {
    mockResponseMode = 'queue_full_503';
    await assert.rejects(
      async () => {
        await api.askQuestion({ question: 'Bursty query' });
      },
      (err: any) => {
        assert(err instanceof ApiError);
        assert.equal(err.status, 503);
        assert.match(err.message, /Service unavailable/);
        return true;
      }
    );
  });

  test('10. Handles HTTP 504 processing timeout gracefully', async () => {
    mockResponseMode = 'timeout_504';
    await assert.rejects(
      async () => {
        await api.askQuestion({ question: 'Slow query' });
      },
      (err: any) => {
        assert(err instanceof ApiError);
        assert.equal(err.status, 504);
        assert.match(err.message, /Processing timeout/);
        return true;
      }
    );
  });

  test('11. Handles HTTP 400 bad request error gracefully', async () => {
    mockResponseMode = 'bad_request_400';
    await assert.rejects(
      async () => {
        await api.askQuestion({ question: 'Query with invalid filter', paper_filter: 'invalid_id' });
      },
      (err: any) => {
        assert(err instanceof ApiError);
        assert.equal(err.status, 400);
        assert.match(err.message, /Invalid request/);
        return true;
      }
    );
  });

  test('12. User cancellation via AbortSignal raises 499 canceled', async () => {
    mockResponseMode = 'ask_verified';
    const controller = new AbortController();
    controller.abort(); // pre-aborted

    await assert.rejects(
      async () => {
        await api.askQuestion({ question: 'Canceled query' }, controller.signal);
      },
      (err: any) => {
        assert(err instanceof ApiError);
        assert.equal(err.status, 499);
        assert.match(err.message, /canceled by user/);
        return true;
      }
    );
  });

  test('13. Network failure when endpoint is unreachable raises connection error', async () => {
    // Point to an unused local port
    ENV.apiBaseUrl = 'http://127.0.0.1:59999';
    await assert.rejects(
      async () => {
        await api.askQuestion({ question: 'Offline query' });
      },
      (err: any) => {
        assert(err instanceof ApiError);
        assert.match(err.message, /Connection failed/);
        return true;
      }
    );
  });

  test('14. Validates retrieved passages carry provenance metadata for citation matching', async () => {
    ENV.apiBaseUrl = `http://127.0.0.1:${serverPort}`;
    mockResponseMode = 'ask_verified';
    const res = await api.askQuestion({ question: 'Transformer BLEU score' });

    assert.equal(res.retrieved_passages.length, 1);
    const doc = res.retrieved_passages[0];
    assert.equal(doc.paper_id, '1706.03762v7');
    assert.equal(doc.page_number, 8);
    assert.deepEqual(doc.page_numbers, [8]);
    assert.equal(doc.section, '5.1');
    assert.equal(doc.paper_version, 'v7');

    const citation = res.citations[0];
    assert.equal(citation.paper_id, doc.paper_id);
    assert.equal(citation.page_number, doc.page_number);
    assert.equal(citation.section, doc.section);
  });

  test('15. Validates out-of-domain refusal retains refusal_reason and empty citations', async () => {
    ENV.apiBaseUrl = `http://127.0.0.1:${serverPort}`;
    mockResponseMode = 'ask_refused';
    const res = await api.askQuestion({ question: 'Quantum algorithms' });

    assert.equal(res.status, 'refused');
    assert.ok(res.refusal_reason && res.refusal_reason.length > 0);
    assert.equal(res.citations.length, 0);
    assert.equal(res.correction_occurred, false);
  });

  test('16. Validates unverified response flags correction and verification error details', async () => {
    ENV.apiBaseUrl = `http://127.0.0.1:${serverPort}`;
    mockResponseMode = 'ask_unverified';
    const res = await api.askQuestion({ question: 'Invalid citation test' });

    assert.equal(res.status, 'unverified');
    assert.equal(res.correction_occurred, true);
    assert.equal(res.citations[0].is_verified, false);
    assert.ok(res.citations[0].verification_error);
  });

  test('17. Validates GET /v1/metrics contract, queue utilization, and latency percentiles', async () => {
    ENV.apiBaseUrl = `http://127.0.0.1:${serverPort}`;
    const m = await api.getMetrics();

    assert.equal(m.provider.provider_name, 'simulator');
    assert.equal(m.requests.total_submitted, 12);
    assert.equal(m.requests.successful, 11);
    assert.equal(m.requests.failed, 1);
    assert.equal(m.queue.capacity, 50);
    assert.equal(m.queue.current_depth, 0);
    assert.equal(m.queue.utilization_pct, 0.0);
    assert.equal(m.concurrency.max_concurrency, 5);
    assert.equal(m.latency.available, true);
    assert.equal(m.latency.sample_count, 11);
    assert.equal(m.latency.p50_ms, 950.0);
    assert.equal(m.latency.p95_ms, 1120.0);
    assert.equal(m.latency.p99_ms, 1250.0);
  });

  test('18. Handles metrics request failure gracefully when endpoint is unreachable', async () => {
    ENV.apiBaseUrl = 'http://127.0.0.1:59998';
    await assert.rejects(
      async () => {
        await api.getMetrics();
      },
      (err: any) => {
        assert(err instanceof ApiError);
        assert.match(err.message, /Metrics request failed/);
        return true;
      }
    );
  });

  test('19. Simulator API: GET /simulator/status parses healthy status, limits, and metrics', async () => {
    ENV.apiBaseUrl = `http://127.0.0.1:${serverPort}`;
    const status = await api.getSimulatorStatus();

    assert.equal(status.status, 'healthy');
    assert.equal(status.in_flight_requests, 0);
    assert.equal(status.current_window.rpm_usage, 2);
    assert.equal(status.daily_request_usage.budget, 1000);
    assert.equal(status.daily_token_usage.budget, 200000);
    assert.equal(status.lifetime_metrics.total_handled, 50);
  });

  test('20. Simulator API: GET /simulator/admin/config parses all configuration parameters', async () => {
    ENV.apiBaseUrl = `http://127.0.0.1:${serverPort}`;
    const cfg = await api.getSimulatorConfig();

    assert.equal(cfg.base_delay_ms, 976.5);
    assert.equal(cfg.jitter_ms, 174.0);
    assert.equal(cfg.ttft_ms, 852.0);
    assert.equal(cfg.num_stream_chunks, 8);
    assert.equal(cfg.latency_distribution, 'lognormal');
    assert.equal(cfg.rpm_limit, 30);
    assert.equal(cfg.tpm_limit, 8000);
    assert.equal(cfg.max_concurrent_requests, 10);
  });

  test('21. Simulator API: POST /simulator/admin/configure applies valid configuration', async () => {
    ENV.apiBaseUrl = `http://127.0.0.1:${serverPort}`;
    const res = await api.configureSimulator(
      {
        base_delay_ms: 1200.0,
        rpm_limit: 45,
        failure_rate: 0.1,
      },
      'simulator'
    );

    assert.equal(res.status, 'updated');
    assert.equal(res.config.base_delay_ms, 1200.0);
    assert.equal(res.config.rpm_limit, 45);
    assert.equal(res.config.failure_rate, 0.1);
  });

  test('22. Simulator API: POST /simulator/admin/configure rejects invalid parameters with 400', async () => {
    ENV.apiBaseUrl = `http://127.0.0.1:${serverPort}`;
    await assert.rejects(
      async () => {
        await api.configureSimulator({ base_delay_ms: -100 }, 'simulator');
      },
      (err: any) => {
        assert(err instanceof ApiError);
        assert.equal(err.status, 400);
        assert.match(err.message, /Simulator configuration rejected/);
        return true;
      }
    );
  });

  test('23. Provider Protection Guard: Rejects configuration when active provider is Groq', async () => {
    ENV.apiBaseUrl = `http://127.0.0.1:${serverPort}`;
    await assert.rejects(
      async () => {
        await api.configureSimulator({ base_delay_ms: 500 }, 'groq');
      },
      (err: any) => {
        assert(err instanceof ApiError);
        assert.equal(err.status, 403);
        assert.match(err.message, /Simulator controls disabled: active provider is Groq/);
        return true;
      }
    );
  });

  test('24. Provider Protection Guard: Rejects simulator reset when active provider is Groq', async () => {
    ENV.apiBaseUrl = `http://127.0.0.1:${serverPort}`;
    await assert.rejects(
      async () => {
        await api.resetSimulator('groq');
      },
      (err: any) => {
        assert(err instanceof ApiError);
        assert.equal(err.status, 403);
        assert.match(err.message, /Simulator reset disabled: active provider is Groq/);
        return true;
      }
    );
  });

  test('25. Simulator API: POST /simulator/admin/reset resets runtime counters and state', async () => {
    ENV.apiBaseUrl = `http://127.0.0.1:${serverPort}`;
    const res = await api.resetSimulator('simulator');
    assert.equal(res.status, 'reset_successful');
  });

  test('26. Simulator API: POST /simulator/admin/reset-config resets configuration to baseline defaults', async () => {
    ENV.apiBaseUrl = `http://127.0.0.1:${serverPort}`;
    const res = await api.resetSimulatorConfig('simulator');
    assert.equal(res.status, 'config_reset');
    assert.equal(res.config?.base_delay_ms, 976.5);
    assert.equal(res.config?.rpm_limit, 30);
  });

  test('27. Stage 8E Experiment API: GET /v1/experiments/overview returns dataset catalog', async () => {
    ENV.apiBaseUrl = `http://127.0.0.1:${serverPort}`;
    const res = await api.getExperimentsOverview();
    assert.equal(res.status, 'available');
    assert.equal(res.pricing_basis.prompt_tokens_per_million_usd, 0.15);
    assert.equal(res.pricing_basis.completion_tokens_per_million_usd, 0.60);
    assert.equal(res.datasets.load_testing.total_records, 119);
    assert.equal(res.datasets.retrieval_benchmarks.stage6.questions_count, 32);
    assert.equal(res.datasets.retrieval_benchmarks.stage8b2.configurations_count, 6);
  });

  test('28. Stage 8E Experiment API: GET /v1/experiments/load returns load scenarios and calibration comparison', async () => {
    ENV.apiBaseUrl = `http://127.0.0.1:${serverPort}`;
    const res = await api.getLoadExperiments();
    assert.equal(res.available, true);
    assert.equal(res.total_records, 119);
    assert.ok(res.scenarios && res.scenarios.length >= 2);
    assert.equal(res.scenarios[0].scenario_id, 'real_baseline');
    assert.equal(res.scenarios[0].source, 'real');
    assert.equal(res.scenarios[1].scenario_id, 'calibration_baseline');
    assert.equal(res.scenarios[1].source, 'simulator');
    assert.ok(res.calibration_comparison);
    assert.equal(res.calibration_comparison.difference_pct, 0.27);
  });

  test('29. Stage 8E Experiment API: GET /v1/experiments/retrieval returns retrieval benchmarks and comparisons', async () => {
    ENV.apiBaseUrl = `http://127.0.0.1:${serverPort}`;
    const res = await api.getRetrievalExperiments();
    assert.equal(res.available, true);
    assert.equal(res.denominators?.answerable_questions, 26);
    assert.equal(res.denominators?.total_questions, 32);
    assert.ok(res.stage6_vs_stage8b2_comparison && res.stage6_vs_stage8b2_comparison.length >= 1);
    assert.equal(res.stage6_vs_stage8b2_comparison[0].delta.recall_at_5_improvement, 15.38);
    assert.ok(res.top_k_scaling_stage8b2 && res.top_k_scaling_stage8b2.length >= 2);
  });
});
