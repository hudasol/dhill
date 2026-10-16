"""The preregistered results document must equal what the code renders from the stored JSON."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "examples"))
pe = pytest.importorskip("prereg_eval")
RESULTS = ROOT / "examples" / "prereg_results.json"
DOC = ROOT / "docs" / "prereg-results.md"


def test_wilson_interval():
    lo, hi = pe.wilson(80, 80)
    assert hi == pytest.approx(1.0) and 0.95 < lo < 1.0
    lo, hi = pe.wilson(40, 80)
    assert lo < 0.5 < hi


def test_bootstrap_is_seeded():
    data = {0: [1.0, 2.0], 1: [3.0], 2: [-1.0, 0.5]}
    assert pe.boot_mean(data, n=200) == pe.boot_mean(data, n=200)


def test_hidden_robot_is_seeded_and_bounded():
    a, over_a = pe.hidden_robot(3)
    b, over_b = pe.hidden_robot(3)
    assert over_a == over_b
    assert set(over_a) == set(pe.DRAWN)
    assert over_a["surface.alpha_clean"] <= 0.95


@pytest.mark.skipif(not RESULTS.exists(), reason="evaluation not run")
def test_results_document_matches_json():
    res = json.loads(RESULTS.read_text(encoding="utf-8"))
    # the stored analysis must follow from the stored raw results
    again = pe.analyse(res["raw"])
    assert json.loads(json.dumps(again)) == {k: res[k] for k in again}
    # every number in the rendered part of the document comes from the JSON
    assert DOC.read_text(encoding="utf-8").startswith(pe.render(res))
