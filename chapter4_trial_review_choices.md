# Chapter 4 Trial Review Choices

Use these fixed choices when filling `chapter4_trial_review_sheet.csv`.

## expected_label

| Choice | Use When |
| --- | --- |
| NORMAL | No smoke, no fire, no forced entry, or normal condition is expected. |
| SMOKE | Smoke/high smoke should be detected. |
| FIRE | A visual fire/flame or fire-fusion alert should be detected. |
| INTRUDER | Forced door activity or unauthorized entry should be detected. |
| AUTHORIZED | An enrolled or authorized person should be recognized. |
| NON_AUTHORIZED | An unknown or non-authorized person should be detected. |
| NO_FACE | No usable face should be detected in the frame. |

## correct

| Choice | Use When |
| --- | --- |
| YES | The predicted label matches the expected label. |
| NO | The predicted label does not match the expected label. |
| REVIEW | The evidence is unclear and should be checked again before final computation. |

Use only `YES` or `NO` in the final version. Keep `REVIEW` temporary while checking screenshots and snapshots.

## remarks

| Choice | Use When |
| --- | --- |
| Correct smoke warning alert created | Smoke/high smoke produced a smoke warning alert. |
| Correct smoke normal result | Smoke returned to normal or no smoke alert was expected. |
| Correct fire fusion alert created | Flame/fire evidence produced a fire alert. |
| Correct forced-door intruder alert created | Door-force activity produced an intruder alert. |
| Correct authorized entry classification | Authorized person was correctly recognized. |
| Correct non-authorized classification | Unknown/non-authorized person was correctly flagged. |
| Correct no-face review alert | Trigger was detected but no usable face was captured. |
| False positive alert | System generated an alert when the expected result was normal. |
| False negative missed alert | System failed to generate the expected alert. |
| Wrong classification | System detected something but assigned the wrong class. |
| Snapshot evidence missing | Event/alert exists but no snapshot was available. |
| Snapshot evidence unclear | Snapshot exists but does not clearly support the decision. |
| Excluded from computation | Trial should not be used in final metrics due to unclear evidence or test error. |
