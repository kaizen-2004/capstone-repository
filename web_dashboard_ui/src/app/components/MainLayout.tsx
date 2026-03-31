import { useEffect, useState } from 'react';
import { Outlet, useLocation } from 'react-router';
import { Menu, X } from 'lucide-react';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { fetchLiveNodes } from '../data/liveApi';
import { systemHealth as fallbackSystemHealth, systemProfile } from '../data/mockData';

export function MainLayout() {
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [desktopSidebarHidden, setDesktopSidebarHidden] = useState(false);
  const [systemHealth, setSystemHealth] = useState(fallbackSystemHealth);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const live = await fetchLiveNodes();
        if (!cancelled) {
          setSystemHealth(live.systemHealth);
        }
      } catch {
        // Keep fallback data if API is temporarily unavailable.
      }
    };

    void load();
    const timer = window.setInterval(() => {
      void load();
    }, 10000);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    setSidebarOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setSidebarOpen(false);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  return (
    <div className="flex h-screen bg-gray-50">
      <Sidebar
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        desktopHidden={desktopSidebarHidden}
        onDesktopToggle={() => setDesktopSidebarHidden((hidden) => !hidden)}
      />
      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="lg:hidden">
          <div className="sticky top-0 z-30 bg-white/95 backdrop-blur border-b border-gray-200 px-3 py-1.5 sm:py-2 flex items-center gap-2.5">
            <button
              onClick={() => setSidebarOpen((open) => !open)}
              className="inline-flex h-8 w-8 items-center justify-center rounded-md hover:bg-gray-100 transition-colors"
              aria-label={sidebarOpen ? 'Close navigation menu' : 'Open navigation menu'}
              aria-expanded={sidebarOpen}
              aria-controls="app-sidebar"
            >
              {sidebarOpen ? (
                <X className="w-5 h-5 text-gray-900" />
              ) : (
                <Menu className="w-5 h-5 text-gray-900" />
              )}
            </button>
            <div className="min-w-0">
              <h1 className="text-sm sm:text-base font-semibold leading-tight text-gray-900 truncate">
                {systemProfile.title}
              </h1>
              <p className="text-[10px] sm:text-[11px] leading-tight text-gray-500 truncate">
                {systemProfile.subtitle}
              </p>
            </div>
          </div>
        </div>
        <div className="hidden lg:block">
          <TopBar
            systemHealth={systemHealth}
            sidebarHidden={desktopSidebarHidden}
            onOpenSidebar={() => setDesktopSidebarHidden(false)}
          />
        </div>
        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-[1520px]">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
