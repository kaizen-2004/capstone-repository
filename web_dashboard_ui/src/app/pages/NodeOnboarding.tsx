import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Camera, CheckCircle2, RefreshCw, Router, Search, Wifi } from 'lucide-react';
import { applyOnboardedCameraStream, reprovisionAllNodes, type ReprovisionNodeResult } from '../data/liveApi';
import {
  fetchProvisionInfo,
  fetchProvisionStatus,
  resetProvisioning,
  scanProvisionNetworks,
  submitProvisionWifi,
  type ProvisionInfoPayload,
  type ProvisionNetwork,
  type ProvisionNodeType,
  type ProvisionStatusPayload,
} from '../data/nodeProvisioningApi';

type NodeOption = {
  id: ProvisionNodeType;
  label: string;
  defaultHostname: string;
  role: string;
};

const NODE_OPTIONS: NodeOption[] = [
  { id: 'cam_door', label: 'Door Camera (ESP32-CAM)', defaultHostname: 'cam-door', role: 'Camera' },
  { id: 'door_force', label: 'Door Force Node', defaultHostname: 'door-force', role: 'Sensor' },
  { id: 'smoke_node1', label: 'Smoke Sensor Node 1', defaultHostname: 'smoke-node1', role: 'Sensor' },
  { id: 'smoke_node2', label: 'Smoke Sensor Node 2', defaultHostname: 'smoke-node2', role: 'Sensor' },
];

export function NodeOnboarding() {
  const [selectedNode, setSelectedNode] = useState<ProvisionNodeType>('cam_door');
  const [setupBaseUrl, setSetupBaseUrl] = useState('http://192.168.4.1');
  const [ssid, setSsid] = useState('');
  const [password, setPassword] = useState('');
  const [hostname, setHostname] = useState('cam-door');
  const [backendBase, setBackendBase] = useState(() => {
    if (typeof window === 'undefined') {
      return '';
    }
    const host = window.location.hostname.toLowerCase();
    if (host === 'localhost' || host === '127.0.0.1' || host === '::1') {
      return '';
    }
    return `${window.location.protocol}//${window.location.host}`;
  });

  const [info, setInfo] = useState<ProvisionInfoPayload | null>(null);
  const [status, setStatus] = useState<ProvisionStatusPayload | null>(null);
  const [networks, setNetworks] = useState<ProvisionNetwork[]>([]);

  const [isCheckingNode, setIsCheckingNode] = useState(false);
  const [isScanning, setIsScanning] = useState(false);
  const [isProvisioning, setIsProvisioning] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [isApplyingCamera, setIsApplyingCamera] = useState(false);
  const [isReprovisioningAll, setIsReprovisioningAll] = useState(false);
  const [isPolling, setIsPolling] = useState(false);
  const [cameraApplyState, setCameraApplyState] = useState<'idle' | 'auto_pending' | 'applied' | 'failed'>('idle');
  const [appliedCameraUrl, setAppliedCameraUrl] = useState('');
  const [reprovisionResults, setReprovisionResults] = useState<ReprovisionNodeResult[]>([]);

  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const selectedNodeMeta = useMemo(
    () => NODE_OPTIONS.find((node) => node.id === selectedNode) || NODE_OPTIONS[0],
    [selectedNode],
  );

  useEffect(() => {
    setHostname(selectedNodeMeta.defaultHostname);
  }, [selectedNodeMeta.defaultHostname]);

  useEffect(() => {
    setCameraApplyState('idle');
    setAppliedCameraUrl('');
  }, [selectedNode]);

  const refreshStatus = async () => {
    const nextStatus = await fetchProvisionStatus(setupBaseUrl);
    setStatus(nextStatus);
    return nextStatus;
  };

  const handleRefreshStatus = async () => {
    setError('');
    try {
      await refreshStatus();
      setMessage('Status refreshed.');
    } catch (caught) {
      const detail = caught instanceof Error ? caught.message : 'Unable to refresh node status.';
      setError(detail);
      setMessage('');
    }
  };

  const handleCheckNode = async () => {
    setIsCheckingNode(true);
    setError('');
    setMessage('Checking setup node...');
    try {
      const [nextInfo, nextStatus] = await Promise.all([
        fetchProvisionInfo(setupBaseUrl),
        fetchProvisionStatus(setupBaseUrl),
      ]);
      setInfo(nextInfo);
      setStatus(nextStatus);
      if (!ssid && nextStatus.sta.ssid) {
        setSsid(nextStatus.sta.ssid);
      }
      if (nextStatus.sta.connected) {
        setMessage(`Node connected at ${nextStatus.sta.ip || nextStatus.mdns.host || 'network ready'}.`);
      } else {
        setCameraApplyState('idle');
        setAppliedCameraUrl('');
        setMessage('Setup node reachable. Ready for Wi-Fi provisioning.');
      }
    } catch (caught) {
      const detail = caught instanceof Error ? caught.message : 'Unable to reach setup node.';
      setError(detail);
      setMessage('');
    } finally {
      setIsCheckingNode(false);
    }
  };

  const handleScanNetworks = async () => {
    setIsScanning(true);
    setError('');
    try {
      const nextNetworks = await scanProvisionNetworks(setupBaseUrl);
      setNetworks(nextNetworks);
      setMessage(nextNetworks.length > 0 ? 'Wi-Fi scan completed.' : 'No visible networks returned by node scan.');
    } catch (caught) {
      const detail = caught instanceof Error ? caught.message : 'Wi-Fi scan failed.';
      setError(detail);
      setMessage('');
    } finally {
      setIsScanning(false);
    }
  };

  const handleProvision = async () => {
    if (!ssid.trim()) {
      setError('SSID is required.');
      return;
    }

    setIsProvisioning(true);
    setError('');
    setMessage('Sending Wi-Fi credentials to node...');
    try {
      const result = await submitProvisionWifi(setupBaseUrl, {
        ssid: ssid.trim(),
        password,
        hostname: hostname.trim() || selectedNodeMeta.defaultHostname,
        backendBase: backendBase.trim(),
      });
      setCameraApplyState('idle');
      setAppliedCameraUrl('');
      setMessage(result.detail || 'Credentials accepted. Waiting for connection...');
      setIsPolling(true);
    } catch (caught) {
      const detail = caught instanceof Error ? caught.message : 'Provisioning request failed.';
      setError(detail);
      setMessage('');
    } finally {
      setIsProvisioning(false);
    }
  };

  const handleResetProvisioning = async () => {
    setIsResetting(true);
    setError('');
    setMessage('Resetting node provisioning...');
    try {
      const result = await resetProvisioning(setupBaseUrl);
      setCameraApplyState('idle');
      setAppliedCameraUrl('');
      setMessage(result.detail || 'Provisioning reset requested.');
      setIsPolling(true);
    } catch (caught) {
      const detail = caught instanceof Error ? caught.message : 'Reset request failed.';
      setError(detail);
      setMessage('');
    } finally {
      setIsResetting(false);
    }
  };

  const handleApplyCameraUrl = async (currentStatus?: ProvisionStatusPayload, fromAuto = false) => {
    const activeStatus = currentStatus || status;
    if (!activeStatus?.sta.connected) {
      setError('Camera must be connected before applying stream URL.');
      return;
    }

    const staStreamUrl = activeStatus.endpoints.stream;
    const mdnsStreamUrl = activeStatus.mdns.ready && activeStatus.mdns.host
      ? `http://${activeStatus.mdns.host}:81/stream`
      : '';
    const preferredStreamUrl = staStreamUrl || mdnsStreamUrl;
    const fallbackStreamUrl = mdnsStreamUrl && mdnsStreamUrl !== preferredStreamUrl
      ? mdnsStreamUrl
      : '';

    if (!preferredStreamUrl) {
      setError('Node did not return a stream URL yet.');
      return;
    }

    setIsApplyingCamera(true);
    setError('');
    setMessage(fromAuto ? 'Node connected. Applying cam_door URL automatically...' : 'Applying camera URL to backend runtime...');
    try {
      const result = await applyOnboardedCameraStream({
        nodeId: 'cam_door',
        streamUrl: preferredStreamUrl,
        fallbackStreamUrl,
      });
      setCameraApplyState('applied');
      setAppliedCameraUrl(result.activeStreamUrl);
      setMessage(
        result.cameraRuntime.status
          ? `${fromAuto ? 'Auto-applied' : 'Backend updated'}: ${result.activeStreamUrl} (${result.cameraRuntime.status}).`
          : `${fromAuto ? 'Auto-applied' : 'Backend updated'}: ${result.activeStreamUrl}.`,
      );
    } catch (caught) {
      setCameraApplyState('failed');
      const detail = caught instanceof Error ? caught.message : 'Unable to apply camera URL.';
      setError(fromAuto ? `${detail} You can retry using the Apply button below.` : detail);
      setMessage('');
    } finally {
      setIsApplyingCamera(false);
    }
  };

  const handleReprovisionAllNodes = async () => {
    if (typeof window !== 'undefined') {
      const confirmed = window.confirm(
        'Send provisioning reset to cam_door, door_force, smoke_node1, and smoke_node2? Online nodes will switch back to setup AP mode.',
      );
      if (!confirmed) {
        return;
      }
    }

    setIsReprovisioningAll(true);
    setError('');
    setMessage('Sending reprovision command to all fixed nodes...');
    setReprovisionResults([]);

    try {
      const result = await reprovisionAllNodes();
      setReprovisionResults(result.results);
      setMessage(
        `Reprovision requested. Accepted: ${result.summary.accepted}, offline/no IP: ${result.summary.offlineNoIp}, failed: ${result.summary.failed}.`,
      );
    } catch (caught) {
      const detail = caught instanceof Error ? caught.message : 'Unable to request reprovision for all nodes.';
      setError(detail);
      setMessage('');
    } finally {
      setIsReprovisioningAll(false);
    }
  };

  useEffect(() => {
    if (!isPolling) {
      return undefined;
    }

    let cancelled = false;
    const tick = async () => {
      try {
        const nextStatus = await refreshStatus();
        if (cancelled) {
          return;
        }
        if (nextStatus.sta.connected) {
          setIsPolling(false);
          setMessage(`Node connected. STA IP: ${nextStatus.sta.ip || 'resolved via mDNS soon'}`);
        }
      } catch {
        if (!cancelled) {
          setIsPolling(false);
        }
      }
    };

    void tick();
    const timer = window.setInterval(() => {
      void tick();
    }, 2000);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [isPolling, setupBaseUrl]);

  useEffect(() => {
    if (selectedNode !== 'cam_door') {
      return;
    }
    if (!status?.sta.connected) {
      return;
    }
    if (cameraApplyState !== 'idle' || isApplyingCamera) {
      return;
    }
    setCameraApplyState('auto_pending');
    void handleApplyCameraUrl(status, true);
  }, [
    selectedNode,
    status,
    cameraApplyState,
    isApplyingCamera,
  ]);

  return (
    <div className="p-3 sm:p-4 md:p-8 space-y-6 md:space-y-8 overflow-x-hidden">
      <div>
        <h2 className="text-xl md:text-2xl font-semibold text-gray-900">Node Onboarding</h2>
        <p className="text-sm md:text-base text-gray-600 mt-1">
          V380-style onboarding for camera and sensor nodes using setup AP mode at `192.168.4.1`.
        </p>
      </div>

      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900 flex gap-3">
        <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
        <p>
          Setup AP is open for convenience and expires after 10 minutes. For `cam_door`, the dashboard auto-applies the discovered camera URL to backend runtime after connection.
        </p>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-4 sm:p-6 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="font-semibold text-gray-900">Reprovision All Nodes (Fixed 4)</h3>
            <p className="text-sm text-gray-600 mt-1">
              Sends reset command to `cam_door`, `door_force`, `smoke_node1`, and `smoke_node2` using their last known LAN IP.
            </p>
          </div>
          <button
            onClick={() => { void handleReprovisionAllNodes(); }}
            disabled={isReprovisioningAll}
            className="px-3 py-2 text-sm bg-amber-600 text-white rounded-lg hover:bg-amber-700 disabled:opacity-60"
          >
            {isReprovisioningAll ? 'Requesting...' : 'Reprovision All Nodes'}
          </button>
        </div>

        {reprovisionResults.length > 0 && (
          <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 space-y-2 text-sm">
            {reprovisionResults.map((row) => (
              <div key={row.nodeId} className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1 sm:gap-3">
                <div className="font-mono text-gray-900">{row.nodeId}</div>
                <div className="text-gray-600 break-all">{row.ip || '-'}</div>
                <div className={`px-2 py-0.5 rounded text-xs uppercase tracking-wide ${row.status === 'accepted' ? 'bg-emerald-100 text-emerald-700' : row.status === 'offline_no_ip' ? 'bg-gray-200 text-gray-700' : row.status === 'timeout' ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700'}`}>
                  {row.status.replace(/_/g, ' ')}
                </div>
                <div className="text-gray-700 sm:text-right">{row.detail}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-4 sm:p-6 space-y-4">
        <div className="flex items-center gap-2 text-gray-900">
          <Router className="w-5 h-5 text-blue-600" />
          <h3 className="font-semibold">1) Select Node and Reach Setup AP</h3>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Target node</label>
            <select
              value={selectedNode}
              onChange={(event) => setSelectedNode(event.target.value as ProvisionNodeType)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
            >
              {NODE_OPTIONS.map((node) => (
                <option key={node.id} value={node.id}>{node.label}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Setup API base URL</label>
            <input
              type="text"
              value={setupBaseUrl}
              onChange={(event) => setSetupBaseUrl(event.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
              placeholder="http://192.168.4.1"
            />
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => { void handleCheckNode(); }}
            disabled={isCheckingNode}
            className="px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-60"
          >
            {isCheckingNode ? 'Checking...' : 'Check Setup Node'}
          </button>
          <button
            onClick={() => { void handleRefreshStatus(); }}
            className="px-3 py-2 text-sm bg-white border border-gray-300 rounded-lg hover:bg-gray-50 inline-flex items-center gap-1.5"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh Status
          </button>
          <button
            onClick={() => { void handleScanNetworks(); }}
            disabled={isScanning}
            className="px-3 py-2 text-sm bg-white border border-gray-300 rounded-lg hover:bg-gray-50 inline-flex items-center gap-1.5 disabled:opacity-60"
          >
            <Search className="w-4 h-4" />
            {isScanning ? 'Scanning...' : 'Scan Nearby Wi-Fi'}
          </button>
        </div>

        {networks.length > 0 && (
          <div className="rounded-lg border border-gray-200 p-3 bg-gray-50">
            <p className="text-sm font-medium text-gray-900 mb-2">Detected Wi-Fi networks</p>
            <div className="space-y-1 max-h-44 overflow-y-auto text-sm text-gray-700">
              {networks.map((network) => (
                <button
                  key={`${network.ssid}-${network.channel}`}
                  onClick={() => setSsid(network.ssid)}
                  className="w-full text-left px-2 py-1 rounded hover:bg-white border border-transparent hover:border-gray-200"
                >
                  {network.ssid} • RSSI {network.rssi} • CH {network.channel} • {network.secure ? 'secured' : 'open'}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-4 sm:p-6 space-y-4">
        <div className="flex items-center gap-2 text-gray-900">
          <Wifi className="w-5 h-5 text-blue-600" />
          <h3 className="font-semibold">2) Send Wi-Fi Credentials</h3>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Home SSID</label>
            <input
              type="text"
              value={ssid}
              onChange={(event) => setSsid(event.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Wi-Fi password</label>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Hostname</label>
            <input
              type="text"
              value={hostname}
              onChange={(event) => setHostname(event.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Backend base URL (optional)</label>
              <input
                type="text"
                value={backendBase}
                onChange={(event) => setBackendBase(event.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                placeholder="http://192.168.1.10:8765"
              />
            </div>
          </div>

        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => { void handleProvision(); }}
            disabled={isProvisioning}
            className="px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-60"
          >
            {isProvisioning ? 'Provisioning...' : 'Provision Wi-Fi'}
          </button>
          <button
            onClick={() => { void handleResetProvisioning(); }}
            disabled={isResetting}
            className="px-3 py-2 text-sm bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-60"
          >
            {isResetting ? 'Resetting...' : 'Reset Provisioning'}
          </button>
        </div>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-4 sm:p-6 space-y-4">
        <div className="flex items-center gap-2 text-gray-900">
          <CheckCircle2 className="w-5 h-5 text-emerald-600" />
          <h3 className="font-semibold">3) Provisioning Status and Apply</h3>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
          <div className="rounded-lg border border-gray-200 p-3 bg-gray-50">
            <p className="font-medium text-gray-900">Node info</p>
            <p className="mt-1 text-gray-700">Node ID: {info?.nodeId || '-'}</p>
            <p className="text-gray-700">Type: {info?.nodeType || selectedNodeMeta.role}</p>
            <p className="text-gray-700">Firmware: {info?.firmwareVersion || '-'}</p>
            <p className="text-gray-700">Chip: {info?.chipId || '-'}</p>
          </div>

          <div className="rounded-lg border border-gray-200 p-3 bg-gray-50">
            <p className="font-medium text-gray-900">Connection state</p>
            <p className="mt-1 text-gray-700">Mode: {status?.mode || '-'}</p>
            <p className="text-gray-700">Provision state: {status?.provisionState || '-'}</p>
            <p className="text-gray-700">STA connected: {status?.sta.connected ? 'Yes' : 'No'}</p>
            <p className="text-gray-700">STA IP: {status?.sta.ip || '-'}</p>
            <p className="text-gray-700">mDNS: {status?.mdns.host || '-'}</p>
            <p className="text-gray-700">Setup AP expires in: {status?.setupAp.expiresInSec ?? 0}s</p>
          </div>
        </div>

        <div className="rounded-lg border border-gray-200 p-3 bg-gray-50 text-sm text-gray-700">
          <p>Stream URL: <span className="font-mono break-all">{status?.endpoints.stream || '-'}</span></p>
          <p>Capture URL: <span className="font-mono break-all">{status?.endpoints.capture || '-'}</span></p>
          <p>Control URL: <span className="font-mono break-all">{status?.endpoints.control || '-'}</span></p>
        </div>

        {selectedNode === 'cam_door' && (
          <div className="space-y-2">
            <button
              onClick={() => { void handleApplyCameraUrl(); }}
              disabled={!status?.sta.connected || isApplyingCamera}
              className="px-3 py-2 text-sm bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 disabled:opacity-60 inline-flex items-center gap-1.5"
            >
              <Camera className="w-4 h-4" />
              {isApplyingCamera ? 'Applying...' : (cameraApplyState === 'applied' ? 'Re-apply cam_door URL' : 'Apply cam_door URL to Backend')}
            </button>
            <p className="text-xs text-gray-600">
              Apply state: {cameraApplyState === 'applied' ? `applied (${appliedCameraUrl || 'ok'})` : cameraApplyState.replace('_', ' ')}
            </p>
          </div>
        )}
      </div>

      {(message || error) && (
        <div className={`rounded-lg border p-3 text-sm ${error ? 'border-red-200 bg-red-50 text-red-800' : 'border-emerald-200 bg-emerald-50 text-emerald-800'}`}>
          {error || message}
        </div>
      )}

      {isPolling && (
        <div className="text-sm text-gray-600 inline-flex items-center gap-2">
          <RefreshCw className="w-4 h-4 animate-spin" />
          Polling node status every 2s...
        </div>
      )}
    </div>
  );
}
