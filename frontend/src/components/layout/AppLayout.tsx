import React, { useState } from 'react';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import type { NavigationTab, ConnectionState, ReadyResponse } from '../../types/api';

interface AppLayoutProps {
  currentTab: NavigationTab;
  onSelectTab: (tab: NavigationTab) => void;
  connectionState: ConnectionState;
  ready: ReadyResponse | null;
  latencyMs: number | null;
  isLoadingHealth: boolean;
  onRefreshHealth: () => void;
  children: React.ReactNode;
}

export const AppLayout: React.FC<AppLayoutProps> = ({
  currentTab,
  onSelectTab,
  connectionState,
  ready,
  latencyMs,
  isLoadingHealth,
  onRefreshHealth,
  children,
}) => {
  const [isOpenMobile, setIsOpenMobile] = useState<boolean>(false);

  return (
    <div className="min-h-screen bg-[#F7F8FA] text-[#202532] flex">
      {/* Sidebar Navigation */}
      <Sidebar
        currentTab={currentTab}
        onSelectTab={onSelectTab}
        connectionState={connectionState}
        ready={ready}
        isOpenMobile={isOpenMobile}
        onCloseMobile={() => setIsOpenMobile(false)}
      />

      {/* Main Content Area */}
      <div className="flex-1 lg:pl-64 flex flex-col min-h-screen overflow-x-hidden">
        {/* Sticky Header */}
        <Header
          currentTab={currentTab}
          onOpenMobileSidebar={() => setIsOpenMobile(true)}
          connectionState={connectionState}
          ready={ready}
          latencyMs={latencyMs}
          isLoadingHealth={isLoadingHealth}
          onRefreshHealth={onRefreshHealth}
        />

        {/* Scrollable Page Body */}
        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto">
          {children}
        </main>
      </div>
    </div>
  );
};
