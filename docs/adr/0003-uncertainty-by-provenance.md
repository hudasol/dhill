# ADR 0003: Uncertainty set by provenance

**Status:** accepted. **Decision:** each parameter's Monte Carlo spread follows its source tag (2% measured to 25% assumption), overridable per parameter. Decisions use a risk quantile of the peak. **Consequences:** an uncalibrated robot is treated conservatively and the cost of not knowing is visible; calibration shrinks spread only for identified parameters. The spreads are priors and must be revisited against field data.
