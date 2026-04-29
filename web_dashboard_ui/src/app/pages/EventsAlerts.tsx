import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router';
import { Search, Filter, Calendar, X, Image as ImageIcon } from 'lucide-react';
import { fetchAlertReviewHistory, fetchLiveEvents, updateAlertReview, type AlertReviewHistoryEntry } from '../data/liveApi';
import type { Alert, SeverityLevel, EventType } from '../data/types';
import { StatusBadge } from '../components/StatusBadge';

type TimeRange = '24h' | '7d' | '30d' | 'all';
type ReviewView = 'queue' | 'history';
type ReviewStatus = 'needs_review' | 'confirmed' | 'false_positive' | 'resolved' | 'archived';

const DEFAULT_TIME_RANGE: TimeRange = '7d';
const TIME_RANGE_DAYS: Record<Exclude<TimeRange, 'all'>, number> = {
  '24h': 1,
  '7d': 7,
  '30d': 30,
};

const displayEventCode = (eventCode: string) =>
  eventCode === 'UNKNOWN' ? 'NON-AUTHORIZED' : eventCode;

const formatReviewStatusLabel = (value: string) =>
  value
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase())
    .trim();

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
  const [events, setEvents] = useState<Alert[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedSeverity, setSelectedSeverity] = useState<SeverityLevel | 'all'>('all');
  const [selectedType, setSelectedType] = useState<EventType | 'all'>('all');
  const [reviewView, setReviewView] = useState<ReviewView>('queue');
  const [selectedReviewStatus, setSelectedReviewStatus] = useState<ReviewStatus | 'all'>('all');
  const [selectedTimeRange, setSelectedTimeRange] = useState<TimeRange>(DEFAULT_TIME_RANGE);
  const [selectedEvent, setSelectedEvent] = useState<Alert | null>(null);
  const [snapshotLoadFailed, setSnapshotLoadFailed] = useState(false);
  const [ackPendingId, setAckPendingId] = useState<string | null>(null);
  const [reviewStatusDraft, setReviewStatusDraft] = useState<'needs_review' | 'confirmed' | 'false_positive' | 'resolved' | 'archived'>('needs_review');
  const [reviewNoteDraft, setReviewNoteDraft] = useState('');
  const [reviewSaving, setReviewSaving] = useState(false);
  const [reviewFeedback, setReviewFeedback] = useState('');
  const [reviewError, setReviewError] = useState('');
  const [reviewHistory, setReviewHistory] = useState<AlertReviewHistoryEntry[]>([]);
  const [reviewHistoryLoading, setReviewHistoryLoading] = useState(false);
  const [selectedAlertIds, setSelectedAlertIds] = useState<Set<string>>(new Set());
  const [bulkReviewStatus, setBulkReviewStatus] = useState<ReviewStatus>('resolved');
  const [bulkReviewNote, setBulkReviewNote] = useState('');
  const [bulkSaving, setBulkSaving] = useState(false);
  const [bulkResult, setBulkResult] = useState<{ updated: number; failed: number } | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState('');

  const handleAcknowledge = async (id: string) => {
    setAckPendingId(id);
    setEvents((prev) => prev.map((event) => (event.id === id ? { ...event, acknowledged: true } : event)));
    setSelectedEvent((prev) => (prev && prev.id === id ? { ...prev, acknowledged: true } : prev));

    const numericId = Number.parseInt(id.replace(/^alert-/, ''), 10);
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
        setLoadError('');
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Unable to load live events.';
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

  useEffect(() => {
    setSnapshotLoadFailed(false);
  }, [selectedEvent?.id, selectedEvent?.snapshotPath]);

  useEffect(() => {
    if (!selectedEvent) {
      return;
    }
    setReviewStatusDraft(selectedEvent.reviewStatus || 'needs_review');
    setReviewNoteDraft(selectedEvent.reviewNote || '');
    setReviewFeedback('');
    setReviewError('');

    if (!selectedEvent.id.startsWith('alert-')) {
      setReviewHistory([]);
      return;
    }

    const alertId = Number.parseInt(selectedEvent.id.replace(/^alert-/, ''), 10);
    if (!Number.isFinite(alertId) || alertId <= 0) {
      setReviewHistory([]);
      return;
    }

    let cancelled = false;
    setReviewHistoryLoading(true);
    void fetchAlertReviewHistory(alertId)
      .then((entries) => {
        if (!cancelled) {
          setReviewHistory(entries);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setReviewHistory([]);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setReviewHistoryLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [selectedEvent]);

  const handleSaveReview = async () => {
    if (!selectedEvent || !selectedEvent.id.startsWith('alert-')) {
      setReviewError('This record cannot be reviewed as an alert.');
      return;
    }
    const alertId = Number.parseInt(selectedEvent.id.replace(/^alert-/, ''), 10);
    if (!Number.isFinite(alertId) || alertId <= 0) {
      setReviewError('Invalid alert ID. Refresh the page and try again.');
      return;
    }

    setReviewSaving(true);
    setReviewFeedback('');
    setReviewError('');
    try {
      const result = await updateAlertReview(alertId, reviewStatusDraft, reviewNoteDraft);
      setEvents((prev) =>
        prev.map((item) => (item.id === selectedEvent.id ? { ...item, ...result.alert } : item)),
      );
      setSelectedEvent((prev) =>
        prev && prev.id === selectedEvent.id ? { ...prev, ...result.alert } : prev,
      );
      if (Number.isFinite(alertId) && alertId > 0) {
        const entries = await fetchAlertReviewHistory(alertId);
        setReviewHistory(entries);
      }
      setReviewFeedback('Review saved.');
      setSelectedAlertIds((prev) => {
        if (!prev.has(selectedEvent.id)) {
          return prev;
        }
        const next = new Set(prev);
        next.delete(selectedEvent.id);
        return next;
      });
      if (reviewView === 'queue' && (result.alert.reviewStatus || reviewStatusDraft) !== 'needs_review') {
        setSelectedEvent(null);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to save review right now.';
      setReviewError(message);
    } finally {
      setReviewSaving(false);
    }
  };

  const toggleAlertSelection = (alertId: string, selected: boolean) => {
    setSelectedAlertIds((prev) => {
      const next = new Set(prev);
      if (selected) {
        next.add(alertId);
      } else {
        next.delete(alertId);
      }
      return next;
    });
  };

  const toggleSelectAllVisible = (selected: boolean) => {
    setSelectedAlertIds((prev) => {
      const next = new Set(prev);
      for (const event of queueAlerts) {
        if (selected) {
          next.add(event.id);
        } else {
          next.delete(event.id);
        }
      }
      return next;
    });
  };

  const handleBulkApplyReview = async () => {
    const ids = Array.from(selectedAlertIds).filter((id) => id.startsWith('alert-'));
    if (ids.length === 0) {
      return;
    }
    setBulkSaving(true);
    setBulkResult(null);
    try {
      const updates = await Promise.allSettled(
        ids.map(async (id) => {
          const numericId = Number.parseInt(id.replace(/^alert-/, ''), 10);
          if (!Number.isFinite(numericId) || numericId <= 0) {
            return null;
          }
          return updateAlertReview(numericId, bulkReviewStatus, bulkReviewNote);
        }),
      );

      const byId = new Map<string, Alert>();
      let failedCount = 0;
      for (const update of updates) {
        if (update.status !== 'fulfilled' || !update.value) {
          failedCount += 1;
          continue;
        }
        byId.set(update.value.alert.id, update.value.alert);
      }
      const updatedCount = byId.size;
      if (byId.size > 0) {
        setEvents((prev) => prev.map((item) => byId.get(item.id) || item));
        setSelectedEvent((prev) => (prev ? byId.get(prev.id) || prev : prev));
      }
      setSelectedAlertIds(new Set());
      setBulkReviewNote('');
      setBulkResult({ updated: updatedCount, failed: failedCount });
    } finally {
      setBulkSaving(false);
    }
  };

  const filteredEvents = useMemo(
    () => {
      const keyword = searchQuery.toLowerCase().trim();
      const days = selectedTimeRange === 'all' ? null : TIME_RANGE_DAYS[selectedTimeRange];
      const cutoffMs = days == null ? Number.NEGATIVE_INFINITY : Date.now() - days * 24 * 60 * 60 * 1000;

      return events.filter((event) => {
        const isAlert = event.id.startsWith('alert-');
        const reviewStatus = event.reviewStatus || 'needs_review';
        const inQueue = isAlert && reviewStatus === 'needs_review';
        if (reviewView === 'queue' && !inQueue) {
          return false;
        }
        if (reviewView === 'history' && inQueue) {
          return false;
        }

        const matchesSearch =
          event.title.toLowerCase().includes(keyword) ||
          event.description.toLowerCase().includes(keyword) ||
          event.eventCode.toLowerCase().includes(keyword) ||
          event.sourceNode.toLowerCase().includes(keyword);
        const matchesSeverity = selectedSeverity === 'all' || event.severity === selectedSeverity;
        const matchesType = selectedType === 'all' || event.type === selectedType;
        const matchesReviewStatus =
          selectedReviewStatus === 'all' ||
          (isAlert && reviewStatus === selectedReviewStatus);
        const eventTimeMs = new Date(event.timestamp).getTime();
        const matchesTime = days == null || (Number.isFinite(eventTimeMs) && eventTimeMs >= cutoffMs);
        return matchesSearch && matchesSeverity && matchesType && matchesReviewStatus && matchesTime;
      });
    },
    [events, searchQuery, selectedSeverity, selectedType, selectedReviewStatus, selectedTimeRange, reviewView],
  );
  const hasActiveFilters =
    searchQuery.trim().length > 0 ||
    selectedSeverity !== 'all' ||
    selectedType !== 'all' ||
    selectedReviewStatus !== 'all' ||
    selectedTimeRange !== DEFAULT_TIME_RANGE;

  const queueAlerts = useMemo(
    () => filteredEvents.filter((event) => event.id.startsWith('alert-')),
    [filteredEvents],
  );

  const selectedQueueCount = useMemo(
    () => queueAlerts.filter((event) => selectedAlertIds.has(event.id)).length,
    [queueAlerts, selectedAlertIds],
  );

  useEffect(() => {
    if (reviewView !== 'queue') {
      setSelectedAlertIds(new Set());
      return;
    }
    const allowedIds = new Set(queueAlerts.map((event) => event.id));
    setSelectedAlertIds((prev) => {
      const next = new Set<string>();
      for (const id of prev) {
        if (allowedIds.has(id)) {
          next.add(id);
        }
      }
      return next.size === prev.size ? prev : next;
    });
  }, [reviewView, queueAlerts]);

  const renderReviewStatus = (event: Alert) => {
    const status = (event.reviewStatus || 'needs_review') as ReviewStatus;
    if (!event.id.startsWith('alert-')) {
      return <span className="text-sm text-gray-600">Event Log</span>;
    }
    const label = formatReviewStatusLabel(status);
    const classes =
      status === 'needs_review'
        ? 'bg-amber-50 border-amber-200 text-amber-700'
        : status === 'confirmed'
          ? 'bg-red-50 border-red-200 text-red-700'
          : status === 'false_positive'
            ? 'bg-blue-50 border-blue-200 text-blue-700'
            : status === 'resolved'
              ? 'bg-green-50 border-green-200 text-green-700'
              : 'bg-gray-50 border-gray-200 text-gray-700';
    return <span className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-medium ${classes}`}>{label}</span>;
  };

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
      ['Event Code', displayEventCode(event.eventCode)],
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
    setSelectedReviewStatus('all');
    setSelectedTimeRange(DEFAULT_TIME_RANGE);
  };

  return (
    <div className="p-3 sm:p-4 md:p-8 space-y-4 md:space-y-6 overflow-x-hidden">
      <div>
        <h2 className="text-xl md:text-2xl font-semibold text-gray-900">Events & Alerts</h2>
        <p className="text-gray-600 mt-1">
          Search event history by fusion result, event code, severity, and source node.
        </p>
        <div className="mt-3 inline-flex rounded-lg border border-gray-200 bg-gray-50 p-1">
          <button
            onClick={() => setReviewView('queue')}
            className={`px-3 py-1.5 text-sm rounded-md transition-colors ${reviewView === 'queue' ? 'bg-white border border-gray-200 text-blue-700' : 'text-gray-600 hover:text-gray-900'}`}
          >
            Review Queue
          </button>
          <button
            onClick={() => setReviewView('history')}
            className={`px-3 py-1.5 text-sm rounded-md transition-colors ${reviewView === 'history' ? 'bg-white border border-gray-200 text-blue-700' : 'text-gray-600 hover:text-gray-900'}`}
          >
            History
          </button>
        </div>
      </div>

      {loadError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Live event data unavailable: {loadError}
        </div>
      )}
      {isLoading && (
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-blue-800">
          Loading live events...
        </div>
      )}

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

          <div className="flex items-center gap-2 w-full sm:w-auto">
            <Filter className="w-4 h-4 text-gray-500" />
            <select
              value={selectedReviewStatus}
              onChange={(e) => setSelectedReviewStatus(e.target.value as ReviewStatus | 'all')}
              className="w-full sm:w-auto px-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">All Review Status</option>
              <option value="needs_review">Needs Review</option>
              <option value="confirmed">Confirmed</option>
              <option value="false_positive">False Positive</option>
              <option value="resolved">Resolved</option>
              <option value="archived">Archived</option>
            </select>
          </div>
        </div>
        {reviewView === 'queue' && (
          <div className="mt-3 pt-3 border-t border-gray-100 space-y-3">
            <div className="flex items-center gap-3">
              <label className="inline-flex items-center gap-2 text-xs text-gray-700">
                <input
                  type="checkbox"
                  checked={queueAlerts.length > 0 && queueAlerts.every((event) => selectedAlertIds.has(event.id))}
                  onChange={(e) => toggleSelectAllVisible(e.target.checked)}
                />
                Select all visible alerts
              </label>
              <span className="text-xs text-gray-600">Selected: {selectedQueueCount}</span>
              <span className="text-xs text-gray-600">Critical: {queueAlerts.filter((event) => event.severity === 'critical').length}</span>
            </div>
            {bulkResult && (
              <p
                className={`text-xs ${bulkResult.failed > 0 ? 'text-amber-700' : 'text-green-700'}`}
                role="status"
                aria-live="polite"
              >
                Bulk review updated {bulkResult.updated} alert{bulkResult.updated === 1 ? '' : 's'}
                {bulkResult.failed > 0
                  ? `; ${bulkResult.failed} failed. Retry to process remaining alerts.`
                  : ' successfully.'}
              </p>
            )}
            <div className="grid grid-cols-1 lg:grid-cols-4 gap-2">
              <select
                value={bulkReviewStatus}
                onChange={(e) => setBulkReviewStatus(e.target.value as ReviewStatus)}
                className="px-3 py-2 border border-gray-200 rounded-lg text-sm"
              >
                <option value="confirmed">Confirmed</option>
                <option value="false_positive">False Positive</option>
                <option value="resolved">Resolved</option>
                <option value="archived">Archived</option>
                <option value="needs_review">Needs Review</option>
              </select>
              <input
                value={bulkReviewNote}
                onChange={(e) => setBulkReviewNote(e.target.value)}
                placeholder="Bulk note (optional)"
                className="lg:col-span-2 px-3 py-2 border border-gray-200 rounded-lg text-sm"
              />
              <button
                onClick={() => {
                  void handleBulkApplyReview();
                }}
                disabled={bulkSaving || selectedQueueCount === 0}
                className="px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-60"
              >
                {bulkSaving ? 'Applying...' : 'Apply to Selected'}
              </button>
            </div>
          </div>
        )}
        <div className="mt-3 pt-3 border-t border-gray-100 flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs md:text-sm text-gray-600">
            {reviewView === 'queue' ? 'Queue items' : 'History items'}:{' '}
            <span className="font-semibold text-gray-900">{filteredEvents.length}</span>
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

              {reviewView === 'queue' && event.id.startsWith('alert-') && (
                <label className="inline-flex items-center gap-2 text-xs text-gray-700">
                  <input
                    type="checkbox"
                    checked={selectedAlertIds.has(event.id)}
                    onChange={(e) => {
                      e.stopPropagation();
                      toggleAlertSelection(event.id, e.target.checked);
                    }}
                    onClick={(e) => e.stopPropagation()}
                  />
                  Select
                </label>
              )}

              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-gray-900 break-words">
                    {displayEventCode(event.eventCode)}
                  </p>
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
                {renderReviewStatus(event)}
              </div>
            </button>
          ))}
        </div>

        <div className="hidden lg:block overflow-x-auto">
          <table className="w-full min-w-[860px]">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-600 uppercase tracking-wider">
                  Pick
                </th>
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
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                    {reviewView === 'queue' && event.id.startsWith('alert-') ? (
                      <input
                        type="checkbox"
                        checked={selectedAlertIds.has(event.id)}
                        onChange={(e) => toggleAlertSelection(event.id, e.target.checked)}
                      />
                    ) : (
                      '—'
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {formatDateTime(event.timestamp)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    {displayEventCode(event.eventCode)}
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
                    {renderReviewStatus(event)}
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
                    <p className="text-sm font-medium text-gray-900 mt-1">
                      {displayEventCode(selectedEvent.eventCode)}
                    </p>
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
                  {selectedEvent.snapshotPath && !snapshotLoadFailed ? (
                    <img
                      src={selectedEvent.snapshotPath}
                      alt="Event snapshot"
                      className="w-full h-full object-cover rounded-lg"
                      onError={() => {
                        setSnapshotLoadFailed(true);
                      }}
                    />
                  ) : (
                    <ImageIcon className="w-12 h-12 text-gray-600" />
                  )}
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
                {!selectedEvent.acknowledged && (
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

              {selectedEvent.id.startsWith('alert-') && (
                <div className="pt-4 border-t border-gray-200 space-y-3">
                  <p className="text-sm font-medium text-gray-900">Review Workflow</p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <select
                      value={reviewStatusDraft}
                      onChange={(event) =>
                        setReviewStatusDraft(
                          event.target.value as
                            | 'needs_review'
                            | 'confirmed'
                            | 'false_positive'
                            | 'resolved'
                            | 'archived',
                        )
                      }
                      className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm"
                    >
                      <option value="needs_review">Needs Review</option>
                      <option value="confirmed">Confirmed</option>
                      <option value="false_positive">False Positive</option>
                      <option value="resolved">Resolved</option>
                      <option value="archived">Archived</option>
                    </select>
                    <button
                      onClick={() => {
                        void handleSaveReview();
                      }}
                      disabled={reviewSaving}
                      className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-60"
                    >
                      {reviewSaving ? 'Saving...' : 'Save Review'}
                    </button>
                  </div>
                  {reviewFeedback ? <p className="text-xs text-green-700">{reviewFeedback}</p> : null}
                  {reviewError ? <p className="text-xs text-red-600">{reviewError}</p> : null}
                  <textarea
                    value={reviewNoteDraft}
                    onChange={(event) => setReviewNoteDraft(event.target.value)}
                    placeholder="Review notes (optional)"
                    className="w-full min-h-24 rounded-lg border border-gray-200 px-3 py-2 text-sm"
                  />
                  <p className="text-xs text-gray-600">
                    Last reviewed by {selectedEvent.reviewedBy || '—'}{' '}
                    {selectedEvent.reviewedTs
                      ? `at ${new Date(selectedEvent.reviewedTs).toLocaleString()}`
                      : ''}
                  </p>

                  <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
                    <p className="text-xs font-semibold text-gray-800">Review History</p>
                    {reviewHistoryLoading ? (
                      <p className="mt-2 text-xs text-gray-600">Loading review history...</p>
                    ) : reviewHistory.length === 0 ? (
                      <p className="mt-2 text-xs text-gray-600">No review history yet.</p>
                    ) : (
                      <div className="mt-2 space-y-2 max-h-36 overflow-y-auto">
                        {reviewHistory.map((entry) => (
                          <div key={entry.id} className="rounded-md border border-gray-200 bg-white px-2 py-1.5">
                            <p className="text-xs text-gray-800">
                              {formatReviewStatusLabel(entry.previousStatus)} {'->'} {formatReviewStatusLabel(entry.nextStatus)}
                            </p>
                            <p className="text-[11px] text-gray-600">
                              {entry.reviewedBy || 'admin'} at {new Date(entry.reviewedTs).toLocaleString()}
                            </p>
                            {entry.note ? <p className="text-[11px] text-gray-700 mt-1">{entry.note}</p> : null}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
