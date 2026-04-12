import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Bell,
  Camera,
  Check,
  Database,
  Link2,
  Save,
  Send,
  Shield,
  Upload,
  User,
  UserPlus,
  Wifi,
  X,
} from 'lucide-react';
import {
  captureFaceTrainingSample,
  createFaceProfile,
  deleteFaceProfile,
  fetchFaceTrainingStatus,
  fetchMdnsStatus,
  fetchMobileRemoteStatus,
  fetchRemoteAccessLinks,
  fetchSettingsLive,
  sendTelegramAccessLink,
  setMobileRemoteEnabled,
  trainFaceModel,
  updateRuntimeSetting,
  type FaceTrainingStatus,
  type MdnsStatusPayload,
  type MobileRemoteStatus,
  type RemoteAccessLinksPayload,
} from '../data/liveApi';
import {
  authorizedProfiles as fallbackAuthorizedProfiles,
  runtimeSettings as fallbackRuntimeSettings,
  systemProfile,
  type AuthorizedProfile,
  type RuntimeSetting,
} from '../data/mockData';

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ''));
    reader.onerror = () => reject(new Error('Failed to read file.'));
    reader.readAsDataURL(file);
  });
}

function readBlobAsDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ''));
    reader.onerror = () => reject(new Error('Failed to read captured frame.'));
    reader.readAsDataURL(blob);
  });
}

export function Settings() {
  const [authorizedProfiles, setAuthorizedProfiles] = useState<AuthorizedProfile[]>(fallbackAuthorizedProfiles);
  const [runtimeSettings, setRuntimeSettings] = useState<RuntimeSetting[]>(fallbackRuntimeSettings);
  const [showAddUserModal, setShowAddUserModal] = useState(false);
  const [newUserName, setNewUserName] = useState('');
  const [newUserRole, setNewUserRole] = useState('Family Member');
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [trainingStatus, setTrainingStatus] = useState<FaceTrainingStatus | null>(null);
  const [trainingComplete, setTrainingComplete] = useState(false);
  const [trainingMessage, setTrainingMessage] = useState('');
  const [trainingError, setTrainingError] = useState('');
  const [trainingInputMode, setTrainingInputMode] = useState<'upload' | 'camera'>('upload');
  const [trainingCameraSource, setTrainingCameraSource] = useState<'device' | 'system'>('device');
  const [trainingSystemCameraNode, setTrainingSystemCameraNode] = useState<'cam_indoor' | 'cam_door'>('cam_indoor');
  const [systemPreviewTick, setSystemPreviewTick] = useState(() => Date.now());
  const [isCameraStarting, setIsCameraStarting] = useState(false);
  const [isCameraLive, setIsCameraLive] = useState(false);
  const [isCapturingSample, setIsCapturingSample] = useState(false);
  const [capturedSamples, setCapturedSamples] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [isTraining, setIsTraining] = useState(false);
  const [isSavingUser, setIsSavingUser] = useState(false);
  const [deletingFaceId, setDeletingFaceId] = useState<number | null>(null);
  const [mobileRemoteStatus, setMobileRemoteStatus] = useState<MobileRemoteStatus | null>(null);
  const [mobileRemoteSaving, setMobileRemoteSaving] = useState(false);
  const [mobileRemoteMessage, setMobileRemoteMessage] = useState('');
  const [remoteLinks, setRemoteLinks] = useState<RemoteAccessLinksPayload | null>(null);
  const [mdnsStatus, setMdnsStatus] = useState<MdnsStatusPayload | null>(null);
  const [remoteLinksMessage, setRemoteLinksMessage] = useState('');
  const [isSendingTelegramLink, setIsSendingTelegramLink] = useState(false);
  const [telegramSnapshotCooldown, setTelegramSnapshotCooldown] = useState('60');
  const [telegramSnapshotSaving, setTelegramSnapshotSaving] = useState(false);
  const [telegramSnapshotMessage, setTelegramSnapshotMessage] = useState('');
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const cameraStreamRef = useRef<MediaStream | null>(null);

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

  const startCameraStream = async () => {
    if (trainingCameraSource !== 'device') {
      return;
    }
    if (cameraStreamRef.current) {
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      setTrainingError(
        'Device camera capture is unavailable in this browser context. Use System Camera Feed or Upload Images.',
      );
      return;
    }
    setIsCameraStarting(true);
    setTrainingError('');
    try {
      let stream: MediaStream | null = null;
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: { ideal: 'user' },
            width: { ideal: 640 },
            height: { ideal: 480 },
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
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Camera access denied or unavailable.';
      setTrainingError(`Unable to start device camera: ${message}. Try System Camera Feed capture.`);
      stopCameraStream();
    } finally {
      setIsCameraStarting(false);
    }
  };

  const captureFrameDataUrl = () => {
    const video = videoRef.current;
    if (!video || video.videoWidth <= 0 || video.videoHeight <= 0) {
      return '';
    }
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const context = canvas.getContext('2d');
    if (!context) {
      return '';
    }
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL('image/jpeg', 0.92);
  };

  const handleCaptureFromDeviceCamera = async () => {
    const cleanName = newUserName.trim();
    if (!cleanName) {
      setTrainingError('Enter the user name before capturing samples.');
      return;
    }
    if (!isCameraLive) {
      setTrainingError('Start the camera before capturing.');
      return;
    }
    const imageData = captureFrameDataUrl();
    if (!imageData) {
      setTrainingError('Camera frame not ready. Wait a moment and try again.');
      return;
    }

    setIsCapturingSample(true);
    setTrainingError('');
    setTrainingMessage('');
    setTrainingComplete(false);
    try {
      const status = await captureFaceTrainingSample(cleanName, imageData);
      setTrainingStatus(status);
      setCapturedSamples((previous) => previous + 1);
      setTrainingMessage(
        `Captured sample accepted. Current total: ${status.count}.`,
      );
    } catch {
      setTrainingError('Capture failed validation. Keep face centered, clear, and well lit.');
    } finally {
      setIsCapturingSample(false);
    }
  };

  const handleCaptureFromSystemCamera = async () => {
    const cleanName = newUserName.trim();
    if (!cleanName) {
      setTrainingError('Enter the user name before capturing samples.');
      return;
    }

    setIsCapturingSample(true);
    setTrainingError('');
    setTrainingMessage('');
    setTrainingComplete(false);
    try {
      const response = await fetch(
        `/camera/frame/${trainingSystemCameraNode}?capture_tick=${Date.now()}`,
        {
          method: 'GET',
          cache: 'no-store',
        },
      );
      if (!response.ok) {
        throw new Error(`camera frame unavailable (${response.status})`);
      }
      const frameBlob = await response.blob();
      const imageData = await readBlobAsDataUrl(frameBlob);
      const status = await captureFaceTrainingSample(cleanName, imageData);
      setTrainingStatus(status);
      setCapturedSamples((previous) => previous + 1);
      setTrainingMessage(`Captured sample accepted. Current total: ${status.count}.`);
      setSystemPreviewTick(Date.now());
    } catch {
      setTrainingError('Unable to capture from system camera feed. Ensure the selected camera feed is online.');
    } finally {
      setIsCapturingSample(false);
    }
  };

  const handleCaptureSample = async () => {
    if (trainingCameraSource === 'system') {
      await handleCaptureFromSystemCamera();
      return;
    }
    await handleCaptureFromDeviceCamera();
  };

  useEffect(() => {
    if (trainingInputMode !== 'camera' || trainingCameraSource !== 'system') {
      return undefined;
    }
    const timer = window.setInterval(() => {
      setSystemPreviewTick(Date.now());
    }, 1000);
    return () => {
      window.clearInterval(timer);
    };
  }, [trainingInputMode, trainingCameraSource]);

  useEffect(() => {
    if (trainingInputMode !== 'camera' || trainingCameraSource !== 'device') {
      stopCameraStream();
    }
  }, [trainingInputMode, trainingCameraSource]);

  const loadSettings = async () => {
    try {
      const [live, remoteStatus, links, mdns] = await Promise.all([
        fetchSettingsLive(),
        fetchMobileRemoteStatus(),
        fetchRemoteAccessLinks(),
        fetchMdnsStatus(),
      ]);
      setAuthorizedProfiles(live.authorizedProfiles);
      setRuntimeSettings(live.runtimeSettings);
      const snapshotCooldown = live.runtimeSettings.find(
        (setting) => setting.key === 'TELEGRAM_SNAPSHOT_COOLDOWN_SECONDS',
      );
      if (snapshotCooldown) {
        setTelegramSnapshotCooldown(snapshotCooldown.value);
      }
      setMobileRemoteStatus(remoteStatus);
      setRemoteLinks(links);
      setMdnsStatus(mdns);
    } catch {
      // Keep fallback data if API is unavailable.
    }
  };

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const [live, remoteStatus, links, mdns] = await Promise.all([
          fetchSettingsLive(),
          fetchMobileRemoteStatus(),
          fetchRemoteAccessLinks(),
          fetchMdnsStatus(),
        ]);
        if (cancelled) {
          return;
        }
        setAuthorizedProfiles(live.authorizedProfiles);
        setRuntimeSettings(live.runtimeSettings);
        const snapshotCooldown = live.runtimeSettings.find(
          (setting) => setting.key === 'TELEGRAM_SNAPSHOT_COOLDOWN_SECONDS',
        );
        if (snapshotCooldown) {
          setTelegramSnapshotCooldown(snapshotCooldown.value);
        }
        setMobileRemoteStatus(remoteStatus);
        setRemoteLinks(links);
        setMdnsStatus(mdns);
      } catch {
        // Keep fallback data if API is unavailable.
      }
    };

    if (!showAddUserModal) {
      void load();
    }
    const timer = window.setInterval(() => {
      if (!showAddUserModal) {
        void load();
      }
    }, 15000);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [showAddUserModal]);

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

  const resetAddUserModal = () => {
    stopCameraStream();
    setShowAddUserModal(false);
    setNewUserName('');
    setNewUserRole('Family Member');
    setSelectedFiles([]);
    setUploadProgress(0);
    setTrainingStatus(null);
    setTrainingComplete(false);
    setTrainingMessage('');
    setTrainingError('');
    setTrainingInputMode('upload');
    setCapturedSamples(0);
    setIsCameraStarting(false);
    setIsCameraLive(false);
    setIsCapturingSample(false);
    setIsUploading(false);
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
    } catch {
      setTrainingError('Unable to refresh training status.');
    }
  };

  const handleUploadImages = async () => {
    const cleanName = newUserName.trim();
    if (!cleanName) {
      setTrainingError('Enter the user name before uploading images.');
      return;
    }
    if (selectedFiles.length === 0) {
      setTrainingError('Select one or more face images first.');
      return;
    }

    setIsUploading(true);
    setTrainingError('');
    setTrainingMessage('');
    setTrainingComplete(false);
    setUploadProgress(0);

    let successCount = 0;
    for (let index = 0; index < selectedFiles.length; index += 1) {
      const file = selectedFiles[index];
      try {
        const dataUrl = await readFileAsDataUrl(file);
        const status = await captureFaceTrainingSample(cleanName, dataUrl);
        setTrainingStatus(status);
        successCount += 1;
      } catch {
        setTrainingError(`Some files failed validation. Keep face centered and well lit.`);
      }
      setUploadProgress(Math.round(((index + 1) / selectedFiles.length) * 100));
    }

    try {
      const latestStatus = await fetchFaceTrainingStatus(cleanName);
      setTrainingStatus(latestStatus);
      if (successCount > 0) {
        setTrainingMessage(
          `${successCount} sample${successCount > 1 ? 's' : ''} accepted. Current total: ${latestStatus.count}.`,
        );
      }
    } catch {
      // Keep latest local training status if refresh fails.
    } finally {
      setIsUploading(false);
    }
  };

  const handleStartTraining = async () => {
    if (!trainingStatus?.ready || isTraining) {
      return;
    }
    setIsTraining(true);
    setTrainingError('');
    setTrainingMessage('');
    try {
      const result = await trainFaceModel();
      if (!result.ok) {
        throw new Error(result.message || 'Face model training failed.');
      }
      setTrainingComplete(true);
      setTrainingMessage('Face recognition model retraining completed successfully.');
      await handleRefreshTrainingStatus();
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Face model training failed.';
      setTrainingError(message);
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
      await createFaceProfile(cleanName, `Role: ${newUserRole}`);
      await loadSettings();
      resetAddUserModal();
    } catch {
      setTrainingError('Unable to save the authorized profile.');
      setIsSavingUser(false);
    }
  };

  const handleRemoveProfile = async (profile: AuthorizedProfile) => {
    const dbId =
      profile.dbId ||
      Number.parseInt(profile.id.replace('auth-', ''), 10);
    if (!Number.isFinite(dbId) || dbId <= 0) {
      return;
    }
    setDeletingFaceId(dbId);
    try {
      await deleteFaceProfile(dbId);
      await loadSettings();
    } catch {
      // Keep current list on failure.
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

  const handleSendAccessLinkToTelegram = async () => {
    if (isSendingTelegramLink) {
      return;
    }
    setIsSendingTelegramLink(true);
    setRemoteLinksMessage('');
    try {
      const result = await sendTelegramAccessLink();
      setRemoteLinksMessage(result.detail || (result.sent ? 'Access link sent to Telegram.' : 'Access link not sent.'));
      await loadSettings();
      window.setTimeout(() => setRemoteLinksMessage(''), 4200);
    } catch {
      setRemoteLinksMessage('Unable to send access link to Telegram.');
      window.setTimeout(() => setRemoteLinksMessage(''), 4200);
    } finally {
      setIsSendingTelegramLink(false);
    }
  };

  const handleSaveTelegramSnapshotCooldown = async () => {
    const trimmed = telegramSnapshotCooldown.trim();
    const parsed = Number.parseInt(trimmed, 10);

    if (!Number.isFinite(parsed) || String(parsed) !== trimmed) {
      setTelegramSnapshotMessage('Enter a whole number between 10 and 3600 seconds.');
      return;
    }
    if (parsed < 10 || parsed > 3600) {
      setTelegramSnapshotMessage('Telegram snapshot cooldown must be between 10 and 3600 seconds.');
      return;
    }

    setTelegramSnapshotSaving(true);
    setTelegramSnapshotMessage('');
    try {
      const result = await updateRuntimeSetting('TELEGRAM_SNAPSHOT_COOLDOWN_SECONDS', String(parsed));
      setTelegramSnapshotCooldown(result.value);
      await loadSettings();
      setTelegramSnapshotMessage(`Telegram snapshot cooldown saved to ${result.value}s.`);
      window.setTimeout(() => setTelegramSnapshotMessage(''), 4200);
    } catch {
      setTelegramSnapshotMessage('Unable to save Telegram snapshot cooldown.');
      window.setTimeout(() => setTelegramSnapshotMessage(''), 4200);
    } finally {
      setTelegramSnapshotSaving(false);
    }
  };

  const mobileRemoteRoute = mobileRemoteStatus?.route || '/dashboard/remote/mobile';
  const mobileRemoteUrl = remoteLinks?.preferredUrl ||
    (typeof window !== 'undefined' ? `${window.location.origin}${mobileRemoteRoute}` : mobileRemoteRoute);

  const addUserModal = (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Add New Authorized User</h3>
            <p className="text-sm text-gray-600 mt-1">Upload samples and retrain the face model.</p>
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
                <li>Use either uploaded photos or live camera capture.</li>
                <li>Use moderate lighting and avoid motion blur.</li>
                <li>Keep the full face visible (no masks/sunglasses).</li>
              </ul>
            </div>

            <div className="inline-flex rounded-lg border border-gray-200 bg-gray-50 p-1">
              <button
                onClick={() => {
                  setTrainingInputMode('upload');
                  setTrainingError('');
                  setTrainingMessage('');
                  stopCameraStream();
                }}
                className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
                  trainingInputMode === 'upload'
                    ? 'bg-white text-blue-700 border border-blue-200'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                Upload Images
              </button>
              <button
                onClick={() => {
                  setTrainingInputMode('camera');
                  setTrainingError('');
                  setTrainingMessage('');
                }}
                className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
                  trainingInputMode === 'camera'
                    ? 'bg-white text-blue-700 border border-blue-200'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                Capture Camera
              </button>
            </div>

            {trainingInputMode === 'upload' ? (
              <>
                <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center">
                  <Camera className="w-10 h-10 text-gray-400 mx-auto mb-3" />
                  <p className="text-sm text-gray-700 mb-3">
                    Select one or more images. Each image is validated before being accepted.
                  </p>
                  <input
                    id="face-upload"
                    type="file"
                    accept="image/*"
                    multiple
                    className="hidden"
                    onChange={(event) => {
                      const files = event.target.files ? Array.from(event.target.files) : [];
                      setSelectedFiles(files);
                      setUploadProgress(0);
                      setTrainingError('');
                      setTrainingMessage('');
                    }}
                  />
                  <label
                    htmlFor="face-upload"
                    className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors cursor-pointer"
                  >
                    <Upload className="w-4 h-4" />
                    Select Images
                  </label>
                </div>

                {selectedFiles.length > 0 && (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between text-sm">
                      <span className="font-medium text-gray-900">
                        {selectedFiles.length} image{selectedFiles.length > 1 ? 's' : ''} selected
                      </span>
                      <span className="text-gray-600">
                        {trainingStatus ? `Current samples: ${trainingStatus.count}` : 'No samples yet'}
                      </span>
                    </div>
                    <div className="grid grid-cols-5 gap-2">
                      {selectedFiles.slice(0, 10).map((file) => (
                        <div
                          key={`${file.name}-${file.lastModified}`}
                          className="aspect-square bg-gray-100 rounded-lg flex items-center justify-center relative"
                        >
                          <Camera className="w-5 h-5 text-gray-500" />
                          <div className="absolute top-1 right-1 w-5 h-5 bg-white/90 rounded-full flex items-center justify-center">
                            <Check className="w-3 h-3 text-green-600" />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="border-2 border-dashed border-gray-300 rounded-lg p-4">
                <div className="mb-3 flex flex-wrap items-center gap-2 justify-center">
                  <button
                    onClick={() => {
                      setTrainingCameraSource('device');
                      setTrainingError('');
                    }}
                    className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
                      trainingCameraSource === 'device'
                        ? 'bg-white text-blue-700 border border-blue-200'
                        : 'text-gray-600 bg-gray-100 hover:text-gray-900'
                    }`}
                  >
                    Device Camera
                  </button>
                  <button
                    onClick={() => {
                      setTrainingCameraSource('system');
                      setTrainingError('');
                    }}
                    className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
                      trainingCameraSource === 'system'
                        ? 'bg-white text-blue-700 border border-blue-200'
                        : 'text-gray-600 bg-gray-100 hover:text-gray-900'
                    }`}
                  >
                    System Camera Feed
                  </button>
                </div>

                {trainingCameraSource === 'device' ? (
                  <>
                    <div className="relative aspect-video bg-gray-900 rounded-lg overflow-hidden mb-3 flex items-center justify-center">
                      <video
                        ref={videoRef}
                        className={`w-full h-full object-cover ${isCameraLive ? '' : 'hidden'}`}
                        muted
                        playsInline
                      />
                      {!isCameraLive && (
                        <div className="text-center text-gray-300 px-4">
                          <Camera className="w-10 h-10 mx-auto mb-2 text-gray-500" />
                          <p className="text-sm">Start camera to preview and capture face samples.</p>
                        </div>
                      )}
                    </div>
                    <div className="flex flex-wrap gap-3 justify-center">
                      <button
                        onClick={() => void startCameraStream()}
                        disabled={isCameraStarting || isCameraLive}
                        className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed"
                      >
                        {isCameraStarting ? 'Starting Camera...' : isCameraLive ? 'Camera Ready' : 'Start Camera'}
                      </button>
                      <button
                        onClick={stopCameraStream}
                        disabled={!isCameraLive || isCameraStarting || isCapturingSample}
                        className="px-4 py-2 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors disabled:text-gray-400"
                      >
                        Stop Camera
                      </button>
                    </div>
                    <p className="text-xs text-gray-600 text-center mt-3">
                      If browser permission is blocked, switch to System Camera Feed.
                    </p>
                  </>
                ) : (
                  <>
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
                    <div className="relative aspect-video bg-gray-900 rounded-lg overflow-hidden mb-3 flex items-center justify-center">
                      <img
                        src={`/camera/frame/${trainingSystemCameraNode}?sample_tick=${systemPreviewTick}`}
                        alt={`${trainingSystemCameraNode} training preview`}
                        className="w-full h-full object-cover"
                        onError={() => {
                          setTrainingError('Selected system camera feed is unavailable.');
                        }}
                      />
                    </div>
                    <div className="flex flex-wrap gap-3 justify-center">
                      <button
                        onClick={() => {
                          setSystemPreviewTick(Date.now());
                          setTrainingError('');
                        }}
                        className="px-4 py-2 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
                      >
                        Refresh Preview
                      </button>
                    </div>
                    <p className="text-xs text-gray-600 text-center mt-3">
                      Uses your backend live feed. No browser camera permission required.
                    </p>
                  </>
                )}
              </div>
            )}

            {trainingInputMode === 'upload' && isUploading && (
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium text-gray-900">Uploading samples</span>
                  <span className="text-gray-600">{uploadProgress}%</span>
                </div>
                <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-blue-600 transition-all duration-300"
                    style={{ width: `${uploadProgress}%` }}
                  />
                </div>
              </div>
            )}

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
              {trainingInputMode === 'upload' ? (
                <button
                  onClick={() => void handleUploadImages()}
                  disabled={isUploading || selectedFiles.length === 0}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed"
                >
                  {isUploading ? 'Uploading...' : 'Upload Samples'}
                </button>
              ) : (
                <button
                  onClick={() => void handleCaptureSample()}
                  disabled={
                    isCameraStarting ||
                    isCapturingSample ||
                    isTraining ||
                    (trainingCameraSource === 'device' && !isCameraLive)
                  }
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed"
                >
                  {isCapturingSample
                    ? 'Capturing...'
                    : trainingCameraSource === 'system'
                      ? 'Capture From Feed'
                      : 'Capture Sample'}
                </button>
              )}
              <button
                onClick={() => void handleRefreshTrainingStatus()}
                disabled={!newUserName.trim()}
                className="px-4 py-2 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors disabled:text-gray-400"
              >
                Refresh Status
              </button>
              <button
                onClick={() => void handleStartTraining()}
                disabled={!trainingStatus?.ready || isTraining || isUploading || isCapturingSample}
                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed"
              >
                {isTraining ? 'Training...' : 'Start Training'}
              </button>
            </div>

            {trainingInputMode === 'camera' && capturedSamples > 0 && (
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
              {
                title: 'Telegram Notifications',
                desc: 'Send active alert summary through Telegram bot channel.',
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

            <div className="rounded-lg border border-gray-200 p-4 bg-gray-50">
              <div className="flex flex-col md:flex-row md:items-end gap-3 md:gap-4">
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-gray-900">Telegram Snapshot Cooldown</p>
                  <p className="text-sm text-gray-600 mt-1 break-words">
                    Minimum interval between Telegram image snapshots for the same source node and alert type.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    min={10}
                    max={3600}
                    step={1}
                    value={telegramSnapshotCooldown}
                    onChange={(event) => setTelegramSnapshotCooldown(event.target.value)}
                    className="w-28 rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900"
                  />
                  <span className="text-sm text-gray-600">seconds</span>
                  <button
                    onClick={() => {
                      void handleSaveTelegramSnapshotCooldown();
                    }}
                    disabled={telegramSnapshotSaving}
                    className="px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-60"
                  >
                    {telegramSnapshotSaving ? 'Saving...' : 'Save'}
                  </button>
                </div>
              </div>
              {telegramSnapshotMessage && (
                <p className="mt-3 text-sm text-gray-700 break-words">{telegramSnapshotMessage}</p>
              )}
            </div>
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
            {authorizedProfiles.length > 0 ? (
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
                  <button
                    onClick={() => void handleRemoveProfile(profile)}
                    disabled={deletingFaceId === profile.dbId}
                    className="self-start sm:self-auto px-3 py-1.5 text-sm text-red-600 hover:bg-red-50 rounded transition-colors disabled:text-gray-400"
                  >
                    {deletingFaceId === profile.dbId ? 'Removing...' : 'Remove'}
                  </button>
                </div>
              ))
            ) : (
              <div className="rounded-lg border border-gray-200 p-4 text-sm text-gray-600">
                No authorized face profiles enrolled yet.
              </div>
            )}
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
              <button
                onClick={() => {
                  void handleSendAccessLinkToTelegram();
                }}
                disabled={isSendingTelegramLink}
                className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-60 inline-flex items-center gap-1.5"
              >
                <Send className="w-4 h-4" />
                {isSendingTelegramLink ? 'Sending...' : 'Send Link to Telegram'}
              </button>
            </div>
            {mobileRemoteMessage && (
              <p className="mt-3 text-sm text-gray-700">{mobileRemoteMessage}</p>
            )}
            {remoteLinksMessage && (
              <p className="mt-2 text-sm text-gray-700 break-words">{remoteLinksMessage}</p>
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
    </div>
  );
}
