"""Validate a profile against a held out telemetry record (the field day check).

The measured loads of the record are replayed through the profile's thermal network, starting from the
first measured temperatures, under the record's weather (ideally an on site station). Each instrumented
node is then compared with the pass criteria of ``docs/validation-protocol.md`` (V2):

* root mean square error under 2 K over the record, and
* the model not colder than the measurement by more than 2 K at the peak.

A Monte Carlo run over the profile's parameter uncertainty (weather error switched off, since the weather
is measured) also reports whether each measured peak lies at or below the predicted 95 % quantile peak.
The record must not have been used for calibration; that is the caller's responsibility and is stated in
the report.
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel

from .calibrate import LOAD_COLS, NODE_COLS, Telemetry
from .physics.constants import c_to_k, k_to_c
from .physics.thermal import Loads, State, simulate
from .profiles.schema import Profile
from .profiles.thermal_adapter import thermal_params
from .weather.base import Weather

RMSE_LIMIT_K = 2.0
COLD_LIMIT_K = 2.0
QUANTILE = 0.95


class NodeResult(BaseModel):
    node: str
    samples: int
    rmse_k: float
    mean_bias_k: float  # predicted minus measured
    measured_peak_c: float
    predicted_peak_c: float
    peak_margin_k: float  # predicted peak minus measured peak; negative means the model runs cold
    q95_peak_c: float
    within_q95: bool
    pass_rmse: bool
    pass_peak: bool

    @property
    def passed(self) -> bool:
        return self.pass_rmse and self.pass_peak


class ValidationReport(BaseModel):
    profile_id: str
    evidence_level: str
    start_utc: str
    end_utc: str
    rows: int
    dt_s: float
    weather_source: str
    rmse_limit_k: float
    cold_limit_k: float
    mc_samples: int
    nodes: list[NodeResult]
    passed: bool
    note: str = ""


def _initial_state(tel: Telemetry, soc: float) -> np.ndarray:
    t0 = np.full(6, np.nan)
    for c, j in NODE_COLS.items():
        if c in tel.temps_c and np.isfinite(tel.temps_c[c][0]):
            t0[j] = c_to_k(tel.temps_c[c][0])
    known = t0[np.isfinite(t0)]
    if known.size == 0:
        raise ValueError("the first telemetry row has no measured temperature")
    fill = t0[1] if np.isfinite(t0[1]) else float(np.mean(known))
    return np.where(np.isfinite(t0), t0, fill)


def replay(
    profile: Profile, weather: Weather, tel: Telemetry, n_mc: int = 1, seed: int = 7
) -> np.ndarray:
    """Node temperatures (degC) for telemetry rows 1..n-1, shape (n_mc, n - 1, 6).

    With ``n_mc`` above 1, parameters are drawn from the profile's provenance spreads; the first sample is
    nominal. Weather error is not sampled because the record's weather is taken as measured.
    """
    if tel.n < 2:
        raise ValueError("telemetry needs at least two rows")
    dt = tel.dt_s
    forcing = weather.to_forcing(dt)
    offset = float((tel.times_utc[0] - weather.times_utc[0]).astype("timedelta64[s]").astype(float))
    if offset < 0 or tel.times_utc[-1] > weather.times_utc[-1]:
        raise ValueError("the weather record does not cover the telemetry period")
    start = int(round(offset / dt))
    if n_mc > 1:
        p = thermal_params(profile, n=n_mc, mc=True, rng=np.random.default_rng(seed))
        p = p.replace_values(d_temp_k=0.0, irr_scale=1.0, wind_scale=1.0)
    else:
        p = thermal_params(profile)
    b = p.n
    steps = tel.n - 1
    t0 = _initial_state(tel, profile.operations.soc_start)
    st = State(np.tile(t0, (b, 1)), np.full(b, profile.operations.soc_start), np.zeros(b))
    ld = Loads(**{k: np.tile(tel.loads[k][:steps][None, :], (b, 1)) for k in LOAD_COLS})
    res = simulate(p, forcing, ld, st, start, steps)
    return k_to_c(res.t_k[:, 1:, :])


def validate(
    profile: Profile,
    weather: Weather,
    tel: Telemetry,
    rmse_limit_k: float = RMSE_LIMIT_K,
    cold_limit_k: float = COLD_LIMIT_K,
    n_mc: int = 64,
    seed: int = 7,
    note: str = "",
) -> ValidationReport:
    nominal = replay(profile, weather, tel)[0]
    mc = replay(profile, weather, tel, n_mc=n_mc, seed=seed) if n_mc > 1 else None
    nodes = []
    for col, j in NODE_COLS.items():
        if col not in tel.temps_c:
            continue
        meas = tel.temps_c[col][1:]
        ok = np.isfinite(meas)
        if ok.sum() < 2:
            continue
        pred = nominal[:, j]
        err = pred[ok] - meas[ok]
        m_peak = float(np.max(meas[ok]))
        p_peak = float(np.max(pred[ok]))
        if mc is not None:
            peaks = np.max(mc[:, ok, j], axis=1)
            q95 = float(np.quantile(peaks, QUANTILE, method="higher"))
        else:
            q95 = p_peak
        rmse = float(np.sqrt(np.mean(err**2)))
        nodes.append(
            NodeResult(
                node=col,
                samples=int(ok.sum()),
                rmse_k=round(rmse, 3),
                mean_bias_k=round(float(np.mean(err)), 3),
                measured_peak_c=round(m_peak, 2),
                predicted_peak_c=round(p_peak, 2),
                peak_margin_k=round(p_peak - m_peak, 2),
                q95_peak_c=round(q95, 2),
                within_q95=bool(m_peak <= q95),
                pass_rmse=bool(rmse < rmse_limit_k),
                pass_peak=bool(p_peak >= m_peak - cold_limit_k),
            )
        )
    if not nodes:
        raise ValueError("no instrumented node has enough measurements")
    return ValidationReport(
        profile_id=profile.id,
        evidence_level=profile.evidence_level,
        start_utc=str(tel.times_utc[0]) + "Z",
        end_utc=str(tel.times_utc[-1]) + "Z",
        rows=tel.n,
        dt_s=tel.dt_s,
        weather_source=weather.source,
        rmse_limit_k=rmse_limit_k,
        cold_limit_k=cold_limit_k,
        mc_samples=n_mc,
        nodes=nodes,
        passed=all(n.passed for n in nodes),
        note=note,
    )


def render_markdown(rep: ValidationReport, telemetry_path: str = "") -> str:
    verdict = "PASS" if rep.passed else "FAIL"
    lines = [
        f"# Validation report: {rep.profile_id} ({verdict})",
        "",
    ]
    if rep.note:
        lines += [f"**{rep.note}**", ""]
    lines += [
        f"- Telemetry: `{telemetry_path}`" if telemetry_path else "- Telemetry: (in memory)",
        f"- Period: {rep.start_utc} to {rep.end_utc}, {rep.rows} rows at {rep.dt_s:g} s",
        f"- Weather source: {rep.weather_source}",
        f"- Profile evidence level at validation: {rep.evidence_level}",
        f"- Criteria (`docs/validation-protocol.md`, V2): RMSE under {rep.rmse_limit_k:g} K on every node, and the "
        f"model not colder than the measurement by more than {rep.cold_limit_k:g} K at the peak",
        f"- Uncertainty: {rep.mc_samples} Monte Carlo samples over parameter provenance, weather taken as measured",
        "- This record must not have been used for calibration.",
        "",
        "| Node | Samples | RMSE (K) | Mean bias (K) | Measured peak (degC) | Predicted peak (degC) "
        "| Peak margin (K) | 95 % quantile peak (degC) | Peak within quantile | RMSE | Peak |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|",
    ]
    ok = {True: "pass", False: "FAIL"}
    for n in rep.nodes:
        lines.append(
            f"| {n.node} | {n.samples} | {n.rmse_k:.2f} | {n.mean_bias_k:+.2f} | {n.measured_peak_c:.1f} | "
            f"{n.predicted_peak_c:.1f} | {n.peak_margin_k:+.1f} | {n.q95_peak_c:.1f} | "
            f"{'yes' if n.within_q95 else 'no'} | {ok[n.pass_rmse]} | {ok[n.pass_peak]} |"
        )
    lines += [
        "",
        f"Overall: **{verdict}**. A FAIL is a result, not an error: report it with the preregistered prediction "
        "(`docs/prediction-template.md`) and do not tune the profile on this record.",
        "",
    ]
    return "\n".join(lines)
