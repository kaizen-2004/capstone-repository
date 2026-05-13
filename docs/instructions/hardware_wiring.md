# Condo Monitoring Hardware Wiring (Windows + RTSP Architecture)

This document defines physical wiring assumptions for active hardware.

## Global Rules

- Use a common GND on each ESP32-C3 node and attached sensor module.
- Keep ESP32-C3 GPIO at 3.3V limits.
- Use stable power for MQ-2 heater modules.
- Keep analog wiring short to reduce ADC noise.
- Use a transistor driver for buzzers instead of driving buzzer current directly from an ESP32-C3 GPIO.
- Keep the detector battery side of any PC817 optocoupler isolated from ESP32-C3 GND.

## 1) Smoke Sensor Node 1 (`smoke_node1`)

Device: ESP32-C3 + MQ-2 module (Living Room)

### Pin Mapping

- `MQ-2 VCC -> 5V`
- `MQ-2 GND -> GND`
- `MQ-2 AO -> GPIO0 (ADC)`
- `PC817 pin 4 / collector -> GPIO1`
- `PC817 pin 3 / emitter -> ESP32-C3 GND`
- `GPIO10 -> 1k -> NPN base` for buzzer switching
- `NPN emitter -> GND`
- `NPN collector -> buzzer negative`
- `Buzzer positive -> 5V`

### Notes

- If AO can exceed 3.3V, use a voltage divider before ADC.
- Recommended divider: `AO -> 10k -> ADC`, `ADC -> 20k -> GND`.
- PC817 detector-side input for the measured low-side-switched LED: `detector battery + -> 1k -> PC817 pin 1 / anode`, then `PC817 pin 2 / cathode -> detector red LED negative pad`.
- Do not connect detector battery negative to ESP32-C3 GND; the PC817 provides isolation.
- Firmware uses `GPIO1` with `INPUT_PULLUP`, so the photoelectric detector signal is active-low.
- Recommended buzzer transistor: `2N2222` or `S8050` NPN.
- Add `100k` from transistor base to GND to keep the buzzer off during boot.
- If the buzzer is magnetic or unknown type, add a flyback diode: cathode to `5V`, anode to transistor collector.

## 2) Smoke Sensor Node 2 (`smoke_node2`)

Device: ESP32-C3 + MQ-2 module (Door Entrance Area)

### Pin Mapping

- `MQ-2 VCC -> 5V`
- `MQ-2 GND -> GND`
- `MQ-2 AO -> GPIO0 (ADC)`
- `PC817 pin 4 / collector -> GPIO1`
- `PC817 pin 3 / emitter -> ESP32-C3 GND`
- `GPIO10 -> 1k -> NPN base` for buzzer switching
- `NPN emitter -> GND`
- `NPN collector -> buzzer negative`
- `Buzzer positive -> 5V`

### Notes

- If AO can exceed 3.3V, use a voltage divider before ADC.
- Recommended divider: `AO -> 10k -> ADC`, `ADC -> 20k -> GND`.
- PC817 detector-side input for the measured low-side-switched LED: `detector battery + -> 1k -> PC817 pin 1 / anode`, then `PC817 pin 2 / cathode -> detector red LED negative pad`.
- Do not connect detector battery negative to ESP32-C3 GND; the PC817 provides isolation.
- Firmware uses `GPIO1` with `INPUT_PULLUP`, so the photoelectric detector signal is active-low.
- Recommended buzzer transistor: `2N2222` or `S8050` NPN.
- Add `100k` from transistor base to GND to keep the buzzer off during boot.
- If the buzzer is magnetic or unknown type, add a flyback diode: cathode to `5V`, anode to transistor collector.

## 3) Door Force Node (`door_force`)

Device: ESP32-C3 + GY-LSM6DS3 IMU

### I2C Mapping

- `VCC -> 3V3`
- `GND -> GND`
- `SDA -> GPIO8`
- `SCL -> GPIO9`
- `INT1 -> optional GPIO10`

### Magnetic Reed Switch

- `GPIO4 -> reed switch NC`, `reed switch COM -> GND`.
- Firmware uses `INPUT_PULLUP`.
- `LOW = door closed`, `HIGH = door open`.
- Place the magnet so the reed switch is closed when the door is fully shut.

### Notes

- Use I2C pull-ups if breakout board does not provide them.
- Keep I2C wires short.
- If the reed wire disconnects, the pull-up reads the door as open and suppresses door-force alerts.

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
