# IPO Framework

Figure 1. IPO Framework

## Input
The development of the multi-sensor intruder-fire monitoring system required foundational knowledge in embedded systems, computer vision, and sensor integration. Core hardware and input resources included:
- two night-vision-capable camera inputs with IR support
- two smoke-sensing nodes
- one door-force sensing node with IMU-based detection
- local monitoring software for dashboard, alerts, logs, and summaries
- HTTP event transport through `POST /api/sensors/event`
- optional Raspberry Pi 2 deployment role for local edge hosting

## Process
The process begins with defining objectives and requirements for intruder and fire detection in a two-area condo scope (Living Room and Door Entrance Area). Detection modules for face recognition, smoke-triggered fire confirmation, smoke events, and door-force events are developed and calibrated. A fusion layer is implemented to combine visual and sensor evidence, followed by iterative scenario-based tests to refine thresholds, rules, and alert behavior.

## Output
The study produces a functional local monitoring prototype that classifies intruder- and fire-related events, generates alerts, and records logs and summaries through the monitoring dashboard. The resulting system demonstrates practical operation under controlled condo-like scenarios using low-cost components and flexible local deployment options.

## Feedback
Feedback comes from repeated scenario trials and optional user evaluation. Observed misclassifications, false alarms, and response delays guide adjustments in thresholds, sensor mapping, and fusion logic. Iterative feedback cycles improve reliability, alert clarity, and overall usability.

Figure 2. Phase 1: System Context, Scope, and Architecture Design  
Researchers review literature and condo constraints, then produce architecture and deployment plans for the two-area prototype.

Figure 3. Phase 2: Development of Core Detection Modules  
Face recognition, flame detection, smoke/door-force sensing, and node firmware are implemented and calibrated on the target architecture.

Figure 4. Phase 3: System Integration and Multi-Sensor Intelligence Layer  
Modules are integrated into one pipeline with HTTP event ingestion, fusion logic, persistent alerts, and structured logging.

Figure 5. Phase 4: Iterative Testing, Adjustment, and System Refinement  
Scenario tests (normal, intruder, fire-related, nuisance) were repeated while tuning parameters and decision rules.

Figure 6. Phase 5: Final Performance Evaluation and Analysis  
Final repeated trials recorded event decisions, timestamps, and latency, with optional user feedback on alert clarity and timeliness.

## ASCII Illustration

```text
INPUTS
+-------------------+   +-------------------+   +-------------------+
| Camera Input A    |   | Camera Input B    |   | Sensor Nodes      |
| Indoor Monitoring |   | Door Monitoring   |   | Smoke / DoorForce |
+-------------------+   +-------------------+   +-------------------+
           \                  /                          |
            \                /                           v
             +-----------------------------------------------+
             | Local Monitoring and Detection Workflow       |
             | Face Analysis | Fire Confirmation | Fusion    |
             +-----------------------------------------------+
                                   |
                                   v
                       +---------------------------+
                       | Alerts, Logs, Summaries   |
                       | Dashboard, Evidence, ACK  |
                       +---------------------------+

OPTIONAL DEPLOYMENT SUPPORT
+---------------------------+
| Raspberry Pi 2            |
| Local Edge Hosting Option |
+---------------------------+
```
