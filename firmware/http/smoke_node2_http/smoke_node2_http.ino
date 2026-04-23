#include <HTTPClient.h>
#include <WiFi.h>

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

// Adaptive TX power profile:
// - start with moderate TX for join attempts
// - escalate to high TX after repeated failures
// - settle to moderate runtime TX
#if defined(WIFI_POWER_13dBm)
#define WIFI_TX_POWER_CONNECT_INITIAL WIFI_POWER_13dBm
#elif defined(WIFI_POWER_11dBm)
#define WIFI_TX_POWER_CONNECT_INITIAL WIFI_POWER_11dBm
#elif defined(WIFI_POWER_8_5dBm)
#define WIFI_TX_POWER_CONNECT_INITIAL WIFI_POWER_8_5dBm
#endif

#if defined(WIFI_POWER_19_5dBm)
#define WIFI_TX_POWER_CONNECT_ESCALATED WIFI_POWER_19_5dBm
#elif defined(WIFI_TX_POWER_CONNECT_INITIAL)
#define WIFI_TX_POWER_CONNECT_ESCALATED WIFI_TX_POWER_CONNECT_INITIAL
#endif

#if defined(WIFI_POWER_11dBm)
#define WIFI_TX_POWER_RUNTIME WIFI_POWER_11dBm
#elif defined(WIFI_POWER_8_5dBm)
#define WIFI_TX_POWER_RUNTIME WIFI_POWER_8_5dBm
#elif defined(WIFI_TX_POWER_CONNECT_INITIAL)
#define WIFI_TX_POWER_RUNTIME WIFI_TX_POWER_CONNECT_INITIAL
#endif

// Connectivity/retry timing.
static const uint32_t WIFI_RETRY_INTERVAL_MS = 15000;
static const uint32_t WIFI_CONNECT_TIMEOUT_MS = 20000;
static const uint32_t REGISTER_RETRY_INTERVAL_MS = 10000;
static const uint8_t WIFI_ESCALATE_AFTER_ATTEMPTS = 2;

// Sensor and heartbeat timing.
static const uint32_t HEARTBEAT_INTERVAL_MS = 15000;
static const uint32_t SENSOR_REPORT_INTERVAL_MS = 5000;

enum ProvisionState {
  PROVISION_UNCONFIGURED = 0,
  PROVISION_CONNECTING,
  PROVISION_CONNECTED,
  PROVISION_CONNECT_FAILED,
};

ProvisionState provisionState = PROVISION_UNCONFIGURED;

String runtimeWiFiSsid;
String runtimeWiFiPassword;
String runtimeHostname;
String runtimeBackendBase;
String lastProvisionError;

uint32_t lastHeartbeatMs = 0;
uint32_t lastReadingMs = 0;
uint32_t lastWiFiAttemptMs = 0;
uint32_t lastWiFiBeginMs = 0;
uint32_t lastRegisterAttemptMs = 0;
uint32_t lastWiFiStatusLogMs = 0;
uint8_t wifiConnectAttempts = 0;
uint8_t lastDisconnectReason = 0;
bool wasWiFiConnected = false;
bool registrationOk = false;

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
}

#if defined(WIFI_TX_POWER_CONNECT_INITIAL) && defined(WIFI_TX_POWER_CONNECT_ESCALATED)
wifi_power_t currentConnectTxPower() {
  if (wifiConnectAttempts >= WIFI_ESCALATE_AFTER_ATTEMPTS) {
    return WIFI_TX_POWER_CONNECT_ESCALATED;
  }
  return WIFI_TX_POWER_CONNECT_INITIAL;
}
#endif

void beginWiFiConnection() {
  if (!hasRuntimeWiFiConfig()) {
    return;
  }

  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.setAutoReconnect(true);
  WiFi.persistent(false);
  WiFi.setHostname(sanitizeHostname(runtimeHostname).c_str());
#if defined(WIFI_TX_POWER_CONNECT_INITIAL) && defined(WIFI_TX_POWER_CONNECT_ESCALATED)
  WiFi.setTxPower(currentConnectTxPower());
#endif
  WiFi.begin(runtimeWiFiSsid.c_str(), runtimeWiFiPassword.c_str());
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
    Serial.println("[WiFi] no configured credentials");
    return;
  }

  beginWiFiConnection();
  uint32_t startedAt = millis();
  while (WiFi.status() != WL_CONNECTED &&
         (millis() - startedAt) < WIFI_CONNECT_TIMEOUT_MS) {
    delay(250);
    Serial.print('.');
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    provisionState = PROVISION_CONNECTED;
    return;
  }

  provisionState = PROVISION_CONNECT_FAILED;
  lastProvisionError = "wifi_connect_timeout";
}

void maintainWiFiConnection() {
  if (!hasRuntimeWiFiConfig()) {
    return;
  }

  wl_status_t status = WiFi.status();
  if (status == WL_CONNECTED) {
    return;
  }

  uint32_t now = millis();
  if ((now - lastWiFiBeginMs) < WIFI_CONNECT_TIMEOUT_MS) {
    return;
  }
  if ((now - lastWiFiAttemptMs) < WIFI_RETRY_INTERVAL_MS) {
    return;
  }
  if (status != WL_DISCONNECTED && status != WL_CONNECT_FAILED &&
      status != WL_NO_SSID_AVAIL) {
    return;
  }

  if (wifiConnectAttempts < 250) {
    wifiConnectAttempts++;
  }

  Serial.printf("[WiFi] reconnecting status=%s\n", wifiStatusText(status));
  WiFi.disconnect();
  delay(20);
  beginWiFiConnection();
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
      lastProvisionError = "";
      Serial.printf("[WiFi] connected ip=%s rssi=%d\n",
                    WiFi.localIP().toString().c_str(), WiFi.RSSI());
      break;
    case ARDUINO_EVENT_WIFI_STA_DISCONNECTED:
      lastDisconnectReason = info.wifi_sta_disconnected.reason;
      if (hasRuntimeWiFiConfig()) {
        provisionState = PROVISION_CONNECT_FAILED;
        lastProvisionError = "wifi_disconnected";
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
  http.setConnectTimeout(3000);
  http.setTimeout(4000);
  if (!http.begin(url)) {
    Serial.printf("[HTTP] begin failed url=%s\n", url.c_str());
    return false;
  }
  http.addHeader("Content-Type", "application/json");
  int code = http.POST(body);
  if (code <= 0) {
    Serial.printf("[HTTP] post failed url=%s code=%d\n", url.c_str(), code);
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
                "\"node_id\":\"" + NODE_ID + "\"," +
                "\"label\":\"" + NODE_LABEL + "\"," +
                "\"device_type\":\"" + NODE_TYPE + "\"," +
                "\"location\":\"" + NODE_LOCATION + "\"}";
  bool ok = postJson(endpoint("/api/devices/register"), body);
  registrationOk = ok;
  Serial.printf("[HTTP] register %s\n", ok ? "ok" : "failed");
}

void sendHeartbeat() {
  if (!backendEnabled()) {
    return;
  }
  String body = String("{") +
                "\"node_id\":\"" + NODE_ID + "\"," +
                "\"note\":\"heartbeat\"}";
  postJson(endpoint("/api/devices/heartbeat"), body);
}

void sendSmokeEvent(float value, const char* eventCode) {
  if (!backendEnabled()) {
    return;
  }
  String body = String("{") +
                "\"node_id\":\"" + NODE_ID + "\"," +
                "\"event\":\"" + eventCode + "\"," +
                "\"location\":\"" + NODE_LOCATION + "\"," +
                "\"value\":" + String(value, 3) + "}";
  bool ok = postJson(endpoint("/api/sensors/event"), body);
  if (ok) {
    Serial.printf("[HTTP] event=%s value=%.3f\n", eventCode, value);
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

  if (hasRuntimeWiFiConfig()) {
    connectWiFiBlocking();
  } else {
    provisionState = PROVISION_UNCONFIGURED;
    lastProvisionError = "manual_wifi_config_required";
    Serial.println("[WiFi] manual config required: set WIFI_SSID/WIFI_PASSWORD/BACKEND_BASE before upload");
  }
}

void loop() {
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
    float simulated = static_cast<float>(esp_random() % 1000) / 1000.0f;
    const char* eventCode = simulated > 0.70f ? "SMOKE_HIGH" : "SMOKE_NORMAL";
    sendSmokeEvent(simulated, eventCode);
    lastReadingMs = now;
  }

  delay(20);
}
