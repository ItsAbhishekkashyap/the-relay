/**
 * Application environment configuration.
 * Reads variables prefixed with VITE_.
 * Supports both Vite (import.meta.env) and Node test runner (process.env via globalThis).
 */

const metaEnv: Record<string, string | undefined> =
  typeof import.meta !== 'undefined' && 'env' in import.meta
    ? (import.meta as unknown as { env: Record<string, string | undefined> }).env
    : {};

const globalProc =
  typeof globalThis !== 'undefined' && 'process' in globalThis
    ? (globalThis as unknown as { process?: { env?: Record<string, string | undefined> } }).process
    : undefined;

const procEnv: Record<string, string | undefined> = globalProc?.env || {};

export const ENV = {
  // If empty string, uses relative path so Vite proxy forwards to backend
  apiBaseUrl: metaEnv.VITE_API_BASE_URL || procEnv.VITE_API_BASE_URL || '',
  // Health probe timeout in milliseconds
  requestTimeoutMs: Number(metaEnv.VITE_REQUEST_TIMEOUT_MS || procEnv.VITE_REQUEST_TIMEOUT_MS) || 5000,
  // Inference question answering timeout in milliseconds (default 60s)
  askTimeoutMs: Number(metaEnv.VITE_ASK_TIMEOUT_MS || procEnv.VITE_ASK_TIMEOUT_MS) || 60000,
  // Polling interval for background health checks (ms)
  healthPollIntervalMs: Number(metaEnv.VITE_POLL_INTERVAL_MS || procEnv.VITE_POLL_INTERVAL_MS) || 15000,
  // Version and metadata
  appVersion: '1.0.0',
  appName: 'THE RELAY',
};
