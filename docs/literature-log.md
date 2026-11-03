# Literature log

**Status: preliminary web search pass, 2026-10-10. NOT a systematic search.**
IEEE Xplore, Scopus and Web of Science need institutional access and were not searched. OpenAlex, arXiv's API and
Crossref could not be queried from the build environment (error / robots disallowed / rate limit). Google Scholar
was not queried directly. Treat "no near duplicate found" as "not found by a shallow search", and repeat the
protocol in `literature-search-protocol.md` on the real databases before any novelty claim.

## Queries run (general web search)
| # | Query (abridged) | Date | Result |
|---|---|---|---|
| 1 | thermal operating envelope unmanned ground vehicle hot desert ambient derating forecast mission planning | 2026-10-10 | No UGV thermal envelope tool. UAV desert thermal management and UGV thermal camera papers only. |
| 2 | lumped thermal network mobile robot battery electronics Monte Carlo uncertainty go/no-go heat | 2026-10-10 | Battery pack thermal modelling and EV literature; no robot go/no-go work. |
| 3 | thermal aware mission planning robot battery ageing scheduling weather forecast high ambient | 2026-10-10 | Energy-aware planning, thermal aware locomotion (arXiv 2603.01631); none combine forecast, ageing and scheduling. |
| 4 | UAE Gulf outdoor robot heat dust operating limits LiDAR dust range degradation | 2026-10-10 | Found `desert-av-reliability` (below) and LiDAR dust physics (Phillips et al. 2017). |
| 5 | weather aware go/no-go robot deployment temperature forecast component thermal limits "operating envelope" | 2026-10-10 | Found Moore et al. 2012 (below). |

## Nearest works found
| Work | What it does | How Dhill differs |
|---|---|---|
| Moore et al., "Thermal Modeling for Temperature Aware Operations in Field Robots" (2012; venue/authors not fully verified, seen via an Academia.edu listing) | Grey box system identification of a small robot's thermal dynamics; predicts temperatures over a 20-minute horizon to a few °C. | Dhill adds weather forecasts, multicomponent limits, Monte Carlo risk quantiles, GO/DERATE/PARK decisions with evidence levels, dust/perception effects, scheduling. **Closest conceptual precedent: cite it.** |
| HemanthMChakravarthy/desert-av-reliability (GitHub, MIT, companion code for an IEEE IV 2027 paper) | Illustrative reliability models for L4 vehicle sensors (LiDAR, camera, thermal, GNSS) in UAE/GCC desert; valid/invalid ODD rule that names the binding constraint; Monte Carlo. | Sensor reliability and ODD focus on road vehicles with infrastructure mitigation. No component thermal limits, battery or derate decision found in the README. **Same region and same "illustrative parameters" honesty; cite and compare.** |
| Miller, Goulet, Ayalew, "Energy-aware Mission Planning for Unmanned Ground Vehicle Fleets" (SAE 2024-01-4071, GVSETS 2024) | MILP fleet routing with energy and time cost to go maps and charging rendezvous. | Energy, not thermal, in the abstract; Dhill's scheduler is thermal- and ageing driven. Full text not checked. |
| Phillips et al., "When the Dust Settles: The Four Behaviors of LiDAR in the Presence of Fine Airborne Particulates", J. Field Robotics 2017 | Empirical LiDAR behaviour in dust. | Source for the perception range effect; Dhill uses a simplified range model, not their data. |
| arXiv 2603.01631, "Learning Thermal-Aware Locomotion Policies for an Electrically-Actuated Quadruped Robot" | Learned locomotion that respects motor temperature. | Onboard control of one component; Dhill is forecast based, fleet level. |

## Verified references (18 October 2026)

DOIs were checked against the publisher or index page, and against the owner's local PDF copies where one
exists. The PDFs are kept in `sourced data/`, which git ignores; they are not redistributed.

| Work | DOI | Local copy |
|---|---|---|
| Phillips, T. G., Guenther, N. and McAree, P. R. (2017), "When the Dust Settles: The Four Behaviors of LiDAR in the Presence of Fine Airborne Particulates", *Journal of Field Robotics* 34(5), 985 to 1009 | [10.1002/rob.21701](https://doi.org/10.1002/rob.21701) | Matches: title, authors and the DOI appear in the PDF (25 pages). |
| Miller, N., Goulet, N. and Ayalew, B. (2024), "Energy-aware Mission Planning for Unmanned Ground Vehicle Fleets", SAE Technical Paper 2024-01-4071, GVSETS 2024, Novi, Michigan | [10.4271/2024-01-4071](https://doi.org/10.4271/2024-01-4071) | Matches: title, authors and venue on the first page (9 pages, Clemson University). The PDF itself prints no DOI; the DOI is from the SAE Mobilus listing. The PDF's embedded metadata carries an unrelated template title. |
| Qian, L., Wan, Y., Wang, S. and Luo, X. (2026), "Learning Thermal-Aware Locomotion Policies for an Electrically-Actuated Quadruped Robot", arXiv:2603.01631 | [10.48550/arXiv.2603.01631](https://doi.org/10.48550/arXiv.2603.01631) (arXiv DOI) | Matches: title and authors (6 pages, Huazhong University of Science and Technology). |
| Moore et al. (2012), "Thermal Modeling for Temperature Aware Operations in Field Robots" | Not found | **Wrong paper.** The file with this name contains "Failure Mode Analysis of Mechanical Seals" by J. Singh, S. Angra and V. K. Mittal, *Journal of Engineering and Technology* 2(2), 2012 (DOI 10.4103/0976-8580.99302). The words "Moore", "thermal model" and "field robot" do not occur in it. The Moore paper's venue, authors and DOI remain unverified (`docs/known-issues.md` item 10). |
| desert-av-reliability (GitHub code repository, companion code for an IEEE IV 2027 paper) | None (software repository) | No local copy. The repository is hosted at https://github.com/HemanthMChakravarthy/desert-av-reliability. The owner identifies the author's profile as https://github.com/b-hemanth (Hemanth Bharatha Chakravarthy); that account does not host the repository, and the link between the two accounts was not verified from GitHub. |

## Prior art step for v0.8 (3 November 2026)

Time boxed web pass using the WebSearch and WebFetch tools. IEEE Xplore, Scopus and Web of Science were still not searched. Every
result below was fetched on 2026-11-03 unless marked.

| # | Query (abridged) | Result |
|---|---|---|
| 6 | thermal operating envelope ground robot hot desert uncertainty GO DERATE PARK decision open source | A lunar rover thermal profiling paper (arXiv 2605.27651, title only, not read) and the Moore et al. listing already in this log. No match. |
| 7 | LiDAR dust range degradation robot thermal derating mission planning weather forecast fleet scheduling battery ageing | Dust filtering algorithms for off road LiDAR (PMC9185448, titles only) and UAV fleet planning under weather. No tool combining thermal limits with dust range and fleet scheduling. |
| 8 | Nav2 thermal aware speed limit robot overheating temperature forecast github | Amazon patent US 11,340,617 B1 (below), a Nav2 speed limit zone tutorial, a segbot issue. No Nav2 thermal envelope package. |
| 9 | arXiv 2026 thermal aware mission planning mobile robot high ambient lumped thermal model | arXiv 2610.35231 (below), arXiv 2603.01631 (already logged), a battery thermal management survey. |
| 10 | GitHub fetch of the desert-av-reliability repository | Not fetched: the address is not on this session's allowlist. The earlier entry in this log stands and is unchanged. |

### New nearest works

| Work | What it does (from the fetched abstract or page) | How Dhill differs |
|---|---|---|
| Roy, Zhou, Shah, Garg, Joshi-Apte, Kudryashov and Cheruvanthala, "Thermal-Headroom Routing for Efficient Robot Perception in Extreme Heat", arXiv:2610.35231, submitted 26 October 2026 | A closed form RC model forecasts processor temperature and excludes perception model configurations predicted to throttle; simulated at 45 to 55 degC; the authors report that a tuned thermostat can match it at a fixed operating point and that their hardware measurements do not validate throttling. Code is linked from the arXiv page (not fetched). | Single node processor model, no component limits for battery, LiDAR or motor, no uncertainty quantiles, no dust, no fleet scheduling or battery ageing. Closest recent work on forecast based thermal gating. Cite it. |
| Amazon Technologies, US 11,340,617 B1, "Thermally regulated autonomous motion by autonomous mobile device" (priority 19 July 2019, granted 24 May 2022; status per Google Patents) | Constrains the speed and sensor rates of one indoor mobile device using component temperature thresholds and a temperature map of the space. The claims were not read (the page text was cut off before them). | Indoor single device; no weather forecast, no uncertainty, no fleet scheduling. Relevance to freedom to operate is unassessed; read the claims before any commercial use. |

### Verdict

The gap is only partly closed in the sense that single component thermal gating (arXiv:2610.35231, US 11,340,617 B1) exists. No free tool or
paper found combines forecast driven multicomponent limits with Monte Carlo risk quantiles, dust limited perception, evidence levels and
fleet scheduling with a battery ageing penalty for hot arid ground robots. The stop rule is not met. Positioning in the README is narrowed
to the combination, not to thermal gating alone. This remains a shallow pass; the "To do" list below is unchanged.

## Conclusion so far
No tool combining forecast driven, multicomponent thermal limits, uncertainty aware GO/DERATE/PARK decisions,
dust limited perception and fleet scheduling was found in this shallow pass. Do not claim novelty until the
IEEE Xplore / Scopus / Web of Science queries are run and logged below.

## To do (needs institutional access)
- [ ] Query 1-7 of the protocol on IEEE Xplore
- [ ] Same on Scopus and Web of Science
- [ ] Google Scholar, plus patent search (Google Patents, Patentscope)
- [ ] Add results to the tables above
