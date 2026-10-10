"""FastAPI service exposing the envelope engine, planner and calibration summary.

Security posture: no file paths are accepted (built-in profile ids or inline
profile objects only), inputs are bounded, an optional API key (``DHILL_API_KEY``)
protects ``/v1`` routes and an optional JSONL audit log (``DHILL_AUDIT_LOG``)
records every decision request. See docs/threat-model.md.
"""

from __future__ import annotations

import hmac
import json
import os
import time
from importlib import resources
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .. import __version__
from ..envelope import EngineConfig, Envelope
from ..models import Decision, Timeline
from ..planner import Comparison, PlannerSpec, compare
from ..profiles.loader import builtin_profile_ids, load_builtin, profile_from_dict
from ..profiles.schema import Profile
from ..sites import SITES
from ..weather import SCENARIOS, WeatherUnavailable, fetch_weather, synthetic_weather
from ..weather.base import Weather

app = FastAPI(
    title="Dhill",
    version=__version__,
    description="Heat and dust operating-envelope intelligence for outdoor robots",
)


def require_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = os.environ.get("DHILL_API_KEY")
    if expected and not (x_api_key and hmac.compare_digest(x_api_key, expected)):
        raise HTTPException(status_code=401, detail="missing or invalid API key")


def audit(event: str, payload: dict[str, Any]) -> None:
    path = os.environ.get("DHILL_AUDIT_LOG")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"t": time.time(), "event": event, **payload}) + "\n")


class Scenario(BaseModel):
    profile: str = "ugv_medium_inspection"
    profile_inline: dict[str, Any] | None = Field(
        default=None, description="Inline profile (YAML structure) instead of a built-in id"
    )
    site: str = "abu_dhabi"
    source: str = Field(default="synthetic", pattern="^(synthetic|live)$")
    scenario: str = "summer_clear"
    start: str | None = Field(default=None, description="UTC start of synthetic weather")
    days: int = Field(default=2, ge=1, le=5)
    mode: str = "drive"
    duration_h: float = Field(default=1.0, gt=0.1, le=8.0)
    samples: int = Field(default=48, ge=8, le=256)


class DecideRequest(Scenario):
    at: str | None = None


class TimelineRequest(Scenario):
    step_min: float = Field(default=60.0, ge=15.0, le=240.0)


class PlanRequest(Scenario):
    robots: list[str] = Field(default_factory=list, max_length=8)
    step_min: float = Field(default=30.0, ge=15.0, le=120.0)
    rest_h: float = Field(default=0.5, ge=0.0, le=4.0)
    max_concurrent: int | None = Field(default=None, ge=1, le=8)
    demand_h: float = Field(default=12.0, gt=0.0, le=200.0)
    utc_offset_h: float = 4.0


def _profile(req: Scenario, override: str | None = None) -> Profile:
    try:
        if req.profile_inline is not None and override is None:
            return profile_from_dict(req.profile_inline)
        return load_builtin(override or req.profile)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, f"invalid profile: {exc}") from exc


def _weather(req: Scenario) -> Weather:
    if req.site not in SITES:
        raise HTTPException(404, f"unknown site; available: {sorted(SITES)}")
    if req.source == "live":
        try:
            return fetch_weather(req.site, forecast_days=req.days)
        except WeatherUnavailable as exc:
            raise HTTPException(502, f"live weather unavailable: {exc}") from exc
    if req.scenario not in SCENARIOS:
        raise HTTPException(404, f"unknown scenario; available: {sorted(SCENARIOS)}")
    return synthetic_weather(
        req.site, req.scenario, start=req.start or "2026-08-05T00:00", days=req.days
    )


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/version", dependencies=[Depends(require_key)])
def version() -> dict[str, str]:
    return {"name": "dhill", "version": __version__}


@app.get("/v1/profiles", dependencies=[Depends(require_key)])
def profiles() -> list[dict[str, Any]]:
    out = []
    for pid in builtin_profile_ids():
        p = load_builtin(pid)
        out.append(
            {
                "id": p.id,
                "name": p.name,
                "category": p.category,
                "evidence_level": p.evidence_level,
                "modes": sorted(p.modes),
                "assumption_fraction": round(p.assumption_fraction(), 3),
            }
        )
    return out


@app.get("/v1/sites", dependencies=[Depends(require_key)])
def sites() -> list[dict[str, Any]]:
    return [s.__dict__ for s in SITES.values()]


@app.get("/v1/scenarios", dependencies=[Depends(require_key)])
def scenarios() -> dict[str, str]:
    return SCENARIOS


@app.post("/v1/envelope", response_model=Decision, dependencies=[Depends(require_key)])
def envelope(req: DecideRequest) -> Decision:
    try:
        env = Envelope(_profile(req), _weather(req), EngineConfig(n_mc=req.samples), site=req.site)
        d = env.decide(req.at, req.duration_h, req.mode)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    audit(
        "envelope",
        {
            "profile": env.profile.id,
            "site": req.site,
            "action": d.action,
            "scale": d.scale,
            "start": d.start_utc,
            "evidence": d.evidence_level,
        },
    )
    return d


@app.post("/v1/forecast", response_model=Timeline, dependencies=[Depends(require_key)])
def forecast(req: TimelineRequest) -> Timeline:
    try:
        env = Envelope(_profile(req), _weather(req), EngineConfig(n_mc=req.samples), site=req.site)
        tl = env.timeline(req.duration_h, req.mode, req.step_min)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    audit("forecast", {"profile": env.profile.id, "site": req.site, "slots": len(tl.slots)})
    return tl


@app.post("/v1/schedule", response_model=Comparison, dependencies=[Depends(require_key)])
def schedule(req: PlanRequest) -> Comparison:
    ids = req.robots or [req.profile]
    w = _weather(req)
    tls = {}
    try:
        for rid in ids:
            env = Envelope(
                _profile(req, override=rid), w, EngineConfig(n_mc=req.samples), site=req.site
            )
            tls[rid] = env.timeline(req.duration_h, req.mode, req.step_min)
        res = compare(
            tls,
            PlannerSpec(
                block_h=req.duration_h,
                rest_h=req.rest_h,
                max_concurrent=req.max_concurrent,
                demand_work_h=req.demand_h,
            ),
            local_offset_h=req.utc_offset_h,
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    audit("schedule", {"robots": ids, "site": req.site, "completed_h": res.dhill.completed_work_h})
    return res


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    return resources.files("dhill.web").joinpath("index.html").read_text(encoding="utf-8")
