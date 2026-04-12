## Data Analysis for Specific Objective #1

## Objective

**Specific Objective #1:** Design the overall system architecture that integrates the Raspberry Pi with a night-vision camera for intruder and fire-related visual monitoring.

## Truth Table for Data Analysis

Use one `trial_id` for each recorded observation.

For confusion-matrix analysis, code each condition as:

- `1 = event present`
- `0 = no event`

For intruder monitoring, `event present` means an unknown or suspicious person is present.

For flame monitoring, `event present` means a visible flame is present.

For smoke monitoring, `event present` means a smoke event is present.

For door-force monitoring, `event present` means an abnormal door-force or forced-entry event is present.

| Trial | Input                   | Output                    | Variable      |
| ----- | ----------------------- | ------------------------- | ------------- |
| 1     | `actual_intruder = 1`   | `detected_intruder = 1`   | `TP_intruder` |
| 2     | `actual_intruder = 0`   | `detected_intruder = 0`   | `TN_intruder` |
| 3     | `actual_intruder = 0`   | `detected_intruder = 1`   | `FP_intruder` |
| 4     | `actual_intruder = 1`   | `detected_intruder = 0`   | `FN_intruder` |
| 5     | `actual_flame = 1`      | `detected_flame = 1`      | `TP_flame`    |
| 6     | `actual_flame = 0`      | `detected_flame = 0`      | `TN_flame`    |
| 7     | `actual_flame = 0`      | `detected_flame = 1`      | `FP_flame`    |
| 8     | `actual_flame = 1`      | `detected_flame = 0`      | `FN_flame`    |
| 9     | `actual_smoke = 1`      | `detected_smoke = 1`      | `TP_smoke`    |
| 10    | `actual_smoke = 0`      | `detected_smoke = 0`      | `TN_smoke`    |
| 11    | `actual_smoke = 0`      | `detected_smoke = 1`      | `FP_smoke`    |
| 12    | `actual_smoke = 1`      | `detected_smoke = 0`      | `FN_smoke`    |
| 13    | `actual_door_force = 1` | `detected_door_force = 1` | `TP_door`     |
| 14    | `actual_door_force = 0` | `detected_door_force = 0` | `TN_door`     |
| 15    | `actual_door_force = 0` | `detected_door_force = 1` | `FP_door`     |
| 16    | `actual_door_force = 1` | `detected_door_force = 0` | `FN_door`     |

## Statistical Treatment

Use `Confusion Matrix`.

## How the Confusion Matrix Will Be Used

For each recorded trial, compare the actual value and the detected value, then classify the row using the truth table above.

Count the total number of:

- `TP_intruder`, `TN_intruder`, `FP_intruder`, `FN_intruder`
- `TP_flame`, `TN_flame`, `FP_flame`, `FN_flame`
- `TP_smoke`, `TN_smoke`, `FP_smoke`, `FN_smoke`
- `TP_door`, `TN_door`, `FP_door`, `FN_door`

Those totals form the confusion matrix for intruder, flame, smoke, and door-force monitoring.
