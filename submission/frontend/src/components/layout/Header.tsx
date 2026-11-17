import React from 'react';
import { Menu, RefreshCw, Server, AlertCircle } from 'lucide-react';
import { StatusDot } from '../ui/StatusDot';
import { Button } from '../ui/Button';
import type { NavigationTab, ConnectionState, ReadyResponse } from '../../types/api';

interface HeaderProps {
  currentTab: NavigationTab;
  onOpenMobileSidebar: () => void;
  connectionState: ConnectionState;
  ready: ReadyResponse | null;
  latencyMs: number | null;
  isLoadingHealth: boolean;
  onRefreshHealth: () => void;
}

const TAB_TITLES: Record<NavigationTab, { title: string; description: string }> = {
  chat: {
    title: 'Research Chat',
    description: 'Evidence-grounded question answering across 3 engineering research papers.',
  },
  overview: {
    title: 'System Overview',
    description: 'Real-time operational status, component readiness, and architecture diagnostics.',
  },
  experiments: {
    title: 'Experiments & Characterization',
    description: 'Controlled load tests, simulator benchmarks, and retrieval quality measurements.',
  },
  settings: {
    title: 'Settings & Configuration',
    description: 'Model provider settings, rate limits, and environment parameters.',
  },
};

export const Header: React.FC<HeaderProps> = ({
  currentTab,
  onOpenMobileSidebar,
  connectionState,
  ready,
  latencyMs,
  isLoadingHealth,
  onRefreshHealth,
}) => {
  const currentMeta = TAB_TITLES[currentTab];

  return (
    <header className="h-16 border-b border-[#E6E9EF] bg-white/90 backdrop-blur-md sticky top-0 z-30 px-4 lg:px-8 flex items-center justify-between">
      {/* Left: Mobile hamburger & Page Title */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onOpenMobileSidebar}
          className="lg:hidden p-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg"
          aria-label="Open sidebar"
        >
          <Menu className="w-5 h-5" />
        </button>

        <div>
          <h1 className="text-base font-semibold text-slate-900 leading-tight tracking-tight">
            {currentMeta.title}
          </h1>
          <p className="text-xs text-slate-500 hidden sm:block leading-none mt-0.5">
            {currentMeta.description}
          </p>
        </div>
      </div>

      {/* Right: Live Connection & Actions */}
      <div className="flex items-center gap-3">
        {/* Backend Connectivity Pill */}
        <div
          className={`flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs font-mono transition-colors ${
            connectionState === 'connected'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
              : connectionState === 'checking'
              ? 'bg-amber-50 border-amber-200 text-amber-700'
              : 'bg-rose-50 border-rose-200 text-rose-700'
          }`}
          title={
            connectionState === 'connected'
              ? `Backend active (${ready?.provider || 'FastAPI'}) • Round-trip: ${latencyMs ?? 0}ms`
              : 'Backend disconnected or unreachable'
          }
        >
          <StatusDot state={connectionState} size="sm" />
          <span className="font-medium hidden md:inline">
            {connectionState === 'connected'
              ? 'FastAPI Ready'
              : connectionState === 'checking'
              ? 'Probing API...'
              : 'API Offline'}
          </span>
          {connectionState === 'connected' && latencyMs !== null && (
            <span className="text-[11px] text-emerald-700 font-semibold hidden xl:inline">
              ({latencyMs}ms)
            </span>
          )}
          {connectionState === 'disconnected' && (
            <AlertCircle className="w-3.5 h-3.5 text-rose-600 hidden sm:inline" />
          )}
        </div>

        {/* Model Provider Info Pill */}
        {ready && (
          <div className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-[#E6E9EF] bg-slate-50 text-xs font-mono text-slate-600">
            <Server className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-slate-500">Provider:</span>
            <span className="font-medium text-slate-800">{ready.provider}</span>
          </div>
        )}

        {/* Refresh Connectivity Button */}
        <Button
          variant="secondary"
          size="sm"
          onClick={onRefreshHealth}
          isLoading={isLoadingHealth}
          title="Probe backend API health"
          leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${isLoadingHealth ? 'animate-spin' : ''}`} />}
        >
          <span className="hidden sm:inline">Check Health</span>
        </Button>
      </div>
    </header>
  );
};
