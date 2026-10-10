# Literature log

**Status: preliminary web-search pass, 2026-10-10 (Claude, on behalf of the author). NOT a systematic search.**
IEEE Xplore, Scopus and Web of Science need institutional access and were not searched. OpenAlex, arXiv's API and
Crossref could not be queried from the build environment (error / robots disallowed / rate limit). Google Scholar
was not queried directly. Treat "no near-duplicate found" as "not found by a shallow search", and repeat the
protocol in `literature-search-protocol.md` on the real databases before any novelty claim.

## Queries run (general web search)
| # | Query (abridged) | Date | Result |
|---|---|---|---|
| 1 | thermal operating envelope unmanned ground vehicle hot desert ambient derating forecast mission planning | 2026-10-10 | No UGV thermal-envelope tool. UAV desert thermal-management and UGV thermal-camera papers only. |
| 2 | lumped thermal network mobile robot battery electronics Monte Carlo uncertainty go/no-go heat | 2026-10-10 | Battery-pack thermal modelling and EV literature; no robot go/no-go work. |
| 3 | thermal-aware mission planning robot battery ageing scheduling weather forecast high ambient | 2026-10-10 | Energy-aware planning, thermal-aware locomotion (arXiv 2603.01631); none combine forecast, ageing and scheduling. |
| 4 | UAE Gulf outdoor robot heat dust operating limits LiDAR dust range degradation | 2026-10-10 | Found `desert-av-reliability` (below) and LiDAR-dust physics (Phillips et al. 2017). |
| 5 | weather-aware go/no-go robot deployment temperature forecast component thermal limits "operating envelope" | 2026-10-10 | Found Moore et al. 2012 (below). |

## Nearest works found
| Work | What it does | How Dhill differs |
|---|---|---|
| Moore et al., "Thermal Modeling for Temperature Aware Operations in Field Robots" (2012; venue/authors not fully verified, seen via an Academia.edu listing) | Grey-box system identification of a small robot's thermal dynamics; predicts temperatures over a 20-minute horizon to a few °C. | Dhill adds weather forecasts, multi-component limits, Monte Carlo risk quantiles, GO/DERATE/PARK decisions with evidence levels, dust/perception effects, scheduling. **Closest conceptual precedent: cite it.** |
| HemanthMChakravarthy/desert-av-reliability (GitHub, MIT, companion code for an IEEE IV 2027 paper) | Illustrative reliability models for L4 vehicle sensors (LiDAR, camera, thermal, GNSS) in UAE/GCC desert; valid/invalid ODD rule that names the binding constraint; Monte Carlo. | Sensor-reliability and ODD focus on road vehicles with infrastructure mitigation. No component thermal limits, battery or derate decision found in the README. **Same region and same "illustrative parameters" honesty; cite and compare.** |
| Miller, Goulet, Ayalew, "Energy-aware Mission Planning for Unmanned Ground Vehicle Fleets" (SAE 2024-01-4071, GVSETS 2024) | MILP fleet routing with energy and time cost-to-go maps and charging rendezvous. | Energy, not thermal, in the abstract; Dhill's scheduler is thermal- and ageing-driven. Full text not checked. |
| Phillips et al., "When the Dust Settles: The Four Behaviors of LiDAR in the Presence of Fine Airborne Particulates", J. Field Robotics 2017 | Empirical LiDAR behaviour in dust. | Source for the perception-range effect; Dhill uses a simplified range model, not their data. |
| arXiv 2603.01631, "Learning Thermal-Aware Locomotion Policies for an Electrically-Actuated Quadruped Robot" | Learned locomotion that respects motor temperature. | Onboard control of one component; Dhill is forecast-based, fleet-level. |

## Conclusion so far
No tool combining forecast-driven, multi-component thermal limits, uncertainty-aware GO/DERATE/PARK decisions,
dust-limited perception and fleet scheduling was found in this shallow pass. Do not claim novelty until the
IEEE Xplore / Scopus / Web of Science queries are run and logged below.

## To do (needs institutional access)
- [ ] Query 1-7 of the protocol on IEEE Xplore
- [ ] Same on Scopus and Web of Science
- [ ] Google Scholar, plus patent search (Google Patents, Patentscope)
- [ ] Add results to the tables above
