import React, { useState, useEffect, useCallback } from 'react';
import {
  TrendingUp,
  BarChart3,
  Database,
  RefreshCw,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Zap,
  Info,
  DollarSign,
  Filter,
} from 'lucide-react';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { api, ApiError } from '../services/api';
import type {
  ExperimentsOverviewResponse,
  LoadExperimentsResponse,
  RetrievalExperimentsResponse,
  LoadScenarioStats,
} from '../types/api';

type TabType = 'traffic' | 'retrieval' | 'catalog';
type SourceFilter = 'all' | 'real' | 'simulator';
type RetrievalView = 'comparison' | 'stage8b2' | 'stage6' | 'top_k';

export const ExperimentsPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>('traffic');
  const [overview, setOverview] = useState<ExperimentsOverviewResponse | null>(null);
  const [loadData, setLoadData] = useState<LoadExperimentsResponse | null>(null);
  const [retrievalData, setRetrievalData] = useState<RetrievalExperimentsResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [lastFetched, setLastFetched] = useState<Date | null>(null);

  // Traffic filters
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>('all');
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>('all');

  // Retrieval filters
  const [retrievalView, setRetrievalView] = useState<RetrievalView>('comparison');
  const [kFilter, setKFilter] = useState<'all' | '5' | '8' | '10'>('all');

  const fetchExperimentData = useCallback(async (isManualRefresh: boolean = false) => {
    if (isManualRefresh) {
      setIsRefreshing(true);
    }
    setError(null);

    try {
      const [overviewRes, loadRes, retrievalRes] = await Promise.all([
        api.getExperimentsOverview(),
        api.getLoadExperiments(),
        api.getRetrievalExperiments(),
      ]);

      setOverview(overviewRes);
      setLoadData(loadRes);
      setRetrievalData(retrievalRes);
      setLastFetched(new Date());
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError(err instanceof Error ? err.message : 'Failed to fetch experiment data');
      }
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    let active = true;
    const run = async () => {
      if (active) {
        await fetchExperimentData();
      }
    };
    void run();
    return () => {
      active = false;
    };
  }, [fetchExperimentData]);

  // Filter load scenarios
  const filteredScenarios: LoadScenarioStats[] = (loadData?.scenarios || []).filter((sc) => {
    if (sourceFilter !== 'all' && sc.source !== sourceFilter) return false;
    if (selectedScenarioId !== 'all' && sc.scenario_id !== selectedScenarioId) return false;
    return true;
  });

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-12">
      {/* Header Banner */}
      <div className="p-5 rounded-xl bg-white border border-[#E6E9EF] flex flex-col md:flex-row items-start md:items-center justify-between gap-4 shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-indigo-600" />
              <span>Experiment Analytics & Empirical Frontiers</span>
            </h2>
            <Badge variant="blue" size="sm">
              Empirical Measurements
            </Badge>
            <Badge variant="neutral" size="sm">
              Read-Only
            </Badge>
          </div>
          <p className="text-xs text-slate-600 max-w-2xl leading-relaxed">
            Interactive characterization dashboard analyzing traffic dynamics across 5 load scenarios, real Groq baseline vs simulator fidelity, and retrieval quality vs cost trade-offs.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 self-stretch md:self-auto justify-between md:justify-end">
          {lastFetched && (
            <span className="text-[11px] font-mono text-slate-500">
              Fetched {lastFetched.toLocaleTimeString()}
            </span>
          )}
          <Button
            variant="secondary"
            size="sm"
            onClick={() => fetchExperimentData(true)}
            isLoading={isRefreshing}
            leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />}
          >
            Refresh
          </Button>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="p-4 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-start gap-3">
          <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <p className="font-semibold">Failed to load empirical experiment records</p>
            <p className="text-rose-700 font-mono text-[11px]">{error}</p>
          </div>
        </div>
      )}

      {/* Main Tab Navigation */}
      <div className="flex items-center gap-2 border-b border-[#E6E9EF] pb-2 overflow-x-auto">
        <button
          onClick={() => setActiveTab('traffic')}
          className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-medium transition-all ${
            activeTab === 'traffic'
              ? 'bg-indigo-50 text-indigo-700 border border-indigo-200/90 font-semibold shadow-xs'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100 border border-transparent'
          }`}
        >
          <TrendingUp className="w-4 h-4" />
          <span>Load Stress & Traffic Dynamics</span>
          {loadData?.scenarios && (
            <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-slate-100 text-slate-600 font-mono">
              {loadData.scenarios.length} scenarios
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveTab('retrieval')}
          className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-medium transition-all ${
            activeTab === 'retrieval'
              ? 'bg-indigo-50 text-indigo-700 border border-indigo-200/90 font-semibold shadow-xs'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100 border border-transparent'
          }`}
        >
          <BarChart3 className="w-4 h-4" />
          <span>Retrieval Quality & Cost Frontier</span>
          <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-slate-100 text-slate-600 font-mono">
            Stage 6 & 8B.2
          </span>
        </button>

        <button
          onClick={() => setActiveTab('catalog')}
          className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-medium transition-all ${
            activeTab === 'catalog'
              ? 'bg-indigo-50 text-indigo-700 border border-indigo-200/90 font-semibold shadow-xs'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100 border border-transparent'
          }`}
        >
          <Database className="w-4 h-4" />
          <span>Datasets & Pricing Basis</span>
        </button>
      </div>

      {isLoading ? (
        <div className="p-12 text-center space-y-3">
          <RefreshCw className="w-6 h-6 text-indigo-600 animate-spin mx-auto" />
          <p className="text-xs text-slate-500 font-mono">Loading empirical experiment data from disk...</p>
        </div>
      ) : (
        <>
          {/* ========================================================================= */}
          {/* TAB 1: LOAD STRESS & TRAFFIC DYNAMICS */}
          {/* ========================================================================= */}
          {activeTab === 'traffic' && (
            <div className="space-y-6">
              {/* Calibration Fidelity Card */}
              {loadData?.calibration_comparison && (
                <div className="p-4 rounded-xl bg-gradient-to-r from-indigo-50/60 via-white to-slate-50 border border-indigo-100 shadow-xs space-y-3">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-indigo-100 pb-2.5">
                    <div className="flex items-center gap-2">
                      <Zap className="w-4 h-4 text-indigo-600 shrink-0" />
                      <h3 className="text-xs font-bold text-indigo-950 uppercase tracking-wider">
                        Real Groq Baseline vs. Simulator Calibration Fidelity
                      </h3>
                    </div>
                    <Badge variant="blue" size="sm">
                      {loadData.calibration_comparison.difference_pct}% Latency Delta
                    </Badge>
                  </div>

                  <p className="text-xs text-slate-700 leading-relaxed font-sans">
                    {loadData.calibration_comparison.conclusion}
                  </p>

                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 pt-1">
                    <div className="p-3 rounded-lg bg-white border border-[#E6E9EF] shadow-2xs space-y-1">
                      <div className="text-[10px] font-mono uppercase text-sky-700 font-semibold">
                        Real Groq API (Median)
                      </div>
                      <div className="text-lg font-bold font-mono text-slate-900">
                        {loadData.calibration_comparison.real_groq_median_ms.toFixed(1)} ms
                      </div>
                      <div className="text-[10px] text-slate-500">Non-streaming turnaround</div>
                    </div>

                    <div className="p-3 rounded-lg bg-white border border-[#E6E9EF] shadow-2xs space-y-1">
                      <div className="text-[10px] font-mono uppercase text-indigo-700 font-semibold">
                        Simulator (Median)
                      </div>
                      <div className="text-lg font-bold font-mono text-slate-900">
                        {loadData.calibration_comparison.simulator_median_ms.toFixed(1)} ms
                      </div>
                      <div className="text-[10px] text-slate-500">Calibrated lognormal</div>
                    </div>

                    <div className="p-3 rounded-lg bg-white border border-[#E6E9EF] shadow-2xs space-y-1">
                      <div className="text-[10px] font-mono uppercase text-emerald-700 font-semibold">
                        Real Groq TTFT (Median)
                      </div>
                      <div className="text-lg font-bold font-mono text-slate-900">
                        {loadData.calibration_comparison.real_groq_ttft_median_ms.toFixed(1)} ms
                      </div>
                      <div className="text-[10px] text-slate-500">Time to first chunk</div>
                    </div>

                    <div className="p-3 rounded-lg bg-white border border-[#E6E9EF] shadow-2xs space-y-1">
                      <div className="text-[10px] font-mono uppercase text-emerald-700 font-semibold">
                        Simulator TTFT (Median)
                      </div>
                      <div className="text-lg font-bold font-mono text-slate-900">
                        {loadData.calibration_comparison.simulator_ttft_median_ms.toFixed(1)} ms
                      </div>
                      <div className="text-[10px] text-slate-500">
                        Delta: {loadData.calibration_comparison.ttft_difference_pct}%
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Traffic Filters Bar */}
              <div className="p-3.5 rounded-lg bg-white border border-[#E6E9EF] shadow-xs flex flex-wrap items-center justify-between gap-3 text-xs">
                <div className="flex flex-wrap items-center gap-3">
                  <div className="flex items-center gap-1.5 text-slate-500 font-mono text-[11px]">
                    <Filter className="w-3.5 h-3.5 text-indigo-600" />
                    <span>Source:</span>
                  </div>
                  <div className="flex items-center gap-1 bg-slate-100 p-0.5 rounded-lg border border-slate-200">
                    <button
                      onClick={() => setSourceFilter('all')}
                      className={`px-2.5 py-1 rounded text-[11px] font-mono transition-all ${
                        sourceFilter === 'all'
                          ? 'bg-white text-slate-900 font-semibold shadow-2xs'
                          : 'text-slate-600 hover:text-slate-900'
                      }`}
                    >
                      All ({loadData?.scenarios?.length || 0})
                    </button>
                    <button
                      onClick={() => setSourceFilter('real')}
                      className={`px-2.5 py-1 rounded text-[11px] font-mono transition-all ${
                        sourceFilter === 'real'
                          ? 'bg-sky-600 text-white font-semibold shadow-2xs'
                          : 'text-slate-600 hover:text-slate-900'
                      }`}
                    >
                      Real Groq (1)
                    </button>
                    <button
                      onClick={() => setSourceFilter('simulator')}
                      className={`px-2.5 py-1 rounded text-[11px] font-mono transition-all ${
                        sourceFilter === 'simulator'
                          ? 'bg-indigo-600 text-white font-semibold shadow-2xs'
                          : 'text-slate-600 hover:text-slate-900'
                      }`}
                    >
                      Simulator (6)
                    </button>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <span className="text-slate-500 font-mono text-[11px]">Scenario:</span>
                  <select
                    value={selectedScenarioId}
                    onChange={(e) => setSelectedScenarioId(e.target.value)}
                    className="bg-white border border-slate-300 text-slate-800 text-xs rounded-md px-2.5 py-1 font-mono focus:outline-none focus:border-indigo-500"
                  >
                    <option value="all">All Scenarios</option>
                    {(loadData?.scenarios || []).map((sc) => (
                      <option key={sc.scenario_id} value={sc.scenario_id}>
                        {sc.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Scenarios Grid */}
              <div className="space-y-4">
                {filteredScenarios.map((sc) => {
                  const isReal = sc.source === 'real';
                  const statusOk = sc.status_breakdown.ok;
                  const status429 = sc.status_breakdown.rate_limited_429;
                  const status504 = sc.status_breakdown.timeout_504;
                  const status500 = sc.status_breakdown.server_error_500;
                  const total = sc.total_requests || 1;

                  const okPct = Math.round((statusOk / total) * 100);
                  const rlPct = Math.round((status429 / total) * 100);
                  const toPct = Math.round((status504 / total) * 100);
                  const errPct = Math.round((status500 / total) * 100);

                  return (
                    <Card key={sc.scenario_id}>
                      <div className="space-y-4">
                        {/* Header */}
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[#E6E9EF] pb-3">
                          <div className="space-y-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <h3 className="text-sm font-bold text-slate-900">{sc.name}</h3>
                              {isReal ? (
                                <Badge variant="blue" size="sm">
                                  REAL GROQ API
                                </Badge>
                              ) : (
                                <Badge variant="purple" size="sm">
                                  STAND-IN SIMULATOR
                                </Badge>
                              )}
                              <span className="text-[11px] font-mono text-slate-500">
                                {sc.total_requests} requests
                              </span>
                            </div>
                            <p className="text-xs text-slate-500 font-mono text-[11px]">
                              Provider: <span className="text-slate-700 font-medium">{sc.provider}</span>
                            </p>
                          </div>

                          <div className="flex items-center gap-2">
                            <div className="text-right">
                              <div className="text-xs font-mono font-bold text-slate-900">
                                Success: {sc.success_rate_pct}%
                              </div>
                              <div className="text-[10px] font-mono text-slate-500">
                                {sc.successful_requests}/{sc.total_requests} fulfilled
                              </div>
                            </div>
                            {sc.success_rate_pct === 100 ? (
                              <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
                            ) : sc.success_rate_pct >= 50 ? (
                              <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0" />
                            ) : (
                              <XCircle className="w-5 h-5 text-rose-600 shrink-0" />
                            )}
                          </div>
                        </div>

                        {/* Traffic Pattern & Description */}
                        <div className="p-3 rounded-lg bg-[#F9FAFB] border border-[#E6E9EF] text-xs space-y-1.5">
                          <p className="text-slate-700 leading-relaxed text-[11.5px] font-sans">
                            {sc.description}
                          </p>
                          <div className="text-[11px] text-slate-500 font-mono">
                            <span className="text-indigo-600 font-semibold">Traffic Pattern:</span> {sc.traffic_pattern}
                          </div>
                        </div>

                        {/* Stacked Status Breakdown Bar */}
                        <div className="space-y-1.5">
                          <div className="flex justify-between text-[11px] font-mono text-slate-500">
                            <span>Status Distribution</span>
                            <span className="text-slate-700 font-medium">
                              {statusOk} OK ({okPct}%)
                              {status429 > 0 && ` • ${status429} Rate Limited (${rlPct}%)`}
                              {status504 > 0 && ` • ${status504} Timed Out (${toPct}%)`}
                              {status500 > 0 && ` • ${status500} Server Error (${errPct}%)`}
                            </span>
                          </div>
                          <div className="h-2.5 w-full rounded-full bg-slate-200 overflow-hidden flex">
                            {okPct > 0 && (
                              <div
                                style={{ width: `${okPct}%` }}
                                className="bg-emerald-500 h-full transition-all"
                                title={`Successful 200 OK: ${statusOk} (${okPct}%)`}
                              />
                            )}
                            {rlPct > 0 && (
                              <div
                                style={{ width: `${rlPct}%` }}
                                className="bg-amber-500 h-full transition-all"
                                title={`Rate Limited 429: ${status429} (${rlPct}%)`}
                              />
                            )}
                            {toPct > 0 && (
                              <div
                                style={{ width: `${toPct}%` }}
                                className="bg-rose-500 h-full transition-all"
                                title={`Gateway Timeout 504: ${status504} (${toPct}%)`}
                              />
                            )}
                            {errPct > 0 && (
                              <div
                                style={{ width: `${errPct}%` }}
                                className="bg-red-700 h-full transition-all"
                                title={`Server Error 500: ${status500} (${errPct}%)`}
                              />
                            )}
                          </div>
                        </div>

                        {/* Metrics Grid */}
                        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 text-xs font-mono">
                          <div className="p-2.5 rounded bg-[#F9FAFB] border border-[#E6E9EF]">
                            <div className="text-[10px] text-slate-400 uppercase font-semibold">Median Latency</div>
                            <div className="text-sm font-bold text-slate-900">
                              {sc.total_latency_ms?.median?.toFixed(1) || sc.total_latency_ms?.p50?.toFixed(1) || '—'} ms
                            </div>
                            <div className="text-[10px] text-slate-400">p50 turnaround</div>
                          </div>

                          <div className="p-2.5 rounded bg-[#F9FAFB] border border-[#E6E9EF]">
                            <div className="text-[10px] text-slate-400 uppercase font-semibold">p95 Latency</div>
                            <div className="text-sm font-bold text-slate-900">
                              {sc.total_latency_ms?.p95?.toFixed(1) || '—'} ms
                            </div>
                            <div className="text-[10px] text-slate-400">95th percentile</div>
                          </div>

                          <div className="p-2.5 rounded bg-[#F9FAFB] border border-[#E6E9EF]">
                            <div className="text-[10px] text-slate-400 uppercase font-semibold">Max Latency</div>
                            <div className="text-sm font-bold text-slate-900">
                              {sc.total_latency_ms?.max?.toFixed(1) || '—'} ms
                            </div>
                            <div className="text-[10px] text-slate-400">Peak wait time</div>
                          </div>

                          <div className="p-2.5 rounded bg-[#F9FAFB] border border-[#E6E9EF]">
                            <div className="text-[10px] text-slate-400 uppercase font-semibold">Streaming TTFT</div>
                            <div className="text-sm font-bold text-slate-900">
                              {sc.ttft_ms?.median?.toFixed(1) || '—'} ms
                            </div>
                            <div className="text-[10px] text-slate-400">p50 time to token</div>
                          </div>

                          <div className="p-2.5 rounded bg-[#F9FAFB] border border-[#E6E9EF]">
                            <div className="text-[10px] text-slate-400 uppercase font-semibold">Total Retries</div>
                            <div className="text-sm font-bold text-slate-900">
                              {sc.total_retries}
                            </div>
                            <div className="text-[10px] text-slate-400">
                              avg {sc.avg_retries_per_request.toFixed(2)}/req
                            </div>
                          </div>

                          <div className="p-2.5 rounded bg-[#F9FAFB] border border-[#E6E9EF]">
                            <div className="text-[10px] text-slate-400 uppercase font-semibold">Cost / 1k Queries</div>
                            <div className="text-sm font-bold text-emerald-600">
                              ${sc.cost_per_1000_answers_usd.toFixed(4)}
                            </div>
                            <div className="text-[10px] text-slate-400">
                              total ${sc.estimated_cost_usd.toFixed(5)}
                            </div>
                          </div>
                        </div>
                      </div>
                    </Card>
                  );
                })}
              </div>
            </div>
          )}

          {/* ========================================================================= */}
          {/* TAB 2: RETRIEVAL QUALITY & COST FRONTIER */}
          {/* ========================================================================= */}
          {activeTab === 'retrieval' && (
            <div className="space-y-6">
              {/* Methodological Context & Denominator Callout */}
              <div className="p-4 rounded-xl bg-indigo-50/50 border border-indigo-100 text-xs space-y-2">
                <div className="flex items-center gap-2 text-indigo-900 font-bold uppercase tracking-wider text-[11px]">
                  <Info className="w-4 h-4 text-indigo-600 shrink-0" />
                  <span>Evaluation Suite & Denominator Methodology</span>
                </div>
                <p className="text-slate-700 leading-relaxed text-[11.5px] font-sans">
                  {retrievalData?.methodology_note ||
                    'Evaluations compare Dense ChromaDB, Rank-BM25, and Hybrid RRF across 32 manually verified research questions (26 answerable, 6 unanswerable) from the 3 assignment papers.'}
                </p>
                <div className="flex flex-wrap gap-4 pt-1 font-mono text-[11px] text-slate-600">
                  <div>
                    <span className="text-indigo-700 font-semibold">Recall@k & MRR Basis:</span> 26 answerable questions
                  </div>
                  <div>
                    <span className="text-indigo-700 font-semibold">Accuracy & Refusal Basis:</span> 32 total questions
                  </div>
                </div>
              </div>

              {/* Retrieval View Switcher */}
              <div className="p-3.5 rounded-lg bg-white border border-[#E6E9EF] shadow-xs flex flex-wrap items-center justify-between gap-3 text-xs">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-slate-500 font-mono text-[11px]">View:</span>
                  <div className="flex items-center gap-1 bg-slate-100 p-0.5 rounded-lg border border-slate-200">
                    <button
                      onClick={() => setRetrievalView('comparison')}
                      className={`px-3 py-1 rounded text-[11px] font-mono transition-all ${
                        retrievalView === 'comparison'
                          ? 'bg-white text-indigo-700 font-semibold shadow-2xs'
                          : 'text-slate-600 hover:text-slate-900'
                      }`}
                    >
                      Stage 6 vs 8B.2 Deltas
                    </button>
                    <button
                      onClick={() => setRetrievalView('stage8b2')}
                      className={`px-3 py-1 rounded text-[11px] font-mono transition-all ${
                        retrievalView === 'stage8b2'
                          ? 'bg-white text-indigo-700 font-semibold shadow-2xs'
                          : 'text-slate-600 hover:text-slate-900'
                      }`}
                    >
                      Stage 8B.2 (Caption-Preserved)
                    </button>
                    <button
                      onClick={() => setRetrievalView('top_k')}
                      className={`px-3 py-1 rounded text-[11px] font-mono transition-all ${
                        retrievalView === 'top_k'
                          ? 'bg-white text-indigo-700 font-semibold shadow-2xs'
                          : 'text-slate-600 hover:text-slate-900'
                      }`}
                    >
                      Top-k Scaling Frontier (k=5, 8, 10)
                    </button>
                    <button
                      onClick={() => setRetrievalView('stage6')}
                      className={`px-3 py-1 rounded text-[11px] font-mono transition-all ${
                        retrievalView === 'stage6'
                          ? 'bg-white text-indigo-700 font-semibold shadow-2xs'
                          : 'text-slate-600 hover:text-slate-900'
                      }`}
                    >
                      Stage 6 (Initial)
                    </button>
                  </div>
                </div>

                {retrievalView === 'stage8b2' && (
                  <div className="flex items-center gap-2">
                    <span className="text-slate-500 font-mono text-[11px]">Top-k:</span>
                    <select
                      value={kFilter}
                      onChange={(e) => setKFilter(e.target.value as any)}
                      className="bg-white border border-slate-300 text-slate-800 text-xs rounded-md px-2.5 py-1 font-mono focus:outline-none focus:border-indigo-500"
                    >
                      <option value="all">All (k=5, 8, 10)</option>
                      <option value="5">k = 5</option>
                      <option value="8">k = 8</option>
                      <option value="10">k = 10</option>
                    </select>
                  </div>
                )}
              </div>

              {/* VIEW 1: COMPARATIVE DELTAS */}
              {retrievalView === 'comparison' && (
                <div className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {(retrievalData?.stage6_vs_stage8b2_comparison || []).map((comp, idx) => {
                      const s6Recall = (comp.stage6.recall_at_5 * 100).toFixed(1);
                      const s8Recall = (comp.stage8b2.recall_at_5 * 100).toFixed(1);
                      const recallDelta = comp.delta.recall_at_5_improvement;

                      const s6Acc = comp.stage6.correct_and_cited_pct.toFixed(1);
                      const s8Acc = comp.stage8b2.correct_and_cited_pct.toFixed(1);
                      const accDelta = comp.delta.correct_and_cited_improvement_pct;

                      return (
                        <Card key={idx}>
                          <div className="space-y-4">
                            <div className="flex items-start justify-between gap-2 border-b border-[#E6E9EF] pb-3">
                              <div>
                                <h4 className="text-sm font-bold text-slate-900">
                                  {comp.configuration_name}
                                </h4>
                                <div className="text-[11px] font-mono text-slate-500">
                                  Evaluation at top-k = {comp.k} (5 passages)
                                </div>
                              </div>
                              <Badge variant="purple" size="sm">
                                k = {comp.k}
                              </Badge>
                            </div>

                            {/* Comparison Metric Bars */}
                            <div className="space-y-3">
                              {/* Recall@5 Comparison */}
                              <div className="space-y-1">
                                <div className="flex justify-between text-xs font-mono">
                                  <span className="text-slate-500">Recall@5 (26 ans. qs)</span>
                                  <span className="text-slate-800">
                                    Stage 6: <span className="text-slate-400">{s6Recall}%</span> → Stage 8B.2:{' '}
                                    <span className="text-indigo-700 font-bold">{s8Recall}%</span>
                                    {recallDelta > 0 && (
                                      <span className="text-emerald-600 ml-1.5 font-bold">
                                        (+{recallDelta.toFixed(1)}%)
                                      </span>
                                    )}
                                  </span>
                                </div>
                                <div className="grid grid-cols-2 gap-2">
                                  <div className="h-2 rounded bg-slate-200 overflow-hidden">
                                    <div
                                      style={{ width: `${s6Recall}%` }}
                                      className="h-full bg-slate-400 rounded"
                                    />
                                  </div>
                                  <div className="h-2 rounded bg-slate-200 overflow-hidden">
                                    <div
                                      style={{ width: `${s8Recall}%` }}
                                      className="h-full bg-indigo-600 rounded"
                                    />
                                  </div>
                                </div>
                              </div>

                              {/* Correct & Cited Accuracy Comparison */}
                              <div className="space-y-1">
                                <div className="flex justify-between text-xs font-mono">
                                  <span className="text-slate-500">Accuracy (32 qs)</span>
                                  <span className="text-slate-800">
                                    Stage 6: <span className="text-slate-400">{s6Acc}%</span> → Stage 8B.2:{' '}
                                    <span className="text-emerald-700 font-bold">{s8Acc}%</span>
                                    {accDelta > 0 && (
                                      <span className="text-emerald-600 ml-1.5 font-bold">
                                        (+{accDelta.toFixed(1)}%)
                                      </span>
                                    )}
                                  </span>
                                </div>
                                <div className="grid grid-cols-2 gap-2">
                                  <div className="h-2 rounded bg-slate-200 overflow-hidden">
                                    <div
                                      style={{ width: `${s6Acc}%` }}
                                      className="h-full bg-slate-400 rounded"
                                    />
                                  </div>
                                  <div className="h-2 rounded bg-slate-200 overflow-hidden">
                                    <div
                                      style={{ width: `${s8Acc}%` }}
                                      className="h-full bg-emerald-600 rounded"
                                    />
                                  </div>
                                </div>
                              </div>
                            </div>

                            {/* Detailed Statistics Grid */}
                            <div className="grid grid-cols-2 gap-2 pt-1 font-mono text-[11px]">
                              <div className="p-2 rounded bg-[#F9FAFB] border border-[#E6E9EF] space-y-0.5">
                                <div className="text-slate-400 text-[10px]">MRR (Mean Reciprocal Rank)</div>
                                <div className="text-slate-800 font-bold">
                                  {comp.stage6.mrr.toFixed(4)} → {comp.stage8b2.mrr.toFixed(4)}
                                </div>
                              </div>

                              <div className="p-2 rounded bg-[#F9FAFB] border border-[#E6E9EF] space-y-0.5">
                                <div className="text-slate-400 text-[10px]">Wrong Answers %</div>
                                <div className="text-slate-800 font-bold">
                                  {comp.stage6.wrong_pct.toFixed(1)}% → {comp.stage8b2.wrong_pct.toFixed(1)}%
                                </div>
                              </div>

                              <div className="p-2 rounded bg-[#F9FAFB] border border-[#E6E9EF] space-y-0.5">
                                <div className="text-slate-400 text-[10px]">Retrieval Latency (Mean)</div>
                                <div className="text-slate-800 font-bold">
                                  {comp.stage6.latency_mean_ms.toFixed(1)}ms → {comp.stage8b2.latency_mean_ms.toFixed(1)}ms
                                </div>
                              </div>

                              <div className="p-2 rounded bg-[#F9FAFB] border border-[#E6E9EF] space-y-0.5">
                                <div className="text-slate-400 text-[10px]">Cost / 1k Queries</div>
                                <div className="text-emerald-600 font-bold">
                                  ${comp.stage6.cost_per_1000_usd.toFixed(4)} → ${comp.stage8b2.cost_per_1000_usd.toFixed(4)}
                                </div>
                              </div>
                            </div>
                          </div>
                        </Card>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* VIEW 2: TOP-K SCALING FRONTIER */}
              {retrievalView === 'top_k' && (
                <div className="space-y-4">
                  <div className="p-4 rounded-xl bg-white border border-[#E6E9EF] shadow-xs space-y-4">
                    <div className="space-y-1">
                      <h4 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                        <TrendingUp className="w-4 h-4 text-indigo-600" />
                        <span>Top-k Scaling Curve: Recall vs. Context Token Cost Frontier</span>
                      </h4>
                      <p className="text-xs text-slate-600">
                        Evaluated across Full Hybrid Retriever (Dense + BM25 + FactStore) expanding context depth from k=5 to k=8 and k=10.
                      </p>
                    </div>

                    {/* Multi-Step Frontier Cards */}
                    <div className="p-4 rounded-lg bg-[#F9FAFB] border border-[#E6E9EF] space-y-4">
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        {(retrievalData?.top_k_scaling_stage8b2 || []).map((step) => {
                          const recallPct = (step.recall * 100).toFixed(1);
                          return (
                            <div
                              key={step.k}
                              className={`p-4 rounded-lg border transition-all ${
                                step.k === 10
                                  ? 'bg-indigo-50/50 border-indigo-200 shadow-2xs'
                                  : 'bg-white border-[#E6E9EF]'
                              }`}
                            >
                              <div className="flex items-center justify-between pb-2 border-b border-[#E6E9EF]">
                                <Badge variant={step.k === 10 ? 'purple' : 'neutral'} size="sm">
                                  Top-k = {step.k}
                                </Badge>
                                <span className="text-xs font-mono font-bold text-slate-900">
                                  Recall: {recallPct}%
                                </span>
                              </div>

                              <div className="space-y-2 pt-3 text-xs font-mono">
                                <div className="flex justify-between">
                                  <span className="text-slate-500">MRR:</span>
                                  <span className="text-slate-800 font-semibold">{step.mrr.toFixed(4)}</span>
                                </div>
                                <div className="flex justify-between">
                                  <span className="text-slate-500">Accuracy (32 qs):</span>
                                  <span className="text-emerald-600 font-semibold">
                                    {step.correct_and_cited_pct.toFixed(1)}%
                                  </span>
                                </div>
                                <div className="flex justify-between">
                                  <span className="text-slate-500">Avg Context Tokens:</span>
                                  <span className="text-slate-800">{step.avg_context_tokens.toFixed(0)}</span>
                                </div>
                                <div className="flex justify-between">
                                  <span className="text-slate-500">Cost / 1k Queries:</span>
                                  <span className="text-emerald-600 font-bold">
                                    ${step.cost_per_1000_usd.toFixed(4)}
                                  </span>
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>

                      {/* Analysis Callout */}
                      <div className="p-3 rounded bg-white border border-[#E6E9EF] text-xs text-slate-700 space-y-1">
                        <span className="font-semibold text-indigo-700">Frontier Conclusion:</span>
                        <p className="text-[11.5px] text-slate-600 leading-relaxed font-sans">
                          Increasing from k=5 to k=10 increases Recall@k from 76.92% (20/26) to 88.46% (23/26) — retrieving the critical Transformer base table chunk with high certainty — at the cost of a 69.9% increase in token expenditure ($0.3474 vs $0.5901 per 1,000 queries).
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* VIEW 3: STAGE 8B.2 FULL CONFIGURATIONS */}
              {retrievalView === 'stage8b2' && (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {(retrievalData?.stage8b2?.configurations || [])
                    .filter((c) => {
                      if (kFilter === 'all') return true;
                      const kVal = c.top_k || c.k;
                      return String(kVal) === kFilter;
                    })
                    .map((cfg, idx) => {
                      const recall = cfg.recall_at_5 ?? cfg.recall_at_8 ?? cfg.recall_at_10 ?? 0;
                      const recallPct = (Number(recall) * 100).toFixed(1);
                      const accPct = Number(cfg.correct_and_cited_percentage || cfg.correct_and_cited_pct || 0).toFixed(1);
                      const wrongPct = Number(cfg.wrong_answer_percentage || cfg.wrong_pct || 0).toFixed(1);

                      return (
                        <Card key={idx}>
                          <div className="space-y-3">
                            <div className="flex items-start justify-between gap-2 border-b border-[#E6E9EF] pb-2.5">
                              <div>
                                <h4 className="text-xs font-bold text-slate-900">{cfg.config_name || cfg.name}</h4>
                                <div className="text-[10px] font-mono text-slate-500">
                                  Top-k: {cfg.top_k || cfg.k} passages
                                </div>
                              </div>
                              <Badge variant="purple" size="sm">
                                {accPct}% Acc
                              </Badge>
                            </div>

                            <div className="space-y-1.5 text-xs font-mono">
                              <div className="flex justify-between">
                                <span className="text-slate-500">Recall@k:</span>
                                <span className="text-indigo-700 font-bold">{recallPct}%</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-slate-500">MRR:</span>
                                <span className="text-slate-800">{Number(cfg.mrr).toFixed(4)}</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-slate-500">Correct & Cited:</span>
                                <span className="text-emerald-600 font-semibold">{cfg.correct_and_cited}/32</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-slate-500">Wrong Answers:</span>
                                <span className="text-rose-600 font-semibold">{cfg.wrong_answers} ({wrongPct}%)</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-slate-500">Correct Refusals:</span>
                                <span className="text-slate-800">{cfg.correct_refusals}/6</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-slate-500">Avg Latency:</span>
                                <span className="text-slate-800">
                                  {Number(cfg.avg_retrieval_latency_ms || cfg.retrieval_latency_mean_ms || 0).toFixed(1)} ms
                                </span>
                              </div>
                              <div className="flex justify-between pt-1.5 border-t border-[#E6E9EF]">
                                <span className="text-slate-500">Cost / 1k Queries:</span>
                                <span className="text-emerald-600 font-bold">
                                  ${Number(cfg.cost_per_1000_queries_usd || cfg.cost_per_1000_answers_usd || 0).toFixed(4)}
                                </span>
                              </div>
                            </div>
                          </div>
                        </Card>
                      );
                    })}
                </div>
              )}

              {/* VIEW 4: STAGE 6 BENCHMARK */}
              {retrievalView === 'stage6' && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {(retrievalData?.stage6?.configurations || []).map((cfg, idx) => {
                    const recallPct = (Number(cfg.recall_at_5 || 0) * 100).toFixed(1);
                    const accPct = Number(cfg.correct_and_cited_pct || 0).toFixed(1);

                    return (
                      <Card key={idx}>
                        <div className="space-y-3">
                          <div className="flex items-start justify-between gap-2 border-b border-[#E6E9EF] pb-2.5">
                            <div>
                              <h4 className="text-xs font-bold text-slate-900">{cfg.config_name || cfg.name}</h4>
                              <div className="text-[10px] font-mono text-slate-500">
                                Stage 6 Initial (Without Table Caption Preservation)
                              </div>
                            </div>
                            <Badge variant="neutral" size="sm">
                              k = 5
                            </Badge>
                          </div>

                          <div className="space-y-1.5 text-xs font-mono">
                            <div className="flex justify-between">
                              <span className="text-slate-500">Recall@5:</span>
                              <span className="text-slate-900 font-bold">{recallPct}%</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-slate-500">MRR:</span>
                              <span className="text-slate-800">{Number(cfg.mrr).toFixed(4)}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-slate-500">Accuracy (Correct & Cited):</span>
                              <span className="text-emerald-600 font-semibold">{accPct}% ({cfg.correct_and_cited}/32)</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-slate-500">Wrong Answers:</span>
                              <span className="text-rose-600">{cfg.wrong_answers}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-slate-500">Retrieval Latency Mean:</span>
                              <span className="text-slate-800">{Number(cfg.retrieval_latency_mean_ms).toFixed(1)} ms</span>
                            </div>
                            <div className="flex justify-between pt-1.5 border-t border-[#E6E9EF]">
                              <span className="text-slate-500">Cost / 1k Answers:</span>
                              <span className="text-emerald-600 font-bold">
                                ${Number(cfg.cost_per_1000_answers_usd).toFixed(4)}
                              </span>
                            </div>
                          </div>
                        </div>
                      </Card>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* ========================================================================= */}
          {/* TAB 3: DATASETS & PRICING BASIS */}
          {/* ========================================================================= */}
          {activeTab === 'catalog' && (
            <div className="space-y-6">
              {/* Pricing Basis Card */}
              <div className="p-4 rounded-xl bg-white border border-[#E6E9EF] shadow-xs space-y-3">
                <div className="flex items-center gap-2 text-slate-900 font-bold text-xs uppercase tracking-wider">
                  <DollarSign className="w-4 h-4 text-emerald-600" />
                  <span>Cost Modeling & Pricing Basis</span>
                </div>
                <p className="text-xs text-slate-600 leading-relaxed font-sans">
                  All dollar projections derive from the standard Groq model pricing for{' '}
                  <code className="text-slate-800 font-mono bg-slate-100 px-1 py-0.5 rounded">openai/gpt-oss-120b</code>:
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                  <div className="p-3 rounded-lg bg-[#F9FAFB] border border-[#E6E9EF] font-mono text-xs space-y-1">
                    <div className="text-slate-500 text-[10px] uppercase font-semibold">Prompt Token Pricing</div>
                    <div className="text-base font-bold text-emerald-600">
                      ${overview?.pricing_basis.prompt_tokens_per_million_usd.toFixed(2)} / 1M tokens
                    </div>
                    <div className="text-[10px] text-slate-400 font-sans">Injected query + retrieved context</div>
                  </div>

                  <div className="p-3 rounded-lg bg-[#F9FAFB] border border-[#E6E9EF] font-mono text-xs space-y-1">
                    <div className="text-slate-500 text-[10px] uppercase font-semibold">Completion Token Pricing</div>
                    <div className="text-base font-bold text-emerald-600">
                      ${overview?.pricing_basis.completion_tokens_per_million_usd.toFixed(2)} / 1M tokens
                    </div>
                    <div className="text-[10px] text-slate-400 font-sans">Generated synthesis answer</div>
                  </div>
                </div>
              </div>

              {/* Preserved File Artifacts Manifest */}
              <Card
                title="Preserved Empirical File Manifest"
                subtitle="Read-only historical CSV and JSON data sources"
              >
                <div className="space-y-2 text-xs font-mono">
                  <div className="p-2.5 rounded bg-[#F9FAFB] border border-[#E6E9EF] flex flex-col sm:flex-row sm:items-center justify-between gap-1">
                    <div>
                      <span className="text-indigo-700 font-bold">experiments/results.csv</span>
                      <div className="text-[11px] text-slate-500">119 records across Real Groq baseline and Scenarios A–E</div>
                    </div>
                    <Badge variant="neutral" size="sm">
                      119 records
                    </Badge>
                  </div>

                  <div className="p-2.5 rounded bg-[#F9FAFB] border border-[#E6E9EF] flex flex-col sm:flex-row sm:items-center justify-between gap-1">
                    <div>
                      <span className="text-indigo-700 font-bold">experiments/reports/load_experiment_summary.json</span>
                      <div className="text-[11px] text-slate-500">Aggregated statistical percentiles (p50, p95, p99, TTFT)</div>
                    </div>
                    <Badge variant="emerald" size="sm">
                      Verified
                    </Badge>
                  </div>

                  <div className="p-2.5 rounded bg-[#F9FAFB] border border-[#E6E9EF] flex flex-col sm:flex-row sm:items-center justify-between gap-1">
                    <div>
                      <span className="text-purple-700 font-bold">experiments/retrieval/retrieval_summary.json</span>
                      <div className="text-[11px] text-slate-500">Stage 6 evaluation across 4 retrieval configurations</div>
                    </div>
                    <Badge variant="purple" size="sm">
                      Stage 6
                    </Badge>
                  </div>

                  <div className="p-2.5 rounded bg-[#F9FAFB] border border-[#E6E9EF] flex flex-col sm:flex-row sm:items-center justify-between gap-1">
                    <div>
                      <span className="text-purple-700 font-bold">experiments/retrieval/retrieval_summary_stage8b2.json</span>
                      <div className="text-[11px] text-slate-500">Stage 8B.2 evaluation with caption preservation and top-k scaling</div>
                    </div>
                    <Badge variant="purple" size="sm">
                      Stage 8B.2
                    </Badge>
                  </div>

                  <div className="p-2.5 rounded bg-[#F9FAFB] border border-[#E6E9EF] flex flex-col sm:flex-row sm:items-center justify-between gap-1">
                    <div>
                      <span className="text-slate-800 font-bold">experiments/retrieval/retrieval_results.csv</span>
                      <div className="text-[11px] text-slate-500">128 question-level records for Stage 6</div>
                    </div>
                    <Badge variant="neutral" size="sm">
                      128 rows
                    </Badge>
                  </div>

                  <div className="p-2.5 rounded bg-[#F9FAFB] border border-[#E6E9EF] flex flex-col sm:flex-row sm:items-center justify-between gap-1">
                    <div>
                      <span className="text-slate-800 font-bold">experiments/retrieval/retrieval_results_stage8b2.csv</span>
                      <div className="text-[11px] text-slate-500">192 question-level records for Stage 8B.2</div>
                    </div>
                    <Badge variant="neutral" size="sm">
                      192 rows
                    </Badge>
                  </div>
                </div>
              </Card>
            </div>
          )}
        </>
      )}
    </div>
  );
};
