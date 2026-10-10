# Concept of operations

**Planner (daily).** Before a shift, the operations planner loads the site forecast and the robots' profiles, runs the timeline, and receives per-robot windows (GO, DERATE with scale, PARK) with the binding constraint named. The fleet scheduler assigns work blocks inside those windows.

**Supervisor (live).** During operation the supervisor re-runs the decision for the next block as forecasts update, sees the evidence level and headroom, and can request shade requirements (for example whether a route segment under a canopy makes a window feasible).

**Maintainer (monthly).** Telemetry from the recorder is calibrated; the new profile replaces the old only if hold-out error improves. Parameters that are not identified keep their prior spread.

**Interfaces.** Library, CLI, REST API (self-hosted container) and a dashboard. Weather from Open-Meteo, a CSV feed or the customer's own station.

**Human factors.** Every output states its evidence level, the share of assumption parameters and the binding constraint, so an operator can judge whether to trust it. The system advises; the operator and the robot's hardware protections decide.
