"""The addendum after the Jackal profile fix must equal what the code renders from both JSON files."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "examples"))
pa = pytest.importorskip("prereg_eval_fixed_profile")


def test_evaluation_profile_is_not_the_jackal():
    # the preregistered design uses the medium UGV only; the Jackal fix cannot change it
    assert pa.pe.BASE.id == "ugv_medium_inspection"


@pytest.mark.skipif(not pa.AFTER.exists(), reason="rerun not done")
def test_addendum_matches_both_json_files():
    before = json.loads(pa.BEFORE.read_text(encoding="utf-8"))
    after = json.loads(pa.AFTER.read_text(encoding="utf-8"))
    again = pa.pe.analyse(after["raw"])
    assert json.loads(json.dumps(again)) == {k: after[k] for k in again}
    assert pa.DOC.read_text(encoding="utf-8") == pa.render(before, after)
