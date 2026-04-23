# System Implementation Overview

This section should summarize the final assembled prototype in terms of actual functional modules rather than only hardware list. The narrative may explain that the system integrates camera-based monitoring, smoke sensing, door-force sensing, local alert management, logging, and dashboard visualization. If Raspberry Pi 2 is used in the final deployment, it may be described here as an optional local edge-hosting component.

## Suggested narrative

The developed prototype integrates camera-based monitoring, smoke sensing, and door-force sensing into one local alert workflow. Sensor-event data are received through the HTTP event endpoint, while camera feeds support selective face recognition and smoke-triggered fire confirmation. The backend preserves alerts, events, snapshots, and daily summaries, and the dashboard presents these outputs to the user for monitoring and acknowledgment.

## Table Template: Final Implemented Components

| Component | Role in the System | Status | Remarks |
| --- | --- | --- | --- |
| Camera Input A | [Fill in] | [Fill in] | [Fill in] |
| Camera Input B | [Fill in] | [Fill in] | [Fill in] |
| Smoke Node 1 | [Fill in] | [Fill in] | [Fill in] |
| Smoke Node 2 | [Fill in] | [Fill in] | [Fill in] |
| Door-Force Node | [Fill in] | [Fill in] | [Fill in] |
| Local Monitoring Backend | [Fill in] | [Fill in] | [Fill in] |
| Dashboard Interface | [Fill in] | [Fill in] | [Fill in] |
| Raspberry Pi 2 (optional) | Local edge-hosting component | [Fill in] | [Fill in] |
