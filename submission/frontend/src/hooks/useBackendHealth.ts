import { useState, useEffect, useCallback, useRef } from 'react';
import { api, ApiError } from '../services/api';
import { ENV } from '../config/env';
import type { HealthResponse, ReadyResponse, ConnectionState } from '../types/api';

export interface BackendHealthState {
  health: HealthResponse | null;
  ready: ReadyResponse | null;
  connectionState: ConnectionState;
  isLoading: boolean;
  error: string | null;
  lastChecked: Date | null;
  latencyMs: number | null;
  refresh: () => Promise<void>;
}

export function useBackendHealth(): BackendHealthState {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [ready, setReady] = useState<ReadyResponse | null>(null);
  const [connectionState, setConnectionState] = useState<ConnectionState>('checking');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);

  const isMountedRef = useRef<boolean>(true);

  const runProbe = useCallback(async (isManualTrigger: boolean = false) => {
    if (isManualTrigger) {
      setIsLoading(true);
      setConnectionState((prev) => (prev === 'connected' ? 'checking' : prev));
    }

    const startTime = performance.now();
    try {
      // Execute health and ready probes in parallel
      const [healthData, readyData] = await Promise.all([
        api.getHealth(),
        api.getReady(),
      ]);

      const elapsed = Math.round(performance.now() - startTime);

      if (!isMountedRef.current) return;

      // Both returned 200 with valid payloads
      setHealth(healthData);
      setReady(readyData);
      setConnectionState('connected');
      setError(null);
      setLatencyMs(elapsed);
      setLastChecked(new Date());
    } catch (err: unknown) {
      if (!isMountedRef.current) return;

      const elapsed = Math.round(performance.now() - startTime);
      setLatencyMs(elapsed);
      setHealth(null);
      setReady(null);
      setConnectionState('disconnected');
      setLastChecked(new Date());

      if (err instanceof ApiError) {
        setError(err.message);
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Failed to connect to backend server');
      }
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    isMountedRef.current = true;
    
    // Schedule initial probe after initial render
    const initialTimer = setTimeout(() => {
      void runProbe(false);
    }, 0);

    const intervalId = setInterval(() => {
      void runProbe(false);
    }, ENV.healthPollIntervalMs);

    return () => {
      isMountedRef.current = false;
      clearTimeout(initialTimer);
      clearInterval(intervalId);
    };
  }, [runProbe]);

  const handleManualRefresh = useCallback(async () => {
    await runProbe(true);
  }, [runProbe]);

  return {
    health,
    ready,
    connectionState,
    isLoading,
    error,
    lastChecked,
    latencyMs,
    refresh: handleManualRefresh,
  };
}
