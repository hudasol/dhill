"""docs/evidence-checks.md must equal its rendering from examples/evidence_checks.json."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
_spec = importlib.util.spec_from_file_location(
    "gen_evidence_checks", ROOT / "scripts" / "gen_evidence_checks.py"
)
ev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ev)


@pytest.mark.skipif(not ev.OUT.exists(), reason="evidence checks not run")
def test_evidence_document_matches_json():
    res = json.loads(ev.OUT.read_text(encoding="utf-8"))
    assert ev.DOC.read_text(encoding="utf-8") == ev.render(res)


@pytest.mark.skipif(not ev.OUT.exists(), reason="evidence checks not run")
def test_every_day_run_covers_the_whole_year():
    res = json.loads(ev.OUT.read_text(encoding="utf-8"))
    assert res["sampling"]["every_day"]["days"] in (365, 366)
    assert [m["month"] for m in res["sampling"]["sampled"]["month"]] == list(range(1, 13))
