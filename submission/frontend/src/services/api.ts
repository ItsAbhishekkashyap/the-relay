import { ENV } from '../config/env.ts';
import type {
  HealthResponse,
  ReadyResponse,
  AskRequest,
  AskResponse,
  MetricsResponse,
  SimulatorConfigData,
  SimulatorStatusResponse,
  SimulatorConfigureResponse,
  SimulatorResetResponse,
  ExperimentsOverviewResponse,
  LoadExperimentsResponse,
  RetrievalExperimentsResponse,
} from '../types/api.ts';

export class ApiError extends Error {
  status?: number;
  data?: unknown;

  constructor(message: string, status?: number, data?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

/**
 * Fetch helper with automatic AbortController timeout and optional external signal.
 */
async function fetchWithTimeout(
  url: string,
  options: RequestInit = {},
  timeoutMs: number = ENV.requestTimeoutMs,
  externalSignal?: AbortSignal
): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  // Link external signal if provided
  const onExternalAbort = () => controller.abort();
  if (externalSignal) {
    if (externalSignal.aborted) {
      clearTimeout(timeoutId);
      controller.abort();
    } else {
      externalSignal.addEventListener('abort', onExternalAbort, { once: true });
    }
  }

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
    });
    return response;
  } catch (error: unknown) {
    if (error instanceof Error && error.name === 'AbortError') {
      if (externalSignal?.aborted) {
        throw new ApiError('Request was canceled by user', 499);
      }
      throw new ApiError(`Request timed out after ${Math.round(timeoutMs / 1000)}s`, 504);
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
    if (externalSignal) {
      externalSignal.removeEventListener('abort', onExternalAbort);
    }
  }
}

/**
 * Extract human-readable error detail from a FastAPI error response.
 */
function extractErrorDetail(errorData: unknown, fallbackStatus: number): string {
  if (typeof errorData === 'object' && errorData !== null) {
    const errObj = errorData as Record<string, unknown>;
    if (typeof errObj.detail === 'string') {
      return errObj.detail;
    }
    if (Array.isArray(errObj.detail)) {
      // Pydantic validation error array
      const first = errObj.detail[0];
      if (first && typeof first === 'object' && 'msg' in first) {
        return String(first.msg);
      }
    }
    if (errObj.detail && typeof errObj.detail === 'object') {
      return JSON.stringify(errObj.detail);
    }
  }
  return `HTTP ${fallbackStatus} request failed`;
}

/**
 * API service for interacting with The Relay FastAPI backend.
 */
export const api = {
  /**
   * Check basic service health (/health).
   */
  async getHealth(): Promise<HealthResponse> {
    const url = `${ENV.apiBaseUrl}/health`;
    try {
      const response = await fetchWithTimeout(url, {
        headers: { Accept: 'application/json' },
      });

      if (!response.ok) {
        throw new ApiError(
          `Health check failed with HTTP ${response.status}`,
          response.status
        );
      }

      const data: HealthResponse = await response.json();
      return data;
    } catch (error: unknown) {
      if (error instanceof ApiError) throw error;
      const message = error instanceof Error ? error.message : 'Unknown network error';
      throw new ApiError(`Unable to connect to backend: ${message}`);
    }
  },

  /**
   * Check component readiness (/ready).
   */
  async getReady(): Promise<ReadyResponse> {
    const url = `${ENV.apiBaseUrl}/ready`;
    try {
      const response = await fetchWithTimeout(url, {
        headers: { Accept: 'application/json' },
      });

      if (!response.ok) {
        let errorBody: unknown;
        try {
          errorBody = await response.json();
        } catch {
          // Ignore JSON parse errors on failure responses
        }
        throw new ApiError(
          `Readiness check failed with HTTP ${response.status}`,
          response.status,
          errorBody
        );
      }

      const data: ReadyResponse = await response.json();
      return data;
    } catch (error: unknown) {
      if (error instanceof ApiError) throw error;
      const message = error instanceof Error ? error.message : 'Unknown network error';
      throw new ApiError(`Readiness probe failed: ${message}`);
    }
  },

  /**
   * Fetch live system operational metrics (/v1/metrics).
   */
  async getMetrics(externalSignal?: AbortSignal): Promise<MetricsResponse> {
    const url = `${ENV.apiBaseUrl}/v1/metrics`;
    try {
      const response = await fetchWithTimeout(
        url,
        { headers: { Accept: 'application/json' } },
        ENV.requestTimeoutMs,
        externalSignal
      );
      if (!response.ok) {
        throw new ApiError(
          `Metrics fetch failed with HTTP ${response.status}`,
          response.status
        );
      }
      const data: MetricsResponse = await response.json();
      return data;
    } catch (error: unknown) {
      if (error instanceof ApiError) throw error;
      const message = error instanceof Error ? error.message : 'Unknown network error';
      throw new ApiError(`Metrics request failed: ${message}`);
    }
  },

  /**
   * Submit research question to /v1/ask.
   */
  async askQuestion(
    req: AskRequest,
    externalSignal?: AbortSignal
  ): Promise<AskResponse> {
    const url = `${ENV.apiBaseUrl}/v1/ask`;

    const body: Record<string, unknown> = {
      question: req.question.trim(),
    };
    if (req.paper_filter) {
      body.paper_filter = req.paper_filter.trim();
    }

    try {
      const response = await fetchWithTimeout(
        url,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'application/json',
          },
          body: JSON.stringify(body),
        },
        ENV.askTimeoutMs,
        externalSignal
      );

      if (!response.ok) {
        let errorData: unknown;
        try {
          errorData = await response.json();
        } catch {
          // Non-JSON error response
        }

        const detailMsg = extractErrorDetail(errorData, response.status);

        if (response.status === 400) {
          throw new ApiError(`Invalid request: ${detailMsg}`, 400, errorData);
        } else if (response.status === 422) {
          throw new ApiError(`Validation error: ${detailMsg}`, 422, errorData);
        } else if (response.status === 429) {
          throw new ApiError(`Rate limit reached: ${detailMsg}`, 429, errorData);
        } else if (response.status === 502) {
          throw new ApiError(`Upstream model provider error: ${detailMsg}`, 502, errorData);
        } else if (response.status === 503) {
          throw new ApiError(`Service unavailable: ${detailMsg}`, 503, errorData);
        } else if (response.status === 504) {
          throw new ApiError(`Processing timeout: ${detailMsg}`, 504, errorData);
        } else {
          throw new ApiError(`Server error (${response.status}): ${detailMsg}`, response.status, errorData);
        }
      }

      const data: AskResponse = await response.json();
      return data;
    } catch (error: unknown) {
      if (error instanceof ApiError) throw error;
      const message = error instanceof Error ? error.message : 'Unknown network error';
      throw new ApiError(`Connection failed: ${message}`);
    }
  },

  /**
   * Fetch live simulator status, active requests, and limits (/simulator/status).
   */
  async getSimulatorStatus(externalSignal?: AbortSignal): Promise<SimulatorStatusResponse> {
    const url = `${ENV.apiBaseUrl}/simulator/status`;
    try {
      const response = await fetchWithTimeout(
        url,
        { headers: { Accept: 'application/json' } },
        ENV.requestTimeoutMs,
        externalSignal
      );
      if (!response.ok) {
        throw new ApiError(
          `Simulator status probe failed with HTTP ${response.status}`,
          response.status
        );
      }
      const data: SimulatorStatusResponse = await response.json();
      return data;
    } catch (error: unknown) {
      if (error instanceof ApiError) throw error;
      const message = error instanceof Error ? error.message : 'Unknown network error';
      throw new ApiError(`Unable to reach simulator service: ${message}`);
    }
  },

  /**
   * Fetch current simulator configuration (/simulator/admin/config).
   */
  async getSimulatorConfig(externalSignal?: AbortSignal): Promise<SimulatorConfigData> {
    const url = `${ENV.apiBaseUrl}/simulator/admin/config`;
    try {
      const response = await fetchWithTimeout(
        url,
        { headers: { Accept: 'application/json' } },
        ENV.requestTimeoutMs,
        externalSignal
      );
      if (!response.ok) {
        throw new ApiError(
          `Simulator config fetch failed with HTTP ${response.status}`,
          response.status
        );
      }
      const data: SimulatorConfigData = await response.json();
      return data;
    } catch (error: unknown) {
      if (error instanceof ApiError) throw error;
      const message = error instanceof Error ? error.message : 'Unknown network error';
      throw new ApiError(`Unable to fetch simulator configuration: ${message}`);
    }
  },

  /**
   * Dynamically update simulator runtime configuration (/simulator/admin/configure).
   * Guards against updating when active provider is not 'simulator'.
   */
  async configureSimulator(
    updates: Partial<SimulatorConfigData>,
    activeProvider?: string,
    externalSignal?: AbortSignal
  ): Promise<SimulatorConfigureResponse> {
    if (activeProvider && activeProvider.toLowerCase() !== 'simulator') {
      throw new ApiError(
        'Simulator controls disabled: active provider is Groq (Cloud LLM API). Configuration requests cannot be sent to external providers.',
        403
      );
    }

    const url = `${ENV.apiBaseUrl}/simulator/admin/configure`;
    try {
      const response = await fetchWithTimeout(
        url,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'application/json',
          },
          body: JSON.stringify(updates),
        },
        ENV.requestTimeoutMs,
        externalSignal
      );

      if (!response.ok) {
        let errorData: unknown;
        try {
          errorData = await response.json();
        } catch {
          // ignore
        }
        const msg = extractErrorDetail(errorData, response.status);
        throw new ApiError(`Simulator configuration rejected: ${msg}`, response.status, errorData);
      }

      const data: SimulatorConfigureResponse = await response.json();
      return data;
    } catch (error: unknown) {
      if (error instanceof ApiError) throw error;
      const message = error instanceof Error ? error.message : 'Unknown network error';
      throw new ApiError(`Failed to update simulator configuration: ${message}`);
    }
  },

  /**
   * Reset simulator counters, in-flight reservations, and sliding window state (/simulator/admin/reset).
   */
  async resetSimulator(
    activeProvider?: string,
    externalSignal?: AbortSignal
  ): Promise<SimulatorResetResponse> {
    if (activeProvider && activeProvider.toLowerCase() !== 'simulator') {
      throw new ApiError(
        'Simulator reset disabled: active provider is Groq (Cloud LLM API).',
        403
      );
    }

    const url = `${ENV.apiBaseUrl}/simulator/admin/reset`;
    try {
      const response = await fetchWithTimeout(
        url,
        {
          method: 'POST',
          headers: { Accept: 'application/json' },
        },
        ENV.requestTimeoutMs,
        externalSignal
      );

      if (!response.ok) {
        throw new ApiError(
          `Simulator reset failed with HTTP ${response.status}`,
          response.status
        );
      }

      const data: SimulatorResetResponse = await response.json();
      return data;
    } catch (error: unknown) {
      if (error instanceof ApiError) throw error;
      const message = error instanceof Error ? error.message : 'Unknown network error';
      throw new ApiError(`Failed to reset simulator: ${message}`);
    }
  },

  /**
   * Reset simulator configuration parameters to default calibrated values (/simulator/admin/reset-config).
   */
  async resetSimulatorConfig(
    activeProvider?: string,
    externalSignal?: AbortSignal
  ): Promise<SimulatorResetResponse> {
    if (activeProvider && activeProvider.toLowerCase() !== 'simulator') {
      throw new ApiError(
        'Simulator configuration reset disabled: active provider is Groq (Cloud LLM API).',
        403
      );
    }

    const url = `${ENV.apiBaseUrl}/simulator/admin/reset-config`;
    try {
      const response = await fetchWithTimeout(
        url,
        {
          method: 'POST',
          headers: { Accept: 'application/json' },
        },
        ENV.requestTimeoutMs,
        externalSignal
      );

      if (!response.ok) {
        throw new ApiError(
          `Simulator config reset failed with HTTP ${response.status}`,
          response.status
        );
      }

      const data: SimulatorResetResponse = await response.json();
      return data;
    } catch (error: unknown) {
      if (error instanceof ApiError) throw error;
      const message = error instanceof Error ? error.message : 'Unknown network error';
      throw new ApiError(`Failed to reset simulator configuration: ${message}`);
    }
  },

  /**
   * Get point-in-time catalog of available empirical experiment datasets (/v1/experiments/overview).
   */
  async getExperimentsOverview(
    externalSignal?: AbortSignal
  ): Promise<ExperimentsOverviewResponse> {
    const url = `${ENV.apiBaseUrl}/v1/experiments/overview`;
    try {
      const response = await fetchWithTimeout(
        url,
        {
          headers: { Accept: 'application/json' },
        },
        ENV.requestTimeoutMs,
        externalSignal
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new ApiError(
          extractErrorDetail(errorData, response.status),
          response.status,
          errorData
        );
      }

      const data: ExperimentsOverviewResponse = await response.json();
      return data;
    } catch (error: unknown) {
      if (error instanceof ApiError) throw error;
      const message = error instanceof Error ? error.message : 'Unknown network error';
      throw new ApiError(`Failed to fetch experiments overview: ${message}`);
    }
  },

  /**
   * Get empirical load testing results across 5 traffic scenarios and calibration baselines (/v1/experiments/load).
   */
  async getLoadExperiments(
    externalSignal?: AbortSignal
  ): Promise<LoadExperimentsResponse> {
    const url = `${ENV.apiBaseUrl}/v1/experiments/load`;
    try {
      const response = await fetchWithTimeout(
        url,
        {
          headers: { Accept: 'application/json' },
        },
        ENV.requestTimeoutMs,
        externalSignal
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new ApiError(
          extractErrorDetail(errorData, response.status),
          response.status,
          errorData
        );
      }

      const data: LoadExperimentsResponse = await response.json();
      return data;
    } catch (error: unknown) {
      if (error instanceof ApiError) throw error;
      const message = error instanceof Error ? error.message : 'Unknown network error';
      throw new ApiError(`Failed to fetch load experiment data: ${message}`);
    }
  },

  /**
   * Get empirical retrieval benchmark results across Stage 6 and Stage 8B.2 (/v1/experiments/retrieval).
   */
  async getRetrievalExperiments(
    version?: string,
    externalSignal?: AbortSignal
  ): Promise<RetrievalExperimentsResponse> {
    const query = version ? `?version=${encodeURIComponent(version)}` : '';
    const url = `${ENV.apiBaseUrl}/v1/experiments/retrieval${query}`;
    try {
      const response = await fetchWithTimeout(
        url,
        {
          headers: { Accept: 'application/json' },
        },
        ENV.requestTimeoutMs,
        externalSignal
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new ApiError(
          extractErrorDetail(errorData, response.status),
          response.status,
          errorData
        );
      }

      const data: RetrievalExperimentsResponse = await response.json();
      return data;
    } catch (error: unknown) {
      if (error instanceof ApiError) throw error;
      const message = error instanceof Error ? error.message : 'Unknown network error';
      throw new ApiError(`Failed to fetch retrieval experiment data: ${message}`);
    }
  },
};
