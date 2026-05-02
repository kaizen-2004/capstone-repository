# Scope and Delimitation

This research covers the conceptualization, development, and controlled evaluation of a local-first intruder and fire monitoring prototype for a condo-like setting.

The implemented system scope is limited to **two monitored areas**:
- **Living Room**
- **Door Entrance Area**

The prototype uses two night-vision-capable camera inputs supported by IR illumination:
- one assigned to the **indoor area**, and
- one assigned to the **door entrance area**.

The exact camera hardware and transport arrangement may vary during development and testing, provided that the system preserves the intended monitoring coverage and event-driven visual analysis workflow.

Sensor coverage includes:
- two ESP32-C3 smoke nodes (`mq2_living`, `mq2_door`) using MQ-2 sensing, and
- one ESP32-C3 door-force node (`door_force`) using a GY-LSM6DS3 inertial sensor.

Sensor-to-server communication is implemented through **HTTP POST + JSON** to `POST /api/sensors/event`.

The system may incorporate **Raspberry Pi 2** as an optional deployment component for local edge hosting. However, this study does not limit the final prototype to one fixed host arrangement; the main concern is the correct integration of sensing, recognition, alerting, and logging functions.

Performance evaluation focuses on controlled scenarios: normal activity, simulated intruder behavior, smoke/flame-related conditions (within safety limits), and nuisance cases such as steam or non-threatening motion. Metrics include face identification performance, fire-related detection performance, door-force detection behavior, and response time.

The investigation is limited to a single-unit prototype and does not include multi-unit deployment, direct integration with external emergency response agencies, or long-term field deployment in occupied condominiums. Remote access and notification channels (e.g., Tailscale and Telegram) are treated as optional layers; core detection, logging, and local dashboard operation remain the primary implementation focus. Dedicated occlusion-aware face analysis (for example, explicit mask or heavy face-covering detection) is treated as out of scope in the present prototype and is reserved for future refinement.
