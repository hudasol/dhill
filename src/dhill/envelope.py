"""Operating-envelope engine: GO / DERATE / PARK decisions with quantified risk.

For a robot profile, a weather forecast and a planned mission window the engine
answers three questions:

1. Can the mission run at full scale without any component exceeding its limit
   (less margin) at the chosen risk quantile?
2. If not, what is the largest operating scale that is safe?
3. If not even the minimum scale is safe, when is the next window, and how much
   shade would make the mission feasible?

Parameter and forecast uncertainty are propagated by Monte Carlo, with spreads
set by each parameter's provenance. Every decision carries the profile's
evidence level so a reader can see how far to trust it.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import loads as loadlib
from .models import ComponentMargin, Decision, Perception, Slot, Timeline
from .physics import dust
from .physics.constants import k_to_c
from .physics.thermal import (
    State,
    ThermalParams,
    lhs_normal,
    simulate,
)
from .profiles.registry import COMPONENTS
from .profiles.schema import Profile
from .weather.base import Weather

# index of each component's node in the thermal network (compute uses the die)
_NODE = {"battery": 2, "lidar": 4, "motor": 5, "interior": 1}

L0_CAVEAT = (
    "Illustrative parameters (evidence level L0). This output demonstrates the method; "
    "it is not an authorisation to operate. Calibrate on telemetry before relying on it."
)


@dataclass
class EngineConfig:
    n_mc: int = 64
    dt_s: float = 600.0
    precondition_h: float = 1.5
    parked_shade: float = 0.0
    seed: int = 7
    coarse_points: int = 8
    refine_rounds: int = 2
    refine_points: int = 5
    pm10_sigma: float = 0.5
    sigma_scale: float = 1.0


class Envelope:
    """Decision engine bound to one profile, one forecast and one configuration."""

    def __init__(
        self, profile: Profile, weather: Weather, config: EngineConfig | None = None, site: str = ""
    ):
        self.profile = profile
        self.weather = weather
        self.cfg = config or EngineConfig()
        self.site = site or weather.label
        self.forcing = weather.to_forcing(self.cfg.dt_s)
        rng = np.random.default_rng(self.cfg.seed)
        self.params = ThermalParams.from_profile(
            profile, n=self.cfg.n_mc, mc=True, rng=rng, sigma_scale=self.cfg.sigma_scale
        )
        self.q = profile.operations.risk_quantile
        self.limits = {c: profile.limits[c] for c in COMPONENTS if c in profile.limits}
        self._build_perception_samples(rng)

    # ------------------------------------------------------------------ helpers
    def _build_perception_samples(self, rng: np.random.Generator) -> None:
        pr = self.profile
        m = self.cfg.n_mc

        def draw(key: str) -> np.ndarray:
            base = pr.value(key)
            sig = pr.sigma(key) * self.cfg.sigma_scale
            out = base * np.exp(sig * lhs_normal(rng, m)) if sig > 0 else np.full(m, base)
            out[0] = base
            return out

        self.range_clear = draw("lidar.range_clear_m")
        self.mass_ext = draw("environment.mass_ext_eff_m2_g")
        pm = np.exp(self.cfg.pm10_sigma * lhs_normal(rng, m))
        pm[0] = 1.0
        self.pm_scale = pm

    def _idx(self, when) -> int:
        return self.weather.index_of(when, self.cfg.dt_s)

    def _time_at(self, idx: int) -> np.datetime64:
        return self.weather.times_utc[0] + np.timedelta64(int(round(idx * self.cfg.dt_s)), "s")

    def _fmt(self, idx: int) -> str:
        return str(self._time_at(idx).astype("datetime64[s]")) + "Z"

    def _steps(self, hours: float) -> int:
        return max(1, int(round(hours * 3600.0 / self.cfg.dt_s)))

    # ------------------------------------------------------------------ perception
    def perception_cap(self, starts: np.ndarray, duration_h: float):
        """Speed-fraction cap, lidar range and window PM10 for each start index.

        Returns arrays of shape (S,): cap (conservative quantile), range, pm10 max.
        """
        n = self._steps(duration_h)
        pm_all = self.forcing.pm10
        out_cap, out_rng, out_pm = [], [], []
        nominal = self.profile.value("perception.nominal_speed_ms")
        for s in starts:
            lo, hi = int(s), min(int(s) + n, pm_all.size - 1)
            pm_max = float(np.max(pm_all[lo : hi + 1]))
            sigma = self.mass_ext * pm_max * self.pm_scale * 1e-6
            rng_eff = np.asarray(dust.lidar_range_m(self.range_clear, sigma), dtype=float)
            v = dust.max_safe_speed_ms(
                rng_eff,
                self.profile.value("perception.decel_ms2"),
                self.profile.value("perception.reaction_s"),
                self.profile.value("perception.margin_m"),
            )
            frac = np.minimum(v / nominal, 1.0)
            out_cap.append(float(np.quantile(frac, 1.0 - self.q)))
            out_rng.append(float(np.quantile(rng_eff, 1.0 - self.q)))
            out_pm.append(pm_max)
        return np.array(out_cap), np.array(out_rng), np.array(out_pm)

    # ------------------------------------------------------------------ core scan
    def _soak_state(self, starts: np.ndarray) -> tuple[State, int]:
        """State after a parked soak before each start, per (start, mc) pair."""
        s_n, m = starts.size, self.cfg.n_mc
        n_pre = self._steps(self.cfg.precondition_h) if self.cfg.precondition_h > 0 else 0
        pre_idx = np.maximum(starts - n_pre, 0)
        tp = self.params.tile(s_n)
        idx_b = np.repeat(pre_idx, m)
        t_air0 = self.forcing.t_air_k[idx_b] + tp.d_temp_k
        t0 = np.repeat(t_air0[:, None], 6, axis=1)
        soc0 = np.full(s_n * m, self.profile.operations.soc_start)
        st = State(t0, soc0, np.zeros(s_n * m))
        if n_pre > 0:
            lo = loadlib.parked_loads(self.profile, s_n * m)
            res = simulate(
                tp,
                self.forcing,
                lo,
                st,
                idx_b,
                n_pre,
                shade=self.cfg.parked_shade,
                record_every=n_pre,
            )
            st = res.end
            # the soak is parked: do not carry its tiny discharge into mission SoC
            st.soc = soc0.copy()
        return st, n_pre

    def scan(
        self, starts, scales, duration_h: float, mode: str, shade=0.0
    ) -> dict[str, np.ndarray]:
        """Evaluate missions for every (start, scale) pair, Monte Carlo included.

        ``scales`` and ``shade`` broadcast against ``(S, K)``. Returns arrays:
        ``headroom`` (S, K, 5) per-component headroom in kelvin at the risk
        quantile, ``risk_peak_c`` (S, K, 5), ``risk_min_soc`` (S, K).
        """
        starts = np.atleast_1d(np.asarray(starts, dtype=int))
        s_n = starts.size
        scales = np.asarray(scales, dtype=float)
        if scales.ndim == 1:
            scales = np.broadcast_to(scales, (s_n, scales.size))
        k_n = scales.shape[1]
        m = self.cfg.n_mc
        shade_a = np.broadcast_to(np.asarray(shade, dtype=float), (s_n, k_n))

        soak, _ = self._soak_state(starts)
        # expand soak (S*M) -> (S*K*M) with layout ((s*K)+k)*M + m
        sel = (
            np.arange(s_n)[:, None, None] * m
            + np.zeros((1, k_n, 1), int)
            + np.arange(m)[None, None, :]
        ).reshape(-1)
        st = State(soak.t_k[sel], soak.soc[sel], soak.dust[sel])
        tp = self.params.tile(s_n * k_n)
        scale_b = np.repeat(scales.reshape(-1), m)
        shade_b = np.repeat(shade_a.reshape(-1), m)
        start_b = np.repeat(starts, k_n * m)
        loads = loadlib.mission_loads(self.profile, scale_b, mode)
        res = simulate(
            tp,
            self.forcing,
            loads,
            st,
            start_b,
            self._steps(duration_h),
            shade=shade_b,
            record_every=10**6,
        )

        comps = list(COMPONENTS)
        peaks = np.zeros((s_n * k_n * m, len(comps)))
        for j, c in enumerate(comps):
            peaks[:, j] = res.peak_die_k if c == "compute_die" else res.peak_k[:, _NODE[c]]
        peaks_c = k_to_c(peaks).reshape(s_n, k_n, m, len(comps))
        risk_peak = np.quantile(peaks_c, self.q, axis=2, method="higher")
        allow = np.array(
            [
                self.limits[c].limit_c - self.limits[c].margin_k if c in self.limits else np.inf
                for c in comps
            ]
        )
        headroom = allow[None, None, :] - risk_peak
        soc = res.min_soc.reshape(s_n, k_n, m)
        risk_soc = np.quantile(soc, 1.0 - self.q, axis=2, method="lower")
        return {
            "headroom": headroom,
            "risk_peak_c": risk_peak,
            "risk_min_soc": risk_soc,
            "comps": comps,
        }

    def _feasible(self, scan: dict, scales: np.ndarray, caps: np.ndarray) -> np.ndarray:
        thermal_ok = np.min(scan["headroom"], axis=2) >= 0.0
        soc_ok = scan["risk_min_soc"] >= self.profile.operations.soc_reserve
        perc_ok = scales <= caps[:, None] + 1e-9
        return thermal_ok & soc_ok & perc_ok

    # ------------------------------------------------------------------ best scale
    def best_scale(self, starts, duration_h: float, mode: str, shade=0.0):
        """Largest verified-feasible scale for each start (0 if none).

        Grid first, then repeated refinement between the largest feasible grid
        point and the next infeasible one. Feasibility is monotone in scale for
        this model (power and thus heat rise with scale), which the tests check.
        """
        starts = np.atleast_1d(np.asarray(starts, dtype=int))
        min_s = self.profile.operations.min_scale
        caps, _, _ = self.perception_cap(starts, duration_h)
        # cap the scan range by perception so the grid is meaningful
        grid = np.linspace(min_s, 1.0, self.cfg.coarse_points)
        scales = np.broadcast_to(grid, (starts.size, grid.size))
        scan = self.scan(starts, scales, duration_h, mode, shade)
        feas = self._feasible(scan, scales, caps)
        best = np.zeros(starts.size)
        lo = np.zeros(starts.size)
        hi = np.zeros(starts.size)
        for i in range(starts.size):
            ok = np.where(feas[i])[0]
            if ok.size == 0:
                # perception may allow only a sub-grid scale: try the cap itself
                lo[i], hi[i] = 0.0, min_s
                continue
            j = ok.max()
            lo[i] = grid[j]
            hi[i] = grid[j + 1] if j + 1 < grid.size else grid[j]
        best[:] = lo
        for _ in range(self.cfg.refine_rounds):
            active = (hi > lo + 1e-4) & (lo > 0)
            if not active.any():
                break
            fine = np.linspace(0.0, 1.0, self.cfg.refine_points + 2)[1:-1]
            sc = lo[:, None] + (hi - lo)[:, None] * fine[None, :]
            sc = np.where(active[:, None], sc, lo[:, None])
            scan2 = self.scan(starts, sc, duration_h, mode, shade)
            f2 = self._feasible(scan2, sc, caps)
            for i in range(starts.size):
                if not active[i]:
                    continue
                ok = np.where(f2[i])[0]
                if ok.size:
                    j = ok.max()
                    lo[i] = sc[i, j]
                    hi[i] = sc[i, j + 1] if j + 1 < sc.shape[1] else hi[i]
                else:
                    hi[i] = sc[i, 0]
            best = lo.copy()
        # sub-minimum scale may still be allowed if perception forces it? No: park instead.
        return np.where(best >= min_s - 1e-9, best, 0.0), caps

    def _binding(self, scan: dict, scale: float, cap: float, action: str) -> tuple[str, float]:
        """Name and thermal headroom of the constraint that stops a larger scale.

        ``scan`` is evaluated one notch above the chosen scale (or at the minimum
        scale for PARK). For GO the tightest component at full scale is reported.
        """
        head = scan["headroom"][0, 0]
        comps = scan["comps"]
        j = int(np.argmin(head))
        if action == "GO":
            return comps[j], float(head[j])
        evaluated = float(scan.get("scale", scale))
        if head[j] < 0:
            return comps[j], float(head[j])
        if scan["risk_min_soc"][0, 0] < self.profile.operations.soc_reserve:
            return "state_of_charge", float(head[j])
        if evaluated > cap + 1e-9:
            return "lidar_range", float(head[j])
        return comps[j], float(head[j])

    def _probe(self, idx: int, scale: float, duration_h: float, mode: str, shade: float) -> dict:
        out = self.scan(np.array([idx]), np.array([[scale]]), duration_h, mode, shade)
        out["scale"] = scale
        return out

    def _probe_scale(self, sc: float) -> float:
        """Scale at which to look for the constraint that binds just above ``sc``."""
        min_s = self.profile.operations.min_scale
        return min_s if sc <= 0 else min(1.0, sc + 0.02)

    # ------------------------------------------------------------------ public API
    def timeline(
        self,
        duration_h: float = 2.0,
        mode: str = "drive",
        step_min: float = 30.0,
        first_utc=None,
        last_utc=None,
        shade: float = 0.0,
    ) -> Timeline:
        """Decision for every start time in the forecast window."""
        w = self.weather
        t0 = np.datetime64(first_utc, "s") if first_utc is not None else w.times_utc[0]
        t1 = (
            np.datetime64(last_utc, "s")
            if last_utc is not None
            else w.times_utc[-1] - np.timedelta64(int(duration_h * 3600), "s")
        )
        if t1 < t0:
            raise ValueError("forecast is shorter than the mission duration")
        stride = max(1, int(round(step_min * 60.0 / self.cfg.dt_s)))
        i0, i1 = self._idx(t0), self._idx(t1)
        starts = np.arange(i0, i1 + 1, stride)
        scales, caps = self.best_scale(starts, duration_h, mode, shade)
        slots = []
        for i, s in enumerate(starts):
            sc = float(scales[i])
            action = "GO" if sc >= 0.999 else ("DERATE" if sc > 0 else "PARK")
            probe = self._probe(
                int(s), 1.0 if action == "GO" else self._probe_scale(sc), duration_h, mode, shade
            )
            name, head = self._binding(probe, sc, float(caps[i]), action)
            slots.append(
                Slot(
                    start_utc=self._fmt(int(s)),
                    action=action,
                    scale=round(sc, 3),
                    limiting_component=name,
                    headroom_k=round(head, 2),
                    risk_min_soc=round(float(probe["risk_min_soc"][0, 0]), 3),
                    perception_limited=bool(caps[i] < 0.999 and sc >= caps[i] - 0.01),
                )
            )
        return Timeline(
            profile_id=self.profile.id,
            site=self.site,
            weather_source=w.source,
            mode=mode,
            duration_h=duration_h,
            step_min=step_min,
            evidence_level=self.profile.evidence_level,
            slots=slots,
        )

    def shade_required(self, start_idx: int, duration_h: float, mode: str) -> float | None:
        """Smallest shade fraction making the mission feasible at the largest allowed scale."""
        caps, _, _ = self.perception_cap(np.array([start_idx]), duration_h)
        target = float(min(1.0, caps[0]))
        if target < self.profile.operations.min_scale:
            return None
        grid = np.linspace(0.0, 1.0, 11)
        sc = np.full((1, grid.size), target)
        scan = self.scan(np.array([start_idx]), sc, duration_h, mode, shade=grid[None, :])
        ok = self._feasible(scan, sc, caps)[0]
        if not ok.any():
            return None
        j = int(np.argmax(ok))
        if j == 0:
            return 0.0
        lo, hi = grid[j - 1], grid[j]
        fine = np.linspace(lo, hi, 8)[1:]
        sc2 = np.full((1, fine.size), target)
        scan2 = self.scan(np.array([start_idx]), sc2, duration_h, mode, shade=fine[None, :])
        ok2 = self._feasible(scan2, sc2, caps)[0]
        return round(float(fine[int(np.argmax(ok2))]) if ok2.any() else float(hi), 3)

    def decide(
        self,
        start_utc=None,
        duration_h: float = 2.0,
        mode: str = "drive",
        shade: float = 0.0,
        look_ahead: bool = True,
    ) -> Decision:
        """Decision for one mission window."""
        w = self.weather
        start = w.times_utc[0] if start_utc is None else np.datetime64(start_utc, "s")
        idx = self._idx(start)
        pr = self.profile
        min_s = pr.operations.min_scale
        scales, caps = self.best_scale(np.array([idx]), duration_h, mode, shade)
        sc = float(scales[0])
        _, rng_eff, pm_max = self.perception_cap(np.array([idx]), duration_h)
        action = "GO" if sc >= 0.999 else ("DERATE" if sc > 0 else "PARK")
        at_scale = self._probe(idx, sc if sc > 0 else min_s, duration_h, mode, shade)
        one = at_scale
        head = one["headroom"][0, 0]
        comps = one["comps"]
        probe = self._probe(
            idx, 1.0 if action == "GO" else self._probe_scale(sc), duration_h, mode, shade
        )
        lim_name, _ = self._binding(probe, sc, float(caps[0]), action)
        nominal = pr.value("perception.nominal_speed_ms")
        v_cap = float(
            dust.max_safe_speed_ms(
                rng_eff[0],
                pr.value("perception.decel_ms2"),
                pr.value("perception.reaction_s"),
                pr.value("perception.margin_m"),
            )
        )
        perc_limited = bool(caps[0] < 0.999 and (sc == 0 or sc >= caps[0] - 0.01))
        reasons: list[str] = []
        pretty = lim_name.replace("_", " ")
        if action == "GO":
            reasons.append(
                f"All components stay below limit less margin at the {self.q:.0%} risk quantile."
            )
        elif action == "DERATE":
            reasons.append(
                f"Full scale is not safe: {pretty} is the first constraint to bind; scale {sc:.2f} is the largest safe setting."
            )
        else:
            reasons.append(
                f"Even at the minimum scale {min_s:.2f}, {pretty} cannot be kept inside its limit."
            )
        if perc_limited:
            reasons.append(
                f"Dust cuts LiDAR range to about {rng_eff[0]:.0f} m, limiting safe speed to {v_cap:.2f} m/s."
            )
        if one["risk_min_soc"][0, 0] < pr.operations.soc_reserve:
            reasons.append("State-of-charge reserve would be breached for this duration.")
        shade_req = nxt_full = nxt_op = None
        if action != "GO":
            shade_req = self.shade_required(idx, duration_h, mode)
            if shade_req is None:
                reasons.append(
                    "No amount of shade makes full-scale operation feasible in this window."
                )
            else:
                reasons.append(
                    f"Full-scale operation becomes feasible with about {shade_req:.0%} of the mission in shade."
                )
            if look_ahead:
                nxt_full, nxt_op = self._look_ahead(idx, duration_h, mode, shade)
        components = [
            ComponentMargin(
                component=c,
                limit_c=self.limits[c].limit_c,
                margin_k=self.limits[c].margin_k,
                risk_peak_c=round(float(one["risk_peak_c"][0, 0, k]), 2),
                headroom_k=round(float(head[k]), 2),
            )
            for k, c in enumerate(comps)
            if c in self.limits
        ]
        return Decision(
            action=action,
            start_utc=self._fmt(idx),
            duration_h=duration_h,
            mode=mode,
            scale=round(sc, 3),
            speed_ms=round(sc * nominal, 3),
            throughput_fraction=round(sc, 3),
            limiting_component=lim_name,
            components=components,
            risk_min_soc=round(float(one["risk_min_soc"][0, 0]), 3),
            soc_reserve=pr.operations.soc_reserve,
            perception=Perception(
                pm10_window_max_ugm3=round(float(pm_max[0]), 1),
                lidar_range_m=round(float(rng_eff[0]), 1),
                max_safe_speed_ms=round(v_cap, 3),
                speed_fraction_cap=round(float(caps[0]), 3),
            ),
            perception_limited=perc_limited,
            shade_required_fraction=shade_req,
            next_full_scale_start_utc=nxt_full,
            next_operable_start_utc=nxt_op,
            reasons=reasons,
            evidence_level=pr.evidence_level,
            evidence_text=pr.evidence_text(),
            assumption_fraction=round(pr.assumption_fraction(), 3),
            risk_quantile=self.q,
            mc_samples=self.cfg.n_mc,
            caveat=L0_CAVEAT
            if pr.evidence_level == "L0"
            else "Calibrated profile; see model card for validity limits.",
        )

    def _look_ahead(self, idx: int, duration_h: float, mode: str, shade: float):
        stride = self._steps(0.5)
        last = self.forcing.n - 1 - self._steps(duration_h)
        starts = np.arange(idx + stride, max(idx + stride, last) + 1, stride)
        starts = starts[starts <= last]
        if starts.size == 0:
            return None, None
        scales, _ = self.best_scale(starts, duration_h, mode, shade)
        full = np.where(scales >= 0.999)[0]
        oper = np.where(scales > 0)[0]
        return (
            self._fmt(int(starts[full[0]])) if full.size else None,
            self._fmt(int(starts[oper[0]])) if oper.size else None,
        )
