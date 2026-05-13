#include <Wire.h>
#include <math.h>

/*
  Door-force IMU calibration sketch

  Purpose:
  - Serial Monitor only. No Wi-Fi, HTTP, backend events, or alerts.
  - Calibrates a magnet-mounted LSM6DS3 IMU for weak locked-knob vibration.
  - Uses the verified reed switch wiring only as context in the output.

  Verified reed wiring:
  - Reed COM -> GND
  - Reed NC  -> GPIO4
  - Firmware uses INPUT_PULLUP
  - Door closed = LOW
  - Door open   = HIGH

  Serial Monitor:
  - Baud: 115200
  - Commands: h = help, b = rebuild baseline, q = measure quiet noise,
              r = reset peaks, s = toggle CSV stream
*/

static const int SERIAL_BAUD = 115200;

static const int I2C_SDA_PIN = 8;
static const int I2C_SCL_PIN = 9;
static const uint32_t I2C_CLOCK_HZ = 100000;  // Safer for short jumper wires to the magnet-mounted IMU.

static const int DOOR_REED_PIN = 4;
static const int DOOR_REED_CLOSED_LEVEL = LOW;

// LSM6DS3 register map.
static const uint8_t REG_WHO_AM_I = 0x0F;
static const uint8_t REG_CTRL1_XL = 0x10;
static const uint8_t REG_CTRL2_G = 0x11;
static const uint8_t REG_CTRL3_C = 0x12;
static const uint8_t REG_OUTX_L_G = 0x22;
static const uint8_t WHO_AM_I_VALUE = 0x69;

// 0x50 = 208 Hz output data rate, +/-2 g accel, +/-245 dps gyro.
// These are the most sensitive accel/gyro full-scale ranges used here.
static const uint8_t IMU_ACCEL_CONFIG = 0x50;
static const uint8_t IMU_GYRO_CONFIG = 0x50;

static const uint32_t IMU_RETRY_INTERVAL_MS = 1000;
static const uint32_t SAMPLE_INTERVAL_US = 5000;   // 200 Hz read target.
static const uint32_t CSV_PRINT_INTERVAL_MS = 100; // Optional CSV output rate.
static const uint32_t WINDOW_INTERVAL_MS = 1000;   // Human-readable peak summary rate.
static const uint32_t ADVICE_INTERVAL_MS = 5000;
static const uint16_t BASELINE_SAMPLES = 1000;     // About 5 seconds at 200 Hz.
static const uint16_t QUIET_NOISE_SAMPLES = 1000;  // About 5 seconds at 200 Hz.

struct ImuSample {
  float ax = 0.0f;
  float ay = 0.0f;
  float az = 0.0f;
  float gx = 0.0f;
  float gy = 0.0f;
  float gz = 0.0f;
};

struct Metrics {
  float magG = 0.0f;
  float deltaG = 0.0f;
  float jerkG = 0.0f;
  float gyroMaxDps = 0.0f;
  float gyroMagDps = 0.0f;
};

struct PeakStats {
  float deltaG = 0.0f;
  float jerkG = 0.0f;
  float gyroMaxDps = 0.0f;
  float gyroMagDps = 0.0f;
  uint32_t samples = 0;
};

bool imuReady = false;
bool baselineReady = false;
bool previousSampleReady = false;
bool streamCsvSamples = false;
bool quietCaptureActive = false;
bool quietNoiseReady = false;

uint8_t imuAddress = 0;
uint16_t baselineCount = 0;

float baselineMagG = 1.0f;
float baselineSumMagG = 0.0f;
float baselineMinMagG = 999.0f;
float baselineMaxMagG = -999.0f;
float baselineMaxJerkG = 0.0f;
float baselineMaxGyroMaxDps = 0.0f;
float baselineMaxGyroMagDps = 0.0f;

float idleMaxDeltaG = 0.0f;
float idleMaxJerkG = 0.0f;
float idleMaxGyroMaxDps = 0.0f;
float idleMaxGyroMagDps = 0.0f;

float previousAx = 0.0f;
float previousAy = 0.0f;
float previousAz = 0.0f;

PeakStats windowPeaks;
PeakStats totalPeaks;
PeakStats quietPeaks;

uint16_t quietNoiseCount = 0;

uint32_t lastImuAttemptMs = 0;
uint32_t lastCsvPrintMs = 0;
uint32_t lastWindowMs = 0;
uint32_t lastAdviceMs = 0;
uint32_t lastSampleUs = 0;

float maxFloat(float a, float b) {
  return a > b ? a : b;
}

float absFloat(float value) {
  return value < 0.0f ? -value : value;
}

void resetPeakStats(PeakStats& stats) {
  stats.deltaG = 0.0f;
  stats.jerkG = 0.0f;
  stats.gyroMaxDps = 0.0f;
  stats.gyroMagDps = 0.0f;
  stats.samples = 0;
}

void updatePeakStats(PeakStats& stats, const Metrics& metrics) {
  stats.deltaG = maxFloat(stats.deltaG, metrics.deltaG);
  stats.jerkG = maxFloat(stats.jerkG, metrics.jerkG);
  stats.gyroMaxDps = maxFloat(stats.gyroMaxDps, metrics.gyroMaxDps);
  stats.gyroMagDps = maxFloat(stats.gyroMagDps, metrics.gyroMagDps);
  stats.samples++;
}

const char* levelText(int level) {
  return level == HIGH ? "HIGH" : "LOW";
}

const char* doorStateText() {
  return digitalRead(DOOR_REED_PIN) == DOOR_REED_CLOSED_LEVEL ? "closed" : "open";
}

bool i2cReadBytes(uint8_t addr, uint8_t reg, uint8_t* out, size_t len) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) {
    return false;
  }

  size_t got = Wire.requestFrom(static_cast<int>(addr), static_cast<int>(len));
  if (got != len) {
    return false;
  }

  for (size_t i = 0; i < len; ++i) {
    out[i] = Wire.read();
  }
  return true;
}

bool i2cWriteByte(uint8_t addr, uint8_t reg, uint8_t val) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  Wire.write(val);
  return Wire.endTransmission() == 0;
}

bool configureImu(uint8_t addr) {
  // BDU + register auto-increment.
  if (!i2cWriteByte(addr, REG_CTRL3_C, 0x44)) {
    return false;
  }
  if (!i2cWriteByte(addr, REG_CTRL1_XL, IMU_ACCEL_CONFIG)) {
    return false;
  }
  if (!i2cWriteByte(addr, REG_CTRL2_G, IMU_GYRO_CONFIG)) {
    return false;
  }
  delay(20);
  return true;
}

bool initImuIfNeeded() {
  if (imuReady) {
    return true;
  }

  uint32_t now = millis();
  if ((uint32_t)(now - lastImuAttemptMs) < IMU_RETRY_INTERVAL_MS) {
    return false;
  }
  lastImuAttemptMs = now;

  uint8_t candidates[2] = {0x6A, 0x6B};
  for (uint8_t i = 0; i < 2; ++i) {
    uint8_t addr = candidates[i];
    uint8_t who = 0;
    if (!i2cReadBytes(addr, REG_WHO_AM_I, &who, 1)) {
      continue;
    }
    if (who != WHO_AM_I_VALUE) {
      continue;
    }
    if (!configureImu(addr)) {
      continue;
    }

    imuAddress = addr;
    imuReady = true;
    Serial.printf("# IMU LSM6DS3 ready at 0x%02X\n", imuAddress);
    return true;
  }

  Serial.println("# IMU LSM6DS3 not detected; check VCC/GND/SDA/SCL, retrying...");
  return false;
}

bool readImuSample(ImuSample& sample) {
  if (!imuReady) {
    return false;
  }

  uint8_t raw[12] = {0};
  if (!i2cReadBytes(imuAddress, REG_OUTX_L_G, raw, sizeof(raw))) {
    imuReady = false;
    Serial.println("# IMU read failed; IMU marked offline");
    return false;
  }

  int16_t gxRaw = static_cast<int16_t>((raw[1] << 8) | raw[0]);
  int16_t gyRaw = static_cast<int16_t>((raw[3] << 8) | raw[2]);
  int16_t gzRaw = static_cast<int16_t>((raw[5] << 8) | raw[4]);
  int16_t axRaw = static_cast<int16_t>((raw[7] << 8) | raw[6]);
  int16_t ayRaw = static_cast<int16_t>((raw[9] << 8) | raw[8]);
  int16_t azRaw = static_cast<int16_t>((raw[11] << 8) | raw[10]);

  sample.gx = gxRaw * 0.00875f;
  sample.gy = gyRaw * 0.00875f;
  sample.gz = gzRaw * 0.00875f;
  sample.ax = axRaw * 0.000061f;
  sample.ay = ayRaw * 0.000061f;
  sample.az = azRaw * 0.000061f;
  return true;
}

Metrics calculateMetrics(const ImuSample& sample) {
  Metrics metrics;
  metrics.magG = sqrtf((sample.ax * sample.ax) +
                       (sample.ay * sample.ay) +
                       (sample.az * sample.az));
  metrics.deltaG = baselineReady ? absFloat(metrics.magG - baselineMagG) : 0.0f;

  if (previousSampleReady) {
    float dx = sample.ax - previousAx;
    float dy = sample.ay - previousAy;
    float dz = sample.az - previousAz;
    metrics.jerkG = sqrtf((dx * dx) + (dy * dy) + (dz * dz));
  }

  metrics.gyroMaxDps = maxFloat(absFloat(sample.gx),
                                maxFloat(absFloat(sample.gy), absFloat(sample.gz)));
  metrics.gyroMagDps = sqrtf((sample.gx * sample.gx) +
                             (sample.gy * sample.gy) +
                             (sample.gz * sample.gz));

  previousAx = sample.ax;
  previousAy = sample.ay;
  previousAz = sample.az;
  previousSampleReady = true;

  return metrics;
}

void printCsvHeader() {
  Serial.println("ms,event,door,reed_level,ax_g,ay_g,az_g,gx_dps,gy_dps,gz_dps,mag_g,delta_g,jerk_g,gyro_max_dps,gyro_mag_dps,win_delta_g,win_jerk_g,win_gyro_max_dps,win_gyro_mag_dps,total_delta_g,total_jerk_g,total_gyro_max_dps,total_gyro_mag_dps");
}

void printCsvRow(const char* event, const ImuSample& sample, const Metrics& metrics) {
  Serial.printf(
      "%lu,%s,%s,%s,%.5f,%.5f,%.5f,%.2f,%.2f,%.2f,%.5f,%.5f,%.5f,%.2f,%.2f,%.5f,%.5f,%.2f,%.2f,%.5f,%.5f,%.2f,%.2f\n",
      static_cast<unsigned long>(millis()),
      event,
      doorStateText(),
      levelText(digitalRead(DOOR_REED_PIN)),
      sample.ax,
      sample.ay,
      sample.az,
      sample.gx,
      sample.gy,
      sample.gz,
      metrics.magG,
      metrics.deltaG,
      metrics.jerkG,
      metrics.gyroMaxDps,
      metrics.gyroMagDps,
      windowPeaks.deltaG,
      windowPeaks.jerkG,
      windowPeaks.gyroMaxDps,
      windowPeaks.gyroMagDps,
      totalPeaks.deltaG,
      totalPeaks.jerkG,
      totalPeaks.gyroMaxDps,
      totalPeaks.gyroMagDps);
}

void printWindowSummary(const Metrics& metrics) {
  Serial.printf(
      "WINDOW t=%lu door=%s reed=%s samples=%lu now(delta=%.5f jerk=%.5f gyro=%.2f gyro_mag=%.2f) peak(delta=%.5f jerk=%.5f gyro=%.2f gyro_mag=%.2f) total(delta=%.5f jerk=%.5f gyro=%.2f gyro_mag=%.2f)\n",
      static_cast<unsigned long>(millis()),
      doorStateText(),
      levelText(digitalRead(DOOR_REED_PIN)),
      static_cast<unsigned long>(windowPeaks.samples),
      metrics.deltaG,
      metrics.jerkG,
      metrics.gyroMaxDps,
      metrics.gyroMagDps,
      windowPeaks.deltaG,
      windowPeaks.jerkG,
      windowPeaks.gyroMaxDps,
      windowPeaks.gyroMagDps,
      totalPeaks.deltaG,
      totalPeaks.jerkG,
      totalPeaks.gyroMaxDps,
      totalPeaks.gyroMagDps);
}

void printHelp() {
  Serial.println("# Door-force IMU calibration, serial-only");
  Serial.println("# Keep the magnet-mounted IMU still during baseline, then rotate the outside knob while locked.");
  Serial.println("# Reed context: COM -> GND, NC -> GPIO4, INPUT_PULLUP, closed=LOW, open=HIGH.");
  Serial.println("# Default output is one WINDOW summary per second. Focus on peak(...) values.");
  Serial.println("# Commands: h=help, b=rebuild baseline, q=measure quiet noise, r=reset peaks, s=toggle CSV stream");
  Serial.println("# Flow: baseline completes -> press q and keep still -> press r -> test locked-knob movement.");
  Serial.println("# Production thresholds should be above quiet_x4 and below the weakest real knob attempt peak.");
}

void resetRuntimePeaks() {
  resetPeakStats(windowPeaks);
  resetPeakStats(totalPeaks);
  lastWindowMs = millis();
  lastAdviceMs = millis();
  Serial.println("# Peak totals reset");
}

void resetBaseline() {
  baselineReady = false;
  previousSampleReady = false;
  baselineCount = 0;
  baselineSumMagG = 0.0f;
  baselineMinMagG = 999.0f;
  baselineMaxMagG = -999.0f;
  baselineMaxJerkG = 0.0f;
  baselineMaxGyroMaxDps = 0.0f;
  baselineMaxGyroMagDps = 0.0f;
  idleMaxDeltaG = 0.0f;
  idleMaxJerkG = 0.0f;
  idleMaxGyroMaxDps = 0.0f;
  idleMaxGyroMagDps = 0.0f;
  quietCaptureActive = false;
  quietNoiseReady = false;
  quietNoiseCount = 0;
  resetPeakStats(quietPeaks);
  resetRuntimePeaks();
  Serial.printf("# Building quiet baseline: keep sensor still for %u samples\n",
                static_cast<unsigned>(BASELINE_SAMPLES));
}

void completeBaseline() {
  baselineMagG = baselineSumMagG / static_cast<float>(baselineCount);
  baselineReady = true;
  previousSampleReady = false;
  resetRuntimePeaks();

  Serial.printf("# Baseline complete: mag=%.5f baseline_min=%.5f baseline_max=%.5f\n",
                baselineMagG,
                baselineMinMagG,
                baselineMaxMagG);
  Serial.println("# Press q and keep the sensor still to measure quiet noise before knob trials.");
}

void updateBaseline(const Metrics& metrics) {
  baselineCount++;
  baselineSumMagG += metrics.magG;
  baselineMinMagG = baselineMinMagG < metrics.magG ? baselineMinMagG : metrics.magG;
  baselineMaxMagG = baselineMaxMagG > metrics.magG ? baselineMaxMagG : metrics.magG;
  baselineMaxJerkG = maxFloat(baselineMaxJerkG, metrics.jerkG);
  baselineMaxGyroMaxDps = maxFloat(baselineMaxGyroMaxDps, metrics.gyroMaxDps);
  baselineMaxGyroMagDps = maxFloat(baselineMaxGyroMagDps, metrics.gyroMagDps);

  if (baselineCount == 1 || baselineCount % 100 == 0) {
    Serial.printf("# Baseline progress: %u/%u mag=%.5f gyro=%.2f\n",
                  static_cast<unsigned>(baselineCount),
                  static_cast<unsigned>(BASELINE_SAMPLES),
                  metrics.magG,
                  metrics.gyroMaxDps);
  }

  if (baselineCount >= BASELINE_SAMPLES) {
    completeBaseline();
  }
}

void printAdvice() {
  if (!quietNoiseReady) {
    Serial.println("# quiet_x4 unavailable: press q and keep the sensor still for quiet-noise capture.");
    Serial.printf("# total_peaks: delta=%.5f jerk=%.5f gyro=%.2f gyro_mag=%.2f\n",
                  totalPeaks.deltaG,
                  totalPeaks.jerkG,
                  totalPeaks.gyroMaxDps,
                  totalPeaks.gyroMagDps);
    return;
  }

  Serial.printf("# noise_x4: delta=%.5f jerk=%.5f gyro=%.2f gyro_mag=%.2f\n",
                idleMaxDeltaG * 4.0f,
                idleMaxJerkG * 4.0f,
                idleMaxGyroMaxDps * 4.0f,
                idleMaxGyroMagDps * 4.0f);
  Serial.printf("# total_peaks: delta=%.5f jerk=%.5f gyro=%.2f gyro_mag=%.2f\n",
                totalPeaks.deltaG,
                totalPeaks.jerkG,
                totalPeaks.gyroMaxDps,
                totalPeaks.gyroMagDps);
}

void completeQuietNoiseCapture() {
  idleMaxDeltaG = quietPeaks.deltaG;
  idleMaxJerkG = quietPeaks.jerkG;
  idleMaxGyroMaxDps = quietPeaks.gyroMaxDps;
  idleMaxGyroMagDps = quietPeaks.gyroMagDps;
  quietCaptureActive = false;
  quietNoiseReady = true;
  resetRuntimePeaks();

  Serial.printf("# Quiet noise complete: delta=%.5f jerk=%.5f gyro=%.2f gyro_mag=%.2f\n",
                idleMaxDeltaG,
                idleMaxJerkG,
                idleMaxGyroMaxDps,
                idleMaxGyroMagDps);
  Serial.printf("# quiet_x4: delta=%.5f jerk=%.5f gyro=%.2f gyro_mag=%.2f\n",
                idleMaxDeltaG * 4.0f,
                idleMaxJerkG * 4.0f,
                idleMaxGyroMaxDps * 4.0f,
                idleMaxGyroMagDps * 4.0f);
  Serial.println("# Press r, then perform locked-knob attempts and compare WINDOW peak(...) against quiet_x4.");
}

void startQuietNoiseCapture() {
  if (!baselineReady) {
    Serial.println("# Baseline is not ready yet; wait for baseline complete first.");
    return;
  }

  quietCaptureActive = true;
  quietNoiseReady = false;
  quietNoiseCount = 0;
  resetPeakStats(quietPeaks);
  resetRuntimePeaks();
  Serial.printf("# Quiet noise capture started: keep sensor still for %u samples\n",
                static_cast<unsigned>(QUIET_NOISE_SAMPLES));
}

void updateQuietNoiseCapture(const Metrics& metrics) {
  updatePeakStats(quietPeaks, metrics);
  quietNoiseCount++;

  if (quietNoiseCount == 1 || quietNoiseCount % 200 == 0) {
    Serial.printf("# Quiet progress: %u/%u peak(delta=%.5f jerk=%.5f gyro=%.2f gyro_mag=%.2f)\n",
                  static_cast<unsigned>(quietNoiseCount),
                  static_cast<unsigned>(QUIET_NOISE_SAMPLES),
                  quietPeaks.deltaG,
                  quietPeaks.jerkG,
                  quietPeaks.gyroMaxDps,
                  quietPeaks.gyroMagDps);
  }

  if (quietNoiseCount >= QUIET_NOISE_SAMPLES) {
    completeQuietNoiseCapture();
  }
}

void handleSerialCommand() {
  while (Serial.available() > 0) {
    char c = static_cast<char>(Serial.read());
    if (c == 'h' || c == 'H' || c == '?') {
      printHelp();
    } else if (c == 'b' || c == 'B') {
      resetBaseline();
    } else if (c == 'q' || c == 'Q') {
      startQuietNoiseCapture();
    } else if (c == 'r' || c == 'R') {
      resetRuntimePeaks();
    } else if (c == 's' || c == 'S') {
      streamCsvSamples = !streamCsvSamples;
      Serial.printf("# CSV sample stream %s\n", streamCsvSamples ? "enabled" : "disabled");
      if (streamCsvSamples) {
        printCsvHeader();
      }
    }
  }
}

void setup() {
  Serial.begin(SERIAL_BAUD);
  unsigned long serialWaitStartMs = millis();
  while (!Serial && (uint32_t)(millis() - serialWaitStartMs) < 2000) {
    delay(10);
  }
  delay(250);

  pinMode(DOOR_REED_PIN, INPUT_PULLUP);
  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN, I2C_CLOCK_HZ);

  printHelp();
  Serial.printf("# Boot reed=%s door=%s sda=%d scl=%d i2c=%lu\n",
                levelText(digitalRead(DOOR_REED_PIN)),
                doorStateText(),
                I2C_SDA_PIN,
                I2C_SCL_PIN,
                static_cast<unsigned long>(I2C_CLOCK_HZ));
  resetBaseline();
}

void loop() {
  handleSerialCommand();

  if (!initImuIfNeeded()) {
    delay(20);
    return;
  }

  uint32_t nowUs = micros();
  if ((uint32_t)(nowUs - lastSampleUs) < SAMPLE_INTERVAL_US) {
    return;
  }
  lastSampleUs = nowUs;

  ImuSample sample;
  if (!readImuSample(sample)) {
    return;
  }

  Metrics metrics = calculateMetrics(sample);

  if (!baselineReady) {
    updateBaseline(metrics);
    return;
  }

  if (quietCaptureActive) {
    updateQuietNoiseCapture(metrics);
    return;
  }

  updatePeakStats(windowPeaks, metrics);
  updatePeakStats(totalPeaks, metrics);

  uint32_t now = millis();
  if (streamCsvSamples && (uint32_t)(now - lastCsvPrintMs) >= CSV_PRINT_INTERVAL_MS) {
    lastCsvPrintMs = now;
    printCsvRow("SAMPLE", sample, metrics);
  }

  if ((uint32_t)(now - lastWindowMs) >= WINDOW_INTERVAL_MS) {
    if (streamCsvSamples) {
      printCsvRow("WINDOW", sample, metrics);
    } else {
      printWindowSummary(metrics);
    }
    resetPeakStats(windowPeaks);
    lastWindowMs = now;
  }

  if ((uint32_t)(now - lastAdviceMs) >= ADVICE_INTERVAL_MS) {
    printAdvice();
    lastAdviceMs = now;
  }
}
