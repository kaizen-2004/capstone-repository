Mobile Companion Application Implementation Plan
Overall Feature Goal

Develop a mobile companion application for the condo intruder and fire monitoring system that provides:

secure access to the monitoring dashboard
live camera preview and sensor readings
alert notifications
node provisioning and reconfiguration
an in-app AI assistant using guided FAQ-style queries for event explanations and system queries
Expected Final Output

By the end of development, the system should produce:

a working mobile application
a backend REST-style API (implemented using FastAPI)
a node onboarding workflow for ESP32-C3 sensor nodes
in-app notifications for alerts
an AI assistant interface using predefined FAQ commands connected to backend monitoring data
Minimum Viable Product (MVP)
MVP Goal

Deliver the minimum working thesis demonstration that proves the app is useful and integrated with the monitoring system.

MVP Scope
1. Open the monitoring system inside the app
user can access the dashboard without opening a raw Tailscale link manually
2. View live system status
current sensor readings
current alert state
basic camera preview or dashboard camera feed
3. Receive and view alerts in the app
intrusion alert
smoke/fire alert
node offline warning
4. Provision or reconfigure ESP32-C3 nodes
set Wi-Fi SSID/password
set backend host/IP and port
set node ID / node role
save configuration without reflashing firmware
5. Use a basic in-app AI assistant (FAQ-style)

Provide predefined guided questions such as:

What is the current system status?
What triggered the last alert?
Which node detected smoke?
Are any nodes offline?
Explain the current warning.

The system returns human-readable explanations based on backend data.

MVP Output

A demo-ready mobile app where evaluators can:

open the app
see the monitoring dashboard
observe alerts
provision a node
use the assistant through predefined system questions
MVP Success Criteria

The MVP is successful if:

the app connects to the backend
the dashboard is accessible inside the app
alerts appear in the app
at least one node can be provisioned without reflashing
the AI assistant returns useful responses using predefined questions
Phase 1 — Scope and Architecture Definition
Goal

Define exactly what will be implemented in the thesis demo.

Tasks
finalize app modules:
Home
Monitor
Alerts
Provision Nodes
Assistant
Settings
define what remains in WebView and what becomes native
define app-backend communication
define app-to-node provisioning communication
define minimum demo scenarios
Output
finalized architecture
module list
MVP scope
system flow diagram
Phase 2 — Backend API Preparation
Goal

Prepare the backend so the app can retrieve data and perform actions.

Tasks

Create or expose REST-style endpoints:

/api/health
/api/sensors
/api/alerts
/api/events
/api/nodes
/api/alerts/{id}/acknowledge
/api/assistant/query

Prepare:

JSON responses
dashboard URL for app WebView
assistant context builder using sensor and event data
Output

A mobile-ready backend API implemented with FastAPI.

Phase 3 — Mobile App Shell
Goal

Create the base Flutter application structure.

Tasks
initialize Flutter project
create app navigation
create placeholder screens
store backend/Tailscale base URL in settings
add loading and error handling
create reusable UI components
Output

A working mobile app shell.

Phase 4 — Monitoring Integration
Goal

Allow users to monitor the system from the app.

Tasks
embed dashboard using WebView
create Home screen with quick status cards
display:
active alerts
node health
latest readings
show live camera preview
add refresh/update logic
Output

Monitoring is visible inside the app.

Phase 5 — In-App Alerts and Notifications
Goal

Allow app-based notification and alert review.

Tasks
define notification types:
intrusion detected
smoke/fire alert
node offline
camera offline
build Alerts screen
implement polling or websocket updates
trigger local app notifications
allow alert acknowledgment
Output

Integrated alert system in the app.

Phase 6 — Node Provisioning
Goal

Configure ESP32-C3 nodes without reflashing.

Tasks on Node Side

Store in NVS/Preferences:

Wi-Fi SSID
Wi-Fi password
backend host
backend port
node ID
node type / room

Implement:

missing config detection
repeated connection failure detection
AP setup mode
local configuration API/page
save configuration and reboot
Tasks on App Side

Create provisioning screen allowing:

SSID entry
password entry
backend host/IP entry
port entry
node ID entry
node type/room selection

Send configuration to node and display success/failure.

Output

Working onboarding and reconfiguration workflow.

Phase 7 — In-App AI Assistant (Guided FAQ)
Goal

Provide AI-assisted system explanations using predefined guided questions.

Tasks

Create Assistant screen with selectable commands such as:

What is the current system status?
What triggered the last alert?
Which node detected smoke?
Are any nodes offline?
Show recent intrusion events.
Explain the current warning.

Backend should:

fetch current readings
fetch node statuses
fetch recent alerts/events
apply rule-based interpretation
optionally use an LLM to improve wording
return a concise human-readable explanation
Output

A guided AI assistant that answers predefined system questions.

Phase 8 — Testing and Demo Readiness
Goal

Make the system stable for thesis demonstration.

Tasks

Test:

normal monitoring
intrusion alert scenario
smoke/fire alert scenario
node offline scenario
provisioning scenario
assistant FAQ responses

Improve:

error handling
retries
loading behavior

Prepare:

screenshots
demo script
architecture diagrams
Output

Stable demo-ready mobile companion application.

Recommended Technology Stack
Mobile App
Flutter
WebView (for embedded dashboard)
Backend API
FastAPI
REST-style endpoints
JSON responses
Sensor Nodes
ESP32-C3
Preferences/NVS for configuration storage
Connectivity
Wi-Fi
Tailscale + stable hostname for backend access
Final System Scope Statement

The companion mobile application will be implemented in phases to provide integrated monitoring, alert notification, node provisioning, and AI-assisted system interaction. Core monitoring and configuration features will be completed first through an MVP, while guided FAQ-based intelligent assistance will provide a controlled and reliable event interpretation layer suitable for thesis demonstration.
