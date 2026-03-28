# Condo Monitoring Hardware Wiring (Windows + RTSP Architecture)

This document defines physical wiring assumptions for active hardware.

## Global Rules

- Use a common GND on each ESP32-C3 node and attached sensor module.
- Keep ESP32-C3 GPIO at 3.3V limits.
- Use stable power for MQ-2 heater modules.
- Keep analog wiring short to reduce ADC noise.

## 1) Smoke Sensor Node 1 (`smoke_node1`)

Device: ESP32-C3 + MQ-2 module (Living Room)

### Pin Mapping

- `MQ-2 VCC -> 5V`
- `MQ-2 GND -> GND`
- `MQ-2 AO -> GPIO0 (ADC)`
- `MQ-2 DO -> optional GPIO1`

### Notes

- If AO can exceed 3.3V, use a voltage divider before ADC.
- Recommended divider: `AO -> 10k -> ADC`, `ADC -> 20k -> GND`.

## 2) Smoke Sensor Node 2 (`smoke_node2`)

Device: ESP32-C3 + MQ-2 module (Door Entrance Area)

### Pin Mapping

- `MQ-2 VCC -> 5V`
- `MQ-2 GND -> GND`
- `MQ-2 AO -> GPIO0 (ADC)`
- `MQ-2 DO -> optional GPIO1`

## 3) Door Force Node (`door_force`)

Device: ESP32-C3 + GY-LSM6DS3 IMU

### I2C Mapping

- `VCC -> 3V3`
- `GND -> GND`
- `SDA -> GPIO8`
- `SCL -> GPIO9`
- `INT1 -> optional GPIO10`

### Notes

- Use I2C pull-ups if breakout board does not provide them.
- Keep I2C wires short.

## 4) Cameras (RTSP IP Night-Vision)

Cameras are independent IP units and are not wired to ESP32 boards.

### Camera 1 (`cam_indoor`)

- Placement: Living Room
- Protocol: RTSP
- Role: person presence + fire confirmation + selective face matching

### Camera 2 (`cam_door`)

- Placement: Door Entrance Area
- Protocol: RTSP
- Role: entry person detection + selective face matching + door-force correlation

### Backend Variables

- `CAMERA_INDOOR_RTSP`
- `CAMERA_DOOR_RTSP`

Both cameras should be configured to ~720p at 10-15 FPS processing target.
