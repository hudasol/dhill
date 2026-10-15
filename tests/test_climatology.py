"""Operating calendar tests on recorded Open-Meteo archive responses (Abu Dhabi, 2024)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import numpy as np
import pytest

from dhill import climatology as cl
from dhill.cli import main
from dhill.profiles.loader import load_builtin
from dhill.weather.openmeteo import WeatherUnavailable

DATA = Path(__file__).parent / "data"
WX = json.loads((DATA / "openmeteo_archive_abu_dhabi_2024.json").read_text())
AQ = json.loads((DATA / "openmeteo_archive_air_abu_dhabi_2024.json").read_text())


def _client(fail_first: int = 0, fail_year: str | None = None, calls: list | None = None):
    state = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(str(req.url))
        if fail_year and req.url.params.get("start_date", "").startswith(fail_year):
            return httpx.Response(429, json={"error": True, "reason": "rate limit"})
        state["n"] += 1
        if state["n"] <= fail_first:
            return httpx.Response(429, json={"error": True, "reason": "rate limit"})
        return httpx.Response(200, json=AQ if "air-quality" in req.url.host else WX)

    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.fixture(autouse=True)
def _cache(tmp_path, monkeypatch):
    monkeypatch.setenv("DHILL_CACHE_DIR", str(tmp_path))


@pytest.fixture(scope="module")
def history(tmp_path_factory):
    import os

    os.environ["DHILL_CACHE_DIR"] = str(tmp_path_factory.mktemp("cache"))
    return cl.fetch_history("abu_dhabi", 2024, 2024, client=_client(), sleep=lambda s: None)


def test_history_has_a_full_leap_year_and_names_its_sources(history):
    assert history.n == 366 * 24
    assert history.source == "open-meteo-archive"
    assert any("CAMS" in n for n in history.notes)
    assert np.isfinite(history.t_air_c).all()
    assert history.t_air_c.max() > 40.0  # Abu Dhabi summer


def test_backoff_retries_with_doubling_waits_then_succeeds():
    waits: list[float] = []
    w = cl.fetch_history("abu_dhabi", 2024, 2024, client=_client(fail_first=2), sleep=waits.append)
    assert w.n == 366 * 24
    assert waits[:2] == [2.0, 4.0]


def test_a_year_that_cannot_be_fetched_is_excluded_and_named_never_invented():
    w = cl.fetch_history(
        "abu_dhabi", 2023, 2024, client=_client(fail_year="2023"), sleep=lambda s: None
    )
    assert w.n == 366 * 24  # only 2024
    assert any(n.startswith("2023: weather unavailable") for n in w.notes)


def test_all_years_failing_raises():
    with pytest.raises(WeatherUnavailable):
        cl.fetch_history(
            "abu_dhabi", 2024, 2024, client=_client(fail_year="2024"), sleep=lambda s: None
        )


def test_representative_days_are_in_month_and_ordered_by_daily_maximum(history):
    days = cl.representative_days(history, 7)
    assert 3 <= len(days) <= 5
    dmax = [history.t_air_c[i : i + 24].max() for i in days]
    assert dmax == sorted(dmax)
    months = history.times_utc[days].astype("datetime64[M]").astype(int) % 12 + 1
    assert set(months) == {7}


def test_summer_is_parked_more_than_winter_and_shares_add_up(history):
    prof = load_builtin("clearpath_jackal")
    cal = cl.operating_calendar(prof, {"abu_dhabi": history}, months=(1, 7), n_mc=16)
    jan, jul = cal.by_site("abu_dhabi")
    for r in (jan, jul):
        assert r.go + r.derate + r.park == pytest.approx(1.0)
        assert r.hours_sampled == r.days_sampled * 24
    assert jul.park >= jan.park
    assert jul.air_above_rated >= jan.air_above_rated == 0.0


def test_air_above_rated_matches_direct_count(history):
    prof = load_builtin("clearpath_jackal")
    cal = cl.operating_calendar(prof, {"abu_dhabi": history}, months=(8,), n_mc=8, rated_max_c=40.0)
    in_aug = history.times_utc.astype("datetime64[M]").astype(int) % 12 + 1 == 8
    expected = float(np.mean(history.t_air_c[in_aug] > 40.0))
    assert cal.by_site("abu_dhabi")[0].air_above_rated == pytest.approx(expected)


def test_headline_is_computed_from_rows_not_typed(history):
    prof = load_builtin("clearpath_jackal")
    cal = cl.operating_calendar(prof, {"abu_dhabi": history}, months=(7, 8), n_mc=8)
    h = cl.headline(cal, months=(7, 8))["sites"]["abu_dhabi"]
    rows = cal.by_site("abu_dhabi")
    hours = np.array([r.hours_sampled for r in rows], dtype=float)
    assert h["park"] == pytest.approx(np.average([r.park for r in rows], weights=hours))


def test_exact_parameters_never_restrict_more_than_uncertain_ones(history):
    prof = load_builtin("clearpath_jackal")
    unc = cl.operating_calendar(prof, {"abu_dhabi": history}, months=(7,), n_mc=24)
    exact = cl.operating_calendar(
        prof, {"abu_dhabi": history}, months=(7,), n_mc=24, sigma_scale=0.0
    )
    assert exact.by_site("abu_dhabi")[0].go >= unc.by_site("abu_dhabi")[0].go - 0.05


def test_cli_calendar_prints_the_l0_disclaimer_and_writes_csv(
    history, monkeypatch, capsys, tmp_path
):
    monkeypatch.setattr(cl, "fetch_history", lambda *a, **k: history)
    out = tmp_path / "cal.csv"
    rc = main(["calendar", "--sites", "abu_dhabi", "--samples", "8", "--csv", str(out)])
    assert rc == 0
    text = capsys.readouterr().out
    assert "L0" in text and "not an operating authorisation" in text
    assert out.read_text().splitlines()[0].startswith("site,month")
