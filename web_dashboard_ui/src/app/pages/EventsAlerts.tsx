import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router';
import { Search, Filter, Calendar, X, Image as ImageIcon } from 'lucide-react';
import { fetchLiveEvents } from '../data/liveApi';
import { recentEvents as fallbackRecentEvents } from '../data/mockData';
import type { Alert, SeverityLevel, EventType } from '../data/mockData';
import { StatusBadge } from '../components/StatusBadge';

type TimeRange = '24h' | '7d' | '30d' | 'all';

const DEFAULT_TIME_RANGE: TimeRange = '7d';
const TIME_RANGE_DAYS: Record<Exclude<TimeRange, 'all'>, number> = {
  '24h': 1,
  '7d': 7,
  '30d': 30,
};

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

export function EventsAlerts() {
  const navigate = useNavigate();
  const [events, setEvents] = useState<Alert[]>(fallbackRecentEvents);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedSeverity, setSelectedSeverity] = useState<SeverityLevel | 'all'>('all');
  const [selectedType, setSelectedType] = useState<EventType | 'all'>('all');
  const [selectedTimeRange, setSelectedTimeRange] = useState<TimeRange>(DEFAULT_TIME_RANGE);
  const [selectedEvent, setSelectedEvent] = useState<Alert | null>(null);
  const [ackPendingId, setAckPendingId] = useState<string | null>(null);

  const handleAcknowledge = async (id: string) => {
    if (!id.startsWith('alert-')) {
      return;
    }

    setAckPendingId(id);
    setEvents((prev) => prev.map((event) => (event.id === id ? { ...event, acknowledged: true } : event)));
    setSelectedEvent((prev) => (prev && prev.id === id ? { ...prev, acknowledged: true } : prev));

    const numericId = Number.parseInt(id.replace('alert-', ''), 10);
    if (!Number.isFinite(numericId) || numericId <= 0) {
      setAckPendingId(null);
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
      // Keep optimistic UI state; backend will refresh from live API on next poll.
    } finally {
      setAckPendingId(null);
    }
  };

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const payload = await fetchLiveEvents(500);
        if (cancelled) {
          return;
        }
        setEvents(
          [...payload.alerts, ...payload.events].sort(
            (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
          ),
        );
      } catch {
        // Keep fallback data if API is unavailable.
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

  const filteredEvents = useMemo(
    () => {
      const keyword = searchQuery.toLowerCase().trim();
      const days = selectedTimeRange === 'all' ? null : TIME_RANGE_DAYS[selectedTimeRange];
      const cutoffMs = days == null ? Number.NEGATIVE_INFINITY : Date.now() - days * 24 * 60 * 60 * 1000;

      return events.filter((event) => {
        const matchesSearch =
          event.title.toLowerCase().includes(keyword) ||
          event.description.toLowerCase().includes(keyword) ||
          event.eventCode.toLowerCase().includes(keyword) ||
          event.sourceNode.toLowerCase().includes(keyword);
        const matchesSeverity = selectedSeverity === 'all' || event.severity === selectedSeverity;
        const matchesType = selectedType === 'all' || event.type === selectedType;
        const eventTimeMs = new Date(event.timestamp).getTime();
        const matchesTime = days == null || (Number.isFinite(eventTimeMs) && eventTimeMs >= cutoffMs);
        return matchesSearch && matchesSeverity && matchesType && matchesTime;
      });
    },
    [events, searchQuery, selectedSeverity, selectedType, selectedTimeRange],
  );
  const hasActiveFilters =
    searchQuery.trim().length > 0 ||
    selectedSeverity !== 'all' ||
    selectedType !== 'all' ||
    selectedTimeRange !== DEFAULT_TIME_RANGE;

  const formatDateTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const handleExportSelectedEvent = (event: Alert) => {
    const rows: Array<Array<unknown>> = [
      ['Event Details Export'],
      ['Exported At', new Date().toISOString()],
      [],
      ['Field', 'Value'],
      ['ID', event.id],
      ['Timestamp', event.timestamp],
      ['Severity', event.severity],
      ['Type', event.type],
      ['Event Code', event.eventCode],
      ['Title', event.title],
      ['Description', event.description],
      ['Location', event.location],
      ['Source Node', event.sourceNode],
      ['Acknowledged', event.acknowledged ? 'yes' : 'no'],
      ['Response Time (ms)', event.responseTimeMs ?? ''],
      ['Confidence (%)', event.confidence ?? ''],
      ['Fusion Evidence', (event.fusionEvidence || []).join(' | ')],
    ];
    const stamp = new Date().toISOString().replace(/[:.]/g, '-');
    downloadCsv(`event-${event.id}-${stamp}.csv`, rows);
  };

  const handleOpenCameraFeed = () => {
    setSelectedEvent(null);
    navigate('/live');
  };

  const clearFilters = () => {
    setSearchQuery('');
    setSelectedSeverity('all');
    setSelectedType('all');
    setSelectedTimeRange(DEFAULT_TIME_RANGE);
  };

  return (
    <div className="p-3 sm:p-4 md:p-8 space-y-4 md:space-y-6 overflow-x-hidden">
      <div>
        <h2 className="text-xl md:text-2xl font-semibold text-gray-900">Events & Alerts</h2>
        <p className="text-gray-600 mt-1">
          Search event history by fusion result, event code, severity, and source node.
        </p>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-3 md:p-4">
        <div className="flex flex-col xl:flex-row gap-3">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Search event code, title, source node..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto">
            <Filter className="w-4 h-4 text-gray-500" />
            <select
              value={selectedSeverity}
              onChange={(e) => setSelectedSeverity(e.target.value as SeverityLevel | 'all')}
              className="w-full sm:w-auto px-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">All Severities</option>
              <option value="critical">Critical</option>
              <option value="warning">Warning</option>
              <option value="normal">Normal</option>
              <option value="info">Info</option>
            </select>
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto">
            <Filter className="w-4 h-4 text-gray-500" />
            <select
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value as EventType | 'all')}
              className="w-full sm:w-auto px-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">All Types</option>
              <option value="intruder">Intruder</option>
              <option value="fire">Fire</option>
              <option value="sensor">Sensor</option>
              <option value="authorized">Authorized</option>
              <option value="system">System</option>
            </select>
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto">
            <Calendar className="w-4 h-4" />
            <select
              value={selectedTimeRange}
              onChange={(e) => setSelectedTimeRange(e.target.value as TimeRange)}
              className="w-full sm:w-auto px-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="24h">Last 24 Hours</option>
              <option value="7d">Last 7 Days</option>
              <option value="30d">Last 30 Days</option>
              <option value="all">All Time</option>
            </select>
          </div>
        </div>
        <div className="mt-3 pt-3 border-t border-gray-100 flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs md:text-sm text-gray-600">
            Showing <span className="font-semibold text-gray-900">{filteredEvents.length}</span> events
          </p>
          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="text-xs md:text-sm px-3 py-1.5 rounded-md border border-gray-200 text-gray-700 hover:bg-gray-50 transition-colors"
            >
              Clear filters
            </button>
          )}
        </div>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <div className="lg:hidden divide-y divide-gray-200">
          {filteredEvents.map((event) => (
            <button
              key={event.id}
              onClick={() => setSelectedEvent(event)}
              className="w-full text-left p-4 space-y-2 hover:bg-gray-50 transition-colors"
            >
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs text-gray-500">{formatDateTime(event.timestamp)}</p>
                <StatusBadge severity={event.severity} label={event.severity.toUpperCase()} size="sm" />
              </div>

              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-gray-900 break-words">{event.eventCode}</p>
                  <p className="text-sm font-medium text-gray-900 mt-1 break-words">{event.title}</p>
                  <p className="text-sm text-gray-600 mt-1 break-words">{event.description}</p>
                </div>
              </div>

              <div className="text-xs text-gray-600 flex flex-wrap items-center gap-x-2 gap-y-1">
                <span>{event.location}</span>
                <span className="text-gray-400">|</span>
                <span className="font-mono break-all">{event.sourceNode}</span>
              </div>

              <div>
                {event.acknowledged ? (
                  <span className="text-xs text-gray-600">Acknowledged</span>
                ) : (
                  <span className="text-xs font-medium text-orange-600">Pending Review</span>
                )}
              </div>
            </button>
          ))}
        </div>

        <div className="hidden lg:block overflow-x-auto">
          <table className="w-full min-w-[860px]">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-600 uppercase tracking-wider">
                  Time
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-600 uppercase tracking-wider">
                  Code
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-600 uppercase tracking-wider">
                  Event
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-600 uppercase tracking-wider">
                  Location
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-600 uppercase tracking-wider">
                  Source Node
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-600 uppercase tracking-wider">
                  Severity
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-600 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-600 uppercase tracking-wider">
                  Action
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {filteredEvents.map((event) => (
                <tr key={event.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {formatDateTime(event.timestamp)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    {event.eventCode}
                  </td>
                  <td className="px-6 py-4">
                    <div>
                      <p className="text-sm font-medium text-gray-900">{event.title}</p>
                      <p className="text-sm text-gray-600">{event.description}</p>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">{event.location}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-mono text-gray-700">
                    {event.sourceNode}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <StatusBadge severity={event.severity} label={event.severity.toUpperCase()} size="sm" />
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    {event.acknowledged ? (
                      <span className="text-sm text-gray-600">Acknowledged</span>
                    ) : (
                      <span className="text-sm font-medium text-orange-600">Pending Review</span>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <button
                      onClick={() => setSelectedEvent(event)}
                      className="text-sm text-blue-600 hover:text-blue-700 font-medium"
                    >
                      View Details
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {filteredEvents.length === 0 && (
          <div className="text-center py-12">
            <p className="text-gray-600">No events found matching your filters.</p>
          </div>
        )}
      </div>

      {selectedEvent && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900">Event Details</h3>
              <button
                onClick={() => setSelectedEvent(null)}
                className="p-1 hover:bg-gray-100 rounded transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-6">
              <div className="space-y-4">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h4 className="text-xl font-semibold text-gray-900">{selectedEvent.title}</h4>
                    <p className="text-gray-600 mt-1">{selectedEvent.description}</p>
                  </div>
                  <StatusBadge
                    severity={selectedEvent.severity}
                    label={selectedEvent.severity.toUpperCase()}
                    size="md"
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-4 border-t border-gray-200">
                  <div>
                    <p className="text-sm text-gray-600">Timestamp</p>
                    <p className="text-sm font-medium text-gray-900 mt-1">
                      {new Date(selectedEvent.timestamp).toLocaleString()}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600">Location</p>
                    <p className="text-sm font-medium text-gray-900 mt-1">{selectedEvent.location}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600">Source Node</p>
                    <p className="text-sm font-mono font-medium text-gray-900 mt-1">{selectedEvent.sourceNode}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600">Event Code</p>
                    <p className="text-sm font-medium text-gray-900 mt-1">{selectedEvent.eventCode}</p>
                  </div>
                  {selectedEvent.responseTimeMs && (
                    <div>
                      <p className="text-sm text-gray-600">Response Time</p>
                      <p className="text-sm font-medium text-gray-900 mt-1">
                        {(selectedEvent.responseTimeMs / 1000).toFixed(2)}s
                      </p>
                    </div>
                  )}
                  {selectedEvent.confidence && (
                    <div>
                      <p className="text-sm text-gray-600">Confidence</p>
                      <p className="text-sm font-medium text-gray-900 mt-1">{selectedEvent.confidence}%</p>
                    </div>
                  )}
                </div>
              </div>

              <div>
                <p className="text-sm font-medium text-gray-900 mb-2">Camera Snapshot</p>
                <div className="bg-gray-900 aspect-video rounded-lg flex items-center justify-center">
                  <ImageIcon className="w-12 h-12 text-gray-600" />
                </div>
              </div>

              <div>
                <p className="text-sm font-medium text-gray-900 mb-2">Fusion / Evidence</p>
                <div className="bg-gray-50 rounded-lg p-4 space-y-2">
                  {selectedEvent.fusionEvidence && selectedEvent.fusionEvidence.length > 0 ? (
                    selectedEvent.fusionEvidence.map((evidence) => (
                      <p key={evidence} className="text-sm text-gray-700">
                        • {evidence}
                      </p>
                    ))
                  ) : (
                    <p className="text-sm text-gray-600">
                      No multi-sensor fusion evidence attached to this event.
                    </p>
                  )}
                </div>
              </div>

              <div className="flex flex-wrap gap-3 pt-4 border-t border-gray-200">
                {!selectedEvent.acknowledged && selectedEvent.id.startsWith('alert-') && (
                  <button
                    onClick={() => void handleAcknowledge(selectedEvent.id)}
                    disabled={ackPendingId === selectedEvent.id}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed"
                  >
                    {ackPendingId === selectedEvent.id ? 'Acknowledging...' : 'Acknowledge Alert'}
                  </button>
                )}
                <button
                  onClick={() => handleExportSelectedEvent(selectedEvent)}
                  className="px-4 py-2 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  Export Data
                </button>
                <button
                  onClick={handleOpenCameraFeed}
                  className="px-4 py-2 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  Open Camera Feed
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
