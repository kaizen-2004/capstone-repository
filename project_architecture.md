
---

# Final Project Architecture

## Project Title

**Real-Time Intruder and Fire Monitoring Alert System Using IoT-Based Sensor Fusion and Event-Driven Facial Recognition with Night-Vision Cameras**

---

## 1. Architectural Overview

The proposed system is a **PC-based, local-first, event-driven security and fire monitoring platform** designed for condominium use. It integrates:

* **ESP32-C3 IoT sensor nodes**
* **two RTSP IP night-vision cameras**
* **a Windows 10 target PC**
* **OpenCV-based selective facial recognition**
* **smoke-first fire detection with camera confirmation**
* **desktop-based monitoring and control**
* **optional Telegram notifications**
* **secure remote access through Tailscale**
* **responsive mobile web access**

The architecture is intentionally designed for a **CPU-only Intel i5 PC with 16GB RAM**, so the system uses **lightweight continuous monitoring** and only performs **heavier image analysis when triggered by relevant events**.

---

## 2. Deployment Context

### Target Deployment Environment

* **OS:** Windows 10
* **CPU:** Intel i5
* **RAM:** 16GB
* **Operation:** intended for **24/7 use**
* **Demo duration:** approximately **half day**

### Deployment Style

The final system will be delivered through a **one-time Windows installer**. After installation, the user launches the system normally through the desktop shortcut or installed application entry.

The system must:

* start from the installed application
* initialize its local backend automatically
* connect to sensors and cameras
* function even without internet
* disable internet-dependent features until connectivity returns

---

## 3. System Design Philosophy

The architecture follows these core principles:

### Local-first operation

All core monitoring and detection functions run on the target PC inside the local network.

### Event-driven computation

Heavy processing such as face matching is not run continuously. It is triggered only when relevant events occur.

### Sensor-assisted decision making

Fire detection is primarily triggered by smoke sensors, with camera analysis used for confirmation. Intrusion-related processing is strengthened by door-force sensing.

### Staged enhancement

The architecture separates:

* **core system to be built this term**
  from
* **future enhancements**, including Telegram alerts, Tailscale remote access, and mobile access

---

## 4. Hardware Architecture

## A. Central Processing Unit

### Target PC

The target PC serves as the central processing and control node.

Responsibilities:

* receives sensor data from ESP32 nodes
* receives RTSP streams from IP cameras
* performs event analysis and face matching
* stores events, logs, and snapshots
* hosts the dashboard backend
* generates local alerts
* supports remote access and notifications when enabled

---

## B. Sensor Layer

The IoT sensor layer uses **three ESP32-C3 Super Mini nodes** connected over Wi-Fi.

### Node 1: Smoke Sensor Node

* monitors smoke level in one indoor area
* sends sensor readings and alerts to the PC backend via HTTP

### Node 2: Smoke Sensor Node

* monitors smoke level in another indoor area
* improves coverage and detection reliability

### Node 3: Door Motion/Force Node

* attached to the doorknob or door mechanism
* uses a gyroscope/IMU to detect abnormal force spikes or suspicious motion patterns
* used for tamper/forced-entry detection

### Sensor Communication Method

Final deployed communication is:

* **HTTP-based**
* not MQTT

Each ESP32 node:

* connects to Wi-Fi
* obtains an IP address
* registers itself to the backend
* sends heartbeats
* sends sensor readings and event triggers

---

## C. Camera Layer

The camera layer uses **two IP night-vision cameras** with RTSP streaming.

### Camera 1: Indoor Camera

Used for:

* indoor person presence detection
* visual fire/flame confirmation
* selective face matching when relevant

### Camera 2: Door-Facing Camera

Used for:

* person detection near entry
* selective face matching for visitors/intruders
* correlation with doorknob force anomalies

### Camera Processing Settings

For CPU efficiency:

* **720p**
* **10 to 15 FPS for processing**

Both camera streams remain open, but **heavy processing is only applied to the triggered camera**.

---

## 5. Software Architecture

## A. Desktop Application Layer

The primary user interface is a **Windows desktop application**.

Recommended implementation:

* **React frontend**
* **browser-based dashboard UI**
* backend launched automatically by the app

### Desktop App Functions

* live dashboard
* alert list
* event acknowledgment
* device status monitoring
* authorized-user management
* system settings
* logs and reports
* camera and node status display

### User Scope

* **single admin user**
* supports **multiple authorized faces**
* does not support multiple system user accounts

### Authentication

The dashboard uses **simple login authentication** for system access.

---

## B. Local Backend Layer

The backend runs locally on the target PC and acts as the main control engine.

Recommended implementation:

* **Python backend**
* **FastAPI**
* packaged for Windows deployment and started locally for browser access

### Main Backend Modules

#### 1. API Layer

Handles:

* dashboard requests
* mobile dashboard requests
* node registration
* event retrieval
* acknowledgment actions
* authorized-user operations
* settings retrieval and update

#### 2. Device Registry

Tracks:

* sensor node identity
* node IP address
* last heartbeat
* online/offline status
* disconnection state

#### 3. Camera Stream Manager

Handles:

* RTSP stream connection
* frame acquisition
* buffering
* reconnection attempts
* disconnection detection

#### 4. Sensor Fusion Engine

Combines:

* smoke sensor inputs
* door-force anomalies
* motion/person presence
* face matching results
* flame-confirmation results

#### 5. Face Recognition Module

Used only for:

* **authorized vs unknown**
* event-triggered face matching
* storing snapshots related to intruder events

This module prioritizes a **balanced approach leaning toward accuracy**.

#### 6. Fire Detection Module

Uses:

* smoke sensors as primary trigger
* indoor camera as confirmation source

This avoids heavy continuous vision-based fire detection and reduces false alarms.

#### 7. Alert Manager

Creates and classifies alerts by:

* source
* type
* severity
* acknowledgment state

#### 8. Notification Manager

Handles:

* local desktop notifications
* alarm sound
* popup alerts
* Telegram alerts in enhancement phase

#### 9. Reporting and Cleanup Module

Handles:

* daily summaries
* event counts
* authorized vs unknown statistics
* automated retention cleanup

---

## 6. Face Enrollment Architecture

The system uses a **hybrid face enrollment approach**.

### Primary Enrollment Method

Face images are initially captured using a **phone** through the responsive mobile dashboard.

### Secondary Enrollment Improvement

After phone-based enrollment, the system automatically captures additional face samples from the **deployed IP camera** when the user stands in front of it.

### Why this is used

This hybrid method improves robustness by including:

* better-quality phone-captured images
* in-situ camera-captured images
* real deployment lighting conditions
* actual angle and camera characteristics

### Processing Flow

* phone captures face images
* images are uploaded to the PC backend
* PC validates image quality
* PC performs face encoding/extraction
* user record is created or updated
* when the person appears in front of the IP camera, additional samples are automatically captured
* those additional samples are stored to improve matching reliability

### Important Note

The phone is only used for **capture and submission**.
The **PC performs enrollment, encoding, registration, and face matching**.

---

## 7. Detection Architecture

## A. Continuous Lightweight Processes

These run continuously:

* camera stream health monitoring
* sensor heartbeat monitoring
* smoke threshold monitoring
* door-force anomaly monitoring
* lightweight motion/person presence checks

## B. Event-Triggered Heavy Processes

These run only when relevant events occur:

* face detection and face matching
* deeper frame analysis
* snapshot capture
* event escalation logic

This is essential because the system is designed for a **CPU-only PC**.

---

## 8. Intruder Detection Logic

The intrusion pipeline works as follows:

### Trigger Conditions

* door camera detects a person
* door-force node detects abnormal force spikes
* suspicious motion pattern near entry

### Event Flow

1. trigger is detected
2. relevant camera frames are captured
3. face matching runs on selected frames
4. result is classified as:

   * authorized
   * unknown
5. event is logged
6. popup, sound, and highlighted alert are shown
7. acknowledgment is required

---

## 9. Fire Detection Logic

The fire pipeline follows a smoke-first strategy.

### Trigger Conditions

* smoke sensor exceeds threshold

### Confirmation Layer

* indoor camera checks for visual signs consistent with flame/fire

### Event Flow

1. smoke anomaly is detected
2. indoor camera confirmation is attempted
3. backend fuses both results
4. event is classified by severity
5. alert is triggered
6. event is logged
7. acknowledgment is required

This architecture gives better reliability while keeping CPU usage manageable.

---

## 10. Alerting Behavior

When an important event occurs, the system must:

* show a **popup**
* play a **sound**
* visually **highlight the alert**
* require **acknowledgment**

This applies especially to:

* fire alerts
* unknown face detections
* door tampering events
* combined critical alerts

---

## 11. Failure Handling and Resilience

The system is designed to show failure states clearly and recover when possible.

### Camera Failure Handling

If a camera disconnects:

* system marks it as disconnected
* warning is shown on dashboard
* automatic reconnection is attempted
* if timeout is exceeded, alert is raised

### ESP32 Node Failure Handling

If a node stops sending heartbeats:

* node is marked offline
* dashboard shows disconnection
* timeout-based alert is generated

### Internet Failure Handling

If internet is unavailable:

* local monitoring continues
* local dashboard continues
* local alerts continue
* Telegram, Tailscale, and other internet-dependent features are disabled until connectivity returns

---

## 12. Data Storage Architecture

The system uses a local database and file-based storage.

### Recommended Storage

* **SQLite** for structured records
* local folders for snapshots and logs

### Main Data Categories

* authorized user records
* event history
* alert acknowledgment state
* sensor node status
* camera status
* captured snapshots
* system logs

---

## 13. Data Retention Policy

The approved retention policy is:

* **Event history:** 90 days
* **Regular snapshots:** 30 days
* **Critical snapshots:** 90 days
* **System logs:** 30 days
* **Authorized user records:** until manually removed

### Cleanup Method

Cleanup is performed automatically through a **background job**.

This prevents unnecessary storage growth during long-term operation.

---

## 14. Security and Access Control

### Local Dashboard Access

Protected with **simple login authentication**

### User Model

* one admin account
* multiple authorized faces
* no multiple system-user roles

### Remote Access Permissions

When remote access is enabled, the admin can:

* view alerts
* view system status
* acknowledge events
* manage authorized users

---

## 15. Remote and Enhancement Architecture

These are added **after the core system is stable**.

## Phase 1: Core Features to Be Built This Term

This includes:

* Windows local dashboard deployment
* local backend
* HTTP-based ESP32 node integration
* indoor and door RTSP camera integration
* smoke-first fire detection with camera confirmation
* event-driven authorized-vs-unknown face matching
* desktop popup/sound/highlight alerts
* login-protected dashboard
* local logging and retention cleanup
* offline-capable local operation
* hybrid face enrollment:

  * phone capture
  * automatic additional IP camera samples

---

## Phase 2: Telegram Bot Notification

After core implementation, add Telegram support.

### Telegram Scope

* notification
* basic command/status
* acknowledgment only

### Example Bot Functions

* send fire alert
* send intruder alert
* send critical alert
* `/status`
* `/latest`
* `/alerts`
* `/ack <event_id>`

Telegram is not the main control interface. It is a **lightweight remote alert and response channel**.

---

## Phase 3: Remote Access Through Tailscale

After Telegram support, add secure remote access via Tailscale.

### Tailscale Role

* secure remote connection to the local system
* no direct public exposure of the backend
* safe access from authorized remote devices

This allows the admin to access the system from outside the local network.

---

## Phase 4: Responsive Mobile Web Dashboard

Instead of building a separate mobile app first, the system will provide a **responsive mobile web dashboard** accessible over Tailscale.

### Mobile Dashboard Functions

* view alerts
* view system/device status
* view recent snapshots
* acknowledge events
* submit face images for enrollment
* assist with authorized-user management

### Mobile Scope Limitation

The mobile dashboard is mainly for:

* monitoring
* acknowledgment
* enrollment capture support

The local dashboard remains the primary full-control interface.

---

## 16. Communication Flow

### Sensor Flow

ESP32-C3 node
→ connects to Wi-Fi
→ registers to backend through HTTP
→ sends heartbeat and readings
→ backend updates device state and evaluates triggers

### Camera Flow

RTSP camera
→ stream opened by backend
→ lightweight monitoring runs
→ triggered frame analysis occurs only when necessary

### Enrollment Flow

Phone capture
→ image upload to backend
→ PC validates and encodes faces
→ authorized record stored
→ additional IP camera samples captured when available

### Alert Flow

trigger detected
→ backend classifies event
→ alert stored
→ popup/sound/highlight shown
→ acknowledgment required
→ Telegram notification sent if enhancement phase is enabled

---

## 17. Performance Strategy

To fit the target hardware, the system uses these optimization rules:

* 720p at 10–15 FPS for processing
* both streams open, but heavy processing only on triggered camera
* face matching only when triggered
* smoke sensors act as primary fire trigger
* accuracy is prioritized slightly over speed, but kept balanced
* automatic cleanup prevents storage overload

---

## 18. Final Summary Statement

The finalized project architecture is a **Windows-deployed, PC-based, local-first, event-driven intruder and fire monitoring system** that integrates ESP32-C3 sensor nodes, RTSP IP night-vision cameras, smoke-priority fire detection, authorized-vs-unknown facial recognition, hybrid face enrollment, dashboard-based monitoring, automatic logging, and offline-capable operation, with future enhancement phases for Telegram notification, Tailscale-secured remote access, and a responsive mobile web dashboard.

---

## 19. Simplified Block Diagram Version

```text
ESP32-C3 Smoke Node 1        ESP32-C3 Smoke Node 2        ESP32-C3 Door Force Node
         │                            │                              │
         └─────────────── Local Wi-Fi / HTTP Communication ─────────┘
                                         │
                                         ▼
                              Windows 10 Target PC
                    ┌──────────────────────────────────────┐
                    │ Local Backend / Processing Engine    │
                    │ - Device Registry                    │
                    │ - Sensor Fusion                      │
                    │ - Face Matching                      │
                    │ - Fire Confirmation                  │
                    │ - Event Logging                      │
                    │ - Alerts / Cleanup                   │
                    └──────────────────────────────────────┘
                               │                     │
                               ▼                     ▼
                     Indoor RTSP IP Camera    Door RTSP IP Camera
                               │                     │
                               └──────────┬──────────┘
                                          ▼
                           Windows Desktop Monitoring App
                           - Login
                           - Alerts
                           - Acknowledge
                           - Manage Authorized Users
                                          │
                      ┌───────────────────┼───────────────────┐
                      ▼                   ▼                   ▼
             Local Popup/Sound      Telegram Bot       Tailscale Remote Access
                                                           │
                                                           ▼
                                              Responsive Mobile Web Dashboard
```

