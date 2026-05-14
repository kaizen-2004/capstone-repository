import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Bell,
  Camera,
  Database,
  Link2,
  Pencil,
  Shield,
  User,
  UserPlus,
  Wifi,
  X,
} from 'lucide-react';
import {
  captureFaceTrainingSample,
  captureFaceTrainingSampleFromNode,
  createFaceProfile,
  deleteFaceProfile,
  fetchFaceTrainingStatus,
  fetchMobileRemoteStatus,
  fetchRemoteAccessLinks,
  fetchSettingsLive,
  changePassword,
  createBackup,
  regenerateRecoveryCode,
  fetchBackupStatus,
  fetchLiveNodes,
  fetchRetentionStatus,
  updateGuestMode,
  trainFaceModel,
  updateFaceProfile,
  updateRuntimeSetting,
  type FaceTrainingStatus,
  type MobileRemoteStatus,
  type BackupStatusPayload,
  type GuestModeStatusPayload,
  type RetentionStatusPayload,
  type RemoteAccessLinksPayload,
} from '../data/liveApi';
import type {
  AuthorizedProfile,
  CameraFeed,
  DetectionPipeline,
  RuntimeSetting,
  SensorStatus,
  ServiceStatus,
  SystemHealth,
} from '../data/types';
import { StatusBadge } from '../components/StatusBadge';
import { Slider } from '../components/ui/slider';

type GuidedPoseId = 'center' | 'left' | 'right' | 'up' | 'down';

type GuidedPoseStep = {
  id: GuidedPoseId;
  label: string;
  instruction: string;
  quota: number;
};

const GUIDED_POSE_PLAN: GuidedPoseStep[] = [
  {
    id: 'center',
    label: 'Center',
    instruction: 'Stay still and keep your face centered inside the guide.',
    quota: 12,
  },
  {
    id: 'left',
    label: 'Left',
    instruction: 'Slowly turn your face to the left and hold still.',
    quota: 8,
  },
  {
    id: 'right',
    label: 'Right',
    instruction: 'Slowly turn your face to the right and hold still.',
    quota: 8,
  },
  {
    id: 'up',
    label: 'Up',
    instruction: 'Raise your chin slightly and keep your face in the guide.',
    quota: 6,
  },
  {
    id: 'down',
    label: 'Down',
    instruction: 'Lower your chin slightly and keep your face in the guide.',
    quota: 6,
  },
];

const GUIDED_CAPTURE_TARGET = 40;
const GUIDED_CAPTURE_INTERVAL_MS = 1000;

const SETTINGS_NAV = [
  {
    id: 'alerts',
    label: 'Alerts',
    icon: Bell,
    sections: [{ id: 'alerts-routing', label: 'Routing' }],
  },
  {
    id: 'profiles',
    label: 'Profiles',
    icon: User,
    sections: [{ id: 'profiles-authorized', label: 'Authorized Faces' }],
  },
  {
    id: 'runtime',
    label: 'Runtime',
    icon: Shield,
    sections: [
      { id: 'runtime-access', label: 'Access' },
      { id: 'runtime-controls', label: 'Controls' },
      { id: 'runtime-security', label: 'Security' },
      { id: 'runtime-backup', label: 'Backup' },
    ],
  },
  {
    id: 'mobile',
    label: 'Mobile',
    icon: Camera,
    sections: [{ id: 'mobile-remote', label: 'Remote' }],
  },
] as const;

type SettingsStep = (typeof SETTINGS_NAV)[number]['id'];
type SettingsSection = (typeof SETTINGS_NAV)[number]['sections'][number]['id'];

const DEFAULT_SECTION_BY_STEP: Record<SettingsStep, SettingsSection> = {
  alerts: 'alerts-routing',
  profiles: 'profiles-authorized',
  runtime: 'runtime-access',
  mobile: 'mobile-remote',
};

type RuntimePreset = {
  label: string;
  value: string;
  helper: string;
};

type RuntimeControlMeta = {
  title: string;
  group: string;
  description: string;
  presets?: RuntimePreset[];
};

const GUEST_MODE_PRESETS: RuntimePreset[] = [
  { label: '1h', value: '1', helper: '1 hour' },
  { label: '2h', value: '2', helper: '2 hours' },
  { label: '4h', value: '4', helper: '4 hours' },
  { label: '8h', value: '8', helper: '8 hours' },
  { label: '12h', value: '12', helper: '12 hours' },
  { label: '24h', value: '24', helper: '24 hours' },
];

const RUNTIME_CONTROL_META: Record<string, RuntimeControlMeta> = {
  FACE_COSINE_THRESHOLD: {
    title: 'Face Match Strictness',
    group: 'Detection Sensitivity',
    description: 'How strict the system is before treating a face as authorized.',
    presets: [
      { label: 'Relaxed', value: '0.50', helper: '0.50' },
      { label: 'Balanced', value: '0.60', helper: '0.60' },
      { label: 'Strict', value: '0.75', helper: '0.75' },
      { label: 'Very strict', value: '0.85', helper: '0.85' },
    ],
  },
  FACE_UNCERTAIN_THRESHOLD: {
    title: 'Face Uncertainty Band',
    group: 'Detection Sensitivity',
    description: 'How much room the system gives borderline face matches before calling them unknown.',
    presets: [
      { label: 'Narrow', value: '0.05', helper: '0.05' },
      { label: 'Balanced', value: '0.10', helper: '0.10' },
      { label: 'Wider', value: '0.20', helper: '0.20' },
    ],
  },
  FIRE_MODEL_ENABLED: {
    title: 'Fire Vision Scanning',
    group: 'Detection Sensitivity',
    description: 'Run camera-frame flame scanning continuously.',
  },
  FIRE_MODEL_THRESHOLD: {
    title: 'Fire Detection Sensitivity',
    group: 'Detection Sensitivity',
    description: 'How easily the vision model reports possible flame activity.',
    presets: [
      { label: 'Very sensitive', value: '0.25', helper: '0.25' },
      { label: 'Sensitive', value: '0.40', helper: '0.40' },
      { label: 'Balanced', value: '0.60', helper: '0.60' },
      { label: 'Conservative', value: '0.75', helper: '0.75' },
      { label: 'Very conservative', value: '0.90', helper: '0.90' },
    ],
  },
  INTRUDER_EVENT_COOLDOWN_SECONDS: {
    title: 'Intruder Alert Cooldown',
    group: 'Detection Timing',
    description: 'How often repeated intruder triggers can create new events.',
    presets: [
      { label: 'Frequent', value: '30', helper: '30s' },
      { label: 'Balanced', value: '120', helper: '120s' },
      { label: 'Quiet', value: '300', helper: '300s' },
    ],
  },
  AUTHORIZED_PRESENCE_LOGGING_ENABLED: {
    title: 'Authorized Entry Logging',
    group: 'Detection Timing',
    description: 'Auto-log recognized authorized entries from the live camera view.',
  },
  AUTHORIZED_PRESENCE_SCAN_SECONDS: {
    title: 'Authorized Scan Pace',
    group: 'Detection Timing',
    description: 'How often the backend checks for authorized presence.',
    presets: [
      { label: 'Fast', value: '3', helper: '3s' },
      { label: 'Balanced', value: '10', helper: '10s' },
      { label: 'Battery friendly', value: '20', helper: '20s' },
    ],
  },
  AUTHORIZED_PRESENCE_COOLDOWN_SECONDS: {
    title: 'Authorized Entry Cooldown',
    group: 'Detection Timing',
    description: 'How often repeated authorized entries are logged.',
    presets: [
      { label: 'Frequent', value: '30', helper: '30s' },
      { label: 'Balanced', value: '120', helper: '120s' },
      { label: 'Quiet', value: '300', helper: '300s' },
    ],
  },
  UNKNOWN_PRESENCE_COOLDOWN_SECONDS: {
    title: 'Unknown Entry Cooldown',
    group: 'Detection Timing',
    description: 'How often repeated unknown-person entries are logged.',
    presets: [
      { label: 'Frequent', value: '30', helper: '30s' },
      { label: 'Balanced', value: '120', helper: '120s' },
      { label: 'Quiet', value: '300', helper: '300s' },
    ],
  },
  NODE_OFFLINE_SECONDS: {
    title: 'Sensor Offline Window',
    group: 'Health Windows',
    description: 'How quickly sensor nodes are marked offline after silence.',
    presets: [
      { label: 'Fast alert', value: '30', helper: '30s' },
      { label: 'Balanced', value: '120', helper: '120s' },
      { label: 'Lenient', value: '300', helper: '300s' },
    ],
  },
  CAMERA_OFFLINE_SECONDS: {
    title: 'Camera Offline Window',
    group: 'Health Windows',
    description: 'How quickly camera streams are marked disconnected.',
    presets: [
      { label: 'Fast alert', value: '15', helper: '15s' },
      { label: 'Balanced', value: '45', helper: '45s' },
      { label: 'Lenient', value: '120', helper: '120s' },
    ],
  },
  EVENT_RETENTION_DAYS: {
    title: 'Event History Retention',
    group: 'Retention Windows',
    description: 'How long event history is kept before cleanup.',
    presets: [
      { label: 'Short', value: '7', helper: '7 days' },
      { label: 'Standard', value: '30', helper: '30 days' },
      { label: 'Long', value: '90', helper: '90 days' },
      { label: 'Archive', value: '180', helper: '180 days' },
    ],
  },
  LOG_RETENTION_DAYS: {
    title: 'System Log Retention',
    group: 'Retention Windows',
    description: 'How long backend logs are kept before cleanup.',
    presets: [
      { label: 'Short', value: '7', helper: '7 days' },
      { label: 'Standard', value: '30', helper: '30 days' },
      { label: 'Long', value: '90', helper: '90 days' },
      { label: 'Archive', value: '180', helper: '180 days' },
    ],
  },
  REGULAR_SNAPSHOT_RETENTION_DAYS: {
    title: 'Regular Snapshot Retention',
    group: 'Retention Windows',
    description: 'How long routine snapshots are kept.',
    presets: [
      { label: 'Short', value: '7', helper: '7 days' },
      { label: 'Standard', value: '30', helper: '30 days' },
      { label: 'Long', value: '90', helper: '90 days' },
      { label: 'Archive', value: '180', helper: '180 days' },
    ],
  },
  CRITICAL_SNAPSHOT_RETENTION_DAYS: {
    title: 'Critical Snapshot Retention',
    group: 'Retention Windows',
    description: 'How long critical alert snapshots are kept.',
    presets: [
      { label: 'Short', value: '30', helper: '30 days' },
      { label: 'Standard', value: '90', helper: '90 days' },
      { label: 'Long', value: '180', helper: '180 days' },
      { label: 'Archive', value: '365', helper: '365 days' },
    ],
  },
};

const RUNTIME_CONTROL_GROUPS = [
  'Detection Sensitivity',
  'Detection Timing',
  'Health Windows',
  'Retention Windows',
] as const;

const RUNTIME_CONTROL_ORDER = Object.keys(RUNTIME_CONTROL_META);

function toRuntimeNumber(value: string): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function nearestPresetIndex(presets: RuntimePreset[], value: string): number {
  const target = toRuntimeNumber(value);
  let nearestIndex = 0;
  let nearestDistance = Number.POSITIVE_INFINITY;
  presets.forEach((preset, index) => {
    const distance = Math.abs(toRuntimeNumber(preset.value) - target);
    if (distance < nearestDistance) {
      nearestIndex = index;
      nearestDistance = distance;
    }
  });
  return nearestIndex;
}

function detectionPipelineSeverity(state: DetectionPipeline['state']): 'online' | 'warning' | 'offline' {
  if (state === 'active') {
    return 'online';
  }
  if (state === 'degraded') {
    return 'warning';
  }
  return 'offline';
}

function formatGuestModeRemaining(seconds: number): string {
  const safeSeconds = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(safeSeconds / 3600);
  const minutes = Math.floor((safeSeconds % 3600) / 60);
  if (hours <= 0) {
    return `${Math.max(1, minutes)}m remaining`;
  }
  return minutes > 0 ? `${hours}h ${minutes}m remaining` : `${hours}h remaining`;
}

function formatGuestModeUntil(untilTs: string): string {
  if (!untilTs) {
    return '';
  }
  const until = new Date(untilTs);
  if (Number.isNaN(until.getTime())) {
    return '';
  }
  return until.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}

function guestModeRemainingSeconds(status: GuestModeStatusPayload | null, nowMs: number): number {
  if (!status?.active || !status.untilTs) {
    return 0;
  }
  const untilMs = new Date(status.untilTs).getTime();
  if (!Number.isFinite(untilMs)) {
    return status.remainingSeconds;
  }
  return Math.max(0, Math.floor((untilMs - nowMs) / 1000));
}

function emptyGuidedPoseCounts(): Record<GuidedPoseId, number> {
  return {
    center: 0,
    left: 0,
    right: 0,
    up: 0,
    down: 0,
  };
}

function distributeGuidedPoseCounts(totalAccepted: number): {
  counts: Record<GuidedPoseId, number>;
  currentIndex: number;
} {
  const next = emptyGuidedPoseCounts();
  let remaining = Math.max(0, totalAccepted);
  let currentIndex = GUIDED_POSE_PLAN.length - 1;

  for (let index = 0; index < GUIDED_POSE_PLAN.length; index += 1) {
    const step = GUIDED_POSE_PLAN[index];
    const acceptedForStep = Math.min(step.quota, remaining);
    next[step.id] = acceptedForStep;
    remaining = Math.max(0, remaining - acceptedForStep);
    if (acceptedForStep < step.quota) {
      currentIndex = index;
      break;
    }
  }

  return { counts: next, currentIndex };
}

export function Settings() {
  const [authorizedProfiles, setAuthorizedProfiles] = useState<AuthorizedProfile[]>([]);
  const [activeSettingsStep, setActiveSettingsStep] = useState<SettingsStep>('alerts');
  const [activeSettingsSection, setActiveSettingsSection] = useState<SettingsSection>('alerts-routing');
  const [runtimeSettings, setRuntimeSettings] = useState<RuntimeSetting[]>([]);
  const [runtimeDrafts, setRuntimeDrafts] = useState<Record<string, string>>({});
  const [runtimeSaveMessages, setRuntimeSaveMessages] = useState<Record<string, string>>({});
  const [runtimeSavingKey, setRuntimeSavingKey] = useState<string | null>(null);
  const [runtimeSecretReplaceMode, setRuntimeSecretReplaceMode] = useState<Record<string, boolean>>({});
  const [guestModeStatus, setGuestModeStatus] = useState<GuestModeStatusPayload | null>(null);
  const [guestModeDraftHours, setGuestModeDraftHours] = useState('2');
  const [guestModeBusy, setGuestModeBusy] = useState(false);
  const [guestModeMessage, setGuestModeMessage] = useState('');
  const [guestModeTick, setGuestModeTick] = useState(() => Date.now());
  const [showAddUserModal, setShowAddUserModal] = useState(false);
  const [newUserName, setNewUserName] = useState('');
  const [newUserRole, setNewUserRole] = useState('Family Member');
  const [trainingStatus, setTrainingStatus] = useState<FaceTrainingStatus | null>(null);
  const [trainingComplete, setTrainingComplete] = useState(false);
  const [trainingMessage, setTrainingMessage] = useState('');
  const [trainingError, setTrainingError] = useState('');
  const [trainingCameraSource, setTrainingCameraSource] = useState<'device' | 'system'>('device');
  const [showSystemCameraFallback, setShowSystemCameraFallback] = useState(false);
  const [trainingSystemCameraNode, setTrainingSystemCameraNode] = useState<'cam_indoor' | 'cam_door'>('cam_indoor');
  const [systemPreviewTick, setSystemPreviewTick] = useState(() => Date.now());
  const [isCameraStarting, setIsCameraStarting] = useState(false);
  const [isCameraLive, setIsCameraLive] = useState(false);
  const [isCapturingSample, setIsCapturingSample] = useState(false);
  const [capturedSamples, setCapturedSamples] = useState(0);
  const [isGuidedCaptureActive, setIsGuidedCaptureActive] = useState(false);
  const [guidedPoseCounts, setGuidedPoseCounts] = useState<Record<GuidedPoseId, number>>(emptyGuidedPoseCounts());
  const [guidedStepIndex, setGuidedStepIndex] = useState(0);
  const [sessionBaseSampleCount, setSessionBaseSampleCount] = useState(0);
  const [autoTrainStarted, setAutoTrainStarted] = useState(false);
  const [requiresManualTrainRetry, setRequiresManualTrainRetry] = useState(false);
  const [isTraining, setIsTraining] = useState(false);
  const [isSavingUser, setIsSavingUser] = useState(false);
  const [deletingFaceId, setDeletingFaceId] = useState<number | null>(null);
  const [editingFaceId, setEditingFaceId] = useState<number | null>(null);
  const [showEditProfileModal, setShowEditProfileModal] = useState(false);
  const [editProfileTarget, setEditProfileTarget] = useState<AuthorizedProfile | null>(null);
  const [editProfileName, setEditProfileName] = useState('');
  const [editProfileRole, setEditProfileRole] = useState('');
  const [profilesLoading, setProfilesLoading] = useState(true);
  const [profilesError, setProfilesError] = useState('');
  const [profilesMessage, setProfilesMessage] = useState('');
  const [mobileRemoteStatus, setMobileRemoteStatus] = useState<MobileRemoteStatus | null>(null);
  const [remoteLinks, setRemoteLinks] = useState<RemoteAccessLinksPayload | null>(null);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [accountSecurityMessage, setAccountSecurityMessage] = useState('');
  const [accountSecurityError, setAccountSecurityError] = useState('');
  const [accountSecurityBusy, setAccountSecurityBusy] = useState(false);
  const [recoveryCode, setRecoveryCode] = useState('');
  const [backupStatus, setBackupStatus] = useState<BackupStatusPayload | null>(null);
  const [retentionStatus, setRetentionStatus] = useState<RetentionStatusPayload | null>(null);
  const [sensorStatuses, setSensorStatuses] = useState<SensorStatus[]>([]);
  const [serviceStatuses, setServiceStatuses] = useState<ServiceStatus[]>([]);
  const [cameraFeeds, setCameraFeeds] = useState<CameraFeed[]>([]);
  const [detectionPipelines, setDetectionPipelines] = useState<DetectionPipeline[]>([]);
  const [systemHealth, setSystemHealth] = useState<SystemHealth | null>(null);
  const [liveNodesError, setLiveNodesError] = useState('');
  const [backupBusy, setBackupBusy] = useState(false);
  const [backupMessage, setBackupMessage] = useState('');
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const cameraStreamRef = useRef<MediaStream | null>(null);
  const captureLoopBusyRef = useRef(false);

  const stopCameraStream = () => {
    const stream = cameraStreamRef.current;
    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
      cameraStreamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setIsCameraLive(false);
  };

  const syncRuntimeDrafts = useCallback((items: RuntimeSetting[]) => {
    setRuntimeDrafts((previous) => {
      const next = { ...previous };
      for (const item of items) {
        if (!(item.key in next)) {
          next[item.key] = item.secret ? '' : item.value;
        }
      }
      return next;
    });
  }, []);

  const startCameraStream = useCallback(async () => {
    if (trainingCameraSource !== 'device') {
      return false;
    }
    if (cameraStreamRef.current) {
      return true;
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      setShowSystemCameraFallback(true);
      setTrainingError(
        'Device camera is unavailable in this browser context. Open the dashboard in your phone browser over HTTPS. System Camera Feed fallback is available.',
      );
      return false;
    }

    setIsCameraStarting(true);
    setTrainingError('');
    try {
      let stream: MediaStream | null = null;
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: { ideal: 'user' },
            width: { ideal: 1280 },
            height: { ideal: 720 },
          },
          audio: false,
        });
      } catch {
        stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      }
      cameraStreamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setIsCameraLive(true);
      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Camera access denied or unavailable.';
      setShowSystemCameraFallback(true);
      setTrainingError(
        `Unable to start device camera: ${message}. Try browser mode over HTTPS. System Camera Feed fallback is available.`,
      );
      stopCameraStream();
      return false;
    } finally {
      setIsCameraStarting(false);
    }
  }, [trainingCameraSource]);

  const captureFrameDataUrl = () => {
    const video = videoRef.current;
    if (!video || video.videoWidth <= 0 || video.videoHeight <= 0) {
      return '';
    }

    const maxWidth = 640;
    const scale = Math.min(1, maxWidth / video.videoWidth);
    const outputWidth = Math.max(1, Math.round(video.videoWidth * scale));
    const outputHeight = Math.max(1, Math.round(video.videoHeight * scale));

    const canvas = document.createElement('canvas');
    canvas.width = outputWidth;
    canvas.height = outputHeight;
    const context = canvas.getContext('2d');
    if (!context) {
      return '';
    }
    context.drawImage(video, 0, 0, outputWidth, outputHeight);
    return canvas.toDataURL('image/jpeg', 0.86);
  };

  const applyGuidedProgress = useCallback((status: FaceTrainingStatus, startedCount: number) => {
    const acceptedThisSession = Math.max(0, status.count - startedCount);
    const boundedAccepted = Math.min(GUIDED_CAPTURE_TARGET, acceptedThisSession);
    const { counts, currentIndex } = distributeGuidedPoseCounts(boundedAccepted);
    setCapturedSamples(boundedAccepted);
    setGuidedPoseCounts(counts);
    setGuidedStepIndex(currentIndex);
  }, []);

  const runTrainingAttempt = useCallback(async () => {
    const result = await trainFaceModel();
    if (!result.ok) {
      throw new Error(result.message || 'Face model training failed.');
    }
  }, []);

  const runMandatoryAutoTraining = useCallback(async () => {
    if (autoTrainStarted || isTraining) {
      return;
    }

    setAutoTrainStarted(true);
    setRequiresManualTrainRetry(false);
    setTrainingComplete(false);
    setIsTraining(true);
    setTrainingError('');

    try {
      try {
        setTrainingMessage('Target reached. Training model...');
        await runTrainingAttempt();
        setTrainingComplete(true);
        setTrainingMessage('Face model training completed. Authorized profile is ready.');
      } catch (firstError) {
        const firstMessage = firstError instanceof Error ? firstError.message : 'Face model training failed.';
        setTrainingMessage(`Training failed (${firstMessage}). Retrying once...`);
        await runTrainingAttempt();
        setTrainingComplete(true);
        setTrainingMessage('Face model training completed after one retry.');
      }

      if (newUserName.trim()) {
        try {
          const refreshed = await fetchFaceTrainingStatus(newUserName.trim());
          setTrainingStatus(refreshed);
        } catch {
          // Keep current status when refresh fails.
        }
      }
    } catch (secondError) {
      const message = secondError instanceof Error ? secondError.message : 'Face model training failed.';
      setTrainingError(`${message} Click Retry Train to try again.`);
      setTrainingMessage('Auto-training failed after one retry. Manual retry is required.');
      setRequiresManualTrainRetry(true);
      setTrainingComplete(false);
    } finally {
      setIsTraining(false);
    }
  }, [autoTrainStarted, isTraining, newUserName, runTrainingAttempt]);

  const captureFromActiveSource = useCallback(async () => {
    const cleanName = newUserName.trim();
    if (!cleanName || !isGuidedCaptureActive) {
      return;
    }
    if (captureLoopBusyRef.current || isTraining) {
      return;
    }
    if (trainingCameraSource === 'device' && !isCameraLive) {
      return;
    }

    captureLoopBusyRef.current = true;
    setIsCapturingSample(true);
    setTrainingError('');
    setTrainingComplete(false);

    try {
      let status: FaceTrainingStatus;
      if (trainingCameraSource === 'system') {
        status = await captureFaceTrainingSampleFromNode(cleanName, trainingSystemCameraNode);
      } else {
        const imageData = captureFrameDataUrl();
        if (!imageData) {
          throw new Error('camera_frame_not_ready');
        }
        status = await captureFaceTrainingSample(cleanName, imageData);
      }

      setTrainingStatus(status);
      applyGuidedProgress(status, sessionBaseSampleCount);

      const acceptedThisSession = Math.max(0, status.count - sessionBaseSampleCount);
      if (acceptedThisSession >= GUIDED_CAPTURE_TARGET) {
        setIsGuidedCaptureActive(false);
        await runMandatoryAutoTraining();
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : '';
      if (trainingCameraSource === 'device') {
        setTrainingError(`Capture rejected (${message || 'validation'}). Keep your face inside the guide and stay steady.`);
      } else {
        setTrainingError('System camera capture failed. Check selected feed availability and alignment.');
      }
    } finally {
      setIsCapturingSample(false);
      captureLoopBusyRef.current = false;
    }
  }, [
    newUserName,
    isGuidedCaptureActive,
    isTraining,
    trainingCameraSource,
    isCameraLive,
    trainingSystemCameraNode,
    applyGuidedProgress,
    sessionBaseSampleCount,
    runMandatoryAutoTraining,
  ]);

  useEffect(() => {
    if (trainingCameraSource !== 'system') {
      return undefined;
    }
    const timer = window.setInterval(() => {
      setSystemPreviewTick(Date.now());
    }, 1000);
    return () => {
      window.clearInterval(timer);
    };
  }, [trainingCameraSource]);

  useEffect(() => {
    if (!isGuidedCaptureActive) {
      return undefined;
    }
    const timer = window.setInterval(() => {
      void captureFromActiveSource();
    }, GUIDED_CAPTURE_INTERVAL_MS);
    return () => {
      window.clearInterval(timer);
    };
  }, [isGuidedCaptureActive, captureFromActiveSource]);

  useEffect(() => {
    if (trainingCameraSource !== 'device') {
      stopCameraStream();
    }
  }, [trainingCameraSource]);

  const loadSettings = useCallback(async () => {
    const [liveResult, remoteStatusResult, linksResult, backupResult, retentionResult, nodesResult] = await Promise.allSettled([
      fetchSettingsLive(),
      fetchMobileRemoteStatus(),
      fetchRemoteAccessLinks(),
      fetchBackupStatus(),
      fetchRetentionStatus(),
      fetchLiveNodes(),
    ]);

    if (liveResult.status === 'fulfilled') {
      setAuthorizedProfiles(liveResult.value.authorizedProfiles);
      setRuntimeSettings(liveResult.value.runtimeSettings);
      setGuestModeStatus({
        ok: true,
        active: liveResult.value.guestMode,
        untilTs: liveResult.value.guestModeUntilTs,
        remainingSeconds: liveResult.value.guestModeRemainingSeconds,
      });
      syncRuntimeDrafts(liveResult.value.runtimeSettings);
      setProfilesError('');
    } else {
      setProfilesError('Unable to load authorized profiles right now.');
    }
    setProfilesLoading(false);

    if (remoteStatusResult.status === 'fulfilled') {
      setMobileRemoteStatus(remoteStatusResult.value);
    }
    if (linksResult.status === 'fulfilled') {
      setRemoteLinks(linksResult.value);
    }
    if (backupResult.status === 'fulfilled') {
      setBackupStatus(backupResult.value);
    }
    if (retentionResult.status === 'fulfilled') {
      setRetentionStatus(retentionResult.value);
    }
    if (nodesResult.status === 'fulfilled') {
      setSensorStatuses(nodesResult.value.sensorStatuses);
      setServiceStatuses(nodesResult.value.serviceStatuses);
      setCameraFeeds(nodesResult.value.cameraFeeds);
      setDetectionPipelines(nodesResult.value.detectionPipelines);
      setSystemHealth(nodesResult.value.systemHealth);
      setLiveNodesError('');
    } else {
      setLiveNodesError('Backend component status is unavailable right now.');
    }
  }, [syncRuntimeDrafts]);

  useEffect(() => {
    if (showAddUserModal) {
      return undefined;
    }

    setProfilesLoading(true);
    void loadSettings();

    const timer = window.setInterval(() => {
      void loadSettings();
    }, 15000);

    return () => {
      window.clearInterval(timer);
    };
  }, [showAddUserModal, loadSettings]);

  useEffect(() => {
    if (!guestModeStatus?.active) {
      return undefined;
    }
    const timer = window.setInterval(() => {
      setGuestModeTick(Date.now());
    }, 30000);
    return () => {
      window.clearInterval(timer);
    };
  }, [guestModeStatus?.active]);

  useEffect(() => {
    return () => {
      const stream = cameraStreamRef.current;
      if (stream) {
        stream.getTracks().forEach((track) => track.stop());
        cameraStreamRef.current = null;
      }
    };
  }, []);

  const runtimeEditableSettings = useMemo(
    () => runtimeSettings.filter((setting) => setting.editable !== false),
    [runtimeSettings],
  );

  const runtimeNonSecretSettings = useMemo(
    () => runtimeEditableSettings.filter((setting) => !setting.secret),
    [runtimeEditableSettings],
  );

  const primaryRuntimeKeys = useMemo(() => new Set(RUNTIME_CONTROL_ORDER), []);

  const runtimeMainSettings = useMemo(
    () =>
      runtimeNonSecretSettings
        .filter((setting) => primaryRuntimeKeys.has(setting.key))
        .sort((left, right) => RUNTIME_CONTROL_ORDER.indexOf(left.key) - RUNTIME_CONTROL_ORDER.indexOf(right.key)),
    [runtimeNonSecretSettings, primaryRuntimeKeys],
  );

  const runtimeControlGroups = useMemo(
    () =>
      RUNTIME_CONTROL_GROUPS.map((group) => ({
        group,
        settings: runtimeMainSettings.filter((setting) => RUNTIME_CONTROL_META[setting.key]?.group === group),
      })).filter((group) => group.settings.length > 0),
    [runtimeMainSettings],
  );

  const runtimeSettingByKey = useMemo(() => {
    const index = new Map<string, RuntimeSetting>();
    for (const setting of runtimeSettings) {
      index.set(setting.key, setting);
    }
    return index;
  }, [runtimeSettings]);

  const handleSelectSettingsStep = (step: SettingsStep) => {
    setActiveSettingsStep(step);
    setActiveSettingsSection(DEFAULT_SECTION_BY_STEP[step]);
  };

  const handleSelectSettingsSection = (step: SettingsStep, section: SettingsSection) => {
    setActiveSettingsStep(step);
    setActiveSettingsSection(section);
  };

  useEffect(() => {
    const setting = runtimeSettingByKey.get('LAN_BASE_URL');
    if (!setting || setting.editable === false) {
      return;
    }
    const draft = (runtimeDrafts.LAN_BASE_URL ?? '').trim();
    if (draft) {
      return;
    }
    const fallback = (remoteLinks?.lanUrl || window.location.origin || '').trim();
    if (!fallback) {
      return;
    }
    setRuntimeDrafts((previous) => ({
      ...previous,
      LAN_BASE_URL: fallback,
    }));
  }, [runtimeSettingByKey, runtimeDrafts.LAN_BASE_URL, remoteLinks?.lanUrl]);

  const resetAddUserModal = () => {
    stopCameraStream();
    setShowAddUserModal(false);
    setNewUserName('');
    setNewUserRole('Family Member');
    setTrainingStatus(null);
    setTrainingComplete(false);
    setTrainingMessage('');
    setTrainingError('');
    setTrainingCameraSource('device');
    setShowSystemCameraFallback(false);
    setTrainingSystemCameraNode('cam_indoor');
    setSystemPreviewTick(Date.now());
    setCapturedSamples(0);
    setSessionBaseSampleCount(0);
    setGuidedPoseCounts(emptyGuidedPoseCounts());
    setGuidedStepIndex(0);
    setIsGuidedCaptureActive(false);
    setIsCameraStarting(false);
    setIsCameraLive(false);
    setIsCapturingSample(false);
    setAutoTrainStarted(false);
    setRequiresManualTrainRetry(false);
    setIsTraining(false);
    setIsSavingUser(false);
  };

  const handleRefreshTrainingStatus = async () => {
    const cleanName = newUserName.trim();
    if (!cleanName) {
      return;
    }
    setTrainingError('');
    try {
      const status = await fetchFaceTrainingStatus(cleanName);
      setTrainingStatus(status);
      if (isGuidedCaptureActive) {
        applyGuidedProgress(status, sessionBaseSampleCount);
      }
    } catch {
      setTrainingError('Unable to refresh training status.');
    }
  };

  const handleStartGuidedCapture = async () => {
    const cleanName = newUserName.trim();
    if (!cleanName) {
      setTrainingError('Enter the user name before starting guided capture.');
      return;
    }

    setTrainingError('');
    setTrainingMessage('');
    setTrainingComplete(false);
    setRequiresManualTrainRetry(false);
    setAutoTrainStarted(false);

    let status: FaceTrainingStatus;
    try {
      status = await fetchFaceTrainingStatus(cleanName);
      setTrainingStatus(status);
    } catch {
      setTrainingError('Unable to start guided capture because status refresh failed.');
      return;
    }

    if (trainingCameraSource === 'device') {
      const cameraReady = await startCameraStream();
      if (!cameraReady) {
        return;
      }
    }

    setSessionBaseSampleCount(status.count);
    setCapturedSamples(0);
    setGuidedPoseCounts(emptyGuidedPoseCounts());
    setGuidedStepIndex(0);
    setIsGuidedCaptureActive(true);
    setTrainingMessage('Guided auto-capture started. Follow each on-screen instruction.');
  };

  const handleManualRetryTraining = async () => {
    if (isTraining) {
      return;
    }

    setIsTraining(true);
    setTrainingError('');
    setTrainingMessage('Retrying training...');
    try {
      await runTrainingAttempt();
      setTrainingComplete(true);
      setRequiresManualTrainRetry(false);
      setTrainingMessage('Face model training completed successfully.');
      await handleRefreshTrainingStatus();
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Face model training failed.';
      setTrainingError(`${message} Click Retry Train to try again.`);
      setTrainingComplete(false);
    } finally {
      setIsTraining(false);
    }
  };

  const handleAddUser = async () => {
    const cleanName = newUserName.trim();
    if (!cleanName || !trainingStatus?.ready || !trainingComplete) {
      return;
    }
    setIsSavingUser(true);
    setTrainingError('');
    try {
      await createFaceProfile(cleanName, newUserRole);
      await loadSettings();
      resetAddUserModal();
    } catch {
      setTrainingError('Unable to save the authorized profile.');
      setIsSavingUser(false);
    }
  };

  const resolveProfileDbId = (profile: AuthorizedProfile): number => {
    const fromDb = Number(profile.dbId || 0);
    if (Number.isFinite(fromDb) && fromDb > 0) {
      return fromDb;
    }
    const fromId = Number.parseInt(profile.id.replace('auth-', ''), 10);
    return Number.isFinite(fromId) ? fromId : 0;
  };

  const openEditProfileModal = (profile: AuthorizedProfile) => {
    setEditProfileTarget(profile);
    setEditProfileName(profile.label || '');
    setEditProfileRole(profile.role || 'Authorized');
    setProfilesMessage('');
    setProfilesError('');
    setShowEditProfileModal(true);
  };

  const resetEditProfileModal = () => {
    setShowEditProfileModal(false);
    setEditProfileTarget(null);
    setEditProfileName('');
    setEditProfileRole('');
    setEditingFaceId(null);
  };

  const handleSaveProfileEdit = async () => {
    if (!editProfileTarget) {
      return;
    }

    const dbId = resolveProfileDbId(editProfileTarget);
    if (!Number.isFinite(dbId) || dbId <= 0) {
      setProfilesError('Invalid profile identifier.');
      return;
    }

    const name = editProfileName.trim();
    const role = editProfileRole.trim();
    if (!name) {
      setProfilesError('Profile name is required.');
      return;
    }

    setEditingFaceId(dbId);
    setProfilesError('');
    try {
      await updateFaceProfile(dbId, {
        name,
        note: role,
      });
      await loadSettings();
      setProfilesMessage('Authorized profile updated.');
      window.setTimeout(() => setProfilesMessage(''), 3000);
      resetEditProfileModal();
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to update authorized profile.';
      setProfilesError(message);
    } finally {
      setEditingFaceId(null);
    }
  };

  const handleRemoveProfile = async (profile: AuthorizedProfile) => {
    const dbId = resolveProfileDbId(profile);
    if (!Number.isFinite(dbId) || dbId <= 0) {
      setProfilesError('Invalid profile identifier.');
      return;
    }
    const confirmed = window.confirm(`Remove profile "${profile.label}"? This cannot be undone.`);
    if (!confirmed) {
      return;
    }
    setDeletingFaceId(dbId);
    setProfilesError('');
    setProfilesMessage('');
    try {
      await deleteFaceProfile(dbId);
      setAuthorizedProfiles((previous) => previous.filter((item) => resolveProfileDbId(item) !== dbId));
      setProfilesMessage('Authorized profile removed.');
      window.setTimeout(() => setProfilesMessage(''), 3000);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to remove authorized profile.';
      setProfilesError(message);
    } finally {
      setDeletingFaceId(null);
    }
  };

  const isRuntimeBoolOn = (setting: RuntimeSetting): boolean => {
    const fallback = String(setting.value || '').trim().toLowerCase();
    const source = String(runtimeDrafts[setting.key] ?? fallback).trim().toLowerCase();
    return source === 'true' || source === '1' || source === 'yes' || source === 'on' || source === 'enabled';
  };

  const handleStartGuestMode = async () => {
    if (guestModeBusy) {
      return;
    }
    const durationHours = Math.max(1, Math.min(24, Math.round(toRuntimeNumber(guestModeDraftHours))));
    setGuestModeBusy(true);
    setGuestModeMessage('');
    try {
      const status = await updateGuestMode(durationHours);
      setGuestModeStatus(status);
      setGuestModeTick(Date.now());
      setGuestModeMessage(`Guest Mode is active for ${durationHours} hour${durationHours === 1 ? '' : 's'}.`);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to start Guest Mode.';
      setGuestModeMessage(message);
    } finally {
      setGuestModeBusy(false);
    }
  };

  const handleEndGuestMode = async () => {
    if (guestModeBusy) {
      return;
    }
    setGuestModeBusy(true);
    setGuestModeMessage('');
    try {
      const status = await updateGuestMode(0);
      setGuestModeStatus(status);
      setGuestModeTick(Date.now());
      setGuestModeMessage('Guest Mode ended. Unknown visitors will be treated normally again.');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to end Guest Mode.';
      setGuestModeMessage(message);
    } finally {
      setGuestModeBusy(false);
    }
  };

  const handleRuntimeDraftChange = (key: string, value: string) => {
    setRuntimeDrafts((previous) => ({
      ...previous,
      [key]: value,
    }));
  };

  const handleRuntimeSecretReplaceToggle = (key: string, enabled: boolean) => {
    setRuntimeSecretReplaceMode((previous) => ({
      ...previous,
      [key]: enabled,
    }));
    if (!enabled) {
      setRuntimeDrafts((previous) => ({
        ...previous,
        [key]: '',
      }));
      setRuntimeSaveMessages((previous) => ({
        ...previous,
        [key]: '',
      }));
    }
  };

  const handleSaveRuntimeSetting = async (setting: RuntimeSetting) => {
    if (setting.editable === false || runtimeSavingKey) {
      return;
    }

    const key = setting.key;
    const rawDraftValue = runtimeDrafts[key] ?? (setting.secret ? '' : setting.value);
    const presetOptions = RUNTIME_CONTROL_META[key]?.presets;
    const draftValue = presetOptions && setting.inputType === 'number'
      ? presetOptions[nearestPresetIndex(presetOptions, rawDraftValue)].value
      : rawDraftValue;
    const normalizedValue = setting.inputType === 'switch'
      ? (draftValue.trim().toLowerCase() === 'true' ? 'true' : 'false')
      : draftValue.trim();

    if (setting.secret && !runtimeSecretReplaceMode[key]) {
      handleRuntimeSecretReplaceToggle(key, true);
      return;
    }

    if (setting.secret && !normalizedValue) {
      setRuntimeSaveMessages((previous) => ({
        ...previous,
        [key]: 'Enter a value before saving replacement.',
      }));
      return;
    }

    setRuntimeSavingKey(key);
    setRuntimeSaveMessages((previous) => ({
      ...previous,
      [key]: '',
    }));
    try {
      const result = await updateRuntimeSetting(key, normalizedValue);
      setRuntimeSettings((previous) =>
        previous.map((item) => {
          if (item.key !== key) {
            return item;
          }
          return {
            ...item,
            value: result.secret ? '' : result.value,
            configured: result.secret ? result.configured : item.configured,
          };
        }),
      );
      setRuntimeDrafts((previous) => ({
        ...previous,
        [key]: result.secret ? '' : result.value,
      }));
      if (result.secret) {
        handleRuntimeSecretReplaceToggle(key, false);
      }
      if (result.key === 'LAN_BASE_URL' || result.key === 'TAILSCALE_BASE_URL') {
        const linksResult = await fetchRemoteAccessLinks();
        setRemoteLinks(linksResult);
      }
      setRuntimeSaveMessages((previous) => ({
        ...previous,
        [key]: setting.secret
          ? (result.configured ? 'Secret updated.' : 'Secret cleared.')
          : 'Saved.',
      }));
      window.setTimeout(() => {
        setRuntimeSaveMessages((previous) => ({
          ...previous,
          [key]: '',
        }));
      }, 3000);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to save setting.';
      setRuntimeSaveMessages((previous) => ({
        ...previous,
        [key]: message,
      }));
    } finally {
      setRuntimeSavingKey(null);
    }
  };

  const mobileRemoteRoute = mobileRemoteStatus?.route || '/dashboard/remote/mobile';
  const mobileRemoteUrl = remoteLinks?.preferredUrl ||
    (typeof window !== 'undefined' ? `${window.location.origin}${mobileRemoteRoute}` : mobileRemoteRoute);
  const guidedStep = GUIDED_POSE_PLAN[Math.min(guidedStepIndex, GUIDED_POSE_PLAN.length - 1)];
  const guidedProgressPercent = Math.max(
    0,
    Math.min(100, Math.round((capturedSamples / GUIDED_CAPTURE_TARGET) * 100)),
  );
  const onlineSensorCount = sensorStatuses.filter((sensor) => sensor.status === 'online').length;
  const warningSensorCount = sensorStatuses.filter((sensor) => sensor.status === 'warning').length;
  const offlineSensorCount = sensorStatuses.filter((sensor) => sensor.status === 'offline').length;
  const onlineServiceCount = serviceStatuses.filter((service) => service.status === 'online').length;
  const onlineCameraCount = cameraFeeds.filter((cameraFeed) => cameraFeed.status === 'online').length;
  const latestBackupLabel = backupStatus?.latest?.name || 'No backup yet';
  const guestModePresetIndex = nearestPresetIndex(GUEST_MODE_PRESETS, guestModeDraftHours);
  const selectedGuestModePreset = GUEST_MODE_PRESETS[guestModePresetIndex];
  const guestModeRemaining = guestModeRemainingSeconds(guestModeStatus, guestModeTick);
  const guestModeActive = Boolean(guestModeStatus?.active && guestModeRemaining > 0);
  const guestModeUntilLabel = formatGuestModeUntil(guestModeStatus?.untilTs || '');

  const handleChangePassword = async () => {
    if (!currentPassword || !newPassword) {
      setAccountSecurityError('Enter your current password and a new password.');
      setAccountSecurityMessage('');
      return;
    }
    if (newPassword.length < 8) {
      setAccountSecurityError('New password must be at least 8 characters.');
      setAccountSecurityMessage('');
      return;
    }
    setAccountSecurityBusy(true);
    setAccountSecurityError('');
    setAccountSecurityMessage('');
    try {
      const result = await changePassword(currentPassword, newPassword);
      setAccountSecurityMessage(result.message || 'Password updated.');
      setCurrentPassword('');
      setNewPassword('');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to update password.';
      setAccountSecurityError(message);
    } finally {
      setAccountSecurityBusy(false);
    }
  };

  const handleGenerateRecoveryCode = async () => {
    setAccountSecurityBusy(true);
    setAccountSecurityError('');
    setAccountSecurityMessage('');
    try {
      const result = await regenerateRecoveryCode();
      setRecoveryCode(result.recoveryCode);
      setAccountSecurityMessage(result.message || 'Recovery code generated. Save it now.');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to generate recovery code.';
      setAccountSecurityError(message);
    } finally {
      setAccountSecurityBusy(false);
    }
  };

  const handleCreateBackup = async () => {
    setBackupBusy(true);
    setBackupMessage('');
    try {
      const created = await createBackup();
      setBackupMessage(`Backup created: ${created.name}`);
      const latestStatus = await fetchBackupStatus();
      setBackupStatus(latestStatus);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to create backup.';
      setBackupMessage(message);
    } finally {
      setBackupBusy(false);
    }
  };

  const editProfileModal = (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg max-w-md w-full">
        <div className="border-b border-gray-200 px-5 py-4 flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Edit Authorized Profile</h3>
            <p className="text-sm text-gray-600 mt-1">Update the profile label and role metadata.</p>
          </div>
          <button
            onClick={resetEditProfileModal}
            className="p-1 hover:bg-gray-100 rounded transition-colors"
            aria-label="Close edit profile dialog"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="px-5 py-4 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Name</label>
            <input
              type="text"
              value={editProfileName}
              onChange={(event) => setEditProfileName(event.target.value)}
              placeholder="Resident name"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Role</label>
            <input
              type="text"
              value={editProfileRole}
              onChange={(event) => setEditProfileRole(event.target.value)}
              placeholder="Owner, Family, Guest"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900"
            />
          </div>
        </div>

        <div className="border-t border-gray-200 px-5 py-4 flex items-center justify-end gap-2">
          <button
            onClick={resetEditProfileModal}
            disabled={Boolean(editingFaceId)}
            className="px-3 py-2 text-sm bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-60"
          >
            Cancel
          </button>
          <button
            onClick={() => {
              void handleSaveProfileEdit();
            }}
            disabled={Boolean(editingFaceId)}
            className="px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-60"
          >
            {editingFaceId ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  );

  const addUserModal = (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Add New Authorized User</h3>
            <p className="text-sm text-gray-600 mt-1">Guided auto-capture with mandatory retraining.</p>
          </div>
          <button
            onClick={resetAddUserModal}
            className="p-1 hover:bg-gray-100 rounded transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-6">
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center text-sm font-semibold">
                1
              </div>
              <h4 className="font-semibold text-gray-900">User Information</h4>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Full Name <span className="text-red-600">*</span>
              </label>
              <input
                type="text"
                value={newUserName}
                onChange={(event) => setNewUserName(event.target.value)}
                placeholder="Enter full name"
                className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Relationship/Role</label>
              <select
                value={newUserRole}
                onChange={(event) => setNewUserRole(event.target.value)}
                className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option>Family Member</option>
                <option>Friend</option>
                <option>Service Provider</option>
                <option>Caretaker</option>
                <option>Guest</option>
                <option>Other</option>
              </select>
            </div>
          </div>

          <div className="space-y-4 pt-4 border-t border-gray-200">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center text-sm font-semibold">
                2
              </div>
              <h4 className="font-semibold text-gray-900">Face Training</h4>
            </div>

            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <h5 className="font-medium text-blue-900 mb-2">Training Guidelines</h5>
              <ul className="text-sm text-blue-800 space-y-1">
                <li>Auto-capture target: 40 accepted samples in guided poses.</li>
                <li>Follow prompts exactly: Center, Left, Right, Up, Down.</li>
                <li>Keep your full face inside the on-screen template.</li>
                <li>Training starts automatically after target is reached.</li>
              </ul>
            </div>

            <div className="inline-flex rounded-lg border border-gray-200 bg-gray-50 p-1">
              <button
                onClick={() => {
                  setTrainingCameraSource('device');
                  setTrainingError('');
                  setTrainingMessage('');
                }}
                className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
                  trainingCameraSource === 'device'
                    ? 'bg-white text-blue-700 border border-blue-200'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                Device Camera
              </button>
              {showSystemCameraFallback && (
                <button
                  onClick={() => {
                    setTrainingCameraSource('system');
                    setTrainingError('');
                    setTrainingMessage('Using System Camera Feed fallback mode.');
                  }}
                  className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
                    trainingCameraSource === 'system'
                      ? 'bg-white text-blue-700 border border-blue-200'
                      : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  System Camera Feed
                </button>
              )}
            </div>
            <div className="border-2 border-dashed border-gray-300 rounded-lg p-4">
              {trainingCameraSource === 'system' && showSystemCameraFallback ? (
                <div className="mb-3 flex items-center justify-center gap-2">
                  <label className="text-xs text-gray-700">Feed</label>
                  <select
                    value={trainingSystemCameraNode}
                    onChange={(event) => {
                      setTrainingSystemCameraNode(event.target.value as 'cam_indoor' | 'cam_door');
                      setSystemPreviewTick(Date.now());
                    }}
                    className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="cam_indoor">cam_indoor</option>
                    <option value="cam_door">cam_door</option>
                  </select>
                </div>
              ) : null}

              <div className="relative aspect-video bg-gray-900 rounded-lg overflow-hidden mb-3 flex items-center justify-center">
                {trainingCameraSource === 'device' ? (
                  <>
                    <video
                      ref={videoRef}
                      className={`w-full h-full object-cover ${isCameraLive ? '' : 'hidden'}`}
                      muted
                      playsInline
                    />
                    {!isCameraLive && (
                      <div className="text-center text-gray-300 px-4">
                        <Camera className="w-10 h-10 mx-auto mb-2 text-gray-500" />
                        <p className="text-sm">Start camera to begin guided capture.</p>
                      </div>
                    )}
                  </>
                ) : (
                  <img
                    src={`/camera/frame/${trainingSystemCameraNode}?sample_tick=${systemPreviewTick}`}
                    alt={`${trainingSystemCameraNode} training preview`}
                    className="w-full h-full object-cover"
                    onError={() => {
                      setTrainingError('Selected system camera feed is unavailable.');
                    }}
                  />
                )}

                <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
                  <svg className="w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
                    <ellipse cx="50" cy="50" rx="24" ry="33" fill="none" stroke="rgba(56, 189, 248, 0.95)" strokeWidth="1.4" strokeDasharray="4 2" />
                  </svg>
                </div>
                <p className="pointer-events-none absolute top-3 left-1/2 -translate-x-1/2 rounded-full bg-black/55 px-3 py-1 text-[11px] text-white">
                  Keep your face inside the guide shape
                </p>
              </div>

              <div className="flex flex-wrap gap-3 justify-center">
                <button
                  onClick={() => void startCameraStream()}
                  disabled={trainingCameraSource !== 'device' || isCameraStarting || isCameraLive}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed"
                >
                  {isCameraStarting ? 'Starting Camera...' : isCameraLive ? 'Camera Ready' : 'Start Camera'}
                </button>
                <button
                  onClick={stopCameraStream}
                  disabled={trainingCameraSource !== 'device' || !isCameraLive || isCameraStarting || isCapturingSample}
                  className="px-4 py-2 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors disabled:text-gray-400"
                >
                  Stop Camera
                </button>
                {trainingCameraSource === 'system' && (
                  <button
                    onClick={() => {
                      setSystemPreviewTick(Date.now());
                      setTrainingError('');
                    }}
                    className="px-4 py-2 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
                  >
                    Refresh Preview
                  </button>
                )}
              </div>
              <p className="text-xs text-gray-600 text-center mt-3">
                {trainingCameraSource === 'system'
                  ? 'Fallback mode: using backend camera feed when device camera is unavailable.'
                  : 'Device camera is the default for guided auto-capture.'}
              </p>
            </div>

            <div className="rounded-lg border border-gray-200 p-4 space-y-3">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-medium text-gray-900">Guided progress</p>
                <p className="text-sm text-gray-600">{capturedSamples}/{GUIDED_CAPTURE_TARGET}</p>
              </div>
              <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-600 transition-all duration-300"
                  style={{ width: `${guidedProgressPercent}%` }}
                />
              </div>
              <p className="text-sm text-blue-800 bg-blue-50 border border-blue-200 rounded-lg px-3 py-2">
                {isGuidedCaptureActive
                  ? `Current instruction: ${guidedStep.instruction}`
                  : 'Current instruction: Start guided capture to begin automated sampling.'}
              </p>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-2 text-xs">
                {GUIDED_POSE_PLAN.map((step) => (
                  <div key={step.id} className="rounded-md border border-gray-200 px-2 py-2 bg-gray-50">
                    <p className="font-medium text-gray-800">{step.label}</p>
                    <p className="text-gray-600">{guidedPoseCounts[step.id]}/{step.quota}</p>
                  </div>
                ))}
              </div>
            </div>

            {trainingStatus && (
              <div className="rounded-lg border border-gray-200 p-4 text-sm">
                <p className="font-medium text-gray-900">
                  {trainingStatus.count} sample{trainingStatus.count > 1 ? 's' : ''} accepted
                </p>
                <p className="text-gray-600 mt-1">
                  Minimum required: {trainingStatus.minRequired}. Target: {trainingStatus.target}.
                </p>
              </div>
            )}

            <div className="flex flex-wrap gap-3">
              <button
                onClick={() => void handleStartGuidedCapture()}
                disabled={isGuidedCaptureActive || isTraining || isCapturingSample || !newUserName.trim()}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed"
              >
                {isGuidedCaptureActive ? 'Guided Capture Active' : 'Start Guided Auto-Capture'}
              </button>
              <button
                onClick={() => {
                  setIsGuidedCaptureActive(false);
                  setTrainingMessage('Guided capture paused.');
                }}
                disabled={!isGuidedCaptureActive || isTraining}
                className="px-4 py-2 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors disabled:text-gray-400"
              >
                Stop Guided Capture
              </button>
              <button
                onClick={() => void handleRefreshTrainingStatus()}
                disabled={!newUserName.trim()}
                className="px-4 py-2 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors disabled:text-gray-400"
              >
                Refresh Status
              </button>
              {requiresManualTrainRetry && (
                <button
                  onClick={() => void handleManualRetryTraining()}
                  disabled={isTraining}
                  className="px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed"
                >
                  {isTraining ? 'Retrying...' : 'Retry Train'}
                </button>
              )}
            </div>

            {capturedSamples > 0 && (
              <p className="text-sm text-gray-600">
                Captures this session: {capturedSamples}
              </p>
            )}

            {trainingMessage && (
              <div className="rounded-lg bg-green-50 border border-green-200 px-4 py-3 text-sm text-green-800">
                {trainingMessage}
              </div>
            )}
            {trainingError && (
              <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
                {trainingError}
              </div>
            )}
          </div>

          <div className="space-y-4 pt-4 border-t border-gray-200">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center text-sm font-semibold">
                3
              </div>
              <h4 className="font-semibold text-gray-900">Access Permissions</h4>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div>
                  <p className="font-medium text-gray-900">Alert on Entry</p>
                  <p className="text-sm text-gray-600">Receive notifications when detected</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input type="checkbox" className="sr-only peer" defaultChecked />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-100 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600" />
                </label>
              </div>
              <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div>
                  <p className="font-medium text-gray-900">Log Entry Events</p>
                  <p className="text-sm text-gray-600">Record in event history</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input type="checkbox" className="sr-only peer" defaultChecked />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-100 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600" />
                </label>
              </div>
            </div>
          </div>
        </div>

        <div className="sticky bottom-0 bg-gray-50 border-t border-gray-200 px-6 py-4 flex justify-end gap-3">
          <button
            onClick={resetAddUserModal}
            className="px-6 py-2 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={() => void handleAddUser()}
            disabled={!newUserName.trim() || !trainingStatus?.ready || !trainingComplete || isSavingUser}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed"
          >
            {isSavingUser ? 'Saving...' : 'Add User'}
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="p-3 sm:p-4 md:p-8 space-y-6 md:space-y-8 overflow-x-hidden">
      <div>
        <h2 className="text-xl md:text-2xl font-semibold text-gray-900">Settings</h2>
        <p className="text-sm md:text-base text-gray-600 mt-1">
          Configuration for alerts, fusion behavior, authorized faces, and local system services.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[260px_minmax(0,1fr)] gap-4 md:gap-6">
        <aside className="lg:sticky lg:top-4 lg:self-start rounded-lg border border-gray-200 bg-white p-3">
          <p className="px-2 pb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Sections</p>
          <nav className="space-y-1" aria-label="Settings section navigation">
            {SETTINGS_NAV.map((group) => {
              const isGroupActive = activeSettingsStep === group.id;
              const Icon = group.icon;
              return (
                <div key={group.id} className="space-y-1">
                  <button
                    onClick={() => handleSelectSettingsStep(group.id)}
                    className={`w-full flex items-center gap-2 rounded-md px-2.5 py-2 text-sm transition-colors ${
                      isGroupActive
                        ? 'bg-blue-50 text-blue-800 border border-blue-200'
                        : 'text-gray-700 hover:bg-gray-50 border border-transparent'
                    }`}
                  >
                    <Icon className="w-4 h-4 shrink-0" />
                    <span className="font-medium">{group.label}</span>
                  </button>
                  {isGroupActive && (
                    <div className="ml-6 space-y-1 border-l border-gray-200 pl-2">
                      {group.sections.map((section) => {
                        const isSectionActive = activeSettingsSection === section.id;
                        return (
                          <button
                            key={section.id}
                            onClick={() => handleSelectSettingsSection(group.id, section.id)}
                            className={`w-full text-left rounded-md px-2 py-1.5 text-xs transition-colors ${
                              isSectionActive
                                ? 'bg-blue-50 text-blue-700 font-semibold'
                                : 'text-gray-600 hover:bg-gray-50'
                            }`}
                          >
                            {section.label}
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </nav>
        </aside>

        <div className="space-y-6">
        <div className={`${activeSettingsSection === 'alerts-routing' ? '' : 'hidden'} bg-white rounded-lg border border-gray-200 p-4 sm:p-6`}>
          <div className="flex items-center gap-3 mb-4 sm:mb-6">
            <div className="w-10 h-10 bg-blue-50 rounded-lg flex items-center justify-center">
              <Bell className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <h3 className="font-semibold text-gray-900">Alert Routing</h3>
              <p className="text-sm text-gray-600">Keep critical notifications immediate and persistent.</p>
            </div>
          </div>

          <div className="space-y-4">
            {[
              {
                title: 'Critical Intruder Alerts',
                desc: 'Immediate alert for INTRUDER and DOOR_FORCE escalation.',
              },
              {
                title: 'Critical Fire Alerts',
                desc: 'Immediate alert for FIRE fusion output.',
              },
            ].map((item) => (
              <div
                key={item.title}
                className="flex items-start sm:items-center justify-between gap-3 py-3 border-b border-gray-200 last:border-b-0"
              >
                <div className="min-w-0">
                  <p className="font-medium text-gray-900">{item.title}</p>
                  <p className="text-sm text-gray-600 break-words">{item.desc}</p>
                </div>
                <span className="shrink-0 rounded-full border border-green-200 bg-green-50 px-3 py-1 text-xs font-medium text-green-700">
                  Always on
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className={`${activeSettingsSection === 'runtime-access' ? '' : 'hidden'} bg-white rounded-lg border border-gray-200 p-4 sm:p-6`}>
          <div className="flex items-center gap-3 mb-4 sm:mb-6">
            <div className="w-10 h-10 bg-blue-50 rounded-lg flex items-center justify-center">
              <Wifi className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <h3 className="font-semibold text-gray-900">Backend Access</h3>
              <p className="text-sm text-gray-600">Configure local and remote backend URLs used by mobile clients.</p>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {(() => {
              const lanSetting = runtimeSettingByKey.get('LAN_BASE_URL');
              const tailscaleSetting = runtimeSettingByKey.get('TAILSCALE_BASE_URL');
              const indoorCameraSetting = runtimeSettingByKey.get('CAMERA_INDOOR_STREAM_URL');
              const doorCameraSetting = runtimeSettingByKey.get('CAMERA_DOOR_STREAM_URL');
              const lanDraft = runtimeDrafts.LAN_BASE_URL ?? '';
              const tailscaleDraft = runtimeDrafts.TAILSCALE_BASE_URL ?? '';
              const indoorCameraDraft = runtimeDrafts.CAMERA_INDOOR_STREAM_URL ?? '';
              const doorCameraDraft = runtimeDrafts.CAMERA_DOOR_STREAM_URL ?? '';
              const lanSaving = runtimeSavingKey === 'LAN_BASE_URL';
              const tailscaleSaving = runtimeSavingKey === 'TAILSCALE_BASE_URL';
              const indoorCameraSaving = runtimeSavingKey === 'CAMERA_INDOOR_STREAM_URL';
              const doorCameraSaving = runtimeSavingKey === 'CAMERA_DOOR_STREAM_URL';
              const lanMessage = runtimeSaveMessages.LAN_BASE_URL || '';
              const tailscaleMessage = runtimeSaveMessages.TAILSCALE_BASE_URL || '';
              const indoorCameraMessage = runtimeSaveMessages.CAMERA_INDOOR_STREAM_URL || '';
              const doorCameraMessage = runtimeSaveMessages.CAMERA_DOOR_STREAM_URL || '';
              const hasCameraRuntimeKeys = Boolean(indoorCameraSetting) && Boolean(doorCameraSetting);

              return (
                <>
                  {!hasCameraRuntimeKeys ? (
                    <div className="lg:col-span-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                      Camera stream settings are unavailable from the current backend runtime. Restart the backend to load the latest runtime keys.
                    </div>
                  ) : null}
                  <div className="rounded-lg border border-gray-200 p-4 space-y-2">
                    <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Local LAN URL</p>
                    <input
                      type="text"
                      value={lanDraft}
                      onChange={(event) => handleRuntimeDraftChange('LAN_BASE_URL', event.target.value)}
                      placeholder="http://192.168.x.x:8765"
                      disabled={lanSaving || !lanSetting || lanSetting.editable === false}
                      className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono text-gray-900"
                    />
                    <p className="text-xs text-gray-600 break-all">
                      Active: {remoteLinks?.lanUrl || 'LAN URL unavailable'}
                    </p>
                    <button
                      onClick={() => {
                        if (lanSetting) {
                          void handleSaveRuntimeSetting(lanSetting);
                        }
                      }}
                      disabled={Boolean(runtimeSavingKey) || !lanSetting || lanSetting.editable === false}
                      className="px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-60"
                    >
                      {lanSaving ? 'Saving...' : 'Save LAN URL'}
                    </button>
                    {lanMessage ? <p className="text-xs text-gray-700">{lanMessage}</p> : null}
                  </div>

                  <div className="rounded-lg border border-gray-200 p-4 space-y-2">
                    <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Tailscale URL</p>
                    <input
                      type="text"
                      value={tailscaleDraft}
                      onChange={(event) => handleRuntimeDraftChange('TAILSCALE_BASE_URL', event.target.value)}
                      placeholder="http://100.x.x.x:8765 or https://host.ts.net"
                      disabled={tailscaleSaving || !tailscaleSetting || tailscaleSetting.editable === false}
                      className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono text-gray-900"
                    />
                    <p className="text-xs text-gray-600 break-all">
                      Active: {remoteLinks?.tailscaleUrl || 'Tailscale URL not configured'}
                    </p>
                    <button
                      onClick={() => {
                        if (tailscaleSetting) {
                          void handleSaveRuntimeSetting(tailscaleSetting);
                        }
                      }}
                      disabled={Boolean(runtimeSavingKey) || !tailscaleSetting || tailscaleSetting.editable === false}
                      className="px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-60"
                    >
                      {tailscaleSaving ? 'Saving...' : 'Save Tailscale URL'}
                    </button>
                    {tailscaleMessage ? <p className="text-xs text-gray-700">{tailscaleMessage}</p> : null}
                  </div>

                  <div className="rounded-lg border border-gray-200 p-4 space-y-2">
                    <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Indoor Camera Stream</p>
                    <input
                      type="text"
                      value={indoorCameraDraft}
                      onChange={(event) => handleRuntimeDraftChange('CAMERA_INDOOR_STREAM_URL', event.target.value)}
                      placeholder="rtsp://user:pass@host:554/stream"
                      disabled={indoorCameraSaving || !indoorCameraSetting || indoorCameraSetting.editable === false}
                      className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono text-gray-900"
                    />
                    <p className="text-xs text-gray-600 break-all">
                      Active: {runtimeSettingByKey.get('CAMERA_INDOOR_STREAM_URL')?.value || 'Not configured'}
                    </p>
                    <button
                      onClick={() => {
                        if (indoorCameraSetting) {
                          void handleSaveRuntimeSetting(indoorCameraSetting);
                        }
                      }}
                      disabled={Boolean(runtimeSavingKey) || !indoorCameraSetting || indoorCameraSetting.editable === false}
                      className="px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-60"
                    >
                      {indoorCameraSaving ? 'Saving...' : 'Save Indoor Stream'}
                    </button>
                    {indoorCameraMessage ? <p className="text-xs text-gray-700">{indoorCameraMessage}</p> : null}
                  </div>

                  <div className="rounded-lg border border-gray-200 p-4 space-y-2">
                    <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Door Camera Stream</p>
                    <input
                      type="text"
                      value={doorCameraDraft}
                      onChange={(event) => handleRuntimeDraftChange('CAMERA_DOOR_STREAM_URL', event.target.value)}
                      placeholder="rtsp://user:pass@host:554/stream"
                      disabled={doorCameraSaving || !doorCameraSetting || doorCameraSetting.editable === false}
                      className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono text-gray-900"
                    />
                    <p className="text-xs text-gray-600 break-all">
                      Active: {runtimeSettingByKey.get('CAMERA_DOOR_STREAM_URL')?.value || 'Not configured'}
                    </p>
                    <button
                      onClick={() => {
                        if (doorCameraSetting) {
                          void handleSaveRuntimeSetting(doorCameraSetting);
                        }
                      }}
                      disabled={Boolean(runtimeSavingKey) || !doorCameraSetting || doorCameraSetting.editable === false}
                      className="px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-60"
                    >
                      {doorCameraSaving ? 'Saving...' : 'Save Door Stream'}
                    </button>
                    {doorCameraMessage ? <p className="text-xs text-gray-700">{doorCameraMessage}</p> : null}
                  </div>
                </>
              );
            })()}
          </div>
        </div>

        <div className={`${activeSettingsSection === 'profiles-authorized' ? '' : 'hidden'} bg-white rounded-lg border border-gray-200 p-4 sm:p-6`}>
          <div className="flex items-center gap-3 mb-4 sm:mb-6">
            <div className="w-10 h-10 bg-blue-50 rounded-lg flex items-center justify-center">
              <User className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <h3 className="font-semibold text-gray-900">Authorized Face Profiles</h3>
              <p className="text-sm text-gray-600">Profiles enrolled for AUTHORIZED detection events.</p>
            </div>
          </div>

          <div className="space-y-3">
            {profilesLoading ? (
              <div className="rounded-lg border border-gray-200 p-4 text-sm text-gray-600">
                Loading authorized profiles...
              </div>
            ) : authorizedProfiles.length > 0 ? (
              authorizedProfiles.map((profile) => (
                <div
                  key={profile.id}
                  className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-3 bg-gray-50 rounded-lg"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-10 h-10 bg-blue-600 rounded-full flex items-center justify-center text-white font-medium">
                      {profile.label.slice(0, 2).toUpperCase()}
                    </div>
                    <div className="min-w-0">
                      <p className="font-medium text-gray-900">{profile.label}</p>
                      <p className="text-xs text-gray-600 break-words">
                        {profile.role} • enrolled {profile.enrolledAt}
                        {profile.sampleCount != null ? ` • samples ${profile.sampleCount}` : ''}
                      </p>
                    </div>
                  </div>
                  <div className="self-start sm:self-auto inline-flex items-center gap-2">
                    <button
                      onClick={() => openEditProfileModal(profile)}
                      disabled={Boolean(deletingFaceId) || Boolean(editingFaceId)}
                      className="inline-flex items-center gap-1 px-3 py-1.5 text-sm text-blue-700 hover:bg-blue-50 rounded transition-colors disabled:text-gray-400"
                    >
                      <Pencil className="w-3.5 h-3.5" />
                      Edit
                    </button>
                    <button
                      onClick={() => void handleRemoveProfile(profile)}
                      disabled={deletingFaceId === resolveProfileDbId(profile) || Boolean(editingFaceId)}
                      className="px-3 py-1.5 text-sm text-red-600 hover:bg-red-50 rounded transition-colors disabled:text-gray-400"
                    >
                      {deletingFaceId === resolveProfileDbId(profile) ? 'Removing...' : 'Remove'}
                    </button>
                  </div>
                </div>
              ))
            ) : (
              <div className="rounded-lg border border-gray-200 p-4 text-sm text-gray-600">
                No authorized face profiles enrolled yet.
              </div>
            )}

            {profilesError ? (
              <p className="text-sm text-red-600">{profilesError}</p>
            ) : null}
            {profilesMessage ? (
              <p className="text-sm text-green-700">{profilesMessage}</p>
            ) : null}
          </div>

          <button
            onClick={() => setShowAddUserModal(true)}
            className="mt-4 w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors inline-flex items-center justify-center gap-2"
          >
            <UserPlus className="w-4 h-4" />
            Add Authorized Profile
          </button>
        </div>

        <div className={`${activeSettingsSection === 'runtime-controls' ? '' : 'hidden'} bg-white rounded-lg border border-gray-200 p-4 sm:p-6`}>
          <div className="flex items-center gap-3 mb-4 sm:mb-6">
            <div className="w-10 h-10 bg-blue-50 rounded-lg flex items-center justify-center">
              <Shield className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <h3 className="font-semibold text-gray-900">Detection & Backend Controls</h3>
              <p className="text-sm text-gray-600">Adjust live behavior with labeled ranges and monitor the backend components behind them.</p>
            </div>
          </div>

          <div className="space-y-4">
            <section className="rounded-xl border border-blue-200 bg-blue-50/80 p-3 text-gray-900 dark:border-blue-400/30 dark:bg-blue-400/10 dark:text-foreground">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h4 className="font-semibold text-gray-900 dark:text-foreground">Guest Mode</h4>
                    <span className={`rounded-full px-2 py-0.5 text-xs ${guestModeActive ? 'bg-green-100 text-green-800 dark:bg-green-400/15 dark:text-green-200' : 'bg-gray-100 text-gray-700 dark:bg-background dark:text-foreground/75'}`}>
                      {guestModeActive ? 'Active' : 'Inactive'}
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-gray-700 dark:text-foreground/80">
                    Temporarily allow guests without creating unknown-person intruder alerts.
                  </p>
                  {guestModeActive ? (
                    <p className="mt-1 text-xs text-gray-700 dark:text-foreground/75">
                      Ends at {guestModeUntilLabel || 'scheduled time'} • {formatGuestModeRemaining(guestModeRemaining)}
                    </p>
                  ) : (
                    <p className="mt-1 text-xs text-gray-700 dark:text-foreground/75">
                      Choose how long Guest Mode should stay active, then start it when guests arrive.
                    </p>
                  )}
                </div>

                <div className="w-full lg:max-w-md space-y-2">
                  <div className="rounded-lg border border-blue-200 bg-white px-3 py-2.5 dark:border-blue-400/30 dark:bg-background/80">
                    <Slider
                      value={[guestModePresetIndex]}
                      min={0}
                      max={GUEST_MODE_PRESETS.length - 1}
                      step={1}
                      onValueChange={(values) => {
                        const nextIndex = Math.max(0, Math.min(GUEST_MODE_PRESETS.length - 1, Math.round(values[0] ?? 0)));
                        setGuestModeDraftHours(GUEST_MODE_PRESETS[nextIndex].value);
                      }}
                      disabled={guestModeBusy}
                    />
                    <div className="mt-2 grid gap-1" style={{ gridTemplateColumns: `repeat(${GUEST_MODE_PRESETS.length}, minmax(0, 1fr))` }}>
                      {GUEST_MODE_PRESETS.map((preset, index) => (
                        <button
                          key={preset.label}
                          type="button"
                          onClick={() => setGuestModeDraftHours(preset.value)}
                          disabled={guestModeBusy}
                          className={`min-w-0 rounded-md px-1 py-0.5 text-center text-[10px] leading-tight transition-colors disabled:opacity-60 sm:text-[11px] ${index === guestModePresetIndex ? 'bg-primary/15 font-semibold text-foreground ring-1 ring-primary/30' : 'text-foreground/75 hover:bg-accent'}`}
                        >
                          {preset.label}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-[11px] text-gray-700 dark:text-foreground/75">
                      Duration: <span className="font-medium text-gray-900 dark:text-foreground">{selectedGuestModePreset.helper}</span>
                    </p>
                    <div className="flex flex-wrap gap-2">
                      <button
                        onClick={() => void handleStartGuestMode()}
                        disabled={guestModeBusy}
                        className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-60"
                      >
                        {guestModeBusy ? 'Updating...' : guestModeActive ? 'Extend Guest Mode' : 'Start Guest Mode'}
                      </button>
                      {guestModeActive ? (
                        <button
                          onClick={() => void handleEndGuestMode()}
                          disabled={guestModeBusy}
                          className="px-3 py-1.5 text-sm border border-blue-200 bg-white text-blue-700 rounded-lg hover:bg-blue-50 transition-colors disabled:opacity-60 dark:border-blue-400/30 dark:bg-background dark:text-blue-200 dark:hover:bg-blue-400/10"
                        >
                          End now
                        </button>
                      ) : null}
                    </div>
                  </div>
                  {guestModeMessage ? <p className="text-xs text-gray-800 dark:text-foreground/80">{guestModeMessage}</p> : null}
                </div>
              </div>
            </section>

            {runtimeControlGroups.map(({ group, settings }) => (
              <section key={group} className="space-y-2.5">
                <div>
                  <h4 className="text-sm font-semibold text-gray-900">{group}</h4>
                  <p className="text-xs text-gray-600">Changes are staged until you press Save.</p>
                </div>
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-2.5">
                  {settings.map((setting) => {
                    const meta = RUNTIME_CONTROL_META[setting.key];
                    const currentDraft = runtimeDrafts[setting.key] ?? setting.value;
                    const saving = runtimeSavingKey === setting.key;
                    const message = runtimeSaveMessages[setting.key] || '';
                    const presets = meta?.presets;
                    const presetIndex = presets ? nearestPresetIndex(presets, currentDraft) : 0;
                    const selectedPreset = presets?.[presetIndex];

                    return (
                      <div key={setting.key} className="rounded-xl border border-border bg-card p-3 text-card-foreground">
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div className="min-w-0">
                            <p className="text-sm font-medium text-card-foreground">{meta?.title || setting.key}</p>
                            <p className="mt-0.5 text-[11px] font-mono text-muted-foreground break-all">{setting.key}</p>
                          </div>
                          <span className={`rounded-full px-2 py-0.5 text-xs ${setting.liveApply ? 'bg-green-50 text-green-700 dark:bg-green-400/15 dark:text-green-200' : 'bg-amber-50 text-amber-700 dark:bg-amber-400/15 dark:text-amber-100'}`}>
                            {setting.liveApply ? 'Live apply' : 'Restart'}
                          </span>
                        </div>
                        <p className="mt-1 text-xs text-foreground/80">{meta?.description || setting.description}</p>

                        <div className="mt-2.5 space-y-2">
                          {setting.inputType === 'switch' ? (
                            <div className="flex items-center justify-between gap-3 rounded-lg border border-border bg-background/70 px-3 py-2">
                              <span className="text-sm text-foreground">{isRuntimeBoolOn(setting) ? 'Enabled' : 'Disabled'}</span>
                              <label className="relative inline-flex items-center cursor-pointer shrink-0">
                                <input
                                  type="checkbox"
                                  className="sr-only peer"
                                  checked={isRuntimeBoolOn(setting)}
                                  onChange={(event) => {
                                    handleRuntimeDraftChange(setting.key, event.target.checked ? 'true' : 'false');
                                  }}
                                  disabled={Boolean(runtimeSavingKey)}
                                />
                                <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-100 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600 peer-disabled:opacity-60" />
                              </label>
                            </div>
                          ) : presets && selectedPreset ? (
                            <div className="space-y-2">
                              <div className="rounded-lg border border-border bg-background/70 px-3 py-2.5">
                                <Slider
                                  value={[presetIndex]}
                                  min={0}
                                  max={presets.length - 1}
                                  step={1}
                                  onValueChange={(values) => {
                                    const nextIndex = Math.max(0, Math.min(presets.length - 1, Math.round(values[0] ?? 0)));
                                    handleRuntimeDraftChange(setting.key, presets[nextIndex].value);
                                  }}
                                  disabled={Boolean(runtimeSavingKey)}
                                />
                                <div className="mt-2 grid gap-1" style={{ gridTemplateColumns: `repeat(${presets.length}, minmax(0, 1fr))` }}>
                                  {presets.map((preset, index) => (
                                    <button
                                      key={preset.label}
                                      type="button"
                                      onClick={() => handleRuntimeDraftChange(setting.key, preset.value)}
                                      disabled={Boolean(runtimeSavingKey)}
                                      className={`min-w-0 whitespace-normal break-words rounded-md px-1 py-0.5 text-center text-[10px] leading-tight transition-colors disabled:opacity-60 sm:text-[11px] ${index === presetIndex ? 'bg-primary/15 font-semibold text-foreground ring-1 ring-primary/30' : 'text-foreground/75 hover:bg-accent'}`}
                                    >
                                      {preset.label}
                                    </button>
                                  ))}
                                </div>
                              </div>
                              <p className="text-[11px] text-foreground/75">
                                Selected: <span className="font-medium text-foreground">{selectedPreset.label}</span> ({selectedPreset.helper})
                              </p>
                            </div>
                          ) : (
                            <input
                              type={setting.inputType === 'number' ? 'number' : 'text'}
                              min={setting.min}
                              max={setting.max}
                              step={setting.step || (setting.inputType === 'number' ? 1 : undefined)}
                              value={currentDraft}
                              onChange={(event) => {
                                handleRuntimeDraftChange(setting.key, event.target.value);
                              }}
                              disabled={Boolean(runtimeSavingKey)}
                              className="w-full rounded-lg border border-border bg-background px-3 py-1.5 text-sm text-foreground"
                            />
                          )}

                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <button
                              onClick={() => {
                                void handleSaveRuntimeSetting(setting);
                              }}
                              disabled={Boolean(runtimeSavingKey)}
                              className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-60"
                            >
                              {saving ? 'Saving...' : 'Save'}
                            </button>
                            {message ? <p className="text-xs text-foreground/80 break-words">{message}</p> : null}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </section>
            ))}

            {runtimeMainSettings.length === 0 && (
              <div className="rounded-lg border border-gray-200 p-4 text-sm text-gray-600">
                No user-facing runtime controls reported by backend.
              </div>
            )}

            <section className="space-y-4 border-t border-gray-200 pt-5">
              <div>
                <h4 className="text-sm font-semibold text-gray-900">Backend Components</h4>
                <p className="text-xs text-gray-600">Read-only status for the services and pipelines affected by these controls.</p>
              </div>

              {liveNodesError ? (
                <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                  {liveNodesError}
                </div>
              ) : null}

              <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
                <div className="rounded-xl border border-gray-200 p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <Shield className="w-4 h-4 text-blue-600" />
                    <p className="font-medium text-gray-900">System Health</p>
                  </div>
                  {systemHealth ? (
                    <div className="space-y-2 text-sm">
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-gray-600">Backend</span>
                        <StatusBadge severity={systemHealth.backend} label={systemHealth.backend.toUpperCase()} size="sm" />
                      </div>
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-gray-600">Sensor Transport</span>
                        <StatusBadge severity={systemHealth.sensorTransport} label={systemHealth.sensorTransport.toUpperCase()} size="sm" />
                      </div>
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-gray-600">Host</span>
                        <StatusBadge severity={systemHealth.host} label={systemHealth.host.toUpperCase()} size="sm" />
                      </div>
                      <p className="text-xs text-gray-500 break-words">Last sync: {systemHealth.lastSync || '-'}</p>
                    </div>
                  ) : (
                    <p className="text-sm text-gray-600">No system health reported yet.</p>
                  )}
                </div>

                <div className="rounded-xl border border-gray-200 p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <Wifi className="w-4 h-4 text-blue-600" />
                    <p className="font-medium text-gray-900">Sensor Nodes</p>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-center text-sm">
                    <div className="rounded-lg bg-green-50 px-2 py-3 text-green-700">
                      <p className="text-2xl font-semibold">{onlineSensorCount}</p>
                      <p className="text-xs">Online</p>
                    </div>
                    <div className="rounded-lg bg-orange-50 px-2 py-3 text-orange-700">
                      <p className="text-2xl font-semibold">{warningSensorCount}</p>
                      <p className="text-xs">Warning</p>
                    </div>
                    <div className="rounded-lg bg-gray-50 px-2 py-3 text-gray-700">
                      <p className="text-2xl font-semibold">{offlineSensorCount}</p>
                      <p className="text-xs">Offline</p>
                    </div>
                  </div>
                </div>

                <div className="rounded-xl border border-gray-200 p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <Database className="w-4 h-4 text-blue-600" />
                    <p className="font-medium text-gray-900">Runtime Services</p>
                  </div>
                  <p className="mb-3 text-sm text-gray-600">{onlineServiceCount}/{serviceStatuses.length} services online</p>
                  <div className="space-y-2">
                    {serviceStatuses.map((service) => (
                      <div key={service.id} className="flex items-start justify-between gap-3 rounded-lg bg-gray-50 px-3 py-2">
                        <div className="min-w-0">
                          <p className="text-sm font-medium text-gray-900">{service.name}</p>
                          <p className="text-xs text-gray-600 break-words">{service.detail}</p>
                        </div>
                        <StatusBadge severity={service.status} label={service.status.toUpperCase()} size="sm" />
                      </div>
                    ))}
                    {serviceStatuses.length === 0 ? <p className="text-sm text-gray-600">No runtime services reported yet.</p> : null}
                  </div>
                </div>

                <div className="rounded-xl border border-gray-200 p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <Shield className="w-4 h-4 text-blue-600" />
                    <p className="font-medium text-gray-900">Detection Pipelines</p>
                  </div>
                  <div className="space-y-2">
                    {detectionPipelines.map((pipeline) => {
                      const severity = detectionPipelineSeverity(pipeline.state);
                      return (
                        <div key={pipeline.name} className="flex items-start justify-between gap-3 rounded-lg bg-gray-50 px-3 py-2">
                          <div className="min-w-0">
                            <p className="text-sm font-medium text-gray-900">{pipeline.name}</p>
                            <p className="text-xs text-gray-600 break-words">{pipeline.detail}</p>
                          </div>
                          <StatusBadge severity={severity} label={pipeline.state.toUpperCase()} size="sm" />
                        </div>
                      );
                    })}
                    {detectionPipelines.length === 0 ? <p className="text-sm text-gray-600">No detection pipelines reported yet.</p> : null}
                  </div>
                </div>

                <div className="rounded-xl border border-gray-200 p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <Camera className="w-4 h-4 text-blue-600" />
                    <p className="font-medium text-gray-900">Camera Health</p>
                  </div>
                  <p className="mb-3 text-sm text-gray-600">{onlineCameraCount}/{cameraFeeds.length} camera feeds online</p>
                  <div className="space-y-2">
                    {cameraFeeds.map((cameraFeed) => (
                      <div key={cameraFeed.nodeId} className="flex items-start justify-between gap-3 rounded-lg bg-gray-50 px-3 py-2">
                        <div className="min-w-0">
                          <p className="text-sm font-medium text-gray-900">{cameraFeed.location || cameraFeed.nodeId}</p>
                          <p className="text-xs text-gray-600 break-words">
                            {cameraFeed.fps} FPS target{cameraFeed.frameWidth && cameraFeed.frameHeight ? ` • ${cameraFeed.frameWidth}x${cameraFeed.frameHeight}` : ''}
                          </p>
                        </div>
                        <StatusBadge severity={cameraFeed.status} label={cameraFeed.status.toUpperCase()} size="sm" />
                      </div>
                    ))}
                    {cameraFeeds.length === 0 ? <p className="text-sm text-gray-600">No camera feeds reported yet.</p> : null}
                  </div>
                </div>

                <div className="rounded-xl border border-gray-200 p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <Database className="w-4 h-4 text-blue-600" />
                    <p className="font-medium text-gray-900">Retention & Backup</p>
                  </div>
                  <div className="space-y-2 text-sm">
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-gray-600">Events</span>
                      <span className="font-medium text-gray-900">{retentionStatus ? `${retentionStatus.eventRetentionDays} days` : '-'}</span>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-gray-600">Logs</span>
                      <span className="font-medium text-gray-900">{retentionStatus ? `${retentionStatus.logRetentionDays} days` : '-'}</span>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-gray-600">Latest backup</span>
                      <span className="font-medium text-gray-900 text-right break-all">{latestBackupLabel}</span>
                    </div>
                    <p className="text-xs text-gray-500">Backup files available: {backupStatus?.count ?? 0}</p>
                  </div>
                </div>
              </div>
            </section>
          </div>
        </div>

        <div className={`${activeSettingsSection === 'runtime-security' ? '' : 'hidden'} bg-white rounded-lg border border-gray-200 p-4 sm:p-6`}>
          <div className="flex items-center gap-3 mb-4 sm:mb-6">
            <div className="w-10 h-10 bg-blue-50 rounded-lg flex items-center justify-center">
              <Shield className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <h3 className="font-semibold text-gray-900">Account Security</h3>
              <p className="text-sm text-gray-600">Manage admin password and emergency recovery code.</p>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="rounded-lg border border-gray-200 p-4 space-y-3">
              <p className="text-sm font-medium text-gray-900">Change Password</p>
              <input
                type="password"
                value={currentPassword}
                onChange={(event) => setCurrentPassword(event.target.value)}
                placeholder="Current password"
                disabled={accountSecurityBusy}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900"
              />
              <input
                type="password"
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
                placeholder="New password (min 8 chars)"
                disabled={accountSecurityBusy}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900"
              />
              <button
                onClick={() => {
                  void handleChangePassword();
                }}
                disabled={accountSecurityBusy}
                className="px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-60"
              >
                {accountSecurityBusy ? 'Saving...' : 'Update Password'}
              </button>
            </div>

            <div className="rounded-lg border border-gray-200 p-4 space-y-3">
              <p className="text-sm font-medium text-gray-900">Recovery Code</p>
              <p className="text-xs text-gray-600">
                Generate a one-time recovery code and store it securely. It is required for forgot-password resets.
              </p>
              <button
                onClick={() => {
                  void handleGenerateRecoveryCode();
                }}
                disabled={accountSecurityBusy}
                className="px-3 py-2 text-sm bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-60"
              >
                {accountSecurityBusy ? 'Generating...' : 'Generate Recovery Code'}
              </button>
              {recoveryCode ? (
                <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2">
                  <p className="text-xs font-semibold text-amber-800">Save this now (shown once):</p>
                  <p className="mt-1 font-mono text-sm text-amber-800 break-all">{recoveryCode}</p>
                </div>
              ) : null}
            </div>
          </div>

          {accountSecurityError ? <p className="mt-3 text-sm text-red-600">{accountSecurityError}</p> : null}
          {accountSecurityMessage ? <p className="mt-3 text-sm text-green-700">{accountSecurityMessage}</p> : null}
        </div>

        <div className={`${activeSettingsSection === 'runtime-backup' ? '' : 'hidden'} bg-white rounded-lg border border-gray-200 p-4 sm:p-6`}>
          <div className="flex items-center gap-3 mb-4 sm:mb-6">
            <div className="w-10 h-10 bg-blue-50 rounded-lg flex items-center justify-center">
              <Database className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <h3 className="font-semibold text-gray-900">Backup & Retention</h3>
              <p className="text-sm text-gray-600">Create full backups and inspect automatic cleanup activity.</p>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="rounded-lg border border-gray-200 p-4 space-y-3">
              <p className="text-sm font-medium text-gray-900">Backups</p>
              <p className="text-xs text-gray-600">Stored backups: {backupStatus?.count ?? 0}</p>
              <p className="text-xs text-gray-600 break-all">
                Latest: {backupStatus?.latest ? `${backupStatus.latest.name} (${Math.max(1, Math.round(backupStatus.latest.sizeBytes / 1024))} KB)` : 'No backups yet'}
              </p>
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => {
                    void handleCreateBackup();
                  }}
                  disabled={backupBusy}
                  className="px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-60"
                >
                  {backupBusy ? 'Creating...' : 'Create Backup Now'}
                </button>
                {backupStatus?.latest ? (
                  <a
                    href={`/api/ui/backup/download/${backupStatus.latest.name}`}
                    className="px-3 py-2 text-sm bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                  >
                    Download Latest
                  </a>
                ) : null}
              </div>
              {backupMessage ? <p className="text-xs text-gray-700 break-words">{backupMessage}</p> : null}
            </div>

            <div className="rounded-lg border border-gray-200 p-4 space-y-2">
              <p className="text-sm font-medium text-gray-900">Retention Status</p>
              <p className="text-xs text-gray-600">Events: {retentionStatus?.eventRetentionDays ?? '—'} days</p>
              <p className="text-xs text-gray-600">Logs: {retentionStatus?.logRetentionDays ?? '—'} days</p>
              <p className="text-xs text-gray-600">Snapshots (regular/critical): {retentionStatus?.regularSnapshotRetentionDays ?? '—'} / {retentionStatus?.criticalSnapshotRetentionDays ?? '—'} days</p>
              <p className="text-xs text-gray-600">Last cleanup: {retentionStatus?.lastRunTs ? new Date(retentionStatus.lastRunTs).toLocaleString() : 'Not yet reported'}</p>
              <p className="text-xs text-gray-600">Last deleted: events {retentionStatus?.lastEventsDeleted ?? 0}, logs {retentionStatus?.lastLogsDeleted ?? 0}, snapshots {retentionStatus?.lastSnapshotsDeleted ?? 0}</p>
            </div>
          </div>
        </div>

        <div className={`${activeSettingsSection === 'mobile-remote' ? '' : 'hidden'} bg-white rounded-lg border border-gray-200 p-4 sm:p-6`}>
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 bg-blue-50 rounded-lg flex items-center justify-center">
              <Camera className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <h3 className="font-semibold text-gray-900">Mobile Remote Interface</h3>
              <p className="text-sm text-gray-600">
                Phone-optimized monitoring view for local network sessions.
              </p>
            </div>
          </div>

          <div className="rounded-lg border border-gray-200 p-4">
            <div className="flex items-start sm:items-center justify-between gap-4">
              <div className="min-w-0">
                <p className="font-medium text-gray-900">Mobile Remote</p>
                <p className="text-sm text-gray-600 mt-1 break-words">
                  Always available for local network sessions. No manual enable switch is required.
                </p>
              </div>
              <span className="shrink-0 rounded-full border border-green-200 bg-green-50 px-3 py-1 text-xs font-medium text-green-700">
                Always on
              </span>
            </div>

            <div className="mt-4 text-sm text-gray-700 space-y-2">
              <p>
                Status: <span className="font-medium">Enabled</span>
              </p>
              <p>
                Route: <span className="font-mono break-all">{mobileRemoteRoute}</span>
              </p>
              <p>
                Preferred URL:{' '}
                <span className="font-mono break-all">
                  {remoteLinks?.preferredUrl || mobileRemoteUrl}
                </span>
              </p>
              <p className="text-xs text-gray-600 break-words">
                {mobileRemoteStatus?.detail || 'Mobile remote interface is always enabled for local network session access.'}
              </p>
            </div>

            <div className="mt-4 rounded-lg border border-gray-200 bg-gray-50 p-3 space-y-2 text-sm text-gray-700">
              <div className="flex items-center gap-2">
                <Link2 className="w-4 h-4 text-blue-600" />
                <p className="font-medium text-gray-900">Remote Access Links</p>
              </div>
              <p className="break-all">
                Tailscale: <span className="font-mono">{remoteLinks?.tailscaleUrl || 'Not configured'}</span>
              </p>
              <p className="break-all">
                LAN: <span className="font-mono">{remoteLinks?.lanUrl || 'Unavailable'}</span>
              </p>
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
              <a
                href={mobileRemoteRoute}
                className="px-3 py-1.5 text-sm bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
              >
                Open Mobile Interface
              </a>
              <button
                onClick={() => {
                  void navigator.clipboard?.writeText(mobileRemoteUrl);
                }}
                className="px-3 py-1.5 text-sm bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
              >
                Copy Preferred URL
              </button>
            </div>
          </div>
        </div>
      </div>

      </div>

      {showAddUserModal && addUserModal}
      {showEditProfileModal && editProfileModal}
    </div>
  );
}
