"""Operating calendar: download cache, day selection, envelope runs and outputs.

The fixture files under tests/data/climatology are real Open-Meteo responses (archive and
CAMS air quality) for Abu Dhabi, 1 to 6 July 2021 and 2024, trimmed to those days.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import httpx
import numpy as np
import pytest

from dhill import climatology as clim
from dhill.cli import main
from dhill.envelope import EngineConfig
from dhill.profiles.loader import load_profile
from dhill.weather.openmeteo import WeatherUnavailable

DATA = Path(__file__).parent / "data" / "climatology"
ROOT = Path(__file__).parents[1]
YEARS = (2021, 2024)


@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.setenv("DHILL_CACHE_DIR", str(tmp_path))
    d = tmp_path / "climatology"
    d.mkdir()
    for f in DATA.glob("*.json"):
        shutil.copy(f, d / f.name)
    return d


@pytest.fixture
def record(cache):
    return clim.load_site_record("abu_dhabi", YEARS, offline=True)


def test_backoff_on_429_then_cache(tmp_path):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429, json={"error": True, "reason": "too many requests"})
        return httpx.Response(200, json={"hourly": {"time": []}})

    waits = []
    path = tmp_path / "x.json"
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        data = clim.get_json_cached(
            "https://example.test", {}, path, client, base_wait_s=1.0, sleep=waits.append
        )
    assert data == {"hourly": {"time": []}}
    assert waits == [1.0, 2.0]  # exponential
    assert path.exists() and not path.with_suffix(".part").exists()
    # second call is served from disk without touching the network
    assert clim.get_json_cached("https://example.test", {}, path, offline=True) == data


def test_gives_up_without_writing_cache(tmp_path):
    path = tmp_path / "x.json"
    with (
        httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(429))) as client,
        pytest.raises(WeatherUnavailable),
    ):
        clim.get_json_cached(
            "https://example.test", {}, path, client, max_tries=3, sleep=lambda s: None
        )
    assert not path.exists()


def test_missing_year_is_a_gap_not_filled(cache):
    rec = clim.load_site_record("abu_dhabi", (2021, 2023, 2024), offline=True)
    assert any("2023" in g and "weather not available" in g for g in rec.gaps)
    years = set(rec.times_utc.astype("datetime64[Y]").astype(int) + 1970)
    assert years == {2021, 2024}


def test_record_is_real_and_pm10_only_from_cams(record):
    assert record.times_utc.size == 2 * 6 * 24
    pre = record.times_utc < np.datetime64("2022-01-01")
    assert np.isnan(record.pm10_ugm3[pre]).all()  # no PM10 requested or invented before 2022
    assert np.isfinite(record.pm10_ugm3[~pre]).mean() > 0.9
    assert record.t_air_c.max() > 35.0  # a July record, sanity only


def test_select_days_quantiles_and_weights():
    days = np.arange("2020-07-01", "2020-07-11", dtype="datetime64[D]")
    tmax = np.array([40, 41, 39, 45, 42, 38, 44, 43, 46, 37], dtype=float)
    sel = clim.select_days(days, tmax, 7)
    labels = [s[0] for s in sel]
    assert labels == ["p10", "p30", "p50", "p70", "p90", "mildest", "hottest"]
    assert sum(s[3] for s in sel) == pytest.approx(1.0)
    by = {s[0]: s[2] for s in sel}
    assert by["mildest"] == 37 and by["hottest"] == 46
    assert by["p10"] <= by["p50"] <= by["p90"]
    assert clim.select_days(days, tmax, 1) == []


def test_daily_max_uses_complete_local_days(record):
    days, tmax = clim.daily_max_by_local_day(record)
    # 6 UTC days per year shift into 5 complete local days (UTC+4)
    assert days.size == 2 * 5
    assert np.all(tmax > 30.0)


def test_day_weather_flags_pm10_fill(record):
    days, _ = clim.daily_max_by_local_day(record)
    med = clim.pm10_hourly_median(record)
    w21, fill21 = clim.day_weather(record, days[1], med)
    w24, fill24 = clim.day_weather(record, days[-2], med)
    assert fill21 == 1.0 and fill24 == 0.0
    assert w21.source == "open-meteo-archive"
    with pytest.raises(WeatherUnavailable):
        clim.day_weather(record, np.datetime64("2019-01-05"), med)


def test_run_site_and_summary(record):
    prof = load_profile("clearpath_jackal")
    rows = clim.run_site(prof, record, months=[7], cfg=EngineConfig(n_mc=16))
    assert len(rows) == 7 * 24
    assert {r.action for r in rows} <= set(clim.ACTIONS)
    for r in rows:
        assert (r.action == "GO") == (r.scale >= 0.999)
        assert (r.action == "PARK") == (r.scale == 0.0)
    above = {"abu_dhabi": clim.hours_above(record, 45.0)}
    month = clim.summarise([r.__dict__ for r in rows], above, 45.0)
    assert len(month) == 1
    m = month[0]
    assert m["share_go"] + m["share_derate"] + m["share_park"] == pytest.approx(1.0, abs=1e-3)
    assert m["record_hours"] == 2 * 6 * 24  # every July hour of the record
    head = clim.headline(month)
    assert head["share_go"] == pytest.approx(m["share_go"])
    assert 0.0 <= head["share_air_above_rated"] <= 1.0


def test_hours_above_counts_every_record_hour(record):
    counts = clim.hours_above(record, 45.0)
    n_above, n = counts[7]
    assert n == int(np.isfinite(record.t_air_c).sum())
    assert n_above == int(np.sum(record.t_air_c > 45.0))
    assert counts[1] == (0, 0)


def test_cli_calendar_offline(cache, tmp_path, capsys):
    out = tmp_path / "month.csv"
    hours = tmp_path / "hours.csv"
    code = main(
        [
            "calendar",
            "--sites",
            "abu_dhabi",
            "--years",
            "2021-2024",
            "--samples",
            "8",
            "--offline",
            "--out",
            str(out),
            "--hours-csv",
            str(hours),
        ]
    )
    assert code == 0
    text = capsys.readouterr().out
    assert "[L0]" in text and "gap: abu_dhabi 2022" in text
    month = clim.read_month_csv(out)
    assert [r["month"] for r in month] == [7]
    assert len(clim.read_hour_csv(hours)) == 7 * 24


def test_cli_calendar_no_data_reports_gap(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DHILL_CACHE_DIR", str(tmp_path))
    assert main(["calendar", "--sites", "liwa", "--years", "2020", "--offline"]) == 2
    assert "nothing computed" in capsys.readouterr().err


def test_published_headline_is_computed_from_the_csv():
    """The headline in docs/operating-calendar.md must equal the code's result on the CSV."""
    csv_path = ROOT / "examples" / "operating_calendar_clearpath_jackal.csv"
    doc = ROOT / "docs" / "operating-calendar.md"
    if not csv_path.exists() or not doc.exists():
        pytest.skip("calendar outputs not generated")
    head = clim.headline(clim.read_month_csv(csv_path))
    text = doc.read_text(encoding="utf-8")
    for key in ("share_go", "share_derate", "share_park", "share_air_above_rated"):
        assert f"{100 * head[key]:.1f} %" in text, key
    meta = json.loads((ROOT / "examples" / "operating_calendar_meta.json").read_text())
    assert meta["profile_evidence_level"] == "L0"


def test_published_before_after_table_is_computed():
    """The before and after table in docs/operating-calendar.md equals the generator's output."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "gen_cal", ROOT / "scripts" / "gen_operating_calendar.py"
    )
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    if not gen.MONTH_CSV.exists() or not gen.BEFORE_CSV.exists():
        pytest.skip("calendar outputs not generated")
    text = (ROOT / "docs" / "operating-calendar.md").read_text(encoding="utf-8")
    for line in gen.before_after(clim.read_month_csv(gen.MONTH_CSV)):
        assert line in text, line
