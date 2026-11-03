"""Fleet description file: which robots, where, and how they share the work.

A fleet file is YAML (or JSON) validated against ``FleetSpec``. The JSON schema generated from the model is
committed as ``docs/fleet.schema.json`` so editors can validate a file before it reaches Dhill.

.. code-block:: yaml

    schema_version: 1
    name: Campus inspection pilot (illustrative)
    site: al_ain
    robots:
      - id: inspector
        profile: ugv_medium_inspection
        count: 2
      - id: courier
        profile: sidewalk_delivery_robot
    planner:
      block_h: 1.0
      demand_work_h: 12.0
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from .profiles.loader import load_profile
from .profiles.schema import Profile
from .sites import site_ids


class FleetRobot(BaseModel):
    id: str = Field(description="Name of the robot, or the prefix of its numbered copies")
    profile: str = Field(description="Built in profile id or path to a profile YAML file")
    count: int = Field(default=1, ge=1, le=500, description="Number of identical robots")
    mode: str = Field(default="drive", description="Mission mode used for planning")

    @field_validator("id")
    @classmethod
    def _id_ok(cls, v: str) -> str:
        if not v or not all(c.isalnum() or c in "-_" for c in v):
            raise ValueError("robot id must be alphanumeric with - or _")
        return v


class FleetPlanner(BaseModel):
    block_h: float = Field(default=1.0, gt=0, le=8)
    rest_h: float = Field(default=0.5, ge=0, le=12)
    max_concurrent: int | None = Field(default=None, ge=1)
    demand_work_h: float = Field(default=12.0, gt=0, le=1000)
    utc_offset_h: float = Field(default=4.0, ge=-12, le=14)
    step_min: float = Field(default=30.0, ge=5, le=240)


class FleetSpec(BaseModel):
    schema_version: int = 1
    name: str
    site: str
    robots: list[FleetRobot] = Field(min_length=1)
    planner: FleetPlanner = Field(default_factory=FleetPlanner)

    @field_validator("site")
    @classmethod
    def _site_ok(cls, v: str) -> str:
        if v not in site_ids():
            raise ValueError(f"unknown site '{v}'; choose one of {', '.join(site_ids())}")
        return v

    @model_validator(mode="after")
    def _unique(self) -> FleetSpec:
        names = [r.id for r in self.robots]
        if len(set(names)) != len(names):
            raise ValueError("robot ids must be unique")
        return self

    def expand(self) -> list[tuple[str, FleetRobot]]:
        """One entry per physical robot: ``id`` for a single robot, ``id-01``, ``id-02`` for copies."""
        out = []
        for r in self.robots:
            if r.count == 1:
                out.append((r.id, r))
            else:
                width = max(2, len(str(r.count)))
                out += [(f"{r.id}-{i + 1:0{width}d}", r) for i in range(r.count)]
        return out

    def profiles(self) -> dict[str, Profile]:
        """Load every distinct profile once; raises ``ValueError`` naming the profile that fails."""
        loaded: dict[str, Profile] = {}
        for r in self.robots:
            if r.profile not in loaded:
                try:
                    loaded[r.profile] = load_profile(r.profile)
                except Exception as exc:
                    raise ValueError(f"profile '{r.profile}': {exc}") from exc
            if r.mode not in loaded[r.profile].modes:
                raise ValueError(f"profile '{r.profile}' has no mode '{r.mode}'")
        return loaded


def load_fleet(path: str | Path) -> FleetSpec:
    text = Path(path).read_text(encoding="utf-8")
    data = json.loads(text) if str(path).endswith(".json") else yaml.safe_load(text)
    return FleetSpec.model_validate(data)


def fleet_json_schema() -> dict:
    return FleetSpec.model_json_schema()
