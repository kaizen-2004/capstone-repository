#include "esp_camera.h"
#include "img_converters.h"
#include "esp_http_server.h"

#include <ESPmDNS.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <WiFi.h>

#include <ctype.h>

// Compile-time fallback values.
static const char* WIFI_SSID = "";
static const char* WIFI_PASSWORD = "";
static const char* WIFI_HOSTNAME = "cam-door";
static const char* BACKEND_BASE = "";
static const char* BACKEND_EVENT_URL = "";
static const char* API_KEY = "";

static const char* NODE_ID = "cam_door";
static const char* ROOM_NAME = "Door Entrance Area";
static const char* NODE_TYPE = "camera";
static const char* FIRMWARE_VERSION = "cam_door_esp32cam_v2_lowlatency";

// Low-latency live profile (trades sharpness for smoothness).
static const framesize_t CAMERA_FRAME_SIZE = FRAMESIZE_QVGA;
static const int CAMERA_JPEG_QUALITY = 16;
static const uint32_t STREAM_FRAME_DELAY_MS = 0;

static const uint32_t WIFI_RETRY_INTERVAL_MS = 15000;
static const uint32_t WIFI_CONNECT_TIMEOUT_MS = 20000;
static const uint32_t HTTP_RETRY_INTERVAL_MS = 5000;
static const uint32_t HTTP_TIMEOUT_MS = 5000;
static const uint32_t HEARTBEAT_INTERVAL_MS = 60000;

// LED behavior: prewarm + pulse.
static const uint16_t FLASH_PREWARM_MS = 120;
static const uint16_t FLASH_HOLD_MS = 80;

// Provisioning behavior.
static const uint32_t SETUP_AP_TIMEOUT_MS = 600000;  // 10 minutes
static const uint32_t SETUP_AP_POST_CONNECT_GRACE_MS = 30000;  // 30 seconds
static const char* SETUP_AP_PREFIX = "Thesis-Setup";

// AI Thinker ESP32-CAM pins.
#define PWDN_GPIO_NUM 32
#define RESET_GPIO_NUM -1
#define XCLK_GPIO_NUM 0
#define SIOD_GPIO_NUM 26
#define SIOC_GPIO_NUM 27

#define Y9_GPIO_NUM 35
#define Y8_GPIO_NUM 34
#define Y7_GPIO_NUM 39
#define Y6_GPIO_NUM 36
#define Y5_GPIO_NUM 21
#define Y4_GPIO_NUM 19
#define Y3_GPIO_NUM 18
#define Y2_GPIO_NUM 5
#define VSYNC_GPIO_NUM 25
#define HREF_GPIO_NUM 23
#define PCLK_GPIO_NUM 22

#define FLASH_LED_PIN 4

static const char* STREAM_CONTENT_TYPE =
    "multipart/x-mixed-replace;boundary=frame";
static const char* STREAM_BOUNDARY = "\r\n--frame\r\n";
static const char* STREAM_PART =
    "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n";

static const char* NVS_NAMESPACE = "provision";
static const char* NVS_WIFI_SSID = "wifi_ssid";
static const char* NVS_WIFI_PASS = "wifi_pass";
static const char* NVS_HOSTNAME = "hostname";
static const char* NVS_BACKEND_BASE = "backend_base";
static const char* NVS_FORCE_SETUP_AP = "force_ap";

httpd_handle_t cameraHttpd = nullptr;
httpd_handle_t streamHttpd = nullptr;
bool cameraServerRunning = false;
bool flashForcedOn = false;

bool setupApActive = false;
bool setupApExpired = false;
String setupApSsid;
uint32_t setupApStartedMs = 0;
bool pendingDisableSetupAp = false;
uint32_t setupApDisableAtMs = 0;

bool mdnsStarted = false;
String mdnsHost;

String runtimeWiFiSsid;
String runtimeWiFiPassword;
String runtimeHostname;
String runtimeBackendBase;
String runtimeBackendEventUrl;

String lastProvisionError;
uint8_t lastDisconnectReason = 0;
bool forceSetupApOnBoot = false;

enum ProvisionState {
  PROVISION_UNCONFIGURED = 0,
  PROVISION_AP_SETUP,
  PROVISION_CONNECTING,
  PROVISION_CONNECTED,
  PROVISION_CONNECT_FAILED,
};

ProvisionState provisionState = PROVISION_UNCONFIGURED;

struct PendingEvent {
  bool active = false;
  String event;
  float value = 0.0f;
  String unit;
  String note;
  uint32_t nextAttemptMs = 0;
};

PendingEvent pendingEvent;

uint32_t lastWiFiReconnectAttemptAt = 0;
uint32_t lastWiFiBeginAt = 0;
uint32_t lastHeartbeatMs = 0;

bool isConfiguredValue(const String& value) {
  String trimmed = value;
  trimmed.trim();
  if (trimmed.length() == 0) {
    return false;
  }
  if (trimmed.startsWith("YOUR_") || trimmed.equalsIgnoreCase("CHANGE_ME")) {
    return false;
  }
  return true;
}

bool hasRuntimeWiFiConfig() { return isConfiguredValue(runtimeWiFiSsid); }

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
    return "cam-door";
  }
  if (out.length() > 31) {
    out = out.substring(0, 31);
  }
  return out;
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
  return base;
}

String sanitizeBackendEventUrl(const String& urlRaw) {
  String url = urlRaw;
  url.trim();
  if (url.length() == 0) {
    return "";
  }
  if (isLocalOnlyBackendTarget(url)) {
    Serial.printf("[PROV] ignoring local-only backend_event_url=%s\n", url.c_str());
    return "";
  }
  return url;
}

String backendEventUrlFromBase(const String& baseRaw) {
  String base = sanitizeBackendBase(baseRaw);
  if (base.length() == 0) {
    return "";
  }
  if (base.endsWith("/")) {
    base.remove(base.length() - 1);
  }
  if (base.endsWith("/api/sensors/event")) {
    return base;
  }
  return base + "/api/sensors/event";
}

String provisionStateText() {
  switch (provisionState) {
    case PROVISION_UNCONFIGURED:
      return "unconfigured";
    case PROVISION_AP_SETUP:
      return "ap_setup";
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

String jsonEscape(const String& in) {
  String out;
  out.reserve(in.length() + 8);
  for (size_t i = 0; i < in.length(); ++i) {
    char c = in.charAt(i);
    if (c == '\\' || c == '"') {
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

String chipIdSuffix() {
  uint64_t chipId = ESP.getEfuseMac();
  char suffix[7];
  snprintf(suffix, sizeof(suffix), "%06llX", chipId & 0xFFFFFFULL);
  return String(suffix);
}

String chipIdHex() {
  uint64_t chipId = ESP.getEfuseMac();
  char buf[13];
  snprintf(buf, sizeof(buf), "%012llX", chipId);
  return String(buf);
}

String buildSetupApSsid() {
  return String(SETUP_AP_PREFIX) + "-" + chipIdSuffix();
}

String activeHostIp() {
  if (WiFi.status() == WL_CONNECTED) {
    return WiFi.localIP().toString();
  }
  if (setupApActive) {
    return WiFi.softAPIP().toString();
  }
  return "";
}

String activeModeText() {
  if (setupApActive && WiFi.status() == WL_CONNECTED) {
    return "ap_sta";
  }
  if (setupApActive) {
    return "ap";
  }
  if (WiFi.status() == WL_CONNECTED) {
    return "sta";
  }
  return "idle";
}

uint32_t setupApRemainingSec() {
  if (!setupApActive) {
    return 0;
  }
  uint32_t elapsed = millis() - setupApStartedMs;
  if (elapsed >= SETUP_AP_TIMEOUT_MS) {
    return 0;
  }
  return static_cast<uint32_t>((SETUP_AP_TIMEOUT_MS - elapsed) / 1000U);
}

void setCorsHeaders(httpd_req_t* req) {
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Methods", "GET,POST,OPTIONS");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Headers", "Content-Type");
}

const char* statusTextForCode(int code) {
  switch (code) {
    case 200:
      return "200 OK";
    case 204:
      return "204 No Content";
    case 400:
      return "400 Bad Request";
    case 404:
      return "404 Not Found";
    case 500:
      return "500 Internal Server Error";
    default:
      return "200 OK";
  }
}

void sendJsonResponse(httpd_req_t* req, const String& payload, int statusCode = 200) {
  httpd_resp_set_status(req, statusTextForCode(statusCode));
  httpd_resp_set_type(req, "application/json");
  setCorsHeaders(req);
  httpd_resp_send(req, payload.c_str(), payload.length());
}

String readRequestBody(httpd_req_t* req) {
  int total = req->content_len;
  if (total <= 0) {
    return "";
  }
  if (total > 2048) {
    return "";
  }

  String body;
  body.reserve(total + 1);
  int remaining = total;
  char buffer[256];

  while (remaining > 0) {
    int toRead = remaining > static_cast<int>(sizeof(buffer))
                     ? static_cast<int>(sizeof(buffer))
                     : remaining;
    int got = httpd_req_recv(req, buffer, toRead);
    if (got <= 0) {
      break;
    }
    for (int i = 0; i < got; ++i) {
      body += buffer[i];
    }
    remaining -= got;
  }
  return body;
}

bool extractJsonStringField(const String& body, const char* key, String& out) {
  String marker = String("\"") + key + "\"";
  int keyPos = body.indexOf(marker);
  if (keyPos < 0) {
    return false;
  }

  int colon = body.indexOf(':', keyPos + marker.length());
  if (colon < 0) {
    return false;
  }

  int i = colon + 1;
  while (i < body.length() && isspace(static_cast<unsigned char>(body.charAt(i)))) {
    ++i;
  }
  if (i >= body.length() || body.charAt(i) != '"') {
    return false;
  }

  ++i;
  String value;
  bool escaped = false;
  while (i < body.length()) {
    char c = body.charAt(i++);
    if (escaped) {
      switch (c) {
        case 'n':
          value += '\n';
          break;
        case 'r':
          value += '\r';
          break;
        case 't':
          value += '\t';
          break;
        default:
          value += c;
          break;
      }
      escaped = false;
      continue;
    }
    if (c == '\\') {
      escaped = true;
      continue;
    }
    if (c == '"') {
      out = value;
      return true;
    }
    value += c;
  }

  return false;
}

void loadRuntimeConfigFromStorage() {
  runtimeWiFiSsid = String(WIFI_SSID);
  runtimeWiFiPassword = String(WIFI_PASSWORD);
  runtimeHostname = sanitizeHostname(String(WIFI_HOSTNAME));
  runtimeBackendBase = sanitizeBackendBase(String(BACKEND_BASE));
  runtimeBackendEventUrl = backendEventUrlFromBase(runtimeBackendBase);
  if (runtimeBackendEventUrl.length() == 0) {
    runtimeBackendEventUrl = sanitizeBackendEventUrl(String(BACKEND_EVENT_URL));
  }

  Preferences prefs;
  if (prefs.begin(NVS_NAMESPACE, true)) {
    String storedSsid = prefs.getString(NVS_WIFI_SSID, "");
    String storedPass = prefs.getString(NVS_WIFI_PASS, "");
    String storedHostname = prefs.getString(NVS_HOSTNAME, "");
    String storedBackendBase = sanitizeBackendBase(prefs.getString(NVS_BACKEND_BASE, ""));
    forceSetupApOnBoot = prefs.getBool(NVS_FORCE_SETUP_AP, false);
    prefs.end();

    if (isConfiguredValue(storedSsid)) {
      runtimeWiFiSsid = storedSsid;
      runtimeWiFiPassword = storedPass;
    }
    if (isConfiguredValue(storedHostname)) {
      runtimeHostname = sanitizeHostname(storedHostname);
    }
    if (isConfiguredValue(storedBackendBase)) {
      runtimeBackendBase = storedBackendBase;
      runtimeBackendEventUrl = backendEventUrlFromBase(runtimeBackendBase);
    }

    if (forceSetupApOnBoot) {
      runtimeWiFiSsid = "";
      runtimeWiFiPassword = "";
    }
  }
}

bool saveProvisioningToStorage(const String& ssid, const String& password,
                              const String& hostname,
                              const String& backendBase) {
  Preferences prefs;
  if (!prefs.begin(NVS_NAMESPACE, false)) {
    return false;
  }
  prefs.putString(NVS_WIFI_SSID, ssid);
  prefs.putString(NVS_WIFI_PASS, password);
  prefs.putString(NVS_HOSTNAME, hostname);
  prefs.putString(NVS_BACKEND_BASE, backendBase);
  prefs.putBool(NVS_FORCE_SETUP_AP, false);
  prefs.end();
  return true;
}

void clearProvisioningStorage() {
  Preferences prefs;
  if (!prefs.begin(NVS_NAMESPACE, false)) {
    return;
  }
  prefs.remove(NVS_WIFI_SSID);
  prefs.remove(NVS_WIFI_PASS);
  prefs.remove(NVS_HOSTNAME);
  prefs.remove(NVS_BACKEND_BASE);
  prefs.remove(NVS_FORCE_SETUP_AP);
  prefs.end();
}

void setForceSetupApFlag(bool enabled) {
  Preferences prefs;
  if (!prefs.begin(NVS_NAMESPACE, false)) {
    return;
  }
  prefs.putBool(NVS_FORCE_SETUP_AP, enabled);
  prefs.end();
}

bool backendEnabled() {
  String url = runtimeBackendEventUrl;
  url.trim();
  return url.length() > 0;
}

void setFlashState(bool enabled) {
  flashForcedOn = enabled;
  digitalWrite(FLASH_LED_PIN, enabled ? HIGH : LOW);
}

void stopMdns() {
  if (mdnsStarted) {
    MDNS.end();
    mdnsStarted = false;
    mdnsHost = "";
  }
}

void refreshMdnsState() {
  if (WiFi.status() != WL_CONNECTED) {
    stopMdns();
    return;
  }

  String desiredHost = sanitizeHostname(runtimeHostname);
  if (desiredHost.length() == 0) {
    desiredHost = "cam-door";
  }

  if (mdnsStarted && desiredHost == mdnsHost) {
    return;
  }

  stopMdns();
  if (MDNS.begin(desiredHost.c_str())) {
    mdnsStarted = true;
    mdnsHost = desiredHost;
    Serial.printf("[mDNS] ready host=%s.local\n", mdnsHost.c_str());
  } else {
    Serial.println("[mDNS] failed to start");
  }
}

void startSetupAP(const String& reason) {
  if (setupApActive) {
    return;
  }

  setupApSsid = buildSetupApSsid();
  WiFi.mode(WIFI_AP_STA);
  WiFi.setSleep(false);

  bool ok = WiFi.softAP(setupApSsid.c_str());
  if (!ok) {
    Serial.println("[PROV] failed to start setup AP");
    return;
  }

  setupApActive = true;
  setupApExpired = false;
  setupApStartedMs = millis();
  provisionState = PROVISION_AP_SETUP;
  lastProvisionError = reason;
  pendingDisableSetupAp = false;
  setupApDisableAtMs = 0;

  Serial.printf("[PROV] setup AP active ssid=%s ip=%s\n", setupApSsid.c_str(),
                WiFi.softAPIP().toString().c_str());
}

void stopSetupAP(bool markExpired) {
  if (!setupApActive) {
    return;
  }

  WiFi.softAPdisconnect(true);
  setupApActive = false;
  setupApSsid = "";
  setupApStartedMs = 0;
  pendingDisableSetupAp = false;
  setupApDisableAtMs = 0;
  if (markExpired) {
    setupApExpired = true;
  }

  if (WiFi.status() == WL_CONNECTED || hasRuntimeWiFiConfig()) {
    WiFi.mode(WIFI_STA);
  }

  Serial.println("[PROV] setup AP stopped");
}

void handleSetupApTimeout() {
  if (!setupApActive) {
    return;
  }
  if (pendingDisableSetupAp && WiFi.status() == WL_CONNECTED) {
    return;
  }
  if ((millis() - setupApStartedMs) < SETUP_AP_TIMEOUT_MS) {
    return;
  }

  Serial.println("[PROV] setup AP timed out (10 minutes)");
  stopSetupAP(true);
  if (WiFi.status() != WL_CONNECTED) {
    lastProvisionError = "setup_ap_timeout";
    if (!hasRuntimeWiFiConfig()) {
      provisionState = PROVISION_UNCONFIGURED;
    } else {
      provisionState = PROVISION_CONNECT_FAILED;
    }
  }
}

void beginWiFiConnection() {
  if (!hasRuntimeWiFiConfig()) {
    return;
  }

  WiFi.mode(setupApActive ? WIFI_AP_STA : WIFI_STA);
  WiFi.setSleep(false);
  WiFi.setAutoReconnect(true);
  WiFi.persistent(false);
  WiFi.setHostname(sanitizeHostname(runtimeHostname).c_str());
  WiFi.begin(runtimeWiFiSsid.c_str(), runtimeWiFiPassword.c_str());
  lastWiFiBeginAt = millis();
  provisionState = PROVISION_CONNECTING;
  Serial.printf("[WiFi] connecting ssid=%s\n", runtimeWiFiSsid.c_str());
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
    Serial.printf("[WiFi] connected ip=%s rssi=%d\n",
                  WiFi.localIP().toString().c_str(), WiFi.RSSI());
  } else {
    provisionState = PROVISION_CONNECT_FAILED;
    if (!setupApActive && !setupApExpired) {
      startSetupAP("initial_connect_failed");
    }
  }
}

void maintainWiFiConnection() {
  if (!hasRuntimeWiFiConfig()) {
    if (!setupApActive && !setupApExpired) {
      startSetupAP("missing_credentials");
    }
    return;
  }

  wl_status_t status = WiFi.status();
  if (status == WL_CONNECTED) {
    provisionState = PROVISION_CONNECTED;
    return;
  }

  uint32_t now = millis();
  bool joinTimedOut = (now - lastWiFiBeginAt) >= WIFI_CONNECT_TIMEOUT_MS;
  if (status == WL_IDLE_STATUS && !joinTimedOut) {
    return;
  }
  if ((now - lastWiFiReconnectAttemptAt) < WIFI_RETRY_INTERVAL_MS) {
    return;
  }

  lastWiFiReconnectAttemptAt = now;
  provisionState = PROVISION_CONNECT_FAILED;
  lastProvisionError = "wifi_connect_failed";

  if (!setupApActive && !setupApExpired) {
    startSetupAP("wifi_connect_failed");
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
      if (setupApActive) {
        pendingDisableSetupAp = true;
        setupApDisableAtMs = millis() + SETUP_AP_POST_CONNECT_GRACE_MS;
      }
      Serial.printf("[WiFi] connected ip=%s rssi=%d\n",
                    WiFi.localIP().toString().c_str(), WiFi.RSSI());
      break;
    case ARDUINO_EVENT_WIFI_STA_DISCONNECTED:
      lastDisconnectReason = info.wifi_sta_disconnected.reason;
      if (pendingDisableSetupAp) {
        pendingDisableSetupAp = false;
        setupApDisableAtMs = 0;
      }
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

bool postEventNow(const String& eventName, float value, const String& unit,
                 const String& note) {
  if (!backendEnabled()) {
    return true;
  }
  if (WiFi.status() != WL_CONNECTED) {
    return false;
  }

  HTTPClient http;
  http.setConnectTimeout(HTTP_TIMEOUT_MS);
  http.setTimeout(HTTP_TIMEOUT_MS);

  if (!http.begin(runtimeBackendEventUrl)) {
    Serial.println("[HTTP] begin() failed");
    return false;
  }

  http.addHeader("Content-Type", "application/json");
  if (API_KEY && API_KEY[0] != '\0') {
    http.addHeader("X-API-KEY", API_KEY);
  }

  String payload;
  payload.reserve(320);
  payload += "{\"node\":\"" + jsonEscape(String(NODE_ID)) + "\"";
  payload += ",\"event\":\"" + jsonEscape(eventName) + "\"";
  payload += ",\"location\":\"" + jsonEscape(String(ROOM_NAME)) + "\"";
  payload += ",\"value\":" + String(value, 3);
  payload += ",\"unit\":\"" + jsonEscape(unit) + "\"";
  payload += ",\"note\":\"" + jsonEscape(note) + "\"";
  payload += "}";

  int code = http.POST(payload);
  String body = http.getString();
  http.end();

  bool ok = code >= 200 && code < 300;
  if (ok) {
    Serial.printf("[HTTP] %s sent code=%d\n", eventName.c_str(), code);
  } else {
    Serial.printf("[HTTP] send failed event=%s code=%d body=%s\n",
                  eventName.c_str(), code, body.c_str());
  }
  return ok;
}

void queuePending(const String& eventName, float value, const String& unit,
                 const String& note) {
  pendingEvent.active = true;
  pendingEvent.event = eventName;
  pendingEvent.value = value;
  pendingEvent.unit = unit;
  pendingEvent.note = note;
  pendingEvent.nextAttemptMs = 0;
}

void emitEvent(const String& eventName, float value, const String& unit,
               const String& note) {
  if (!backendEnabled()) {
    return;
  }
  if (!postEventNow(eventName, value, unit, note)) {
    queuePending(eventName, value, unit, note);
  }
}

void processPendingEvent() {
  if (!pendingEvent.active) {
    return;
  }

  uint32_t now = millis();
  if (now < pendingEvent.nextAttemptMs) {
    return;
  }

  if (postEventNow(pendingEvent.event, pendingEvent.value, pendingEvent.unit,
                   pendingEvent.note)) {
    pendingEvent.active = false;
    return;
  }

  pendingEvent.nextAttemptMs = now + HTTP_RETRY_INTERVAL_MS;
}

bool queryBoolParam(httpd_req_t* req, const char* key) {
  char query[96];
  char value[16];
  if (httpd_req_get_url_query_str(req, query, sizeof(query)) != ESP_OK) {
    return false;
  }
  if (httpd_query_key_value(query, key, value, sizeof(value)) != ESP_OK) {
    return false;
  }
  return strcmp(value, "1") == 0 || strcasecmp(value, "true") == 0 ||
         strcasecmp(value, "on") == 0;
}

camera_fb_t* captureFrame(bool useFlash) {
  if (useFlash || flashForcedOn) {
    digitalWrite(FLASH_LED_PIN, HIGH);
    delay(FLASH_PREWARM_MS);
  }

  camera_fb_t* fb = esp_camera_fb_get();

  if (useFlash && !flashForcedOn) {
    delay(FLASH_HOLD_MS);
    digitalWrite(FLASH_LED_PIN, LOW);
  }
  return fb;
}

esp_err_t optionsHandler(httpd_req_t* req) {
  httpd_resp_set_status(req, "204 No Content");
  setCorsHeaders(req);
  httpd_resp_send(req, nullptr, 0);
  return ESP_OK;
}

esp_err_t indexHandler(httpd_req_t* req) {
  String ip = activeHostIp();
  String page =
      String(
          "<!doctype html><html><head><meta name='viewport' "
          "content='width=device-width,initial-scale=1'/><title>Door "
          "Camera</title></head><body style='font-family:sans-serif'>") +
      "<h3>ESP32-CAM Door Camera</h3>"
      "<p><a href='/capture'>Capture</a> | <a href='/capture?flash=1'>Capture with "
      "flash</a> | <a href='/snapshot.jpg?flash=1'>snapshot.jpg</a></p>"
      "<p><a href='/control?cmd=status'>Control status</a> | <a "
      "href='/api/provision/status'>Provisioning status</a></p>"
      "<img src='http://" +
      ip +
      ":81/stream' style='max-width:100%;height:auto;border:1px solid #ccc'/>"
      "</body></html>";

  httpd_resp_set_type(req, "text/html");
  setCorsHeaders(req);
  return httpd_resp_send(req, page.c_str(), page.length());
}

esp_err_t captureHandler(httpd_req_t* req) {
  bool useFlash = queryBoolParam(req, "flash");
  camera_fb_t* fb = captureFrame(useFlash);
  if (!fb) {
    httpd_resp_send_500(req);
    return ESP_FAIL;
  }

  httpd_resp_set_type(req, "image/jpeg");
  httpd_resp_set_hdr(req, "Content-Disposition", "inline; filename=capture.jpg");
  setCorsHeaders(req);

  esp_err_t res =
      httpd_resp_send(req, reinterpret_cast<const char*>(fb->buf), fb->len);
  esp_camera_fb_return(fb);
  return res;
}

esp_err_t controlHandler(httpd_req_t* req) {
  char query[96];
  char cmd[24];
  if (httpd_req_get_url_query_str(req, query, sizeof(query)) != ESP_OK ||
      httpd_query_key_value(query, "cmd", cmd, sizeof(cmd)) != ESP_OK) {
    sendJsonResponse(req, "{\"ok\":false,\"error\":\"missing_cmd\"}", 400);
    return ESP_OK;
  }

  String command = String(cmd);
  command.toLowerCase();
  if (command == "flash_on") {
    setFlashState(true);
  } else if (command == "flash_off") {
    setFlashState(false);
  } else if (command == "flash_pulse") {
    digitalWrite(FLASH_LED_PIN, HIGH);
    delay(FLASH_PREWARM_MS + FLASH_HOLD_MS);
    if (!flashForcedOn) {
      digitalWrite(FLASH_LED_PIN, LOW);
    }
  } else if (command != "status") {
    sendJsonResponse(req,
                     "{\"ok\":false,\"error\":\"unsupported_command\"}",
                     400);
    return ESP_OK;
  }

  String body = String("{\"ok\":true,\"node_id\":\"") + NODE_ID +
                "\",\"command\":\"" + command + "\",\"flash_on\":" +
                (flashForcedOn ? "true" : "false") + ",\"ip\":\"" +
                activeHostIp() + "\"}";
  sendJsonResponse(req, body);
  return ESP_OK;
}

esp_err_t provisionInfoHandler(httpd_req_t* req) {
  String body = String("{\"ok\":true,\"node_id\":\"") + NODE_ID +
                "\",\"node_type\":\"" + NODE_TYPE +
                "\",\"firmware_version\":\"" + FIRMWARE_VERSION +
                "\",\"chip_id\":\"" + chipIdHex() + "\",\"api_version\":\"v1\"," +
                "\"setup_ap\":{\"ssid\":\"" +
                jsonEscape(setupApSsid.length() ? setupApSsid : buildSetupApSsid()) +
                "\",\"ip\":\"" + WiFi.softAPIP().toString() +
                "\",\"open\":true},"
                "\"capabilities\":{\"camera_stream\":true,\"camera_snapshot\":true,"
                "\"flash_control\":true,\"sensor_events\":false}}";
  sendJsonResponse(req, body);
  return ESP_OK;
}

esp_err_t provisionStatusHandler(httpd_req_t* req) {
  String staIp = WiFi.status() == WL_CONNECTED ? WiFi.localIP().toString() : "";
  String host = activeHostIp();
  String streamUrl = host.length() ? ("http://" + host + ":81/stream") : "";
  String captureUrl = host.length() ? ("http://" + host + "/capture") : "";
  String controlUrl =
      host.length() ? ("http://" + host + "/control?cmd=status") : "";

  String body = String("{\"ok\":true,\"node_id\":\"") + NODE_ID +
                "\",\"mode\":\"" + activeModeText() +
                "\",\"provision_state\":\"" + provisionStateText() +
                "\",\"setup_ap\":{\"active\":" +
                (setupApActive ? "true" : "false") + ",\"ssid\":\"" +
                jsonEscape(setupApSsid) + "\",\"ip\":\"" +
                (setupApActive ? WiFi.softAPIP().toString() : String("")) +
                "\",\"expires_in_sec\":" + String(setupApRemainingSec()) +
                "},\"sta\":{\"configured\":" +
                (hasRuntimeWiFiConfig() ? "true" : "false") +
                ",\"connected\":" +
                (WiFi.status() == WL_CONNECTED ? "true" : "false") +
                ",\"ssid\":\"" + jsonEscape(runtimeWiFiSsid) +
                "\",\"ip\":\"" + staIp + "\",\"rssi\":" +
                (WiFi.status() == WL_CONNECTED ? String(WiFi.RSSI()) : String("null")) +
                ",\"last_error\":\"" + jsonEscape(lastProvisionError) +
                "\",\"last_disconnect_reason\":" + String(lastDisconnectReason) +
                "},\"mdns\":{\"enabled\":true,\"host\":\"" +
                (mdnsHost.length() ? mdnsHost + ".local" : "") +
                "\",\"ready\":" + (mdnsStarted ? "true" : "false") +
                "},\"endpoints\":{\"stream\":\"" + streamUrl +
                "\",\"capture\":\"" + captureUrl +
                "\",\"control\":\"" + controlUrl + "\"}}";
  sendJsonResponse(req, body);
  return ESP_OK;
}

esp_err_t provisionScanHandler(httpd_req_t* req) {
  int n = WiFi.scanNetworks(false, true);
  if (n < 0) {
    sendJsonResponse(
        req,
        "{\"ok\":false,\"error\":\"scan_failed\",\"detail\":\"Wi-Fi scan failed\"}",
        500);
    return ESP_OK;
  }

  String payload = "{\"ok\":true,\"networks\":[";
  bool first = true;
  for (int i = 0; i < n; ++i) {
    String ssid = WiFi.SSID(i);
    if (ssid.length() == 0) {
      continue;
    }
    if (!first) {
      payload += ",";
    }
    first = false;
    bool secure = WiFi.encryptionType(i) != WIFI_AUTH_OPEN;
    payload += "{\"ssid\":\"" + jsonEscape(ssid) + "\",\"rssi\":" +
               String(WiFi.RSSI(i)) + ",\"secure\":" +
               (secure ? "true" : "false") + ",\"channel\":" +
               String(WiFi.channel(i)) + "}";
  }
  payload += "]}";
  WiFi.scanDelete();

  sendJsonResponse(req, payload);
  return ESP_OK;
}

esp_err_t provisionWifiHandler(httpd_req_t* req) {
  String body = readRequestBody(req);
  String ssid;
  String password;
  String hostname;
  String backendBase;

  if (!extractJsonStringField(body, "ssid", ssid)) {
    sendJsonResponse(req,
                     "{\"ok\":false,\"error\":\"invalid_input\",\"detail\":\"ssid is required\"}",
                     400);
    return ESP_OK;
  }
  extractJsonStringField(body, "password", password);
  if (!extractJsonStringField(body, "hostname", hostname)) {
    hostname = runtimeHostname;
  }
  if (!extractJsonStringField(body, "backend_base", backendBase)) {
    backendBase = runtimeBackendBase;
  }

  ssid.trim();
  hostname = sanitizeHostname(hostname);
  backendBase = sanitizeBackendBase(backendBase);

  if (!isConfiguredValue(ssid)) {
    sendJsonResponse(
        req,
        "{\"ok\":false,\"error\":\"invalid_input\",\"detail\":\"ssid must be configured\"}",
        400);
    return ESP_OK;
  }

  if (!saveProvisioningToStorage(ssid, password, hostname, backendBase)) {
    sendJsonResponse(req,
                     "{\"ok\":false,\"error\":\"storage_error\",\"detail\":\"failed to store provisioning\"}",
                     500);
    return ESP_OK;
  }

  runtimeWiFiSsid = ssid;
  runtimeWiFiPassword = password;
  runtimeHostname = hostname;
  runtimeBackendBase = backendBase;
  forceSetupApOnBoot = false;
  if (runtimeBackendBase.length() > 0) {
    runtimeBackendEventUrl = backendEventUrlFromBase(runtimeBackendBase);
  } else {
    runtimeBackendEventUrl = sanitizeBackendEventUrl(String(BACKEND_EVENT_URL));
  }

  setupApExpired = false;
  lastProvisionError = "";
  beginWiFiConnection();

  sendJsonResponse(req,
                   "{\"ok\":true,\"accepted\":true,\"provision_state\":\"connecting\",\"detail\":\"credentials saved\"}");
  return ESP_OK;
}

esp_err_t provisionResetHandler(httpd_req_t* req) {
  clearProvisioningStorage();
  setForceSetupApFlag(true);

  runtimeWiFiSsid = "";
  runtimeWiFiPassword = "";
  forceSetupApOnBoot = true;
  runtimeHostname = sanitizeHostname(String(WIFI_HOSTNAME));
  runtimeBackendBase = sanitizeBackendBase(String(BACKEND_BASE));
  runtimeBackendEventUrl = runtimeBackendBase.length() > 0
                                ? backendEventUrlFromBase(runtimeBackendBase)
                                : sanitizeBackendEventUrl(String(BACKEND_EVENT_URL));

  stopMdns();
  WiFi.disconnect(true, true);
  setupApExpired = false;
  startSetupAP("reset");

  sendJsonResponse(
      req,
      "{\"ok\":true,\"accepted\":true,\"detail\":\"provisioning cleared; setup AP enabled\"}");
  return ESP_OK;
}

esp_err_t streamHandler(httpd_req_t* req) {
  esp_err_t res = httpd_resp_set_type(req, STREAM_CONTENT_TYPE);
  if (res != ESP_OK) {
    return res;
  }
  setCorsHeaders(req);

  camera_fb_t* fb = nullptr;
  uint8_t* jpgBuf = nullptr;
  size_t jpgLen = 0;
  char partBuf[64];

  while (true) {
    fb = captureFrame(false);
    if (!fb) {
      Serial.println("[CAM] frame capture failed");
      res = ESP_FAIL;
    } else if (fb->format != PIXFORMAT_JPEG) {
      bool ok = frame2jpg(fb, CAMERA_JPEG_QUALITY, &jpgBuf, &jpgLen);
      esp_camera_fb_return(fb);
      fb = nullptr;
      if (!ok) {
        Serial.println("[CAM] jpeg conversion failed");
        res = ESP_FAIL;
      }
    } else {
      jpgBuf = fb->buf;
      jpgLen = fb->len;
    }

    if (res == ESP_OK) {
      size_t hlen = snprintf(partBuf, sizeof(partBuf), STREAM_PART, jpgLen);
      res = httpd_resp_send_chunk(req, STREAM_BOUNDARY, strlen(STREAM_BOUNDARY));
      if (res == ESP_OK) {
        res = httpd_resp_send_chunk(req, partBuf, hlen);
      }
      if (res == ESP_OK) {
        res = httpd_resp_send_chunk(req, reinterpret_cast<const char*>(jpgBuf), jpgLen);
      }
    }

    if (fb) {
      esp_camera_fb_return(fb);
      fb = nullptr;
      jpgBuf = nullptr;
    } else if (jpgBuf) {
      free(jpgBuf);
      jpgBuf = nullptr;
    }

    if (res != ESP_OK) {
      break;
    }

    delay(STREAM_FRAME_DELAY_MS);
  }

  Serial.println("[HTTP] stream client disconnected");
  return res;
}

void stopCameraServer() {
  if (streamHttpd) {
    httpd_stop(streamHttpd);
    streamHttpd = nullptr;
  }
  if (cameraHttpd) {
    httpd_stop(cameraHttpd);
    cameraHttpd = nullptr;
  }
  cameraServerRunning = false;
}

bool startCameraServer() {
  if (cameraServerRunning) {
    return true;
  }

  httpd_config_t cfg = HTTPD_DEFAULT_CONFIG();
  cfg.server_port = 80;
  cfg.max_uri_handlers = 20;

  if (httpd_start(&cameraHttpd, &cfg) != ESP_OK) {
    Serial.println("[HTTP] failed to start control server");
    cameraHttpd = nullptr;
    return false;
  }

  httpd_uri_t indexUri = {"/", HTTP_GET, indexHandler, nullptr};
  httpd_uri_t captureUri = {"/capture", HTTP_GET, captureHandler, nullptr};
  httpd_uri_t snapshotUri = {"/snapshot.jpg", HTTP_GET, captureHandler, nullptr};
  httpd_uri_t controlUri = {"/control", HTTP_GET, controlHandler, nullptr};

  httpd_uri_t provInfoUri = {"/api/provision/info", HTTP_GET,
                             provisionInfoHandler, nullptr};
  httpd_uri_t provStatusUri = {"/api/provision/status", HTTP_GET,
                               provisionStatusHandler, nullptr};
  httpd_uri_t provScanUri = {"/api/provision/scan", HTTP_GET,
                             provisionScanHandler, nullptr};
  httpd_uri_t provWifiPostUri = {"/api/provision/wifi", HTTP_POST,
                                 provisionWifiHandler, nullptr};
  httpd_uri_t provWifiOptionsUri = {"/api/provision/wifi", HTTP_OPTIONS,
                                    optionsHandler, nullptr};
  httpd_uri_t provResetPostUri = {"/api/provision/reset", HTTP_POST,
                                  provisionResetHandler, nullptr};
  httpd_uri_t provResetOptionsUri = {"/api/provision/reset", HTTP_OPTIONS,
                                     optionsHandler, nullptr};

  httpd_register_uri_handler(cameraHttpd, &indexUri);
  httpd_register_uri_handler(cameraHttpd, &captureUri);
  httpd_register_uri_handler(cameraHttpd, &snapshotUri);
  httpd_register_uri_handler(cameraHttpd, &controlUri);
  httpd_register_uri_handler(cameraHttpd, &provInfoUri);
  httpd_register_uri_handler(cameraHttpd, &provStatusUri);
  httpd_register_uri_handler(cameraHttpd, &provScanUri);
  httpd_register_uri_handler(cameraHttpd, &provWifiPostUri);
  httpd_register_uri_handler(cameraHttpd, &provWifiOptionsUri);
  httpd_register_uri_handler(cameraHttpd, &provResetPostUri);
  httpd_register_uri_handler(cameraHttpd, &provResetOptionsUri);

  httpd_config_t streamCfg = HTTPD_DEFAULT_CONFIG();
  streamCfg.server_port = 81;
  streamCfg.ctrl_port = 32769;

  if (httpd_start(&streamHttpd, &streamCfg) != ESP_OK) {
    Serial.println("[HTTP] failed to start stream server");
    stopCameraServer();
    return false;
  }

  httpd_uri_t streamUri = {"/stream", HTTP_GET, streamHandler, nullptr};
  httpd_register_uri_handler(streamHttpd, &streamUri);

  cameraServerRunning = true;
  Serial.println("[HTTP] camera server started");
  Serial.printf("[HTTP] snapshot: http://%s/capture?flash=1\n", activeHostIp().c_str());
  Serial.printf("[HTTP] stream  : http://%s:81/stream\n", activeHostIp().c_str());
  return true;
}

bool initCamera() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  if (psramFound()) {
    config.frame_size = CAMERA_FRAME_SIZE;
    config.jpeg_quality = CAMERA_JPEG_QUALITY;
    config.fb_count = 3;
  } else {
    config.frame_size = FRAMESIZE_QVGA;
    config.jpeg_quality = 18;
    config.fb_count = 1;
  }

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("[CAM] init failed 0x%x\n", err);
    return false;
  }

  sensor_t* s = esp_camera_sensor_get();
  if (s) {
    s->set_brightness(s, 0);
    s->set_contrast(s, 1);
    s->set_saturation(s, 0);
    s->set_framesize(s, CAMERA_FRAME_SIZE);
    s->set_quality(s, CAMERA_JPEG_QUALITY);
  }

  pinMode(FLASH_LED_PIN, OUTPUT);
  setFlashState(false);
  Serial.println("[CAM] camera initialized");
  return true;
}

void setup() {
  Serial.begin(115200);
  delay(250);
  Serial.println("\n[BOOT] cam_door ESP32-CAM start");

  WiFi.onEvent(onWiFiEvent);
  loadRuntimeConfigFromStorage();

  if (!forceSetupApOnBoot && hasRuntimeWiFiConfig()) {
    connectWiFiBlocking();
  } else {
    startSetupAP(forceSetupApOnBoot ? "forced_setup" : "unconfigured");
  }

  if (!initCamera()) {
    Serial.println("[BOOT] camera init failed, rebooting in 5s");
    delay(5000);
    ESP.restart();
  }

  if (WiFi.status() == WL_CONNECTED) {
    provisionState = PROVISION_CONNECTED;
  }
}

void loop() {
  handleSetupApTimeout();
  maintainWiFiConnection();

  if (pendingDisableSetupAp && setupApActive && WiFi.status() == WL_CONNECTED) {
    bool graceElapsed =
        (setupApDisableAtMs == 0) ||
        (static_cast<int32_t>(millis() - setupApDisableAtMs) >= 0);
    if (graceElapsed) {
      stopSetupAP(false);
    }
  }

  refreshMdnsState();

  bool shouldServeHttp = setupApActive || (WiFi.status() == WL_CONNECTED);
  if (shouldServeHttp) {
    if (!cameraServerRunning) {
      startCameraServer();
    }
  } else if (cameraServerRunning) {
    stopCameraServer();
    setFlashState(false);
    Serial.println("[NET] no AP/STA link, camera server stopped");
  }

  if (WiFi.status() == WL_CONNECTED) {
    uint32_t now = millis();
    if ((now - lastHeartbeatMs) >= HEARTBEAT_INTERVAL_MS) {
      lastHeartbeatMs = now;
      String note = "ip=" + WiFi.localIP().toString() + " rssi=" +
                    String(WiFi.RSSI()) + " stream=http://" +
                    WiFi.localIP().toString() + ":81/stream";
      emitEvent("CAM_HEARTBEAT", 0.0f, "na", note);
    }
  }

  processPendingEvent();
  delay(20);
}
