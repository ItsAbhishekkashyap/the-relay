import { useState } from 'react';
import { AppLayout } from './components/layout/AppLayout';
import { ChatPage } from './pages/ChatPage';
import { OverviewPage } from './pages/OverviewPage';
import { ExperimentsPage } from './pages/ExperimentsPage';
import { SettingsPage } from './pages/SettingsPage';
import { useBackendHealth } from './hooks/useBackendHealth';
import type { NavigationTab } from './types/api';

export function App() {
  const [currentTab, setCurrentTab] = useState<NavigationTab>('chat');
  const healthState = useBackendHealth();

  const renderActivePage = () => {
    switch (currentTab) {
      case 'chat':
        return (
          <ChatPage
            connectionState={healthState.connectionState}
            ready={healthState.ready}
          />
        );
      case 'overview':
        return (
          <OverviewPage
            health={healthState.health}
            ready={healthState.ready}
            connectionState={healthState.connectionState}
            isLoading={healthState.isLoading}
            error={healthState.error}
            lastChecked={healthState.lastChecked}
            latencyMs={healthState.latencyMs}
            onRefresh={healthState.refresh}
          />
        );
      case 'experiments':
        return <ExperimentsPage />;
      case 'settings':
        return (
          <SettingsPage
            ready={healthState.ready}
            connectionState={healthState.connectionState}
          />
        );
      default:
        return (
          <ChatPage
            connectionState={healthState.connectionState}
            ready={healthState.ready}
          />
        );
    }
  };

  return (
    <AppLayout
      currentTab={currentTab}
      onSelectTab={setCurrentTab}
      connectionState={healthState.connectionState}
      ready={healthState.ready}
      latencyMs={healthState.latencyMs}
      isLoadingHealth={healthState.isLoading}
      onRefreshHealth={healthState.refresh}
    >
      {renderActivePage()}
    </AppLayout>
  );
}

export default App;
