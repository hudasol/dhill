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
| Operating ambient | **-20 to 45 degC** | not a model input; used as the comparison in the operating calendar | datasheet |
| Cooling | none listed | cooling capacity zero | datasheet (absence) |

Not in the datasheet, so assumed and flagged in the YAML: battery voltage and cell data, all heat capacities and
conductances, paint absorptance, LiDAR (the base robot has none; the node models a typical add on), all
component temperature limits, DC-DC efficiency, IP rating.

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
The operating calendar (`docs/operating-calendar.md`) quantifies how many hours per site and month fall outside such ratings.
