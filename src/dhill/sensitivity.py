"""One-at-a-time sensitivity of mission peak temperatures to each profile parameter.

Each parameter is moved by plus and minus one prior standard deviation (lognormal, from
its provenance) while the others stay nominal. The swing in peak temperature of the
component that binds at the nominal point tells an engineer which measurements would
shrink the decision uncertainty most. Effects are assumed roughly additive, so the
variance shares are an approximation; interactions are not captured.
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel

from .envelope import EngineConfig, Envelope
from .profiles.registry import PARAMS
from .profiles.schema import Profile
from .weather.base import Weather

MEASURED_SIGMA = 0.02


class Sensitivity(BaseModel):
    key: str
    source: str
    sigma: float
    swing_k: float
    share: float
    measured_gain_k: float
    rank: int


class SensitivityReport(BaseModel):
    profile_id: str
    start_utc: str
    mode: str
    scale: float
    binding_component: str
    nominal_peak_c: float
    allowed_c: float
    rows: list[Sensitivity]
    total_sd_k: float


def tornado(
    profile: Profile,
    weather: Weather,
    start_utc: str,
    duration_h: float = 1.0,
    mode: str = "drive",
    scale: float = 1.0,
    shade: float = 0.0,
    cfg: EngineConfig | None = None,
) -> SensitivityReport:
    cfg = cfg or EngineConfig()
    base_cfg = EngineConfig(
        n_mc=1, dt_s=cfg.dt_s, precondition_h=cfg.precondition_h, parked_shade=cfg.parked_shade
    )

    def peaks(prof: Profile):
        env = Envelope(prof, weather, base_cfg)
        idx = env.index_of(start_utc)
        r = env.scan(np.array([idx]), np.array([[scale]]), duration_h, mode, shade)
        return r["risk_peak_c"][0, 0], env

    nom, env0 = peaks(profile)
    allowed = np.array(
        [
            env0.limits[c].limit_c - env0.limits[c].margin_k if c in env0.limits else np.inf
            for c in ["battery", "compute_die", "lidar", "motor", "interior"]
        ]
    )
    comps = ["battery", "compute_die", "lidar", "motor", "interior"]
    j = int(np.argmin(allowed - nom))
    rows = []
    for key, spec in profile.parameters.items():
        sig = spec.sigma
        if sig <= 0:
            continue
        d = PARAMS[key]
        v0 = spec.value
        hi = float(np.clip(v0 * np.exp(sig), d.lo, d.hi))
        lo = float(np.clip(v0 * np.exp(-sig), d.lo, d.hi))
        if hi == lo:
            continue
        ph, _ = peaks(profile.with_overrides({key: hi}, source=spec.source))
        pl, _ = peaks(profile.with_overrides({key: lo}, source=spec.source))
        swing = float(abs(ph[j] - pl[j]) / 2.0)  # half-range, K per one sigma
        rows.append((key, spec.source, sig, swing))
    tot2 = sum(r[3] ** 2 for r in rows) or 1.0
    rows.sort(key=lambda r: -r[3])
    out = [
        Sensitivity(
            key=k,
            source=s,
            sigma=sg,
            swing_k=round(sw, 3),
            share=round(sw**2 / tot2, 4),
            measured_gain_k=round(sw * max(0.0, 1.0 - MEASURED_SIGMA / sg), 3),
            rank=i + 1,
        )
        for i, (k, s, sg, sw) in enumerate(rows)
    ]
    return SensitivityReport(
        profile_id=profile.id,
        start_utc=start_utc,
        mode=mode,
        scale=scale,
        binding_component=comps[j],
        nominal_peak_c=round(float(nom[j]), 2),
        allowed_c=float(allowed[j]),
        rows=out,
        total_sd_k=round(float(np.sqrt(tot2)), 3),
    )
