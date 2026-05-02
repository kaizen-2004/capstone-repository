#include <HTTPClient.h>
#include <DNSServer.h>
#include <Preferences.h>
#include <WebServer.h>
#include <WiFi.h>

#include <ctype.h>

#include "../common/network_config.h"

// Network values are shared across all node sketches.
// Edit firmware/http/common/network_config.h for hotspot/LAN changes.
static const char* WIFI_SSID = THESIS_WIFI_SSID;
static const char* WIFI_PASSWORD = THESIS_WIFI_PASSWORD;
static const char* WIFI_HOSTNAME = "smoke-node2";
static const char* BACKEND_BASE = THESIS_BACKEND_BASE;

// Node identity is intentionally per-sketch and must stay unique.
static const char* NODE_ID = "smoke_node2";
static const char* NODE_LABEL = "Smoke Sensor Node 2";
static const char* NODE_LOCATION = "Door Entrance Area";
static const char* NODE_TYPE = "smoke";
static const char* FIRMWARE_VERSION = "smoke_node2_http_v3_manual_wifi";

// Low TX power profile to reduce local RF noise around the analog smoke sensor.
#if defined(WIFI_POWER_8_5dBm)
#define WIFI_TX_POWER_CONNECT_INITIAL WIFI_POWER_8_5dBm
#elif defined(WIFI_POWER_11dBm)
#define WIFI_TX_POWER_CONNECT_INITIAL WIFI_POWER_11dBm
#elif defined(WIFI_POWER_13dBm)
#define WIFI_TX_POWER_CONNECT_INITIAL WIFI_POWER_13dBm
#endif

#if defined(WIFI_TX_POWER_CONNECT_INITIAL)
#define WIFI_TX_POWER_CONNECT_ESCALATED WIFI_TX_POWER_CONNECT_INITIAL
#endif

#if defined(WIFI_POWER_8_5dBm)
#define WIFI_TX_POWER_RUNTIME WIFI_POWER_8_5dBm
#elif defined(WIFI_POWER_11dBm)
#define WIFI_TX_POWER_RUNTIME WIFI_POWER_11dBm
#elif defined(WIFI_TX_POWER_CONNECT_INITIAL)
#define WIFI_TX_POWER_RUNTIME WIFI_TX_POWER_CONNECT_INITIAL
#endif

#if defined(WIFI_TX_POWER_CONNECT_INITIAL)
#define WIFI_TX_POWER_PROVISIONING WIFI_TX_POWER_CONNECT_INITIAL
#endif

// Connectivity/retry timing.
static const uint32_t WIFI_RETRY_INTERVAL_MS = 15000;
static const uint32_t WIFI_CONNECT_TIMEOUT_MS = 20000;
static const uint32_t REGISTER_RETRY_INTERVAL_MS = 10000;
static const uint32_t SMOKE_EVENT_RETRY_INTERVAL_MS = 1000;
static const uint8_t WIFI_ESCALATE_AFTER_ATTEMPTS = 2;

// Sensor and heartbeat timing.
static const uint32_t HEARTBEAT_INTERVAL_MS = 15000;
static const uint32_t SENSOR_REPORT_INTERVAL_MS = 200;
static const uint32_t WIFI_PROVISIONING_FALLBACK_MS = 30000;
static const uint32_t PROVISIONING_SUCCESS_HOLD_MS = 30000;
static const uint32_t PROVISIONING_CONNECT_DELAY_MS = 1500;

static const int MQ2_ADC_PIN = 0;
static const int BUZZER_PIN = 5;
static const int ADC_RESOLUTION = 4095;
static const float ESP32_ADC_MAX_VOLTAGE = 3.3f;
static const float DIVIDER_MULTIPLIER = 1.5f;
static const int MQ2_ADC_SAMPLES = 10;
static const uint32_t MQ2_ADC_SAMPLE_DELAY_MS = 2;
static const int SMOKE_WARNING_THRESHOLD = 80;
static const int SMOKE_HIGH_THRESHOLD = 120;
static const uint8_t MQ2_CLEAR_CONFIRM_SAMPLES = 5;
static const uint32_t MQ2_WARMUP_MS = 0;
static const uint32_t BUZZER_HIGH_ON_MS = 150;
static const uint32_t BUZZER_HIGH_OFF_MS = 150;
static const uint32_t BUZZER_WARNING_ON_MS = 100;
static const uint32_t BUZZER_WARNING_OFF_MS = 600;

enum SmokeStatus {
  SMOKE_STATUS_NORMAL = 0,
  SMOKE_STATUS_WARNING,
  SMOKE_STATUS_HIGH,
};

struct Mq2Reading {
  int avgRaw;
  int minRaw;
  int maxRaw;
  float espVoltage;
  float mq2A0Voltage;
};

static const char* PROVISIONING_AP_PREFIX = "Thesis-Setup";
static const char* PROVISIONING_AP_PASSWORD = "12345678";
static const byte PROVISIONING_DNS_PORT = 53;
static const uint8_t PROVISIONING_AP_CHANNEL = 1;
static const uint8_t PROVISIONING_AP_MAX_CLIENTS = 4;
static const char* PROVISIONING_SETUP_IP = "192.168.4.1";
static const IPAddress PROVISIONING_AP_IP(192, 168, 4, 1);
static const IPAddress PROVISIONING_AP_GATEWAY(192, 168, 4, 1);
static const IPAddress PROVISIONING_AP_SUBNET(255, 255, 255, 0);

static const char* PROVISION_PREFS_NAMESPACE = "nodeprov";
static const char* PROVISION_PREFS_SSID_KEY = "wifi_ssid";
static const char* PROVISION_PREFS_PASSWORD_KEY = "wifi_pass";
static const char* PROVISION_PREFS_BACKEND_KEY = "backend";
static const char* PROVISION_PREFS_NODE_ID_KEY = "node_id";
static const char* PROVISION_PREFS_ROOM_KEY = "room";

enum ProvisionState {
  PROVISION_UNCONFIGURED = 0,
  PROVISION_CONNECTING,
  PROVISION_CONNECTED,
  PROVISION_CONNECT_FAILED,
};

String provisionStateText();
void beginWiFiConnection(bool resetBeforeBegin = false);

ProvisionState provisionState = PROVISION_UNCONFIGURED;

String runtimeWiFiSsid;
String runtimeWiFiPassword;
String runtimeHostname;
String runtimeBackendBase;
String runtimeNodeId;
String runtimeNodeLocation;
String lastProvisionError;
String provisioningFailureReason = "none";

uint32_t lastHeartbeatMs = 0;
uint32_t lastReadingMs = 0;
uint32_t lastWiFiAttemptMs = 0;
uint32_t lastWiFiBeginMs = 0;
uint32_t wifiConnectWindowStartedAt = 0;
uint32_t lastRegisterAttemptMs = 0;
uint32_t lastWiFiStatusLogMs = 0;
uint32_t provisioningConnectEarliestAt = 0;
uint32_t provisioningSuccessAt = 0;
uint32_t lastSmokeEventAttemptMs = 0;
uint8_t wifiConnectAttempts = 0;
uint8_t lastDisconnectReason = 0;
bool provisioningConnectRequested = false;
bool wasWiFiConnected = false;
bool registrationOk = false;
bool setupApActive = false;
bool provisioningRoutesRegistered = false;
bool provisioningServerStarted = false;
bool hasPreferredWiFiBssid = false;
bool smokeLatched = false;
bool buzzerOutputHigh = false;
uint8_t smokeClearConfirmCount = 0;
uint8_t preferredWiFiBssid[6] = {0, 0, 0, 0, 0, 0};
int32_t preferredWiFiChannel = 0;
uint32_t sensorWarmupUntilMs = 0;
uint32_t lastBuzzerToggleMs = 0;
String setupApSsid;
SmokeStatus currentSmokeStatus = SMOKE_STATUS_NORMAL;
SmokeStatus buzzerPatternStatus = SMOKE_STATUS_NORMAL;
SmokeStatus notifiedSmokeStatus = SMOKE_STATUS_NORMAL;

WebServer provisioningServer(80);
DNSServer provisioningDnsServer;

String sanitizeHostname(const String& raw) {
  String out;
  out.reserve(raw.length());
  for (size_t i = 0; i < raw.length(); ++i) {
    char c = raw.charAt(i);
    if (isalnum(static_cast<unsigned char>(c))) {
      out += static_cast<char>(tolower(c));
    } else if (c == '-' || c == '_') {
      out += '-';
    }
  }
  while (out.startsWith("-")) {
    out.remove(0, 1);
  }
  while (out.endsWith("-")) {
    out.remove(out.length() - 1);
  }
  if (out.length() == 0) {
    return "smoke-node2";
  }
  if (out.length() > 31) {
    out = out.substring(0, 31);
  }
  return out;
}

bool isConfiguredValue(const String& valueRaw) {
  String value = valueRaw;
  value.trim();
  if (value.length() == 0) {
    return false;
  }

  String lower = value;
  lower.toLowerCase();
  return !(lower == "changeme" || lower == "none" || lower == "null");
}

bool isLocalOnlyBackendTarget(const String& valueRaw) {
  String value = valueRaw;
  value.trim();
  if (value.length() == 0) {
    return false;
  }

  String lower = value;
  lower.toLowerCase();
  return lower.indexOf("://127.0.0.1") >= 0 ||
         lower.indexOf("://localhost") >= 0 ||
         lower.indexOf("://0.0.0.0") >= 0 ||
         lower.startsWith("127.0.0.1") ||
         lower.startsWith("localhost") ||
         lower.startsWith("0.0.0.0");
}

String sanitizeBackendBase(const String& baseRaw) {
  String base = baseRaw;
  base.trim();
  if (base.length() == 0) {
    return "";
  }
  if (isLocalOnlyBackendTarget(base)) {
    Serial.printf("[PROV] ignoring local-only backend_base=%s\n", base.c_str());
    return "";
  }
  if (base.endsWith("/")) {
    base.remove(base.length() - 1);
  }
  return base;
}

String jsonEscape(const String& input) {
  String out;
  out.reserve(input.length() + 8);
  for (size_t i = 0; i < input.length(); ++i) {
    char c = input.charAt(i);
    if (c == '"' || c == '\\') {
      out += '\\';
      out += c;
    } else if (c == '\n') {
      out += "\\n";
    } else if (c == '\r') {
      out += "\\r";
    } else {
      out += c;
    }
  }
  return out;
}

bool extractJsonStringField(const String& json, const char* fieldName, String& outValue) {
  String needle = String("\"") + fieldName + "\"";
  int keyStart = json.indexOf(needle);
  if (keyStart < 0) {
    return false;
  }

  int colon = json.indexOf(':', keyStart + needle.length());
  if (colon < 0) {
    return false;
  }

  int valueStart = json.indexOf('"', colon + 1);
  if (valueStart < 0) {
    return false;
  }

  String value;
  bool escaping = false;
  for (int i = valueStart + 1; i < json.length(); ++i) {
    char c = json.charAt(i);
    if (escaping) {
      value += c;
      escaping = false;
      continue;
    }
    if (c == '\\') {
      escaping = true;
      continue;
    }
    if (c == '"') {
      outValue = value;
      return true;
    }
    value += c;
  }
  return false;
}

bool extractJsonIntField(const String& json, const char* fieldName, int& outValue) {
  String needle = String("\"") + fieldName + "\"";
  int keyStart = json.indexOf(needle);
  if (keyStart < 0) {
    return false;
  }
  int colon = json.indexOf(':', keyStart + needle.length());
  if (colon < 0) {
    return false;
  }

  int i = colon + 1;
  while (i < json.length() && isspace(static_cast<unsigned char>(json.charAt(i)))) {
    ++i;
  }
  if (i >= json.length()) {
    return false;
  }

  int sign = 1;
  if (json.charAt(i) == '-') {
    sign = -1;
    ++i;
  }
  if (i >= json.length() || !isdigit(static_cast<unsigned char>(json.charAt(i)))) {
    return false;
  }

  int value = 0;
  while (i < json.length() && isdigit(static_cast<unsigned char>(json.charAt(i)))) {
    value = (value * 10) + (json.charAt(i) - '0');
    ++i;
  }

  outValue = value * sign;
  return true;
}

void setProvisioningCorsHeaders() {
  provisioningServer.sendHeader("Access-Control-Allow-Origin", "*");
  provisioningServer.sendHeader("Access-Control-Allow-Methods", "GET,POST,OPTIONS");
  provisioningServer.sendHeader("Access-Control-Allow-Headers", "Content-Type");
}

void sendProvisioningJsonResponse(int statusCode, const String& payload) {
  setProvisioningCorsHeaders();
  provisioningServer.send(statusCode, "application/json", payload);
}

bool saveProvisioningConfig(
    const String& wifiSsid,
    const String& wifiPassword,
    const String& backendBase,
    const String& nodeId,
    const String& roomName) {
  Preferences prefs;
  if (!prefs.begin(PROVISION_PREFS_NAMESPACE, false)) {
    return false;
  }
  bool ok = true;
  ok = ok && (prefs.putString(PROVISION_PREFS_SSID_KEY, wifiSsid) > 0);
  ok = ok && (prefs.putString(PROVISION_PREFS_PASSWORD_KEY, wifiPassword) >= 0);
  ok = ok && (prefs.putString(PROVISION_PREFS_BACKEND_KEY, backendBase) > 0);
  ok = ok && (prefs.putString(PROVISION_PREFS_NODE_ID_KEY, nodeId) > 0);
  ok = ok && (prefs.putString(PROVISION_PREFS_ROOM_KEY, roomName) > 0);
  prefs.end();

  if (!ok) {
    return false;
  }

  runtimeWiFiSsid = wifiSsid;
  runtimeWiFiPassword = wifiPassword;
  runtimeBackendBase = backendBase;
  runtimeNodeId = nodeId;
  runtimeNodeLocation = roomName;
  return true;
}

void clearProvisioningConfig() {
  Preferences prefs;
  if (prefs.begin(PROVISION_PREFS_NAMESPACE, false)) {
    prefs.remove(PROVISION_PREFS_SSID_KEY);
    prefs.remove(PROVISION_PREFS_PASSWORD_KEY);
    prefs.remove(PROVISION_PREFS_BACKEND_KEY);
    prefs.remove(PROVISION_PREFS_NODE_ID_KEY);
    prefs.remove(PROVISION_PREFS_ROOM_KEY);
    prefs.end();
  }

  runtimeWiFiSsid = String(WIFI_SSID);
  runtimeWiFiPassword = String(WIFI_PASSWORD);
  runtimeBackendBase = sanitizeBackendBase(String(BACKEND_BASE));
  runtimeNodeId = String(NODE_ID);
  runtimeNodeLocation = String(NODE_LOCATION);

  hasPreferredWiFiBssid = false;
  preferredWiFiChannel = 0;
}

void scanAndLogTargetSSID() {
  WiFi.mode(setupApActive ? WIFI_AP_STA : WIFI_STA);
  int16_t found = WiFi.scanNetworks(false, true);
  if (found < 0) {
    hasPreferredWiFiBssid = false;
    preferredWiFiChannel = 0;
    Serial.printf("[WiFi] scan failed code=%d\n", static_cast<int>(found));
    return;
  }

  hasPreferredWiFiBssid = false;
  preferredWiFiChannel = 0;
  int16_t bestRssi = -127;
  uint8_t bssidBuf[6] = {0, 0, 0, 0, 0, 0};

  Serial.printf("[WiFi] scan found %d AP(s)\n", static_cast<int>(found));
  for (int16_t i = 0; i < found; ++i) {
    String ssid = WiFi.SSID(i);
    if (ssid != runtimeWiFiSsid) {
      continue;
    }

    int32_t rssi = WiFi.RSSI(i);
    int32_t channel = WiFi.channel(i);
    if (!hasPreferredWiFiBssid || rssi > bestRssi) {
      bestRssi = static_cast<int16_t>(rssi);
      preferredWiFiChannel = channel > 0 ? channel : 0;
      uint8_t* bssid = WiFi.BSSID(i, bssidBuf);
      if (bssid) {
        for (uint8_t j = 0; j < 6; ++j) {
          preferredWiFiBssid[j] = bssid[j];
        }
        hasPreferredWiFiBssid = true;
      }
    }
  }
  WiFi.scanDelete();
}

String provisioningApName() {
  uint64_t chipId = ESP.getEfuseMac();
  uint32_t suffix = static_cast<uint32_t>(chipId & 0xFFFFFF);
  char buf[48];
  const char* nodeAlias = strcmp(NODE_ID, "smoke_node2") == 0 ? "smoke2" : "smoke1";
  snprintf(
      buf,
      sizeof(buf),
      "%s-%s-%06X",
      PROVISIONING_AP_PREFIX,
      nodeAlias,
      static_cast<unsigned>(suffix));
  return String(buf);
}

void startSetupApMode(const char* reason) {
  provisioningConnectRequested = false;
  provisioningConnectEarliestAt = 0;
  provisioningSuccessAt = 0;
  wifiConnectWindowStartedAt = 0;
  lastWiFiBeginMs = 0;
  provisionState = PROVISION_UNCONFIGURED;
  provisioningFailureReason =
      (reason != nullptr && strlen(reason) > 0) ? String(reason) : String("none");
  lastProvisionError = provisioningFailureReason;

  if (setupApActive) {
    return;
  }

  WiFi.setAutoReconnect(false);
  WiFi.disconnect(true, false);
  WiFi.mode(WIFI_AP);
  delay(120);
  WiFi.setSleep(false);
#if defined(WIFI_TX_POWER_PROVISIONING)
  WiFi.setTxPower(WIFI_TX_POWER_PROVISIONING);
#endif
  if (!WiFi.softAPConfig(PROVISIONING_AP_IP, PROVISIONING_AP_GATEWAY, PROVISIONING_AP_SUBNET)) {
    Serial.println("[PROV] setup AP static IP config failed");
  }
  setupApSsid = provisioningApName();
  if (!WiFi.softAP(setupApSsid.c_str(), PROVISIONING_AP_PASSWORD, PROVISIONING_AP_CHANNEL, false, PROVISIONING_AP_MAX_CLIENTS)) {
    Serial.println("[PROV] failed to start setup AP");
    return;
  }

  setupApActive = true;
  provisioningDnsServer.start(PROVISIONING_DNS_PORT, "*", PROVISIONING_AP_IP);
  Serial.printf("[PROV] setup AP active ssid=%s password=%s ip=%s channel=%u mac=%s\n",
                setupApSsid.c_str(),
                PROVISIONING_AP_PASSWORD,
                WiFi.softAPIP().toString().c_str(),
                static_cast<unsigned>(PROVISIONING_AP_CHANNEL),
                WiFi.softAPmacAddress().c_str());
}

void stopSetupApMode() {
  if (!setupApActive) {
    return;
  }
  provisioningDnsServer.stop();
  WiFi.softAPdisconnect(true);
  WiFi.mode(WIFI_STA);
  setupApActive = false;
  setupApSsid = "";
  provisioningConnectRequested = false;
  provisioningConnectEarliestAt = 0;
  provisioningSuccessAt = 0;
  provisioningFailureReason = "none";
}

bool isAllowedNodeRole(const String& roleRaw) {
  String role = roleRaw;
  role.trim();
  role.toLowerCase();
  return role == "smoke_node2" || role == "smoke";
}

bool isAllowedNodeId(const String& nodeIdRaw) {
  String nodeId = nodeIdRaw;
  nodeId.trim();
  nodeId.toLowerCase();
  return nodeId == "smoke_node1" || nodeId == "smoke_node2";
}

bool isAllowedRoomName(const String& roomRaw) {
  String room = roomRaw;
  room.trim();
  room.toLowerCase();
  return room == "living room" ||
         room == "door entrance area" ||
         room == "kitchen" ||
         room == "hallway";
}

String provisioningPortalHtml() {
  String html;
  html.reserve(6200);
  html += "<!doctype html><html><head><meta charset='utf-8'>";
  html += "<meta name='viewport' content='width=device-width,initial-scale=1'>";
  html += "<title>Smoke Node Setup</title>";
  html += "<style>body{font-family:Arial,sans-serif;background:#f2f4f8;margin:0;padding:16px;}";
  html += ".card{max-width:460px;margin:20px auto;background:#fff;border-radius:10px;padding:18px;box-shadow:0 2px 14px rgba(0,0,0,.08);}";
  html += "h2{margin:0 0 12px;font-size:20px;}label{display:block;font-weight:600;margin:10px 0 6px;}";
  html += "input,select,button{width:100%;box-sizing:border-box;padding:10px;border:1px solid #c9ced6;border-radius:8px;font-size:14px;}";
  html += "button{margin-top:14px;background:#0a7cff;color:#fff;border:none;font-weight:700;}";
  html += "#msg{margin-top:10px;font-size:13px;white-space:pre-wrap;}small{color:#666;display:block;margin-top:10px;}";
  html += "</style></head><body><div class='card'>";
  html += "<h2>Smoke Node Provisioning</h2>";
  html += "<label for='ssid'>WiFi SSID</label><input id='ssid' autocomplete='off'>";
  html += "<label for='pass'>WiFi Password</label><input id='pass' type='password' autocomplete='off'>";
  html += "<label for='backend'>Backend Host/IP</label><input id='backend' value='192.168.1.8' autocomplete='off'>";
  html += "<label for='port'>Backend Port</label><input id='port' type='number' value='8765' min='1' max='65535'>";
  html += "<label for='node'>Node ID</label><select id='node'>";
  html += "<option value='smoke_node1'";
  if (runtimeNodeId == "smoke_node1") {
    html += " selected";
  }
  html += ">smoke_node1</option>";
  html += "<option value='smoke_node2'";
  if (runtimeNodeId == "smoke_node2") {
    html += " selected";
  }
  html += ">smoke_node2</option></select>";
  html += "<label for='room'>Room Name</label><select id='room'>";
  html += "<option value='Living Room'";
  if (runtimeNodeLocation == "Living Room") {
    html += " selected";
  }
  html += ">Living Room</option>";
  html += "<option value='Door Entrance Area'";
  if (runtimeNodeLocation == "Door Entrance Area") {
    html += " selected";
  }
  html += ">Door Entrance Area</option>";
  html += "<option value='Kitchen'";
  if (runtimeNodeLocation == "Kitchen") {
    html += " selected";
  }
  html += ">Kitchen</option>";
  html += "<option value='Hallway'";
  if (runtimeNodeLocation == "Hallway") {
    html += " selected";
  }
  html += ">Hallway</option></select>";
  html += "<button onclick='submitConfig()'>Save and Connect</button><div id='msg'></div>";
  html += "<small>If captive portal does not auto-open, browse to http://";
  html += PROVISIONING_SETUP_IP;
  html += "</small></div><script>";
  html += "const msg=document.getElementById('msg');";
  html += "function show(t,c){msg.textContent=t;msg.style.color=c||'#333';}";
  html += "async function submitConfig(){";
  html += "const payload={wifi_ssid:document.getElementById('ssid').value.trim(),wifi_password:document.getElementById('pass').value,backend_host:document.getElementById('backend').value.trim(),backend_port:parseInt(document.getElementById('port').value||'0',10),node_id:document.getElementById('node').value,node_role:'smoke',room_name:document.getElementById('room').value};";
  html += "if(!payload.wifi_ssid||!payload.backend_host||!payload.backend_port){show('Please fill SSID, backend host, and port.','#b00020');return;}";
  html += "show('Saving configuration...');";
  html += "try{const r=await fetch('/api/provisioning/configure',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const j=await r.json();if(r.ok&&j.ok){show('Saved. Device is connecting to WiFi...','#0a7a0a');}else{show('Failed: '+(j.error||'unknown_error'),'#b00020');}}catch(e){show('Request failed: '+e,'#b00020');}}";
  html += "</script></body></html>";
  return html;
}

void ensureProvisioningRoutes() {
  if (provisioningRoutesRegistered) {
    return;
  }

  auto handleOptions = []() {
    setProvisioningCorsHeaders();
    provisioningServer.send(204, "text/plain", "");
  };

  auto currentNetworkIp = []() {
    if (WiFi.status() == WL_CONNECTED) {
      return WiFi.localIP().toString();
    }
    if (setupApActive) {
      return WiFi.softAPIP().toString();
    }
    return String("0.0.0.0");
  };

  auto buildStatusJson = [currentNetworkIp]() {
    String json = "{";
    json += "\"ok\":true,";
    json += "\"state\":\"" + jsonEscape(provisionStateText()) + "\",";
    json += "\"failure_reason\":\"" + jsonEscape(provisioningFailureReason) + "\",";
    json += "\"setup_ap\":" + String(setupApActive ? "true" : "false") + ",";
    json += "\"setup_ssid\":\"" + jsonEscape(setupApSsid) + "\",";
    json += "\"wifi_connected\":" + String(WiFi.status() == WL_CONNECTED ? "true" : "false") + ",";
    json += "\"ssid\":\"" + jsonEscape(runtimeWiFiSsid) + "\",";
    json += "\"ip\":\"" + jsonEscape(currentNetworkIp()) + "\"";
    json += "}";
    return json;
  };

  auto buildProvisioningInfoJson = []() {
    String json = "{";
    json += "\"device_name\":\"" + jsonEscape(String(NODE_LABEL)) + "\",";
    json += "\"node_id\":\"" + jsonEscape(runtimeNodeId) + "\",";
    json += "\"mode\":\"" + String(setupApActive ? "provisioning" : "normal") + "\",";
    json += "\"ap_ssid\":\"" + jsonEscape(setupApSsid) + "\",";
    json += "\"setup_ip\":\"192.168.4.1\",";
    json += "\"firmware_version\":\"" + jsonEscape(String(FIRMWARE_VERSION)) + "\",";
    json += "\"status\":\"" + jsonEscape(provisionStateText()) + "\"";
    json += "}";
    return json;
  };

  auto buildProvisioningResultJson = []() {
    String json = "{";
    json += "\"state\":\"" + jsonEscape(provisionStateText()) + "\"";
    if (provisioningFailureReason.length() > 0 && provisioningFailureReason != "none") {
      json += ",\"reason\":\"" + jsonEscape(provisioningFailureReason) + "\"";
    }
    if (WiFi.status() == WL_CONNECTED) {
      json += ",\"ip\":\"" + WiFi.localIP().toString() + "\"";
      json += ",\"ssid\":\"" + jsonEscape(runtimeWiFiSsid) + "\"";
    }
    json += "}";
    return json;
  };

  auto handleConfigure = []() {
    if (!setupApActive) {
      sendProvisioningJsonResponse(409, "{\"ok\":false,\"error\":\"setup_ap_inactive\"}");
      return;
    }

    String body = provisioningServer.arg("plain");
    String wifiSsid;
    String wifiPassword;
    String backendHost;
    String nodeId;
    String nodeRole;
    String roomName;
    int backendPort = 0;

    bool hasRequired =
        extractJsonStringField(body, "wifi_ssid", wifiSsid) &&
        extractJsonStringField(body, "wifi_password", wifiPassword) &&
        extractJsonStringField(body, "backend_host", backendHost) &&
        extractJsonIntField(body, "backend_port", backendPort) &&
        extractJsonStringField(body, "node_id", nodeId) &&
        extractJsonStringField(body, "node_role", nodeRole) &&
        extractJsonStringField(body, "room_name", roomName);

    if (!hasRequired) {
      sendProvisioningJsonResponse(400, "{\"ok\":false,\"error\":\"invalid_payload\"}");
      return;
    }

    wifiSsid.trim();
    backendHost.trim();
    nodeId.trim();
    roomName.trim();
    if (wifiSsid.length() == 0 || backendHost.length() == 0 || nodeId.length() == 0 ||
        roomName.length() == 0 || backendPort <= 0 || backendPort > 65535) {
      sendProvisioningJsonResponse(400, "{\"ok\":false,\"error\":\"invalid_payload\"}");
      return;
    }

    if (!isAllowedNodeRole(nodeRole)) {
      sendProvisioningJsonResponse(400, "{\"ok\":false,\"error\":\"invalid_node_role\"}");
      return;
    }
    if (!isAllowedNodeId(nodeId)) {
      sendProvisioningJsonResponse(400, "{\"ok\":false,\"error\":\"invalid_node_id\"}");
      return;
    }
    if (!isAllowedRoomName(roomName)) {
      sendProvisioningJsonResponse(400, "{\"ok\":false,\"error\":\"invalid_room_name\"}");
      return;
    }

    String backendBase = sanitizeBackendBase(
        String("http://") + backendHost + ":" + String(backendPort));
    if (backendBase.length() == 0) {
      sendProvisioningJsonResponse(400, "{\"ok\":false,\"error\":\"invalid_backend_host\"}");
      return;
    }

    if (!saveProvisioningConfig(wifiSsid, wifiPassword, backendBase, nodeId, roomName)) {
      sendProvisioningJsonResponse(500, "{\"ok\":false,\"error\":\"storage_error\"}");
      return;
    }

    provisionState = PROVISION_CONNECTING;
    provisioningFailureReason = "none";
    lastProvisionError = "";
    wifiConnectAttempts = 0;
    lastWiFiAttemptMs = 0;
    lastWiFiBeginMs = 0;
    provisioningConnectRequested = true;
    provisioningConnectEarliestAt = millis() + PROVISIONING_CONNECT_DELAY_MS;
    provisioningSuccessAt = 0;
    hasPreferredWiFiBssid = false;
    preferredWiFiChannel = 0;

    sendProvisioningJsonResponse(
        202,
        String("{\"ok\":true,\"accepted\":true,\"message\":\"configuration_saved\",\"node_id\":\"") +
            jsonEscape(runtimeNodeId) + "\"}");
  };

  auto handleResetWiFi = []() {
    String body = provisioningServer.arg("plain");
    if (body.indexOf("\"confirm\":true") < 0) {
      sendProvisioningJsonResponse(400, "{\"ok\":false,\"error\":\"confirmation_required\"}");
      return;
    }

    sendProvisioningJsonResponse(202, "{\"ok\":true,\"accepted\":true,\"message\":\"wifi_reset_requested\"}");
    delay(200);
    clearProvisioningConfig();
    startSetupApMode("wifi_reset");
  };

  provisioningServer.on("/", HTTP_GET, []() {
    provisioningServer.sendHeader("Cache-Control", "no-cache, no-store, must-revalidate");
    provisioningServer.sendHeader("Pragma", "no-cache");
    provisioningServer.send(200, "text/html", provisioningPortalHtml());
  });
  provisioningServer.on("/", HTTP_OPTIONS, handleOptions);

  provisioningServer.on("/configure", HTTP_OPTIONS, handleOptions);
  provisioningServer.on("/configure", HTTP_POST, handleConfigure);

  provisioningServer.on("/api/provisioning/configure", HTTP_OPTIONS, handleOptions);
  provisioningServer.on("/api/provisioning/configure", HTTP_POST, handleConfigure);

  provisioningServer.on("/status", HTTP_GET, [buildStatusJson]() {
    sendProvisioningJsonResponse(200, buildStatusJson());
  });
  provisioningServer.on("/status", HTTP_OPTIONS, handleOptions);

  provisioningServer.on("/api/status", HTTP_GET, [buildStatusJson]() {
    sendProvisioningJsonResponse(200, buildStatusJson());
  });
  provisioningServer.on("/api/status", HTTP_OPTIONS, handleOptions);

  provisioningServer.on("/api/provisioning/info", HTTP_GET, [buildProvisioningInfoJson]() {
    sendProvisioningJsonResponse(200, buildProvisioningInfoJson());
  });
  provisioningServer.on("/api/provisioning/info", HTTP_OPTIONS, handleOptions);

  provisioningServer.on("/api/provisioning/result", HTTP_GET, [buildProvisioningResultJson]() {
    sendProvisioningJsonResponse(200, buildProvisioningResultJson());
  });
  provisioningServer.on("/api/provisioning/result", HTTP_OPTIONS, handleOptions);

  provisioningServer.on("/api/device/reset-wifi", HTTP_POST, handleResetWiFi);
  provisioningServer.on("/api/device/reset-wifi", HTTP_OPTIONS, handleOptions);

  provisioningServer.on("/health", HTTP_GET, []() {
    sendProvisioningJsonResponse(200, "{\"ok\":true,\"status\":\"online\"}");
  });
  provisioningServer.on("/health", HTTP_OPTIONS, handleOptions);

  provisioningServer.on("/healthz", HTTP_GET, []() {
    sendProvisioningJsonResponse(200, "{\"ok\":true,\"status\":\"online\"}");
  });
  provisioningServer.on("/healthz", HTTP_OPTIONS, handleOptions);

  provisioningServer.onNotFound([]() {
    if (setupApActive) {
      provisioningServer.sendHeader("Location", String("http://") + PROVISIONING_SETUP_IP);
      provisioningServer.send(302, "text/plain", "Redirecting to setup portal");
      return;
    }
    sendProvisioningJsonResponse(404, "{\"ok\":false,\"error\":\"not_found\"}");
  });

  provisioningRoutesRegistered = true;
}

void ensureProvisioningServerState() {
  bool shouldRun = setupApActive || WiFi.status() == WL_CONNECTED;
  if (shouldRun && !provisioningServerStarted) {
    ensureProvisioningRoutes();
    provisioningServer.begin();
    provisioningServerStarted = true;
  } else if (!shouldRun && provisioningServerStarted) {
    provisioningServer.stop();
    provisioningServerStarted = false;
  }
}

const char* wifiStatusText(wl_status_t s) {
  switch (s) {
    case WL_IDLE_STATUS:
      return "IDLE";
    case WL_NO_SSID_AVAIL:
      return "NO_SSID";
    case WL_SCAN_COMPLETED:
      return "SCAN_DONE";
    case WL_CONNECTED:
      return "CONNECTED";
    case WL_CONNECT_FAILED:
      return "CONNECT_FAILED";
    case WL_CONNECTION_LOST:
      return "CONNECTION_LOST";
    case WL_DISCONNECTED:
      return "DISCONNECTED";
    default:
      return "UNKNOWN";
  }
}

String provisionStateText() {
  switch (provisionState) {
    case PROVISION_UNCONFIGURED:
      return "unconfigured";
    case PROVISION_CONNECTING:
      return "connecting";
    case PROVISION_CONNECTED:
      return "connected";
    case PROVISION_CONNECT_FAILED:
      return "connect_failed";
    default:
      return "unknown";
  }
}

bool hasRuntimeWiFiConfig() {
  return isConfiguredValue(runtimeWiFiSsid);
}

bool backendEnabled() {
  return runtimeBackendBase.length() > 0;
}

String endpoint(const char* path) {
  if (!backendEnabled()) {
    return "";
  }
  return runtimeBackendBase + String(path);
}

void loadRuntimeConfigFromStorage() {
  runtimeWiFiSsid = String(WIFI_SSID);
  runtimeWiFiPassword = String(WIFI_PASSWORD);
  runtimeHostname = sanitizeHostname(String(WIFI_HOSTNAME));
  runtimeBackendBase = sanitizeBackendBase(String(BACKEND_BASE));
  runtimeNodeId = String(NODE_ID);
  runtimeNodeLocation = String(NODE_LOCATION);

  Preferences prefs;
  if (!prefs.begin(PROVISION_PREFS_NAMESPACE, true)) {
    return;
  }

  String storedSsid = prefs.getString(PROVISION_PREFS_SSID_KEY, "");
  String storedPassword = prefs.getString(PROVISION_PREFS_PASSWORD_KEY, "");
  String storedBackend = prefs.getString(PROVISION_PREFS_BACKEND_KEY, "");
  String storedNodeId = prefs.getString(PROVISION_PREFS_NODE_ID_KEY, "");
  String storedRoom = prefs.getString(PROVISION_PREFS_ROOM_KEY, "");
  prefs.end();

  if (isConfiguredValue(storedSsid)) {
    runtimeWiFiSsid = storedSsid;
    runtimeWiFiPassword = storedPassword;
  }

  String sanitizedBackend = sanitizeBackendBase(storedBackend);
  if (isConfiguredValue(sanitizedBackend)) {
    runtimeBackendBase = sanitizedBackend;
  }
  if (isConfiguredValue(storedNodeId)) {
    runtimeNodeId = storedNodeId;
  }
  if (isConfiguredValue(storedRoom)) {
    runtimeNodeLocation = storedRoom;
  }
}

#if defined(WIFI_TX_POWER_CONNECT_INITIAL) && defined(WIFI_TX_POWER_CONNECT_ESCALATED)
wifi_power_t currentConnectTxPower() {
  if (wifiConnectAttempts >= WIFI_ESCALATE_AFTER_ATTEMPTS) {
    return WIFI_TX_POWER_CONNECT_ESCALATED;
  }
  return WIFI_TX_POWER_CONNECT_INITIAL;
}
#endif

void beginWiFiConnection(bool resetBeforeBegin) {
  if (!hasRuntimeWiFiConfig()) {
    return;
  }

  if (resetBeforeBegin) {
    WiFi.setAutoReconnect(false);
    WiFi.disconnect(false, false);
    WiFi.mode(setupApActive ? WIFI_AP : WIFI_OFF);
    delay(120);
  }

  WiFi.mode(setupApActive ? WIFI_AP_STA : WIFI_STA);
  WiFi.setSleep(false);
  WiFi.setAutoReconnect(true);
  WiFi.persistent(false);
  WiFi.setHostname(sanitizeHostname(runtimeHostname).c_str());
#if defined(WIFI_TX_POWER_CONNECT_INITIAL) && defined(WIFI_TX_POWER_CONNECT_ESCALATED)
  WiFi.setTxPower(currentConnectTxPower());
#endif

  if (hasPreferredWiFiBssid && preferredWiFiChannel > 0) {
    WiFi.begin(runtimeWiFiSsid.c_str(), runtimeWiFiPassword.c_str(),
               preferredWiFiChannel, preferredWiFiBssid, true);
  } else {
    WiFi.begin(runtimeWiFiSsid.c_str(), runtimeWiFiPassword.c_str());
  }

  lastWiFiBeginMs = millis();
  lastWiFiAttemptMs = lastWiFiBeginMs;
  provisionState = PROVISION_CONNECTING;
  bool escalated = wifiConnectAttempts >= WIFI_ESCALATE_AFTER_ATTEMPTS;
  Serial.printf("[WiFi] connecting ssid=%s tx=%s attempt=%u\n",
                runtimeWiFiSsid.c_str(),
                escalated ? "escalated" : "initial",
                static_cast<unsigned>(wifiConnectAttempts + 1));
}

void connectWiFiBlocking() {
  if (!hasRuntimeWiFiConfig()) {
    Serial.println("[WiFi] no configured credentials; starting setup AP");
    startSetupApMode("no_credentials");
    return;
  }

  wifiConnectWindowStartedAt = millis();
  scanAndLogTargetSSID();
  beginWiFiConnection(false);
  uint32_t startedAt = millis();
  while (WiFi.status() != WL_CONNECTED &&
         (millis() - startedAt) < WIFI_CONNECT_TIMEOUT_MS) {
    ensureProvisioningServerState();
    if (provisioningServerStarted) {
      if (setupApActive) {
        provisioningDnsServer.processNextRequest();
      }
      provisioningServer.handleClient();
    }
    delay(250);
    Serial.print('.');
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    provisionState = PROVISION_CONNECTED;
    provisioningFailureReason = "none";
    lastProvisionError = "";
    wifiConnectWindowStartedAt = 0;
    return;
  }

  provisionState = PROVISION_CONNECT_FAILED;
  provisioningFailureReason = "wifi_initial_connect_failed";
  lastProvisionError = provisioningFailureReason;
  startSetupApMode("wifi_initial_connect_failed");
}

void maintainWiFiConnection() {
  if (setupApActive) {
    if (!provisioningConnectRequested) {
      return;
    }
    if ((int32_t)(millis() - provisioningConnectEarliestAt) < 0) {
      return;
    }

    if (lastWiFiBeginMs == 0) {
      Serial.printf("[PROV] connect attempt ssid=%s\n", runtimeWiFiSsid.c_str());
      scanAndLogTargetSSID();
      beginWiFiConnection(true);
      return;
    }

    wl_status_t status = WiFi.status();
    if (status == WL_CONNECTED) {
      provisioningConnectRequested = false;
      provisionState = PROVISION_CONNECTED;
      provisioningFailureReason = "none";
      lastProvisionError = "";
      if (provisioningSuccessAt == 0) {
        provisioningSuccessAt = millis();
      }
      return;
    }

    if ((uint32_t)(millis() - lastWiFiBeginMs) >= WIFI_CONNECT_TIMEOUT_MS) {
      provisioningConnectRequested = false;
      provisionState = PROVISION_CONNECT_FAILED;
      provisioningFailureReason =
          (status == WL_NO_SSID_AVAIL) ? "ssid_not_found" :
          (status == WL_CONNECT_FAILED) ? "auth_failed" : "connect_timeout";
      lastProvisionError = provisioningFailureReason;
      lastWiFiBeginMs = 0;
      provisioningConnectEarliestAt = 0;
      WiFi.disconnect(false, false);
      WiFi.mode(WIFI_AP);
    }
    return;
  }

  if (!hasRuntimeWiFiConfig()) {
    return;
  }

  uint32_t now = millis();
  wl_status_t status = WiFi.status();
  if (status == WL_CONNECTED) {
    wifiConnectWindowStartedAt = 0;
    return;
  }

  if (wifiConnectWindowStartedAt == 0) {
    wifiConnectWindowStartedAt = now;
  }

  if ((uint32_t)(now - wifiConnectWindowStartedAt) >= WIFI_PROVISIONING_FALLBACK_MS) {
    startSetupApMode("wifi_connect_timeout");
    return;
  }

  if (status == WL_IDLE_STATUS ||
      (lastWiFiBeginMs != 0 && (uint32_t)(now - lastWiFiBeginMs) < WIFI_CONNECT_TIMEOUT_MS)) {
    return;
  }
  if ((uint32_t)(now - lastWiFiAttemptMs) < WIFI_RETRY_INTERVAL_MS) {
    return;
  }

  if (status != WL_DISCONNECTED && status != WL_CONNECT_FAILED &&
      status != WL_NO_SSID_AVAIL && status != WL_CONNECTION_LOST) {
    return;
  }

  if (wifiConnectAttempts < 250) {
    wifiConnectAttempts++;
  }

  Serial.printf("[WiFi] reconnecting status=%s\n", wifiStatusText(status));
  if (status == WL_NO_SSID_AVAIL) {
    scanAndLogTargetSSID();
  }
  beginWiFiConnection(true);
}

void onWiFiEvent(WiFiEvent_t event, WiFiEventInfo_t info) {
  switch (event) {
    case ARDUINO_EVENT_WIFI_STA_START:
      Serial.println("[WiFi] STA started");
      break;
    case ARDUINO_EVENT_WIFI_STA_CONNECTED:
      Serial.println("[WiFi] associated with AP");
      break;
    case ARDUINO_EVENT_WIFI_STA_GOT_IP:
      provisionState = PROVISION_CONNECTED;
      provisioningFailureReason = "none";
      lastProvisionError = "";
      if (setupApActive && provisioningSuccessAt == 0) {
        provisioningSuccessAt = millis();
      }
      Serial.printf("[WiFi] connected ip=%s rssi=%d\n",
                    WiFi.localIP().toString().c_str(), WiFi.RSSI());
      break;
    case ARDUINO_EVENT_WIFI_STA_DISCONNECTED:
      lastDisconnectReason = info.wifi_sta_disconnected.reason;
      if (hasRuntimeWiFiConfig()) {
        provisionState = PROVISION_CONNECT_FAILED;
        provisioningFailureReason = "wifi_disconnected";
        lastProvisionError = provisioningFailureReason;
      }
      Serial.printf("[WiFi] disconnected reason=%u status=%s\n",
                    static_cast<unsigned>(lastDisconnectReason),
                    wifiStatusText(WiFi.status()));
      break;
    default:
      break;
  }
}

bool postJson(const String& url, const String& body) {
  if (url.length() == 0 || WiFi.status() != WL_CONNECTED) {
    return false;
  }

  HTTPClient http;
  http.setConnectTimeout(1000);
  http.setTimeout(1500);
  if (!http.begin(url)) {
    Serial.printf("[HTTP] begin failed url=%s\n", url.c_str());
    return false;
  }
  http.addHeader("Content-Type", "application/json");
  int code = http.POST(body);
  if (code <= 0) {
    String error = http.errorToString(code);
    String localIp = WiFi.localIP().toString();
    String gatewayIp = WiFi.gatewayIP().toString();
    Serial.printf("[HTTP] post failed url=%s code=%d error=%s local_ip=%s gateway=%s rssi=%d\n",
                  url.c_str(),
                  code,
                  error.c_str(),
                  localIp.c_str(),
                  gatewayIp.c_str(),
                  WiFi.RSSI());
  } else if (code >= 400) {
    Serial.printf("[HTTP] post error url=%s code=%d\n", url.c_str(), code);
  }
  http.end();
  return code > 0 && code < 400;
}

void sendRegister() {
  if (!backendEnabled()) {
    return;
  }
  lastRegisterAttemptMs = millis();
  String body = String("{") +
                "\"node_id\":\"" + runtimeNodeId + "\"," +
                "\"label\":\"" + NODE_LABEL + "\"," +
                "\"device_type\":\"" + NODE_TYPE + "\"," +
                "\"location\":\"" + runtimeNodeLocation + "\"}";
  bool ok = postJson(endpoint("/api/devices/register"), body);
  registrationOk = ok;
  Serial.printf("[HTTP] register %s\n", ok ? "ok" : "failed");
}

void sendHeartbeat() {
  if (!backendEnabled()) {
    return;
  }
  String body = String("{") +
                "\"node_id\":\"" + runtimeNodeId + "\"," +
                "\"note\":\"heartbeat\"}";
  postJson(endpoint("/api/devices/heartbeat"), body);
}

bool sendSmokeEvent(float value, const char* eventCode) {
  if (!backendEnabled()) {
    return false;
  }
  String body = String("{") +
                "\"node_id\":\"" + runtimeNodeId + "\"," +
                "\"event\":\"" + eventCode + "\"," +
                "\"location\":\"" + runtimeNodeLocation + "\"," +
                "\"value\":" + String(value, 3) + "}";
  bool ok = postJson(endpoint("/api/sensors/event"), body);
  if (ok) {
    Serial.printf("[HTTP] event=%s value=%.3f\n", eventCode, value);
  } else {
    Serial.printf("[HTTP] event=%s failed value=%.3f\n", eventCode, value);
  }
  return ok;
}

Mq2Reading readMq2() {
  long sum = 0;
  int minReading = ADC_RESOLUTION;
  int maxReading = 0;

  for (int i = 0; i < MQ2_ADC_SAMPLES; ++i) {
    int reading = analogRead(MQ2_ADC_PIN);
    sum += reading;
    if (reading < minReading) {
      minReading = reading;
    }
    if (reading > maxReading) {
      maxReading = reading;
    }
    delay(MQ2_ADC_SAMPLE_DELAY_MS);
  }

  Mq2Reading result;
  result.avgRaw = static_cast<int>(sum / MQ2_ADC_SAMPLES);
  result.minRaw = minReading;
  result.maxRaw = maxReading;
  result.espVoltage = (result.avgRaw / static_cast<float>(ADC_RESOLUTION)) * ESP32_ADC_MAX_VOLTAGE;
  result.mq2A0Voltage = result.espVoltage * DIVIDER_MULTIPLIER;
  return result;
}

float normalizeMq2Raw(int raw) {
  if (raw < 0) {
    raw = 0;
  } else if (raw > ADC_RESOLUTION) {
    raw = ADC_RESOLUTION;
  }
  return static_cast<float>(raw) / static_cast<float>(ADC_RESOLUTION);
}

SmokeStatus classifyMq2Reading(int raw) {
  if (raw >= SMOKE_HIGH_THRESHOLD) {
    return SMOKE_STATUS_HIGH;
  }
  if (raw >= SMOKE_WARNING_THRESHOLD) {
    return SMOKE_STATUS_WARNING;
  }
  return SMOKE_STATUS_NORMAL;
}

const char* smokeStatusText(SmokeStatus status) {
  switch (status) {
    case SMOKE_STATUS_HIGH:
      return "SMOKE_HIGH";
    case SMOKE_STATUS_WARNING:
      return "SMOKE_WARNING";
    case SMOKE_STATUS_NORMAL:
    default:
      return "NORMAL";
  }
}

void setBuzzerOutput(bool enabled) {
  buzzerOutputHigh = enabled;
  digitalWrite(BUZZER_PIN, enabled ? HIGH : LOW);
}

void updateBuzzer() {
  uint32_t now = millis();

  if (currentSmokeStatus == SMOKE_STATUS_NORMAL) {
    buzzerPatternStatus = SMOKE_STATUS_NORMAL;
    lastBuzzerToggleMs = now;
    if (buzzerOutputHigh) {
      setBuzzerOutput(false);
    }
    return;
  }

  if (currentSmokeStatus != buzzerPatternStatus) {
    buzzerPatternStatus = currentSmokeStatus;
    lastBuzzerToggleMs = now;
    setBuzzerOutput(true);
    return;
  }

  uint32_t onMs = currentSmokeStatus == SMOKE_STATUS_HIGH ? BUZZER_HIGH_ON_MS : BUZZER_WARNING_ON_MS;
  uint32_t offMs = currentSmokeStatus == SMOKE_STATUS_HIGH ? BUZZER_HIGH_OFF_MS : BUZZER_WARNING_OFF_MS;
  uint32_t intervalMs = buzzerOutputHigh ? onMs : offMs;
  if ((uint32_t)(now - lastBuzzerToggleMs) >= intervalMs) {
    setBuzzerOutput(!buzzerOutputHigh);
    lastBuzzerToggleMs = now;
  }
}

void handleWiFiStateChange() {
  bool connected = WiFi.status() == WL_CONNECTED;
  if (connected && !wasWiFiConnected) {
#if defined(WIFI_TX_POWER_RUNTIME)
    WiFi.setTxPower(WIFI_TX_POWER_RUNTIME);
#endif
    WiFi.setSleep(false);
    wifiConnectAttempts = 0;
    registrationOk = false;
    Serial.printf("[WiFi] got ip=%s rssi=%d\n", WiFi.localIP().toString().c_str(),
                  WiFi.RSSI());
    sendRegister();
  } else if (!connected && wasWiFiConnected) {
    Serial.println("[WiFi] disconnected");
    registrationOk = false;
  }
  wasWiFiConnected = connected;
}

void setup() {
  Serial.begin(115200);
  unsigned long serialWaitStartMs = millis();
  while (!Serial && (uint32_t)(millis() - serialWaitStartMs) < 2000) {
    delay(10);
  }
  delay(250);
  Serial.println("\n[BOOT] Smoke node 2 HTTP start");

  WiFi.onEvent(onWiFiEvent);
  loadRuntimeConfigFromStorage();

  analogReadResolution(12);
  analogSetPinAttenuation(MQ2_ADC_PIN, ADC_11db);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);
  sensorWarmupUntilMs = millis() + MQ2_WARMUP_MS;
  Serial.printf("[SENSOR] mq2 pin=%d buzzer_pin=%d warning=%d high=%d warmup_ms=%lu\n",
                MQ2_ADC_PIN,
                BUZZER_PIN,
                SMOKE_WARNING_THRESHOLD,
                SMOKE_HIGH_THRESHOLD,
                static_cast<unsigned long>(MQ2_WARMUP_MS));

  if (hasRuntimeWiFiConfig()) {
    connectWiFiBlocking();
  } else {
    provisionState = PROVISION_UNCONFIGURED;
    provisioningFailureReason = "no_credentials";
    lastProvisionError = provisioningFailureReason;
    startSetupApMode("no_credentials");
  }
}

void loop() {
  updateBuzzer();

  if (!setupApActive && !hasRuntimeWiFiConfig()) {
    startSetupApMode("no_credentials");
  }

  if (setupApActive && provisionState == PROVISION_CONNECTED &&
      provisioningSuccessAt != 0 &&
      (uint32_t)(millis() - provisioningSuccessAt) >= PROVISIONING_SUCCESS_HOLD_MS) {
    stopSetupApMode();
  }

  ensureProvisioningServerState();
  if (provisioningServerStarted) {
    if (setupApActive) {
      provisioningDnsServer.processNextRequest();
    }
    provisioningServer.handleClient();
  }

  maintainWiFiConnection();

  handleWiFiStateChange();

  if (WiFi.status() != WL_CONNECTED) {
    uint32_t now = millis();
    if ((uint32_t)(now - lastWiFiStatusLogMs) >= 2000) {
      Serial.printf("[WiFi] waiting status=%s attempt=%u\n",
                    wifiStatusText(WiFi.status()),
                    static_cast<unsigned>(wifiConnectAttempts + 1));
      lastWiFiStatusLogMs = now;
    }
    delay(20);
    return;
  }

  uint32_t now = millis();

  if (backendEnabled() && !registrationOk &&
      (uint32_t)(now - lastRegisterAttemptMs) >= REGISTER_RETRY_INTERVAL_MS) {
    sendRegister();
  }

  if (backendEnabled() && (now - lastHeartbeatMs) >= HEARTBEAT_INTERVAL_MS) {
    sendHeartbeat();
    lastHeartbeatMs = now;
  }

  if ((now - lastReadingMs) >= SENSOR_REPORT_INTERVAL_MS) {
    Mq2Reading reading = readMq2();
    int raw = reading.avgRaw;
    float normalized = normalizeMq2Raw(raw);
    SmokeStatus status = classifyMq2Reading(raw);

    Serial.printf("[SENSOR] raw_avg=%d min=%d max=%d esp_v=%.3f mq2_a0_v=%.3f status=%s%s\n",
                  reading.avgRaw,
                  reading.minRaw,
                  reading.maxRaw,
                  reading.espVoltage,
                  reading.mq2A0Voltage,
                  smokeStatusText(status),
                  (int32_t)(now - sensorWarmupUntilMs) < 0 ? " warmup" : "");

    if ((int32_t)(now - sensorWarmupUntilMs) < 0) {
      smokeLatched = false;
      notifiedSmokeStatus = SMOKE_STATUS_NORMAL;
      currentSmokeStatus = SMOKE_STATUS_NORMAL;
      smokeClearConfirmCount = 0;
    } else {
      if (status == SMOKE_STATUS_NORMAL) {
        if (smokeClearConfirmCount < 255) {
          smokeClearConfirmCount++;
        }
        if (!smokeLatched) {
          lastSmokeEventAttemptMs = 0;
          notifiedSmokeStatus = SMOKE_STATUS_NORMAL;
          currentSmokeStatus = SMOKE_STATUS_NORMAL;
        }
      } else {
        smokeClearConfirmCount = 0;
      }

      if (status != SMOKE_STATUS_NORMAL &&
          (!smokeLatched || (status == SMOKE_STATUS_HIGH && notifiedSmokeStatus != SMOKE_STATUS_HIGH))) {
        bool highEscalation = status == SMOKE_STATUS_HIGH && notifiedSmokeStatus != SMOKE_STATUS_HIGH;
        if (lastSmokeEventAttemptMs == 0 || highEscalation ||
            (uint32_t)(now - lastSmokeEventAttemptMs) >= SMOKE_EVENT_RETRY_INTERVAL_MS) {
          const char* eventCode = status == SMOKE_STATUS_HIGH ? "SMOKE_HIGH" : "SMOKE_WARNING";
          lastSmokeEventAttemptMs = now;
          if (sendSmokeEvent(normalized, eventCode)) {
            smokeLatched = true;
            notifiedSmokeStatus = status;
            currentSmokeStatus = status;
          } else {
            Serial.printf("[SENSOR] event pending status=%s; buzzer held until backend accepts event\n",
                          smokeStatusText(status));
          }
        }
      } else if (smokeLatched && smokeClearConfirmCount >= MQ2_CLEAR_CONFIRM_SAMPLES) {
        sendSmokeEvent(normalized, "SMOKE_NORMAL");
        smokeClearConfirmCount = 0;
        smokeLatched = false;
        notifiedSmokeStatus = SMOKE_STATUS_NORMAL;
        lastSmokeEventAttemptMs = 0;
        currentSmokeStatus = SMOKE_STATUS_NORMAL;
      } else {
        currentSmokeStatus = notifiedSmokeStatus;
      }
    }

    lastReadingMs = now;
  }

  updateBuzzer();

  delay(20);
}
