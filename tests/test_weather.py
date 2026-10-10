from __future__ import annotations

import json
from pathlib import Path

import httpx
import numpy as np
import pytest

from dhill.sites import SITES, get_site
from dhill.weather import (
    Weather,
    WeatherUnavailable,
    fetch_weather,
    load_weather_csv,
    openmeteo,
    synthetic_weather,
)

DATA = Path(__file__).parent / "data"


def test_sites_are_in_the_uae_bounding_box():
    for s in SITES.values():
        assert 22.0 < s.lat < 26.5 and 51.0 < s.lon < 56.5
    with pytest.raises(KeyError):
        get_site("atlantis")


@pytest.mark.parametrize(
    "scenario",
    [
        "summer_clear",
        "heatwave",
        "dust_event",
        "shamal_day",
        "rain_event",
        "winter_mild",
        "humid_coastal",
    ],
)
def test_synthetic_scenarios_are_physical(scenario):
    w = synthetic_weather("abu_dhabi", scenario, days=2)
    f = w.to_forcing(600)
    assert np.all(f.dew_c <= f.t_air_k - 273.15 + 1e-9)
    assert f.ghi.max() > 300 and f.ghi.min() == 0.0
    assert np.all(f.wind10_ms >= 0) and np.all(f.pm10 >= 0)


def test_heatwave_hotter_than_summer_and_dust_event_has_surge():
    a = synthetic_weather("sweihan", "summer_clear")
    b = synthetic_weather("sweihan", "heatwave")
    assert b.t_air_c.max() > a.t_air_c.max() + 3
    d = synthetic_weather("sweihan", "dust_event")
    assert d.pm10_ugm3.max() > 1000


def test_synthetic_is_deterministic():
    a = synthetic_weather("dubai", "summer_clear", seed=3)
    b = synthetic_weather("dubai", "summer_clear", seed=3)
    assert np.array_equal(a.t_air_c, b.t_air_c)


def test_weather_validation():
    t = np.array(["2026-01-01T00:00", "2026-01-01T01:00"], dtype="datetime64[s]")
    ok = dict(
        times_utc=t,
        t_air_c=[1, 2],
        dew_c=[0, 0],
        wind10_ms=[1, 1],
        pm10_ugm3=[1, 1],
        precip_mm_h=[0, 0],
        lat=24,
        lon=54,
    )
    Weather(**ok)
    with pytest.raises(ValueError):
        Weather(**{**ok, "t_air_c": [1, 2, 3]})
    with pytest.raises(ValueError):
        Weather(**{**ok, "times_utc": t[::-1]})


def test_cloud_scaling_reduces_irradiance():
    clear = synthetic_weather("abu_dhabi", "summer_clear").to_forcing(600)
    rain = synthetic_weather("abu_dhabi", "rain_event").to_forcing(600)
    assert rain.ghi.max() < 0.75 * clear.ghi.max()


def test_csv_roundtrip(tmp_path):
    w = synthetic_weather("abu_dhabi", "summer_clear", days=1)
    p = tmp_path / "w.csv"
    lines = ["time_utc,t_air_c,dew_c,wind10_ms,pm10_ugm3,precip_mm_h"]
    for i in range(w.n):
        lines.append(
            f"{w.times_utc[i]},{w.t_air_c[i]},{w.dew_c[i]},{w.wind10_ms[i]},{w.pm10_ugm3[i]},{w.precip_mm_h[i]}"
        )
    p.write_text("\n".join(lines))
    r = load_weather_csv(p, 24.45, 54.38)
    assert r.n == w.n and r.t_air_c[5] == pytest.approx(w.t_air_c[5])
    p.write_text("time_utc,t_air_c\n2026-01-01T00:00,1\n")
    with pytest.raises(ValueError):
        load_weather_csv(p, 24.45, 54.38)


def _mock_client() -> httpx.Client:
    fc = json.loads((DATA / "openmeteo_forecast_abu_dhabi.json").read_text())
    aq = json.loads((DATA / "openmeteo_air_abu_dhabi.json").read_text())

    def handler(request: httpx.Request) -> httpx.Response:
        if "air-quality" in str(request.url):
            return httpx.Response(200, json=aq)
        return httpx.Response(200, json=fc)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_open_meteo_parsing_with_recorded_response(tmp_path, monkeypatch):
    monkeypatch.setenv("DHILL_CACHE_DIR", str(tmp_path))
    w = fetch_weather("abu_dhabi", 2, client=_mock_client())
    assert w.source == "open-meteo" and w.n == 48
    assert w.t_air_c.min() > 15 and w.t_air_c.max() < 50
    assert w.ghi_wm2.max() > 500
    assert np.all(w.pm10_ugm3 > 0)
    f = w.to_forcing(600)
    assert f.n > 100


def test_open_meteo_failure_is_explicit(tmp_path, monkeypatch):
    monkeypatch.setenv("DHILL_CACHE_DIR", str(tmp_path))
    client = httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(429, json={"error": True}))
    )
    with pytest.raises(WeatherUnavailable):
        fetch_weather("abu_dhabi", 2, client=client)


def test_cache_used_second_time(tmp_path, monkeypatch):
    monkeypatch.setenv("DHILL_CACHE_DIR", str(tmp_path))
    calls = {"n": 0}
    fc = json.loads((DATA / "openmeteo_forecast_abu_dhabi.json").read_text())
    aq = json.loads((DATA / "openmeteo_air_abu_dhabi.json").read_text())

    def handler(request):
        calls["n"] += 1
        return httpx.Response(200, json=aq if "air-quality" in str(request.url) else fc)

    c = httpx.Client(transport=httpx.MockTransport(handler))
    fetch_weather("abu_dhabi", 2, client=c)
    n1 = calls["n"]
    fetch_weather("abu_dhabi", 2, client=c)
    assert calls["n"] == n1
    assert openmeteo.CACHE_TTL_S > 0
