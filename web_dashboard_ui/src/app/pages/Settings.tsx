import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Bell,
  Camera,
  Database,
  Link2,
  Pencil,
  Save,
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
  fetchMdnsStatus,
  fetchMobileRemoteStatus,
  fetchRemoteAccessLinks,
  fetchSettingsLive,
  setMobileRemoteEnabled,
  trainFaceModel,
  updateFaceProfile,
  updateRuntimeSetting,
  type FaceTrainingStatus,
  type MdnsStatusPayload,
  type MobileRemoteStatus,
  type RemoteAccessLinksPayload,
} from '../data/liveApi';
import {
  runtimeSettings as fallbackRuntimeSettings,
  systemProfile,
  type AuthorizedProfile,
  type RuntimeSetting,
} from '../data/mockData';

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
  const [runtimeSettings, setRuntimeSettings] = useState<RuntimeSetting[]>(fallbackRuntimeSettings);
  const [runtimeDrafts, setRuntimeDrafts] = useState<Record<string, string>>({});
  const [runtimeSaveMessages, setRuntimeSaveMessages] = useState<Record<string, string>>({});
  const [runtimeSavingKey, setRuntimeSavingKey] = useState<string | null>(null);
  const [runtimeSecretReplaceMode, setRuntimeSecretReplaceMode] = useState<Record<string, boolean>>({});
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
  const [mobileRemoteSaving, setMobileRemoteSaving] = useState(false);
  const [mobileRemoteMessage, setMobileRemoteMessage] = useState('');
  const [remoteLinks, setRemoteLinks] = useState<RemoteAccessLinksPayload | null>(null);
  const [mdnsStatus, setMdnsStatus] = useState<MdnsStatusPayload | null>(null);
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
    const [liveResult, remoteStatusResult, linksResult, mdnsResult] = await Promise.allSettled([
      fetchSettingsLive(),
      fetchMobileRemoteStatus(),
      fetchRemoteAccessLinks(),
      fetchMdnsStatus(),
    ]);

    if (liveResult.status === 'fulfilled') {
      setAuthorizedProfiles(liveResult.value.authorizedProfiles);
      setRuntimeSettings(liveResult.value.runtimeSettings);
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
    if (mdnsResult.status === 'fulfilled') {
      setMdnsStatus(mdnsResult.value);
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
    return () => {
      const stream = cameraStreamRef.current;
      if (stream) {
        stream.getTracks().forEach((track) => track.stop());
        cameraStreamRef.current = null;
      }
    };
  }, []);

  const fusionSettings = useMemo(
    () =>
      runtimeSettings.filter(
        (setting) => setting.key.includes('FUSION_WINDOW') || setting.key.includes('COOLDOWN'),
      ),
    [runtimeSettings],
  );

  const connectivitySettings = useMemo(
    () =>
      runtimeSettings.filter(
        (setting) => !setting.key.includes('FUSION_WINDOW') && !setting.key.includes('COOLDOWN'),
      ),
    [runtimeSettings],
  );

  const runtimeEditableSettings = useMemo(
    () => runtimeSettings.filter((setting) => setting.editable !== false),
    [runtimeSettings],
  );

  const runtimeNonSecretSettings = useMemo(
    () => runtimeEditableSettings.filter((setting) => !setting.secret),
    [runtimeEditableSettings],
  );

  const runtimeSecretSettings = useMemo(
    () => runtimeEditableSettings.filter((setting) => setting.secret),
    [runtimeEditableSettings],
  );

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
      await loadSettings();
      setProfilesMessage('Authorized profile removed.');
      window.setTimeout(() => setProfilesMessage(''), 3000);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to remove authorized profile.';
      setProfilesError(message);
    } finally {
      setDeletingFaceId(null);
    }
  };

  const handleToggleMobileRemote = async (enabled: boolean) => {
    if (mobileRemoteSaving) {
      return;
    }
    setMobileRemoteSaving(true);
    setMobileRemoteMessage('');
    try {
      const updated = await setMobileRemoteEnabled(enabled);
      setMobileRemoteStatus(updated);
      setMobileRemoteMessage(
        updated.enabled
          ? 'Mobile remote interface enabled.'
          : 'Mobile remote interface disabled.',
      );
      window.setTimeout(() => setMobileRemoteMessage(''), 3000);
    } catch {
      setMobileRemoteMessage('Unable to update mobile remote interface setting.');
      window.setTimeout(() => setMobileRemoteMessage(''), 3500);
    } finally {
      setMobileRemoteSaving(false);
    }
  };

  const isRuntimeBoolOn = (setting: RuntimeSetting): boolean => {
    const fallback = String(setting.value || '').trim().toLowerCase();
    const source = String(runtimeDrafts[setting.key] ?? fallback).trim().toLowerCase();
    return source === 'true' || source === '1' || source === 'yes' || source === 'on' || source === 'enabled';
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
    const draftValue = runtimeDrafts[key] ?? (setting.secret ? '' : setting.value);
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

      <div className="space-y-6">
        <div className="bg-white rounded-lg border border-gray-200 p-4 sm:p-6">
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
                enabled: true,
              },
              {
                title: 'Critical Fire Alerts',
                desc: 'Immediate alert for FIRE fusion output.',
                enabled: true,
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
                <label className="relative inline-flex items-center cursor-pointer shrink-0">
                  <input type="checkbox" className="sr-only peer" defaultChecked={item.enabled} />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-100 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600" />
                </label>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-lg border border-gray-200 p-4 sm:p-6">
          <div className="flex items-center gap-3 mb-4 sm:mb-6">
            <div className="w-10 h-10 bg-blue-50 rounded-lg flex items-center justify-center">
              <Shield className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <h3 className="font-semibold text-gray-900">Fusion & Detection Parameters</h3>
              <p className="text-sm text-gray-600">Threshold windows used by the multi-sensor logic.</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {fusionSettings.map((setting) => (
              <div key={setting.key} className="rounded-lg border border-gray-200 p-4">
                <p className="text-[11px] sm:text-xs font-mono text-gray-500 break-all">{setting.key}</p>
                <p className="text-lg font-semibold text-gray-900 mt-1">{setting.value}</p>
                <p className="text-sm text-gray-600 mt-1">{setting.description}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-lg border border-gray-200 p-4 sm:p-6">
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

        <div className="bg-white rounded-lg border border-gray-200 p-4 sm:p-6">
          <div className="flex items-center gap-3 mb-4 sm:mb-6">
            <div className="w-10 h-10 bg-blue-50 rounded-lg flex items-center justify-center">
              <Wifi className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <h3 className="font-semibold text-gray-900">Connectivity & Runtime</h3>
              <p className="text-sm text-gray-600">Core endpoints used by the Windows local-first stack.</p>
            </div>
          </div>

          <div className="space-y-3">
            {connectivitySettings.map((setting) => (
              <div key={setting.key} className="rounded-lg border border-gray-200 p-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-[11px] sm:text-sm font-mono text-gray-900 break-all">{setting.key}</p>
                  <Database className="w-4 h-4 text-gray-500 shrink-0" />
                </div>
                <p className="text-sm font-medium text-gray-900 mt-1 break-all">{setting.value}</p>
                <p className="text-xs text-gray-600 mt-1">{setting.description}</p>
              </div>
            ))}
          </div>

          <div className="mt-4 p-3 rounded-lg bg-gray-50 border border-gray-200 text-sm text-gray-700 break-words">
            <p>
              Monitored scope: {systemProfile.monitoredAreas.join(' and ')}. Contract preserved:{' '}
              {systemProfile.apiContract}.
            </p>
          </div>
        </div>

        <div className="bg-white rounded-lg border border-gray-200 p-4 sm:p-6">
          <div className="flex items-center gap-3 mb-4 sm:mb-6">
            <div className="w-10 h-10 bg-blue-50 rounded-lg flex items-center justify-center">
              <Database className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <h3 className="font-semibold text-gray-900">Runtime Variable Overrides</h3>
              <p className="text-sm text-gray-600">Update selected .env-backed runtime values without editing .env.</p>
            </div>
          </div>

          <div className="space-y-3">
            {runtimeNonSecretSettings.map((setting) => {
              const currentDraft = runtimeDrafts[setting.key] ?? setting.value;
              const saving = runtimeSavingKey === setting.key;
              const message = runtimeSaveMessages[setting.key] || '';
              return (
                <div key={setting.key} className="rounded-lg border border-gray-200 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-[11px] sm:text-sm font-mono text-gray-900 break-all">{setting.key}</p>
                    <div className="flex items-center gap-2 text-xs text-gray-600">
                      <span className="rounded-full bg-gray-100 px-2 py-0.5">{setting.group || 'Runtime'}</span>
                      <span className="rounded-full bg-green-50 text-green-700 px-2 py-0.5">
                        {setting.liveApply ? 'Live' : 'Restart'}
                      </span>
                    </div>
                  </div>
                  <p className="text-xs text-gray-600 mt-1">{setting.description}</p>

                  <div className="mt-3 flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3">
                    {setting.inputType === 'switch' ? (
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
                        className="w-full sm:w-72 rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900"
                      />
                    )}

                    <button
                      onClick={() => {
                        void handleSaveRuntimeSetting(setting);
                      }}
                      disabled={Boolean(runtimeSavingKey)}
                      className="px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-60"
                    >
                      {saving ? 'Saving...' : 'Save'}
                    </button>
                  </div>
                  {message ? <p className="mt-2 text-xs text-gray-700 break-words">{message}</p> : null}
                </div>
              );
            })}
          </div>

          <div className="mt-6">
            <h4 className="font-medium text-gray-900 mb-3">Secrets (Configured / Replace)</h4>
            <div className="space-y-3">
              {runtimeSecretSettings.map((setting) => {
                const key = setting.key;
                const replacing = Boolean(runtimeSecretReplaceMode[key]);
                const saving = runtimeSavingKey === key;
                const message = runtimeSaveMessages[key] || '';
                const configured = Boolean(setting.configured);
                const draft = runtimeDrafts[key] ?? '';

                return (
                  <div key={key} className="rounded-lg border border-gray-200 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-[11px] sm:text-sm font-mono text-gray-900 break-all">{key}</p>
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs ${
                          configured ? 'bg-green-50 text-green-700' : 'bg-amber-50 text-amber-700'
                        }`}
                      >
                        {configured ? 'Configured' : 'Unconfigured'}
                      </span>
                    </div>
                    <p className="text-xs text-gray-600 mt-1">{setting.description}</p>

                    {!replacing ? (
                      <button
                        onClick={() => {
                          handleRuntimeSecretReplaceToggle(key, true);
                        }}
                        disabled={Boolean(runtimeSavingKey)}
                        className="mt-3 px-3 py-2 text-sm bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-60"
                      >
                        Replace
                      </button>
                    ) : (
                      <div className="mt-3 flex flex-col sm:flex-row sm:items-center gap-2">
                        <input
                          type="password"
                          value={draft}
                          onChange={(event) => {
                            handleRuntimeDraftChange(key, event.target.value);
                          }}
                          placeholder="Enter replacement value"
                          disabled={Boolean(runtimeSavingKey)}
                          className="w-full sm:w-80 rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900"
                        />
                        <button
                          onClick={() => {
                            void handleSaveRuntimeSetting(setting);
                          }}
                          disabled={Boolean(runtimeSavingKey)}
                          className="px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-60"
                        >
                          {saving ? 'Saving...' : 'Save'}
                        </button>
                        <button
                          onClick={() => {
                            handleRuntimeSecretReplaceToggle(key, false);
                          }}
                          disabled={Boolean(runtimeSavingKey)}
                          className="px-3 py-2 text-sm bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-60"
                        >
                          Cancel
                        </button>
                      </div>
                    )}
                    {message ? <p className="mt-2 text-xs text-gray-700 break-words">{message}</p> : null}
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg border border-gray-200 p-4 sm:p-6">
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
                <p className="font-medium text-gray-900">Enable Mobile Remote</p>
                <p className="text-sm text-gray-600 mt-1 break-words">
                  Disabled by default. Keep local-only access unless secure overlay is configured.
                </p>
              </div>
              <label className="relative inline-flex items-center cursor-pointer shrink-0">
                <input
                  type="checkbox"
                  className="sr-only peer"
                  checked={Boolean(mobileRemoteStatus?.enabled)}
                  onChange={(event) => {
                    void handleToggleMobileRemote(event.target.checked);
                  }}
                  disabled={mobileRemoteSaving}
                />
                <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-100 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600 peer-disabled:opacity-60" />
              </label>
            </div>

            <div className="mt-4 text-sm text-gray-700 space-y-2">
              <p>
                Status: <span className="font-medium">{mobileRemoteStatus?.enabled ? 'Enabled' : 'Disabled'}</span>
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
              <p className="text-xs text-gray-600 break-words">{mobileRemoteStatus?.detail}</p>
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
                mDNS: <span className="font-mono">{remoteLinks?.mdnsUrl || 'Not available'}</span>
              </p>
              <p className="break-all">
                LAN: <span className="font-mono">{remoteLinks?.lanUrl || 'Unavailable'}</span>
              </p>
              <p className="text-xs text-gray-600 break-words">
                mDNS status: {mdnsStatus?.published ? 'Published' : mdnsStatus?.detail || 'Unavailable'}
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
            {mobileRemoteMessage && (
              <p className="mt-3 text-sm text-gray-700">{mobileRemoteMessage}</p>
            )}
          </div>
        </div>
      </div>

      <div className="flex flex-col sm:flex-row sm:justify-end gap-3 pt-6 border-t border-gray-200">
        <button className="w-full sm:w-auto px-6 py-2 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
          Revert
        </button>
        <button className="w-full sm:w-auto px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors inline-flex items-center justify-center gap-2">
          <Save className="w-4 h-4" />
          Save Changes
        </button>
      </div>

      {showAddUserModal && addUserModal}
      {showEditProfileModal && editProfileModal}
    </div>
  );
}
