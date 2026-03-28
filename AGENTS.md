# Always keep the thesis problem statement and objectives aligned with the active architecture.

# Always use the OpenAI developer documentation MCP server for OpenAI API/Codex/ChatGPT SDK tasks.

### Current Implementation Status (2026-03-28)

- **Primary host:** Windows 10 PC (FastAPI backend, local DB, RTSP managers, alert engine).
- **Desktop shell:** Tauri (`desktop/`) with React dashboard (`web_dashboard_ui/`).
- **Monitored areas:** Living Room and Door Entrance Area.
- **Sensor protocol:** HTTP (`POST /api/sensors/event` compatibility retained).
- **Transport implementation status:** Active transport is Wi-Fi HTTP for ESP32-C3 nodes.
- **Camera topology:** RTSP IP cameras (`cam_indoor`, `cam_door`).
- **Enhancement state:** Telegram/Tailscale/mobile remote interfaces are scaffolded and disabled by default.

### Session Context Bootstrap (2026-03-28)

For new coding sessions in this repository, read context in this order:

1. `AGENTS.md`
2. `docs/README.md`
3. `docs/context/CURRENT_STATUS.md`
4. `README.md`

For firmware and sensor transport tasks, additionally read:

5. `docs/instructions/transport/http_quick_start.md`
6. `docs/instructions/transport/http_deployment.md`

For deployment tasks on Windows desktop shell, additionally read:

7. `docs/instructions/deployment/windows_desktop_autostart.md`

If the user says to "use docs directory" or similar, treat `docs/` as the primary project context source and follow the read order above.

### Title

**Real-Time Intruder and Fire Monitoring Alert System Using IoT-Based Sensor Fusion and Event-Driven Facial Recognition with Night-Vision Cameras**

### 1. Main Objective

The main objective of this research is to **design, construct, and evaluate a Windows PC–based real-time intruder and fire monitoring alert system** that uses **RTSP night-vision cameras for OpenCV-based selective facial recognition and visual fire confirmation**, together with **indoor smoke sensors and a door motion/force sensor**, to provide timely and persistent warnings.

### 2. Specific Objectives

1. **Design** the integrated architecture using a Windows target PC, two RTSP IP cameras, ESP32-C3 HTTP sensor nodes, and local-first processing.
2. **Develop** event-driven detection modules for authorized-vs-unknown face matching and smoke-first fire confirmation.
3. **Implement** hardware/software integration for HTTP node registration, heartbeat, sensor ingest, camera stream handling, and multi-sensor fusion.
4. **Generate** daily and period summaries for authorized detections, suspicious/unknown detections, and fire-related events.
5. **Evaluate** reliability/performance for face accuracy, fire detection false-positive/false-negative behavior, and event-to-alert response time.

### Keywords

Windows Local-First, Sensor Fusion, Facial Recognition, Fire Detection, RTSP, ESP32-C3, FastAPI, Tauri
