# Face Recognition Module Results

This section should present the results of enrollment, training, and live classification tests for the face-recognition pipeline. It is appropriate to discuss whether the system correctly classifies enrolled faces as authorized, identifies unknown persons as non-authorized, and returns no-face results when no usable face is present.

## Suggested narrative

The face-recognition module was evaluated using controlled face samples and live camera observations. The researchers observed whether enrolled users were correctly classified as authorized and whether unknown individuals were correctly flagged as non-authorized. Additional observations may include the behavior of the module under low-light conditions, partial pose variation, motion blur, and frames where no face was detectable.

## Recommended statistics
- Accuracy
- Precision
- Recall or Sensitivity
- Specificity
- F1-score
- False Positive Rate
- False Negative Rate

## Table Template: Face Recognition Scenario Results

| Trial No. | Scenario | Expected Output | Actual Output | Correct? | Remarks |
| --- | --- | --- | --- | --- | --- |
| 1 | Enrolled person appears | AUTHORIZED | [Fill in] | [Fill in] | [Fill in] |
| 2 | Unknown person appears | NON-AUTHORIZED | [Fill in] | [Fill in] | [Fill in] |
| 3 | No clear face in frame | NO-FACE | [Fill in] | [Fill in] | [Fill in] |

## Table Template: Face Recognition Metrics Summary

| Metric | Value |
| --- | --- |
| Accuracy | [Fill in] |
| Precision | [Fill in] |
| Recall / Sensitivity | [Fill in] |
| Specificity | [Fill in] |
| F1-score | [Fill in] |
| False Positive Rate | [Fill in] |
| False Negative Rate | [Fill in] |

## Interpretation guide

After completing the table, discuss which conditions produced the strongest and weakest results. If authorized faces were recognized consistently while unknown faces were rejected appropriately, that supports the effectiveness of the module. If missed detections occurred, explain whether lighting, pose, blur, or training-sample quality may have contributed.
