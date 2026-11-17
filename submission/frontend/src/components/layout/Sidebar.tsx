import React from 'react';
import {
  MessageSquare,
  Activity,
  BarChart3,
  Settings,
  Layers,
  X,
  FileText,
} from 'lucide-react';
import { NavItem } from '../navigation/NavItem';
import { StatusDot } from '../ui/StatusDot';
import { Badge } from '../ui/Badge';
import type { NavigationTab, ConnectionState, ReadyResponse } from '../../types/api';

interface SidebarProps {
  currentTab: NavigationTab;
  onSelectTab: (tab: NavigationTab) => void;
  connectionState: ConnectionState;
  ready: ReadyResponse | null;
  isOpenMobile: boolean;
  onCloseMobile: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onSelectTab,
  connectionState,
  ready,
  isOpenMobile,
  onCloseMobile,
}) => {
  const navItems: Array<{
    id: NavigationTab;
    label: string;
    icon: React.ReactNode;
    badge?: string;
  }> = [
    {
      id: 'chat',
      label: 'Research Chat',
      icon: <MessageSquare className="w-4 h-4" />,
    },
    {
      id: 'overview',
      label: 'System Overview',
      icon: <Activity className="w-4 h-4" />,
      badge: ready?.status === 'ready' ? 'Ready' : undefined,
    },
    {
      id: 'experiments',
      label: 'Experiments',
      icon: <BarChart3 className="w-4 h-4" />,
    },
    {
      id: 'settings',
      label: 'Settings',
      icon: <Settings className="w-4 h-4" />,
    },
  ];

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpenMobile && (
        <div
          className="fixed inset-0 z-40 bg-slate-900/30 backdrop-blur-xs lg:hidden"
          onClick={onCloseMobile}
          aria-hidden="true"
        />
      )}

      {/* Sidebar Panel */}
      <aside
        className={`fixed top-0 bottom-0 left-0 z-50 w-64 bg-white border-r border-[#E6E9EF] flex flex-col transition-transform duration-200 ease-in-out lg:translate-x-0 ${
          isOpenMobile ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Brand / Logo Area */}
        <div className="h-16 flex items-center justify-between px-5 border-b border-[#E6E9EF]">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 shadow-xs">
              <Layers className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <span className="font-bold text-sm tracking-tight text-slate-900 font-sans">
                  The Relay
                </span>
                <span className="text-[10px] bg-slate-100 text-slate-600 border border-slate-200 px-1 py-0.2 rounded font-mono font-medium">
                  v1.0
                </span>
              </div>
              <p className="text-[11px] text-slate-500 leading-none mt-0.5 font-medium">
                Research Assistant
              </p>
            </div>
          </div>

          {/* Mobile close button */}
          <button
            type="button"
            onClick={onCloseMobile}
            className="lg:hidden p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-md"
            aria-label="Close sidebar"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Navigation Items */}
        <div className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          <div className="px-3 pb-2 text-[10.5px] font-semibold uppercase tracking-wider text-slate-400 font-mono">
            Navigation
          </div>
          {navItems.map((item) => (
            <NavItem
              key={item.id}
              id={item.id}
              label={item.label}
              icon={item.icon}
              badge={item.badge}
              isActive={currentTab === item.id}
              onClick={(id) => {
                onSelectTab(id);
                onCloseMobile();
              }}
            />
          ))}

          {/* Research Corpus Information Card */}
          <div className="pt-6">
            <div className="px-3 pb-2 text-[10.5px] font-semibold uppercase tracking-wider text-slate-400 font-mono">
              Research Corpus
            </div>
            <div className="mx-1 p-3 rounded-lg bg-[#F9FAFB] border border-[#E6E9EF] text-xs space-y-2">
              <div className="flex items-center gap-1.5 text-slate-700 font-medium">
                <FileText className="w-3.5 h-3.5 text-slate-500" />
                <span>3 Approved Papers</span>
              </div>
              <ul className="text-[11px] text-slate-600 space-y-1 pl-1 font-mono">
                <li className="truncate" title="1706.03762v7: Attention Is All You Need">
                  • 1706.03762v7 (15p)
                </li>
                <li className="truncate" title="2410.00037v1: Moshi Speech-Text Foundation">
                  • 2410.00037v1 (66p)
                </li>
                <li className="truncate" title="2507.07955v2: Dynamic Chunking">
                  • 2507.07955v2 (39p)
                </li>
              </ul>
              <div className="pt-1.5 border-t border-[#E6E9EF] text-[10px] text-slate-400 font-mono">
                120 pages total • 402 chunks
              </div>
            </div>
          </div>
        </div>

        {/* Backend Status Indicator Card at Bottom of Sidebar */}
        <div className="p-3 border-t border-[#E6E9EF] bg-white">
          <div className="p-2.5 rounded-lg bg-[#F9FAFB] border border-[#E6E9EF] space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-600 font-medium">Backend API</span>
              <div className="flex items-center gap-1.5">
                <StatusDot state={connectionState} size="sm" />
                <span
                  className={`text-[11px] font-mono font-medium capitalize ${
                    connectionState === 'connected'
                      ? 'text-emerald-700'
                      : connectionState === 'checking'
                      ? 'text-amber-700'
                      : 'text-rose-700'
                  }`}
                >
                  {connectionState === 'connected'
                    ? 'Connected'
                    : connectionState === 'checking'
                    ? 'Checking...'
                    : 'Disconnected'}
                </span>
              </div>
            </div>

            {ready && (
              <div className="flex items-center justify-between text-[11px] text-slate-600 font-mono pt-1.5 border-t border-[#E6E9EF]">
                <span>Provider</span>
                <Badge variant={ready.provider === 'simulator' ? 'purple' : 'blue'} size="sm">
                  {ready.provider}
                </Badge>
              </div>
            )}
          </div>
        </div>
      </aside>
    </>
  );
};
