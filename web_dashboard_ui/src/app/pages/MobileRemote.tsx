import { useEffect, useMemo, useState } from 'react';
import { BellRing, Camera, LogOut, RefreshCw, ShieldAlert, Smartphone, Wifi } from 'lucide-react';
import {
  fetchLiveEvents,
  fetchLiveNodes,
  fetchMobileBootstrap,
  fetchMobileNotificationPreferences,
  fetchMobileRemoteStatus,
  registerMobileDevice,
  saveMobileNotificationPreferences,
  type MobileBootstrapPayload,
  type MobileNetworkMode,
  type MobileNotificationPreferences,
  unregisterMobileDevice,
} from '../data/liveApi';
import type {
  Alert,
  CameraFeed,
  SensorStatus,
  ServiceStatus,
} from '../data/mockData';
import { useAuth } from '../components/AuthGate';
import { StatusBadge } from '../components/StatusBadge';
import {
  disablePushSubscription,
  ensurePushSubscription,
  getOrCreateMobileDeviceId,
  isPushSupported,
  registerDashboardServiceWorker,
} from '../mobile/push';

const NETWORK_MODE_KEY = 'thesis_mobile_network_mode_v1';

function detectPlatformLabel(): string {
  const ua = navigator.userAgent.toLowerCase();
  if (ua.includes('android')) {
    return 'web_pwa_android';
  }
  if (ua.includes('iphone') || ua.includes('ipad') || ua.includes('ios')) {
    return 'web_pwa_ios';
  }
  return 'web_pwa';
}

function parseAlertId(rawId: string): number | null {
  const digits = rawId.replace(/\D+/g, '');
  if (!digits) {
    return null;
  }
  const parsed = Number.parseInt(digits, 10);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return null;
  }
  return parsed;
}

export function MobileRemote() {
  const { user, logout } = useAuth();
  const [loading, setLoading] = useState(true);
  const [enabled, setEnabled] = useState(false);
  const [statusDetail, setStatusDetail] = useState('');
  const [lastSync, setLastSync] = useState('');
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [cameraFeeds, setCameraFeeds] = useState<CameraFeed[]>([]);
  const [sensorStatuses, setSensorStatuses] = useState<SensorStatus[]>([]);
  const [serviceStatuses, setServiceStatuses] = useState<ServiceStatus[]>([]);
  const [ackPendingId, setAckPendingId] = useState('');
  const [refreshing, setRefreshing] = useState(false);
  const [bootstrap, setBootstrap] = useState<MobileBootstrapPayload | null>(null);
  const [notificationPrefs, setNotificationPrefs] = useState<MobileNotificationPreferences | null>(null);
  const [networkMode, setNetworkMode] = useState<MobileNetworkMode>('auto');
  const [pushRegistered, setPushRegistered] = useState(false);
  const [pushWorking, setPushWorking] = useState(false);
  const [pushMessage, setPushMessage] = useState('');

  const refreshPushRegistrationState = async () => {
    if (!isPushSupported()) {
      setPushRegistered(false);
      return;
    }
    try {
      const registration = await navigator.serviceWorker.getRegistration('/dashboard/');
      const subscription = registration ? await registration.pushManager.getSubscription() : null;
      setPushRegistered(Boolean(subscription));
    } catch {
      setPushRegistered(false);
    }
  };

  const syncDeviceRegistration = async (pushSubscription?: PushSubscriptionJSON | Record<string, unknown>) => {
    const deviceId = getOrCreateMobileDeviceId();
    await registerMobileDevice({
      deviceId,
      platform: detectPlatformLabel(),
      networkMode,
      pushSubscription,
    });
  };

  const load = async () => {
    setRefreshing(true);
    try {
      const [mobileStatus, eventsLive, nodesLive, bootstrapPayload, prefs] = await Promise.all([
        fetchMobileRemoteStatus(),
        fetchLiveEvents(120),
        fetchLiveNodes(),
        fetchMobileBootstrap(),
        fetchMobileNotificationPreferences(),
      ]);
      setEnabled(mobileStatus.enabled);
      setStatusDetail(mobileStatus.detail);
      setAlerts(eventsLive.alerts);
      setCameraFeeds(nodesLive.cameraFeeds);
      setSensorStatuses(nodesLive.sensorStatuses);
      setServiceStatuses(nodesLive.serviceStatuses);
      setBootstrap(bootstrapPayload);
      setNotificationPrefs(prefs);
      const savedMode = window.localStorage.getItem(NETWORK_MODE_KEY);
      if (savedMode === 'lan' || savedMode === 'tailscale' || savedMode === 'auto') {
        setNetworkMode(savedMode);
      } else if (bootstrapPayload.networkModes.includes('auto')) {
        setNetworkMode('auto');
      }
      setLastSync(new Date().toISOString());
      await refreshPushRegistrationState();
    } finally {
      setRefreshing(false);
      setLoading(false);
    }
  };

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

  const activeAlerts = useMemo(
    () => alerts.filter((alert) => !alert.acknowledged),
    [alerts],
  );

  const onlineSensors = useMemo(
    () => sensorStatuses.filter((node) => node.status === 'online').length,
    [sensorStatuses],
  );

  const onlineCameras = useMemo(
    () => cameraFeeds.filter((feed) => feed.status === 'online').length,
    [cameraFeeds],
  );

  const handleAck = async (id: string) => {
    const numericId = parseAlertId(id);
    if (!numericId) {
      return;
    }
    setAckPendingId(id);
    try {
      await fetch(`/api/alerts/${numericId}/ack`, {
        method: 'POST',
        credentials: 'include',
      });
      setAlerts((previous) =>
        previous.map((alert) => (alert.id === id ? { ...alert, acknowledged: true } : alert)),
      );
    } finally {
      setAckPendingId('');
    }
  };

  const handleEnablePush = async () => {
    if (!bootstrap) {
      return;
    }
    if (!bootstrap.pushAvailable) {
      setPushMessage('Push backend is not configured yet. Set VAPID keys first.');
      return;
    }
    if (!isPushSupported()) {
      setPushMessage('Push is not supported on this browser.');
      return;
    }
    setPushWorking(true);
    setPushMessage('');
    try {
      const subscription = await ensurePushSubscription(bootstrap.vapidPublicKey);
      if (!subscription) {
        setPushMessage('Push permission not granted or subscription failed.');
        return;
      }
      await syncDeviceRegistration(subscription.toJSON());
      const prefs = await saveMobileNotificationPreferences({ pushEnabled: true });
      setNotificationPrefs(prefs);
      await refreshPushRegistrationState();
      setPushMessage('App push notifications enabled.');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error.';
      setPushMessage(`Failed to enable push: ${message}`);
    } finally {
      setPushWorking(false);
    }
  };

  const handleDisablePush = async () => {
    setPushWorking(true);
    setPushMessage('');
    try {
      await disablePushSubscription();
      await unregisterMobileDevice(getOrCreateMobileDeviceId());
      const prefs = await saveMobileNotificationPreferences({ pushEnabled: false });
      setNotificationPrefs(prefs);
      await refreshPushRegistrationState();
      setPushMessage('App push notifications disabled.');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error.';
      setPushMessage(`Failed to disable push: ${message}`);
    } finally {
      setPushWorking(false);
    }
  };

  const handleSaveNetworkMode = async () => {
    window.localStorage.setItem(NETWORK_MODE_KEY, networkMode);
    setPushWorking(true);
    setPushMessage('');
    try {
      if (pushRegistered && isPushSupported()) {
        await registerDashboardServiceWorker();
        const registration = await navigator.serviceWorker.getRegistration('/dashboard/');
        const subscription = registration ? await registration.pushManager.getSubscription() : null;
        await syncDeviceRegistration(subscription?.toJSON());
      } else {
        await syncDeviceRegistration();
      }
      setPushMessage('Network mode updated for this mobile device.');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error.';
      setPushMessage(`Failed to update network mode: ${message}`);
    } finally {
      setPushWorking(false);
    }
  };

  const handleToggleTelegramFallback = async (enabledValue: boolean) => {
    setPushWorking(true);
    setPushMessage('');
    try {
      const prefs = await saveMobileNotificationPreferences({
        telegramFallbackEnabled: enabledValue,
      });
      setNotificationPrefs(prefs);
      setPushMessage(
        enabledValue
          ? 'Telegram fallback enabled as backup channel.'
          : 'Telegram fallback disabled. App push is now primary only.',
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error.';
      setPushMessage(`Failed to update fallback setting: ${message}`);
    } finally {
      setPushWorking(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center text-sm text-gray-600">
        Loading mobile remote interface...
      </div>
    );
  }

  if (!enabled) {
    return (
      <div className="min-h-screen bg-slate-50 p-4 flex items-center justify-center">
        <div className="max-w-md w-full rounded-xl border border-gray-200 bg-white p-5 shadow-sm space-y-3">
          <div className="inline-flex items-center gap-2 rounded-full bg-blue-50 border border-blue-200 px-3 py-1 text-xs font-medium text-blue-700">
            <Smartphone className="w-4 h-4" />
            Mobile Remote Interface
          </div>
          <h1 className="text-lg font-semibold text-gray-900">Interface Disabled</h1>
          <p className="text-sm text-gray-600">{statusDetail || 'This feature is currently disabled.'}</p>
          <a
            href="/dashboard/settings"
            className="inline-flex items-center justify-center w-full rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Open Settings
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 text-gray-900">
      <header className="sticky top-0 z-20 border-b border-gray-200 bg-white/95 backdrop-blur px-3 py-2">
        <div className="max-w-3xl mx-auto flex items-center justify-between gap-3">
          <div>
            <h1 className="text-base font-semibold">Mobile Remote</h1>
            <p className="text-[11px] text-gray-500">
              {lastSync ? `Synced ${new Date(lastSync).toLocaleTimeString()}` : 'Waiting for sync'}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                void load();
              }}
              className="inline-flex items-center justify-center rounded-md border border-gray-200 p-2 text-gray-700 hover:bg-gray-50"
              aria-label="Refresh mobile remote data"
              title="Refresh"
            >
              <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            </button>
            <button
              onClick={() => {
                void logout();
              }}
              className="inline-flex items-center gap-1.5 rounded-md border border-gray-200 px-2.5 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
              aria-label={`Logout ${user.username}`}
            >
              <LogOut className="w-4 h-4" />
              Logout
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-3xl mx-auto p-3 space-y-3 pb-8">
        <section className="grid grid-cols-2 gap-2">
          <div className="rounded-lg border border-blue-200 bg-blue-50 p-3">
            <p className="text-xs text-blue-700">Active Alerts</p>
            <p className="text-xl font-semibold text-blue-900 mt-1">{activeAlerts.length}</p>
          </div>
          <div className="rounded-lg border border-green-200 bg-green-50 p-3">
            <p className="text-xs text-green-700">Online Sensors</p>
            <p className="text-xl font-semibold text-green-900 mt-1">
              {onlineSensors}/{sensorStatuses.length}
            </p>
          </div>
          <div className="rounded-lg border border-indigo-200 bg-indigo-50 p-3 col-span-2">
            <p className="text-xs text-indigo-700">Online Cameras</p>
            <p className="text-xl font-semibold text-indigo-900 mt-1">
              {onlineCameras}/{cameraFeeds.length}
            </p>
          </div>
        </section>

        <section className="rounded-lg border border-gray-200 bg-white p-3 space-y-3">
          <div className="flex items-center gap-2">
            <BellRing className="w-4 h-4 text-blue-600" />
            <h2 className="text-sm font-semibold">App Notifications</h2>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-gray-700">
            <div className="rounded-md border border-gray-200 bg-gray-50 p-2">
              <p className="text-gray-500">Push Capability</p>
              <p className="font-medium mt-0.5">
                {bootstrap?.pushAvailable ? 'Ready (VAPID configured)' : 'Not configured on backend'}
              </p>
            </div>
            <div className="rounded-md border border-gray-200 bg-gray-50 p-2">
              <p className="text-gray-500">Device Registration</p>
              <p className="font-medium mt-0.5">{pushRegistered ? 'Registered' : 'Not registered'}</p>
            </div>
            <div className="rounded-md border border-gray-200 bg-gray-50 p-2">
              <p className="text-gray-500">Browser Permission</p>
              <p className="font-medium mt-0.5">{isPushSupported() ? Notification.permission : 'unsupported'}</p>
            </div>
            <div className="rounded-md border border-gray-200 bg-gray-50 p-2">
              <p className="text-gray-500">Telegram Fallback</p>
              <p className="font-medium mt-0.5">
                {notificationPrefs?.telegramFallbackEnabled ? 'Enabled' : 'Disabled'}
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-[1fr_auto] gap-2">
            <label className="text-xs text-gray-600 flex flex-col gap-1">
              Network Mode
              <select
                value={networkMode}
                onChange={(event) => setNetworkMode(event.target.value as MobileNetworkMode)}
                className="px-3 py-2 rounded-md border border-gray-200 bg-white text-sm text-gray-800"
              >
                {(bootstrap?.networkModes || ['auto', 'lan', 'tailscale']).map((mode) => (
                  <option key={mode} value={mode}>
                    {mode.toUpperCase()}
                  </option>
                ))}
              </select>
            </label>
            <button
              onClick={() => {
                void handleSaveNetworkMode();
              }}
              disabled={pushWorking}
              className="px-3 py-2 rounded-md border border-gray-200 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-60"
            >
              Save Network
            </button>
          </div>

          <div className="rounded-md border border-gray-200 bg-gray-50 p-2 text-xs text-gray-700 space-y-1">
            <p className="text-gray-500">Resolved Access Endpoints</p>
            <p className="break-all">
              Preferred: <span className="font-mono">{bootstrap?.preferredBaseUrl || '-'}</span>
            </p>
            <p className="break-all">
              mDNS: <span className="font-mono">{bootstrap?.mdnsBaseUrl || '-'}</span>
            </p>
            <p className="break-all">
              Tailscale: <span className="font-mono">{bootstrap?.tailscaleBaseUrl || '-'}</span>
            </p>
            <p className="break-all">
              LAN: <span className="font-mono">{bootstrap?.lanBaseUrl || '-'}</span>
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => {
                void handleEnablePush();
              }}
              disabled={pushWorking}
              className="px-3 py-2 rounded-md bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-60"
            >
              Enable App Push
            </button>
            <button
              onClick={() => {
                void handleDisablePush();
              }}
              disabled={pushWorking}
              className="px-3 py-2 rounded-md border border-gray-200 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-60"
            >
              Disable App Push
            </button>
            <button
              onClick={() => {
                void handleToggleTelegramFallback(!Boolean(notificationPrefs?.telegramFallbackEnabled));
              }}
              disabled={pushWorking}
              className="px-3 py-2 rounded-md border border-gray-200 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-60"
            >
              {notificationPrefs?.telegramFallbackEnabled ? 'Disable Telegram Fallback' : 'Enable Telegram Fallback'}
            </button>
          </div>

          {pushMessage && (
            <p className="text-xs text-gray-600 break-words">{pushMessage}</p>
          )}
        </section>

        <section className="rounded-lg border border-gray-200 bg-white p-3 space-y-2">
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-red-600" />
            <h2 className="text-sm font-semibold">Active Alerts</h2>
          </div>
          {activeAlerts.length === 0 && (
            <p className="text-sm text-gray-600">No active alerts.</p>
          )}
          {activeAlerts.slice(0, 6).map((alert) => (
            <div key={alert.id} className="rounded-lg border border-gray-200 p-2.5 space-y-1">
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm font-medium text-gray-900 break-words">{alert.title}</p>
                <StatusBadge severity={alert.severity} label={alert.severity.toUpperCase()} size="sm" />
              </div>
              <p className="text-xs text-gray-600 break-words">{alert.description}</p>
              <div className="flex items-center justify-between gap-2">
                <p className="text-[11px] text-gray-500">{alert.location}</p>
                <button
                  onClick={() => {
                    void handleAck(alert.id);
                  }}
                  disabled={ackPendingId === alert.id}
                  className="text-xs rounded-md border border-gray-200 px-2 py-1 hover:bg-gray-50 disabled:text-gray-400"
                >
                  {ackPendingId === alert.id ? 'Ack...' : 'Acknowledge'}
                </button>
              </div>
            </div>
          ))}
        </section>

        <section className="rounded-lg border border-gray-200 bg-white p-3 space-y-2">
          <div className="flex items-center gap-2">
            <Camera className="w-4 h-4 text-blue-600" />
            <h2 className="text-sm font-semibold">Camera Live Preview</h2>
          </div>
          <div className="grid grid-cols-1 gap-3">
            {cameraFeeds.map((feed) => (
              <div key={feed.nodeId} className="rounded-lg overflow-hidden border border-gray-200">
                <div className="relative bg-gray-900 aspect-video">
                  {feed.streamAvailable && feed.streamPath ? (
                    <img
                      src={`${feed.streamPath}${feed.streamPath.includes('?') ? '&' : '?'}face_debug=1`}
                      alt={`${feed.location} live preview`}
                      className="absolute inset-0 h-full w-full object-cover"
                    />
                  ) : (
                    <div className="absolute inset-0 flex items-center justify-center text-gray-400 text-sm">
                      Stream unavailable
                    </div>
                  )}
                </div>
                <div className="p-2.5 flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-900">{feed.location}</p>
                    <p className="text-[11px] text-gray-500 font-mono">{feed.nodeId}</p>
                  </div>
                  <StatusBadge severity={feed.status} label={feed.status.toUpperCase()} size="sm" />
                </div>
              </div>
            ))}
            {cameraFeeds.length === 0 && (
              <p className="text-sm text-gray-600">No camera feeds reported.</p>
            )}
          </div>
        </section>

        <section className="rounded-lg border border-gray-200 bg-white p-3 space-y-2">
          <div className="flex items-center gap-2">
            <Wifi className="w-4 h-4 text-green-600" />
            <h2 className="text-sm font-semibold">Node & Service Health</h2>
          </div>
          <div className="space-y-1.5">
            {sensorStatuses.slice(0, 8).map((node) => (
              <div key={node.id} className="flex items-center justify-between gap-2 text-sm">
                <span className="text-gray-700 truncate">{node.name}</span>
                <StatusBadge severity={node.status} label={node.status.toUpperCase()} size="sm" />
              </div>
            ))}
            {serviceStatuses.map((service) => (
              <div key={service.id} className="flex items-center justify-between gap-2 text-sm">
                <span className="text-gray-700 truncate">{service.name}</span>
                <StatusBadge severity={service.status} label={service.status.toUpperCase()} size="sm" />
              </div>
            ))}
          </div>
        </section>

        <a
          href="/dashboard"
          className="inline-flex items-center justify-center w-full rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          Open Full Dashboard
        </a>
      </main>
    </div>
  );
}
