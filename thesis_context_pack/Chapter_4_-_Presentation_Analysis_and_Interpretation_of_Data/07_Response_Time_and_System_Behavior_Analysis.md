# Response Time and System Behavior Analysis

This section should analyze how quickly the system responded after a trigger event and how stable the workflow remained across repeated tests.

## Suggested narrative

Response time was evaluated by measuring the time interval between event occurrence and the creation or presentation of the corresponding alert. Separate latency summaries may be prepared for authorized-entry recognition, non-authorized detection, smoke-triggered fire evaluation, and other major scenarios.

## Recommended statistics
- Mean latency
- Median latency
- Standard deviation
- Minimum latency
- Maximum latency

## Table Template: Response-Time Results

| Trial No. | Scenario | Event Timestamp | Alert Timestamp | Latency (seconds) | Remarks |
| --- | --- | --- | --- | --- | --- |
| 1 | [Fill in] | [Fill in] | [Fill in] | [Fill in] | [Fill in] |
| 2 | [Fill in] | [Fill in] | [Fill in] | [Fill in] | [Fill in] |
| 3 | [Fill in] | [Fill in] | [Fill in] | [Fill in] | [Fill in] |

## Table Template: Latency Summary

| Metric | Value |
| --- | --- |
| Mean | [Fill in] |
| Median | [Fill in] |
| Standard Deviation | [Fill in] |
| Minimum | [Fill in] |
| Maximum | [Fill in] |

## Interpretation guide

Discuss whether latency remained acceptable across repeated runs and note any scenario that produced higher delays. If certain event types required more processing time because they triggered camera analysis, this should be explained rather than hidden.
