"""Tests of the engine versus plant harness on recorded fixture weather (SYNTHETIC plant)."""

from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pytest

from dhill import climatology as clim
from dhill.plant.rating import draw_rated_plants
from dhill.profiles.loader import load_builtin
from dhill.structural import (
    CLASS_PROFILE,
    SCENARIOS,
    allowed_limits,
    conformal_level,
    conformal_offset,
    engine_slots,
    hard_limits,
    plant_peaks,
    run_class_day,
    window_weather,
)

ROOT = Path(__file__).parents[1]
DATA = ROOT / "tests" / "data"


@pytest.fixture(scope="module")
def record():
    return clim.load_site_record("abu_dhabi", (2024,), offline=True, cache_root=DATA)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            out.add("." * node.level + (node.module or ""))
        elif isinstance(node, ast.Import):
            out |= {a.name for a in node.names}
    return out


def test_plant_package_does_not_import_engine_physics():
    banned = ("physics", "envelope", "profiles", "policies", "calibrate", "validate")
    offenders = []
    for f in sorted((ROOT / "src" / "dhill" / "plant").glob("*.py")):
        for mod in _imports(f):
            parts = [p for p in mod.split(".") if p]
            if any(p in banned for p in parts) or mod.startswith(("dhill.physics", "..")):
                offenders.append((f.name, mod))
    assert offenders == []


def test_window_weather_covers_the_slots(record):
    w = window_weather(record, "2024-07-03")
    assert w.times_utc[0] == np.datetime64("2024-07-02T20:00:00")
    assert w.times_utc[-1] == np.datetime64("2024-07-03T16:00:00")
    assert np.isfinite(w.pm10_ugm3).all()


def test_conformal_level_and_offset():
    assert conformal_level(19) == 1.0
    assert conformal_level(100) == pytest.approx(np.ceil(101 * 0.95) / 100)
    scores = np.arange(1.0, 101.0)
    assert conformal_offset(scores) == 96.0
    with pytest.raises(ValueError):
        conformal_offset(np.array([]))


@pytest.mark.parametrize("cls", sorted(CLASS_PROFILE))
def test_class_day_shapes_and_oracle_never_breaches(record, cls):
    profile = load_builtin(CLASS_PROFILE[cls])
    w = window_weather(record, "2024-07-03")
    es = engine_slots(profile, w, "2024-07-03T03:00", "2024-07-03T06:00", seed=7)
    assert es.slot_s.shape == es.cap.shape == (4,)
    assert es.risk_peak.shape == (4, 5)
    plants = draw_rated_plants(3, 900, cls=cls)
    out = run_class_day(profile, plants, w, es, SCENARIOS["S1"], seed=1)
    assert out.scales["P6"].shape == (4, 3) and out.peak_p4.shape == (4, 3, 5)
    assert (out.scales["P6"] <= es.cap[:, None] + 1e-9).all()
    assert not out.breach["P6"].any()
    assert (allowed_limits(profile) < hard_limits(profile)).all()


def test_plant_peaks_are_reproducible_and_scenarios_differ(record):
    w = window_weather(record, "2024-07-03")
    plants = draw_rated_plants(2, 901)
    slots = np.array([8 * 3600.0, 10 * 3600.0])
    a = plant_peaks(plants, w, slots, np.ones(2), SCENARIOS["S1"], seed=3)
    b = plant_peaks(plants, w, slots, np.ones(2), SCENARIOS["S1"], seed=3)
    warm = plant_peaks(plants, w, slots, np.ones(2), SCENARIOS["S4"], seed=3)
    assert np.array_equal(a, b)
    assert warm.mean() > a.mean()
