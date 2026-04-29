import { Wifi, WifiOff, Database, Clock, Server, Menu, Moon, Sun } from 'lucide-react';
import { systemProfile } from '../data/appConfig';
import type { SystemHealth } from '../data/types';
import { StatusBadge } from './StatusBadge';

interface TopBarProps {
  systemHealth: SystemHealth | null;
  sidebarHidden: boolean;
  onOpenSidebar: () => void;
  themeMode: 'light' | 'dark';
  onToggleTheme: () => void;
}

export function TopBar({ systemHealth, sidebarHidden, onOpenSidebar, themeMode, onToggleTheme }: TopBarProps) {
  const compactHeader = sidebarHidden;
  const statusIconSize = compactHeader ? 'w-3.5 h-3.5' : 'w-4 h-4';
  const hostStatus = systemHealth?.host ?? 'offline';
  const transportStatus = systemHealth?.sensorTransport ?? 'disconnected';
  const backendStatus = systemHealth?.backend ?? 'offline';

  const formatLastSync = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffSecs = Math.floor(diffMs / 1000);
    
    if (diffSecs < 60) return `${diffSecs}s ago`;
    if (diffSecs < 3600) return `${Math.floor(diffSecs / 60)}m ago`;
    return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div
      className={`bg-gray-50 dark:bg-[#162032] border-b border-gray-200 ${
        compactHeader ? 'px-4 md:px-6 py-2' : 'px-4 md:px-8 py-4'
      }`}
    >
      <div className="flex flex-col xl:flex-row xl:items-center xl:justify-between gap-3">
        <div className="flex items-start gap-2.5">
          {sidebarHidden && (
            <button
              onClick={onOpenSidebar}
              className="inline-flex items-center justify-center rounded-md border border-gray-300 bg-white dark:bg-[#0f2032] p-2 text-gray-700 hover:bg-gray-100 transition-colors"
              aria-label="Open navigation menu"
              title="Open navigation menu"
            >
              <Menu className="w-4 h-4" />
            </button>
          )}
          <div>
            <h1 className={`${compactHeader ? 'text-base md:text-lg' : 'text-lg md:text-xl'} font-semibold text-gray-900`}>
              {systemProfile.title}
            </h1>
            <p className={compactHeader ? 'text-[11px] md:text-xs text-gray-600' : 'text-xs md:text-sm text-gray-600'}>
              {systemProfile.subtitle}
            </p>
          </div>
        </div>

        <div
          className={`flex items-center gap-3 md:gap-4 ${
            compactHeader ? 'overflow-x-auto whitespace-nowrap pb-0.5' : 'flex-wrap'
          }`}
        >
          <div className="flex items-center gap-2 shrink-0">
            {hostStatus === 'online' ? (
              <Wifi className={`${statusIconSize} text-green-600`} />
            ) : (
              <WifiOff className={`${statusIconSize} text-red-600`} />
            )}
            <StatusBadge severity={hostStatus} label="Host" size="sm" />
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <Database className={`${statusIconSize} ${transportStatus === 'connected' ? 'text-green-600' : 'text-red-600'}`} />
            <StatusBadge severity={transportStatus} label="HTTP" size="sm" />
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <Server className={`${statusIconSize} ${backendStatus === 'online' ? 'text-green-600' : 'text-red-600'}`} />
            <StatusBadge severity={backendStatus} label="Backend" size="sm" />
          </div>

          <div className={`flex items-center gap-2 ${compactHeader ? 'text-xs' : 'text-sm'} text-gray-700 shrink-0`}>
            <Clock className={`${statusIconSize} text-blue-600`} />
            <span className="font-medium">
              {systemHealth ? formatLastSync(systemHealth.lastSync) : 'Waiting for live data'}
            </span>
            {!compactHeader && systemHealth && (
              <>
                <span className="text-gray-400">|</span>
                <span>{systemHealth.uptime}</span>
              </>
            )}
          </div>

          <button
            onClick={onToggleTheme}
            className="inline-flex items-center gap-2 rounded-md border border-gray-200 bg-white dark:bg-[#0f2032] px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 transition-colors shrink-0"
            aria-label="Toggle light and dark theme"
            title="Toggle theme"
          >
            {themeMode === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            {themeMode === 'dark' ? 'Light' : 'Dark'}
          </button>
        </div>
      </div>
    </div>
  );
}
