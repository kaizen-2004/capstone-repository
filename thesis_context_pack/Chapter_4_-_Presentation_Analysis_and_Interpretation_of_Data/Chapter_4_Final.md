# CHAPTER 4

# PRESENTATION, ANALYSIS, AND INTERPRETATION OF DATA

## 4.1 Introduction

This chapter presents the implementation output, test observations, and analytical interpretation of the Real-Time Intruder and Fire Monitoring Alert System. The chapter focuses on how the completed prototype behaved during controlled demonstration and evaluation trials involving smoke detection, door-force detection, camera-based face recognition, event logging, alert generation, dashboard monitoring, mobile monitoring, and snapshot evidence capture.

The analysis is based on three main evidence sources. First, the system-generated event and alert logs were exported from the backend through the application programming interface. Second, a 50-row trial review sheet was prepared from the exported logs and manually checked using the Events screen, Alerts screen, and Snapshot Gallery. Third, dashboard screenshots and generated graph outputs were used as visual support for the discussion. These data sources made it possible to examine both functional behavior and measurable performance.

The presentation of results is organized according to the major system components and objectives of the study. The chapter begins with the final implementation overview, followed by dashboard statistics, event and alert summaries, smoke and fire results, door-force and intruder results, face recognition results, integrated scenario testing, response-time analysis, snapshot evidence analysis, and a final synthesis.

## 4.2 System Implementation Overview

The final prototype integrates hardware sensing, camera monitoring, backend processing, dashboard visualization, and mobile monitoring into one event-driven workflow. The system uses sensor nodes to detect smoke and possible forced-door activity, while camera inputs provide visual evidence and face-related classification support. The backend receives device events, records them in local storage, creates alerts, saves snapshots when available, and presents the data through the web dashboard and mobile monitoring interface.

Table 4.1 summarizes the final implemented components and their roles in the prototype.

**Table 4.1**

**Final Implemented Components of the Prototype**

| Component | Role in the System | Status | Remarks |
| --- | --- | --- | --- |
| Indoor Camera (`cam_indoor`) | Captures indoor monitoring frames and supports smoke/fire and person-related evidence capture | Implemented | Used for living room monitoring, flame/fire evidence, and some unknown-person detections |
| Door Camera (`cam_door`) | Captures entrance-area frames and supports door-force, authorized-entry, and intruder evidence | Implemented | Used for forced-door scenarios and authorized-entry evidence |
| Smoke Node 1 (`smoke_node1`) | Detects smoke level changes in the living room | Implemented | Generated `SMOKE_HIGH` and `SMOKE_NORMAL` events during testing |
| Smoke Node 2 (`smoke_node2`) | Detects smoke level changes near the door entrance area | Implemented | Generated smoke events in the door entrance area during testing |
| Door-Force Node (`door_force`) | Detects forced-door or abnormal impact activity | Implemented | Generated `DOOR_FORCE` events and triggered intruder-related alerts |
| Local Backend | Receives sensor events, processes detection logic, creates event and alert records, and saves snapshots | Implemented | FastAPI backend with local event, alert, and snapshot persistence |
| Web Dashboard | Displays monitoring statistics, events, alerts, and snapshot evidence | Implemented | Used as the main monitoring and review interface during Chapter 4 testing |
| Mobile Monitoring Interface | Provides mobile access to system status, alerts, and monitoring information | Implemented | Used as an auxiliary monitoring interface for remote or handheld viewing |

Table 4.1 shows that the prototype was not limited to a single detector. Instead, it combined smoke sensing, force sensing, camera evidence, backend processing, and user-facing interfaces. This integration supports the objective of creating a coordinated monitoring workflow rather than separate stand-alone alarms.

[Figure 4.1]

Figure 4.1 shows the generated dashboard statistics summary based on the exported Chapter 4 logs. The figure corresponds to `chapter4_outputs/01_dashboard_statistics_summary.png`. It provides an overview of authorized detections, unknown detections, fire fusion alerts, intruder fusion alerts, average response time, authorized detection share, alert rate, and fire evidence conversion. This figure supports the implementation overview by showing that the system produced measurable monitoring outputs from the integrated prototype.

## 4.3 Data Sources and Evaluation Basis

The Chapter 4 analysis used exported system records and manually reviewed trial evidence. The event and alert logs were exported from the backend, while the trial review sheet was prepared to compare expected labels against predicted labels. The expected label represents the intended condition of the test scenario, while the predicted label represents the output produced by the system.

Table 4.2 presents the data sources used for the analysis.

**Table 4.2**

**Data Sources Used for Chapter 4 Analysis**

| Data Source | File or Source | Purpose in the Analysis |
| --- | --- | --- |
| Event log export | `chapter4_events_log.json` | Used to identify event IDs, event codes, source nodes, locations, timestamps, and snapshot links |
| Alert log export | `chapter4_alerts_log.json` | Used to identify alert IDs, alert types, severities, acknowledgement status, timestamps, and alert snapshot paths |
| Trial review sheet | `chapter4_trial_review_sheet.csv` | Used to compare expected labels and predicted labels for confusion matrix computation |
| Generated graph outputs | `chapter4_outputs/` | Used to produce dashboard-style figures, event graphs, alert graphs, response-time graphs, and confusion matrices |
| System screenshots | Web dashboard, Events screen, Alerts screen, Snapshot Gallery | Used as visual evidence for selected smoke, door-force, intruder, and snapshot cases |

Table 4.2 shows that the results were taken from both machine-generated records and manual verification. The logs provide timestamped and traceable evidence, while the trial sheet provides the ground-truth comparison needed for confusion matrix analysis.

The final trial review sheet contained 50 rows. However, two trials were marked as excluded from computation due to review limitations. As a result, 48 trials were used for the final confusion matrix and classification analysis.

**Table 4.3**

**Trial Review Sheet Summary**

| Item | Count |
| --- | ---: |
| Total trial rows prepared | 50 |
| Trials used in final computation | 48 |
| Trials excluded from computation | 2 |
| Correct classifications | 40 |
| Incorrect classifications | 8 |
| Overall classification accuracy | 83.33% |

Table 4.3 indicates that the final evaluation was based on 48 usable reviewed trials. The overall classification accuracy was 83.33%. This value reflects the combined performance of face recognition, smoke/fire monitoring, and door-force/intruder monitoring. The result shows that the prototype was able to reach a considerable overall classification level under the controlled testing conditions, although no-face and non-authorized edge cases still require refinement.

### 4.3.1 Statistical Treatment and Sample Computations

The statistical treatment used in this chapter followed the evaluation metrics described in Chapter 3. The classification results were computed from the 48 usable reviewed trials in `chapter4_trial_review_sheet.csv`, while the event frequencies, alert frequencies, dashboard statistics, and response-time values were computed from the exported event and alert logs.

For the confusion-matrix-based metrics, the following terms were used:

- True Positive (TP): the system predicted the target class and the expected label was also the target class.
- False Positive (FP): the system predicted the target class, but the expected label was a different class.
- False Negative (FN): the expected label was the target class, but the system predicted a different class.
- True Negative (TN): the system correctly predicted that a record did not belong to the target class.

The formulas used in the analysis were as follows:

```text
Accuracy = (Number of Correct Classifications / Total Number of Trials) x 100
```

```text
Precision = TP / (TP + FP) x 100
```

```text
Recall or Sensitivity = TP / (TP + FN) x 100
```

```text
F1-score = 2 x (Precision x Recall) / (Precision + Recall)
```

```text
Response Time = Alert Timestamp - Event Timestamp
```

```text
Mean Latency = Sum of Latency Values / Number of Event-to-Alert Records
```

```text
Alert Rate = Total Number of Alerts / Number of Days Covered by the Exported Logs
```

```text
Authorized Detection Share = Authorized Detections / (Authorized Detections + Unknown Detections) x 100
```

```text
Fire Evidence Conversion = Fire Fusion Alerts / (Fire Fusion Alerts + Smoke Warning Alerts) x 100
```

The following sample computations show how the final values in the chapter were derived:

```text
Overall Accuracy = (40 / 48) x 100
Overall Accuracy = 83.33%
```

```text
Face Recognition Accuracy = (16 / 18) x 100
Face Recognition Accuracy = 88.89%
```

```text
Smoke and Fire Detection Accuracy = (16 / 20) x 100
Smoke and Fire Detection Accuracy = 80.00%
```

```text
Door-Force and Intruder Detection Accuracy = (8 / 10) x 100
Door-Force and Intruder Detection Accuracy = 80.00%
```

```text
Authorized Detection Share = 67 / (67 + 175) x 100
Authorized Detection Share = 27.69%
```

```text
Fire Evidence Conversion = 86 / (86 + 94) x 100
Fire Evidence Conversion = 47.78%
```

```text
Alert Rate = 500 / 5
Alert Rate = 100.00 alerts/day
```

```text
Overall Mean Latency = 13.00 seconds / 410 event-to-alert records
Overall Mean Latency = 0.0317 seconds
```

For class-level performance, the face recognition class `AUTHORIZED` may be used as an example. Based on the face recognition confusion matrix, there were 10 true authorized classifications, 0 false authorized classifications, and 1 missed authorized classification.

```text
AUTHORIZED Precision = 10 / (10 + 0) x 100
AUTHORIZED Precision = 100.00%
```

```text
AUTHORIZED Recall = 10 / (10 + 1) x 100
AUTHORIZED Recall = 90.91%
```

```text
AUTHORIZED F1-score = 2 x (100.00 x 90.91) / (100.00 + 90.91)
AUTHORIZED F1-score = 95.24%
```

These computations show that the values presented in the succeeding tables were not manually estimated. They were computed from the reviewed trial sheet and exported system logs, then interpreted in relation to the actual behavior of the prototype during testing.

## 4.4 Dashboard Statistics and Event Summary

The dashboard statistics were generated from the latest exported logs. The dashboard-level metrics summarize recorded detections and alert outputs over the export period.

**Table 4.4**

**Dashboard Statistics Summary from Exported Logs**

| Metric | Value |
| --- | ---: |
| Authorized Face Detections | 67 |
| Unknown Detections | 175 |
| Fire Fusion Alerts | 86 |
| Intruder Fusion Alerts | 226 |
| Average Response Time | 0.0317 seconds |
| Authorized Detection Share | 27.69% |
| Alert Rate | 100.00 alerts/day |
| Fire Evidence Conversion | 47.78% |

Table 4.4 shows that the monitoring system generated a substantial number of detection and alert records. Unknown detections and intruder fusion alerts were higher than authorized detections, which indicates that the system was actively logging suspicious or non-authorized events during the testing period. The average response time of 0.0317 seconds also suggests that event-to-alert record creation was fast under the local deployment setup.

[Figure 4.2]

Figure 4.2 shows the generated event code distribution from `chapter4_outputs/02_event_code_distribution.png`. The figure visualizes the frequency of recorded event codes such as `AUTHORIZED`, `UNKNOWN`, `SMOKE_HIGH`, `SMOKE_NORMAL`, `DOOR_FORCE`, and `FLAME_SIGNAL`. This figure supports the event summary by showing which types of events appeared most frequently in the exported logs.

The exported event log contained the latest 500 event records. Table 4.5 presents the event code frequencies from these records.

**Table 4.5**

**Event Code Frequency from Latest 500 Exported Event Records**

| Event Code | Count |
| --- | ---: |
| `UNKNOWN` | 175 |
| `SMOKE_NORMAL` | 84 |
| `AUTHORIZED` | 67 |
| `FLAME_SIGNAL` | 61 |
| `SMOKE_HIGH` | 52 |
| `DOOR_FORCE` | 40 |
| `NODE_OFFLINE` | 9 |
| `CAMERA_OFFLINE` | 6 |
| `SNAPSHOT_DIRECT_TEST` | 2 |
| `SNAPSHOT_LINKED_TEST` | 2 |
| `SMOKE_WARNING` | 1 |
| `ENTRY_MOTION` | 1 |
| **Total** | **500** |

Table 4.5 shows that `UNKNOWN` was the most frequent event code in the exported event records. This means that a large portion of camera-related records involved unknown or non-authorized detections. Smoke-related events were also recorded frequently through `SMOKE_HIGH`, `SMOKE_NORMAL`, and `SMOKE_WARNING`. The `DOOR_FORCE` count confirms that the door-force sensor node contributed repeated intrusion-related event records.

Table 4.6 presents the same event records grouped according to source node.

**Table 4.6**

**Event Frequency by Source Node**

| Source Node | Count |
| --- | ---: |
| `cam_indoor` | 187 |
| `smoke_node1` | 131 |
| `cam_door` | 122 |
| `door_force` | 48 |
| `smoke_node2` | 10 |
| `smoke_warning_ef5835df` | 2 |
| **Total** | **500** |

Table 4.6 shows that both camera and sensor components contributed to the event history. The indoor camera generated the highest number of events, followed by Smoke Node 1 and the door camera. This result supports the integrated nature of the prototype, where both visual and sensor inputs are used in the monitoring workflow.

The exported alert log also contained the latest 500 alert records. Table 4.7 summarizes the alert outputs by alert type.

**Table 4.7**

**Alert Output Frequency from Latest 500 Exported Alert Records**

| Alert Type | Count |
| --- | ---: |
| `INTRUDER` | 226 |
| `SMOKE_WARNING` | 94 |
| `FIRE` | 86 |
| `AUTHORIZED_ENTRY` | 75 |
| `NODE_OFFLINE` | 11 |
| `CAMERA_OFFLINE` | 8 |
| **Total** | **500** |

Table 4.7 shows that `INTRUDER` was the most frequent alert type. This is consistent with the high number of unknown camera detections and door-force-related events. The presence of `SMOKE_WARNING` and `FIRE` alerts shows that the fire-monitoring workflow also produced alert outputs during the evaluation period. The `AUTHORIZED_ENTRY` records show that recognized entries were also logged, but these were classified as informational rather than critical alarms.

Table 4.8 summarizes the alert severity distribution.

**Table 4.8**

**Alert Severity Distribution**

| Severity | Count |
| --- | ---: |
| Critical | 312 |
| Warning | 113 |
| Info | 75 |
| **Total** | **500** |

Table 4.8 shows that most alerts were classified as critical, primarily due to intruder and fire-related alert outputs. Warning-level alerts were mainly associated with smoke warning and device-related conditions, while informational alerts were associated with recognized or authorized entry records.

[Figure 4.3]

Figure 4.3 shows the daily event trend from `chapter4_outputs/03_daily_event_trend.png`. The figure compares authorized detections, unknown detections, smoke-related events, and door-force events by date. This visualization helps show how the recorded events changed across the testing period.

Table 4.9 presents the daily event summary derived from the exported event records.

**Table 4.9**

**Daily Event Summary from Exported Event Records**

| Date | Authorized Detections | Unknown Detections | Smoke Events | Flame Signals | Door-Force Events |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2026-04-30 | 2 | 8 | 34 | 10 | 20 |
| 2026-05-01 | 0 | 14 | 0 | 34 | 0 |
| 2026-05-02 | 22 | 37 | 16 | 12 | 15 |
| 2026-05-03 | 43 | 116 | 3 | 5 | 5 |

Table 4.9 shows that the system produced event records across multiple days. The highest number of unknown detections occurred on 2026-05-03, while the highest number of smoke events occurred on 2026-04-30. Door-force events were present on 2026-04-30, 2026-05-02, and 2026-05-03, showing that the door-force node was repeatedly tested and recorded in the logs.

[Figure 4.4]

Figure 4.4 shows fire evidence and fusion alert outputs from `chapter4_outputs/04_fire_evidence_and_fusion_outputs.png`. The figure compares daily fire alerts, intruder alerts, and smoke alerts. It supports the finding that intrusion-related alerts were the most frequent output, while smoke and fire alerts were also actively recorded.

[Figure 4.5]

Figure 4.5 shows the alert severity distribution from `chapter4_outputs/05_alert_severity_distribution.png`. The figure visually confirms the dominance of critical alerts in the exported alert records.

## 4.5 Smoke and Fire Detection Results

The smoke and fire workflow was evaluated using smoke-related events and flame/fire-fusion records. Smoke events were primarily generated by the smoke nodes, while fire-related alerts were associated with visual flame or fire-fusion outputs from camera evidence.

The smoke and fire portion of the trial review sheet used 20 trials. These included smoke warning/high smoke, smoke-normal, and visual flame/fire-fusion cases. Table 4.10 summarizes the trial result for this module.

**Table 4.10**

**Smoke and Fire Detection Trial Results**

| Measure | Value |
| --- | ---: |
| Trials used | 20 |
| Correct classifications | 16 |
| Incorrect classifications | 4 |
| Accuracy | 80.00% |

Table 4.10 shows that the smoke and fire detection portion of the reviewed trials obtained an accuracy of 80.00%. This result indicates that the smoke/fire pipeline performed at a considerable level under the controlled testing conditions. The reviewed trials showed that high-smoke events were generally classified correctly, normal smoke recovery events were recorded properly, and visual fire/fusion alerts were detected. The remaining errors were caused by normal conditions that were interpreted as fire and one smoke case that returned a normal output.

Table 4.11 presents the smoke and fire confusion matrix values.

**Table 4.11**

**Smoke and Fire Confusion Matrix Values**

| Expected \ Predicted | NORMAL | SMOKE | FIRE |
| --- | ---: | ---: | ---: |
| NORMAL | 4 | 0 | 3 |
| SMOKE | 1 | 10 | 0 |
| FIRE | 0 | 0 | 2 |

Table 4.11 shows that 10 smoke trials were correctly classified as smoke, four normal cases were correctly classified as normal, and two fire/fusion cases were correctly classified as fire. Three normal cases were predicted as fire, and one smoke case was predicted as normal. This result explains why the fire/smoke module reached 80.00% accuracy rather than a near-perfect value, and it identifies visual fire/fusion sensitivity as the main area for further refinement.

[Figure 4.6]

Figure 4.6 shows the smoke and fire confusion matrix generated from the reviewed trial sheet. The corresponding file is `chapter4_outputs/08_confusion_matrix_fire.png`. The figure visualizes the same classification pattern shown in Table 4.11 and highlights both the correct smoke/fire decisions and the remaining fire false-positive cases.

[Figure 4.7]

Figure 4.7 shows the `SMOKE_HIGH` event list screenshot from the web dashboard. The screenshot demonstrates that smoke events from `smoke_node1` and `smoke_node2` were displayed on the Events screen with timestamp, source node, location, severity, and action details. This supports the finding that smoke sensor events were successfully logged and made visible to the user.

[Figure 4.8]

Figure 4.8 shows the smoke warning alert screenshot from the Alerts screen. The screenshot demonstrates that a smoke-related event was converted into a warning alert, allowing the user to review the alert details and associated status.

[Figure 4.9]

Figure 4.9 shows the smoke warning camera evidence from the Snapshot Gallery. This visual evidence demonstrates that the system was able to associate smoke-related events with camera snapshots, supporting the role of the camera as an evidence-capture component.

## 4.6 Door-Force and Intruder Detection Results

The door-force and intruder workflow was evaluated using door-force trigger events and corresponding alert outputs. A forced door opening attempt was simulated by generating `DOOR_FORCE` events from the door-force node. These events were expected to create intrusion-related alerts and capture evidence from the door camera or available camera feed.

The intruder portion of the trial review sheet used 10 trials. Table 4.12 summarizes the result.

**Table 4.12**

**Door-Force and Intruder Detection Trial Results**

| Measure | Value |
| --- | ---: |
| Trials used | 10 |
| Correct classifications | 8 |
| Incorrect classifications | 2 |
| Accuracy | 80.00% |

Table 4.12 shows that the door-force and intruder workflow achieved 80.00% accuracy in the reviewed trials. The system successfully generated intruder-related outputs for forced-door cases and recognized authorized-entry cases when expected. The remaining errors were related to no-face cases that were escalated as intruder outputs, showing that the system favored safety when camera evidence was unclear.

Table 4.13 presents the intruder confusion matrix values.

**Table 4.13**

**Door-Force and Intruder Confusion Matrix Values**

| Expected \ Predicted | INTRUDER | AUTHORIZED | NO_FACE |
| --- | ---: | ---: | ---: |
| INTRUDER | 6 | 0 | 0 |
| AUTHORIZED | 0 | 2 | 0 |
| NO_FACE | 2 | 0 | 0 |

Table 4.13 shows that six expected intruder cases were predicted as intruder and both authorized cases were predicted as authorized. However, two no-face cases were predicted as intruder. This result shows that the system correctly handled direct forced-door and authorized-entry cases but still needs refinement in distinguishing no-face evidence from intruder evidence.

[Figure 4.10]

Figure 4.10 shows the intruder confusion matrix generated from the reviewed trial sheet. The corresponding file is `chapter4_outputs/08_confusion_matrix_intruder.png`. The figure visually summarizes the correct and incorrect classifications in the door-force and intruder workflow.

[Figure 4.11]

Figure 4.11 shows the `DOOR_FORCE` event details screenshot. The screenshot displays the strong door impact event, timestamp, source node, location, severity, and camera snapshot. This supports the result that the door-force node successfully produced event records and that camera evidence was attached for review.

[Figure 4.12]

Figure 4.12 shows the forced door opening attempt event list screenshot. The screenshot demonstrates that repeated forced-door events were displayed in the Events screen with the event code `DOOR_FORCE`, the source node `door_force`, and the door entrance location.

[Figure 4.13]

Figure 4.13 shows the forced door opening attempt alert screenshot. The screenshot demonstrates that the door-force event was converted into an alert with the description indicating that someone was trying to forcefully open the main door.

[Figure 4.14]

Figure 4.14 shows the intruder critical alert screenshot. The screenshot demonstrates that the system generated critical intruder alerts when unknown or suspicious activity was detected. This supports the role of the alert system in escalating possible security threats.

[Figure 4.15]

Figure 4.15 shows the intruder unknown camera evidence from the Snapshot Gallery. The screenshot demonstrates that the system was able to save and display visual evidence linked to an intruder-related alert.

## 4.7 Face Recognition Results

The face recognition workflow was evaluated using authorized-person and unknown-person records. The system produced `AUTHORIZED` events for recognized users and `UNKNOWN` or intruder-related outputs for non-authorized persons.

The face recognition portion of the trial review sheet used 18 trials after two rows were excluded from computation. Table 4.14 summarizes the face recognition trial result.

**Table 4.14**

**Face Recognition Trial Results**

| Measure | Value |
| --- | ---: |
| Trials used | 18 |
| Correct classifications | 16 |
| Incorrect classifications | 2 |
| Accuracy | 88.89% |

Table 4.14 shows that face recognition obtained the strongest module-level performance among the evaluated components. The 88.89% accuracy indicates that the system was generally effective in distinguishing authorized and non-authorized persons in the reviewed trials.

Table 4.15 presents selected class-level metrics for the face recognition module.

**Table 4.15**

**Face Recognition Class-Level Metrics**

| Class | Support | Precision | Recall | F1-score |
| --- | ---: | ---: | ---: | ---: |
| AUTHORIZED | 11 | 100.00% | 90.91% | 95.24% |
| NON_AUTHORIZED | 6 | 75.00% | 100.00% | 85.71% |
| NO_FACE | 1 | 0.00% | 0.00% | 0.00% |

Table 4.15 shows that the system had strong performance for authorized recognition and non-authorized detection. Authorized recognition produced 100.00% precision and 90.91% recall, while non-authorized detection produced 75.00% precision and 100.00% recall. The no-face category had weak performance because the reviewed no-face case was predicted as non-authorized. This suggests that the system can detect and classify visible faces effectively but may still need better handling of unclear or no-face frames.

Table 4.16 presents the face recognition confusion matrix values.

**Table 4.16**

**Face Recognition Confusion Matrix Values**

| Expected \ Predicted | AUTHORIZED | NON_AUTHORIZED | NO_FACE |
| --- | ---: | ---: | ---: |
| AUTHORIZED | 10 | 1 | 0 |
| NON_AUTHORIZED | 0 | 6 | 0 |
| NO_FACE | 0 | 1 | 0 |

Table 4.16 shows that 10 authorized cases were correctly recognized, and six non-authorized cases were correctly detected. One authorized case was predicted as non-authorized, and one no-face case was also predicted as non-authorized. This indicates that the face recognition pipeline is useful for monitoring but may classify unclear frames conservatively as non-authorized.

[Figure 4.16]

Figure 4.16 shows the face recognition confusion matrix generated from the reviewed trial sheet. The corresponding file is `chapter4_outputs/08_confusion_matrix_face.png`. The figure supports the face recognition analysis by showing that most reviewed face-related trials were classified correctly.

## 4.8 Integrated System Testing Results

Integrated testing was conducted to determine whether the combined hardware and software workflow behaved as expected. The system was evaluated in scenarios involving normal smoke status, high smoke, forced-door activity, authorized entry, unknown-person detection, and visual fire/fusion outputs.

Table 4.17 summarizes the integrated scenario results.

**Table 4.17**

**Integrated System Scenario Results**

| Scenario | Expected System Behavior | Actual System Behavior | Match? | Remarks |
| --- | --- | --- | --- | --- |
| Smoke Node 1 high smoke | Create smoke event and smoke warning alert | `SMOKE_HIGH` events and `SMOKE_WARNING` alerts were recorded | Yes | Smoke alert workflow was functional |
| Smoke normal condition | Record normal smoke status without critical alert | `SMOKE_NORMAL` events were recorded without linked alert IDs | Yes | Normal recovery events were logged |
| Forced door opening attempt | Create door-force event and intruder alert | `DOOR_FORCE` events and intruder alerts were recorded | Partially | Intruder escalation worked, but some no-face/authorized cases were conservatively marked intruder |
| Authorized person detected | Record authorized event and recognized-entry alert | `AUTHORIZED` events and `AUTHORIZED_ENTRY` alerts were recorded | Yes | Face recognition performed well for authorized users |
| Unknown person detected | Flag unknown or non-authorized person | `UNKNOWN` events and intruder alerts were recorded | Yes | Unknown-person detection contributed to critical alert workflow |
| Visual fire/fusion evidence | Create fire-related output when visual fire evidence is detected | `FLAME_SIGNAL` events and `FIRE` alerts were recorded | Yes | Final reviewed fire/fusion cases matched the expected fire output |

Table 4.17 shows that the integrated system was able to connect sensor and camera triggers to dashboard-visible events, alerts, and evidence. The main strength of the system was its ability to create traceable outputs from multiple sources. The main limitation was classification refinement under ambiguous or nuisance-like cases.

Table 4.18 presents the overall confusion matrix values for the 48 usable reviewed trials.

**Table 4.18**

**Overall Confusion Matrix Values**

| Expected \ Predicted | NORMAL | SMOKE | FIRE | INTRUDER | AUTHORIZED | NON_AUTHORIZED | NO_FACE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| NORMAL | 4 | 0 | 3 | 0 | 0 | 0 | 0 |
| SMOKE | 1 | 10 | 0 | 0 | 0 | 0 | 0 |
| FIRE | 0 | 0 | 2 | 0 | 0 | 0 | 0 |
| INTRUDER | 0 | 0 | 0 | 6 | 0 | 0 | 0 |
| AUTHORIZED | 0 | 0 | 0 | 0 | 12 | 1 | 0 |
| NON_AUTHORIZED | 0 | 0 | 0 | 0 | 0 | 6 | 0 |
| NO_FACE | 0 | 0 | 0 | 2 | 0 | 1 | 0 |

Table 4.18 shows that the system performed strongly in smoke, intruder, authorized, and non-authorized classifications. The remaining errors were concentrated mostly in normal cases predicted as fire, one smoke case predicted as normal, one authorized case predicted as non-authorized, and no-face cases predicted as intruder or non-authorized. The overall correct classifications were 40 out of 48, giving an overall accuracy of 83.33%.

[Figure 4.17]

Figure 4.17 shows the overall confusion matrix generated from the reviewed trial sheet. The corresponding file is `chapter4_outputs/07_confusion_matrix_all.png`. This figure summarizes the complete classification behavior across all evaluated modules.

Table 4.19 summarizes the module-level accuracy values.

**Table 4.19**

**Module-Level Accuracy Summary**

| Module | Trials Used | Correct Classifications | Accuracy |
| --- | ---: | ---: | ---: |
| Face Recognition | 18 | 16 | 88.89% |
| Smoke and Fire Detection | 20 | 16 | 80.00% |
| Door-Force and Intruder Detection | 10 | 8 | 80.00% |
| **Overall** | **48** | **40** | **83.33%** |

Table 4.19 shows that face recognition obtained the highest module-level accuracy, followed by smoke/fire detection and door-force/intruder detection. Both smoke/fire detection and door-force/intruder detection remained at a considerable 80.00% accuracy. This indicates that the final system performed well overall, while fire/fusion sensitivity and no-face handling remain practical areas for further improvement.

## 4.9 Response-Time and System Behavior Analysis

Response time was analyzed by comparing event timestamps and alert timestamps in the exported logs. The response-time calculation used alert records that had linked event IDs and valid timestamps. A total of 410 event-to-alert pairs were included in the latency summary.

Table 4.20 presents the response-time statistics by alert type.

**Table 4.20**

**Response-Time Summary by Alert Type**

| Alert Type | N | Mean Latency (s) | Median (s) | Standard Deviation (s) | Minimum (s) | Maximum (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `AUTHORIZED_ENTRY` | 67 | 0.0149 | 0.0000 | 0.1222 | 0.0000 | 1.0000 |
| `CAMERA_OFFLINE` | 6 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `FIRE` | 63 | 0.0635 | 0.0000 | 0.2458 | 0.0000 | 1.0000 |
| `INTRUDER` | 212 | 0.0236 | 0.0000 | 0.1521 | 0.0000 | 1.0000 |
| `NODE_OFFLINE` | 9 | 0.1111 | 0.0000 | 0.3333 | 0.0000 | 1.0000 |
| `SMOKE_WARNING` | 53 | 0.0377 | 0.0000 | 0.1924 | 0.0000 | 1.0000 |
| **Overall** | **410** | **0.0317** | **0.0000** | **0.1754** | **0.0000** | **1.0000** |

Table 4.20 shows that the system created alert records very quickly under the local-first setup. The overall mean latency was 0.0317 seconds, and the maximum observed latency was 1.0000 second. The low latency values indicate that local event ingestion and alert creation were responsive during testing. The slightly higher means for fire and node-offline alerts may be due to additional processing or timing differences in the alert workflow.

[Figure 4.18]

Figure 4.18 shows the response-time summary generated from `chapter4_outputs/06_response_time_summary.png`. The figure compares mean event-to-alert latency by alert type and supports the finding that the local system produced alerts rapidly.

## 4.10 Snapshot and Evidence Capture Analysis

The system supported snapshot evidence for several major scenarios. Snapshot paths were attached to event and alert records when camera evidence was available. These paths were visible in the exported logs and were also displayed in the Snapshot Gallery.

Table 4.21 presents representative event and alert records with linked snapshots.

**Table 4.21**

**Representative Event and Alert Evidence Records**

| Scenario | Event ID | Alert ID | Event Code | Alert Type | Snapshot Path |
| --- | ---: | ---: | --- | --- | --- |
| Smoke Node 1 high smoke | 7711 | 5321 | `SMOKE_HIGH` | `SMOKE_WARNING` | `/snapshots/2026-05-03/smoke_warning_cam_indoor_145120.jpg` |
| Smoke Node 1 high smoke | 7706 | 5316 | `SMOKE_HIGH` | `SMOKE_WARNING` | `/snapshots/2026-05-03/smoke_warning_cam_indoor_144805.jpg` |
| Forced door opening attempt | 7690 | 5301 | `DOOR_FORCE` | `INTRUDER` | `/snapshots/2026-05-03/intruder_unknown_cam_door_144136.jpg` |
| Forced door opening attempt | 7686 | 5297 | `DOOR_FORCE` | `INTRUDER` | `/snapshots/2026-05-03/intruder_unknown_cam_door_143900.jpg` |
| Authorized entry | 7746 | 5356 | `AUTHORIZED` | `AUTHORIZED_ENTRY` | `/snapshots/2026-05-03/authorized_presence_cam_door_151640.jpg` |
| Unknown person detected | 7712 | 5322 | `UNKNOWN` | `INTRUDER` | `/snapshots/2026-05-03/intruder_unknown_presence_cam_indoor_145325.jpg` |

Table 4.21 shows that events and alerts were not only stored as text records. The system also attached visual evidence through snapshot paths. This strengthens the monitoring workflow because users can review what the camera captured during smoke, intrusion, authorized-entry, or unknown-person events.

The snapshot evidence also shows the importance of the cameras in the system. Sensor nodes provide fast trigger signals, while camera snapshots provide contextual evidence that helps users verify whether an event requires action.

## 4.11 Chapter Synthesis

The Chapter 4 results show that the developed prototype successfully integrated smoke nodes, a door-force sensor node, camera monitoring, backend processing, event logging, alert generation, snapshot evidence, dashboard monitoring, and mobile monitoring support. The exported logs confirmed that the system recorded multiple event types, including `SMOKE_HIGH`, `SMOKE_NORMAL`, `DOOR_FORCE`, `AUTHORIZED`, `UNKNOWN`, and `FLAME_SIGNAL`. The alert logs confirmed that the system created `SMOKE_WARNING`, `INTRUDER`, `FIRE`, `AUTHORIZED_ENTRY`, `NODE_OFFLINE`, and `CAMERA_OFFLINE` alerts.

The results also show that the system performed best in face recognition. The face recognition module achieved 88.89% accuracy, with strong results for authorized and non-authorized classifications. The smoke and fire workflow achieved 80.00% accuracy, which is a considerable result but still shows the need to refine visual fire/fusion sensitivity in some normal-condition cases. The door-force and intruder workflow also achieved 80.00% accuracy, indicating that forced-door events and authorized-entry cases were generally handled correctly, while no-face cases still required improved distinction from intruder evidence.

The overall accuracy across all usable reviewed trials was 83.33%. This result indicates that the prototype is operational and capable of producing a complete monitoring workflow with considerable classification performance under controlled testing conditions. The main remaining improvement areas are fire/fusion sensitivity under normal visual conditions and no-face handling in face-related and intrusion-related review cases.

The response-time analysis showed strong local performance. Across 410 event-to-alert pairs, the mean response time was 0.0317 seconds, with a maximum observed latency of 1.0000 second. This supports the suitability of the local-first architecture for timely alert recording and presentation.

Overall, the system met the main implementation objective of creating an integrated intruder and fire monitoring alert system for a condo-like environment. It demonstrated the ability to detect and log sensor and camera events, generate alerts, display monitoring information, and preserve camera evidence for review. The results support the relevance of the system to safer residential monitoring and align with the broader goals of SDG 3 on good health and well-being, SDG 9 on innovation and infrastructure, and SDG 11 on safer and more sustainable communities. However, the evaluation also shows that additional testing and tuning, especially for no-face and ambiguous door-force conditions, are necessary before the prototype can be considered fully reliable for long-term deployment.
