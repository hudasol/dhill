"""The v0.7 results document must equal its rendering from the stored JSON."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "examples"))
pj = pytest.importorskip("prereg_eval_jackal")


def test_hidden_robots_follow_the_preregistered_worlds():
    _, w1 = pj.hidden_robot(4, "W1")
    _, w2 = pj.hidden_robot(4, "W2")
    assert set(w1) == set(pj.DRAWN)
    for k, v in pj.PRE_FIX.items():
        assert w2[k] == v
    shared = set(pj.DRAWN) - set(pj.PRE_FIX)
    assert all(w1[k] == w2[k] for k in shared)
    assert w1["power.dcdc_efficiency"] <= 0.98 and w1["surface.alpha_clean"] <= 0.95


def test_bootstrap_is_seeded_and_brackets_the_point():
    groups = {s: [{"x": float(s)}] for s in range(10)}
    a = pj._boot(groups, pj.mean(lambda r: r["x"]))
    assert a == pj._boot(groups, pj.mean(lambda r: r["x"]))
    assert a[1][0] <= a[0] <= a[1][1]


@pytest.mark.skipif(not pj.RESULTS.exists(), reason="evaluation not run")
def test_v07_document_matches_json():
    res = json.loads(pj.RESULTS.read_text(encoding="utf-8"))
    again = pj.analyse(res["raw"])
    assert json.loads(json.dumps(again)) == {k: res[k] for k in again}
    assert pj.DOC.read_text(encoding="utf-8").startswith(pj.render(res))
