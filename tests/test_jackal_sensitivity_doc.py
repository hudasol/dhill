"""The headline and tables of docs/jackal-sensitivity.md must match examples/jackal_sensitivity.csv."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "examples"))
js = pytest.importorskip("jackal_sensitivity")


def _csv_rows() -> list[dict]:
    with open(js.OUT_CSV, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        for k in ("value", "share_go", "die_q95_peak_c"):
            r[k] = float(r[k])
    return rows


def test_headline_matches_csv():
    rows = _csv_rows()
    assert [r["parameter"] for r in rows[::3]] == js.KEYS
    sp = js.spans(rows)
    top = max(sp, key=lambda k: sp[k][0])
    doc = js.OUT_MD.read_text(encoding="utf-8")
    headline = next(line for line in doc.splitlines() if line.startswith("**Headline:**"))
    assert (
        f"`{top}` moves the calendar GO share the most, by {sp[top][0]:.1f} percentage" in headline
    )


def test_doc_tables_match_csv():
    rows = _csv_rows()
    doc_lines = [line.rstrip() for line in js.OUT_MD.read_text(encoding="utf-8").splitlines()]
    hot = next(line for line in doc_lines if "hottest July day" in line)
    hot_day = hot.split("13:00 local on ")[1].split(",")[0]
    expected = [line.rstrip() for line in js.render(rows, hot_day).splitlines()]
    tables = [line for line in expected if line.startswith("| ")]
    assert tables and all(line in doc_lines for line in tables)
