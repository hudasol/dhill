"""Patrol route simulation: does the envelope change the mission plan, not only the yes or no?

A patrol is a small graph of waypoints. Each segment has a length and a shaded fraction;
each waypoint has a shade fraction for a robot parked there. A plan is a start delay at the
depot, a path through the graph, an operating scale, and an optional wait at a shaded node
on the way. The thermal state is integrated segment by segment with the existing solver
(``physics.thermal.simulate``) and the existing loads; shade enters through the solver's own
shade input. There is no new physics here.

Three planning policies are compared:

* ``shortest``: shortest path, full scale, leave now. No thermal awareness.
* ``air_rule``: shortest path, full scale, but wait at the depot until the forecast air
  temperature over the expected mission stays at or below a threshold (default 40 degC).
* ``envelope``: search start delays, paths, scales and shaded waits; keep only plans whose
  95 % risk quantile peak of every component stays below its limit less margin under the
  engine's parameter and forecast uncertainty; leave at the earliest delay that has an
  accepted plan and take the shortest accepted plan at that delay.

Plans are scored on a hidden, hotter "true" robot over many weather draws, as in
``policies.py``. This is a kinematic and thermal simulation in Python. It is not Gazebo, not
a dynamics simulator and not a physical test.
"""

from __future__ import annotations

import heapq
import itertools
from dataclasses import dataclass, field

import numpy as np

from . import loads as loadlib
from .envelope import EngineConfig, Envelope
from .physics.constants import k_to_c
from .physics.thermal import State, ThermalParams, lhs_normal, simulate
from .profiles.registry import COMPONENTS
from .profiles.schema import Profile
from .weather.base import Weather

_NODE = {"battery": 2, "lidar": 4, "motor": 5, "interior": 1}


# ---------------------------------------------------------------------- graph
@dataclass(frozen=True)
class Waypoint:
    id: str
    shade: float = 0.0  # shade fraction for a robot parked here
    note: str = ""


@dataclass(frozen=True)
class Segment:
    a: str
    b: str
    length_m: float
    shade: float = 0.0  # fraction of the segment's sky view blocked (solver shade input)
    max_speed_ms: float | None = None  # terrain or site rule; None means the profile speed


@dataclass
class RouteGraph:
    waypoints: dict[str, Waypoint]
    segments: list[Segment]
    _adj: dict[str, list[Segment]] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        for s in self.segments:
            if s.a not in self.waypoints or s.b not in self.waypoints:
                raise ValueError(f"segment {s.a}-{s.b} names an unknown waypoint")
            if s.length_m <= 0 or not 0.0 <= s.shade <= 1.0:
                raise ValueError(f"segment {s.a}-{s.b}: bad length or shade")
            rev = Segment(s.b, s.a, s.length_m, s.shade, s.max_speed_ms)
            self._adj.setdefault(s.a, []).append(s)
            self._adj.setdefault(s.b, []).append(rev)

    def neighbours(self, node: str) -> list[Segment]:
        return self._adj.get(node, [])

    def shortest_path(self, a: str, b: str) -> list[Segment]:
        """Dijkstra on segment length."""
        dist = {a: 0.0}
        prev: dict[str, Segment] = {}
        heap = [(0.0, a)]
        while heap:
            d, u = heapq.heappop(heap)
            if u == b:
                break
            if d > dist.get(u, np.inf):
                continue
            for s in self.neighbours(u):
                nd = d + s.length_m
                if nd < dist.get(s.b, np.inf):
                    dist[s.b] = nd
                    prev[s.b] = s
                    heapq.heappush(heap, (nd, s.b))
        if b not in dist:
            raise ValueError(f"no path from {a} to {b}")
        path = []
        node = b
        while node != a:
            seg = prev[node]
            path.append(seg)
            node = seg.a
        return path[::-1]

    def simple_paths(self, a: str, b: str, max_paths: int = 20) -> list[list[Segment]]:
        """All simple paths from ``a`` to ``b`` (depth first), shortest first."""
        out: list[list[Segment]] = []

        def walk(node: str, seen: set[str], path: list[Segment]) -> None:
            if len(out) >= 10 * max_paths:
                return
            if node == b:
                out.append(list(path))
                return
            for s in self.neighbours(node):
                if s.b not in seen:
                    path.append(s)
                    walk(s.b, seen | {s.b}, path)
                    path.pop()

        walk(a, {a}, [])
        out.sort(key=lambda p: (path_length(p), len(p)))
        return out[:max_paths]


def path_length(path: list[Segment]) -> float:
    return float(sum(s.length_m for s in path))


# ---------------------------------------------------------------------- plans
@dataclass(frozen=True)
class Plan:
    """A concrete mission plan. ``legs`` are paths visited in order (a patrol loop)."""

    policy: str
    delay_min: float
    legs: tuple[tuple[Segment, ...], ...]
    scale: float
    wait_node: str | None = None
    wait_min: float = 0.0

    @property
    def route(self) -> str:
        nodes = [self.legs[0][0].a] if self.legs and self.legs[0] else []
        for leg in self.legs:
            nodes += [s.b for s in leg]
        return "-".join(nodes)


@dataclass(frozen=True)
class Step:
    kind: str  # "move" or "wait"
    minutes: float
    shade: float
    scale: float = 0.0


def plan_steps(plan: Plan, graph: RouteGraph, nominal_speed_ms: float) -> list[Step]:
    """Turn a plan into timed steps: depot wait, moves, optional shaded wait."""
    steps = []
    depot = plan.legs[0][0].a
    if plan.delay_min > 0:
        steps.append(Step("wait", plan.delay_min, graph.waypoints[depot].shade))
    waited = False
    for leg in plan.legs:
        for s in leg:
            v = nominal_speed_ms * plan.scale
            if s.max_speed_ms is not None:
                v = min(v, s.max_speed_ms)
            steps.append(Step("move", s.length_m / v / 60.0, s.shade, plan.scale))
            if not waited and plan.wait_node == s.b and plan.wait_min > 0:
                steps.append(Step("wait", plan.wait_min, graph.waypoints[s.b].shade))
                waited = True
    return steps


def mission_minutes(steps: list[Step]) -> float:
    return float(sum(s.minutes for s in steps))


# ---------------------------------------------------------------------- execution
@dataclass
class Execution:
    finish_min: float  # from request time
    peaks_c: np.ndarray  # (B, n_components) peak over the whole plan
    comps: list[str]
    end: State | None = None


def execute(
    profile: Profile,
    env: Envelope,
    params: ThermalParams,
    plan: Plan,
    graph: RouteGraph,
    request_idx: int,
    state0: State,
    steps: list[Step] | None = None,
) -> Execution:
    """Integrate the thermal network along a plan for every batch member of ``params``."""
    dt = env.forcing.dt_s
    if steps is None:
        steps = plan_steps(plan, graph, profile.value("perception.nominal_speed_ms"))
    st = state0.copy()
    b = st.batch
    comps = list(COMPONENTS)
    peaks = np.full((b, len(comps)), -np.inf)
    idx = request_idx
    elapsed_s = 0.0
    for stp in steps:
        n = max(1, int(round(stp.minutes * 60.0 / dt)))
        if stp.kind == "move":
            lo = loadlib.mission_loads(profile, np.full(b, stp.scale), "drive")
        else:
            lo = loadlib.parked_loads(profile, b)
        res = simulate(params, env.forcing, lo, st, idx, n, shade=stp.shade, record_every=10**6)
        for j, c in enumerate(comps):
            pk = res.peak_die_k if c == "compute_die" else res.peak_k[:, _NODE[c]]
            peaks[:, j] = np.maximum(peaks[:, j], k_to_c(pk))
        st = res.end
        idx += n
        elapsed_s += n * dt
    return Execution(finish_min=elapsed_s / 60.0, peaks_c=peaks, comps=comps, end=st)


# ---------------------------------------------------------------------- policies
@dataclass
class PlanningProblem:
    profile: Profile  # what the planner believes (L0)
    weather: Weather  # forecast the planner sees
    graph: RouteGraph
    depot: str
    checkpoints: tuple[str, ...]  # visited in order, then back to the depot
    request_utc: str
    deadline_min: float = 360.0
    cfg: EngineConfig = field(default_factory=lambda: EngineConfig(n_mc=48, dt_s=120.0))

    def __post_init__(self) -> None:
        self.cfg.parked_shade = self.graph.waypoints[self.depot].shade
        self.env = Envelope(self.profile, self.weather, self.cfg)
        self.request_idx = self.env._idx(self.request_utc)
        self.stops = (self.depot, *self.checkpoints, self.depot)

    def soak(self, env: Envelope | None = None) -> State:
        """State after the parked soak at the depot before the request time."""
        e = env or self.env
        st, _ = e._soak_state(np.array([self.request_idx]))
        return st

    def shortest_legs(self) -> tuple[tuple[Segment, ...], ...]:
        return tuple(
            tuple(self.graph.shortest_path(a, b)) for a, b in itertools.pairwise(self.stops)
        )

    def air_c(self) -> np.ndarray:
        return k_to_c(self.env.forcing.t_air_k)


def plan_shortest(pp: PlanningProblem) -> Plan:
    return Plan("shortest", 0.0, pp.shortest_legs(), 1.0)


def plan_air_rule(
    pp: PlanningProblem, limit_c: float = 40.0, step_min: float = 30.0
) -> Plan | None:
    """Wait at the depot until the forecast air over the expected mission is within the rule."""
    legs = pp.shortest_legs()
    nominal = pp.profile.value("perception.nominal_speed_ms")
    dur = mission_minutes(plan_steps(Plan("x", 0.0, legs, 1.0), pp.graph, nominal))
    air = pp.air_c()
    dt_min = pp.env.forcing.dt_s / 60.0
    delay = 0.0
    while delay + dur <= pp.deadline_min:
        i0 = pp.request_idx + int(round(delay / dt_min))
        i1 = i0 + int(np.ceil(dur / dt_min))
        if i1 >= air.size:
            return None
        if air[i0 : i1 + 1].max() <= limit_c:
            return Plan("air_rule", delay, legs, 1.0)
        delay += step_min
    return None


def _allowed(profile: Profile, comps: list[str]) -> np.ndarray:
    return np.array(
        [
            profile.limits[c].limit_c - profile.limits[c].margin_k
            if c in profile.limits
            else np.inf
            for c in comps
        ]
    )


def envelope_ok(pp: PlanningProblem, plan: Plan, state0: State) -> tuple[bool, float]:
    """Feasible on the planner's own uncertain model at the profile's risk quantile."""
    ex = execute(pp.profile, pp.env, pp.env.params, plan, pp.graph, pp.request_idx, state0)
    q = pp.profile.operations.risk_quantile
    risk = np.quantile(ex.peaks_c, q, axis=0, method="higher")
    return bool(np.all(risk <= _allowed(pp.profile, ex.comps))), ex.finish_min


def plan_envelope(
    pp: PlanningProblem,
    scales=(1.0, 0.7),
    waits_min=(20.0,),
    delay_step_min: float = 30.0,
    max_paths: int = 2,
) -> Plan | None:
    """Earliest start with an accepted plan, shortest accepted plan at that start, or None.

    Candidates: up to ``max_paths`` simple paths per leg, each scale, and optionally one wait
    at a shaded waypoint on the route. Start delays are tried in steps of ``delay_step_min``;
    the parked wait at the depot is integrated once per delay and shared by all candidates.
    """
    state0 = pp.soak()
    q = pp.profile.operations.risk_quantile
    leg_options = [pp.graph.simple_paths(a, b, max_paths) for a, b in itertools.pairwise(pp.stops)]
    nominal = pp.profile.value("perception.nominal_speed_ms")
    shaded = {w for w, p in pp.graph.waypoints.items() if p.shade > 0 and w != pp.depot}
    candidates = []
    for legs in itertools.product(*leg_options):
        legs_t = tuple(tuple(p) for p in legs)
        visited = [s.b for leg in legs_t for s in leg]
        for sc in scales:
            for wn in [None, *sorted(shaded & set(visited))]:
                for wm in waits_min if wn else (0.0,):
                    p = Plan("envelope", 0.0, legs_t, sc, wn, wm)
                    steps = plan_steps(p, pp.graph, nominal)
                    candidates.append((mission_minutes(steps), p, steps))
    candidates.sort(key=lambda c: c[0])
    depot_shade = pp.graph.waypoints[pp.depot].shade
    dt_min = pp.env.forcing.dt_s / 60.0
    st = state0
    wait_peak = np.full((st.batch, len(COMPONENTS)), -np.inf)
    delay = 0.0
    while delay + candidates[0][0] <= pp.deadline_min:
        idx = pp.request_idx + int(round(delay / dt_min))
        for dur, p, steps in candidates:
            if delay + dur > pp.deadline_min:
                break
            ex = execute(pp.profile, pp.env, pp.env.params, p, pp.graph, idx, st, steps)
            peaks = np.maximum(ex.peaks_c, wait_peak)
            risk = np.quantile(peaks, q, axis=0, method="higher")
            if np.all(risk <= _allowed(pp.profile, ex.comps)):
                return Plan(p.policy, delay, p.legs, p.scale, p.wait_node, p.wait_min)
        # wait one more delay step at the depot, then try again
        wait = Plan("wait", delay_step_min, ((),), 0.0)
        ex = execute(
            pp.profile,
            pp.env,
            pp.env.params,
            wait,
            pp.graph,
            idx,
            st,
            [Step("wait", delay_step_min, depot_shade)],
        )
        st = ex.end
        wait_peak = np.maximum(wait_peak, ex.peaks_c)
        delay += delay_step_min
    return None


# ---------------------------------------------------------------------- scoring
@dataclass
class RouteScore:
    policy: str
    planned: bool  # the policy produced a plan within the deadline
    finish_min: float  # planned completion time from the request (nan if no plan)
    p_violation: float  # share of weather draws with any component above its hard limit
    completion_rate: float  # share of draws completed within the deadline without violation
    route: str = ""
    scale: float = 0.0
    delay_min: float = 0.0
    wait: str = ""


def truth_env(
    truth: Profile,
    weather: Weather,
    worlds: int,
    seed: int,
    dt_s: float,
    parked_shade: float,
    sigma_t: float = 2.0,
    sigma_irr: float = 0.15,
    sigma_wind: float = 0.30,
) -> Envelope:
    """Envelope bound to the true robot with forecast error drawn heavier than the engine's."""
    env = Envelope(
        truth, weather, EngineConfig(n_mc=worlds, dt_s=dt_s, parked_shade=parked_shade, seed=seed)
    )
    rng = np.random.default_rng(seed)
    p0 = ThermalParams.from_profile(truth, n=worlds)
    env.params = p0.replace_values(
        d_temp_k=sigma_t * lhs_normal(rng, worlds),
        irr_scale=np.exp(sigma_irr * lhs_normal(rng, worlds)),
        wind_scale=np.exp(sigma_wind * lhs_normal(rng, worlds)),
    )
    return env


def score_plan(
    pp: PlanningProblem, plan: Plan | None, policy: str, true_env: Envelope, truth: Profile
) -> RouteScore:
    if plan is None:
        return RouteScore(policy, False, float("nan"), 0.0, 0.0)
    st, _ = true_env._soak_state(np.array([pp.request_idx]))
    ex = execute(truth, true_env, true_env.params, plan, pp.graph, pp.request_idx, st)
    hard = np.array([truth.limits[c].limit_c if c in truth.limits else np.inf for c in ex.comps])
    viol = np.any(ex.peaks_c > hard[None, :], axis=1)
    on_time = ex.finish_min <= pp.deadline_min
    return RouteScore(
        policy=policy,
        planned=True,
        finish_min=round(ex.finish_min, 1),
        p_violation=float(viol.mean()),
        completion_rate=float(np.mean(~viol & on_time)),
        route=plan.route,
        scale=plan.scale,
        delay_min=plan.delay_min,
        wait=f"{plan.wait_node} {plan.wait_min:g} min" if plan.wait_node else "",
    )


def compare(
    pp: PlanningProblem,
    truth: Profile,
    worlds: int = 200,
    seed: int = 123,
    air_limit_c: float = 40.0,
) -> list[RouteScore]:
    """Plan with each policy on the L0 profile, then score every plan on the true robot."""
    true_env = truth_env(
        truth, pp.weather, worlds, seed, pp.cfg.dt_s, pp.graph.waypoints[pp.depot].shade
    )
    plans = {
        "shortest": plan_shortest(pp),
        f"air_rule_{air_limit_c:g}C": plan_air_rule(pp, air_limit_c),
        "envelope": plan_envelope(pp),
    }
    return [score_plan(pp, p, name, true_env, truth) for name, p in plans.items()]
