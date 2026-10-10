"""Result models shared by the engine, CLI and API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Action = Literal["GO", "DERATE", "PARK"]


class ComponentMargin(BaseModel):
    component: str
    limit_c: float
    margin_k: float = Field(description="Safety margin that must remain below the hard limit")
    risk_peak_c: float = Field(description="Risk-quantile peak temperature over the mission")
    headroom_k: float = Field(description="limit - margin - risk peak; negative means violated")


class Perception(BaseModel):
    pm10_window_max_ugm3: float
    lidar_range_m: float
    max_safe_speed_ms: float
    speed_fraction_cap: float


class Decision(BaseModel):
    action: Action
    start_utc: str
    duration_h: float
    mode: str
    scale: float = Field(description="Operating scale 0..1: speed, drive power and compute duty")
    speed_ms: float
    throughput_fraction: float
    limiting_component: str
    components: list[ComponentMargin]
    risk_min_soc: float
    soc_reserve: float
    perception: Perception
    perception_limited: bool = False
    shade_required_fraction: float | None = Field(
        default=None,
        description="Share of the mission in shade needed for full-scale operation, if not GO",
    )
    next_full_scale_start_utc: str | None = None
    next_operable_start_utc: str | None = None
    reasons: list[str] = Field(default_factory=list)
    evidence_level: str
    evidence_text: str
    assumption_fraction: float
    risk_quantile: float
    mc_samples: int
    caveat: str


class Slot(BaseModel):
    start_utc: str
    action: Action
    scale: float
    limiting_component: str
    headroom_k: float
    risk_min_soc: float
    perception_limited: bool = False


class Timeline(BaseModel):
    profile_id: str
    site: str
    weather_source: str
    mode: str
    duration_h: float
    step_min: float
    evidence_level: str
    slots: list[Slot]

    @property
    def productive_hours(self) -> float:
        return sum(s.scale for s in self.slots) * self.step_min / 60.0
