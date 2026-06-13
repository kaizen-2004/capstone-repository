# IntruFlare - Real-Time Intruder and Fire Monitoring System

> An intelligent home security system that detects intruders and fires in real time, identifies faces, answers questions about system status, and sends instant alerts -- all running locally on a single Windows PC with no cloud dependency.

---

## The Problem

Residential safety systems are often fragmented. Smoke alarms, motion sensors, cameras, and door locks usually operate separately, which delays response and makes incidents harder to verify. Single-sensor systems produce false alarms with no supporting evidence.

**IntruFlare solves this** by combining IoT sensors, night-vision cameras, and artificial intelligence into one unified monitoring system that detects threats, verifies them with visual evidence, and alerts the user immediately.

## How It Works

```
  PHYSICAL SENSORS                  CAMERAS
  ┌──────────────────┐         ┌──────────────────┐
  │ Smoke sensors (x2)│         │ Indoor night-    │
  │ Door tamper sensor│         │ vision camera    │
  │ (IMU gyroscope)   │         │ Door camera      │
  └────────┬─────────┘         └────────┬─────────┘
           │                            │
           └────────────┬───────────────┘
                        ▼
           ┌────────────────────────┐
           │   WINDOWS 10 PC        │
           │   (local processing)   │
           │                        │
           │   AI verifies:         │
           │   • Is this really     │
           │     fire or just smoke?│
           │   • Is this person     │
           │     a resident or a    │
           │     stranger?          │
           │                        │
           │   Event engine decides │
           │   what alerts to send  │
           └───────────┬────────────┘
                       │
           ┌───────────┼────────────┐
           ▼           ▼            ▼
       Web Dashboard  Mobile App  Telegram
       (browser)    (phone/tablet)  Bot
```

---

## Web Dashboard

The **React-based web dashboard** is the main monitoring hub, accessible from any browser on the local network.

| Page | What It Does |
|------|-------------|
| **Dashboard** | KPI cards showing system health, active alerts, online nodes, and recent activity at a glance |
| **Live Monitoring** | Real-time camera feeds with live status indicators for each sensor node |
| **Events & Alerts** | Chronological event log with snapshot evidence, severity levels, and one-click acknowledgment |
| **Sensors & Nodes** | Status of every ESP32 sensor board and camera -- online/offline, last heartbeat, location |
| **Statistics** | Charts and daily trends for incident frequency, response times, and node uptime |
| **Settings** | Runtime configuration, face enrollment tools, integration setup (Telegram, Tailscale, Web Push) |

**Key capabilities:**
- Login-protected single-admin access
- Live camera snapshot overlays with face bounding boxes
- Alert acknowledgment workflow with evidence review
- Face enrollment via image upload and live camera capture
- Daily PDF report generation with metrics and 7-day trend graphs
- Runtime settings that update without restarting the server

---

## Mobile App with Intelligent Assistant

The **Flutter companion app** (IntruFlare / Condo Guardian) provides a handheld monitoring experience for Android devices.

### App Screens

| Screen | Purpose |
|--------|---------|
| **Home** | System snapshot: alert count, online nodes, sensor readings, quick-action buttons |
| **Monitor** | Live camera feeds (embedded WebView of the mobile dashboard route) |
| **Alerts** | Active alert list with polling refresh, severity indicators, and acknowledgment |
| **Events** | Historical event log with snapshot evidence |
| **Snapshots** | Browse and review captured evidence images |
| **Face Enrollment** | Capture photos via phone camera for face recognition training |
| **Assistant** | AI-powered Q&A about system status (see below) |
| **Settings** | Backend URL, connection preferences, polling interval |

### System Assistant (RAG-based Q&A)

The **Assistant screen** provides an intelligent question-answering feature that retrieves live data from the backend and generates contextual responses. Users can ask natural-language questions about the current state of their security system:

| Question | What It Answers |
|----------|----------------|
| "What is the current system status?" | Online node count, active alerts, overall health |
| "What triggered the latest alert?" | Most recent alert title, source, location, and reason |
| "Which node detected smoke?" | Identifies the specific smoke sensor and its location |
| "Are any nodes offline?" | Lists disconnected nodes with suggested troubleshooting |
| "What intrusion events were logged?" | Recent forced-entry or unknown-person detections |
| "Explain the current warning" | Context and recommended action for active warnings |

Each answer includes **context** (why the answer matters) and a **suggested action** (what the user should do next). Responses appear with a typewriter animation for a conversational feel.

### Other Mobile Features

- **Push notifications** via Web Push (VAPID) when configured
- **Telegram fallback** for alert delivery and access link sharing
- **Daily PDF report export** directly to the phone (Android)
- **Persistent alerts** that remain visible until the user acknowledges them
- **Text-to-speech** channel for spoken alert announcements on Android

---

## AI and Computer Vision

### Face Recognition

When an intruder sensor triggers, the system captures a camera frame and runs **two-stage face analysis**:

1. **Detection** (SCRFD model) -- Locates faces in the image
2. **Recognition** (ArcFace model) -- Compares detected faces against enrolled authorized residents

Results fall into three categories:
- **Authorized** -- Recognized resident (informational log)
- **Unknown** -- Unrecognized person (triggers intruder alert)
- **Uncertain** -- Face detected but confidence too low (escalated for user review)

Face enrollment is done through the dashboard or mobile app -- upload a photo or capture live from the camera, and the system trains the recognition model locally.

### Fire Detection

The fire detection pipeline uses a **two-step verification** approach:

1. **Smoke sensor triggers first** -- MQ-2 sensors detect elevated smoke levels and send an immediate alert
2. **Camera confirms visually** -- YOLOv8s AI model analyzes the camera frame for fire/flame patterns

This reduces false alarms: cooking steam triggers the smoke sensor, but the camera confirms whether actual fire is present before escalating to a critical alert.

---

## Sensor Network

| Sensor Node | Location | Hardware | Detects |
|------------|----------|----------|---------|
| Smoke Node 1 | Living Room | ESP32-C3 + MQ-2 | Smoke, fire conditions |
| Smoke Node 2 | Door Entrance | ESP32-C3 + MQ-2 | Smoke, fire conditions |
| Door Force | Door Entrance | ESP32-C3 + GY-LSM6DS3 IMU | Forced entry, tampering |
| Indoor Camera | Living Room | RTSP night-vision | Visual evidence, face recognition |
| Door Camera | Door Entrance | RTSP night-vision / ESP32-CAM | Visual evidence, face recognition |

All sensor nodes communicate wirelessly over Wi-Fi using HTTP. Each node self-registers with the backend on boot and sends periodic heartbeats to confirm it is online.

---

## Event-Driven Architecture

The system is **event-driven**, not continuously polling for heavy analysis:

- **Always running (lightweight):** Camera health monitoring, sensor heartbeats, smoke level checks
- **Triggered on demand (heavy):** Face recognition, fire visual confirmation, snapshot capture

This design keeps the system responsive on consumer hardware (Intel i5, 16 GB RAM) while still providing intelligent analysis when it matters.

### Alert Workflow

```
Sensor trigger → Event engine processes → Camera captures evidence
→ AI analyzes (face/fire) → Alert created → Dashboard updates
→ Mobile notification sent → User reviews & acknowledges
```

---

## Remote Access and Notifications

All core monitoring works **offline on the local network**. When internet is available, optional enhancements activate:

| Feature | How It Works |
|---------|-------------|
| **Web Push** | Browser/phone notifications via VAPID keys |
| **Telegram Bot** | Alert messages and access links delivered to a Telegram chat |
| **Tailscale** | Secure remote access from anywhere via Tailscale VPN |
| **mDNS** | Automatic local network discovery (`thesis-monitor.local`) |
| **LAN Access** | Direct IP-based access for devices on the same network |

---

## Key Results

From testing in a controlled condo-like environment:

| Metric | Result |
|--------|--------|
| Overall classification accuracy | **83.33%** (40/48 trials) |
| Face recognition accuracy | **88.89%** |
| Smoke/fire detection accuracy | **80.00%** |
| Door-force/intruder detection accuracy | **80.00%** |
| Mean event-to-alert response time | **0.032 seconds** |
| Maximum observed latency | **1.0 second** |

---

## Quick Start

### Requirements
- Windows 10 PC
- Python 3.11+ and Node.js 20+
- RTSP IP cameras (or USB webcams for testing)
- ESP32-C3 sensor boards (optional for full demo)

### Install and Run

```bash
git clone <repo-url> && cd thesis
cp .env.example .env

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python backend/run_backend.py
```

### Build the Dashboard

```bash
cd web_dashboard_ui
npm install
npm run build
```

### Access

| URL | Description |
|-----|-------------|
| `http://127.0.0.1:8765/dashboard` | Web dashboard |
| `http://127.0.0.1:8765/dashboard/remote/mobile` | Mobile-optimized view |

**Default login:** `admin` / `admin123`

### Windows Installer

Download `IntruFlare-Setup-v2.2.0.exe` for a one-click desktop installation. Requires the AI model pack (`IntruFlare-AI-Models-v2.2.0.zip`).

---

## Sustainable Development Goals

This project supports:

- **SDG 3** (Good Health and Well-Being) -- Faster awareness of fire hazards and security threats
- **SDG 9** (Industry, Innovation and Infrastructure) -- Affordable integrated safety using IoT and AI
- **SDG 11** (Sustainable Cities and Communities) -- Safer residential spaces through continuous monitoring
- **SDG 13** (Climate Action) -- Earlier fire warning reduces escalation and environmental impact
- **SDG 16** (Peace, Justice and Strong Institutions) -- Structured logs and evidence improve accountability

---

## Project Structure

```
thesis/
├── backend/                    # Python backend (FastAPI + SQLite + AI models)
│   ├── app/api/                # 65 REST endpoints
│   ├── app/modules/            # Event engine, face service, fire service
│   └── app/services/           # Camera, notifications, remote access, reports
├── web_dashboard_ui/           # React dashboard (TypeScript + Tailwind CSS)
├── condo_guardian_app/         # Flutter mobile companion app
├── firmware/http/              # ESP32 sensor node firmware
├── scripts/                    # Build and test automation
├── installer/                  # Windows installer scripts
└── docs/                       # User manual, architecture, deployment guides
```

---

## License

Internal thesis project. Not published under an open-source license.
