# Evidence checks on the operating calendar

Rendered by `scripts/gen_evidence_checks.py` from `examples/evidence_checks.json`;
`tests/test_evidence_checks.py` fails if this document differs from that rendering. Recorded
Open-Meteo weather, profile `clearpath_jackal` (L0), engine seed 7, 64 Monte Carlo samples.

## 1. Does the PM10 fill change the calendar? (known issue 6)

Days were chosen only from the period with recorded CAMS PM10 (first complete local day per site:
abu_dhabi 2022-08-05, al_ain 2022-08-05, dubai 2022-08-05, sweihan 2022-08-05, liwa 2022-08-05, fujairah 2022-08-05; to 2025-12-31).
The full calendar chooses days from 2015 to 2025 and fills PM10 before August 2022 with CAMS
hourly medians. The two runs differ in PM10 and also in which days are selected, so the
difference is an upper bound on the effect of the fill.

| Share of hours | Full period, with fill | CAMS period only | Difference (points) |
|---|---:|---:|---:|
| GO | 63.9 % | 64.2 % | +0.3 |
| DERATE | 16.5 % | 16.2 % | -0.3 |
| PARK | 19.6 % | 19.6 % | -0.0 |

Weighted sampled days using the PM10 fill in the CAMS period run: 0.0 %.

## 2. How large is the sampling error? (known issue 7)

Site `al_ain`, year 2024: every complete local day of the year in the record (365 days; 1 January starts in the
previous UTC year, which this check does not load) against the
calendar method (five representative days per month, 10th to 90th percentile of daily maximum,
equal weight) applied to the same year. The sampled run also computes the hottest and mildest
day per month (84 days in all), which carry no weight.

| Share of hours, year | Every day | Five sampled days per month | Sampling error (points) |
|---|---:|---:|---:|
| GO | 63.6 % | 63.3 % | -0.3 |
| DERATE | 15.8 % | 16.0 % | +0.2 |
| PARK | 20.6 % | 20.7 % | +0.1 |

Per month, sampled minus every day, percentage points:

| Month | GO | DERATE | PARK |
|---|---:|---:|---:|
| Jan | -2.2 | +2.2 | +0.0 |
| Feb | +1.1 | -1.1 | +0.0 |
| Mar | +3.3 | -4.3 | +1.0 |
| Apr | +1.9 | -1.9 | +0.0 |
| May | -2.2 | +2.6 | -0.4 |
| Jun | +3.1 | -2.2 | -0.8 |
| Jul | -1.3 | +1.8 | -0.5 |
| Aug | -3.0 | +2.8 | +0.3 |
| Sep | -1.7 | +0.4 | +1.2 |
| Oct | -1.0 | -0.5 | +1.4 |
| Nov | -1.0 | +2.2 | -1.3 |
| Dec | -0.2 | +0.2 | +0.0 |

Largest monthly error: 4.3 points; mean absolute monthly error:
1.4 points.

## Limits

- One site and one year for the sampling check; other sites and years may differ.
- Both checks inherit every limit of `docs/operating-calendar.md`, including the L0 profile.
