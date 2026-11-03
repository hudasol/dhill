"""The pastel theme meets WCAG 2.1 AA and the dashboard carries cues other than colour."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient

from dhill.api.app import app

ROOT = Path(__file__).parents[1]


def _script():
    spec = importlib.util.spec_from_file_location(
        "check_contrast", ROOT / "scripts" / "check_contrast.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_every_theme_pair_passes_aa():
    rows = _script().check()
    failed = [r for r in rows if not r[5]]
    assert failed == [] and len(rows) >= 20


def test_ratio_of_black_on_white_is_21():
    assert abs(_script().ratio("#000000", "#ffffff") - 21.0) < 1e-6


def test_dashboard_inlines_theme_and_marks_decisions_with_shapes():
    html = TestClient(app).get("/").text
    assert "--sakura-50" in html and "/*THEME*/" not in html
    assert "\\u25CF" in html and "\\u25B2" in html and "\\u25A0" in html
    assert "—" not in html
