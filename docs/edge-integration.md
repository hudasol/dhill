# Integration path for EDGE and subsidiaries

Written as an engineering proposal, not a claim of relationship. EDGE entities are named only to describe where such a tool could fit.

## Where it fits
Units that operate or integrate unmanned ground and aerial platforms need a documented answer to "what can this platform do at 50 degC with dust". Dhill produces that answer per platform, site and mission, with stated uncertainty.

## What a pilot needs
1. One platform with a thermal design description (heat capacities, conductances, limits) or willingness to instrument it.
2. Telemetry: temperatures of shell, interior, battery, compute and sensors, plus power channels, at 1 to 5 minute intervals.
3. A site weather source: own station preferred, forecast feed acceptable.
4. A host engineer to agree the V2 and V3 protocols in `validation-protocol.md`.

## Deployment
Self hosted container (non root, read only filesystem, no outbound calls required), REST/JSON and Python library, CSV telemetry, optional API key and audit log. SBOM and dependency audit generated in CI. See `threat-model.md`.

## Not claimed
- Compliance with MIL-STD-810H, IEC 60529, IEC 62133-2, ISO 13482 or ISO 3691-4. The method is informed by their environmental test thinking and is not a substitute for testing to them.
- Any result on a real EDGE platform.
- Relevance to the EDGE ATP 2026 ChallengeOn track, which is about seamless connectivity across networks, not heat and dust. The route to EDGE is a technical conversation or pilot, not that challenge.
