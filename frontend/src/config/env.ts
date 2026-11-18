/**
 * Application environment configuration.
 * Reads variables prefixed with VITE_.
 * Uses direct static access so Vite AST compiler can statically replace
 * import.meta.env.VITE_* with production environment variables during build,
 * while safely guarding in Node.js test environments.
 */

declare const process: { env?: Record<string, string | undefined> } | undefined;

const hasMetaEnv = typeof import.meta !== 'undefined' && Boolean((import.meta as unknown as { env?: unknown }).env);

const rawApiBaseUrl =
  (hasMetaEnv ? import.meta.env.VITE_API_BASE_URL : undefined) ||
  (typeof process !== 'undefined' && process?.env?.VITE_API_BASE_URL) ||
  '';

const rawRequestTimeout =
  (hasMetaEnv ? import.meta.env.VITE_REQUEST_TIMEOUT_MS : undefined) ||
  (typeof process !== 'undefined' && process?.env?.VITE_REQUEST_TIMEOUT_MS) ||
  '15000';

const rawAskTimeout =
  (hasMetaEnv ? import.meta.env.VITE_ASK_TIMEOUT_MS : undefined) ||
  (typeof process !== 'undefined' && process?.env?.VITE_ASK_TIMEOUT_MS) ||
  '60000';

const rawPollInterval =
  (hasMetaEnv ? import.meta.env.VITE_POLL_INTERVAL_MS : undefined) ||
  (typeof process !== 'undefined' && process?.env?.VITE_POLL_INTERVAL_MS) ||
  '15000';

export const ENV = {
  // If empty string, uses relative path so Vite proxy forwards to backend
  apiBaseUrl: String(rawApiBaseUrl).trim().replace(/\/+$/, ''),
  // Health probe timeout in milliseconds (15s default for cloud spin-up resilience)
  requestTimeoutMs: Number(rawRequestTimeout) || 15000,
  // Inference question answering timeout in milliseconds (default 60s)
  askTimeoutMs: Number(rawAskTimeout) || 60000,
  // Polling interval for background health checks (ms)
  healthPollIntervalMs: Number(rawPollInterval) || 15000,
  // Version and metadata
  appVersion: '1.0.0',
  appName: 'THE RELAY',
};
