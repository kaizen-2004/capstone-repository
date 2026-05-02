import { useEffect, useState } from 'react';
import { Camera, LogOut, RefreshCw } from 'lucide-react';
import { fetchLiveNodes, fetchMobileRemoteStatus } from '../data/liveApi';
import type { CameraFeed } from '../data/types';
import { useAuth } from '../components/AuthGate';

function cameraStatusClass(status: CameraFeed['status']): string {
  if (status === 'online') {
    return 'border-emerald-400/35 bg-emerald-500/10 text-emerald-300';
  }
  return 'border-slate-500/40 bg-slate-500/20 text-slate-300';
}

export function MobileRemote() {
  const { user, logout } = useAuth();
  const [loading, setLoading] = useState(true);
  const [enabled, setEnabled] = useState(false);
  const [statusDetail, setStatusDetail] = useState('');
  const [lastSync, setLastSync] = useState('');
  const [cameraFeeds, setCameraFeeds] = useState<CameraFeed[]>([]);
  const [streamRetryTickByNode, setStreamRetryTickByNode] = useState<Record<string, number>>({});
  const [reconnectingByNode, setReconnectingByNode] = useState<Record<string, boolean>>({});
  const [retryCountByNode, setRetryCountByNode] = useState<Record<string, number>>({});
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    setRefreshing(true);
    try {
      const [mobileStatus, nodesLive] = await Promise.all([
        fetchMobileRemoteStatus(),
        fetchLiveNodes(),
      ]);
      setEnabled(mobileStatus.enabled);
      setStatusDetail(mobileStatus.detail);
      setCameraFeeds(nodesLive.cameraFeeds);
      setLastSync(new Date().toISOString());
    } finally {
      setRefreshing(false);
      setLoading(false);
    }
  };

  useEffect(() => {
    document.documentElement.classList.add('dark');
    return () => {
      document.documentElement.classList.remove('dark');
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    const run = async () => {
      try {
        await load();
      } catch {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void run();
    const timer = window.setInterval(() => {
      if (!cancelled) {
        void load();
      }
    }, 12000);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#040b16] text-slate-200 flex items-center justify-center text-sm">
        Loading monitor stream...
      </div>
    );
  }

  if (!enabled) {
    return (
      <div className="min-h-screen bg-[#040b16] text-slate-100 p-4 flex items-center justify-center">
        <div className="max-w-md w-full rounded-2xl border border-slate-700/70 bg-[#0d1b2a] p-5 shadow-2xl shadow-black/20 space-y-3">
          <div className="inline-flex items-center gap-2 rounded-full border border-sky-500/40 bg-sky-500/15 px-3 py-1 text-xs font-medium text-sky-300">
            <Camera className="w-4 h-4" />
            Mobile Remote Monitor
          </div>
          <h1 className="text-lg font-semibold text-slate-100">Interface Disabled</h1>
          <p className="text-sm text-slate-400">{statusDetail || 'This feature is currently disabled.'}</p>
          <a
            href="/dashboard/settings"
            className="inline-flex items-center justify-center w-full rounded-lg border border-slate-600 px-4 py-2 text-sm font-medium text-slate-100 hover:bg-slate-700/40"
          >
            Open Settings
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#040b16] text-slate-100">
      <header className="sticky top-0 z-20 border-b border-[#14304f] bg-[#0a1628]/95 backdrop-blur px-3 py-2.5">
        <div className="max-w-3xl mx-auto flex items-center justify-between gap-3">
          <div>
            <h1 className="text-base font-semibold tracking-wide">Mobile Remote Monitor</h1>
            <p className="text-[11px] text-slate-400">
              {lastSync ? `Synced ${new Date(lastSync).toLocaleTimeString()}` : 'Waiting for sync'}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                void load();
              }}
              className="inline-flex items-center justify-center rounded-md border border-[#274a73] bg-[#0c1f35] p-2 text-slate-300 hover:bg-[#12304f]"
              aria-label="Refresh mobile remote data"
              title="Refresh"
            >
              <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            </button>
            <button
              onClick={() => {
                void logout();
              }}
              className="inline-flex items-center gap-1.5 rounded-md border border-[#274a73] bg-[#0c1f35] px-2.5 py-1.5 text-xs font-medium text-slate-300 hover:bg-[#12304f]"
              aria-label={`Logout ${user.username}`}
            >
              <LogOut className="w-4 h-4" />
              Logout
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-3xl mx-auto p-3 space-y-3 pb-8">
        <section className="rounded-xl border border-[#1b3b5d] bg-[#081a2f] p-3">
          <div className="flex items-center gap-2">
            <Camera className="w-4 h-4 text-sky-300" />
            <h2 className="text-sm font-semibold text-slate-100">Camera Monitor</h2>
          </div>
          <p className="mt-1 text-xs text-slate-400">
            Live feed only. Dashboard cards and controls are managed in the mobile app.
          </p>
        </section>

        <section className="space-y-3">
          {cameraFeeds.map((feed) => (
            <div key={feed.nodeId} className="rounded-xl overflow-hidden border border-[#1b3b5d] bg-[#081a2f]">
              <div className="relative bg-black aspect-video">
                {feed.streamPath ? (
                  <img
                    src={`${feed.streamPath}${feed.streamPath.includes('?') ? '&' : '?'}retry_tick=${streamRetryTickByNode[feed.nodeId] || 0}`}
                    alt={`${feed.location} live preview`}
                    className="absolute inset-0 h-full w-full object-cover"
                    onError={() => {
                      setReconnectingByNode((prev) => ({ ...prev, [feed.nodeId]: true }));
                      setRetryCountByNode((prev) => ({
                        ...prev,
                        [feed.nodeId]: (prev[feed.nodeId] || 0) + 1,
                      }));
                      window.setTimeout(() => {
                        setStreamRetryTickByNode((prev) => ({
                          ...prev,
                          [feed.nodeId]: Date.now(),
                        }));
                      }, 1500);
                    }}
                    onLoad={() => {
                      setReconnectingByNode((prev) => ({ ...prev, [feed.nodeId]: false }));
                      setRetryCountByNode((prev) => ({ ...prev, [feed.nodeId]: 0 }));
                    }}
                  />
                ) : (
                  <div className="absolute inset-0 flex items-center justify-center text-slate-400 text-sm">
                    Stream unavailable
                  </div>
                )}
                {reconnectingByNode[feed.nodeId] && (
                  <div className="absolute bottom-2 right-2 rounded bg-amber-500/90 px-2 py-0.5 text-[11px] font-medium text-white">
                    Reconnecting ({(retryCountByNode[feed.nodeId] || 0) > 99 ? '99+' : (retryCountByNode[feed.nodeId] || 0)})...
                  </div>
                )}
              </div>
              <div className="p-2.5 flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-slate-100 truncate">{feed.location}</p>
                  <p className="text-[11px] text-slate-400 font-mono truncate">{feed.nodeId}</p>
                </div>
                <span
                  className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${cameraStatusClass(feed.status)}`}
                >
                  {feed.status.toUpperCase()}
                </span>
              </div>
            </div>
          ))}

          {cameraFeeds.length === 0 && (
            <div className="rounded-xl border border-[#1b3b5d] bg-[#081a2f] p-4 text-sm text-slate-400">
              No camera feeds reported.
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
