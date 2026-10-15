"""Patrol route simulation: does the envelope change a mission plan, not just a yes or no?

A patrol is an ordered list of stops on a small graph. Each edge has a length and a shade
fraction (0 open road, close to 1 under a canopy or building shadow). Some nodes are shaded
places where the robot may pause. The robot's thermal state is integrated along the route with
the existing network (`physics.thermal.simulate`), one piece at a time (drive, wait, dwell),
using the shade input per piece. No new physics is added.

Three policies are compared:

* ``shortest``: shortest path, leave at once.
* ``air_rule``: shortest path, but delay departure in the shaded depot until the forecast air
  temperature stays at or below a threshold for the nominal mission duration.
* ``envelope``: choose among the shortest and the least sun exposed path for every leg and
  pause in shaded nodes so that, at the risk quantile over the Monte Carlo ensemble, no
  component passes its limit less margin and the battery keeps its reserve.

Plans are made from the forecast and the profile (with its uncertainty) only. They are then
executed by a hidden, hotter "true" robot over many weather realisations whose forecast error is
heavier than the engine assumes (see :mod:`dhill.policies`). This is a kinematic and thermal
simulation in Python. It is not Gazebo and not a physical test, and the graph is illustrative.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field, replace

import numpy as np

from . import loads as loadlib
from .envelope import _NODE, EngineConfig, Envelope
from .physics.constants import k_to_c
from .physics.thermal import State, ThermalParams, lhs_normal, simulate
from .profiles.schema import Profile
from .weather.base import Weather

COMPONENTS = ("battery", "compute_die", "lidar", "motor", "interior")
WAIT_OPTIONS_MIN = (0, 5, 10, 15, 20, 30, 45, 60)


# ----------------------------------------------------------------------------- graph
@dataclass(frozen=True)
class Edge:
    a: str
    b: str
    length_m: float
    shade: float  # 0 open, 1 fully shaded


@dataclass
class Graph:
    """Undirected graph of edges plus the nodes where waiting in shade is possible."""

    edges: tuple[Edge, ...]
    shaded_nodes: dict[str, float] = field(default_factory=dict)  # node -> shade while waiting

    def neighbours(self, node: str) -> list[tuple[str, Edge]]:
        out = []
        for e in self.edges:
            if e.a == node:
                out.append((e.b, e))
            elif e.b == node:
                out.append((e.a, e))
        return out

    def edge(self, u: str, v: str) -> Edge:
        for e in self.edges:
            if {e.a, e.b} == {u, v}:
                return e
        raise KeyError(f"no edge {u}-{v}")

    def _best_path(self, src: str, dst: str, cost) -> tuple[str, ...]:
        """Dijkstra on ``cost(edge)``."""
        best = {src: 0.0}
        prev: dict[str, str] = {}
        heap = [(0.0, src)]
        while heap:
            d, u = heapq.heappop(heap)
            if u == dst:
                break
            if d > best.get(u, np.inf):
                continue
            for v, e in self.neighbours(u):
                nd = d + cost(e)
                if nd < best.get(v, np.inf):
                    best[v] = nd
                    prev[v] = u
                    heapq.heappush(heap, (nd, v))
        if dst not in best:
            raise KeyError(f"no path {src} to {dst}")
        path = [dst]
        while path[-1] != src:
            path.append(prev[path[-1]])
        return tuple(reversed(path))

    def shortest(self, src: str, dst: str) -> tuple[str, ...]:
        return self._best_path(src, dst, lambda e: e.length_m)

    def least_exposed(self, src: str, dst: str) -> tuple[str, ...]:
        """Path minimising the sun exposed length, sum of length times (1 - shade)."""
        return self._best_path(src, dst, lambda e: e.length_m * (1.0 - e.shade) + 1e-3 * e.length_m)

    def path_length(self, path: tuple[str, ...]) -> float:
        return sum(self.edge(u, v).length_m for u, v in zip(path[:-1], path[1:], strict=True))


def patrol_graph() -> Graph:
    """Illustrative depot patrol: an open ring road and a longer sheltered service corridor.

    The geometry is invented for this simulation. Lengths are metres. The sheltered corridor
    is about 27 percent longer than the open road and about 80 percent shaded.
    """
    open_, cover = 0.05, 0.80
    e = [
        Edge("depot", "T1", 500, open_),
        Edge("T1", "T2", 600, open_),
        Edge("T2", "T3", 450, open_),
        Edge("T3", "depot", 650, open_),
        Edge("depot", "S1", 350, cover),
        Edge("S1", "T1", 300, cover),
        Edge("T1", "S2", 400, cover),
        Edge("S2", "T2", 350, cover),
        Edge("T2", "S3", 300, cover),
        Edge("S3", "T3", 250, cover),
        Edge("T3", "S4", 450, cover),
        Edge("S4", "depot", 400, cover),
    ]
    shaded = {"depot": 0.90, "S1": 0.80, "S2": 0.80, "S3": 0.80, "S4": 0.80}
    return Graph(tuple(e), shaded)


@dataclass(frozen=True)
class Mission:
    stops: tuple[str, ...] = ("depot", "T1", "T2", "T3", "depot")
    dwell_min: float = 6.0  # inspection dwell at every stop except the last
    deadline_h: float = 4.0  # must be finished this long after the desired start
    speed_ms: float | None = None  # default: the profile's nominal speed


# ----------------------------------------------------------------------------- pieces
@dataclass(frozen=True)
class Piece:
    kind: str  # "drive", "wait" or "dwell"
    seconds: float
    shade: float


def leg_pieces(
    graph: Graph, path: tuple[str, ...], wait_min: float, wait_node: str | None, speed_ms: float
) -> list[Piece]:
    """Drive pieces along ``path`` with a pause at ``wait_node`` (a shaded node on the path)."""
    pieces: list[Piece] = []
    for i, node in enumerate(path):
        if wait_min > 0 and node == wait_node:
            pieces.append(Piece("wait", wait_min * 60.0, graph.shaded_nodes[node]))
        if i + 1 < len(path):
            e = graph.edge(node, path[i + 1])
            pieces.append(Piece("drive", e.length_m / speed_ms, e.shade))
    return pieces


@dataclass(frozen=True)
class LegPlan:
    path: tuple[str, ...]
    wait_min: float = 0.0
    wait_node: str | None = None


@dataclass
class Plan:
    name: str
    legs: list[LegPlan] | None  # None means the policy declined to run
    reason: str = ""

    @property
    def runs(self) -> bool:
        return self.legs is not None


def plan_pieces(graph: Graph, plan: Plan, mission: Mission, speed_ms: float) -> list[Piece]:
    assert plan.legs is not None
    pieces: list[Piece] = []
    for j, leg in enumerate(plan.legs):
        pieces += leg_pieces(graph, leg.path, leg.wait_min, leg.wait_node, speed_ms)
        if j + 1 < len(plan.legs) and mission.dwell_min > 0:
            pieces.append(Piece("dwell", mission.dwell_min * 60.0, 0.10))
    return pieces


# ----------------------------------------------------------------------------- execution
@dataclass
class Ensemble:
    """Thermal state and running extremes for a batch of Monte Carlo members or true worlds."""

    state: State
    peak_k: np.ndarray  # (B, 6)
    peak_die_k: np.ndarray  # (B,)
    min_soc: np.ndarray  # (B,)
    steps: int = 0  # elapsed forcing steps

    def copy(self) -> Ensemble:
        return Ensemble(
            self.state.copy(),
            self.peak_k.copy(),
            self.peak_die_k.copy(),
            self.min_soc.copy(),
            self.steps,
        )

    def peaks_c(self) -> np.ndarray:
        """Per member component peaks in degC, columns in COMPONENTS order."""
        out = np.zeros((self.peak_k.shape[0], len(COMPONENTS)))
        for j, c in enumerate(COMPONENTS):
            out[:, j] = self.peak_die_k if c == "compute_die" else self.peak_k[:, _NODE[c]]
        return k_to_c(out)


def start_ensemble(env: Envelope, idx: int) -> Ensemble:
    """Parked, soaked start at forcing index ``idx`` for every member of ``env``."""
    soak, _ = env._soak_state(np.array([idx]))
    return Ensemble(soak.copy(), soak.t_k.copy(), np.zeros(soak.batch), soak.soc.copy(), 0)


def advance(env: Envelope, ens: Ensemble, idx0: int, piece: Piece) -> Ensemble:
    """Integrate one piece from the ensemble state. Returns a new ensemble."""
    prof = env.profile
    if piece.kind == "drive":
        loads = loadlib.mission_loads(prof, 1.0, "drive")
    elif piece.kind == "dwell":
        loads = loadlib.mission_loads(prof, 1.0, "work")
    else:
        loads = loadlib.parked_loads(prof, None)
    n = max(1, int(np.ceil(piece.seconds / env.forcing.dt_s)))
    res = simulate(
        env.params,
        env.forcing,
        loads,
        ens.state,
        idx0 + ens.steps,
        n,
        shade=piece.shade,
        record_every=10**6,
    )
    return Ensemble(
        res.end,
        np.maximum(ens.peak_k, res.peak_k),
        np.maximum(ens.peak_die_k, res.peak_die_k),
        np.minimum(ens.min_soc, res.min_soc),
        ens.steps + n,
    )


def execute(env: Envelope, pieces: list[Piece], idx0: int) -> Ensemble:
    ens = start_ensemble(env, idx0)
    for p in pieces:
        ens = advance(env, ens, idx0, p)
    return ens


def feasible(env: Envelope, ens: Ensemble) -> bool:
    """Risk quantile peaks inside limit less margin, and battery reserve kept."""
    q = env.q
    pk = ens.peaks_c()
    for j, c in enumerate(COMPONENTS):
        lim = env.limits.get(c)
        if lim is None:
            continue
        if np.quantile(pk[:, j], q, method="higher") > lim.limit_c - lim.margin_k:
            return False
    low_soc = float(np.quantile(ens.min_soc, 1.0 - q))
    return low_soc >= env.profile.operations.soc_reserve


# ----------------------------------------------------------------------------- policies
def _speed(env: Envelope, mission: Mission) -> float:
    return mission.speed_ms or env.profile.value("perception.nominal_speed_ms")


def shortest_plan(graph: Graph, mission: Mission) -> Plan:
    legs = [
        LegPlan(graph.shortest(a, b))
        for a, b in zip(mission.stops[:-1], mission.stops[1:], strict=True)
    ]
    return Plan("shortest", legs)


def nominal_minutes(graph: Graph, plan: Plan, mission: Mission, speed_ms: float) -> float:
    return sum(p.seconds for p in plan_pieces(graph, plan, mission, speed_ms)) / 60.0


def air_rule_plan(
    env: Envelope,
    graph: Graph,
    mission: Mission,
    idx0: int,
    limit_c: float = 40.0,
    step_min: float = 5.0,
) -> Plan:
    """Shortest path; delay departure until forecast air stays at or below ``limit_c``."""
    base = shortest_plan(graph, mission)
    speed = _speed(env, mission)
    dur_min = nominal_minutes(graph, base, mission, speed)
    slack_min = mission.deadline_h * 60.0 - dur_min
    air = k_to_c(env.forcing.t_air_k)
    wait = 0.0
    while wait <= slack_min:
        i0 = idx0 + int(round(wait * 60.0 / env.forcing.dt_s))
        i1 = i0 + int(np.ceil(dur_min * 60.0 / env.forcing.dt_s))
        if air[i0 : i1 + 1].max() <= limit_c:
            legs = list(base.legs)
            legs[0] = LegPlan(legs[0].path, wait, "depot" if wait > 0 else None)
            return Plan("air_rule", legs)
        wait += step_min
    return Plan("air_rule", None, f"forecast air stays above {limit_c:g} C for the whole window")


def _candidates(graph: Graph, a: str, b: str, speed: float) -> list[LegPlan]:
    """Path variants and pauses for one leg, fastest first."""
    paths = {graph.shortest(a, b), graph.least_exposed(a, b)}
    out: list[tuple[float, LegPlan]] = []
    for path in paths:
        wait_node = next((n for n in path if n in graph.shaded_nodes), None)
        for w in WAIT_OPTIONS_MIN if wait_node else (0,):
            leg = LegPlan(path, float(w), wait_node if w else None)
            t = sum(p.seconds for p in leg_pieces(graph, path, w, wait_node, speed))
            out.append((t, leg))
    out.sort(key=lambda x: x[0])
    return [leg for _, leg in out]


def envelope_plan(
    env: Envelope,
    graph: Graph,
    mission: Mission,
    idx0: int,
    max_evals: int = 4000,
) -> Plan:
    """Depth first search over (path variant, pause) per leg, fastest feasible first."""
    speed = _speed(env, mission)
    base = shortest_plan(graph, mission)
    slack_min = mission.deadline_h * 60.0 - nominal_minutes(graph, base, mission, speed)
    pairs = list(zip(mission.stops[:-1], mission.stops[1:], strict=True))
    cands = [_candidates(graph, a, b, speed) for a, b in pairs]
    evals = 0

    def dwell(ens: Ensemble, j: int) -> Ensemble:
        if j + 1 < len(pairs) and mission.dwell_min > 0:
            return advance(env, ens, idx0, Piece("dwell", mission.dwell_min * 60.0, 0.10))
        return ens

    def search(j: int, ens: Ensemble, waited: float) -> list[LegPlan] | None:
        nonlocal evals
        if j == len(pairs):
            return []
        for leg in cands[j]:
            if waited + leg.wait_min > slack_min + 1e-9:
                continue
            evals += 1
            if evals > max_evals:
                raise _Budget
            e2 = ens
            for p in leg_pieces(graph, leg.path, leg.wait_min, leg.wait_node, speed):
                e2 = advance(env, e2, idx0, p)
            e2 = dwell(e2, j)
            if not feasible(env, e2):
                continue
            rest = search(j + 1, e2, waited + leg.wait_min)
            if rest is not None:
                return [leg, *rest]
        return None

    try:
        legs = search(0, start_ensemble(env, idx0), 0.0)
    except _Budget:
        return Plan("envelope", None, f"search budget of {max_evals} evaluations exhausted")
    if legs is None:
        return Plan("envelope", None, "no path and pause combination keeps every limit in time")
    return Plan("envelope", legs)


class _Budget(Exception):
    pass


# ----------------------------------------------------------------------------- scoring
@dataclass
class RouteScore:
    policy: str
    runs: bool
    completed: float  # P(plan runs and no hard limit is exceeded)
    violation_prob: float  # P(any hard limit exceeded | plan runs); nan if it does not run
    minutes: float  # mission time in minutes from the desired start; nan if it does not run
    reason: str = ""


def truth_env(
    truth: Profile,
    weather: Weather,
    worlds: int,
    cfg: EngineConfig,
    sigma_t: float = 2.0,
    sigma_irr: float = 0.15,
    sigma_wind: float = 0.30,
    seed: int = 123,
) -> Envelope:
    """Envelope whose members are the true robot over weather error draws (no parameter spread)."""
    env = Envelope(truth, weather, replace(cfg, n_mc=worlds))
    rng = np.random.default_rng(seed)
    p0 = ThermalParams.from_profile(truth, n=worlds)
    env.params = p0.replace_values(
        d_temp_k=sigma_t * lhs_normal(rng, worlds),
        irr_scale=np.exp(sigma_irr * lhs_normal(rng, worlds)),
        wind_scale=np.exp(sigma_wind * lhs_normal(rng, worlds)),
    )
    return env


def score_plan(
    truth: Envelope, graph: Graph, mission: Mission, plan: Plan, idx0: int, speed_ms: float
) -> RouteScore:
    """Execute ``plan`` on the true robot and score it."""
    if not plan.runs:
        return RouteScore(plan.name, False, 0.0, float("nan"), float("nan"), plan.reason)
    pieces = plan_pieces(graph, plan, mission, speed_ms)
    ens = execute(truth, pieces, idx0)
    hard = np.array([truth.profile.limits[c].limit_c for c in COMPONENTS])
    viol = np.any(ens.peaks_c() > hard[None, :], axis=1)
    minutes = nominal_minutes(graph, plan, mission, speed_ms)
    return RouteScore(
        plan.name, True, float(1.0 - viol.mean()), float(viol.mean()), float(minutes), plan.reason
    )


def compare_case(
    base: Profile,
    truth_profile: Profile,
    weather: Weather,
    start_idx: int,
    graph: Graph,
    mission: Mission,
    cfg: EngineConfig,
    worlds: int = 100,
    calibrated: Profile | None = None,
    air_limit_c: float = 40.0,
    truth: Envelope | None = None,
) -> list[RouteScore]:
    """Plan with every policy from the forecast and ``base``, then score on the true robot.

    ``calibrated`` is an optional profile fitted on telemetry; it gives the ``envelope_l2`` row.
    ``truth`` may be passed to reuse the true robot's weather draws across start times.
    """
    env = Envelope(base, weather, cfg)
    truth = truth or truth_env(truth_profile, weather, worlds, cfg)
    speed = _speed(env, mission)
    plans = [
        shortest_plan(graph, mission),
        air_rule_plan(env, graph, mission, start_idx, air_limit_c),
        replace_name(envelope_plan(env, graph, mission, start_idx), "envelope_l0"),
    ]
    if calibrated is not None:
        env2 = Envelope(calibrated, weather, cfg)
        plans.append(replace_name(envelope_plan(env2, graph, mission, start_idx), "envelope_l2"))
    return [score_plan(truth, graph, mission, p, start_idx, speed) for p in plans]


def replace_name(plan: Plan, name: str) -> Plan:
    return Plan(name, plan.legs, plan.reason)
