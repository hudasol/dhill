"""Operating policies and a scorer against a hidden 'true' robot.

Policies map each hourly mission slot to an operating scale. The scorer simulates the
true robot over many weather realisations (forecast error drawn heavier than the engine
assumes) and counts hard-limit violations and productive hours. It exists to answer one
question honestly: does the envelope beat the rules operators use today?
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .envelope import EngineConfig, Envelope
from .physics.constants import k_to_c
from .physics.thermal import ThermalParams, lhs_normal
from .profiles.schema import Profile
from .weather.base import Weather

Policy = dict[str, np.ndarray]  # name -> scale per slot


@dataclass
class Score:
    name: str
    productive_h: float
    operated_slots: int
    violation_prob_mean: float
    risky_hours: int  # operated slots whose violation probability exceeds 5%
    expected_violation_h: float


def slot_starts(env: Envelope, first_utc: str, last_utc: str, step_min: float = 60.0) -> np.ndarray:
    stride = int(round(step_min * 60.0 / env.cfg.dt_s))
    return np.arange(env._idx(first_utc), env._idx(last_utc) + 1, stride)


def ambient_threshold(
    env: Envelope, starts: np.ndarray, duration_h: float, limit_c: float
) -> np.ndarray:
    n = env._steps(duration_h)
    air = k_to_c(env.forcing.t_air_k)
    return np.array([1.0 if air[s : s + n + 1].max() <= limit_c else 0.0 for s in starts])


def midday_ban(
    env: Envelope, starts: np.ndarray, start_h: float = 12.5, end_h: float = 15.0
) -> np.ndarray:
    hour = env.forcing.solar_hour
    return np.array([0.0 if start_h <= hour[s] < end_h else 1.0 for s in starts])


def envelope_policy(
    profile: Profile,
    weather: Weather,
    starts: np.ndarray,
    duration_h: float,
    mode: str,
    cfg: EngineConfig,
) -> np.ndarray:
    env = Envelope(profile, weather, cfg)
    scales, _ = env.best_scale(starts, duration_h, mode)
    return scales


def score_policies(
    truth: Profile,
    weather: Weather,
    starts: np.ndarray,
    policies: Policy,
    duration_h: float,
    mode: str,
    worlds: int = 200,
    sigma_t: float = 2.0,
    sigma_irr: float = 0.15,
    sigma_wind: float = 0.30,
    seed: int = 123,
) -> list[Score]:
    """Score each policy on the hidden robot across weather realisations."""
    cfg = EngineConfig(n_mc=worlds, precondition_h=1.5)
    env = Envelope(truth, weather, cfg)
    rng = np.random.default_rng(seed)
    p0 = ThermalParams.from_profile(truth, n=worlds)  # true parameters, no parameter uncertainty
    env.params = p0.replace_values(
        d_temp_k=sigma_t * lhs_normal(rng, worlds),
        irr_scale=np.exp(sigma_irr * lhs_normal(rng, worlds)),
        wind_scale=np.exp(sigma_wind * lhs_normal(rng, worlds)),
    )
    hard = np.array(
        [truth.limits[c].limit_c for c in ["battery", "compute_die", "lidar", "motor", "interior"]]
    )
    out = []
    for name, scales in policies.items():
        operate = scales > 0
        viol_p = np.zeros(len(starts))
        if operate.any():
            idx = np.where(operate)[0]
            r = env.scan(starts[idx], scales[idx][:, None], duration_h, mode)
            exceed = np.any(r["peaks_c"][:, 0, :, :] > hard[None, None, :], axis=2)  # (S, worlds)
            viol_p[idx] = exceed.mean(axis=1)
        n_op = int(operate.sum())
        out.append(
            Score(
                name=name,
                productive_h=float(np.sum(scales) * duration_h),
                operated_slots=n_op,
                violation_prob_mean=float(viol_p[operate].mean()) if n_op else 0.0,
                risky_hours=int(np.sum(viol_p[operate] > 0.05)),
                expected_violation_h=float(np.sum(viol_p) * duration_h),
            )
        )
    return out
