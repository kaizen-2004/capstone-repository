import type {
  Alert,
  AuthorizedProfile,
  CameraFeed,
  DailyStats,
  DetectionPipeline,
  EventType,
  FaceOverlay,
  RuntimeSetting,
  SensorStatus,
  ServiceStatus,
  SeverityLevel,
  SystemHealth,
} from './types';

type Json = Record<string, unknown>;

export interface LiveEventsPayload {
  alerts: Alert[];
  events: Alert[];
}

export interface LiveNodesPayload {
  sensorStatuses: SensorStatus[];
  serviceStatuses: ServiceStatus[];
  cameraFeeds: CameraFeed[];
  detectionPipelines: DetectionPipeline[];
  systemHealth: SystemHealth;
}

export interface LiveSettingsPayload {
  guestMode: boolean;
  authorizedProfiles: AuthorizedProfile[];
  runtimeSettings: RuntimeSetting[];
}

export interface RuntimeSettingUpdatePayload {
  ok: boolean;
  key: string;
  value: string;
  description: string;
  secret: boolean;
  configured: boolean;
  group: string;
  inputType: RuntimeSetting['inputType'];
  liveApply: boolean;
}

export interface BackupStatusPayload {
  ok: boolean;
  count: number;
  files: Array<{
    name: string;
    sizeBytes: number;
    modifiedTs: string;
  }>;
  latest: {
    name: string;
    sizeBytes: number;
    modifiedTs: string;
  } | null;
}

export interface BackupCreatePayload {
  ok: boolean;
  name: string;
  sizeBytes: number;
}

export interface BackupRestorePayload {
  ok: boolean;
  name: string;
  snapshotsRestored: number;
  rollbackBackupName: string;
  scope: 'database_only' | 'database_and_snapshots';
  message: string;
}

export interface RetentionStatusPayload {
  ok: boolean;
  eventRetentionDays: number;
  logRetentionDays: number;
  regularSnapshotRetentionDays: number;
  criticalSnapshotRetentionDays: number;
  lastRunTs: string;
  lastEventsDeleted: number;
  lastLogsDeleted: number;
  lastSnapshotsDeleted: number;
}

export interface AlertReviewUpdatePayload {
  ok: boolean;
  alert: Alert;
}

export interface AlertReviewHistoryEntry {
  id: number;
  alertId: number;
  previousStatus: string;
  nextStatus: string;
  note: string;
  reviewedBy: string;
  reviewedTs: string;
}

export interface AuthUser {
  username: string;
}

export interface PasswordResetResult {
  ok: boolean;
  message: string;
}

export interface RecoveryCodeResult extends PasswordResetResult {
  recoveryCode: string;
}

export interface FaceTrainingStatus {
  ok: boolean;
  name: string;
  count: number;
  minRequired: number;
  target: number;
  remaining: number;
  ready: boolean;
  targetReached: boolean;
  error?: string;
}

export type CameraControlCommand = 'flash_on' | 'flash_off' | 'status';

export interface MobileRemoteStatus {
  ok: boolean;
  enabled: boolean;
  phase: string;
  route: string;
  localOnly: boolean;
  pushAvailable: boolean;
  pushEnabled: boolean;
  detail: string;
}

export type MobileNetworkMode = 'auto' | 'lan' | 'tailscale';

export interface MobileBootstrapPayload {
  ok: boolean;
  mobileRemoteEnabled: boolean;
  route: string;
  lanBaseUrl: string;
  tailscaleBaseUrl: string;
  mdnsBaseUrl: string;
  preferredBaseUrl: string;
  networkModes: MobileNetworkMode[];
  pushAvailable: boolean;
  pushEnabled: boolean;
  vapidPublicKey: string;
}

export interface RemoteAccessLinksPayload {
  ok: boolean;
  preferredUrl: string;
  tailscaleUrl: string;
  lanUrl: string;
  mdnsUrl: string;
  route: string;
  hostLabel: string;
  port: number;
  fingerprint: string;
}

export interface MdnsStatusPayload {
  ok: boolean;
  enabled: boolean;
  available: boolean;
  published: boolean;
  serviceName: string;
  hostname: string;
  port: number;
  boundIp: string;
  mdnsBaseUrl: string;
  detail: string;
}

export interface MobileDeviceRegistrationPayload {
  deviceId: string;
  platform?: string;
  networkMode?: MobileNetworkMode;
  pushSubscription?: PushSubscriptionJSON | Record<string, unknown>;
  pushToken?: string;
}

export interface MobileNotificationPreferences {
  ok: boolean;
  pushEnabled: boolean;
  quietHours: Record<string, unknown>;
  updatedTs: string;
}

export interface CameraControlResult {
  ok: boolean;
  nodeId: string;
  command: CameraControlCommand;
  topic: string;
}

function toInt(value: unknown, fallback = 0): number {
  const asNumber = Number(value);
  return Number.isFinite(asNumber) ? Math.trunc(asNumber) : fallback;
}

function toFloat(value: unknown, fallback = 0): number {
  const asNumber = Number(value);
  return Number.isFinite(asNumber) ? asNumber : fallback;
}

function normalizeSeverity(value: unknown): SeverityLevel {
  const key = String(value || '').toLowerCase();
  if (key === 'critical' || key === 'warning' || key === 'normal' || key === 'info') {
    return key;
  }
  return 'info';
}

function normalizeEventType(value: unknown): EventType {
  const key = String(value || '').toLowerCase();
  if (key === 'intruder' || key === 'fire' || key === 'sensor' || key === 'authorized' || key === 'system') {
    return key;
  }
  return 'system';
}

function normalizeNodeStatus(value: unknown): SensorStatus['status'] {
  const key = String(value || '').toLowerCase();
  if (key === 'online' || key === 'offline' || key === 'warning') {
    return key;
  }
  return 'offline';
}

function normalizeServiceStatus(value: unknown): ServiceStatus['status'] {
  const key = String(value || '').toLowerCase();
  if (key === 'online' || key === 'offline' || key === 'warning') {
    return key;
  }
  return 'offline';
}

function normalizeCameraStatus(value: unknown): CameraFeed['status'] {
  const key = String(value || '').toLowerCase();
  return key === 'online' ? 'online' : 'offline';
}

function normalizePipelineState(value: unknown): DetectionPipeline['state'] {
  const key = String(value || '').toLowerCase();
  if (key === 'active' || key === 'degraded' || key === 'offline') {
    return key;
  }
  return 'offline';
}

function normalizeSensorType(value: unknown): SensorStatus['type'] {
  const key = String(value || '').toLowerCase();
  if (key === 'camera' || key === 'smoke' || key === 'force') {
    return key;
  }
  return 'smoke';
}

function mapFaceOverlay(raw: Json): FaceOverlay | null {
  const bboxRaw = raw.bbox;
  if (!Array.isArray(bboxRaw) || bboxRaw.length !== 4) {
    return null;
  }

  const bboxNumbers = bboxRaw.map((value) => toInt(value, 0));
  if (bboxNumbers.some((value) => !Number.isFinite(value))) {
    return null;
  }

  return {
    bbox: [bboxNumbers[0], bboxNumbers[1], bboxNumbers[2], bboxNumbers[3]],
    classification: String(raw.classification ?? ''),
    confidence: raw.confidence == null ? undefined : toFloat(raw.confidence),
    label: String(raw.label ?? ''),
  };
}

function mapAlert(raw: Json, kind: 'alert' | 'event' = 'event'): Alert {
  const sourceNode = String(raw.source_node ?? raw.sourceNode ?? 'unknown');
  const location = String(raw.location ?? 'Door Entrance Area');
  const eventCode = String(raw.event_code ?? raw.eventCode ?? 'EVENT');
  const fusionRaw = raw.fusion_evidence;
  const fusionEvidence = Array.isArray(fusionRaw) ? fusionRaw.map((item) => String(item)) : [];
  const responseTimeMs = raw.response_time_ms == null ? undefined : toInt(raw.response_time_ms);
  const confidence = raw.confidence == null ? undefined : toInt(raw.confidence);
  const snapshotPathRaw = String(raw.snapshot_path ?? raw.snapshotPath ?? '').trim();
  const snapshotPath = snapshotPathRaw
    ? (snapshotPathRaw.startsWith('/') ? snapshotPathRaw : `/${snapshotPathRaw}`)
    : undefined;
  const faceOverlaysRaw = Array.isArray(raw.face_overlays) ? raw.face_overlays : [];
  const faceOverlays = faceOverlaysRaw
    .map((item) => mapFaceOverlay((item as Json) || {}))
    .filter((item): item is FaceOverlay => item !== null);

  const rawId = String(raw.id ?? '').trim();
  const normalizedId = rawId
    ? (rawId.startsWith('alert-') || rawId.startsWith('event-')
        ? rawId
        : `${kind}-${rawId}`)
    : '';

  return {
    id: normalizedId,
    timestamp: String(raw.timestamp ?? ''),
    severity: normalizeSeverity(raw.severity),
    type: normalizeEventType(raw.type),
    eventCode,
    sourceNode,
    location,
    title: String(raw.title ?? eventCode),
    description: String(raw.description ?? ''),
    acknowledged: Boolean(raw.acknowledged),
    reviewStatus: String(raw.review_status ?? raw.reviewStatus ?? 'needs_review').toLowerCase() as Alert['reviewStatus'],
    reviewNote: String(raw.review_note ?? raw.reviewNote ?? ''),
    reviewedBy: String(raw.reviewed_by ?? raw.reviewedBy ?? ''),
    reviewedTs: String(raw.reviewed_ts ?? raw.reviewedTs ?? ''),
    responseTimeMs,
    confidence,
    fusionEvidence,
    snapshotPath,
    faceOverlays: faceOverlays.length > 0 ? faceOverlays : undefined,
  };
}

function mapSensorStatus(raw: Json): SensorStatus {
  return {
    id: String(raw.id ?? ''),
    name: String(raw.name ?? 'Node'),
    location: String(raw.location ?? 'System'),
    type: normalizeSensorType(raw.type),
    status: normalizeNodeStatus(raw.status),
    lastUpdate: String(raw.last_update ?? raw.lastUpdate ?? ''),
    note: String(raw.note ?? ''),
  };
}

function mapServiceStatus(raw: Json): ServiceStatus {
  return {
    id: String(raw.id ?? ''),
    name: String(raw.name ?? 'Service'),
    status: normalizeServiceStatus(raw.status),
    endpoint: String(raw.endpoint ?? ''),
    lastUpdate: String(raw.last_update ?? raw.lastUpdate ?? ''),
    detail: String(raw.detail ?? ''),
  };
}

function mapCameraFeed(raw: Json): CameraFeed {
  return {
    location: String(raw.location ?? 'Living Room'),
    nodeId: String(raw.node_id ?? raw.nodeId ?? ''),
    status: normalizeCameraStatus(raw.status),
    quality: String(raw.quality ?? ''),
    fps: toInt(raw.fps),
    latencyMs: toInt(raw.latency_ms ?? raw.latencyMs),
    streamPath: String(raw.stream_path ?? raw.streamPath ?? ''),
    streamAvailable: Boolean(raw.stream_available ?? raw.streamAvailable),
  };
}

function mapDetectionPipeline(raw: Json): DetectionPipeline {
  return {
    name: String(raw.name ?? 'Pipeline'),
    state: normalizePipelineState(raw.state),
    detail: String(raw.detail ?? ''),
  };
}

function mapSystemHealth(raw: Json): SystemHealth {
  const host = raw.host === 'offline' ? 'offline' : 'online';
  const sensorTransport = raw.sensor_transport === 'disconnected' || raw.sensorTransport === 'disconnected'
    ? 'disconnected'
    : 'connected';
  const backend = raw.backend === 'offline' ? 'offline' : 'online';
  return {
    host,
    sensorTransport,
    backend,
    lastSync: String(raw.last_sync ?? raw.lastSync ?? new Date().toISOString()),
    uptime: String(raw.uptime ?? '-'),
  };
}

function mapDailyStat(raw: Json): DailyStats {
  return {
    date: String(raw.date ?? ''),
    authorizedFaces: toInt(raw.authorized_faces),
    unknownDetections: toInt(raw.unknown_detections),
    flameSignals: toInt(raw.flame_signals),
    smokeHighEvents: toInt(raw.smoke_high_events),
    fireAlerts: toInt(raw.fire_alerts),
    intruderAlerts: toInt(raw.intruder_alerts),
    avgResponseSeconds: toFloat(raw.avg_response_seconds),
  };
}

function mapProfile(raw: Json): AuthorizedProfile {
  return {
    id: String(raw.id ?? ''),
    dbId: toInt(raw.db_id),
    label: String(raw.label ?? ''),
    role: String(raw.role ?? 'Authorized'),
    enrolledAt: String(raw.enrolled_at ?? '-'),
    sampleCount: toInt(raw.sample_count),
  };
}

function mapRuntimeSetting(raw: Json): RuntimeSetting {
  const inputTypeRaw = String(raw.input_type ?? raw.inputType ?? 'text').toLowerCase();
  const inputType: RuntimeSetting['inputType'] =
    inputTypeRaw === 'number' || inputTypeRaw === 'switch' || inputTypeRaw === 'secret'
      ? (inputTypeRaw as RuntimeSetting['inputType'])
      : 'text';
  return {
    key: String(raw.key ?? ''),
    value: String(raw.value ?? ''),
    description: String(raw.description ?? ''),
    editable: raw.editable == null ? true : Boolean(raw.editable),
    secret: Boolean(raw.secret),
    configured: Boolean(raw.configured),
    group: String(raw.group ?? 'Runtime'),
    inputType,
    liveApply: Boolean(raw.live_apply ?? raw.liveApply),
    min: raw.min == null ? undefined : toFloat(raw.min),
    max: raw.max == null ? undefined : toFloat(raw.max),
    step: raw.step == null ? undefined : toFloat(raw.step),
  };
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    credentials: 'include',
    ...init,
  });
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    const errorMessage =
      payload && typeof payload === 'object' && ('error' in payload || 'detail' in payload)
        ? String((payload as Json).error ?? (payload as Json).detail)
        : `Request failed (${response.status}) for ${url}`;
    throw new Error(errorMessage);
  }
  return (payload || {}) as T;
}

export async function fetchLiveEvents(limit = 250): Promise<LiveEventsPayload> {
  const payload = await fetchJson<Json>(`/api/ui/events/live?limit=${Math.max(20, Math.min(limit, 500))}`);
  const alertsRaw = Array.isArray(payload.alerts) ? payload.alerts : [];
  const eventsRaw = Array.isArray(payload.events) ? payload.events : [];
  return {
    alerts: alertsRaw.map((row) => mapAlert(row as Json, 'alert')),
    events: eventsRaw.map((row) => mapAlert(row as Json, 'event')),
  };
}

export async function updateAlertReview(
  alertId: number,
  reviewStatus: 'needs_review' | 'confirmed' | 'false_positive' | 'resolved' | 'archived',
  reviewNote: string,
): Promise<AlertReviewUpdatePayload> {
  const payload = await fetchJson<Json>(`/api/alerts/${alertId}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      review_status: reviewStatus,
      review_note: reviewNote,
    }),
  });
  return {
    ok: Boolean(payload.ok),
    alert: mapAlert((payload.alert as Json) || {}, 'alert'),
  };
}

export async function fetchAlertReviewHistory(
  alertId: number,
  limit = 50,
): Promise<AlertReviewHistoryEntry[]> {
  const payload = await fetchJson<Json>(`/api/alerts/${alertId}/review/history?limit=${Math.max(1, Math.min(limit, 200))}`);
  const rows = Array.isArray(payload.history) ? payload.history : [];
  return rows.map((row) => {
    const item = (row as Json) || {};
    return {
      id: toInt(item.id),
      alertId: toInt(item.alert_id ?? item.alertId),
      previousStatus: String(item.previous_status ?? item.previousStatus ?? ''),
      nextStatus: String(item.next_status ?? item.nextStatus ?? ''),
      note: String(item.note ?? ''),
      reviewedBy: String(item.reviewed_by ?? item.reviewedBy ?? ''),
      reviewedTs: String(item.reviewed_ts ?? item.reviewedTs ?? ''),
    };
  });
}

export async function fetchBackupStatus(): Promise<BackupStatusPayload> {
  const payload = await fetchJson<Json>('/api/ui/backup/status');
  const latestRaw = payload.latest && typeof payload.latest === 'object' ? (payload.latest as Json) : null;
  const filesRaw = Array.isArray(payload.files) ? payload.files : [];
  return {
    ok: Boolean(payload.ok),
    count: toInt(payload.count),
    files: filesRaw.map((item) => {
      const row = (item as Json) || {};
      return {
        name: String(row.name ?? ''),
        sizeBytes: toInt(row.size_bytes ?? row.sizeBytes),
        modifiedTs: String(row.modified_ts ?? row.modifiedTs ?? ''),
      };
    }),
    latest: latestRaw
      ? {
          name: String(latestRaw.name ?? ''),
          sizeBytes: toInt(latestRaw.size_bytes ?? latestRaw.sizeBytes),
          modifiedTs: String(latestRaw.modified_ts ?? latestRaw.modifiedTs ?? ''),
        }
      : null,
  };
}

export async function createBackup(): Promise<BackupCreatePayload> {
  const payload = await fetchJson<Json>('/api/ui/backup/create', {
    method: 'POST',
  });
  return {
    ok: Boolean(payload.ok),
    name: String(payload.name ?? ''),
    sizeBytes: toInt(payload.size_bytes ?? payload.sizeBytes),
  };
}

export async function restoreBackup(name: string, includeSnapshots: boolean): Promise<BackupRestorePayload> {
  const payload = await fetchJson<Json>('/api/ui/backup/restore', {
    method: 'POST',
    body: JSON.stringify({ name, include_snapshots: includeSnapshots }),
  });
  return {
    ok: Boolean(payload.ok),
    name: String(payload.name ?? ''),
    snapshotsRestored: toInt(payload.snapshots_restored ?? payload.snapshotsRestored),
    rollbackBackupName: String(payload.rollback_backup_name ?? payload.rollbackBackupName ?? ''),
    scope: String(payload.scope ?? 'database_only') === 'database_and_snapshots' ? 'database_and_snapshots' : 'database_only',
    message: String(payload.message ?? 'Backup restored.'),
  };
}

export async function fetchRetentionStatus(): Promise<RetentionStatusPayload> {
  const payload = await fetchJson<Json>('/api/ui/retention/status');
  return {
    ok: Boolean(payload.ok),
    eventRetentionDays: toInt(payload.event_retention_days ?? payload.eventRetentionDays),
    logRetentionDays: toInt(payload.log_retention_days ?? payload.logRetentionDays),
    regularSnapshotRetentionDays: toInt(payload.regular_snapshot_retention_days ?? payload.regularSnapshotRetentionDays),
    criticalSnapshotRetentionDays: toInt(payload.critical_snapshot_retention_days ?? payload.criticalSnapshotRetentionDays),
    lastRunTs: String(payload.last_run_ts ?? payload.lastRunTs ?? ''),
    lastEventsDeleted: toInt(payload.last_events_deleted ?? payload.lastEventsDeleted),
    lastLogsDeleted: toInt(payload.last_logs_deleted ?? payload.lastLogsDeleted),
    lastSnapshotsDeleted: toInt(payload.last_snapshots_deleted ?? payload.lastSnapshotsDeleted),
  };
}

export async function fetchLiveNodes(): Promise<LiveNodesPayload> {
  const payload = await fetchJson<Json>('/api/ui/nodes/live');
  const sensorsRaw = Array.isArray(payload.sensor_statuses) ? payload.sensor_statuses : [];
  const servicesRaw = Array.isArray(payload.service_statuses) ? payload.service_statuses : [];
  const cameraRaw = Array.isArray(payload.camera_feeds) ? payload.camera_feeds : [];
  const pipelinesRaw = Array.isArray(payload.detection_pipelines) ? payload.detection_pipelines : [];
  const healthRaw = (payload.system_health as Json) || {};

  return {
    sensorStatuses: sensorsRaw.map((row) => mapSensorStatus(row as Json)),
    serviceStatuses: servicesRaw.map((row) => mapServiceStatus(row as Json)),
    cameraFeeds: cameraRaw.map((row) => mapCameraFeed(row as Json)),
    detectionPipelines: pipelinesRaw.map((row) => mapDetectionPipeline(row as Json)),
    systemHealth: mapSystemHealth(healthRaw),
  };
}

export async function fetchDailyStats(days = 7): Promise<DailyStats[]> {
  const payload = await fetchJson<Json>(`/api/ui/stats/daily?days=${Math.max(1, Math.min(days, 31))}`);
  const statsRaw = Array.isArray(payload.stats) ? payload.stats : [];
  return statsRaw.map((row) => mapDailyStat(row as Json));
}

export async function fetchSettingsLive(): Promise<LiveSettingsPayload> {
  const payload = await fetchJson<Json>('/api/ui/settings/live');
  const profilesRaw = Array.isArray(payload.authorized_profiles) ? payload.authorized_profiles : [];
  const settingsRaw = Array.isArray(payload.runtime_settings) ? payload.runtime_settings : [];
  return {
    guestMode: Boolean(payload.guest_mode),
    authorizedProfiles: profilesRaw.map((row) => mapProfile(row as Json)),
    runtimeSettings: settingsRaw.map((row) => mapRuntimeSetting(row as Json)),
  };
}

export async function updateRuntimeSetting(key: string, value: string): Promise<RuntimeSettingUpdatePayload> {
  const payload = await fetchJson<Json>('/api/ui/settings/runtime', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ key, value }),
  });
  return {
    ok: Boolean(payload.ok),
    key: String(payload.key ?? key),
    value: String(payload.value ?? value),
    description: String(payload.description ?? ''),
    secret: Boolean(payload.secret),
    configured: Boolean(payload.configured),
    group: String(payload.group ?? 'Runtime'),
    inputType: String(payload.input_type ?? payload.inputType ?? 'text') as RuntimeSetting['inputType'],
    liveApply: Boolean(payload.live_apply ?? payload.liveApply),
  };
}

export async function sendCameraControl(
  nodeId: string,
  command: CameraControlCommand,
): Promise<CameraControlResult> {
  const payload = await fetchJson<Json>('/api/ui/camera/control', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      node_id: nodeId,
      command,
    }),
  });

  return {
    ok: Boolean(payload.ok),
    nodeId: String(payload.node_id ?? nodeId),
    command: String(payload.command ?? command) as CameraControlCommand,
    topic: String(payload.topic ?? ''),
  };
}

export async function createFaceProfile(name: string, note = ''): Promise<AuthorizedProfile> {
  const payload = await fetchJson<Json>('/api/faces', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, note }),
  });
  const faceRaw = (payload.face as Json) || {};
  return mapProfile(faceRaw);
}

export async function deleteFaceProfile(dbId: number): Promise<void> {
  await fetchJson<Json>(`/api/faces/${dbId}`, { method: 'DELETE' });
}

export async function updateFaceProfile(
  dbId: number,
  input: { name?: string; note?: string },
): Promise<AuthorizedProfile> {
  const payload = await fetchJson<Json>(`/api/faces/${dbId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: input.name,
      note: input.note,
    }),
  });
  const faceRaw = (payload.face as Json) || {};
  return mapProfile(faceRaw);
}

function mapTrainingStatus(raw: Json): FaceTrainingStatus {
  return {
    ok: Boolean(raw.ok),
    name: String(raw.name ?? ''),
    count: toInt(raw.count),
    minRequired: toInt(raw.min_required),
    target: toInt(raw.target),
    remaining: toInt(raw.remaining),
    ready: Boolean(raw.ready),
    targetReached: Boolean(raw.target_reached),
    error: raw.error == null ? undefined : String(raw.error),
  };
}

export async function fetchFaceTrainingStatus(name: string): Promise<FaceTrainingStatus> {
  const encoded = encodeURIComponent(name.trim());
  const payload = await fetchJson<Json>(`/api/training/face/status?name=${encoded}`);
  return mapTrainingStatus(payload);
}

export async function captureFaceTrainingSample(name: string, imageDataUrl: string): Promise<FaceTrainingStatus> {
  const payload = await fetchJson<Json>('/api/training/face/capture', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, image: imageDataUrl }),
  });
  return mapTrainingStatus(payload);
}

export async function captureFaceTrainingSampleFromNode(
  name: string,
  nodeId: 'cam_indoor' | 'cam_door',
): Promise<FaceTrainingStatus> {
  const payload = await fetchJson<Json>('/api/training/face/capture-node', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, node_id: nodeId }),
  });
  return mapTrainingStatus(payload);
}

export async function trainFaceModel(): Promise<{ ok: boolean; message: string }> {
  const payload = await fetchJson<Json>('/api/training/face/train', {
    method: 'POST',
  });
  return {
    ok: Boolean(payload.ok),
    message: String(payload.message ?? ''),
  };
}

export async function fetchAuthMe(): Promise<AuthUser> {
  const payload = await fetchJson<Json>('/api/auth/me');
  const user = (payload.user as Json) || {};
  return {
    username: String(user.username ?? 'admin'),
  };
}

export async function login(username: string, password: string): Promise<AuthUser> {
  const payload = await fetchJson<Json>('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  const user = (payload.user as Json) || {};
  return {
    username: String(user.username ?? username),
  };
}

export async function logout(): Promise<void> {
  await fetchJson<Json>('/api/auth/logout', {
    method: 'POST',
  });
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<PasswordResetResult> {
  const payload = await fetchJson<Json>('/api/auth/change-password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  });
  return {
    ok: Boolean(payload.ok),
    message: String(payload.message ?? 'Password updated.'),
  };
}

export async function regenerateRecoveryCode(): Promise<RecoveryCodeResult> {
  const payload = await fetchJson<Json>('/api/auth/recovery-code/regenerate', {
    method: 'POST',
  });
  return {
    ok: Boolean(payload.ok),
    message: String(payload.message ?? ''),
    recoveryCode: String(payload.recovery_code ?? payload.recoveryCode ?? ''),
  };
}

export async function resetPasswordWithRecoveryCode(
  username: string,
  recoveryCode: string,
  newPassword: string,
): Promise<PasswordResetResult> {
  const payload = await fetchJson<Json>('/api/auth/reset-password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      username,
      recovery_code: recoveryCode,
      new_password: newPassword,
    }),
  });
  return {
    ok: Boolean(payload.ok),
    message: String(payload.message ?? 'Password reset successfully.'),
  };
}

export async function fetchMobileRemoteStatus(): Promise<MobileRemoteStatus> {
  const payload = await fetchJson<Json>('/api/remote/mobile/status');
  return {
    ok: Boolean(payload.ok),
    enabled: Boolean(payload.enabled),
    phase: String(payload.phase ?? ''),
    route: String(payload.route ?? '/dashboard/remote/mobile'),
    localOnly: Boolean(payload.local_only ?? payload.localOnly),
    pushAvailable: Boolean(payload.push_available ?? payload.pushAvailable),
    pushEnabled: Boolean(payload.push_enabled ?? payload.pushEnabled),
    detail: String(payload.detail ?? ''),
  };
}

export async function setMobileRemoteEnabled(enabled: boolean): Promise<MobileRemoteStatus> {
  await fetchJson<Json>('/api/remote/mobile/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled }),
  });
  return fetchMobileRemoteStatus();
}

export async function fetchMobileBootstrap(): Promise<MobileBootstrapPayload> {
  const payload = await fetchJson<Json>('/api/mobile/bootstrap');
  const modesRaw = Array.isArray(payload.network_modes) ? payload.network_modes : ['auto', 'lan', 'tailscale'];
  const modes = modesRaw
    .map((mode) => String(mode).toLowerCase())
    .filter((mode): mode is MobileNetworkMode => mode === 'auto' || mode === 'lan' || mode === 'tailscale');
  return {
    ok: Boolean(payload.ok),
    mobileRemoteEnabled: Boolean(payload.mobile_remote_enabled ?? payload.mobileRemoteEnabled),
    route: String(payload.route ?? '/dashboard/remote/mobile'),
    lanBaseUrl: String(payload.lan_base_url ?? payload.lanBaseUrl ?? ''),
    tailscaleBaseUrl: String(payload.tailscale_base_url ?? payload.tailscaleBaseUrl ?? ''),
    mdnsBaseUrl: String(payload.mdns_base_url ?? payload.mdnsBaseUrl ?? ''),
    preferredBaseUrl: String(payload.preferred_base_url ?? payload.preferredBaseUrl ?? ''),
    networkModes: modes.length > 0 ? modes : ['auto', 'lan', 'tailscale'],
    pushAvailable: Boolean(payload.push_available ?? payload.pushAvailable),
    pushEnabled: Boolean(payload.push_enabled ?? payload.pushEnabled),
    vapidPublicKey: String(payload.vapid_public_key ?? payload.vapidPublicKey ?? ''),
  };
}

export async function registerMobileDevice(payload: MobileDeviceRegistrationPayload): Promise<void> {
  await fetchJson<Json>('/api/mobile/device/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      device_id: payload.deviceId,
      platform: payload.platform ?? 'web_pwa',
      network_mode: payload.networkMode ?? 'auto',
      push_subscription: payload.pushSubscription ?? null,
      push_token: payload.pushToken ?? '',
    }),
  });
}

export async function unregisterMobileDevice(deviceId: string): Promise<void> {
  await fetchJson<Json>('/api/mobile/device/unregister', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ device_id: deviceId }),
  });
}

export async function fetchMobileNotificationPreferences(): Promise<MobileNotificationPreferences> {
  const payload = await fetchJson<Json>('/api/mobile/notifications/preferences');
  return {
    ok: Boolean(payload.ok),
    pushEnabled: Boolean(payload.push_enabled ?? payload.pushEnabled),
    quietHours:
      payload.quiet_hours && typeof payload.quiet_hours === 'object'
        ? (payload.quiet_hours as Record<string, unknown>)
        : {},
    updatedTs: String(payload.updated_ts ?? payload.updatedTs ?? ''),
  };
}

export async function saveMobileNotificationPreferences(
  input: Partial<Pick<MobileNotificationPreferences, 'pushEnabled' | 'quietHours'>>,
): Promise<MobileNotificationPreferences> {
  const payload = await fetchJson<Json>('/api/mobile/notifications/preferences', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      push_enabled: input.pushEnabled,
      quiet_hours: input.quietHours,
    }),
  });
  return {
    ok: Boolean(payload.ok),
    pushEnabled: Boolean(payload.push_enabled ?? payload.pushEnabled),
    quietHours:
      payload.quiet_hours && typeof payload.quiet_hours === 'object'
        ? (payload.quiet_hours as Record<string, unknown>)
        : {},
    updatedTs: String(payload.updated_ts ?? payload.updatedTs ?? ''),
  };
}

export async function fetchRemoteAccessLinks(): Promise<RemoteAccessLinksPayload> {
  const payload = await fetchJson<Json>('/api/remote/access/links');
  return {
    ok: Boolean(payload.ok),
    preferredUrl: String(payload.preferred_url ?? payload.preferredUrl ?? ''),
    tailscaleUrl: String(payload.tailscale_url ?? payload.tailscaleUrl ?? ''),
    lanUrl: String(payload.lan_url ?? payload.lanUrl ?? ''),
    mdnsUrl: String(payload.mdns_url ?? payload.mdnsUrl ?? ''),
    route: String(payload.route ?? '/dashboard/remote/mobile'),
    hostLabel: String(payload.host_label ?? payload.hostLabel ?? ''),
    port: toInt(payload.port, 0),
    fingerprint: String(payload.fingerprint ?? ''),
  };
}

export async function fetchMdnsStatus(): Promise<MdnsStatusPayload> {
  const payload = await fetchJson<Json>('/api/integrations/mdns/status');
  return {
    ok: Boolean(payload.ok),
    enabled: Boolean(payload.enabled),
    available: Boolean(payload.available),
    published: Boolean(payload.published),
    serviceName: String(payload.service_name ?? payload.serviceName ?? ''),
    hostname: String(payload.hostname ?? ''),
    port: toInt(payload.port, 0),
    boundIp: String(payload.bound_ip ?? payload.boundIp ?? ''),
    mdnsBaseUrl: String(payload.mdns_base_url ?? payload.mdnsBaseUrl ?? ''),
    detail: String(payload.detail ?? ''),
  };
}
