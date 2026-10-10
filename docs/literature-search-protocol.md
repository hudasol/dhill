# Literature and novelty search protocol

Purpose: before claiming novelty or choosing a licence/venue, show what already exists. Record every query, date,
database and hit count in a log; keep the log in the repo (`docs/literature-log.md`). Nothing here has been run yet.

## Databases
IEEE Xplore, Scopus, Web of Science, Google Scholar, arXiv, plus patent search (Google Patents, WIPO Patentscope).

## Query strings (adapt syntax per database)
1. ("thermal" OR "heat") AND ("operating envelope" OR "derating" OR "thermal management") AND ("unmanned ground vehicle" OR UGV OR "mobile robot") AND (desert OR "hot climate" OR "high ambient")
2. ("lumped" OR "RC network" OR "thermal network") AND (robot OR UGV) AND (battery OR electronics) AND "Monte Carlo"
3. ("mission planning" OR scheduling) AND (thermal OR heat) AND ("battery ageing" OR "battery aging") AND robot
4. (dust OR "particulate" OR soiling) AND ("LiDAR" OR lidar) AND ("range degradation" OR visibility) AND robot
5. ("forecast" OR "weather-aware" OR "weather-based") AND ("autonomous" OR robot) AND (heat OR temperature) AND (go OR "no-go" OR derate)
6. "thermal-aware" AND (robot OR drone OR UAV) AND planning
7. Gulf / UAE specific: ("UAE" OR "Gulf" OR "Saudi" OR "Abu Dhabi") AND (robot OR "autonomous vehicle") AND (heat OR temperature OR dust)

## Screening
Two-stage (title/abstract, then full text). Record inclusion/exclusion reasons. Note the nearest 5 prior works and
state in one sentence each what Dhill does differently. If a near-duplicate exists, say so in the README.

## Output
`docs/literature-log.md` (queries, dates, counts, nearest works) and a short "related work" section in the model card.
