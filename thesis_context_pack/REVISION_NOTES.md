# Revision Notes (2026-04-18)

This revision aligns the thesis pack with the current state of the project while preserving flexibility for the final deployment narrative.

## Key alignment decisions
- The thesis pack now covers **Chapters 1 to 5**.
- Implementation-facing sections were rewritten to describe the system in terms of **functional roles** instead of overcommitting to one fixed host arrangement.
- **Raspberry Pi 2** remains part of the thesis narrative as an **optional deployment component for local edge hosting**.

## Current system profile reflected in this pack
- **Monitoring scope:** two monitored areas
  - **Living Room**
  - **Door Entrance Area**
- **Core sensing and monitoring elements:**
  - night-vision-capable camera inputs
  - smoke sensing nodes
  - door-force sensing node
  - local dashboard, logs, alerts, and summaries
- **Sensor event transport:** **HTTP POST + JSON** through `POST /api/sensors/event`
- **Face pipeline:** OpenCV **YuNet + SFace** enrollment, training, and classification flow
- **Fire pipeline:** **smoke-first** logic with camera-based flame confirmation
- **Alert workflow:** local alert generation, acknowledgment, persistence, and optional remote delivery layers

## Chapter 4 and 5 notes
- **Chapter 4** is scaffolded with table templates and sample narrative text.
- No fabricated final measured results were inserted.
- Statistical guidance was updated to favor:
  - descriptive statistics for technical testing
  - confusion-matrix metrics for detection modules
  - weighted mean and standard deviation for optional user evaluation
  - chi-square only when grouped respondent comparisons are actually conducted

## Illustration policy
- Diagram sections use **ASCII or Markdown-native layouts** for portability and easy editing.
