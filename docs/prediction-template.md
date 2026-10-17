# Preregistered prediction (commit this file BEFORE the validation run)

- Date / time of registration (UTC):
- Git commit of Dhill used:
- Profile id and file hash:
- Calibration data used (files + dates):
- Weather source and forecast issue time:
- Site, route, mission mode, duration:

## Predictions (from `dhill decide` / `dhill timeline`)
| Slot (UTC) | Decision | Predicted peak (risk quantile) per component | Binding constraint | P(exceed hard limit) |
|---|---|---|---|---|

## What would count as a failure (write this now)
- A measured peak exceeds the predicted risk quantile peak by more than ___ K in more than ___ % of slots.
- A GO slot reaches a hard limit.
- Other:

## After the run (fill in, do not edit the above)
| Slot | Measured peak per component | Within prediction? | Notes |
|---|---|---|---|

Summary of misses, and what changes in the model because of them:
