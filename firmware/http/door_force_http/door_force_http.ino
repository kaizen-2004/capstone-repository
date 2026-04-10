#include <WiFi.h>
#include <HTTPClient.h>

// Configure these before flashing.
static const char* WIFI_SSID = "Villa";
static const char* WIFI_PASSWORD = "Beliy@f@m_2026";
// Use backend LAN API base URL (no /dashboard suffix).
static const char* BACKEND_BASE = "http://192.168.1.8:8765";

// Adaptive TX power profile:
// - start with moderate TX for join attempts
// - escalate to high TX after repeated failures
// - settle to moderate runtime TX (fallback to low if 11 dBm option is unavailable)
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

static const char* NODE_ID = "door_force";
static const char* NODE_LABEL = "Door Force Node";
static const char* NODE_LOCATION = "Door Entrance Area";

static const uint32_t WIFI_RETRY_INTERVAL_MS = 15000;
static const uint32_t WIFI_CONNECT_TIMEOUT_MS = 20000;
static const uint32_t REGISTER_RETRY_INTERVAL_MS = 10000;
static const uint8_t WIFI_ESCALATE_AFTER_ATTEMPTS = 2;

unsigned long lastHeartbeatMs = 0;
unsigned long lastReadingMs = 0;
unsigned long lastWiFiAttemptMs = 0;
unsigned long lastWiFiBeginMs = 0;
unsigned long lastRegisterAttemptMs = 0;
unsigned long lastWiFiStatusLogMs = 0;
uint8_t wifiConnectAttempts = 0;
bool wasWiFiConnected = false;
bool registrationOk = false;

const char* wlStatusText(wl_status_t s) {
  switch (s) {
    case WL_IDLE_STATUS: return "IDLE";
    case WL_NO_SSID_AVAIL: return "NO_SSID";
    case WL_SCAN_COMPLETED: return "SCAN_DONE";
    case WL_CONNECTED: return "CONNECTED";
    case WL_CONNECT_FAILED: return "CONNECT_FAILED";
    case WL_CONNECTION_LOST: return "CONNECTION_LOST";
    case WL_DISCONNECTED: return "DISCONNECTED";
    default: return "UNKNOWN";
  }
}

const char* reasonText(uint8_t reason) {
  switch (reason) {
    case 2: return "AUTH_EXPIRE";
    case 3: return "AUTH_LEAVE";
    case 4: return "ASSOC_EXPIRE";
    case 6: return "NOT_AUTHED";
    case 7: return "NOT_ASSOCED";
    case 8: return "ASSOC_LEAVE";
    case 15: return "4WAY_HANDSHAKE_TIMEOUT";
    case 201: return "NO_AP_FOUND";
    case 202: return "AUTH_FAIL";
    case 205: return "CONNECTION_FAIL";
    default: return "OTHER";
  }
}

void onWiFiEvent(WiFiEvent_t event, WiFiEventInfo_t info) {
  switch (event) {
    case ARDUINO_EVENT_WIFI_STA_CONNECTED:
      Serial.println("[WiFi] associated with AP");
      break;
    case ARDUINO_EVENT_WIFI_STA_GOT_IP:
      Serial.printf("[WiFi] got ip=%s rssi=%d\n", WiFi.localIP().toString().c_str(), WiFi.RSSI());
      break;
    case ARDUINO_EVENT_WIFI_STA_DISCONNECTED:
      Serial.printf(
        "[WiFi] disconnected reason=%u (%s) status=%s\n",
        info.wifi_sta_disconnected.reason,
        reasonText(info.wifi_sta_disconnected.reason),
        wlStatusText(WiFi.status())
      );
      break;
    default:
      break;
  }
}

String endpoint(const char* path) {
  return String(BACKEND_BASE) + path;
}

bool postJson(const String& url, const String& body) {
  if (WiFi.status() != WL_CONNECTED) return false;
  HTTPClient http;
  http.setConnectTimeout(3000);
  http.setTimeout(4000);
  http.begin(url);
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

#if defined(WIFI_TX_POWER_CONNECT_INITIAL) && defined(WIFI_TX_POWER_CONNECT_ESCALATED)
wifi_power_t currentConnectTxPower() {
  if (wifiConnectAttempts >= WIFI_ESCALATE_AFTER_ATTEMPTS) {
    return WIFI_TX_POWER_CONNECT_ESCALATED;
  }
  return WIFI_TX_POWER_CONNECT_INITIAL;
}
#endif

void beginWiFiConnection() {
#if defined(WIFI_TX_POWER_CONNECT_INITIAL) && defined(WIFI_TX_POWER_CONNECT_ESCALATED)
  WiFi.setTxPower(currentConnectTxPower());
#endif
  WiFi.setSleep(false);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  lastWiFiBeginMs = millis();
  bool escalated = wifiConnectAttempts >= WIFI_ESCALATE_AFTER_ATTEMPTS;
  Serial.printf(
    "[WiFi] connecting ssid=%s tx=%s attempt=%u\n",
    WIFI_SSID,
    escalated ? "escalated" : "initial",
    (unsigned)(wifiConnectAttempts + 1)
  );
}

void ensureWiFi() {
  wl_status_t status = WiFi.status();
  if (status == WL_CONNECTED) return;

  unsigned long now = millis();
  if ((uint32_t)(now - lastWiFiBeginMs) < WIFI_CONNECT_TIMEOUT_MS) return;
  if ((uint32_t)(now - lastWiFiAttemptMs) < WIFI_RETRY_INTERVAL_MS) return;
  if (status != WL_DISCONNECTED && status != WL_CONNECT_FAILED && status != WL_NO_SSID_AVAIL) return;

  lastWiFiAttemptMs = now;
  if (wifiConnectAttempts < 250) {
    wifiConnectAttempts++;
  }
  WiFi.disconnect();
  delay(200);
  beginWiFiConnection();
  Serial.printf("[WiFi] reconnecting status=%d\n", (int)status);
}

void handleWiFiStateChange() {
  bool connected = WiFi.status() == WL_CONNECTED;
  if (connected && !wasWiFiConnected) {
#if defined(WIFI_TX_POWER_RUNTIME)
    WiFi.setTxPower(WIFI_TX_POWER_RUNTIME);
#endif
    WiFi.setSleep(false);
    wifiConnectAttempts = 0;
    Serial.printf("[WiFi] connected ip=%s rssi=%d\n", WiFi.localIP().toString().c_str(), WiFi.RSSI());
    sendRegister();
  } else if (!connected && wasWiFiConnected) {
    Serial.println("[WiFi] disconnected");
    registrationOk = false;
  }
  wasWiFiConnected = connected;
}

void sendRegister() {
  lastRegisterAttemptMs = millis();
  String body = String("{") +
    "\"node_id\":\"" + NODE_ID + "\"," +
    "\"label\":\"" + NODE_LABEL + "\"," +
    "\"device_type\":\"force\"," +
    "\"location\":\"" + NODE_LOCATION + "\"}";
  bool ok = postJson(endpoint("/api/devices/register"), body);
  registrationOk = ok;
  Serial.printf("[HTTP] register %s\n", ok ? "ok" : "failed");
}

void sendHeartbeat() {
  String body = String("{") +
    "\"node_id\":\"" + NODE_ID + "\"," +
    "\"note\":\"heartbeat\"}";
  postJson(endpoint("/api/devices/heartbeat"), body);
}

void sendDoorEvent(float spike, const char* eventCode) {
  String body = String("{") +
    "\"node_id\":\"" + NODE_ID + "\"," +
    "\"event\":\"" + eventCode + "\"," +
    "\"location\":\"" + NODE_LOCATION + "\"," +
    "\"value\":" + String(spike, 3) + "}";
  bool ok = postJson(endpoint("/api/sensors/event"), body);
  if (ok) {
    Serial.printf("[HTTP] event=%s value=%.3f\n", eventCode, spike);
  }
}

void setup() {
  Serial.begin(115200);
  unsigned long serialWaitStartMs = millis();
  while (!Serial && (uint32_t)(millis() - serialWaitStartMs) < 2000) {
    delay(10);
  }
  delay(250);
  Serial.println("\n[BOOT] Door-force HTTP node start");

  WiFi.onEvent(onWiFiEvent);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.setAutoReconnect(false);
  WiFi.persistent(false);

  beginWiFiConnection();
}

void loop() {
  ensureWiFi();
  handleWiFiStateChange();

  if (WiFi.status() != WL_CONNECTED) {
    unsigned long now = millis();
    if ((uint32_t)(now - lastWiFiStatusLogMs) >= 2000) {
      Serial.printf("[WiFi] waiting status=%d attempt=%u\n", (int)WiFi.status(), (unsigned)(wifiConnectAttempts + 1));
      lastWiFiStatusLogMs = now;
    }
    delay(50);
    return;
  }

  unsigned long now = millis();

  if (!registrationOk && (uint32_t)(now - lastRegisterAttemptMs) >= REGISTER_RETRY_INTERVAL_MS) {
    sendRegister();
  }

  if (now - lastHeartbeatMs >= 15000) {
    sendHeartbeat();
    lastHeartbeatMs = now;
  }

  if (now - lastReadingMs >= 3000) {
    // Replace with real IMU spike/motion classification.
    float simulated = (float)(esp_random() % 1000) / 1000.0;
    const char* eventCode = simulated > 0.80 ? "DOOR_FORCE" : "ENTRY_MOTION";
    sendDoorEvent(simulated, eventCode);
    lastReadingMs = now;
  }
}
