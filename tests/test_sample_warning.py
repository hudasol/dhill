"""Small Monte Carlo sample counts must be flagged everywhere (known issue 19)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from dhill import cli
from dhill.api.app import Scenario, app
from dhill.envelope import MIN_RELIABLE_SAMPLES, EngineConfig, Envelope, sample_count_warning
from dhill.profiles.loader import load_builtin
from dhill.weather import synthetic_weather

W = synthetic_weather("abu_dhabi", "summer_clear", days=2)


def test_threshold_is_64_and_the_warning_names_the_count():
    assert MIN_RELIABLE_SAMPLES == 64
    assert sample_count_warning(64) is None
    assert sample_count_warning(200) is None
    text = sample_count_warning(16)
    assert text is not None and "16" in text and "64" in text


def test_engine_outputs_carry_the_warning_only_below_the_threshold():
    prof = load_builtin("ugv_medium_inspection")
    low = Envelope(prof, W, EngineConfig(n_mc=16))
    d = low.decide("2026-08-05T00:00", 1.0, look_ahead=False)
    assert d.warnings == [sample_count_warning(16)]
    tl = low.timeline(1.0, "drive", 240.0, last_utc="2026-08-05T08:00")
    assert tl.warnings == [sample_count_warning(16)]
    ok = Envelope(prof, W, EngineConfig(n_mc=64))
    assert ok.decide("2026-08-05T00:00", 1.0, look_ahead=False).warnings == []


def test_cli_warns_on_stderr_below_the_threshold(capsys):
    assert cli.main(["decide", "--at", "2026-08-05T00:00", "--samples", "16", "--json"]) == 0
    err = capsys.readouterr().err
    assert "warning:" in err and "16 Monte Carlo samples" in err


def test_cli_default_is_silent(capsys):
    assert cli.main(["list", "sites"]) == 0
    assert "warning" not in capsys.readouterr().err
    assert cli.main(["decide", "--at", "2026-08-05T00:00", "--json"]) == 0
    assert "warning" not in capsys.readouterr().err


def test_api_defaults_to_64_and_flags_smaller_requests():
    assert Scenario.model_fields["samples"].default == MIN_RELIABLE_SAMPLES
    client = TestClient(app)
    body = {"site": "abu_dhabi", "scenario": "summer_clear", "at": "2026-08-05T00:00"}
    low = client.post("/v1/envelope", json={**body, "samples": 16}).json()
    assert low["mc_samples"] == 16 and low["warnings"] == [sample_count_warning(16)]
    default = client.post("/v1/envelope", json=body).json()
    assert default["mc_samples"] == 64 and default["warnings"] == []
