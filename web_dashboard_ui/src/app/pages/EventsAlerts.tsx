import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router';
import { Calendar, Camera, CheckCircle2, Filter, Search, X, Image as ImageIcon } from 'lucide-react';
import { fetchLiveEvents, fetchLiveNodes, fetchSettingsLive, submitSnapshotFeedback, trainFaceModel } from '../data/liveApi';
import type { Alert, AuthorizedProfile, CameraFeed, SeverityLevel, EventType } from '../data/types';
import { StatusBadge } from '../components/StatusBadge';

type TimeRange = '24h' | '7d' | '30d' | 'all';
type DecisionFilter = 'all' | 'unknown_face' | 'face_unclear' | 'no_face' | 'authorized';
type ReviewFilter = 'all' | 'needs_review' | 'confirmed' | 'false_positive' | 'resolved' | 'archived';

const DEFAULT_TIME_RANGE: TimeRange = '7d';
const TIME_RANGE_DAYS: Record<Exclude<TimeRange, 'all'>, number> = {
  '24h': 1,
  '7d': 7,
  '30d': 30,
};

const displayEventCode = (eventCode: string) =>
  eventCode === 'UNKNOWN' ? 'NON-AUTHORIZED' : eventCode;

const formatLabel = (value: string) => value.replace(/_/g, ' ') || '-';

const formatFrameAge = (ageMs?: number | null) => {
  if (ageMs == null || !Number.isFinite(ageMs)) {
    return 'unknown';
  }
  if (ageMs < 1000) {
    return `${Math.max(0, Math.round(ageMs))} ms`;
  }
  return `${(ageMs / 1000).toFixed(1)} s`;
};

const cameraSnapshotReady = (feed: CameraFeed) =>
  feed.status === 'online' && Boolean(feed.framePath) && (feed.frameAgeMs == null || feed.frameAgeMs < 5000);

const isIntruderFeedbackEvent = (event: Alert) => {
  const eventCode = event.eventCode.toUpperCase();
  return event.type === 'intruder' || ['INTRUDER', 'DOOR_TAMPER', 'AUTHORIZED_ENTRY'].includes(eventCode);
};

const isFireFeedbackEvent = (event: Alert) => {
  const eventCode = event.eventCode.toUpperCase();
  return event.type === 'fire' || ['FIRE', 'SMOKE_WARNING'].includes(eventCode);
};

const hasFeedbackReview = (event: Alert) =>
  ['confirmed', 'false_positive', 'resolved', 'archived'].includes(String(event.reviewStatus || '').toLowerCase());

const feedbackAlertId = (event: Alert) => {
  if (event.id.startsWith('alert-')) {
    const id = Number.parseInt(event.id.replace(/^alert-/, ''), 10);
    return Number.isFinite(id) && id > 0 ? id : null;
  }
  return event.relatedAlertId && event.relatedAlertId > 0 ? event.relatedAlertId : null;
};

const canSubmitSnapshotFeedback = (event: Alert) =>
  feedbackAlertId(event) !== null &&
  !hasFeedbackReview(event) &&
  (isIntruderFeedbackEvent(event) || isFireFeedbackEvent(event));

const canBulkFalseAlarm = (event: Alert) =>
  canSubmitSnapshotFeedback(event) && isIntruderFeedbackEvent(event) && Boolean(event.snapshotPath);

const getSnapshotCardId = (snapshotPath: string) => {
  let hash = 0;
  for (let index = 0; index < snapshotPath.length; index += 1) {
    hash = ((hash << 5) - hash + snapshotPath.charCodeAt(index)) | 0;
  }
  return `snapshot-card-${(hash >>> 0).toString(36)}`;
};

function overlayColor(overlay: NonNullable<Alert['faceOverlays']>[number]) {
  const kind = String(overlay.kind || '').toLowerCase();
  const classification = overlay.classification.toUpperCase();
  if (kind === 'fire' || classification.includes('FIRE')) {
    return '#ef4444';
  }
  if (classification.includes('SMOKE')) {
    return '#f97316';
  }
  if (classification === 'AUTHORIZED') {
    return '#22c55e';
  }
  return '#f59e0b';
}

function overlayLabel(overlay: NonNullable<Alert['faceOverlays']>[number]) {
  const kind = String(overlay.kind || '').toLowerCase();
  const classification = overlay.classification.toUpperCase();
  if (kind === 'fire' || classification.includes('FIRE')) {
    return 'FIRE';
  }
  if (classification.includes('SMOKE')) {
    return 'SMOKE';
  }
  if (classification === 'AUTHORIZED') {
    return 'AUTH';
  }
  if (classification === 'NON-AUTHORIZED' || classification === 'UNKNOWN_FACE' || classification === 'UNKNOWN') {
    return 'NON-AUTH';
  }
  return classification || 'FACE';
}

function SnapshotImageWithOverlay({
  event,
  alt,
  imageClassName = '',
  onError,
}: {
  event: Alert;
  alt: string;
  imageClassName?: string;
  onError?: () => void;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [imageSize, setImageSize] = useState<{ width: number; height: number } | null>(null);
  const [containerSize, setContainerSize] = useState<{ width: number; height: number } | null>(null);
  const overlays = event.faceOverlays || [];

  useEffect(() => {
    const node = containerRef.current;
    if (!node) {
      return;
    }

    const updateSize = () => {
      const rect = node.getBoundingClientRect();
      setContainerSize({ width: rect.width, height: rect.height });
    };
    updateSize();

    const observer = new ResizeObserver(updateSize);
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const overlayStyle = (bbox: [number, number, number, number]) => {
    if (!imageSize || !containerSize || imageSize.width <= 0 || imageSize.height <= 0) {
      return { display: 'none' };
    }
    const scale = Math.min(containerSize.width / imageSize.width, containerSize.height / imageSize.height);
    const renderedWidth = imageSize.width * scale;
    const renderedHeight = imageSize.height * scale;
    const offsetX = (containerSize.width - renderedWidth) / 2;
    const offsetY = (containerSize.height - renderedHeight) / 2;
    const [x, y, width, height] = bbox;
    return {
      left: `${offsetX + x * scale}px`,
      top: `${offsetY + y * scale}px`,
      width: `${width * scale}px`,
      height: `${height * scale}px`,
    };
  };

  return (
    <div ref={containerRef} className="relative h-full w-full overflow-hidden bg-black">
      <img
        src={event.snapshotPath}
        alt={alt}
        loading="lazy"
        className={`h-full w-full object-contain ${imageClassName}`}
        onLoad={(event) => {
          const image = event.currentTarget;
          setImageSize({ width: image.naturalWidth, height: image.naturalHeight });
        }}
        onError={onError}
      />
      {overlays.map((overlay, index) => {
        const color = overlayColor(overlay);
        return (
          <div
            key={`${overlay.classification}-${index}-${overlay.bbox.join('-')}`}
            className="pointer-events-none absolute rounded-sm border-2"
            style={{ ...overlayStyle(overlay.bbox), borderColor: color }}
          >
            <span
              className="absolute -top-6 left-0 whitespace-nowrap rounded px-1.5 py-0.5 text-[10px] font-bold text-white shadow"
              style={{ backgroundColor: color }}
            >
              {overlayLabel(overlay)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function SnapshotGalleryCard({
  event,
  highlighted,
  onOpen,
  selectable = false,
  selected = false,
  bulkEligible = false,
  onToggleSelected,
}: {
  event: Alert;
  highlighted: boolean;
  onOpen: (event: Alert) => void;
  selectable?: boolean;
  selected?: boolean;
  bulkEligible?: boolean;
  onToggleSelected?: (event: Alert) => void;
}) {
  const [imageFailed, setImageFailed] = useState(false);
  const snapshotPath = event.snapshotPath || '';
  const isAlert = event.id.startsWith('alert-');
  const recordLabel = `${isAlert ? 'Alert' : 'Event'} #${event.id.replace(/^(alert|event)-/, '')}`;
  const linkedRecord = isAlert && event.eventId
    ? `Event #${event.eventId}`
    : !isAlert && event.relatedAlertId
      ? `Alert #${event.relatedAlertId}`
      : '';

  return (
    <button
      id={getSnapshotCardId(snapshotPath)}
      type="button"
      onClick={() => {
        if (selectable && bulkEligible && onToggleSelected) {
          onToggleSelected(event);
          return;
        }
        onOpen(event);
      }}
      className={`group overflow-hidden rounded-xl border bg-white text-left shadow-sm transition-all focus:outline-none focus:ring-2 focus:ring-blue-500 ${
        selected
          ? 'border-amber-500 ring-4 ring-amber-100'
          : highlighted
          ? 'border-blue-500 ring-4 ring-blue-200'
          : 'border-gray-200 hover:-translate-y-0.5 hover:shadow-md'
      }`}
    >
      <div className="relative aspect-video bg-gray-900">
        {snapshotPath && !imageFailed ? (
          <SnapshotImageWithOverlay
            event={event}
            alt={`${recordLabel} snapshot`}
            imageClassName="transition-transform duration-300 group-hover:scale-[1.02]"
            onError={() => setImageFailed(true)}
          />
        ) : (
          <div className="flex h-full w-full flex-col items-center justify-center gap-2 text-gray-500">
            <ImageIcon className="h-10 w-10" />
            <span className="text-xs">Snapshot unavailable</span>
          </div>
        )}
        <div className="absolute left-3 top-3 flex flex-wrap items-center gap-2">
          <span className="rounded-full bg-black/70 px-2.5 py-1 text-xs font-semibold text-white">
            {recordLabel}
          </span>
          <StatusBadge severity={event.severity} label={event.severity.toUpperCase()} size="sm" />
        </div>
        {selectable ? (
          <div className="absolute right-3 top-3 rounded-full bg-white/95 px-2 py-1 text-xs font-semibold shadow">
            {bulkEligible ? (selected ? 'Selected' : 'Select') : 'Not eligible'}
          </div>
        ) : null}
      </div>

      <div className="space-y-3 p-4">
        <div>
          <div className="flex flex-wrap items-center gap-2 text-xs font-semibold text-blue-700">
            <span>{displayEventCode(event.eventCode)}</span>
            {linkedRecord ? <span className="text-gray-500">Linked {linkedRecord}</span> : null}
          </div>
          <h3 className="mt-1 text-sm font-semibold text-gray-900 break-words">{event.title}</h3>
          <p className="mt-1 text-sm text-gray-600 break-words">
            {event.description || 'No description attached to this record.'}
          </p>
        </div>

        <div className="grid grid-cols-1 gap-1 text-xs text-gray-600 sm:grid-cols-2">
          <span>{new Date(event.timestamp).toLocaleString()}</span>
          <span className="font-mono break-all sm:text-right">{event.sourceNode}</span>
          <span className="sm:col-span-2">{event.location || 'No location recorded'}</span>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full border border-gray-200 bg-gray-50 px-2 py-0.5 text-xs font-medium text-gray-700">
            {isAlert ? 'Acknowledged Alert' : 'Event Snapshot'}
          </span>
          <span className="text-xs text-gray-500">Click to open details</span>
        </div>
      </div>
    </button>
  );
}

function ActiveAlertSnapshotCard({
  alert,
  ackPending,
  onAcknowledge,
  onOpen,
  selectable = false,
  selected = false,
  bulkEligible = false,
  onToggleSelected,
}: {
  alert: Alert;
  ackPending: boolean;
  onAcknowledge: (alert: Alert) => void;
  onOpen: (alert: Alert) => void;
  selectable?: boolean;
  selected?: boolean;
  bulkEligible?: boolean;
  onToggleSelected?: (alert: Alert) => void;
}) {
  const [imageFailed, setImageFailed] = useState(false);
  const snapshotPath = alert.snapshotPath || '';
  const formattedTime = new Date(alert.timestamp).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });

  return (
    <article className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
      <button
        type="button"
        onClick={() => {
          if (selectable && bulkEligible && onToggleSelected) {
            onToggleSelected(alert);
            return;
          }
          onOpen(alert);
        }}
        className="relative block aspect-video w-full bg-gray-900 text-left focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
      >
        {snapshotPath && !imageFailed ? (
          <SnapshotImageWithOverlay
            event={alert}
            alt={`${alert.title} snapshot`}
            imageClassName="transition-transform duration-300 hover:scale-[1.02]"
            onError={() => setImageFailed(true)}
          />
        ) : (
          <div className="flex h-full w-full flex-col items-center justify-center gap-2 text-gray-500">
            <ImageIcon className="h-12 w-12" />
            <span className="text-sm">Snapshot unavailable</span>
          </div>
        )}
        <div className="absolute left-3 top-3 flex flex-wrap items-center gap-2">
          <StatusBadge severity={alert.severity} label={alert.severity.toUpperCase()} size="sm" />
          <span className="rounded-full bg-black/70 px-2.5 py-1 text-xs font-semibold text-white">
            {displayEventCode(alert.eventCode)}
          </span>
        </div>
        {selectable ? (
          <div className="absolute right-3 top-3 rounded-full bg-white/95 px-2 py-1 text-xs font-semibold shadow">
            {bulkEligible ? (selected ? 'Selected' : 'Select') : 'Not eligible'}
          </div>
        ) : null}
      </button>

      <div className="space-y-4 p-4">
        <div>
          <h3 className="text-base font-semibold text-gray-900 break-words">{alert.title}</h3>
          <p className="mt-1 text-sm text-gray-600 break-words">{alert.description}</p>
        </div>

        <div className="grid grid-cols-1 gap-1 text-xs text-gray-600 sm:grid-cols-2">
          <span>{alert.location || 'No location recorded'}</span>
          <span className="font-mono break-all sm:text-right">{alert.sourceNode}</span>
          <span className="sm:col-span-2">{formattedTime}</span>
        </div>

        {alert.fusionEvidence && alert.fusionEvidence.length > 0 ? (
          <p className="rounded-lg bg-gray-50 px-3 py-2 text-xs text-gray-600">
            Evidence: {alert.fusionEvidence.join(', ')}
          </p>
        ) : null}

        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <span className="text-xs text-gray-500">Open the snapshot for details if needed.</span>
          <div className="flex flex-wrap gap-2">
            {selectable ? (
              <button
                type="button"
                onClick={() => onToggleSelected?.(alert)}
                disabled={!bulkEligible}
                className="inline-flex items-center justify-center rounded-lg border border-amber-300 bg-amber-50 px-4 py-2 text-sm font-medium text-amber-800 transition-colors hover:bg-amber-100 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {selected ? 'Unselect' : 'Select'}
              </button>
            ) : null}
            <button
              type="button"
              onClick={() => onAcknowledge(alert)}
              disabled={ackPending}
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <CheckCircle2 className="h-4 w-4" />
              {ackPending ? 'Acknowledging...' : 'Acknowledge'}
            </button>
          </div>
        </div>
      </div>
    </article>
  );
}

export function EventsAlerts() {
  const navigate = useNavigate();
  const [events, setEvents] = useState<Alert[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedSeverity, setSelectedSeverity] = useState<SeverityLevel | 'all'>('all');
  const [selectedType, setSelectedType] = useState<EventType | 'all'>('all');
  const [selectedDecision, setSelectedDecision] = useState<DecisionFilter>('all');
  const [selectedReview, setSelectedReview] = useState<ReviewFilter>('all');
  const [selectedTimeRange, setSelectedTimeRange] = useState<TimeRange>(DEFAULT_TIME_RANGE);
  const [historyFiltersOpen, setHistoryFiltersOpen] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState<Alert | null>(null);
  const [cameraFeeds, setCameraFeeds] = useState<CameraFeed[]>([]);
  const [snapshotLoadFailed, setSnapshotLoadFailed] = useState(false);
  const [ackPendingId, setAckPendingId] = useState<string | null>(null);
  const [feedbackPendingId, setFeedbackPendingId] = useState<string | null>(null);
  const [feedbackProfiles, setFeedbackProfiles] = useState<AuthorizedProfile[]>([]);
  const [feedbackProfileName, setFeedbackProfileName] = useState('');
  const [feedbackMessage, setFeedbackMessage] = useState('');
  const [groupTrainMessage, setGroupTrainMessage] = useState('');
  const [groupTraining, setGroupTraining] = useState(false);
  const [bulkFalseAlarmMode, setBulkFalseAlarmMode] = useState(false);
  const [bulkFalseAlarmIds, setBulkFalseAlarmIds] = useState<Set<string>>(() => new Set());
  const [bulkFeedbackProfileName, setBulkFeedbackProfileName] = useState('');
  const [bulkFeedbackPending, setBulkFeedbackPending] = useState(false);
  const [bulkFeedbackMessage, setBulkFeedbackMessage] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState('');

  const handleAcknowledge = async (id: string) => {
    setAckPendingId(id);

    const numericId = Number.parseInt(id.replace(/^alert-/, ''), 10);
    if (!Number.isFinite(numericId) || numericId <= 0) {
      setLoadError('Unable to acknowledge alert: invalid alert ID.');
      setAckPendingId(null);
      return;
    }

    try {
      const response = await fetch(`/api/alerts/${numericId}/ack`, {
        method: 'POST',
      });
      if (!response.ok) {
        throw new Error(`Acknowledge failed (${response.status}).`);
      }
      setEvents((prev) => prev.map((event) => (event.id === id ? { ...event, acknowledged: true } : event)));
      setSelectedEvent((prev) => (prev && prev.id === id ? { ...prev, acknowledged: true } : prev));
      setLoadError('');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to acknowledge alert right now.';
      setLoadError(message);
    } finally {
      setAckPendingId(null);
    }
  };

  useEffect(() => {
    let cancelled = false;
    let controller: AbortController | null = null;
    let timer: number | null = null;

    const load = async () => {
      controller = new AbortController();
      try {
        const [payload, nodesPayload] = await Promise.all([
          fetchLiveEvents(500, controller.signal),
          fetchLiveNodes(controller.signal),
        ]);
        if (cancelled) {
          return;
        }
        setEvents(
          [...payload.alerts, ...payload.events].sort(
            (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
          ),
        );
        setCameraFeeds(nodesPayload.cameraFeeds);
        setLoadError('');
      } catch (error) {
        if (cancelled) {
          return;
        }
        const message = error instanceof Error ? error.message : 'Unable to load live events.';
        if (!cancelled) {
          setLoadError(message);
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
          timer = window.setTimeout(() => {
            void load();
          }, 2000);
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

  useEffect(() => {
    setSnapshotLoadFailed(false);
    setFeedbackMessage('');
  }, [selectedEvent?.id, selectedEvent?.snapshotPath]);

  useEffect(() => {
    let cancelled = false;
    setFeedbackProfiles([]);
    setFeedbackProfileName('');
    setBulkFeedbackProfileName('');
    if (
      !bulkFalseAlarmMode &&
      (!selectedEvent || !canSubmitSnapshotFeedback(selectedEvent) || !isIntruderFeedbackEvent(selectedEvent))
    ) {
      return;
    }

    fetchSettingsLive()
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setFeedbackProfiles(payload.authorizedProfiles);
        setFeedbackProfileName(payload.authorizedProfiles[0]?.label || '');
        setBulkFeedbackProfileName(payload.authorizedProfiles[0]?.label || '');
      })
      .catch((error) => {
        if (cancelled) {
          return;
        }
        const message = error instanceof Error ? error.message : 'Unable to load authorized profiles.';
        setFeedbackMessage(message);
      });

    return () => {
      cancelled = true;
    };
  }, [selectedEvent, bulkFalseAlarmMode]);

  const activeAlerts = useMemo(
    () =>
      events
        .filter((event) => event.id.startsWith('alert-') && !event.acknowledged)
        .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()),
    [events],
  );

  const activeAlertIds = useMemo(
    () => new Set(activeAlerts.map((alert) => alert.id)),
    [activeAlerts],
  );

  const activeSnapshotPaths = useMemo(
    () => new Set(activeAlerts.map((alert) => alert.snapshotPath).filter(Boolean)),
    [activeAlerts],
  );

  const filteredEvents = useMemo(
    () => {
      const keyword = searchQuery.toLowerCase().trim();
      const days = selectedTimeRange === 'all' ? null : TIME_RANGE_DAYS[selectedTimeRange];
      const cutoffMs = days == null ? Number.NEGATIVE_INFINITY : Date.now() - days * 24 * 60 * 60 * 1000;

      return events.filter((event) => {
        if (activeAlertIds.has(event.id) || !event.snapshotPath || activeSnapshotPaths.has(event.snapshotPath)) {
          return false;
        }

        const matchesSearch =
          event.title.toLowerCase().includes(keyword) ||
          event.description.toLowerCase().includes(keyword) ||
          event.eventCode.toLowerCase().includes(keyword) ||
          event.sourceNode.toLowerCase().includes(keyword);
        const matchesSeverity = selectedSeverity === 'all' || event.severity === selectedSeverity;
        const matchesType = selectedType === 'all' || event.type === selectedType;
        const matchesDecision = selectedDecision === 'all' || event.decisionState === selectedDecision;
        const matchesReview = selectedReview === 'all' || event.reviewStatus === selectedReview;
        const eventTimeMs = new Date(event.timestamp).getTime();
        const matchesTime = days == null || (Number.isFinite(eventTimeMs) && eventTimeMs >= cutoffMs);
        return matchesSearch && matchesSeverity && matchesType && matchesDecision && matchesReview && matchesTime;
      });
    },
    [events, searchQuery, selectedSeverity, selectedType, selectedDecision, selectedReview, selectedTimeRange, activeAlertIds, activeSnapshotPaths],
  );
  const hasActiveFilters =
    searchQuery.trim().length > 0 ||
    selectedSeverity !== 'all' ||
    selectedType !== 'all' ||
    selectedDecision !== 'all' ||
    selectedReview !== 'all' ||
    selectedTimeRange !== DEFAULT_TIME_RANGE;

  const snapshotGalleryEvents = useMemo(() => {
    const bySnapshotPath = new Map<string, Alert>();
    for (const event of filteredEvents) {
      const snapshotPath = event.snapshotPath;
      if (!snapshotPath) {
        continue;
      }

      const current = bySnapshotPath.get(snapshotPath);
      if (!current) {
        bySnapshotPath.set(snapshotPath, event);
        continue;
      }

      const currentIsAlert = current.id.startsWith('alert-');
      const nextIsAlert = event.id.startsWith('alert-');
      if (nextIsAlert && !currentIsAlert) {
        bySnapshotPath.set(snapshotPath, event);
      }
    }
    return Array.from(bySnapshotPath.values());
  }, [filteredEvents]);

  const bulkEligibleEvents = useMemo(() => {
    const byId = new Map<string, Alert>();
    for (const event of [...activeAlerts, ...snapshotGalleryEvents]) {
      if (canBulkFalseAlarm(event)) {
        byId.set(event.id, event);
      }
    }
    return Array.from(byId.values());
  }, [activeAlerts, snapshotGalleryEvents]);

  const bulkEligibleIds = useMemo(
    () => new Set(bulkEligibleEvents.map((event) => event.id)),
    [bulkEligibleEvents],
  );

  const bulkSelectedEvents = useMemo(
    () => bulkEligibleEvents.filter((event) => bulkFalseAlarmIds.has(event.id)),
    [bulkEligibleEvents, bulkFalseAlarmIds],
  );

  useEffect(() => {
    setBulkFalseAlarmIds((prev) => {
      const next = new Set(Array.from(prev).filter((id) => bulkEligibleIds.has(id)));
      return next.size === prev.size ? prev : next;
    });
  }, [bulkEligibleIds]);

  const visibleItemCount = snapshotGalleryEvents.length;
  const selectedFalseAlarmSnapshotUnavailable = Boolean(
    selectedEvent && (!selectedEvent.snapshotPath || snapshotLoadFailed),
  );

  const toggleBulkFalseAlarmSelection = (event: Alert) => {
    if (!canBulkFalseAlarm(event)) {
      return;
    }
    setBulkFeedbackMessage('');
    setBulkFalseAlarmIds((prev) => {
      const next = new Set(prev);
      if (next.has(event.id)) {
        next.delete(event.id);
      } else {
        next.add(event.id);
      }
      return next;
    });
  };

  const handleBulkSnapshotFeedback = async () => {
    if (bulkFeedbackPending) {
      return;
    }
    if (bulkSelectedEvents.length === 0) {
      setBulkFeedbackMessage('Select at least one eligible intruder alert first.');
      return;
    }

    const faceName = bulkFeedbackProfileName.trim();
    if (!faceName) {
      setBulkFeedbackMessage('Select the authorized person before marking selected intruder alerts as false alarms.');
      return;
    }

    setBulkFeedbackPending(true);
    setBulkFeedbackMessage(`Saving ${bulkSelectedEvents.length} false alarm${bulkSelectedEvents.length === 1 ? '' : 's'} for group retraining...`);
    let savedCount = 0;
    let failedMessage = '';
    const savedIds = new Set<string>();

    for (const event of bulkSelectedEvents) {
      const alertId = feedbackAlertId(event);
      if (alertId === null) {
        failedMessage = 'One selected item does not have a linked alert record.';
        break;
      }

      try {
        const response = await submitSnapshotFeedback(alertId, {
          verdict: 'false_positive',
          faceName,
        });
        savedCount += 1;
        savedIds.add(event.id);
        setEvents((prev) =>
          prev.map((item) => {
            if (item.id === response.alert.id) {
              return response.alert;
            }
            if (item.id === event.id || feedbackAlertId(item) === alertId) {
              return {
                ...item,
                reviewStatus: response.alert.reviewStatus,
                reviewNote: response.alert.reviewNote,
                reviewedBy: response.alert.reviewedBy,
                reviewedTs: response.alert.reviewedTs,
              };
            }
            return item;
          }),
        );
      } catch (error) {
        failedMessage = error instanceof Error ? error.message : 'Unable to submit selected false alarms.';
        break;
      }
    }

    setBulkFalseAlarmIds((prev) => new Set(Array.from(prev).filter((id) => !savedIds.has(id))));
    setBulkFeedbackPending(false);
    if (failedMessage) {
      setBulkFeedbackMessage(
        savedCount > 0
          ? `${savedCount} false alarm${savedCount === 1 ? '' : 's'} saved before an error: ${failedMessage}`
          : failedMessage,
      );
      return;
    }
    setBulkFeedbackMessage(
      `${savedCount} false alarm${savedCount === 1 ? '' : 's'} saved for ${faceName}. Run Group Retrain Face Model after reviewing your false alarms.`,
    );
  };

  const handleSnapshotFeedback = async (event: Alert, verdict: 'confirmed' | 'false_positive') => {
    const alertId = feedbackAlertId(event);
    if (alertId === null) {
      setFeedbackMessage('Snapshot feedback requires a linked alert record.');
      return;
    }

    if (verdict === 'false_positive' && !event.snapshotPath) {
      setFeedbackMessage('False-alarm training requires an alert snapshot, but this alert has no snapshot attached.');
      return;
    }

    if (verdict === 'false_positive' && selectedEvent?.id === event.id && snapshotLoadFailed) {
      setFeedbackMessage('False-alarm training requires a snapshot file that can still be loaded.');
      return;
    }

    const faceName = feedbackProfileName.trim();
    if (verdict === 'false_positive' && isIntruderFeedbackEvent(event) && !faceName) {
      setFeedbackMessage('Select the authorized person before marking this intruder snapshot as a false alarm.');
      return;
    }

    if (verdict === 'false_positive' && isFireFeedbackEvent(event)) {
      const confirmed = window.confirm(
        'Mark this fire snapshot as a false alarm and save it as a hard-negative training sample?',
      );
      if (!confirmed) {
        return;
      }
    }

    setFeedbackPendingId(event.id);
    setFeedbackMessage('');
    try {
      const response = await submitSnapshotFeedback(alertId, {
        verdict,
        faceName: verdict === 'false_positive' ? faceName : '',
      });
      setEvents((prev) => prev.map((item) => (item.id === response.alert.id ? response.alert : item)));
      setSelectedEvent((prev) => {
        if (!prev) {
          return prev;
        }
        if (prev.id === response.alert.id) {
          return response.alert;
        }
        return {
          ...prev,
          reviewStatus: response.alert.reviewStatus,
          reviewNote: response.alert.reviewNote,
          reviewedBy: response.alert.reviewedBy,
          reviewedTs: response.alert.reviewedTs,
        };
      });
      if (verdict === 'confirmed') {
        setFeedbackMessage('Snapshot confirmed.');
      } else if (isIntruderFeedbackEvent(event)) {
        setFeedbackMessage(
          `False alarm saved for group retraining. ${response.trainMessage || 'Run Group Retrain Face Model after reviewing your false alarms.'}`.trim(),
        );
      } else {
        setFeedbackMessage('False alarm saved as a fire hard-negative sample.');
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to submit snapshot feedback.';
      setFeedbackMessage(message);
    } finally {
      setFeedbackPendingId(null);
    }
  };

  const handleGroupRetrain = async () => {
    if (groupTraining) {
      return;
    }
    setGroupTraining(true);
    setGroupTrainMessage('Training face model from all current samples...');
    try {
      const result = await trainFaceModel();
      setGroupTrainMessage(result.ok ? `Group retrain complete. ${result.message}` : `Group retrain failed. ${result.message}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to retrain face model.';
      setGroupTrainMessage(message);
    } finally {
      setGroupTraining(false);
    }
  };

  const handleOpenCameraFeed = () => {
    setSelectedEvent(null);
    navigate('/live');
  };

  const clearFilters = () => {
    setSearchQuery('');
    setSelectedSeverity('all');
    setSelectedType('all');
    setSelectedDecision('all');
    setSelectedReview('all');
    setSelectedTimeRange(DEFAULT_TIME_RANGE);
  };

  return (
    <div className="p-3 sm:p-4 md:p-8 space-y-4 md:space-y-6 overflow-x-hidden">
      <div>
        <h2 className="text-xl md:text-2xl font-semibold text-gray-900">Alerts</h2>
        <p className="text-gray-600 mt-1">
          Review recent events, active alerts, and captured snapshots.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
          <span className="inline-flex items-center rounded-full border border-red-200 bg-red-50 px-2.5 py-1 font-medium text-red-700">
            Active alerts: {activeAlerts.length}
          </span>
          <span className="inline-flex items-center rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 font-medium text-blue-700">
            Snapshot history: {snapshotGalleryEvents.length}
          </span>
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

      <section className="rounded-lg border border-amber-200 bg-amber-50 p-4">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div className="space-y-1">
            <h3 className="text-base font-semibold text-gray-900">Intruder False Alarm Review</h3>
            <p className="text-sm text-gray-700">
              Select multiple intruder snapshots, mark them as false alarms for one authorized person, then retrain once as a group.
            </p>
            <p className="text-xs text-gray-600">
              {bulkSelectedEvents.length} selected of {bulkEligibleEvents.length} eligible intruder snapshot{bulkEligibleEvents.length === 1 ? '' : 's'}.
            </p>
          </div>

          <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
            {bulkFalseAlarmMode ? (
              <label className="flex min-w-56 flex-col gap-1 text-xs font-medium text-gray-700">
                Authorized person
                <select
                  value={bulkFeedbackProfileName}
                  onChange={(event) => setBulkFeedbackProfileName(event.target.value)}
                  className="rounded-lg border border-amber-200 bg-white px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-amber-500"
                >
                  {feedbackProfiles.length === 0 ? (
                    <option value="">No profiles loaded</option>
                  ) : (
                    feedbackProfiles.map((profile) => (
                      <option key={profile.id || profile.label} value={profile.label}>
                        {profile.label} ({profile.sampleCount ?? 0} samples)
                      </option>
                    ))
                  )}
                </select>
              </label>
            ) : null}

            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => {
                  setBulkFalseAlarmMode((mode) => !mode);
                  setBulkFeedbackMessage('');
                }}
                className="inline-flex items-center justify-center rounded-lg border border-amber-300 bg-white px-4 py-2 text-sm font-medium text-amber-800 transition-colors hover:bg-amber-100"
              >
                {bulkFalseAlarmMode ? 'Stop Selecting' : 'Select Intruder Alerts'}
              </button>
              {bulkFalseAlarmMode ? (
                <button
                  type="button"
                  onClick={() => void handleBulkSnapshotFeedback()}
                  disabled={bulkFeedbackPending || bulkSelectedEvents.length === 0}
                  className="inline-flex items-center justify-center rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-amber-700 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {bulkFeedbackPending ? 'Saving...' : 'Mark Selected False Alarm'}
                </button>
              ) : null}
              <button
                type="button"
                onClick={() => void handleGroupRetrain()}
                disabled={groupTraining}
                className="inline-flex items-center justify-center rounded-lg border border-blue-200 bg-white px-4 py-2 text-sm font-medium text-blue-700 transition-colors hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {groupTraining ? 'Retraining...' : 'Group Retrain Face Model'}
              </button>
            </div>
          </div>
        </div>
        {bulkFeedbackMessage ? (
          <p className="mt-3 rounded-md border border-amber-100 bg-white px-3 py-2 text-sm text-amber-800">
            {bulkFeedbackMessage}
          </p>
        ) : null}
        {groupTrainMessage ? (
          <p className="mt-3 rounded-md border border-green-100 bg-white px-3 py-2 text-sm text-green-800">
            {groupTrainMessage}
          </p>
        ) : null}
      </section>

      <section className="space-y-3 rounded-lg border border-gray-200 bg-white p-4">
        <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h3 className="text-base md:text-lg font-semibold text-gray-900">Camera Diagnostics</h3>
            <p className="text-sm text-gray-600">Snapshot readiness and live frame health for evidence capture.</p>
          </div>
          <span className="text-xs text-gray-500">
            {cameraFeeds.filter(cameraSnapshotReady).length}/{cameraFeeds.length} snapshot-ready
          </span>
        </div>

        {cameraFeeds.length > 0 ? (
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            {cameraFeeds.map((feed) => {
              const ready = cameraSnapshotReady(feed);
              return (
                <div key={feed.nodeId} className="rounded-lg border border-gray-100 bg-gray-50 p-3">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <p className="text-sm font-semibold text-gray-900">{feed.location || feed.nodeId}</p>
                      <p className="text-xs font-mono text-gray-500">{feed.nodeId}</p>
                    </div>
                    <span
                      className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
                        ready
                          ? 'bg-green-100 text-green-700'
                          : feed.status === 'online'
                            ? 'bg-amber-100 text-amber-700'
                            : 'bg-red-100 text-red-700'
                      }`}
                    >
                      {ready ? 'snapshot ready' : feed.status === 'online' ? 'check frame' : 'offline'}
                    </span>
                  </div>
                  <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-gray-600 sm:grid-cols-4">
                    <span>Status: <strong className="text-gray-900">{feed.status}</strong></span>
                    <span>Stream: <strong className="text-gray-900">{feed.streamAvailable ? 'yes' : 'no'}</strong></span>
                    <span>Frame age: <strong className="text-gray-900">{formatFrameAge(feed.frameAgeMs)}</strong></span>
                    <span>FPS: <strong className="text-gray-900">{feed.fps || '-'}</strong></span>
                    <span className="sm:col-span-2">Resolution: <strong className="text-gray-900">{feed.frameWidth && feed.frameHeight ? `${feed.frameWidth}x${feed.frameHeight}` : 'unknown'}</strong></span>
                    <span className="sm:col-span-2">Snapshot: <strong className="text-gray-900">{ready ? 'available' : 'not ready'}</strong></span>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="rounded-lg bg-gray-50 p-3 text-sm text-gray-600">No camera feeds reported yet.</p>
        )}
      </section>

      <section className="space-y-3">
        <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h3 className="text-base md:text-lg font-semibold text-gray-900">Active Alerts</h3>
            <p className="text-sm text-gray-600">Acknowledge an alert after it has been checked or handled.</p>
          </div>
          <span className="text-xs text-gray-500">
            {activeAlerts.length} alert{activeAlerts.length === 1 ? '' : 's'} need action
          </span>
        </div>

        {activeAlerts.length > 0 ? (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
            {activeAlerts.map((alert) => (
              <ActiveAlertSnapshotCard
                key={alert.id}
                alert={alert}
                ackPending={ackPendingId === alert.id}
                onAcknowledge={(selectedAlert) => void handleAcknowledge(selectedAlert.id)}
                onOpen={(selectedAlert) => setSelectedEvent(selectedAlert)}
                selectable={bulkFalseAlarmMode}
                selected={bulkFalseAlarmIds.has(alert.id)}
                bulkEligible={canBulkFalseAlarm(alert)}
                onToggleSelected={toggleBulkFalseAlarmSelection}
              />
            ))}
          </div>
        ) : (
          <div className="rounded-lg border border-green-200 bg-green-50 p-4 text-sm text-green-800">
            No active alerts need acknowledgement right now.
          </div>
        )}
      </section>

      <div className="space-y-3">
        <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h3 className="text-base md:text-lg font-semibold text-gray-900">Snapshot History</h3>
            <p className="text-sm text-gray-600">Browse recent acknowledged alerts and logged events with captured evidence.</p>
          </div>
          <span className="text-xs text-gray-500">
            {visibleItemCount} snapshot{visibleItemCount === 1 ? '' : 's'} shown
          </span>
        </div>

        <div className="bg-white rounded-lg border border-gray-200 p-3 md:p-4">
          <div className="flex flex-col lg:flex-row gap-3">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder="Search code, title, or source node..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div className="flex items-center gap-2 w-full sm:w-auto">
              <Calendar className="w-4 h-4 text-gray-500" />
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

            <button
              type="button"
              onClick={() => setHistoryFiltersOpen((open) => !open)}
              className="inline-flex items-center justify-center gap-2 rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50"
              aria-expanded={historyFiltersOpen}
            >
              <Filter className="w-4 h-4" />
              {historyFiltersOpen ? 'Hide filters' : 'More filters'}
            </button>
          </div>

          {historyFiltersOpen && (
            <div className="mt-3 grid grid-cols-1 gap-3 border-t border-gray-100 pt-3 sm:grid-cols-2 xl:grid-cols-4">
              <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
                Severity
                <select
                  value={selectedSeverity}
                  onChange={(e) => setSelectedSeverity(e.target.value as SeverityLevel | 'all')}
                  className="w-full px-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="all">All Severities</option>
                  <option value="critical">Critical</option>
                  <option value="warning">Warning</option>
                  <option value="normal">Normal</option>
                  <option value="info">Info</option>
                </select>
              </label>

              <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
                Type
                <select
                  value={selectedType}
                  onChange={(e) => setSelectedType(e.target.value as EventType | 'all')}
                  className="w-full px-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="all">All Types</option>
                  <option value="intruder">Intruder</option>
                  <option value="fire">Fire</option>
                  <option value="sensor">Sensor</option>
                  <option value="authorized">Authorized</option>
                  <option value="system">System</option>
                </select>
              </label>

              <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
                Decision State
                <select
                  value={selectedDecision}
                  onChange={(e) => setSelectedDecision(e.target.value as DecisionFilter)}
                  className="w-full px-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="all">All Decisions</option>
                  <option value="unknown_face">Unknown Face</option>
                  <option value="face_unclear">Face Unclear</option>
                  <option value="no_face">No Face</option>
                  <option value="authorized">Authorized</option>
                </select>
              </label>

              <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
                Review Status
                <select
                  value={selectedReview}
                  onChange={(e) => setSelectedReview(e.target.value as ReviewFilter)}
                  className="w-full px-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="all">All Reviews</option>
                  <option value="needs_review">Needs Review</option>
                  <option value="confirmed">Confirmed</option>
                  <option value="false_positive">False Positive</option>
                  <option value="resolved">Resolved</option>
                  <option value="archived">Archived</option>
                </select>
              </label>
            </div>
          )}

          <div className="mt-3 pt-3 border-t border-gray-100 flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs md:text-sm text-gray-600">
              Snapshot history: <span className="font-semibold text-gray-900">{visibleItemCount}</span>
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
      </div>

      <div>
        {snapshotGalleryEvents.length > 0 ? (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {snapshotGalleryEvents.map((event) => (
              <SnapshotGalleryCard
                key={event.snapshotPath}
                event={event}
                highlighted={false}
                onOpen={(selected) => setSelectedEvent(selected)}
                selectable={bulkFalseAlarmMode}
                selected={bulkFalseAlarmIds.has(event.id)}
                bulkEligible={canBulkFalseAlarm(event)}
                onToggleSelected={toggleBulkFalseAlarmSelection}
              />
            ))}
          </div>
        ) : (
          <div className="rounded-lg border border-gray-200 bg-white py-12 text-center">
            <p className="text-gray-600">No snapshots found matching your filters.</p>
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

              {(selectedEvent.decisionState || selectedEvent.decisionConsensus || selectedEvent.decisionSamples?.length) ? (
                <div className="rounded-lg border border-blue-100 bg-blue-50 p-4">
                  <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <p className="text-sm font-medium text-blue-950">Decision Explanation</p>
                      <p className="text-sm text-blue-800">
                        Final state: <span className="font-semibold uppercase">{formatLabel(selectedEvent.decisionState || '')}</span>
                      </p>
                    </div>
                    <span className="rounded-full bg-white px-2.5 py-1 text-xs font-semibold text-blue-800">
                      {selectedEvent.consensusFrames || selectedEvent.decisionSamples?.length || 0} frame{(selectedEvent.consensusFrames || selectedEvent.decisionSamples?.length || 0) === 1 ? '' : 's'} checked
                    </span>
                  </div>

                  <div className="mt-3 grid grid-cols-1 gap-3 text-sm md:grid-cols-2">
                    <div className="rounded-lg bg-white p-3">
                      <p className="text-xs font-semibold uppercase tracking-wide text-blue-700">Consensus</p>
                      <p className="mt-1 font-medium text-gray-900">{formatLabel(selectedEvent.decisionConsensus || 'not recorded')}</p>
                      <p className="mt-1 text-xs text-gray-600">
                        Required agreement: {selectedEvent.consensusRequired || 2} matching frames.
                      </p>
                    </div>
                    <div className="rounded-lg bg-white p-3">
                      <p className="text-xs font-semibold uppercase tracking-wide text-blue-700">Votes</p>
                      {selectedEvent.decisionVotes && Object.keys(selectedEvent.decisionVotes).length > 0 ? (
                        <div className="mt-2 flex flex-wrap gap-2">
                          {Object.entries(selectedEvent.decisionVotes).map(([state, count]) => (
                            <span key={state} className="rounded-full border border-blue-100 bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-800">
                              {formatLabel(state)}: {count}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <p className="mt-1 text-xs text-gray-600">No vote breakdown recorded.</p>
                      )}
                    </div>
                  </div>

                  {selectedEvent.decisionSamples && selectedEvent.decisionSamples.length > 0 ? (
                    <div className="mt-3 overflow-hidden rounded-lg bg-white">
                      <div className="grid grid-cols-4 gap-2 border-b border-blue-50 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-blue-700">
                        <span>Frame</span>
                        <span>Decision</span>
                        <span>Face Status</span>
                        <span>Confidence</span>
                      </div>
                      {selectedEvent.decisionSamples.map((sample) => (
                        <div key={`${sample.frame}-${sample.decisionState}`} className="grid grid-cols-4 gap-2 px-3 py-2 text-xs text-gray-700 odd:bg-gray-50">
                          <span>#{sample.frame || '-'}</span>
                          <span>{formatLabel(sample.decisionState)}</span>
                          <span>{formatLabel(sample.faceStatus)}</span>
                          <span>{sample.confidence == null ? '-' : `${Number(sample.confidence).toFixed(1)}%`}</span>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>
              ) : null}

              <div>
                <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-medium text-gray-900">Camera Snapshot</p>
                </div>
                <div className="bg-gray-900 aspect-video rounded-lg flex items-center justify-center">
                  {selectedEvent.snapshotPath && !snapshotLoadFailed ? (
                    <img
                      src={selectedEvent.snapshotPath}
                      alt="Event snapshot"
                      loading="lazy"
                      className="h-full w-full object-contain"
                      onError={() => {
                        setSnapshotLoadFailed(true);
                      }}
                    />
                  ) : (
                    <div className="flex flex-col items-center gap-2 text-gray-600">
                      <ImageIcon className="w-12 h-12" />
                      <span className="text-xs">Snapshot unavailable</span>
                    </div>
                  )}
                </div>
              </div>

              <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
                  <div className="space-y-1">
                    <p className="text-sm font-medium text-gray-900">Continuous Improvement</p>
                    <p className="text-sm text-gray-600">
                      Confirm valid detections or mark false alarms to queue better training samples, then retrain once as a group.
                    </p>
                    {selectedEvent.reviewStatus ? (
                      <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                        Review status: {selectedEvent.reviewStatus.replace(/_/g, ' ')}
                      </p>
                    ) : null}
                  </div>

                  <button
                    type="button"
                    onClick={() => void handleGroupRetrain()}
                    disabled={groupTraining}
                    className="inline-flex items-center justify-center rounded-lg border border-blue-200 bg-white px-4 py-2 text-sm font-medium text-blue-700 transition-colors hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {groupTraining ? 'Retraining...' : 'Group Retrain Face Model'}
                  </button>

                  {canSubmitSnapshotFeedback(selectedEvent) ? (
                    <div className="flex flex-col gap-2 sm:min-w-64">
                      {isIntruderFeedbackEvent(selectedEvent) ? (
                        <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
                          Authorized person for false alarm
                          <select
                            value={feedbackProfileName}
                            onChange={(event) => setFeedbackProfileName(event.target.value)}
                            className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                          >
                            {feedbackProfiles.length === 0 ? (
                              <option value="">No profiles loaded</option>
                            ) : (
                              feedbackProfiles.map((profile) => (
                                <option key={profile.id || profile.label} value={profile.label}>
                                  {profile.label} ({profile.sampleCount ?? 0} samples)
                                </option>
                              ))
                            )}
                          </select>
                        </label>
                      ) : null}

                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() => void handleSnapshotFeedback(selectedEvent, 'confirmed')}
                          disabled={feedbackPendingId === selectedEvent.id}
                          className="inline-flex items-center justify-center rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          Confirm
                        </button>
                        <button
                          type="button"
                          onClick={() => void handleSnapshotFeedback(selectedEvent, 'false_positive')}
                          disabled={feedbackPendingId === selectedEvent.id || selectedFalseAlarmSnapshotUnavailable}
                          className="inline-flex items-center justify-center rounded-lg border border-amber-300 bg-amber-50 px-4 py-2 text-sm font-medium text-amber-800 transition-colors hover:bg-amber-100 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          False Alarm
                        </button>
                      </div>
                      {selectedFalseAlarmSnapshotUnavailable ? (
                        <p className="text-xs text-amber-700">
                          False-alarm training needs an existing snapshot file. This alert can still be confirmed, but it cannot be used as a training sample.
                        </p>
                      ) : null}
                    </div>
                  ) : (
                    <p className="text-sm text-gray-500">
                      Feedback is complete or unavailable for this snapshot type.
                    </p>
                  )}
                </div>
                {feedbackMessage ? (
                  <p className="mt-3 rounded-md border border-blue-100 bg-white px-3 py-2 text-sm text-blue-800">
                    {feedbackMessage}
                  </p>
                ) : null}
                {groupTrainMessage ? (
                  <p className="mt-3 rounded-md border border-green-100 bg-white px-3 py-2 text-sm text-green-800">
                    {groupTrainMessage}
                  </p>
                ) : null}
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
                <button
                  onClick={handleOpenCameraFeed}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  <Camera className="w-4 h-4" />
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
