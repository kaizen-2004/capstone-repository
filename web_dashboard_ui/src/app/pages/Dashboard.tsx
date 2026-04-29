import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router';
import { Download, Filter, ChevronRight } from 'lucide-react';
import { AlertCard } from '../components/AlertCard';
import { KPICard } from '../components/KPICard';
import { CameraPreview } from '../components/CameraPreview';
import { fetchDailyStats, fetchLiveEvents, fetchLiveNodes } from '../data/liveApi';
import { systemProfile } from '../data/appConfig';
import type { Alert, CameraFeed, KPI, SensorStatus } from '../data/types';

type FilterType = 'all' | 'intruder' | 'fire' | 'sensor' | 'authorized' | 'system';

function toCsvCell(value: unknown): string {
  const raw = String(value ?? '');
  if (/[",\n]/.test(raw)) {
    return `"${raw.replace(/"/g, '""')}"`;
  }
  return raw;
}

function downloadCsv(fileName: string, rows: Array<Array<unknown>>): void {
  const csv = rows.map((row) => row.map((cell) => toCsvCell(cell)).join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = fileName;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

function buildKpis(
  sensorStatuses: SensorStatus[],
  dailyStats: Awaited<ReturnType<typeof fetchDailyStats>>,
): KPI[] {
  const latest = dailyStats[dailyStats.length - 1];
  const previous = dailyStats[dailyStats.length - 2];
  const onlineNodes = sensorStatuses.filter((node) => node.status === 'online').length;
  return [
    {
      label: 'Authorized Faces',
      value: latest?.authorizedFaces ?? 0,
      trend: latest && previous ? latest.authorizedFaces - previous.authorizedFaces : undefined,
      icon: 'UserCheck',
      subtitle: 'Today',
    },
    {
      label: 'Non-Authorized Detections',
      value: latest?.unknownDetections ?? 0,
      trend: latest && previous ? latest.unknownDetections - previous.unknownDetections : undefined,
      icon: 'UserX',
      subtitle: 'Today',
    },
    {
      label: 'Fire Fusion Alerts',
      value: latest?.fireAlerts ?? 0,
      trend: latest && previous ? latest.fireAlerts - previous.fireAlerts : undefined,
      icon: 'ShieldAlert',
      subtitle: 'Today',
    },
    {
      label: 'Active Nodes',
      value: onlineNodes,
      icon: 'Activity',
      subtitle: `${sensorStatuses.length} total nodes`,
    },
  ];
}

export function Dashboard() {
  const navigate = useNavigate();
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [events, setEvents] = useState<Alert[]>([]);
  const [kpis, setKpis] = useState<KPI[]>([]);
  const [cameraFeeds, setCameraFeeds] = useState<CameraFeed[]>([]);
  const [eventFilter, setEventFilter] = useState<FilterType>('all');
  const [isExporting, setIsExporting] = useState(false);
  const [exportMessage, setExportMessage] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState('');

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const [eventsLive, stats, nodesLive] = await Promise.all([
          fetchLiveEvents(250),
          fetchDailyStats(2),
          fetchLiveNodes(),
        ]);
        if (cancelled) {
          return;
        }
        setAlerts(eventsLive.alerts);
        setEvents(eventsLive.events);
        setCameraFeeds(nodesLive.cameraFeeds);
        setKpis(buildKpis(nodesLive.sensorStatuses, stats));
        setLoadError('');
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Unable to load live dashboard data.';
        if (!cancelled) {
          setLoadError(message);
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    void load();
    const timer = window.setInterval(() => {
      void load();
    }, 12000);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const handleAcknowledge = async (id: string) => {
    setAlerts((prev) =>
      prev.map((alert) => (alert.id === id ? { ...alert, acknowledged: true } : alert)),
    );

    const numericId = Number.parseInt(id.replace(/^alert-/, ''), 10);
    if (!Number.isFinite(numericId) || numericId <= 0) {
      return;
    }
    try {
      const body = new URLSearchParams({ status: 'ACK' });
      await fetch(`/ack/${numericId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: body.toString(),
      });
    } catch {
      // Local optimistic update already applied.
    }
  };

  const timelineEvents = useMemo(
    () =>
      [...alerts, ...events].sort(
        (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
      ),
    [alerts, events],
  );

  const criticalAlerts = alerts.filter((alert) => !alert.acknowledged && alert.severity === 'critical');
  const warningAlerts = alerts.filter((alert) => !alert.acknowledged && alert.severity === 'warning');

  const filteredEvents =
    eventFilter === 'all'
      ? timelineEvents
      : timelineEvents.filter((event) => event.type === eventFilter);
  const activeAlertCount = criticalAlerts.length + warningAlerts.length;
  const latestEventTimestamp = timelineEvents[0]?.timestamp;
  const liveLocations = useMemo(() => {
    const locations = [...cameraFeeds.map((feed) => feed.location), ...timelineEvents.map((event) => event.location)]
      .map((location) => String(location || '').trim())
      .filter(Boolean);
    return Array.from(new Set(locations));
  }, [cameraFeeds, timelineEvents]);
  const monitoringScope = liveLocations.length > 0 ? liveLocations.join(' and ') : 'reported live areas';

  const handleExportDailySummary = async () => {
    if (isExporting) {
      return;
    }
    setIsExporting(true);
    setExportMessage('');

    try {
      const [statsRows, eventsLive, nodesLive] = await Promise.all([
        fetchDailyStats(1),
        fetchLiveEvents(500),
        fetchLiveNodes(),
      ]);

      const today = statsRows[0];
      const mergedEvents = [...eventsLive.alerts, ...eventsLive.events].sort(
        (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
      );
      const activeAlerts = eventsLive.alerts.filter((alert) => !alert.acknowledged);

      const now = new Date();
      const fileDate = now.toISOString().slice(0, 10);
      const rows: Array<Array<unknown>> = [];

      rows.push(['Condo Monitoring Dashboard - Daily Summary']);
      rows.push(['Generated At', now.toISOString()]);
      rows.push([
        'Monitored Areas',
        Array.from(
          new Set(
            nodesLive.sensorStatuses
              .map((node) => String(node.location || '').trim())
              .filter(Boolean),
          ),
        ).join(' + ') || 'No live areas reported',
      ]);
      rows.push([]);

      rows.push(['Summary']);
      rows.push(['Metric', 'Value']);
      rows.push(['Authorized Faces', today?.authorizedFaces ?? 0]);
      rows.push(['Unknown Detections', today?.unknownDetections ?? 0]);
      rows.push(['Fire Fusion Alerts', today?.fireAlerts ?? 0]);
      rows.push(['Intruder Fusion Alerts', today?.intruderAlerts ?? 0]);
      rows.push(['Online Nodes', nodesLive.sensorStatuses.filter((node) => node.status === 'online').length]);
      rows.push(['Total Nodes', nodesLive.sensorStatuses.length]);
      rows.push([]);

      rows.push(['Active Alerts']);
      rows.push(['Timestamp', 'Severity', 'Code', 'Title', 'Location', 'Source Node', 'Description']);
      if (activeAlerts.length === 0) {
        rows.push(['-', '-', '-', 'No active alerts', '-', '-', '-']);
      } else {
        activeAlerts.slice(0, 200).forEach((alert) => {
          rows.push([
            alert.timestamp,
            alert.severity,
            alert.eventCode,
            alert.title,
            alert.location,
            alert.sourceNode,
            alert.description,
          ]);
        });
      }
      rows.push([]);

      rows.push(['Recent Events']);
      rows.push(['Timestamp', 'Severity', 'Code', 'Type', 'Title', 'Location', 'Source Node', 'Acknowledged']);
      if (mergedEvents.length === 0) {
        rows.push(['-', '-', '-', '-', 'No events found', '-', '-', '-']);
      } else {
        mergedEvents.slice(0, 500).forEach((event) => {
          rows.push([
            event.timestamp,
            event.severity,
            event.eventCode,
            event.type,
            event.title,
            event.location,
            event.sourceNode,
            event.acknowledged ? 'yes' : 'no',
          ]);
        });
      }

      downloadCsv(`daily_summary_${fileDate}.csv`, rows);
      setExportMessage('Daily summary exported.');
      window.setTimeout(() => setExportMessage(''), 3000);
    } catch {
      setExportMessage('Export failed. Try again.');
      window.setTimeout(() => setExportMessage(''), 3500);
    } finally {
      setIsExporting(false);
    }
  };

  const formatLastUpdate = (timestamp?: string) => {
    if (!timestamp) {
      return 'No recent events';
    }
    const date = new Date(timestamp);
    const diffMs = Date.now() - date.getTime();
    if (!Number.isFinite(diffMs) || diffMs < 0) {
      return date.toLocaleString();
    }
    const diffSeconds = Math.floor(diffMs / 1000);
    if (diffSeconds < 60) {
      return `${diffSeconds}s ago`;
    }
    const diffMinutes = Math.floor(diffSeconds / 60);
    if (diffMinutes < 60) {
      return `${diffMinutes}m ago`;
    }
    const diffHours = Math.floor(diffMinutes / 60);
    if (diffHours < 24) {
      return `${diffHours}h ago`;
    }
    return date.toLocaleString();
  };

  return (
    <div className="p-3 md:p-8 space-y-5 md:space-y-7">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl md:text-2xl font-semibold text-gray-900">Dashboard Overview</h2>
          <p className="text-sm md:text-base text-gray-600 mt-1">
            Focused monitoring for {monitoringScope}.
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
            <span className="inline-flex items-center rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 font-medium text-blue-700">
              Active alerts: {activeAlertCount}
            </span>
            <span className="inline-flex items-center rounded-full border border-orange-200 bg-orange-50 px-2.5 py-1 font-medium text-orange-700">
              Warnings: {warningAlerts.length}
            </span>
            <span className="inline-flex items-center rounded-full border border-gray-200 bg-gray-50 px-2.5 py-1 font-medium text-gray-700">
              Last update: {formatLastUpdate(latestEventTimestamp)}
            </span>
          </div>
        </div>
        <button
          onClick={() => void handleExportDailySummary()}
          disabled={isExporting}
          className="flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 text-white border border-blue-600 rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
        >
          <Download className="w-4 h-4" />
          <span className="hidden sm:inline">{isExporting ? 'Exporting...' : 'Export Daily Summary'}</span>
          <span className="sm:hidden">{isExporting ? '...' : 'Export'}</span>
        </button>
      </div>
      {exportMessage && (
        <div className="text-sm text-gray-700">{exportMessage}</div>
      )}
      {loadError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Live data unavailable: {loadError}
        </div>
      )}
      {isLoading && (
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-blue-800">
          Loading live dashboard data...
        </div>
      )}

      <div className="bg-white rounded-lg border border-gray-200 p-4 md:p-5 grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <p className="text-xs uppercase tracking-wide text-gray-500">Transport</p>
          <p className="text-sm font-medium text-gray-900 mt-1">{systemProfile.transport}</p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-gray-500">Sensor API Contract</p>
          <p className="text-sm font-medium text-gray-900 mt-1">{systemProfile.apiContract}</p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-gray-500">Live Timeline Size</p>
          <p className="text-sm font-medium text-gray-900 mt-1">{timelineEvents.length} events</p>
        </div>
      </div>

      {(criticalAlerts.length > 0 || warningAlerts.length > 0) && (
        <div className="space-y-3">
          <h3 className="text-base md:text-lg font-semibold text-gray-900">Active Alerts</h3>
          <div className="space-y-3">
            {criticalAlerts.map((alert) => (
              <AlertCard
                key={alert.id}
                alert={alert}
                onAcknowledge={handleAcknowledge}
                onClick={() => navigate('/events')}
              />
            ))}
            {warningAlerts.map((alert) => (
              <AlertCard
                key={alert.id}
                alert={alert}
                onAcknowledge={handleAcknowledge}
                onClick={() => navigate('/events')}
              />
            ))}
          </div>
        </div>
      )}
      {criticalAlerts.length === 0 && warningAlerts.length === 0 && (
        <div className="rounded-lg border border-green-200 bg-green-50 p-4 text-sm text-green-800">
          No active critical or warning alerts right now.
        </div>
      )}

      <div className="space-y-3">
        <h3 className="text-base md:text-lg font-semibold text-gray-900">Today's Summary</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 md:gap-6">
          {kpis.map((kpi) => (
            <KPICard key={kpi.label} {...kpi} />
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 md:gap-6">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base md:text-lg font-semibold text-gray-900">Camera Feeds</h3>
            <span className="text-xs text-gray-500">{cameraFeeds.length} live feed{cameraFeeds.length === 1 ? '' : 's'}</span>
          </div>
          {cameraFeeds.map((feed) => (
            <CameraPreview
              key={feed.nodeId}
              location={feed.location}
              status={feed.status}
              nodeId={feed.nodeId}
              caption={`${feed.quality} • ${feed.fps} FPS • ${feed.latencyMs} ms`}
              onViewLive={() => navigate('/live')}
            />
          ))}
          {cameraFeeds.length === 0 && !isLoading && (
            <div className="rounded-lg border border-gray-200 bg-white p-4 text-sm text-gray-600">
              No live camera feeds reported by the backend.
            </div>
          )}
        </div>

        <div className="lg:col-span-2 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <h3 className="text-base md:text-lg font-semibold text-gray-900">Recent Events</h3>
            <div className="flex items-center gap-2 w-full sm:w-auto">
              <Filter className="w-4 h-4 text-gray-500" />
              <select
                value={eventFilter}
                onChange={(e) => setEventFilter(e.target.value as FilterType)}
                className="w-full sm:w-auto px-3 py-1.5 bg-white border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="all">All Events</option>
                <option value="intruder">Intruder</option>
                <option value="fire">Fire</option>
                <option value="sensor">Sensor</option>
                <option value="authorized">Authorized</option>
                <option value="system">System</option>
              </select>
            </div>
          </div>

          <div className="rounded-lg border border-gray-200 bg-white p-3 md:p-4 space-y-3">
            <div className="flex items-center justify-between text-xs text-gray-600">
              <span>{filteredEvents.length} matching events</span>
              {eventFilter !== 'all' && (
                <button
                  onClick={() => setEventFilter('all')}
                  className="px-2 py-1 rounded-md border border-gray-200 hover:bg-gray-50"
                >
                  Clear filter
                </button>
              )}
            </div>
            {filteredEvents.slice(0, 5).map((event) => (
              <AlertCard key={event.id} alert={event} onClick={() => navigate('/events')} />
            ))}
            {filteredEvents.length === 0 && (
              <p className="text-sm text-gray-600 py-2">No events match the selected filter.</p>
            )}
          </div>

          <button
            onClick={() => navigate('/events')}
            className="w-full py-3 bg-white border border-gray-200 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors flex items-center justify-center gap-2"
          >
            View All Events
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
