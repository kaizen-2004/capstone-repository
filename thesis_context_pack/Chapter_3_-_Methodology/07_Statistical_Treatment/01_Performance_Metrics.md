# Performance Metrics for Detection Modules and System

The following performance metrics are recommended for the technical evaluation of the prototype:

## 1. Detection and Classification Metrics
- Accuracy
- Precision
- Recall or Sensitivity
- Specificity
- F1-score
- False Positive Rate (FPR)
- False Negative Rate (FNR)

These metrics are applied where ground-truth labels are available, especially for:
- face recognition outcomes (authorized vs. unknown or non-authorized)
- fire-related decisions (fire-confirmed vs. not-confirmed)
- door-force trigger classification when repeated labeled trials are performed

## 2. Descriptive Counts and Rates
- Frequency
- Percentage
- Number of correct detections
- Number of missed detections
- Number of false alarms

These are used for repeated scenario runs and daily summary analysis.

## 3. Response-Time Metrics
- Mean latency
- Median latency
- Standard deviation
- Minimum latency
- Maximum latency

These are used to evaluate the time difference between event occurrence and alert presentation or logging.
