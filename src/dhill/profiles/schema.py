"""Robot profile model with parameter provenance and evidence level."""

from __future__ import annotations

from collections import Counter
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from .registry import COMPONENTS, PARAMS, SOURCE_SIGMA, Source

EvidenceLevel = Literal["L0", "L1", "L2", "L3"]

EVIDENCE_TEXT = {
    "L0": "L0: uncalibrated defaults (textbook values and assumptions)",
    "L1": "L1: parameterised from datasheets and measurements of this robot",
    "L2": "L2: calibrated on field telemetry from this robot",
    "L3": "L3: validated on a held-out field campaign",
}


class ParamSpec(BaseModel):
    """A numeric parameter with its provenance."""

    value: float
    source: Source = "assumption"
    note: str | None = None
    rel_sigma: float | None = Field(default=None, ge=0.0, le=2.0)

    @property
    def sigma(self) -> float:
        return self.rel_sigma if self.rel_sigma is not None else SOURCE_SIGMA[self.source]


class Limit(BaseModel):
    """Temperature limit for a component.

    ``limit_c`` is the hard limit; a mission is acceptable only if the
    risk-quantile peak stays below ``limit_c - margin_k``.
    """

    limit_c: float
    margin_k: float = Field(ge=0.0)
    source: Source = "assumption"
    note: str | None = None


class Mode(BaseModel):
    """Mean drivetrain and payload power for an operating mode, at full scale."""

    mech_w: float = Field(ge=0.0)
    payload_w: float = Field(default=0.0, ge=0.0)


class Operations(BaseModel):
    soc_reserve: float = Field(default=0.15, ge=0.0, lt=1.0)
    soc_start: float = Field(default=0.95, gt=0.0, le=1.0)
    min_scale: float = Field(default=0.3, gt=0.0, le=1.0)
    risk_quantile: float = Field(default=0.95, gt=0.5, lt=1.0)


class Profile(BaseModel):
    schema_version: int = 1
    id: str
    name: str
    description: str = ""
    category: str = "generic"
    evidence_level: EvidenceLevel = "L0"
    calibrated_from: list[str] = Field(default_factory=list)
    parameters: dict[str, ParamSpec]
    limits: dict[str, Limit]
    modes: dict[str, Mode]
    operations: Operations = Field(default_factory=Operations)

    @field_validator("id")
    @classmethod
    def _id_ok(cls, v: str) -> str:
        if not v or not all(c.isalnum() or c in "-_" for c in v):
            raise ValueError("id must be alphanumeric with - or _")
        return v

    @model_validator(mode="after")
    def _check(self) -> Profile:
        unknown = set(self.parameters) - set(PARAMS)
        if unknown:
            raise ValueError(f"unknown parameters: {sorted(unknown)}")
        for key, spec in PARAMS.items():
            if key not in self.parameters:
                if not spec.optional:
                    raise ValueError(f"missing required parameter: {key}")
                continue
            val = self.parameters[key].value
            if not (spec.lo <= val <= spec.hi) and not (spec.optional and val == spec.default):
                raise ValueError(f"{key}={val} outside [{spec.lo}, {spec.hi}] {spec.unit}")
        for comp in ("battery", "compute_die", "lidar", "motor"):
            if comp not in self.limits:
                raise ValueError(f"missing limit for component: {comp}")
        extra = set(self.limits) - set(COMPONENTS)
        if extra:
            raise ValueError(f"unknown limit components: {sorted(extra)}")
        for need in ("drive", "idle"):
            if need not in self.modes:
                raise ValueError(f"missing mode: {need}")
        if self.evidence_level in ("L2", "L3") and not self.calibrated_from:
            raise ValueError("evidence level L2/L3 requires calibrated_from")
        return self

    def value(self, key: str) -> float:
        """Parameter value, falling back to the registry default if optional."""
        if key in self.parameters:
            return self.parameters[key].value
        default = PARAMS[key].default
        if default is None:
            raise KeyError(key)
        return default

    def sigma(self, key: str) -> float:
        if key in self.parameters:
            return self.parameters[key].sigma
        return SOURCE_SIGMA["assumption"]

    def source_counts(self) -> dict[str, int]:
        counts = Counter(p.source for p in self.parameters.values())
        return dict(counts)

    def assumption_fraction(self) -> float:
        """Share of declared parameters that are assumptions rather than data."""
        n = len(self.parameters)
        return self.source_counts().get("assumption", 0) / n if n else 1.0

    def evidence_text(self) -> str:
        return EVIDENCE_TEXT[self.evidence_level]

    def with_overrides(self, overrides: dict[str, float], source: Source = "calibrated") -> Profile:
        """Return a copy with parameter values replaced (used by calibration)."""
        params = {k: v.model_copy() for k, v in self.parameters.items()}
        for key, val in overrides.items():
            if key not in PARAMS:
                raise KeyError(key)
            base = params.get(key)
            params[key] = ParamSpec(
                value=float(val),
                source=source,
                note=(base.note if base else None),
            )
        return self.model_copy(update={"parameters": params})
