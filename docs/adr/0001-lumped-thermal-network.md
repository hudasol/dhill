# ADR 0001: Lumped six-node thermal network

**Status:** accepted. **Context:** operators need fast, explainable answers with uncertainty, not a CFD model. **Decision:** six nodes (shell, interior, battery, compute, LiDAR, motor) with analytical convection and radiation, solved with backward Euler in batch. **Consequences:** a full uncertainty-aware day in seconds; parameters are few enough to calibrate from telemetry; spatial effects are out of scope and listed in the model card.
