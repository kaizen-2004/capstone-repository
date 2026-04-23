# Software and System Instruments

OpenCV-based facial detection and recognition module - provides authorized-versus-unknown classification together with similarity or confidence information.  
Fire-related visual analysis module - provides a visual confirmation signal for smoke-triggered fire evaluation.  
Smoke sensing module - yields readings for each MQ-2 sensor together with smoke/no-smoke flags.  
Door-force sensing module - interprets GY-LSM6DS3 inertial readings to generate door-force or forced-entry events.  
Local monitoring interface - presents live status, alerts, events, snapshots, settings, and daily summaries.  
SQLite-backed event and alert store - preserves logs, acknowledgments, and summary data for later analysis.  

## Camera acquisition and transport (implementation notes)
- Camera sources are configured according to the available deployment setup while preserving one indoor monitoring view and one door-area monitoring view.  
- The system supports local monitoring and event-driven visual analysis using the configured camera feeds.

## Sensor node communication (implementation notes)
- ESP32-based nodes submit readings and events via **HTTP POST + JSON** to `POST /api/sensors/event`.  
- Typical JSON fields include: `node`, `event`, optional `room`, `value`, `unit`, `ts`, and `note`.  
- This transport allows local sensor events to be fused with camera-based analysis inside one monitoring workflow.
