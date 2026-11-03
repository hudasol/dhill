"""The browser demo is labelled SYNTHETIC and L0 and its data matches the engine."""

from __future__ import annotations

import json
from pathlib import Path

from dhill.envelope import EngineConfig, Envelope
from dhill.profiles.loader import builtin_profile_ids, load_builtin
from dhill.weather import synthetic_weather

DEMO = Path(__file__).parents[1] / "docs" / "demo"


def test_page_and_data_carry_the_labels():
    html = (DEMO / "index.html").read_text(encoding="utf-8")
    data = json.loads((DEMO / "data.json").read_text(encoding="utf-8"))
    assert "SYNTHETIC" in html and "L0" in html and "SYNTHETIC" in data["label"]
    assert set(data["profiles"]) == set(builtin_profile_ids())
    assert all(p["evidence_level"] == "L0" for p in data["profiles"].values())
    assert len(data["timelines"]) == len(data["profiles"]) * len(data["sites"]) * len(
        data["scenarios"]
    )
    assert "—" not in html


def test_one_timeline_matches_a_fresh_engine_run():
    data = json.loads((DEMO / "data.json").read_text(encoding="utf-8"))
    pid, site, sc = "ugv_medium_inspection", "sweihan", "heatwave"
    w = synthetic_weather(site, sc, start=data["start_utc"], days=2)
    tl = Envelope(load_builtin(pid), w, EngineConfig(n_mc=64, seed=7), site=site).timeline(
        1.0, "drive", 60.0
    )
    fresh = [
        (s.start_utc, s.action, round(s.scale, 2))
        for s in tl.slots
        if s.start_utc[:10] == data["start_utc"][:10]
    ]
    stored = [(r["t"], r["a"], r["s"]) for r in data["timelines"][f"{pid}|{site}|{sc}"]]
    assert fresh == stored
