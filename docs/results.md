# Results from the shipped examples

All numbers come from synthetic weather and illustrative L0 profiles. They show what the method does; they are not field results.
Reproduce with the commands shown. Outputs are deterministic for a given seed.

## 1. One day, medium inspection UGV, Sweihan heatwave (1 h missions)

```
ugv_medium_inspection @ sweihan  (synthetic, L0)  1 h missions
08-05T00:00  GO     1.00 #################### battery
08-05T02:00  GO     1.00 #################### compute_die
08-05T04:00  DERATE 0.57 ############         battery
08-05T06:00  PARK   0.00                      battery
08-05T08:00  PARK   0.00                      lidar
08-05T10:00  PARK   0.00                      battery
08-05T12:00  PARK   0.00                      battery
08-05T14:00  PARK   0.00                      battery
08-05T16:00  DERATE 0.78 ################     battery
08-05T18:00  GO     1.00 #################### battery
08-05T20:00  GO     1.00 #################### battery
08-05T22:00  GO     1.00 #################### battery
08-06T00:00  GO     1.00 #################### battery
```

`dhill timeline --site sweihan --scenario heatwave --step-min 120`

## 2. Fleet schedule versus a fixed shift

```
Dhill plan: 12.0 h of 12 h demand, 0 predicted limit breaches (optimal)
Fixed 08:00-17:00 shift at full speed: 2.0 h usable, 22 of 24 blocks would breach a limit
```

The "breach" count is relative to Dhill's own L0 envelope model. It says the fixed shift would have been unsafe *if the model is right*, which is the question a field trial must answer.

## 3. Does ignoring uncertainty hurt? (synthetic hidden robot)

```
profile                            productive h  unsafe slots  lost vs truth h
L0 nominal (ignores uncertainty)           20.9             8              0.0
L0 prior + uncertainty                     13.9             0              5.3
L2 calibrated + uncertainty                13.2             0              6.0
hidden truth (zero uncertainty)            19.2             0              0.0

calibration RMSE hold-out 0.39 K (prior 1.17 K)
```

`python examples/value_of_calibration.py`

Reading the table:
- A nominal model that ignores parameter uncertainty promises 20.9 productive hours and is unsafe in 8 slots compared with the hidden robot, which is actually hotter than the prior assumed.
- Carrying uncertainty keeps every slot safe at the cost of about 5 hours of caution.
- Calibration cut hold-out temperature error from about 1.2 K to 0.4 K, but only five parameters were fitted; the rest keep their prior spread, so the calibrated envelope is still conservative. More fitted parameters and a real field campaign (validation protocol, level L3) are what close that gap. Calibration here made the robot's true heat visible, not more permissive.
- The calibration step is an inverse crime (the same model generates and fits the data). Recovery on real telemetry will be harder; see the model card.

## 4. Live forecast run

`examples/live_forecast_abu_dhabi_2026-10-10.txt` is a real run on Open-Meteo data for Abu Dhabi on 10 October 2026: the illustrative UGV is GO overnight, derates 05:00 to 06:00 UTC, is parked 07:00 to 11:00 UTC, and returns to GO from 14:00 UTC. Same caveats: L0 profile, no field validation.
