import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router';
import { CalendarDays, Download, Filter, ChevronRight } from 'lucide-react';
import { AlertCard } from '../components/AlertCard';
import { KPICard } from '../components/KPICard';
import { CameraPreview } from '../components/CameraPreview';
import { fetchDailyStats, fetchDailySummaryReport, fetchLiveEvents, fetchLiveNodes } from '../data/liveApi';
import { systemProfile } from '../data/appConfig';
import type { Alert, CameraFeed, KPI, SensorStatus } from '../data/types';

type FilterType = 'all' | 'intruder' | 'fire' | 'sensor' | 'authorized' | 'system';

function currentDateInputValue(): string {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 10);
}

function downloadBlob(fileName: string, blob: Blob): void {
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
  const [reportDate, setReportDate] = useState(currentDateInputValue);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState('');

  useEffect(() => {
    let cancelled = false;
    let controller: AbortController | null = null;
    let timer: number | null = null;

    const load = async () => {
      controller = new AbortController();
      try {
        const [eventsLive, stats, nodesLive] = await Promise.all([
          fetchLiveEvents(250, controller.signal),
          fetchDailyStats(2, controller.signal),
          fetchLiveNodes(controller.signal),
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
        if (cancelled) {
          return;
        }
        const message = error instanceof Error ? error.message : 'Unable to load live dashboard data.';
        if (!cancelled) {
          setLoadError(message);
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
          timer = window.setTimeout(() => {
            void load();
          }, 12000);
        }
        controller = null;
      }
    };

    void load();

    return () => {
      cancelled = true;
      controller?.abort();
      if (timer !== null) {
        window.clearTimeout(timer);
      }
    };
  }, []);

  const timelineEvents = useMemo(
    () =>
      [...events].sort(
        (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
      ),
    [events],
  );

  const activeAlerts = alerts.filter((alert) => !alert.acknowledged);
  const warningAlerts = activeAlerts.filter((alert) => alert.severity === 'warning');

  const filteredEvents =
    eventFilter === 'all'
      ? timelineEvents
      : timelineEvents.filter((event) => event.type === eventFilter);
  const activeAlertCount = activeAlerts.length;
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
    const selectedDate = reportDate || currentDateInputValue();
    setIsExporting(true);
    setExportMessage('');

    try {
      const report = await fetchDailySummaryReport(selectedDate);
      downloadBlob(`intruflare_daily_report_${selectedDate}.pdf`, report);
      setExportMessage('Daily PDF report exported.');
      window.setTimeout(() => setExportMessage(''), 3000);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Export failed. Try again.';
      setExportMessage(message);
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
            <button
              type="button"
              onClick={() => navigate('/events')}
              className="inline-flex items-center rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 font-medium text-blue-700 transition-colors hover:bg-blue-100"
            >
              Active alerts: {activeAlertCount}
            </button>
            <span className="inline-flex items-center rounded-full border border-orange-200 bg-orange-50 px-2.5 py-1 font-medium text-orange-700">
              Warnings: {warningAlerts.length}
            </span>
            <span className="inline-flex items-center rounded-full border border-gray-200 bg-gray-50 px-2.5 py-1 font-medium text-gray-700">
              Last update: {formatLastUpdate(latestEventTimestamp)}
            </span>
          </div>
        </div>
        <div className="flex flex-col sm:flex-row sm:items-end gap-2 w-full sm:w-auto">
          <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
            Report date
            <span className="relative">
              <CalendarDays className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
              <input
                type="date"
                value={reportDate}
                onChange={(event) => setReportDate(event.target.value)}
                className="w-full sm:w-40 rounded-lg border border-gray-300 bg-white py-2 pl-9 pr-3 text-sm text-gray-900 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
              />
            </span>
          </label>
          <button
            onClick={() => void handleExportDailySummary()}
            disabled={isExporting}
            className="flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 text-white border border-blue-600 rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
          >
            <Download className="w-4 h-4" />
            <span className="hidden sm:inline">{isExporting ? 'Exporting...' : 'Export Daily Report'}</span>
            <span className="sm:hidden">{isExporting ? '...' : 'Export'}</span>
          </button>
        </div>
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
