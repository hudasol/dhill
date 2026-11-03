"""Precompute the decisions shown by the browser demo (`docs/demo/index.html`).

Every entry is SYNTHETIC: an illustrative L0 robot profile, a synthetic weather scenario and the
engine's own output. The page needs no server and no network.
Run: python scripts/build_demo.py
"""

from __future__ import annotations

import json
from pathlib import Path

from dhill import __version__
from dhill.envelope import EngineConfig, Envelope
from dhill.profiles.loader import builtin_profile_ids, load_builtin
from dhill.weather import synthetic_weather

ROOT = Path(__file__).resolve().parents[1]
SITES = ("abu_dhabi", "al_ain", "sweihan")
SCENARIOS = ("summer_clear", "heatwave")
START = "2026-08-05T00:00"


def build() -> dict:
    out: dict = {
        "version": __version__,
        "label": "SYNTHETIC weather and illustrative L0 robot profiles. Not a forecast, not a real robot.",
        "start_utc": START,
        "profiles": {},
        "sites": list(SITES),
        "scenarios": list(SCENARIOS),
        "timelines": {},
    }
    for pid in builtin_profile_ids():
        prof = load_builtin(pid)
        out["profiles"][pid] = {
            "name": prof.name,
            "evidence_level": prof.evidence_level,
            "assumption_fraction": round(prof.assumption_fraction(), 3),
        }
        for site in SITES:
            for sc in SCENARIOS:
                w = synthetic_weather(site, sc, start=START, days=2)
                env = Envelope(prof, w, EngineConfig(n_mc=64, seed=7), site=site)
                tl = env.timeline(1.0, "drive", 60.0)
                out["timelines"][f"{pid}|{site}|{sc}"] = [
                    {
                        "t": s.start_utc,
                        "a": s.action,
                        "s": round(s.scale, 2),
                        "c": s.limiting_component,
                    }
                    for s in tl.slots
                    if s.start_utc[:10] == START[:10]
                ]
    return out


def main() -> None:
    data = build()
    path = ROOT / "docs" / "demo" / "data.json"
    path.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    theme = ROOT / "src" / "dhill" / "web" / "theme.css"
    (ROOT / "docs" / "demo" / "theme.css").write_text(
        theme.read_text(encoding="utf-8"), encoding="utf-8"
    )
    print(f"wrote {path} ({path.stat().st_size} bytes, {len(data['timelines'])} timelines)")


if __name__ == "__main__":
    main()
