"""The route result tables in docs/route-simulation.md must equal their rendering from the output files."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "examples"))
rd = pytest.importorskip("route_demo")


def test_summary_parser_reads_every_row():
    rows = rd.parse_summary(rd.OUT.read_text(encoding="utf-8"))
    assert len(rows) == len(rd.TRUTH) * len(rd.CASES) * 3
    for v in rows.values():
        assert 0.0 <= v["completion"] <= 100.0 and v["planned"] <= v["n"]


def test_route_doc_tables_match_outputs():
    text = rd.DOC.read_text(encoding="utf-8")
    block = text[text.index(rd.START) + len(rd.START) : text.index(rd.END)].strip()
    expected = rd.results_markdown(
        rd.OUT.read_text(encoding="utf-8"), rd.BEFORE_OUT.read_text(encoding="utf-8")
    )
    assert block == expected.strip()
