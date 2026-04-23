# Phase 3: System Integration and Multi-Sensor Intelligence Layer

The tested modules are combined to build a single continuous prototype that uses facial recognition, fire-related visual analysis, smoke readings, and door-force readings to detect and classify events as normal, intruder-related, or fire-related. Integration tests are carried out first in the laboratory and then in the condo-like environment to ascertain that sensor events result in correct classifications, persistent alerts, and recorded log entries. System-generated logs and daily summaries are gathered.

In the integrated prototype, sensor nodes transmit readings and events to the backend using **HTTP POST + JSON** to a unified endpoint such as `POST /api/sensors/event`. Camera feeds are then used for event-driven visual analysis, especially for selective face recognition and smoke-triggered fire confirmation.
