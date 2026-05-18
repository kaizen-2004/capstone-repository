import { useEffect, useState } from 'react';
import { Camera, LogOut, RefreshCw } from 'lucide-react';
import { fetchLiveNodes, fetchMobileRemoteStatus } from '../data/liveApi';
import type { CameraFeed } from '../data/types';
import { useAuth } from '../components/AuthGate';

function cameraStatusClass(status: CameraFeed['status'], reconnecting: boolean, hasStream: boolean): string {
  if (!hasStream || reconnecting) {
    return 'border-amber-400/40 bg-amber-500/15 text-amber-200';
  }
  if (status === 'online') {
    return 'border-emerald-400/35 bg-emerald-500/10 text-emerald-300';
  }
  return 'border-slate-500/40 bg-slate-500/20 text-slate-300';
}

function cameraStatusLabel(feed: CameraFeed, reconnecting: boolean): string {
  if (!feed.streamPath) {
    return 'NO STREAM';
  }
  if (reconnecting) {
    return 'RECONNECTING';
  }
  return feed.status.toUpperCase();
}

function formatLastSync(value: string): string {
  if (!value) {
    return 'Waiting for sync';
  }
  return `Synced ${new Date(value).toLocaleTimeString()}`;
}

function buildCameraSrc(path: string | undefined, retryTick: number): string {
  if (!path) {
    return '';
  }

  const separator = path.includes('?') ? '&' : '?';
  const isStream = path.includes('/camera/stream/');
  if (isStream) {
    return `${path}${separator}fps=8&retry_tick=${retryTick}`;
  }
  return `${path}${separator}frame_tick=${retryTick}`;
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
  const [loadError, setLoadError] = useState('');
  const embedded = new URLSearchParams(window.location.search).get('embedded') === '1';
  const onlineCount = cameraFeeds.filter((feed) => feed.status === 'online').length;
  const reconnectingCount = cameraFeeds.filter((feed) => reconnectingByNode[feed.nodeId]).length;
  const offlineCount = cameraFeeds.filter((feed) => feed.status !== 'online').length;
  const syncText = formatLastSync(lastSync);

  const load = async (signal?: AbortSignal) => {
    setRefreshing(true);
    try {
      const [mobileStatus, nodesLive] = await Promise.all([
        fetchMobileRemoteStatus(signal),
        fetchLiveNodes(signal),
      ]);
      if (signal?.aborted) {
        return;
      }
      setEnabled(mobileStatus.enabled);
      setStatusDetail(mobileStatus.detail);
      setCameraFeeds(nodesLive.cameraFeeds);
      setLastSync(new Date().toISOString());
      setLoadError('');
    } catch (error) {
      if (!signal?.aborted) {
        const message = error instanceof Error ? error.message : 'Unable to load mobile monitor.';
        setLoadError(message);
      }
    } finally {
      if (!signal?.aborted) {
        setRefreshing(false);
        setLoading(false);
      }
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
    let controller: AbortController | null = null;
    let timer: number | null = null;

    const run = async () => {
      controller = new AbortController();
      try {
        await load(controller.signal);
      } catch {
        if (!cancelled) {
          setLoading(false);
        }
      } finally {
        controller = null;
        if (!cancelled) {
          timer = window.setTimeout(() => {
            void run();
          }, 12000);
        }
      }
    };

    void run();

    return () => {
      cancelled = true;
      controller?.abort();
      if (timer !== null) {
        window.clearTimeout(timer);
      }
    };
  }, []);

  if (loading) {
    return (
      <div className={`${embedded ? 'min-h-full' : 'min-h-screen'} bg-[#040b16] text-slate-200 flex items-center justify-center text-sm`}>
        Loading monitor stream...
      </div>
    );
  }

  if (!enabled) {
    if (loadError) {
      return (
        <div className={`${embedded ? 'min-h-full' : 'min-h-screen'} bg-[#040b16] text-slate-100 p-4 flex items-center justify-center`}>
          <div className="max-w-md w-full rounded-2xl border border-amber-500/40 bg-[#0d1b2a] p-5 shadow-2xl shadow-black/20 space-y-3">
            <div className="inline-flex items-center gap-2 rounded-full border border-amber-500/40 bg-amber-500/15 px-3 py-1 text-xs font-medium text-amber-200">
              <Camera className="w-4 h-4" />
              Mobile Remote Monitor
            </div>
            <h1 className="text-lg font-semibold text-slate-100">Monitor Unavailable</h1>
            <p className="text-sm text-slate-400">
              Could not reach the mobile monitor data. Check backend, LAN, or Tailscale connectivity.
            </p>
            <p className="rounded-lg border border-slate-700 bg-[#071525] p-3 text-xs text-slate-400 break-words">
              {loadError}
            </p>
            <button
              type="button"
              onClick={() => {
                void load();
              }}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-amber-500/40 bg-amber-500/15 px-4 py-2 text-sm font-medium text-amber-100 hover:bg-amber-500/25"
            >
              <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
              Retry
            </button>
          </div>
        </div>
      );
    }

    return (
      <div className={`${embedded ? 'min-h-full' : 'min-h-screen'} bg-[#040b16] text-slate-100 p-4 flex items-center justify-center`}>
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
    <div className={`${embedded ? 'min-h-full' : 'min-h-screen'} bg-[#040b16] text-slate-100`}>
      {!embedded && (
        <header className="sticky top-0 z-20 border-b border-[#14304f] bg-[#0a1628]/95 backdrop-blur px-3 py-2.5">
          <div className="max-w-3xl mx-auto flex items-center justify-between gap-3">
            <div>
              <h1 className="text-base font-semibold tracking-wide">Mobile Remote Monitor</h1>
              <p className="text-[11px] text-slate-400">{syncText}</p>
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
      )}

      <main className={`max-w-3xl mx-auto ${embedded ? 'p-3 pb-4' : 'p-3 pb-8'} space-y-3`}>
        <section className="rounded-2xl border border-[#1b3b5d] bg-gradient-to-br from-[#081a2f] to-[#061322] p-3 shadow-xl shadow-black/10">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-start gap-2.5">
              <div className="rounded-xl border border-sky-400/30 bg-sky-500/15 p-2">
                <Camera className="w-4 h-4 text-sky-300" />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-slate-100">Camera Feed Body</h2>
                <p className="mt-0.5 text-[11px] text-slate-400">{syncText}</p>
              </div>
            </div>
            <button
              onClick={() => {
                void load();
              }}
              className="inline-flex items-center justify-center rounded-lg border border-[#274a73] bg-[#0c1f35] p-2 text-slate-300 hover:bg-[#12304f]"
              aria-label="Refresh camera feeds"
              title="Refresh"
            >
              <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            </button>
          </div>
          <div className="mt-3 grid grid-cols-3 gap-2 text-center">
            <div className="rounded-xl border border-emerald-400/20 bg-emerald-500/10 px-2 py-2">
              <p className="text-base font-semibold text-emerald-200">{onlineCount}</p>
              <p className="text-[10px] uppercase tracking-wide text-emerald-300/80">Online</p>
            </div>
            <div className="rounded-xl border border-amber-400/20 bg-amber-500/10 px-2 py-2">
              <p className="text-base font-semibold text-amber-200">{reconnectingCount}</p>
              <p className="text-[10px] uppercase tracking-wide text-amber-300/80">Retrying</p>
            </div>
            <div className="rounded-xl border border-slate-500/30 bg-slate-500/10 px-2 py-2">
              <p className="text-base font-semibold text-slate-200">{offlineCount}</p>
              <p className="text-[10px] uppercase tracking-wide text-slate-400">Offline</p>
            </div>
          </div>
          <p className="mt-1 text-xs text-slate-400">
            Live feed only. Face overlays are disabled here for smoother mobile FPS.
          </p>
        </section>

        <section className="space-y-3">
          {cameraFeeds.map((feed) => {
            const reconnecting = Boolean(reconnectingByNode[feed.nodeId]);
            const hasStream = Boolean(feed.streamPath);
            return (
              <div key={feed.nodeId} className="rounded-2xl overflow-hidden border border-[#1b3b5d] bg-[#081a2f] shadow-lg shadow-black/10">
                <div className="relative bg-black aspect-video">
                  {feed.streamPath ? (
                    <img
                      src={buildCameraSrc(feed.streamPath, streamRetryTickByNode[feed.nodeId] || 0)}
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
                    <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 px-6 text-center text-slate-400">
                      <Camera className="w-8 h-8 text-slate-500" />
                      <p className="text-sm font-medium text-slate-300">No stream path</p>
                      <p className="text-xs text-slate-500">This camera is known, but the backend did not publish a live feed URL.</p>
                    </div>
                  )}
                  {reconnecting && (
                    <div className="absolute bottom-2 right-2 rounded bg-amber-500/90 px-2 py-0.5 text-[11px] font-medium text-white">
                      Reconnecting ({(retryCountByNode[feed.nodeId] || 0) > 99 ? '99+' : (retryCountByNode[feed.nodeId] || 0)})...
                    </div>
                  )}
                </div>
                <div className="p-3 flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-slate-100 truncate">{feed.location}</p>
                    <p className="text-[11px] text-slate-400 font-mono truncate">{feed.nodeId}</p>
                  </div>
                  <span
                    className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-semibold ${cameraStatusClass(feed.status, reconnecting, hasStream)}`}
                  >
                    {cameraStatusLabel(feed, reconnecting)}
                  </span>
                </div>
              </div>
            );
          })}

          {cameraFeeds.length === 0 && (
            <div className="rounded-2xl border border-[#1b3b5d] bg-[#081a2f] p-5 text-center text-sm text-slate-400">
              <Camera className="mx-auto mb-2 h-8 w-8 text-slate-500" />
              No camera feeds reported by the backend yet.
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
