# Robot sources

Where the numbers in the `clearpath_jackal` profile come from, what is assumed, and what is still unknown.
Retrieved 2026-10-15 from public manufacturer documents. Re-check before quoting.

## Clearpath Jackal (profile `clearpath_jackal`)
Source: Clearpath Jackal datasheet, September 2020 (copy hosted by Generation Robots):
https://www.generationrobots.com/media/Jackal_mobile_robot_DataSheet_Sept2020.pdf

| Quantity | Value | Used as | Provenance |
|---|---|---|---|
| Size (L x W x H) | 508 x 430 x 250 mm | geometry | datasheet |
| Mass | 17 kg | split into shell, interior and pack heat capacities | datasheet (split assumed) |
| Maximum speed | 2.0 m/s | not used directly; 1.0 m/s assumed for inspection | datasheet |
| Drive power | 500 W | upper bound; not the operating draw | datasheet |
| Battery | Li ion, 270 Wh | pack energy (7S2P x 5.4 Ah x 3.6 V = 272 Wh) | datasheet energy; cells assumed |
| Runtime | about 2 h heavy use, 8 h basic | drive mode power chosen so full scale draw is about 133 W | datasheet, tested |
| Onboard computer | Intel Core i3-4330TE or i5-4570TE | 35 W class compute node | datasheet CPU; power is the Intel class value |
| Operating ambient | **-20 to 45 degC** | consistency constraint on the assumed conductances (a test requires every component inside its hard limit at 45 degC in shade under sustained heavy use); also the comparison in the operating calendar | datasheet |
| Cooling | none listed | cooling capacity zero | datasheet (absence) |

Not in the datasheet, so assumed and flagged in the YAML: battery voltage and cell data, all heat capacities and
conductances, paint absorptance, LiDAR (the base robot has none; the node models a typical add on), all
component temperature limits, DC-DC efficiency, IP rating.

The conductances `ua_shell_interior`, `ua_compute_interior` and `ua_battery_interior` are not measured. They were first scaled by area from the medium UGV profile, which made the robot overheat at 36 degC air, contradicting the rated 45 degC. They were then raised until the profile was consistent with the rating (see `tests/test_profiles.py`). This makes them plausible, not known.

**Plausibility check of the three raised conductances (order of magnitude, assumption).** Heat transfer
coefficients for free convection in gases are typically 2 to 25 W/(m2 K) (Incropera et al., *Fundamentals of
Heat and Mass Transfer*, Table 1.1); linearised internal radiation near 50 degC adds roughly 6 to 7 W/(m2 K)
for emissivity about 0.9.

| Conductance | Value | Implied coefficient | Reading |
|---|---|---|---|
| `ua_shell_interior_w_k` | 12.0 W/K | about 13 W/(m2 K) over the 0.9 m2 shell area from the datasheet dimensions; the medium UGV profile uses about 5 W/(m2 K) | Upper end of what free convection plus radiation can give. Plausible only if the chassis conducts heat to the shell or internal fans move air; the datasheet lists neither. |
| `ua_compute_interior_w_k` | 4.5 W/K | 0.22 K/W heat sink to interior air | Typical of a fan cooled processor heat sink; implausible for a small passive sink in still air (about 1 to 3 K/W). Requires a processor fan, which the datasheet does not mention. |
| `ua_battery_interior_w_k` | 2.0 W/K | about 30 W/(m2 K) over an assumed 0.07 m2 pack surface (pack dimensions not public) | Above free convection alone. Plausible only if the pack is clamped to a metal chassis. |

These values are the least constraining set that satisfies the rated ambient test, not measurements. If a
real unit has no processor fan and a pack in free air, the profile is too optimistic and the rated ambient
claim itself would need checking. They are the first three items to measure (`docs/field-test-kit.md`).

The consistency test runs 8 h of full scale driving, longer than the 2 h heavy use runtime, and the simulator
does not stop at an empty pack (state of charge goes negative). The thermal conclusion does not depend on
this: the peaks are within 0.5 K of steady state after 2 h (battery 54.6 degC at 2 h, 55.1 degC at 8 h,
45 degC air, no sun; computed with the profile on this branch).

Result: 5 of 60 parameters are datasheet values, 83% are assumptions. The profile stays at evidence level L0.
Reaching L1 needs the unit weighed, its pack and cell identified, and its component limits taken from the
component datasheets. Reaching L2 needs the telemetry run in `docs/field-test-kit.md`.

## Clearpath Husky A200 (not yet a profile)
Sources: [datasheet](https://www.generationrobots.com/media/A-000000-01946/HUSKY_DATA_SHEET-v2_editeda.pdf),
[user manual](https://docs.clearpathrobotics.com/docs_robots/outdoor_robots/husky/a200/user_manual_husky).

| Quantity | Value |
|---|---|
| Size / mass | 990 x 670 x 390 mm, 50 kg |
| Battery | sealed lead acid, 24 V, 20 Ah (needs a lead acid model; the engine is Li ion) |
| Max speed / payload | 1.0 m/s, 75 kg (20 kg all terrain) |
| Operating ambient | datasheet -10 to 30 degC; manual up to 40 degC, not in direct sunlight (the two disagree) |
| Ingress protection | IP44, IP55 with weatherproofing kit |
| Thermal behaviour | shuts down at a 50 degC thermal limit; motor casing temperature lags coil temperature |

## Why this matters
Both robots are rated to an ambient air temperature at or below 45 degC. Gulf summer afternoons exceed that, and
a robot parked in sun runs hotter than the air. The Husky's own datasheet and manual disagree on its limit.
The operating calendar (next step) quantifies how many hours per site and month fall outside such ratings.
