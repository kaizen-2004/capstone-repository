type Json = Record<string, unknown>;

export type ProvisionNodeType = 'cam_door' | 'door_force' | 'smoke_node1' | 'smoke_node2';

export interface ProvisionInfoPayload {
  ok: boolean;
  nodeId: string;
  nodeType: string;
  firmwareVersion: string;
  chipId: string;
  setupAp: {
    ssid: string;
    ip: string;
    open: boolean;
  };
}

export interface ProvisionStatusPayload {
  ok: boolean;
  nodeId: string;
  mode: string;
  provisionState: string;
  setupAp: {
    active: boolean;
    ssid: string;
    ip: string;
    expiresInSec: number;
  };
  sta: {
    configured: boolean;
    connected: boolean;
    ssid: string;
    ip: string;
    rssi: number | null;
    lastError: string;
    lastDisconnectReason: number;
  };
  mdns: {
    enabled: boolean;
    host: string;
    ready: boolean;
  };
  endpoints: {
    stream: string;
    capture: string;
    control: string;
  };
}

export interface ProvisionNetwork {
  ssid: string;
  rssi: number;
  secure: boolean;
  channel: number;
}

export interface ProvisionWifiResult {
  ok: boolean;
  accepted: boolean;
  provisionState: string;
  detail: string;
}

function toInt(value: unknown, fallback = 0): number {
  const asNumber = Number(value);
  return Number.isFinite(asNumber) ? Math.trunc(asNumber) : fallback;
}

function normalizeProvisionBaseUrl(baseUrl: string): string {
  const trimmed = baseUrl.trim() || 'http://192.168.4.1';
  return trimmed.endsWith('/') ? trimmed.slice(0, -1) : trimmed;
}

async function fetchProvisionJson<T>(baseUrl: string, path: string, init?: RequestInit): Promise<T> {
  const endpoint = `${normalizeProvisionBaseUrl(baseUrl)}${path}`;
  let response: Response;
  try {
    response = await fetch(endpoint, {
      mode: 'cors',
      credentials: 'omit',
      cache: 'no-store',
      ...init,
    });
  } catch (caught) {
    const detail = caught instanceof Error ? caught.message : 'network request failed';
    const mixedContentHint =
      typeof window !== 'undefined' && window.location.protocol === 'https:' && endpoint.startsWith('http://')
        ? ' Open the dashboard over HTTP during node provisioning.'
        : '';
    throw new Error(`Cannot reach ${endpoint}. Connect this device to the node AP or use the node LAN IP.${mixedContentHint} (${detail})`);
  }

  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    const detail = payload && typeof payload === 'object'
      ? String((payload as Json).detail ?? (payload as Json).error ?? `HTTP ${response.status}`)
      : `HTTP ${response.status}`;
    throw new Error(detail);
  }

  return (payload || {}) as T;
}

export async function fetchProvisionInfo(baseUrl: string): Promise<ProvisionInfoPayload> {
  const payload = await fetchProvisionJson<Json>(baseUrl, '/api/provision/info');
  const setupApRaw = payload.setup_ap && typeof payload.setup_ap === 'object'
    ? (payload.setup_ap as Json)
    : {};

  return {
    ok: Boolean(payload.ok),
    nodeId: String(payload.node_id ?? ''),
    nodeType: String(payload.node_type ?? ''),
    firmwareVersion: String(payload.firmware_version ?? ''),
    chipId: String(payload.chip_id ?? ''),
    setupAp: {
      ssid: String(setupApRaw.ssid ?? ''),
      ip: String(setupApRaw.ip ?? ''),
      open: Boolean(setupApRaw.open),
    },
  };
}

export async function fetchProvisionStatus(baseUrl: string): Promise<ProvisionStatusPayload> {
  const payload = await fetchProvisionJson<Json>(baseUrl, '/api/provision/status');
  const setupApRaw = payload.setup_ap && typeof payload.setup_ap === 'object'
    ? (payload.setup_ap as Json)
    : {};
  const staRaw = payload.sta && typeof payload.sta === 'object'
    ? (payload.sta as Json)
    : {};
  const mdnsRaw = payload.mdns && typeof payload.mdns === 'object'
    ? (payload.mdns as Json)
    : {};
  const endpointsRaw = payload.endpoints && typeof payload.endpoints === 'object'
    ? (payload.endpoints as Json)
    : {};

  return {
    ok: Boolean(payload.ok),
    nodeId: String(payload.node_id ?? ''),
    mode: String(payload.mode ?? ''),
    provisionState: String(payload.provision_state ?? ''),
    setupAp: {
      active: Boolean(setupApRaw.active),
      ssid: String(setupApRaw.ssid ?? ''),
      ip: String(setupApRaw.ip ?? ''),
      expiresInSec: toInt(setupApRaw.expires_in_sec),
    },
    sta: {
      configured: Boolean(staRaw.configured),
      connected: Boolean(staRaw.connected),
      ssid: String(staRaw.ssid ?? ''),
      ip: String(staRaw.ip ?? ''),
      rssi: staRaw.rssi == null ? null : toInt(staRaw.rssi),
      lastError: String(staRaw.last_error ?? ''),
      lastDisconnectReason: toInt(staRaw.last_disconnect_reason),
    },
    mdns: {
      enabled: Boolean(mdnsRaw.enabled),
      host: String(mdnsRaw.host ?? ''),
      ready: Boolean(mdnsRaw.ready),
    },
    endpoints: {
      stream: String(endpointsRaw.stream ?? ''),
      capture: String(endpointsRaw.capture ?? ''),
      control: String(endpointsRaw.control ?? ''),
    },
  };
}

export async function scanProvisionNetworks(baseUrl: string): Promise<ProvisionNetwork[]> {
  const payload = await fetchProvisionJson<Json>(baseUrl, '/api/provision/scan');
  const rawList = Array.isArray(payload.networks) ? payload.networks : [];
  return rawList.map((item) => {
    const row = item && typeof item === 'object' ? (item as Json) : {};
    return {
      ssid: String(row.ssid ?? ''),
      rssi: toInt(row.rssi),
      secure: Boolean(row.secure),
      channel: toInt(row.channel),
    };
  }).filter((row) => row.ssid.length > 0);
}

export async function submitProvisionWifi(
  baseUrl: string,
  input: { ssid: string; password: string; hostname: string; backendBase: string },
): Promise<ProvisionWifiResult> {
  const payload = await fetchProvisionJson<Json>(baseUrl, '/api/provision/wifi', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      ssid: input.ssid,
      password: input.password,
      hostname: input.hostname,
      backend_base: input.backendBase,
    }),
  });

  return {
    ok: Boolean(payload.ok),
    accepted: Boolean(payload.accepted),
    provisionState: String(payload.provision_state ?? ''),
    detail: String(payload.detail ?? ''),
  };
}

export async function resetProvisioning(baseUrl: string): Promise<ProvisionWifiResult> {
  const payload = await fetchProvisionJson<Json>(baseUrl, '/api/provision/reset', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ clear_wifi: true, clear_backend: true }),
  });

  return {
    ok: Boolean(payload.ok),
    accepted: Boolean(payload.accepted ?? true),
    provisionState: String(payload.provision_state ?? ''),
    detail: String(payload.detail ?? ''),
  };
}
