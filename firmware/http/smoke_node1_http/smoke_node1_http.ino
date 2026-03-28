#include <WiFi.h>
#include <HTTPClient.h>

// Configure these before flashing.
static const char* WIFI_SSID = "CHANGE_ME";
static const char* WIFI_PASSWORD = "CHANGE_ME";
static const char* BACKEND_BASE = "http://192.168.1.50:8765";

static const char* NODE_ID = "smoke_node1";
static const char* NODE_LABEL = "Smoke Sensor Node 1";
static const char* NODE_LOCATION = "Living Room";

unsigned long lastHeartbeatMs = 0;
unsigned long lastReadingMs = 0;

String endpoint(const char* path) {
  return String(BACKEND_BASE) + path;
}

void postJson(const String& url, const String& body) {
  if (WiFi.status() != WL_CONNECTED) return;
  HTTPClient http;
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  http.POST(body);
  http.end();
}

void sendRegister() {
  String body = String("{") +
    "\"node_id\":\"" + NODE_ID + "\"," +
    "\"label\":\"" + NODE_LABEL + "\"," +
    "\"device_type\":\"smoke\"," +
    "\"location\":\"" + NODE_LOCATION + "\"}";
  postJson(endpoint("/api/devices/register"), body);
}

void sendHeartbeat() {
  String body = String("{") +
    "\"node_id\":\"" + NODE_ID + "\"," +
    "\"note\":\"heartbeat\"}";
  postJson(endpoint("/api/devices/heartbeat"), body);
}

void sendSmokeEvent(float value, const char* eventCode) {
  String body = String("{") +
    "\"node_id\":\"" + NODE_ID + "\"," +
    "\"event\":\"" + eventCode + "\"," +
    "\"location\":\"" + NODE_LOCATION + "\"," +
    "\"value\":" + String(value, 3) + "}";
  postJson(endpoint("/api/sensors/event"), body);
}

void setup() {
  Serial.begin(115200);
  delay(200);

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
  }

  sendRegister();
}

void loop() {
  unsigned long now = millis();

  if (now - lastHeartbeatMs >= 15000) {
    sendHeartbeat();
    lastHeartbeatMs = now;
  }

  if (now - lastReadingMs >= 5000) {
    // Replace with real MQ-2 ADC reading and threshold logic.
    float simulated = (float)(esp_random() % 1000) / 1000.0;
    const char* eventCode = simulated > 0.70 ? "SMOKE_HIGH" : "SMOKE_NORMAL";
    sendSmokeEvent(simulated, eventCode);
    lastReadingMs = now;
  }
}
