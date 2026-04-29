export type SeverityLevel = 'critical' | 'warning' | 'normal' | 'info';
export type EventType = 'intruder' | 'fire' | 'sensor' | 'authorized' | 'system';
export type Room = 'Living Room' | 'Door Entrance Area' | string;
export type EventCode = string;
export type NodeId = string;

export interface FaceOverlay {
  bbox: [number, number, number, number];
  classification: string;
  confidence?: number;
  label: string;
}

export interface Alert {
  id: string;
  timestamp: string;
  severity: SeverityLevel;
  type: EventType;
  eventCode: EventCode;
  sourceNode: NodeId;
  location: Room;
  title: string;
  description: string;
  acknowledged: boolean;
  reviewStatus?: 'needs_review' | 'confirmed' | 'false_positive' | 'resolved' | 'archived';
  reviewNote?: string;
  reviewedBy?: string;
  reviewedTs?: string;
  responseTimeMs?: number;
  confidence?: number;
  fusionEvidence?: string[];
  snapshotPath?: string;
  faceOverlays?: FaceOverlay[];
}

export interface KPI {
  label: string;
  value: number;
  trend?: number;
  icon: string;
  subtitle?: string;
}

export interface SensorStatus {
  id: NodeId;
  name: string;
  location: Room | 'System';
  type: 'camera' | 'smoke' | 'force';
  status: 'online' | 'offline' | 'warning';
  lastUpdate: string;
  note: string;
}

export interface ServiceStatus {
  id: string;
  name: string;
  status: 'online' | 'offline' | 'warning';
  endpoint: string;
  lastUpdate: string;
  detail: string;
}

export interface DailyStats {
  date: string;
  authorizedFaces: number;
  unknownDetections: number;
  flameSignals: number;
  smokeHighEvents: number;
  fireAlerts: number;
  intruderAlerts: number;
  avgResponseSeconds: number;
}

export interface CameraFeed {
  location: Room;
  nodeId: 'cam_indoor' | 'cam_door' | string;
  status: 'online' | 'offline';
  quality: string;
  fps: number;
  latencyMs: number;
  streamPath?: string;
  streamAvailable?: boolean;
}

export interface DetectionPipeline {
  name: string;
  state: 'active' | 'degraded' | 'offline';
  detail: string;
}

export interface SystemHealth {
  host: 'online' | 'offline';
  sensorTransport: 'connected' | 'disconnected';
  backend: 'online' | 'offline';
  lastSync: string;
  uptime: string;
}

export interface AuthorizedProfile {
  id: string;
  dbId?: number;
  label: string;
  role: string;
  enrolledAt: string;
  sampleCount?: number;
}

export interface RuntimeSetting {
  key: string;
  value: string;
  description: string;
  editable?: boolean;
  secret?: boolean;
  configured?: boolean;
  group?: string;
  inputType?: 'text' | 'number' | 'switch' | 'secret';
  liveApply?: boolean;
  min?: number;
  max?: number;
  step?: number;
}
