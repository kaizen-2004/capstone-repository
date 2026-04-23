# Fire Detection Module Results

This section should discuss the fire-related behavior of the system. Because the implemented logic is smoke-first, the presentation should make clear that smoke events act as the primary trigger and camera-based analysis acts as confirmation support.

## Suggested narrative

The fire-detection workflow was evaluated using controlled smoke-related scenarios and safe visual confirmation tests. The researchers observed whether smoke events correctly initiated the fire-evaluation sequence and whether camera-based visual analysis strengthened or rejected possible fire interpretation. Special attention should be given to nuisance conditions such as steam, lighting artifacts, and non-fire bright objects.

## Recommended statistics
- Accuracy
- Recall or Sensitivity
- Specificity
- False Positive Rate
- False Negative Rate

## Table Template: Fire Scenario Results

| Trial No. | Scenario | Smoke Triggered? | Visual Confirmation? | Final System Decision | Correct? | Remarks |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Smoke without visible flame | [Fill in] | [Fill in] | [Fill in] | [Fill in] | [Fill in] |
| 2 | Smoke with visible flame cue | [Fill in] | [Fill in] | [Fill in] | [Fill in] | [Fill in] |
| 3 | Nuisance condition (steam/light) | [Fill in] | [Fill in] | [Fill in] | [Fill in] | [Fill in] |

## Table Template: Fire Detection Metrics Summary

| Metric | Value |
| --- | --- |
| Accuracy | [Fill in] |
| Sensitivity | [Fill in] |
| Specificity | [Fill in] |
| False Positive Rate | [Fill in] |
| False Negative Rate | [Fill in] |

## Interpretation guide

Explain whether the smoke-first logic helped reduce false positives. If nuisance conditions did not escalate into full fire alerts without supporting evidence, that should be highlighted as a strength. If any smoke or visual scenarios produced incorrect outcomes, discuss possible causes and threshold-adjustment implications.
