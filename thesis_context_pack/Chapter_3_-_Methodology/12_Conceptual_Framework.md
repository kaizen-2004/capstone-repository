# Conceptual Framework (Updated Markdown Version)

Figure X. Updated Conceptual Framework for the Real-Time Intruder and Fire Monitoring Alert System

This conceptual framework follows the five-phase engineering flow used in Chapter 3 and aligns with the current implementation baseline: dual-area monitoring (Living Room and Door Entrance Area), HTTP-based sensor-event ingestion, event-driven camera analysis, and flexible local deployment in which Raspberry Pi 2 may be used for local edge hosting when needed.

## Phase 1: System Architecture and Component Design

1. Define the system scope by identifying target threats: unauthorized persons (intruders) and fire-related events.
2. Design the integrated architecture using camera inputs, smoke-sensor nodes, one door-force sensor node, local monitoring services, and optional deployment support from Raspberry Pi 2.
3. Plan physical deployment, node placement, monitored zones, and notification recipients.

**Phase 1 Output:** Finalized architecture, deployment map, and node/area assignments.

## Phase 2: Core Algorithm and Subsystem Development

4. Develop and benchmark the face pipeline (OpenCV YuNet face detector + SFace recognizer) for authorized-vs-unknown classification.
5. Create the visual flame detection algorithm for indoor camera input.
6. Construct and calibrate smoke and door-force sensor subsystems, including firmware event publishing.
7. Test subsystem-level detection behavior and latency under controlled conditions.

**Phase 2 Output:** Validated module-level detection pipelines and calibrated sensor subsystems.

## Phase 3: System Integration and Multi-Sensor Intelligence Layer

8. Implement multi-criteria fire verification that requires both visual flame evidence and smoke evidence within the configured fusion window.
9. Integrate sensing nodes and monitoring services through HTTP event ingestion (`POST /api/sensors/event`).
10. Develop the monitoring interface for event logs, alerts, settings, daily summaries, and face-management workflows.
11. Construct the notification framework for persistent mobile alerts and operator acknowledgment handling.

**Phase 3 Output:** Fully integrated local-first monitoring stack with fusion logic, persistent alerts, and event logging.

## Phase 4: System Deployment and Operational Testing

12. Deploy the integrated stack in the target condo-like environment for real-time operation.
13. Send automated mobile notifications to designated recipients upon verified threat detection.
14. Activate and validate end-to-end alert operation (detection, classification, logging, notification, acknowledgment).

**Phase 4 Output:** Operational deployment with validated alert delivery and monitoring behavior.

## Phase 5: Performance Evaluation and Analysis

15. Evaluate reliability and performance using face-identification accuracy, fire-detection false-positive/false-negative behavior, and end-to-end alert latency.
16. Analyze consolidated logs and daily summaries to assess system effectiveness over repeated scenarios.
17. Document the final performance statistics and prepare the formal evaluation report.

**Phase 5 Output:** Finalized performance results and thesis-ready evaluation documentation.

## End-to-End Conceptual Flow

`Phase 1 (Design) -> Phase 2 (Module Development) -> Phase 3 (Integration + Fusion) -> Phase 4 (Deployment + Operational Testing) -> Phase 5 (Evaluation + Documentation)`

## ASCII Flow

```text
PHASE 1
Design scope, architecture, deployment options
        |
        v
PHASE 2
Develop face, smoke, door-force, and fire-confirmation modules
        |
        v
PHASE 3
Integrate sensor events, camera analysis, fusion logic, and alerts
        |
        v
PHASE 4
Run repeated scenario tests, tune thresholds, refine workflows
        |
        v
PHASE 5
Analyze results, summarize findings, prepare Chapters 4 and 5
```
