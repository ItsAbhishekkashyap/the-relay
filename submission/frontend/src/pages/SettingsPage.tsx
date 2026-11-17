import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Sliders,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  Zap,
  ShieldAlert,
  Clock,
  Activity,
  RefreshCw,
  Lock,
  ShieldCheck,
  AlertCircle,
  Trash2,
  Gauge,
  Flame,
  FileCheck,
} from 'lucide-react';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { api, ApiError } from '../services/api';
import type {
  ReadyResponse,
  ConnectionState,
  SimulatorConfigData,
  SimulatorStatusResponse,
} from '../types/api';

interface SettingsPageProps {
  ready: ReadyResponse | null;
  connectionState: ConnectionState;
}

// Stage 4 calibrated baseline defaults
const CALIBRATED_DEFAULTS: SimulatorConfigData = {
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
};

function validateConfig(data: SimulatorConfigData): Record<string, string> {
  const errors: Record<string, string> = {};

  if (isNaN(data.base_delay_ms) || data.base_delay_ms < 0) {
    errors.base_delay_ms = 'Base delay must be ≥ 0 ms';
  }
  if (isNaN(data.jitter_ms) || data.jitter_ms < 0) {
    errors.jitter_ms = 'Jitter must be ≥ 0 ms';
  }
  if (isNaN(data.ttft_ms) || data.ttft_ms < 0) {
    errors.ttft_ms = 'TTFT must be ≥ 0 ms';
  }
  if (isNaN(data.ttft_stddev_ms) || data.ttft_stddev_ms < 0) {
    errors.ttft_stddev_ms = 'TTFT stddev must be ≥ 0 ms';
  }
  if (isNaN(data.inter_chunk_delay_ms) || data.inter_chunk_delay_ms < 0) {
    errors.inter_chunk_delay_ms = 'Inter-chunk delay must be ≥ 0 ms';
  }
  if (isNaN(data.num_stream_chunks) || data.num_stream_chunks < 1) {
    errors.num_stream_chunks = 'Must be at least 1 chunk';
  }
  if (isNaN(data.load_slowdown_factor) || data.load_slowdown_factor < 0) {
    errors.load_slowdown_factor = 'Slowdown factor must be ≥ 0';
  }
  if (isNaN(data.failure_rate) || data.failure_rate < 0 || data.failure_rate > 1.0) {
    errors.failure_rate = 'Failure rate must be between 0.0 and 1.0 (0% - 100%)';
  }
  if (isNaN(data.rpm_limit) || data.rpm_limit < 1) {
    errors.rpm_limit = 'RPM limit must be ≥ 1';
  }
  if (isNaN(data.tpm_limit) || data.tpm_limit < 1) {
    errors.tpm_limit = 'TPM limit must be ≥ 1';
  }
  if (isNaN(data.daily_budget) || data.daily_budget < 1) {
    errors.daily_budget = 'Daily budget must be ≥ 1';
  }
  if (data.daily_token_budget !== null && data.daily_token_budget !== undefined) {
    if (isNaN(data.daily_token_budget) || data.daily_token_budget < 1) {
      errors.daily_token_budget = 'Daily token budget must be ≥ 1';
    }
  }
  if (isNaN(data.max_concurrent_requests) || data.max_concurrent_requests < 1) {
    errors.max_concurrent_requests = 'Max concurrency must be ≥ 1';
  }

  return errors;
}

export const SettingsPage: React.FC<SettingsPageProps> = ({ ready }) => {
  const isSimulatorMode = ready?.provider?.toLowerCase() === 'simulator';

  // State from server
  const [simulatorStatus, setSimulatorStatus] = useState<SimulatorStatusResponse | null>(null);
  const [serverConfig, setServerConfig] = useState<SimulatorConfigData | null>(null);
  const [isSimulatorOnline, setIsSimulatorOnline] = useState<boolean>(true);

  // Form state
  const [formData, setFormData] = useState<SimulatorConfigData>(CALIBRATED_DEFAULTS);
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});

  // Loading & feedback states
  const [isLoadingStatus, setIsLoadingStatus] = useState<boolean>(false);
  const [isApplying, setIsApplying] = useState<boolean>(false);
  const [isResettingConfig, setIsResettingConfig] = useState<boolean>(false);
  const [isResettingState, setIsResettingState] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<{
    type: 'success' | 'error' | 'info';
    message: string;
  } | null>(null);
  const [lastAppliedAt, setLastAppliedAt] = useState<string | null>(null);

  // Modal dialog states
  const [showResetConfigModal, setShowResetConfigModal] = useState<boolean>(false);
  const [showResetStateModal, setShowResetStateModal] = useState<boolean>(false);

  // Fetch current simulator status & configuration
  const fetchSimulatorData = useCallback(async (isInitial = false) => {
    if (!isSimulatorMode) return;
    if (isInitial) setIsLoadingStatus(true);
    try {
      const statusData = await api.getSimulatorStatus();
      setSimulatorStatus(statusData);
      setIsSimulatorOnline(true);

      // Extract config from status if present, or query config endpoint
      if (statusData.config) {
        setServerConfig(statusData.config);
        if (isInitial) {
          setFormData(statusData.config);
        }
      } else {
        const configData = await api.getSimulatorConfig();
        setServerConfig(configData);
        if (isInitial) {
          setFormData(configData);
        }
      }
    } catch (err: unknown) {
      setIsSimulatorOnline(false);
      if (isInitial) {
        setFeedback({
          type: 'error',
          message:
            err instanceof Error
              ? `Unable to connect to simulator: ${err.message}`
              : 'Simulator service is offline at http://127.0.0.1:8001',
        });
      }
    } finally {
      if (isInitial) setIsLoadingStatus(false);
    }
  }, [isSimulatorMode]);

  // Initial load
  useEffect(() => {
    let active = true;
    const run = async () => {
      if (active) {
        await fetchSimulatorData(true);
      }
    };
    void run();
    return () => {
      active = false;
    };
  }, [fetchSimulatorData]);

  // Compute dirty fields
  const dirtyFieldsCount = useMemo(() => {
    if (!serverConfig) return 0;
    let count = 0;
    (Object.keys(formData) as Array<keyof SimulatorConfigData>).forEach((key) => {
      if (formData[key] !== serverConfig[key]) {
        count++;
      }
    });
    return count;
  }, [formData, serverConfig]);

  // Update a single form field
  const updateField = <K extends keyof SimulatorConfigData>(
    field: K,
    value: SimulatorConfigData[K]
  ) => {
    const updated = { ...formData, [field]: value };
    setFormData(updated);

    // Validate
    const errors = validateConfig(updated);
    setValidationErrors(errors);
  };

  // Handle Apply Configuration
  const handleApply = async () => {
    if (!isSimulatorMode) {
      setFeedback({
        type: 'error',
        message: 'Cannot apply simulator settings: active provider is Groq (Cloud LLM).',
      });
      return;
    }

    const errors = validateConfig(formData);
    setValidationErrors(errors);
    if (Object.keys(errors).length > 0) {
      setFeedback({
        type: 'error',
        message: 'Please resolve form validation errors before applying configuration.',
      });
      return;
    }

    setIsApplying(true);
    setFeedback(null);
    try {
      const res = await api.configureSimulator(formData, ready?.provider);
      setServerConfig(res.config);
      setFormData(res.config);
      const nowStr = new Date().toLocaleTimeString();
      setLastAppliedAt(nowStr);
      setFeedback({
        type: 'success',
        message: `Simulator configuration applied successfully at ${nowStr}.`,
      });
      // Refresh status telemetry
      await fetchSimulatorData(false);
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : 'Failed to apply configuration.';
      setFeedback({ type: 'error', message: msg });
    } finally {
      setIsApplying(false);
    }
  };

  // Handle Reset Configuration to Defaults
  const handleConfirmResetConfig = async () => {
    setShowResetConfigModal(false);
    if (!isSimulatorMode) return;

    setIsResettingConfig(true);
    setFeedback(null);
    try {
      const res = await api.resetSimulatorConfig(ready?.provider);
      const newCfg = res.config || CALIBRATED_DEFAULTS;
      setServerConfig(newCfg);
      setFormData(newCfg);
      setValidationErrors({});
      const nowStr = new Date().toLocaleTimeString();
      setLastAppliedAt(nowStr);
      setFeedback({
        type: 'success',
        message: `Configuration reset to Stage 4 calibrated baseline defaults at ${nowStr}.`,
      });
      await fetchSimulatorData(false);
    } catch (err: unknown) {
      // Fallback: apply defaults directly via configure
      try {
        const fallbackRes = await api.configureSimulator(CALIBRATED_DEFAULTS, ready?.provider);
        setServerConfig(fallbackRes.config);
        setFormData(fallbackRes.config);
        setValidationErrors({});
        const nowStr = new Date().toLocaleTimeString();
        setLastAppliedAt(nowStr);
        setFeedback({
          type: 'success',
          message: `Configuration reset to Stage 4 baseline defaults at ${nowStr}.`,
        });
      } catch {
        const msg = err instanceof Error ? err.message : 'Reset failed';
        setFeedback({ type: 'error', message: msg });
      }
    } finally {
      setIsResettingConfig(false);
    }
  };

  // Handle Reset Simulator State (Counters / Sliding Window)
  const handleConfirmResetState = async () => {
    setShowResetStateModal(false);
    if (!isSimulatorMode) return;

    setIsResettingState(true);
    setFeedback(null);
    try {
      await api.resetSimulator(ready?.provider);
      const nowStr = new Date().toLocaleTimeString();
      setFeedback({
        type: 'success',
        message: `Simulator runtime counters, sliding-window rate tracking, and in-flight reservations cleared at ${nowStr}.`,
      });
      await fetchSimulatorData(false);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'State reset failed';
      setFeedback({ type: 'error', message: msg });
    } finally {
      setIsResettingState(false);
    }
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-12">
      {/* Header Banner */}
      <div className="p-5 rounded-xl bg-white border border-[#E6E9EF] shadow-[0_1px_3px_rgba(0,0,0,0.04)] flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2.5 flex-wrap">
            <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <Sliders className="w-5 h-5 text-indigo-600" />
              <span>Simulator Control Center</span>
            </h2>
            <Badge
              variant={isSimulatorMode ? 'purple' : 'amber'}
              size="sm"
            >
              {isSimulatorMode ? 'INTERACTIVE ADMIN MODE' : 'CONTROLS DISABLED (GROQ MODE)'}
            </Badge>
          </div>
          <p className="text-xs text-slate-600 max-w-2xl leading-relaxed">
            Configure the local mock model service parameters (latencies, sliding-window rate limits, fault injection, and concurrency) calibrated from Stage 4 characterization.
          </p>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-center shrink-0">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => fetchSimulatorData(true)}
            isLoading={isLoadingStatus}
            leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
            disabled={!isSimulatorMode}
          >
            Refresh Telemetry
          </Button>
        </div>
      </div>

      {/* Safety & Provider Guard Alert */}
      {!isSimulatorMode && (
        <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 flex items-start gap-3 text-xs leading-relaxed shadow-xs">
          <ShieldAlert className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
          <div className="space-y-1.5">
            <span className="font-semibold text-amber-900 block text-sm">
              Simulator Controls Disabled: Active Provider is GROQ (Cloud LLM API)
            </span>
            <p className="text-amber-800">
              The application is currently connected to the live Groq cloud provider (model: <code className="font-mono text-amber-900 font-semibold">{ready?.model || 'openai/gpt-oss-120b'}</code>). Live cloud LLM endpoints enforce upstream rate limits and latencies that cannot be configured via local simulator admin endpoints.
            </p>
            <p className="text-amber-800">
              To test mock latencies, deterministic faults, and simulated rate-limiting, stop the backend and restart with <code className="font-mono text-amber-900 bg-amber-100/80 px-1.5 py-0.5 rounded border border-amber-300">MODEL_PROVIDER=simulator</code>.
            </p>
          </div>
        </div>
      )}

      {/* Feedback Banner */}
      {feedback && (
        <div
          className={`p-4 rounded-xl border flex items-start justify-between gap-3 text-xs shadow-xs ${
            feedback.type === 'success'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
              : feedback.type === 'error'
              ? 'bg-rose-50 border-rose-200 text-rose-800'
              : 'bg-slate-50 border-slate-200 text-slate-800'
          }`}
        >
          <div className="flex items-center gap-2.5">
            {feedback.type === 'success' && <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />}
            {feedback.type === 'error' && <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />}
            {feedback.type === 'info' && <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />}
            <span className="font-medium">{feedback.message}</span>
          </div>
          <button
            onClick={() => setFeedback(null)}
            className="text-slate-400 hover:text-slate-700 font-mono text-xs px-1 cursor-pointer"
          >
            ✕
          </button>
        </div>
      )}

      {/* Live Telemetry Hero Bar */}
      {isSimulatorMode && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="p-3.5 rounded-xl bg-white border border-[#E6E9EF] shadow-2xs space-y-1">
            <div className="flex items-center justify-between text-slate-500 text-[11px] font-mono uppercase font-semibold">
              <span>Service Health</span>
              <Activity className="w-3.5 h-3.5 text-slate-400" />
            </div>
            <div className="flex items-center gap-2">
              <span
                className={`w-2 h-2 rounded-full ${
                  isSimulatorOnline ? 'bg-emerald-500' : 'bg-rose-500'
                }`}
              />
              <span className="text-sm font-semibold text-slate-900 font-mono">
                {isSimulatorOnline ? 'HEALTHY (:8001)' : 'OFFLINE'}
              </span>
            </div>
          </div>

          <div className="p-3.5 rounded-xl bg-white border border-[#E6E9EF] shadow-2xs space-y-1">
            <div className="flex items-center justify-between text-slate-500 text-[11px] font-mono uppercase font-semibold">
              <span>In-Flight Slots</span>
              <Gauge className="w-3.5 h-3.5 text-slate-400" />
            </div>
            <div className="text-sm font-semibold text-slate-900 font-mono">
              {simulatorStatus ? `${simulatorStatus.in_flight_requests} / ${formData.max_concurrent_requests}` : '0 / 10'}
            </div>
          </div>

          <div className="p-3.5 rounded-xl bg-white border border-[#E6E9EF] shadow-2xs space-y-1">
            <div className="flex items-center justify-between text-slate-500 text-[11px] font-mono uppercase font-semibold">
              <span>Current Window (60s)</span>
              <Clock className="w-3.5 h-3.5 text-slate-400" />
            </div>
            <div className="text-sm font-semibold text-slate-900 font-mono truncate">
              {simulatorStatus
                ? `${simulatorStatus.current_window.rpm_usage} RPM · ${simulatorStatus.current_window.tpm_usage.toLocaleString()} TPM`
                : '0 RPM · 0 TPM'}
            </div>
          </div>

          <div className="p-3.5 rounded-xl bg-white border border-[#E6E9EF] shadow-2xs space-y-1">
            <div className="flex items-center justify-between text-slate-500 text-[11px] font-mono uppercase font-semibold">
              <span>Daily Requests</span>
              <Zap className="w-3.5 h-3.5 text-slate-400" />
            </div>
            <div className="text-sm font-semibold text-slate-900 font-mono truncate">
              {simulatorStatus
                ? `${simulatorStatus.daily_request_usage.requests_used} / ${simulatorStatus.daily_request_usage.budget}`
                : '0 / 1,000'}
            </div>
          </div>
        </div>
      )}

      {/* Main Configuration Tabs/Cards */}
      <fieldset disabled={!isSimulatorMode || !isSimulatorOnline} className="space-y-6">
        {/* SECTION 1: Latency & Response Timing */}
        <Card
          title={
            <div className="flex items-center gap-2">
              <Clock className="w-4 h-4 text-indigo-600" />
              <span>Response Latency & Streaming Parameters</span>
            </div>
          }
          subtitle="Calibrated from Stage 4 real Groq empirical measurements (976.5ms non-streaming median, 852.0ms TTFT)"
          action={
            <Badge variant="purple" size="sm">
              STAGE 4 CALIBRATED
            </Badge>
          }
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5 text-xs">
            {/* Base Delay */}
            <div className="space-y-1.5">
              <div className="flex justify-between items-center">
                <label className="font-semibold text-slate-900">
                  Base Artificial Delay (ms)
                </label>
                <span className="font-mono text-indigo-600 font-semibold">
                  {formData.base_delay_ms} ms
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="4000"
                step="10"
                value={formData.base_delay_ms}
                onChange={(e) => updateField('base_delay_ms', parseFloat(e.target.value) || 0)}
                className="w-full accent-indigo-600 bg-slate-200 rounded h-1.5 cursor-pointer"
              />
              <div className="flex items-center justify-between text-[11px] text-slate-400">
                <span>Fast (0 ms)</span>
                <span>Calibrated: 976.5 ms</span>
                <span>Slow (4,000 ms)</span>
              </div>
              {validationErrors.base_delay_ms && (
                <span className="text-[11px] text-rose-600 font-mono">{validationErrors.base_delay_ms}</span>
              )}
            </div>

            {/* Jitter */}
            <div className="space-y-1.5">
              <div className="flex justify-between items-center">
                <label className="font-semibold text-slate-900">
                  Latency Jitter / StdDev (ms)
                </label>
                <span className="font-mono text-indigo-600 font-semibold">
                  ± {formData.jitter_ms} ms
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="800"
                step="5"
                value={formData.jitter_ms}
                onChange={(e) => updateField('jitter_ms', parseFloat(e.target.value) || 0)}
                className="w-full accent-indigo-600 bg-slate-200 rounded h-1.5 cursor-pointer"
              />
              <div className="flex items-center justify-between text-[11px] text-slate-400">
                <span>Deterministic (0 ms)</span>
                <span>Calibrated: 174.0 ms</span>
                <span>High Jitter (800 ms)</span>
              </div>
              {validationErrors.jitter_ms && (
                <span className="text-[11px] text-rose-600 font-mono">{validationErrors.jitter_ms}</span>
              )}
            </div>

            {/* TTFT Delay */}
            <div className="space-y-1.5">
              <div className="flex justify-between items-center">
                <label className="font-semibold text-slate-900">
                  Streaming Time to First Token (TTFT)
                </label>
                <span className="font-mono text-indigo-600 font-semibold">
                  {formData.ttft_ms} ms
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="3000"
                step="10"
                value={formData.ttft_ms}
                onChange={(e) => updateField('ttft_ms', parseFloat(e.target.value) || 0)}
                className="w-full accent-indigo-600 bg-slate-200 rounded h-1.5 cursor-pointer"
              />
              <div className="flex items-center justify-between text-[11px] text-slate-400">
                <span>Instant (0 ms)</span>
                <span>Calibrated: 852.0 ms</span>
                <span>Slow (3,000 ms)</span>
              </div>
              {validationErrors.ttft_ms && (
                <span className="text-[11px] text-rose-600 font-mono">{validationErrors.ttft_ms}</span>
              )}
            </div>

            {/* Inter-Chunk Delay */}
            <div className="space-y-1.5">
              <div className="flex justify-between items-center">
                <label className="font-semibold text-slate-900">
                  Streaming Inter-Chunk Delay
                </label>
                <span className="font-mono text-indigo-600 font-semibold">
                  {formData.inter_chunk_delay_ms} ms
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                step="1"
                value={formData.inter_chunk_delay_ms}
                onChange={(e) => updateField('inter_chunk_delay_ms', parseFloat(e.target.value) || 0)}
                className="w-full accent-indigo-600 bg-slate-200 rounded h-1.5 cursor-pointer"
              />
              <div className="flex items-center justify-between text-[11px] text-slate-400">
                <span>Instant (0 ms)</span>
                <span>Calibrated: 20.0 ms</span>
                <span>Slow (100 ms)</span>
              </div>
              {validationErrors.inter_chunk_delay_ms && (
                <span className="text-[11px] text-rose-600 font-mono">{validationErrors.inter_chunk_delay_ms}</span>
              )}
            </div>

            {/* Distribution & Chunks */}
            <div className="grid grid-cols-2 gap-3 pt-1">
              <div className="space-y-1">
                <label className="font-semibold text-slate-900 text-[11px]">
                  Latency Distribution
                </label>
                <select
                  value={formData.latency_distribution}
                  onChange={(e) => updateField('latency_distribution', e.target.value)}
                  className="w-full bg-white border border-slate-300 rounded-lg px-2.5 py-1.5 text-slate-800 text-xs font-mono focus:outline-none focus:border-indigo-500"
                >
                  <option value="lognormal">lognormal (Stage 4 fit)</option>
                  <option value="normal">normal (Gaussian)</option>
                  <option value="uniform">uniform (flat)</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="font-semibold text-slate-900 text-[11px]">
                  Stream Chunks Count
                </label>
                <input
                  type="number"
                  min="1"
                  max="32"
                  value={formData.num_stream_chunks}
                  onChange={(e) => updateField('num_stream_chunks', parseInt(e.target.value, 10) || 1)}
                  className="w-full bg-white border border-slate-300 rounded-lg px-2.5 py-1.5 text-slate-800 text-xs font-mono focus:outline-none focus:border-indigo-500"
                />
              </div>
            </div>

            {/* Load Slowdown Factor */}
            <div className="space-y-1.5 pt-1">
              <div className="flex justify-between items-center">
                <label className="font-semibold text-slate-900 text-[11px]">
                  Concurrency Contention Slowdown
                </label>
                <span className="font-mono text-indigo-600 font-semibold text-[11px]">
                  +{(formData.load_slowdown_factor * 100).toFixed(0)}% / concurrent request
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="0.25"
                step="0.01"
                value={formData.load_slowdown_factor}
                onChange={(e) => updateField('load_slowdown_factor', parseFloat(e.target.value) || 0)}
                className="w-full accent-indigo-600 bg-slate-200 rounded h-1.5 cursor-pointer"
              />
            </div>
          </div>
        </Card>

        {/* SECTION 2: Fault Injection & Reliability */}
        <Card
          title={
            <div className="flex items-center gap-2">
              <Flame className="w-4 h-4 text-rose-600" />
              <span>Fault Injection & Resilience Testing</span>
            </div>
          }
          subtitle="Inject transient random failures or forced deterministic HTTP error modes to test TrafficManager retries"
          action={
            formData.failure_rate > 0 || formData.deterministic_failure ? (
              <Badge variant="rose" size="sm">
                FAULTS ACTIVE
              </Badge>
            ) : (
              <Badge variant="emerald" size="sm">
                0% FAULTS
              </Badge>
            )
          }
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5 text-xs">
            {/* Random Failure Rate */}
            <div className="space-y-1.5">
              <div className="flex justify-between items-center">
                <label className="font-semibold text-slate-900">
                  Transient Failure Probability (500 Error)
                </label>
                <span
                  className={`font-mono font-semibold ${
                    formData.failure_rate > 0 ? 'text-rose-600' : 'text-slate-500'
                  }`}
                >
                  {(formData.failure_rate * 100).toFixed(1)}%
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="1.0"
                step="0.05"
                value={formData.failure_rate}
                onChange={(e) => updateField('failure_rate', parseFloat(e.target.value) || 0)}
                className="w-full accent-rose-600 bg-slate-200 rounded h-1.5 cursor-pointer"
              />
              <div className="flex items-center justify-between text-[11px] text-slate-400">
                <span>0% (Reliable)</span>
                <span>25%</span>
                <span>50%</span>
                <span>100% (All Fail)</span>
              </div>
            </div>

            {/* Deterministic Failure Mode */}
            <div className="space-y-1.5">
              <label className="font-semibold text-slate-900 block">
                Deterministic Forced Failure Mode
              </label>
              <select
                value={formData.deterministic_failure || ''}
                onChange={(e) => updateField('deterministic_failure', e.target.value || null)}
                className={`w-full border rounded-lg px-3 py-2 text-xs font-mono focus:outline-none ${
                  formData.deterministic_failure
                    ? 'border-rose-300 text-rose-800 bg-rose-50'
                    : 'border-slate-300 text-slate-800 bg-white'
                }`}
              >
                <option value="">None (Normal Execution)</option>
                <option value="rate_limit">rate_limit — HTTP 429 Rate Limit Exceeded</option>
                <option value="server_error">server_error — HTTP 500 Internal Server Error</option>
                <option value="timeout">timeout — HTTP 504 Gateway Timeout</option>
                <option value="auth_error">auth_error — HTTP 401 Authentication Failure</option>
                <option value="overload">overload — HTTP 429 Concurrency Overload</option>
              </select>
              <p className="text-[11px] text-slate-500 leading-relaxed font-sans">
                When active, every completion request immediately raises the specified error to test client-side retry logic and error surfacing.
              </p>
            </div>
          </div>
        </Card>

        {/* SECTION 3: Rate Limiting & Concurrency Quotas */}
        <Card
          title={
            <div className="flex items-center gap-2">
              <Gauge className="w-4 h-4 text-sky-600" />
              <span>Rate Limits & Admission Quotas</span>
            </div>
          }
          subtitle="Configure sliding-window RPM, TPM, daily limits, and concurrency ceilings"
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 text-xs">
            {/* RPM Limit */}
            <div className="p-3 rounded-lg bg-[#F9FAFB] border border-[#E6E9EF] space-y-1">
              <label className="font-semibold text-slate-900 block text-[11px] uppercase tracking-wide">
                Sliding RPM Limit
              </label>
              <input
                type="number"
                min="1"
                max="1000"
                value={formData.rpm_limit}
                onChange={(e) => updateField('rpm_limit', parseInt(e.target.value, 10) || 1)}
                className="w-full bg-white border border-slate-300 rounded px-2.5 py-1.5 font-mono text-slate-900 text-sm focus:outline-none focus:border-indigo-500"
              />
              <span className="text-[10.5px] text-slate-400 block font-sans">
                Stage 4 Calibrated: 30 RPM
              </span>
              {validationErrors.rpm_limit && (
                <span className="text-[10.5px] text-rose-600 block">{validationErrors.rpm_limit}</span>
              )}
            </div>

            {/* TPM Limit */}
            <div className="p-3 rounded-lg bg-[#F9FAFB] border border-[#E6E9EF] space-y-1">
              <label className="font-semibold text-slate-900 block text-[11px] uppercase tracking-wide">
                Sliding TPM Limit
              </label>
              <input
                type="number"
                min="100"
                max="100000"
                step="500"
                value={formData.tpm_limit}
                onChange={(e) => updateField('tpm_limit', parseInt(e.target.value, 10) || 100)}
                className="w-full bg-white border border-slate-300 rounded px-2.5 py-1.5 font-mono text-slate-900 text-sm focus:outline-none focus:border-indigo-500"
              />
              <span className="text-[10.5px] text-slate-400 block font-sans">
                Stage 4 Calibrated: 8,000 TPM
              </span>
              {validationErrors.tpm_limit && (
                <span className="text-[10.5px] text-rose-600 block">{validationErrors.tpm_limit}</span>
              )}
            </div>

            {/* Max Concurrency */}
            <div className="p-3 rounded-lg bg-[#F9FAFB] border border-[#E6E9EF] space-y-1">
              <label className="font-semibold text-slate-900 block text-[11px] uppercase tracking-wide">
                Max Concurrency
              </label>
              <input
                type="number"
                min="1"
                max="50"
                value={formData.max_concurrent_requests}
                onChange={(e) => updateField('max_concurrent_requests', parseInt(e.target.value, 10) || 1)}
                className="w-full bg-white border border-slate-300 rounded px-2.5 py-1.5 font-mono text-slate-900 text-sm focus:outline-none focus:border-indigo-500"
              />
              <span className="text-[10.5px] text-slate-400 block font-sans">
                Simulator in-flight ceiling: 10
              </span>
              {validationErrors.max_concurrent_requests && (
                <span className="text-[10.5px] text-rose-600 block">{validationErrors.max_concurrent_requests}</span>
              )}
            </div>

            {/* Daily Request Budget */}
            <div className="p-3 rounded-lg bg-[#F9FAFB] border border-[#E6E9EF] space-y-1">
              <label className="font-semibold text-slate-900 block text-[11px] uppercase tracking-wide">
                Daily Request Budget
              </label>
              <input
                type="number"
                min="10"
                max="50000"
                step="100"
                value={formData.daily_budget}
                onChange={(e) => updateField('daily_budget', parseInt(e.target.value, 10) || 10)}
                className="w-full bg-white border border-slate-300 rounded px-2.5 py-1.5 font-mono text-slate-900 text-sm focus:outline-none focus:border-indigo-500"
              />
              <span className="text-[10.5px] text-slate-400 block font-sans">
                Standard: 1,000 RPD
              </span>
            </div>

            {/* Daily Token Budget */}
            <div className="p-3 rounded-lg bg-[#F9FAFB] border border-[#E6E9EF] space-y-1">
              <label className="font-semibold text-slate-900 block text-[11px] uppercase tracking-wide">
                Daily Token Budget
              </label>
              <input
                type="number"
                min="1000"
                max="2000000"
                step="50000"
                value={formData.daily_token_budget || ''}
                onChange={(e) =>
                  updateField(
                    'daily_token_budget',
                    e.target.value ? parseInt(e.target.value, 10) : null
                  )
                }
                placeholder="Unlimited"
                className="w-full bg-white border border-slate-300 rounded px-2.5 py-1.5 font-mono text-slate-900 text-sm focus:outline-none focus:border-indigo-500"
              />
              <span className="text-[10.5px] text-slate-400 block font-sans">
                Standard: 200,000 TPD
              </span>
            </div>

            {/* Retry-After Override */}
            <div className="p-3 rounded-lg bg-[#F9FAFB] border border-[#E6E9EF] space-y-1">
              <label className="font-semibold text-slate-900 block text-[11px] uppercase tracking-wide">
                Retry-After Override (sec)
              </label>
              <input
                type="number"
                min="0"
                max="120"
                step="0.5"
                value={formData.retry_after_seconds ?? ''}
                onChange={(e) =>
                  updateField(
                    'retry_after_seconds',
                    e.target.value !== '' ? parseFloat(e.target.value) : null
                  )
                }
                placeholder="Auto-computed"
                className="w-full bg-white border border-slate-300 rounded px-2.5 py-1.5 font-mono text-slate-900 text-sm focus:outline-none focus:border-indigo-500"
              />
              <span className="text-[10.5px] text-slate-400 block font-sans">
                Empty = sliding window delta
              </span>
            </div>
          </div>
        </Card>

        {/* Action Bar */}
        <div className="p-4 rounded-xl bg-white border border-[#E6E9EF] shadow-xs flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            {dirtyFieldsCount > 0 ? (
              <div className="flex items-center gap-2 text-amber-700 text-xs font-mono font-medium">
                <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
                <span>{dirtyFieldsCount} unsaved configuration change(s)</span>
              </div>
            ) : (
              <div className="flex items-center gap-2 text-slate-500 text-xs font-mono">
                <FileCheck className="w-3.5 h-3.5 text-emerald-600" />
                <span>Configuration in sync with server</span>
                {lastAppliedAt && <span>(last updated {lastAppliedAt})</span>}
              </div>
            )}
          </div>

          <div className="flex items-center gap-2.5 flex-wrap justify-end">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowResetConfigModal(true)}
              disabled={isApplying || isResettingConfig}
              leftIcon={<RotateCcw className="w-3.5 h-3.5" />}
            >
              Reset to Defaults
            </Button>

            <Button
              variant="danger"
              size="sm"
              onClick={() => setShowResetStateModal(true)}
              disabled={isApplying || isResettingState}
              leftIcon={<Trash2 className="w-3.5 h-3.5" />}
            >
              Reset Counters / State
            </Button>

            <Button
              variant="primary"
              size="sm"
              onClick={handleApply}
              isLoading={isApplying}
              disabled={
                dirtyFieldsCount === 0 ||
                Object.keys(validationErrors).length > 0 ||
                !isSimulatorOnline
              }
              leftIcon={<CheckCircle2 className="w-3.5 h-3.5" />}
            >
              Apply Configuration
            </Button>
          </div>
        </div>
      </fieldset>

      {/* Lifetime Metrics Summary */}
      {isSimulatorMode && simulatorStatus && (
        <Card
          title="Simulator Lifetime Observability Counters"
          subtitle="Point-in-time runtime metrics tracked in SimulatorService memory"
        >
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3 text-center font-mono text-xs">
            <div className="p-3 rounded-lg bg-[#F9FAFB] border border-[#E6E9EF]">
              <span className="text-[10px] text-slate-400 block uppercase font-semibold">Total Handled</span>
              <span className="text-base font-bold text-slate-900">
                {simulatorStatus.lifetime_metrics.total_handled}
              </span>
            </div>
            <div className="p-3 rounded-lg bg-[#F9FAFB] border border-[#E6E9EF]">
              <span className="text-[10px] text-slate-400 block uppercase font-semibold">Successes</span>
              <span className="text-base font-bold text-emerald-600">
                {simulatorStatus.lifetime_metrics.successes}
              </span>
            </div>
            <div className="p-3 rounded-lg bg-[#F9FAFB] border border-[#E6E9EF]">
              <span className="text-[10px] text-slate-400 block uppercase font-semibold">Failures (500)</span>
              <span className="text-base font-bold text-rose-600">
                {simulatorStatus.lifetime_metrics.failures}
              </span>
            </div>
            <div className="p-3 rounded-lg bg-[#F9FAFB] border border-[#E6E9EF]">
              <span className="text-[10px] text-slate-400 block uppercase font-semibold">Rate Limits (429)</span>
              <span className="text-base font-bold text-amber-600">
                {simulatorStatus.lifetime_metrics.rate_limit_hits}
              </span>
            </div>
            <div className="p-3 rounded-lg bg-[#F9FAFB] border border-[#E6E9EF]">
              <span className="text-[10px] text-slate-400 block uppercase font-semibold">Overload Hits</span>
              <span className="text-base font-bold text-rose-700">
                {simulatorStatus.lifetime_metrics.overload_hits}
              </span>
            </div>
            <div className="p-3 rounded-lg bg-[#F9FAFB] border border-[#E6E9EF]">
              <span className="text-[10px] text-slate-400 block uppercase font-semibold">Cancellations</span>
              <span className="text-base font-bold text-slate-600">
                {simulatorStatus.lifetime_metrics.client_cancellations}
              </span>
            </div>
          </div>
        </Card>
      )}

      {/* Security & Secret Handling Notice */}
      <Card
        title={
          <div className="flex items-center gap-2">
            <Lock className="w-4 h-4 text-emerald-600" />
            <span>Zero-Credential Architecture & Guardrails</span>
          </div>
        }
        subtitle="Frontend client security principles and provider safety"
      >
        <div className="p-3.5 rounded-lg bg-indigo-50/40 border border-indigo-100 text-xs text-slate-700 space-y-2 leading-relaxed">
          <div className="flex items-center gap-2 text-indigo-700 font-semibold font-mono text-xs">
            <ShieldCheck className="w-4 h-4" />
            <span>PROVIDER PROTECTION ACTIVE</span>
          </div>
          <p className="text-slate-600 text-[11.5px] font-sans">
            API keys (including <code className="text-slate-800 font-mono bg-white px-1 py-0.5 rounded border border-indigo-200">GROQ_API_KEY</code>) are stored exclusively in the server environment (<code className="text-slate-800 font-mono bg-white px-1 py-0.5 rounded border border-indigo-200">.env</code>) and are never embedded, serialized, or transmitted to the browser client. Simulator configuration requests are strictly isolated and never transmitted to external cloud providers.
          </p>
        </div>
      </Card>

      {/* Confirmation Modal: Reset Configuration to Baseline Defaults */}
      {showResetConfigModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4">
          <div className="bg-white border border-[#E6E9EF] rounded-xl max-w-md w-full p-5 space-y-4 shadow-xl">
            <div className="flex items-start gap-3">
              <RotateCcw className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
              <div>
                <h3 className="text-sm font-bold text-slate-900">
                  Reset Simulator Configuration to Baseline Defaults?
                </h3>
                <p className="text-xs text-slate-600 mt-1 leading-relaxed font-sans">
                  This will restore all latency distributions, sliding-window rate limits (30 RPM, 8,000 TPM), and zero fault injection back to the Stage 4 calibrated baseline.
                </p>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2.5 pt-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowResetConfigModal(false)}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleConfirmResetConfig}
                isLoading={isResettingConfig}
              >
                Confirm Reset Defaults
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Confirmation Modal: Reset Runtime Counters & State */}
      {showResetStateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4">
          <div className="bg-white border border-[#E6E9EF] rounded-xl max-w-md w-full p-5 space-y-4 shadow-xl">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
              <div>
                <h3 className="text-sm font-bold text-slate-900">
                  Reset Simulator Runtime Counters & State?
                </h3>
                <p className="text-xs text-slate-600 mt-1 leading-relaxed font-sans">
                  This will discard active in-flight request reservations, wipe the 60-second sliding rate window deques, and reset daily token usage counters to 0. Existing configuration parameters will be preserved.
                </p>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2.5 pt-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowResetStateModal(false)}
              >
                Cancel
              </Button>
              <Button
                variant="danger"
                size="sm"
                onClick={handleConfirmResetState}
                isLoading={isResettingState}
              >
                Confirm Reset State
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
