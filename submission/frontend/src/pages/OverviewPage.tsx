import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Activity,
  CheckCircle2,
  XCircle,
  Server,
  Layers,
  ShieldCheck,
  RefreshCw,
  Database,
  Clock,
  Cpu,
  AlertTriangle,
  AlertCircle,
  BarChart2,
  Radio,
  Zap,
  Gauge,
} from 'lucide-react';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { StatusDot } from '../components/ui/StatusDot';
import { api } from '../services/api';
import type {
  HealthResponse,
  ReadyResponse,
  ConnectionState,
  MetricsResponse,
} from '../types/api';

interface OverviewPageProps {
  health: HealthResponse | null;
  ready: ReadyResponse | null;
  connectionState: ConnectionState;
  isLoading: boolean;
  error: string | null;
  lastChecked: Date | null;
  latencyMs: number | null;
  onRefresh: () => void;
}

export const OverviewPage: React.FC<OverviewPageProps> = ({
  health,
  ready,
  connectionState,
  isLoading,
  error,
  lastChecked: _lastChecked,
  latencyMs,
  onRefresh,
}) => {
  const isOnline = connectionState === 'connected';

  // Live Metrics state
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null);
  const [isMetricsLoading, setIsMetricsLoading] = useState<boolean>(false);
  const [lastMetricsUpdate, setLastMetricsUpdate] = useState<Date | null>(null);
  const [isStale, setIsStale] = useState<boolean>(false);
  const [secondsAgo, setSecondsAgo] = useState<number>(0);

  const abortControllerRef = useRef<AbortController | null>(null);
  const isFetchingRef = useRef<boolean>(false);

  // Fetch metrics function
  const fetchMetrics = useCallback(async () => {
    if (isFetchingRef.current) return;
    isFetchingRef.current = true;
    setIsMetricsLoading(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const data = await api.getMetrics(controller.signal);
      setMetrics(data);
      setLastMetricsUpdate(new Date());
      setIsStale(false);
      setSecondsAgo(0);
    } catch {
      // Preserve existing metrics snapshot if available; mark as stale
      if (metrics) {
        setIsStale(true);
      }
    } finally {
      setIsMetricsLoading(false);
      isFetchingRef.current = false;
      abortControllerRef.current = null;
    }
  }, [metrics]);

  // Periodic polling every 5,000ms
  useEffect(() => {
    let active = true;
    const poll = () => {
      if (!active) return;
      void fetchMetrics();
    };

    poll();
    const interval = setInterval(poll, 5000);

    return () => {
      active = false;
      clearInterval(interval);
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [fetchMetrics]);

  // Live seconds elapsed counter
  useEffect(() => {
    const timer = setInterval(() => {
      if (lastMetricsUpdate) {
        setSecondsAgo(Math.floor((Date.now() - lastMetricsUpdate.getTime()) / 1000));
      }
    }, 1000);
    return () => clearInterval(timer);
  }, [lastMetricsUpdate]);

  const handleManualRefreshAll = () => {
    onRefresh();
    fetchMetrics();
  };

  // Safe percentage helper
  const calcRate = (numerator: number, denominator: number): string => {
    if (denominator <= 0) return '0.0%';
    return `${((numerator / denominator) * 100).toFixed(1)}%`;
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* 1. Top Status Header Card */}
      <Card
        className="border-[#E6E9EF] bg-white shadow-[0_1px_3px_rgba(0,0,0,0.04)]"
        padding="lg"
      >
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div
              className={`w-12 h-12 rounded-xl flex items-center justify-center border shadow-2xs ${
                isOnline
                  ? 'bg-emerald-50 border-emerald-200 text-emerald-600'
                  : 'bg-rose-50 border-rose-200 text-rose-600'
              }`}
            >
              <Activity className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-slate-900">
                  FastAPI Gateway & Live Telemetry
                </h2>
                <StatusDot state={connectionState} size="md" />
              </div>
              <p className="text-xs text-slate-500 mt-0.5 font-mono">
                {isOnline
                  ? `Service '${health?.service || 'relay-research-assistant'}' is operational`
                  : error || 'Service is unreachable or not running'}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {lastMetricsUpdate && (
              <div className="text-right hidden md:block">
                <div className="flex items-center gap-1.5 text-[11px] text-emerald-700 font-mono font-medium">
                  <Radio className="w-3 h-3 text-emerald-600 animate-pulse" />
                  <span>LIVE POLLING (5s)</span>
                </div>
                <span className="text-xs text-slate-500 font-mono">
                  {secondsAgo}s ago ({lastMetricsUpdate.toLocaleTimeString()})
                </span>
              </div>
            )}

            <Button
              variant="secondary"
              size="sm"
              onClick={handleManualRefreshAll}
              isLoading={isLoading || isMetricsLoading}
              leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
            >
              Refresh Telemetry
            </Button>
          </div>
        </div>

        {/* Stale Warning Banner if background refresh encountered failure */}
        {isStale && (
          <div className="mt-4 p-3 rounded-lg bg-amber-50 border border-amber-200 flex items-center gap-2.5 text-xs text-amber-800 font-mono">
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
            <span>
              Telemetry refresh encountered a network interruption. Preserving last successful snapshot from{' '}
              {lastMetricsUpdate?.toLocaleTimeString() || 'prior probe'}.
            </span>
          </div>
        )}

        {/* Offline Warning if backend is not connected */}
        {!isOnline && (
          <div className="mt-4 p-3 rounded-lg bg-rose-50 border border-rose-200 flex items-center gap-2.5 text-xs text-rose-800 font-mono">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>
              Backend API is currently offline. Metrics and queue state are unavailable. Start FastAPI server on port 8000 to resume telemetry.
            </span>
          </div>
        )}

        {/* Diagnostic Badges Bar */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-6 pt-5 border-t border-[#E6E9EF]">
          <div className="space-y-1">
            <span className="text-[11px] text-slate-400 font-mono uppercase font-semibold">
              Gateway Connection
            </span>
            <div className="flex items-center gap-1.5">
              <Badge
                variant={isOnline ? 'emerald' : 'rose'}
                size="sm"
                icon={
                  isOnline ? (
                    <CheckCircle2 className="w-3 h-3" />
                  ) : (
                    <XCircle className="w-3 h-3" />
                  )
                }
              >
                {isOnline ? 'CONNECTED' : 'DISCONNECTED'}
              </Badge>
            </div>
          </div>

          <div className="space-y-1">
            <span className="text-[11px] text-slate-400 font-mono uppercase font-semibold">
              Probe Latency
            </span>
            <div className="text-xs font-mono font-medium text-slate-800">
              {latencyMs !== null ? `${latencyMs} ms` : '—'}
            </div>
          </div>

          <div className="space-y-1">
            <span className="text-[11px] text-slate-400 font-mono uppercase font-semibold">
              Active Provider
            </span>
            <div className="text-xs font-mono text-slate-800">
              {ready?.provider || metrics?.provider.provider_name ? (
                <Badge
                  variant={
                    (ready?.provider || metrics?.provider.provider_name) === 'simulator'
                      ? 'purple'
                      : 'blue'
                  }
                  size="sm"
                  icon={<Cpu className="w-3 h-3" />}
                >
                  {ready?.provider || metrics?.provider.provider_name}
                </Badge>
              ) : (
                '—'
              )}
            </div>
          </div>

          <div className="space-y-1">
            <span className="text-[11px] text-slate-400 font-mono uppercase font-semibold">
              Active Model
            </span>
            <div
              className="text-xs font-mono text-slate-800 font-medium truncate max-w-[140px]"
              title={ready?.model || metrics?.provider.model_name}
            >
              {ready?.model || metrics?.provider.model_name || '—'}
            </div>
          </div>
        </div>
      </Card>

      {/* 2. Request Statistics KPI Grid */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-xs font-mono text-slate-500 px-1">
          <span className="flex items-center gap-1.5 font-semibold text-slate-700">
            <BarChart2 className="w-3.5 h-3.5 text-slate-500" />
            REQUEST STATISTICS (LIFECYCLE COUNTERS)
          </span>
          <span>Source: TrafficManager Runtime State</span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {/* Total Submitted */}
          <div className="p-3.5 rounded-xl bg-white border border-[#E6E9EF] shadow-2xs space-y-1">
            <span className="text-[10.5px] font-mono text-slate-500 uppercase font-semibold block">
              Total Submitted
            </span>
            <div className="text-xl font-bold font-mono text-slate-900">
              {metrics ? metrics.requests.total_submitted : '—'}
            </div>
            <span className="text-[10px] font-mono text-slate-400 block truncate">
              Admitted + Queued
            </span>
          </div>

          {/* Successful */}
          <div className="p-3.5 rounded-xl bg-white border border-[#E6E9EF] shadow-2xs space-y-1">
            <span className="text-[10.5px] font-mono text-slate-500 uppercase font-semibold block">
              Successful
            </span>
            <div className="text-xl font-bold font-mono text-emerald-600">
              {metrics ? metrics.requests.successful : '—'}
            </div>
            <span className="text-[10px] font-mono text-emerald-700 font-medium block truncate">
              {metrics
                ? `${calcRate(metrics.requests.successful, metrics.requests.total_submitted)} success rate`
                : '—'}
            </span>
          </div>

          {/* Failed */}
          <div className="p-3.5 rounded-xl bg-white border border-[#E6E9EF] shadow-2xs space-y-1">
            <span className="text-[10.5px] font-mono text-slate-500 uppercase font-semibold block">
              Failed
            </span>
            <div className="text-xl font-bold font-mono text-rose-600">
              {metrics ? metrics.requests.failed : '—'}
            </div>
            <span className="text-[10px] font-mono text-rose-700 font-medium block truncate">
              {metrics
                ? `${calcRate(metrics.requests.failed, metrics.requests.total_submitted)} error rate`
                : '—'}
            </span>
          </div>

          {/* Rate Limited (429) */}
          <div className="p-3.5 rounded-xl bg-white border border-[#E6E9EF] shadow-2xs space-y-1">
            <span className="text-[10.5px] font-mono text-slate-500 uppercase font-semibold block">
              Rate Limited
            </span>
            <div className="text-xl font-bold font-mono text-amber-600">
              {metrics ? metrics.requests.rate_limited : '—'}
            </div>
            <span className="text-[10px] font-mono text-slate-400 block truncate">
              429 Throttled
            </span>
          </div>

          {/* Timed Out (504) */}
          <div className="p-3.5 rounded-xl bg-white border border-[#E6E9EF] shadow-2xs space-y-1">
            <span className="text-[10.5px] font-mono text-slate-500 uppercase font-semibold block">
              Timed Out
            </span>
            <div className="text-xl font-bold font-mono text-slate-700">
              {metrics ? metrics.requests.timed_out : '—'}
            </div>
            <span className="text-[10px] font-mono text-slate-400 block truncate">
              Queue/Exec Timeout
            </span>
          </div>

          {/* Retry Count */}
          <div className="p-3.5 rounded-xl bg-white border border-[#E6E9EF] shadow-2xs space-y-1">
            <span className="text-[10.5px] font-mono text-slate-500 uppercase font-semibold block">
              Retry Count
            </span>
            <div className="text-xl font-bold font-mono text-indigo-600">
              {metrics ? metrics.requests.retried : '—'}
            </div>
            <span className="text-[10px] font-mono text-slate-400 block truncate">
              Backoff Retries
            </span>
          </div>
        </div>
      </div>

      {/* 3. Traffic and Queue Monitoring Section */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* FIFO Queue Status Card */}
        <Card
          title={
            <div className="flex items-center gap-2 font-mono text-xs">
              <Layers className="w-3.5 h-3.5 text-sky-600" />
              <span>FIFO Request Queue & Capacity</span>
            </div>
          }
          subtitle="Governs bounded buffer depth and prompt capacity shedding"
          action={
            metrics ? (
              <Badge
                variant={
                  metrics.queue.utilization_pct > 80
                    ? 'rose'
                    : metrics.queue.utilization_pct > 40
                    ? 'amber'
                    : 'emerald'
                }
                size="sm"
              >
                {metrics.queue.utilization_pct}% Utilized
              </Badge>
            ) : null
          }
        >
          <div className="space-y-4 text-xs">
            <div className="p-3 rounded-lg bg-[#F9FAFB] border border-[#E6E9EF] space-y-2">
              <div className="flex justify-between items-center font-mono">
                <span className="text-slate-600">Current Queue Depth:</span>
                <span className="text-sm font-bold text-slate-900">
                  {metrics ? `${metrics.queue.current_depth} / ${metrics.queue.capacity}` : '—'}
                </span>
              </div>

              {/* Queue Progress Bar */}
              <div className="w-full bg-slate-200 h-2 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${
                    (metrics?.queue.utilization_pct ?? 0) > 80
                      ? 'bg-rose-500'
                      : (metrics?.queue.utilization_pct ?? 0) > 40
                      ? 'bg-amber-500'
                      : 'bg-emerald-500'
                  }`}
                  style={{ width: `${Math.min(100, Math.max(0, metrics?.queue.utilization_pct ?? 0))}%` }}
                />
              </div>

              <div className="flex justify-between text-[11px] font-mono text-slate-400 pt-1">
                <span>0 waiting</span>
                <span>Max Capacity: {metrics?.queue.capacity ?? 50} requests</span>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2 text-[11.5px] font-mono">
              <div className="p-2.5 rounded bg-[#F9FAFB] border border-[#E6E9EF] space-y-0.5">
                <span className="text-slate-400 block text-[10.5px]">QUEUE FULL DROPS</span>
                <span className="text-slate-800 font-semibold">
                  {metrics ? metrics.requests.queue_rejections : '—'}
                </span>
              </div>
              <div className="p-2.5 rounded bg-[#F9FAFB] border border-[#E6E9EF] space-y-0.5">
                <span className="text-slate-400 block text-[10.5px]">CLIENT CANCELS</span>
                <span className="text-slate-800 font-semibold">
                  {metrics ? metrics.requests.client_cancellations : '—'}
                </span>
              </div>
            </div>
          </div>
        </Card>

        {/* Concurrency & Active Workers Card */}
        <Card
          title={
            <div className="flex items-center gap-2 font-mono text-xs">
              <Gauge className="w-3.5 h-3.5 text-indigo-600" />
              <span>Concurrency & Active In-Flight</span>
            </div>
          }
          subtitle="Enforces strict semaphore bounding on concurrent provider execution"
          action={
            metrics ? (
              <Badge variant="purple" size="sm">
                Max: {metrics.concurrency.max_concurrency} Workers
              </Badge>
            ) : null
          }
        >
          <div className="space-y-4 text-xs">
            <div className="p-3 rounded-lg bg-[#F9FAFB] border border-[#E6E9EF] space-y-2">
              <div className="flex justify-between items-center font-mono">
                <span className="text-slate-600">Active In-Flight Calls:</span>
                <span className="text-sm font-bold text-slate-900">
                  {metrics
                    ? `${metrics.concurrency.active_in_flight} / ${metrics.concurrency.max_concurrency}`
                    : '—'}
                </span>
              </div>

              {/* Concurrency Slot Meter */}
              <div className="w-full bg-slate-200 h-2 rounded-full overflow-hidden">
                <div
                  className="h-full bg-indigo-600 rounded-full transition-all duration-500"
                  style={{
                    width: `${
                      metrics && metrics.concurrency.max_concurrency > 0
                        ? Math.min(
                            100,
                            (metrics.concurrency.active_in_flight /
                              metrics.concurrency.max_concurrency) *
                              100
                          )
                        : 0
                    }%`,
                  }}
                />
              </div>

              <div className="flex justify-between text-[11px] font-mono text-slate-400 pt-1">
                <span>0 idle</span>
                <span>Limit: {metrics?.concurrency.max_concurrency ?? 5} slots</span>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2 text-[11.5px] font-mono">
              <div className="p-2.5 rounded bg-[#F9FAFB] border border-[#E6E9EF] space-y-0.5">
                <span className="text-slate-400 block text-[10.5px]">PEAK IN-FLIGHT OBSERVED</span>
                <span className="text-slate-800 font-semibold">
                  {metrics ? `${metrics.concurrency.peak_in_flight} concurrent` : '—'}
                </span>
              </div>
              <div className="p-2.5 rounded bg-[#F9FAFB] border border-[#E6E9EF] space-y-0.5">
                <span className="text-slate-400 block text-[10.5px]">ACTIVE SLOTS RESERVED</span>
                <span className="text-slate-800 font-semibold">
                  {metrics ? `${metrics.rate_limits.reserved_rpm} reservations` : '—'}
                </span>
              </div>
            </div>
          </div>
        </Card>
      </div>

      {/* 4. Live Latency Statistics Section */}
      <Card
        title={
          <div className="flex items-center gap-2 font-mono text-xs">
            <Clock className="w-3.5 h-3.5 text-emerald-600" />
            <span>Live Request Latency Distribution</span>
          </div>
        }
        subtitle="Percentile latencies measured across live completed requests"
        action={
          metrics?.latency.available ? (
            <Badge variant="emerald" size="sm">
              Live ({metrics.latency.sample_count} Samples)
            </Badge>
          ) : (
            <Badge variant="neutral" size="sm">
              Awaiting Traffic Samples
            </Badge>
          )
        }
      >
        <div className="space-y-3 text-xs">
          {metrics?.latency.available ? (
            <div className="space-y-3">
              {/* Percentile Cards Grid */}
              <div className="grid grid-cols-3 gap-3">
                <div className="p-3 rounded-lg bg-[#F9FAFB] border border-[#E6E9EF] text-center space-y-1">
                  <span className="text-[11px] font-mono text-slate-500 uppercase font-semibold block">
                    p50 (Median)
                  </span>
                  <div className="text-lg font-bold font-mono text-emerald-600">
                    {metrics.latency.p50_ms !== null ? `${metrics.latency.p50_ms} ms` : '—'}
                  </div>
                  <span className="text-[10px] text-slate-400 font-mono">50th percentile</span>
                </div>

                <div className="p-3 rounded-lg bg-[#F9FAFB] border border-[#E6E9EF] text-center space-y-1">
                  <span className="text-[11px] font-mono text-slate-500 uppercase font-semibold block">
                    p95 Latency
                  </span>
                  <div className="text-lg font-bold font-mono text-sky-600">
                    {metrics.latency.p95_ms !== null ? `${metrics.latency.p95_ms} ms` : '—'}
                  </div>
                  <span className="text-[10px] text-slate-400 font-mono">95th percentile</span>
                </div>

                <div className="p-3 rounded-lg bg-[#F9FAFB] border border-[#E6E9EF] text-center space-y-1">
                  <span className="text-[11px] font-mono text-slate-500 uppercase font-semibold block">
                    p99 Latency
                  </span>
                  <div className="text-lg font-bold font-mono text-indigo-600">
                    {metrics.latency.p99_ms !== null ? `${metrics.latency.p99_ms} ms` : '—'}
                  </div>
                  <span className="text-[10px] text-slate-400 font-mono">99th percentile</span>
                </div>
              </div>

              {/* Secondary Stats Row */}
              <div className="p-3 rounded-lg bg-slate-50 border border-[#E6E9EF] flex flex-wrap items-center justify-between gap-3 text-[11px] font-mono text-slate-600">
                <div>
                  <span className="text-slate-400">Average: </span>
                  <span className="text-slate-800 font-semibold">{metrics.latency.avg_ms ?? '—'} ms</span>
                </div>
                <div>
                  <span className="text-slate-400">Min: </span>
                  <span className="text-slate-800 font-semibold">{metrics.latency.min_ms ?? '—'} ms</span>
                </div>
                <div>
                  <span className="text-slate-400">Max: </span>
                  <span className="text-slate-800 font-semibold">{metrics.latency.max_ms ?? '—'} ms</span>
                </div>
                <div>
                  <span className="text-slate-400">Measurement Scope: </span>
                  <span className="text-slate-800">{metrics.latency.measurement_scope}</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="p-4 rounded-lg bg-[#F9FAFB] border border-[#E6E9EF] space-y-2 text-center py-6">
              <Clock className="w-6 h-6 text-slate-400 mx-auto" />
              <h4 className="text-xs font-semibold text-slate-800 font-mono">
                No Completed Request Latency Samples Yet
              </h4>
              <p className="text-[11.5px] text-slate-500 font-mono max-w-lg mx-auto leading-relaxed">
                Percentile statistics (p50, p95, p99) are computed strictly from real live requests processed by the application since server startup. Submit research questions in the Research Chat tab to populate live telemetry.
              </p>
              <div className="text-[10px] font-mono text-slate-400">
                Scope: Live TrafficManager execution • Not derived from offline experiment CSVs
              </div>
            </div>
          )}
        </div>
      </Card>

      {/* 5. Rate Admission & Sliding Window Limits */}
      <Card
        title={
          <div className="flex items-center gap-2 font-mono text-xs">
            <Zap className="w-3.5 h-3.5 text-amber-600" />
            <span>Local Rate Admission & Token Window (Sliding 60s)</span>
          </div>
        }
        subtitle="Traffic shaping quotas to prevent upstream rate limiting (documented conservative local policies)"
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 text-xs font-mono">
          <div className="p-3 rounded-lg bg-[#F9FAFB] border border-[#E6E9EF] space-y-1">
            <span className="text-[11px] text-slate-500 uppercase font-semibold block">Completed RPM</span>
            <div className="text-base font-bold text-slate-900">
              {metrics ? `${metrics.rate_limits.completed_rpm} reqs` : '—'}
            </div>
            <span className="text-[10px] text-slate-400 block">
              {metrics?.rate_limits.rpm_limit ? `Limit: ${metrics.rate_limits.rpm_limit} RPM` : 'Limit: Unrestricted'}
            </span>
          </div>

          <div className="p-3 rounded-lg bg-[#F9FAFB] border border-[#E6E9EF] space-y-1">
            <span className="text-[11px] text-slate-500 uppercase font-semibold block">Completed TPM</span>
            <div className="text-base font-bold text-slate-900">
              {metrics ? `${metrics.rate_limits.completed_tpm.toLocaleString()} tok` : '—'}
            </div>
            <span className="text-[10px] text-slate-400 block">
              {metrics?.rate_limits.tpm_limit ? `Limit: ${metrics.rate_limits.tpm_limit.toLocaleString()} TPM` : 'Limit: Unrestricted'}
            </span>
          </div>

          <div className="p-3 rounded-lg bg-[#F9FAFB] border border-[#E6E9EF] space-y-1">
            <span className="text-[11px] text-slate-500 uppercase font-semibold block">Reserved RPM</span>
            <div className="text-base font-bold text-amber-600">
              {metrics ? `${metrics.rate_limits.reserved_rpm} slots` : '—'}
            </div>
            <span className="text-[10px] text-slate-400 block">Active in-flight slots</span>
          </div>

          <div className="p-3 rounded-lg bg-[#F9FAFB] border border-[#E6E9EF] space-y-1">
            <span className="text-[11px] text-slate-500 uppercase font-semibold block">Reserved TPM</span>
            <div className="text-base font-bold text-amber-600">
              {metrics ? `${metrics.rate_limits.reserved_tpm.toLocaleString()} tok` : '—'}
            </div>
            <span className="text-[10px] text-slate-400 block">Active prompt reservations</span>
          </div>
        </div>
      </Card>

      {/* 6. Discovered API Endpoints Table */}
      <Card
        title="Discovered API Endpoints"
        subtitle="Contracted HTTP routes exposed by app/api/routes.py"
        padding="none"
      >
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-[#F9FAFB] text-slate-600 border-b border-[#E6E9EF]">
              <tr>
                <th className="px-5 py-3 font-semibold">METHOD</th>
                <th className="px-5 py-3 font-semibold">PATH</th>
                <th className="px-5 py-3 font-semibold">FUNCTION & PURPOSE</th>
                <th className="px-5 py-3 font-semibold">RESPONSE SCHEMA</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E6E9EF] text-slate-700">
              <tr className="hover:bg-slate-50/80 transition-colors">
                <td className="px-5 py-3 font-bold text-sky-600">GET</td>
                <td className="px-5 py-3 text-slate-900 font-semibold">/health</td>
                <td className="px-5 py-3 font-sans text-slate-600">
                  Liveness check for container orchestration
                </td>
                <td className="px-5 py-3 text-slate-500">HealthResponse</td>
              </tr>
              <tr className="hover:bg-slate-50/80 transition-colors">
                <td className="px-5 py-3 font-bold text-sky-600">GET</td>
                <td className="px-5 py-3 text-slate-900 font-semibold">/ready</td>
                <td className="px-5 py-3 font-sans text-slate-600">
                  Readiness probe verifying retriever, traffic manager & workflow
                </td>
                <td className="px-5 py-3 text-slate-500">ReadyResponse</td>
              </tr>
              <tr className="hover:bg-slate-50/80 transition-colors">
                <td className="px-5 py-3 font-bold text-indigo-600">GET</td>
                <td className="px-5 py-3 text-slate-900 font-semibold">/v1/metrics</td>
                <td className="px-5 py-3 font-sans text-slate-600">
                  Live runtime observability: queue, concurrency, throughput, and latency
                </td>
                <td className="px-5 py-3 text-slate-500">MetricsResponse</td>
              </tr>
              <tr className="hover:bg-slate-50/80 transition-colors">
                <td className="px-5 py-3 font-bold text-emerald-600">POST</td>
                <td className="px-5 py-3 text-slate-900 font-semibold">/v1/ask</td>
                <td className="px-5 py-3 font-sans text-slate-600">
                  Execute 8-node LangGraph research workflow with verified citations
                </td>
                <td className="px-5 py-3 text-slate-500">AskResponse</td>
              </tr>
            </tbody>
          </table>
        </div>
      </Card>

      {/* 7. Architecture & Pipeline Card */}
      <Card
        title="Production Architecture Overview"
        subtitle="End-to-end request lifecycle through traffic control, workflow, and retrieval"
      >
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs">
          <div className="p-3.5 rounded-lg bg-[#F9FAFB] border border-[#E6E9EF] space-y-2">
            <div className="flex items-center gap-1.5 text-slate-900 font-semibold font-mono">
              <Server className="w-4 h-4 text-sky-600" />
              <span>1. TrafficManager</span>
            </div>
            <p className="text-slate-600 text-[11.5px] leading-relaxed">
              Enforces semaphore concurrency bounding, sliding-window RPM/TPM admission, bounded FIFO wait queue, and cooperative cancellation safety.
            </p>
          </div>

          <div className="p-3.5 rounded-lg bg-[#F9FAFB] border border-[#E6E9EF] space-y-2">
            <div className="flex items-center gap-1.5 text-slate-900 font-semibold font-mono">
              <Layers className="w-4 h-4 text-indigo-600" />
              <span>2. LangGraph</span>
            </div>
            <p className="text-slate-600 text-[11.5px] leading-relaxed">
              8-node cyclic state graph executing tool calls, deterministic evidence sufficiency gates, answer generation, and a bounded single-attempt correction loop.
            </p>
          </div>

          <div className="p-3.5 rounded-lg bg-[#F9FAFB] border border-[#E6E9EF] space-y-2">
            <div className="flex items-center gap-1.5 text-slate-900 font-semibold font-mono">
              <Database className="w-4 h-4 text-emerald-600" />
              <span>3. Hybrid Retriever</span>
            </div>
            <p className="text-slate-600 text-[11.5px] leading-relaxed">
              Fuses ChromaDB dense semantic vectors (384d), Rank-BM25 sparse keyword indices, and SQLite FactStore tables via Reciprocal Rank Fusion (k=60).
            </p>
          </div>

          <div className="p-3.5 rounded-lg bg-[#F9FAFB] border border-[#E6E9EF] space-y-2">
            <div className="flex items-center gap-1.5 text-slate-900 font-semibold font-mono">
              <ShieldCheck className="w-4 h-4 text-amber-600" />
              <span>4. Verification</span>
            </div>
            <p className="text-slate-600 text-[11.5px] leading-relaxed">
              Verifies arXiv paper IDs, page numbers, and section names against retrieved metadata. Rejects hallucinations and routes to grounded refusals.
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
};
