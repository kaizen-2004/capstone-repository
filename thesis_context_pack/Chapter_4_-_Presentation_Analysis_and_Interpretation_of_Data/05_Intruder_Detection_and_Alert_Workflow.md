# Intruder Detection and Alert Workflow Results

This section should focus on the event-to-alert behavior of the intruder pipeline, including trigger detection, selective face analysis, classification, and alert creation.

## Suggested narrative

The intruder workflow was assessed by observing how the system responded to door-force events and person-related triggers near the monitored entrance. The researchers examined whether the system correctly classified authorized individuals, flagged unknown persons, and generated persistent alerts that could be acknowledged through the local dashboard.

## Table Template: Intruder Workflow Results

| Trial No. | Trigger Event | Face Result | Final Alert / Classification | Expected Outcome | Correct? | Remarks |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Door-force event with authorized person | [Fill in] | [Fill in] | [Fill in] | [Fill in] | [Fill in] |
| 2 | Door-force event with unknown person | [Fill in] | [Fill in] | [Fill in] | [Fill in] | [Fill in] |
| 3 | Trigger with no detectable face | [Fill in] | [Fill in] | [Fill in] | [Fill in] | [Fill in] |

## Interpretation guide

Discuss whether the trigger-to-classification path behaved consistently. If cooldown or suppression logic prevented duplicate alerts, mention this explicitly and explain how it contributed to a cleaner alert history.
