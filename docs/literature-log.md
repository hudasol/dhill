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

## Conclusion so far
No tool combining forecast driven, multicomponent thermal limits, uncertainty aware GO/DERATE/PARK decisions,
dust limited perception and fleet scheduling was found in this shallow pass. Do not claim novelty until the
IEEE Xplore / Scopus / Web of Science queries are run and logged below.

## To do (needs institutional access)
- [ ] Query 1-7 of the protocol on IEEE Xplore
- [ ] Same on Scopus and Web of Science
- [ ] Google Scholar, plus patent search (Google Patents, Patentscope)
- [ ] Add results to the tables above
