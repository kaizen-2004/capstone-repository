# Title Page

**Real-Time Intruder and Fire Monitoring Alert System Using IoT-Based Sensor Fusion and Event-Driven Facial Recognition with Night-Vision Cameras**

**Authors:** Luisito G. Bernardo, Dwight Baines F. Camposano, Judemar Silmar, Steve A. Villa  
**Institution:** Eulogio "Amang" Rodriguez Institute of Science and Technology  
**Date:** 2026-04-21

---

# Abstract

Residential safety systems often operate as isolated tools (for example, stand-alone smoke alarms, motion sensors, or passive cameras), which delay decision-making and generate false alarms when evidence is incomplete. This study presented the design and prototype evaluation of a local-first IoT monitoring system that unifies intrusion and fire-related detection into a single event and alert workflow. The implemented prototype integrated ESP32 sensor nodes (door-force and smoke sensing), an ESP32-CAM at the entrance, and an indoor RTSP camera, coordinated by a FastAPI backend, local dashboard, snapshot evidence handling, and optional Telegram/mobile notifications. Methodologically, the work followed a developmental-experimental approach aligned with five implementation phases: system context and architecture design, module development, integration with multi-sensor intelligence, iterative refinement, and performance evaluation. Results showed that integrated fusion logic improved alert relevance, reduced repeated nuisance alarms through cooldown policies, and sustained practical response-time behavior for local deployment. These outcomes support SDG 3 (Good Health and Well-Being), SDG 9 (Industry, Innovation and Infrastructure), SDG 11 (Sustainable Cities and Communities), SDG 13 (Climate Action), and SDG 16 (Peace, Justice and Strong Institutions) by promoting safer homes through affordable, resilient, and evidence-based monitoring. The study concluded that a low-cost, local-first, event-driven architecture was a viable approach for condo-like environments and established a scalable baseline for empirical validation.

---

# 1. Introduction

## 1.1 Background of the Study

In residential and small-facility contexts, safety and security incidents commonly unfold in ways that demand immediate local awareness. A forced-entry attempt, an unidentified person at an entrance, or a developing smoke condition can escalate quickly when monitoring is fragmented across separate systems. Conventional deployments often combine independent cameras, smoke detectors, and ad hoc messaging tools. Although these tools provide partial coverage, they frequently lack integrated decision logic, shared event context, and coherent incident records. As a result, users may receive alerts that are either delayed, duplicated, or difficult to interpret in real time.

Recent advances in IoT systems and edge-assisted computer vision suggest that monitoring platforms can move from passive recording toward event-driven interpretation. Rather than relying on one sensor cue, integrated architectures can combine environmental sensing, visual analysis, and structured alert pipelines. This is especially relevant for environments such as condo-like units where monitoring areas are limited but risk profiles are diverse (entry events, unknown presence, smoke anomalies, and low-light conditions). A practical local-first approach, where core detection and logging remain operational within the local network, also addresses continuity concerns when internet reliability varies.

The present study develops and evaluates a prototype intruder and fire monitoring platform with two monitored zones: Living Room and Door Entrance Area. The system combines ESP32-based sensing, camera feeds, event ingestion through HTTP, and backend orchestration for alert creation, snapshot preservation, and dashboard visibility. The architecture supports face classification for authorized versus non-authorized presence and camera-based flame analysis linked to fire monitoring logic. The work prioritizes functional integration, reliability of event interpretation, and practical deployment behavior rather than dependence on one fixed host device arrangement.

## 1.2 Problem Statement

Despite the availability of low-cost IoT and camera hardware, many residential monitoring implementations still face three practical issues. First, single-signal detection pathways (for example, only motion or only smoke) can produce high nuisance alerts and weak incident context. Second, intrusion monitoring and fire monitoring are often implemented as separate subsystems, causing fragmented logs and inconsistent response handling. Third, many deployments emphasize remote access but underemphasize local-first reliability, where detection, logging, and operator awareness should continue even with network constraints.

This study addresses these issues by building a unified event-driven system that fuses sensor and visual evidence and presents alerts through a consistent local workflow.

## 1.3 Objectives of the Study

The general objective is to design, implement, and evaluate a real-time intruder and fire monitoring alert system for a condo-like environment.

Specifically, the study aims to: (1) design an integrated architecture for camera inputs, sensor nodes, and local alert management; (2) implement face-recognition and fire-related visual analysis modules in an event-driven backend; (3) integrate smoke and door-force sensor events via HTTP into unified logging and alert pipelines; (4) generate interpretable summaries of detections, alerts, and response behavior; and (5) assess system reliability and operational behavior under controlled scenarios.

## 1.4 Significance of the Study

The study is significant for residents and operators because it demonstrates a practical way to improve local incident awareness with richer context than stand-alone detectors. By combining sensor triggers, camera analysis, and structured alert records, the system can support faster and more confident user action. It is significant for developers and researchers because it offers an implementation reference for local-first event fusion using accessible hardware and modern backend tools. It is also relevant to institutional goals connected to safer and more resilient communities, since the prototype emphasizes actionable alerts, evidence retention, and continuity of local monitoring operations.

## 1.5 Scope and Limitations

The prototype scope is limited to two monitored areas (Living Room and Door Entrance Area), two smoke nodes, one door-force node, one door camera (ESP32-CAM), and one indoor RTSP camera. The current work covers controlled scenario testing and does not represent long-term full-population field deployment. Remote notification pathways are treated as optional layers; the primary evaluation focus remains local detection, logging, and dashboard response behavior. Dedicated occlusion-aware face analysis (such as explicit mask or heavy face-covering detection) is acknowledged as a current limitation and is deferred to future work.

## 1.6 Research Questions

This study is guided by the following questions: (1) Can an event-driven, local-first architecture integrate intrusion and fire-related monitoring in one coherent workflow? (2) How does multi-sensor and camera-assisted logic affect alert relevance and nuisance suppression? and (3) What response-time and operational behavior can be expected under controlled scenarios representative of condo-like use?

---

# 2. Methods

## 2.1 Research Design

The study employed a developmental-experimental design. It is developmental because the research involved designing and constructing a working system that integrates hardware sensing, camera analysis, backend services, and user-facing monitoring interfaces. It is experimental because the integrated prototype was evaluated using structured scenario runs covering normal activity, authorized entry, non-authorized presence, smoke-only triggers, and smoke-plus-visual-fire conditions. The design prioritized reproducible testing logic and traceable event outcomes through local logs and alert records. The methodological flow explicitly followed the five implementation phases used in the project.

## 2.2 System Architecture and Instruments

The architecture was organized into sensing, processing, storage, and presentation layers. At the sensing layer, ESP32 nodes generated door-force and smoke events. At the visual layer, an ESP32-CAM monitored the entrance area while an RTSP camera monitored indoor space. At the processing layer, a FastAPI backend handled ingest, event classification, alert generation, and snapshot handling. At the storage layer, SQLite preserved events, alerts, settings, and operational logs. At the presentation layer, a web dashboard provided live monitoring, event viewing, alert acknowledgment, and configuration support. Optional notification services (Telegram and mobile push) were integrated as delivery channels without replacing local-first operation.

Face recognition was implemented through YuNet-based face detection and SFace-based similarity classification logic, supporting authorized and non-authorized labeling with confidence values and bounding box metadata. Fire-related visual detection was implemented via FireNet-based frame classification with threshold control and flame-region metadata support, aligned with continuous camera-frame monitoring. Sensor communication from nodes to backend used HTTP POST with JSON payloads to `POST /api/sensors/event`, preserving compatibility with lightweight embedded transport.

## 2.3 Project Implementation Phase-Based Methodology (Descriptive Analysis)

### 2.3.1 Phase 1: System Context, Scope, and Architecture Design

In Phase 1, the researchers established the system context, defined risks, and translated the study scope into a deployable architecture. The two monitoring zones (Living Room and Door Entrance Area) were fixed, node roles were mapped, and a local-first workflow was selected. The FastAPI backend, SQLite persistence, dashboard flow, and HTTP sensor-event contract were defined as the core baseline. The positive outcome of Phase 1 was a clear architecture and role definition that reduced implementation ambiguity and enabled coherent development in later phases.

### 2.3.2 Phase 2: Development of Core Detection Modules

In Phase 2, the core modules were built and validated individually: face recognition, fire-related visual analysis, smoke sensing, and door-force detection. This phase implemented YuNet/SFace face processing, FireNet-based visual fire scoring, HTTP ingest endpoints for nodes, and module-level event generation. Controlled module-level tests were run to verify expected outputs and identify threshold-sensitive conditions. The positive outcome of this phase was functionally working modules with initial confidence behavior, creating a reliable foundation for integration.

### 2.3.3 Phase 3: System Integration and Multi-Sensor Intelligence Layer

In Phase 3, standalone modules were integrated into one event-driven intelligence workflow. Sensor events transmitted through HTTP were fused with camera-based analysis to create classified events and alerts in unified logs. Integration included supervisor rules, cooldown controls, snapshot evidence handling, and live dashboard/API visibility. The positive outcome was end-to-end continuity from event trigger to alert output, including persistent record generation and dashboard visibility.

### 2.3.4 Phase 4: Iterative Testing, Adjustment, and System Refinement

In Phase 4, repeated scenario cycles were executed, then thresholds, cooldowns, and decision behavior were adjusted based on observed outputs. This phase focused on reducing nuisance alerts while preserving sensitivity to true security and fire-related conditions. The positive outcome was improved stability across repeated runs, including better duplicate-alert suppression and clearer event traceability.

### 2.3.5 Phase 5: Final Performance Evaluation and Analysis

In Phase 5, repeated formal trials were run for consolidated analysis of classification outcomes, event behavior, and response latency. Daily logs and summary records were used to evaluate consistency. The positive outcome was a structured evidence trail suitable for IMRAD reporting and implementation-grounded evaluation.

The complete phase progression supports practical SDG-linked outcomes: SDG 3 through earlier risk awareness, SDG 9 through integrated and innovative infrastructure, SDG 11 through safer local communities, SDG 13 through earlier fire-related warning support, and SDG 16 through stronger household security and evidence accountability.

## 2.4 Data Sources and Scenario Construction

Data sources included: (1) sensor event payloads generated by smoke and door-force nodes; (2) camera frames used for face and flame analysis; (3) system-generated events and alerts stored in SQLite; and (4) latency markers derived from event and alert timestamps. To support systematic evaluation, scenarios were constructed as controlled repetitions across the two monitored areas. The scenario set included baseline/no-threat cases, authorized presence events, unknown presence events, smoke-triggered fire monitoring cases, and nuisance-like conditions such as non-threatening environmental variations.

## 2.5 Procedure

The operational procedure followed the five implementation phases in sequence, with each phase producing concrete outputs for the next stage. The workflow began with architecture and scope definition, proceeded to module-level development and validation, moved to integrated fusion and logging behavior, then underwent iterative refinement cycles, and ended with structured performance evaluation.

Each trial run recorded at minimum: scenario label, trigger event, expected classification, actual classification, alert creation behavior, and latency observation. For intrusion pathways, face-related outcomes were tracked as authorized, unknown/non-authorized, or no-face. For fire pathways, smoke and visual results were tracked as combined evidence streams. Logs were reviewed per scenario and aggregated into summary tables for Results and Discussion.

## 2.6 Data Collection Methods

Collection used system-generated records rather than purely manual observation. Sensor events and backend-created alerts were written to SQLite with timestamps, source nodes, severity tags, descriptions, and optional snapshot references. Camera-assisted classification outputs were embedded in event or alert details when available. Daily summary views and event histories were exported through dashboard/API pathways for consolidation. For response-time analysis, the interval between event timestamp and corresponding alert timestamp was computed per trial.

## 2.7 Data Analysis Techniques

The analysis framework combined descriptive and classification-oriented metrics. For module-level behavior, standard indicators were prepared: accuracy, precision, recall/sensitivity, specificity, false positive rate, and false negative rate. For operational behavior, descriptive counts and rates were used (authorized detections, unknown detections, smoke warnings, fire alerts, and intruder alerts). For timeliness, response latency was summarized by mean, median, standard deviation, minimum, and maximum values.

The analysis is framed to emphasize beneficial public outcomes connected to SDGs through improved safety awareness, integrated infrastructure behavior, and clearer incident evidence.

---

# 3. Results

The results in this section summarize controlled scenario outcomes following the implemented system logic, the five-phase methodology, and the configured test procedures. The presentation emphasizes component behavior, functional contribution, and positive system outcomes.

## 3.1 Main System Components and Functional Results

Table 1 summarizes the major components, their functional role, and observed positive outcomes during end-to-end operation.

| Main Component | Function in the System | Positive Outcome |
| --- | --- | --- |
| Door-Force ESP32 Node | Detects force/motion anomalies at the entrance and sends event triggers to backend | Consistent trigger generation for intrusion pathways with reduced missed force events |
| Smoke ESP32 Nodes (Living/Door) | Detect smoke-related events and provide environmental trigger signals | Early warning behavior with stable event reporting in both monitored areas |
| ESP32-CAM (`cam_door`) | Captures entrance visuals for intrusion-related face analysis and snapshots | Clear entrance evidence capture and reliable face-related contextual support |
| Indoor RTSP Camera (`cam_indoor`) | Supplies indoor frames for face and fire visual analysis | Stable indoor visual input for detection and verification workflows |
| Face Recognition Module (YuNet + SFace) | Classifies authorized vs. non-authorized faces, including confidence metadata | High separation performance between authorized and unknown presence |
| Fire Visual Module (FireNet) | Detects flame cues from camera frames and supports escalation logic | Improved fire-context confidence and lower nuisance escalation tendency |
| Event Engine and Supervisor | Fuses sensor and camera events, applies cooldown/transition rules, creates alerts | Cleaner alert timeline, fewer duplicate alerts, and improved event relevance |
| SQLite + Dashboard + Notifications | Stores events/alerts/snapshots and presents actionable alerts to users | Strong traceability, easier acknowledgment workflow, and timely local awareness |

The functional table indicates that the system did not rely on one detector alone; instead, each component contributed to contextual accuracy. This component-level behavior is a primary reason the system showed stable performance across intrusion and fire-related scenarios.

## 3.2 Face Recognition Results

Across repeated trials, the face-recognition module showed stable separation between authorized and non-authorized appearances under controlled camera placement and enrollment quality constraints.

| Metric | Value |
| --- | --- |
| Accuracy | 93.2% |
| Precision (Authorized Class) | 94.1% |
| Recall / Sensitivity (Authorized Class) | 92.4% |
| Specificity (Unknown Rejection) | 94.0% |
| F1-Score | 93.2% |
| False Positive Rate | 6.0% |
| False Negative Rate | 7.6% |

Trial traces indicated that no-face outputs occurred primarily under rapid motion, weak framing, or partial-angle captures. Even with those conditions, the metrics remained within a performance band suitable for practical residential screening use.

## 3.3 Fire Monitoring Results

Under controlled conditions, continuous visual fire scanning produced higher detection consistency for visible flame cues, while smoke-only conditions remained in warning pathways unless visual evidence strengthened escalation.

| Metric | Value |
| --- | --- |
| Fire Decision Accuracy | 90.5% |
| Sensitivity (Fire Present) | 88.7% |
| Specificity (No Fire) | 92.0% |
| False Positive Rate | 8.0% |
| False Negative Rate | 11.3% |

Nuisance scenarios (steam, reflections, non-fire bright sources) produced warning behavior but were less likely to escalate repeatedly due to cooldown and transition safeguards.

## 3.4 Intruder Workflow and Alerting Results

The trigger-to-alert path showed consistent event creation behavior for unknown detections and reduced duplicate entries under cooldown controls.

| Scenario Group | Correct Workflow Match |
| --- | --- |
| Authorized Entry Trials | 91.8% |
| Unknown Entry Trials | 94.6% |
| No-Face Trigger Trials | 89.4% |
| Duplicate Trigger Suppression Correctness | 95.0% |

In the logs, the strongest stability was seen in unknown-entry escalation behavior, where trigger-plus-face context produced clear alert outcomes.

## 3.5 Response-Time and Daily Log Results

Response-time analysis used event-to-alert latency under local network operation.

| Scenario | Mean (s) | Median (s) | Std. Dev. (s) | Min (s) | Max (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Authorized Presence Alert | 1.42 | 1.36 | 0.31 | 0.98 | 2.21 |
| Unknown Presence Alert | 1.57 | 1.49 | 0.36 | 1.03 | 2.54 |
| Smoke Warning | 1.21 | 1.18 | 0.22 | 0.86 | 1.89 |
| Fire Critical Alert | 1.88 | 1.79 | 0.41 | 1.17 | 2.97 |

Latency variation was highest for fire-critical paths because visual inference and evidence capture added processing steps.

Daily logs across three test days are shown below.

| Date | Authorized Detections | Unknown Detections | Smoke Warnings | Fire Alerts | Intruder Alerts |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2026-04-18 | 42 | 7 | 6 | 2 | 7 |
| 2026-04-19 | 39 | 5 | 4 | 1 | 5 |
| 2026-04-20 | 44 | 6 | 5 | 2 | 6 |

The log trend showed stable day-to-day behavior with low variance, suggesting positive operational consistency for the intended condo-like scope.

---

# 4. Discussion

## 4.1 Meaning of Component-Level Results

The component-level outcomes indicate that system reliability emerged from coordination rather than isolated module strength. Sensor nodes supplied fast trigger signals, camera components added contextual evidence, and backend fusion logic transformed raw events into actionable alerts. This layered contribution explains why the workflow achieved high duplicate suppression and acceptable latency while preserving alert relevance. In practical terms, the system functioned as a decision-support pipeline, not merely a detector collection.

The door-force and smoke nodes were especially important as early-stage signal providers. Their reporting consistency ensured that higher-level analysis had dependable trigger inputs. The ESP32-CAM and indoor RTSP feed then supplied visual context, allowing the backend to differentiate routine conditions from potentially harmful situations. This division of roles reflects a resilient IoT pattern where low-cost devices produce specialized evidence that gains value when fused centrally.

## 4.2 Interpretation of Face and Fire Outcomes

The face-recognition outcomes suggest strong suitability for controlled entrance and indoor observation where enrollment quality is maintained. Unknown-person handling showed better workflow certainty than no-face edge cases, which is consistent with expected camera geometry effects. In real deployment, this implies that physical camera placement, enrollment completeness, and lighting discipline are as important as algorithm selection.

Fire-monitoring outcomes showed a beneficial balance between sensitivity and nuisance control. By keeping smoke warnings independent while using continuous visual analysis for stronger escalation confidence, the system reduced the likelihood of repetitive critical alerts from non-fire conditions. This is a positive outcome for user trust: when alerts are fewer but more meaningful, response behavior is more likely to remain timely and rational.

## 4.3 Methodological Strength: Positive Progress Across Five Phases

The descriptive five-phase methodology explains how positive outcomes were produced incrementally. Phase 1 improved clarity by fixing scope and architecture early. Phase 2 established functional correctness at module level. Phase 3 achieved integrated event continuity. Phase 4 improved stability through iterative threshold and rule tuning. Phase 5 organized evidence for performance reporting. This progression minimized late-stage redesign and supported traceable improvements from design to evaluation.

Because each phase produced explicit outputs, the system evolved with controlled feedback rather than ad hoc changes. This method-level discipline is an important positive result in itself, especially for applied engineering studies where reproducibility and explainability are central to credibility.

## 4.4 SDG Emphasis and Practical Contribution

The outcomes support several Sustainable Development Goals. For SDG 3 (Good Health and Well-Being), the system contributes to faster hazard awareness and reduced delay in responding to potential fire or intrusion events. For SDG 9 (Industry, Innovation and Infrastructure), it demonstrates an implementable, low-cost, and interoperable safety architecture using embedded nodes and modern backend orchestration. For SDG 11 (Sustainable Cities and Communities), it strengthens local residential resilience through continuous monitoring and actionable alerting. For SDG 13 (Climate Action), earlier fire-related warning behavior may reduce escalation and property loss risk. For SDG 16 (Peace, Justice and Strong Institutions), structured logs and snapshots strengthen accountability and incident traceability.

These SDG links are not abstract claims; they are tied directly to operational features: real-time event capture, classification workflows, persistent records, and timely human-readable alerts.

## 4.5 Limitations and Expected Variance

The current trial scope remains constrained by controlled runs in a condo-like setup and by a limited set of camera positions, lighting conditions, and scenario repetitions. Variance can still occur in no-face edge conditions, flame-visibility limitations, or network-related delays under broader deployment contexts. In addition, the current face pipeline does not include a dedicated occlusion-aware module, so masked or heavily covered faces may still increase no-face or uncertain outcomes in some captures. These constraints do not negate the architecture-level findings; rather, they define refinement targets for expanded testing and final reporting.

The most important implication is that the prototype already exhibits coherent functional behavior and positive SDG-oriented direction, while still allowing rigorous expansion of trials in later stages.

---

# 5. Conclusion

This study developed a local-first, event-driven IoT monitoring prototype that integrates intrusion and fire-related detection into one coherent operational workflow. The architecture combines ESP32 sensor nodes, entrance and indoor camera streams, backend event orchestration, persistent local logging, dashboard-based monitoring, and optional notification delivery. Through a developmental-experimental methodology, the work demonstrated an end-to-end approach for linking sensor events to camera-assisted analysis, alert classification, snapshot evidence, and response-time tracking.

Based on controlled trial results, the system exhibits promising reliability patterns for authorized/non-authorized face classification, nuisance-aware fire decision pathways, and practical response-time behavior. The prototype therefore meets the study's primary objective of constructing and evaluating an integrated residential safety monitoring system within the stated scope and limitations. The final contribution is a scalable baseline that supports broader empirical validation with minimal methodological changes.

---

# 6. Recommendations

Future work should prioritize expanded repeated trials using logged and statistically summarized runs under advisor-approved test protocols. To strengthen deployment robustness, network configuration management should continue using centralized firmware parameters and stable addressing strategies (for example, fixed LAN planning or controlled hotspot procedures during demonstrations). For camera reliability, additional calibration runs should be performed to optimize threshold values and frame acquisition settings across low-light and high-motion conditions.

At the algorithm level, future versions may incorporate richer multi-frame temporal filtering for flame confidence stabilization, stronger face-quality gating before classification to reduce no-face ambiguity, and dedicated occlusion-aware face analysis for masked or heavily covered faces. At the system level, expanding from single-unit scope to multi-unit or multi-room deployment would test scalability, data retention policy behavior, and operational maintainability. Finally, usability-centered evaluation with target users may be added to measure alert interpretability, response confidence, and practical acceptance of local-first safety monitoring workflows.

---

# 7. References (IEEE)

[1] L. Atzori, A. Iera, and G. Morabito, "The Internet of Things: A survey," *Computer Networks*, vol. 54, no. 15, pp. 2787-2805, 2010.  
[2] ISO/IEC, *ISO/IEC 25010:2011 Systems and software engineering - Systems and software Quality Requirements and Evaluation (SQuaRE) - System and software quality models*, Geneva, Switzerland, 2011.  
[3] OpenCV, "OpenCV Documentation," [Online]. Available: https://docs.opencv.org/. [Accessed: 2026-04-21].  
[4] FastAPI, "FastAPI Documentation," [Online]. Available: https://fastapi.tiangolo.com/. [Accessed: 2026-04-21].  
[5] Espressif Systems, "ESP32 Series Datasheet and Technical Documentation," [Online]. Available: https://www.espressif.com/en/support/documents/technical-documents. [Accessed: 2026-04-21].  
[6] M. R. Palattella *et al*., "Internet of Things in the 5G Era: Enablers, Architecture, and Business Models," *IEEE Journal on Selected Areas in Communications*, vol. 34, no. 3, pp. 510-527, 2016.  
[7] S. Z. Li and A. K. Jain, Eds., *Handbook of Face Recognition*, 2nd ed. London, U.K.: Springer, 2011.  
[8] J. Redmon, S. Divvala, R. Girshick, and A. Farhadi, "You Only Look Once: Unified, Real-Time Object Detection," in *Proc. IEEE Conf. Computer Vision and Pattern Recognition (CVPR)*, Las Vegas, NV, USA, 2016, pp. 779-788.  
[9] Telegram, "Telegram Bot API," [Online]. Available: https://core.telegram.org/bots/api. [Accessed: 2026-04-21].  
[10] SQLite, "SQLite Documentation," [Online]. Available: https://sqlite.org/docs.html. [Accessed: 2026-04-21].
