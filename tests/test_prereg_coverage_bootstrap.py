"""The H5 coverage addendum must equal its rendering from the stored preregistered results."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "examples"))
cb = pytest.importorskip("prereg_coverage_bootstrap")


def test_bootstrap_resamples_whole_seeds_and_is_seeded():
    counts = {0: (90, 100), 1: (100, 100), 2: (95, 100)}
    a, b = cb.bootstrap(counts, n=500), cb.bootstrap(counts, n=500)
    assert a == b
    assert 0.90 <= a[0] <= a[1] <= 1.0


def test_coverage_addendum_matches_results():
    res = json.loads(cb.RESULTS.read_text(encoding="utf-8"))
    assert cb.DOC.read_text(encoding="utf-8") == cb.render(res)
