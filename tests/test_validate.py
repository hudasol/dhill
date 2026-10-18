"""Field day validation, exercised on SYNTHETIC telemetry from known hidden robots."""

from __future__ import annotations

import numpy as np
import pytest

from dhill import cli
from dhill.calibrate import save_telemetry_csv, synthetic_telemetry
from dhill.profiles.loader import load_builtin
from dhill.validate import render_markdown, replay, validate
from dhill.weather import synthetic_weather

W = synthetic_weather("al_ain", "summer_clear", days=2)
BASE = load_builtin("clearpath_jackal")
HOT = BASE.with_overrides(
    {
        "surface.alpha_clean": BASE.value("surface.alpha_clean") * 1.3,
        "coupling.ua_shell_interior_w_k": BASE.value("coupling.ua_shell_interior_w_k") * 0.6,
    }
)


def tel(truth, seed=1):
    return synthetic_telemetry(truth, W, "2026-08-05T02:00", hours=8, seed=seed)


def test_replay_without_noise_reproduces_the_generator():
    t = synthetic_telemetry(BASE, W, "2026-08-05T02:00", hours=4, noise_k=0.0)
    pred = replay(BASE, W, t)[0]
    for col, j in (("t_shell_c", 0), ("t_battery_c", 2)):
        assert np.max(np.abs(pred[:, j] - t.temps_c[col][1:])) < 1e-6


def test_same_robot_passes_with_error_near_sensor_noise():
    rep = validate(BASE, W, tel(BASE), n_mc=16)
    assert rep.passed
    assert all(0.15 < n.rmse_k < 0.5 for n in rep.nodes)  # generator noise is 0.3 K


def test_hotter_robot_fails_on_the_cold_peak_criterion():
    rep = validate(BASE, W, tel(HOT), n_mc=16)
    assert not rep.passed
    assert any(not n.pass_peak and n.peak_margin_k < -2.0 for n in rep.nodes)


def test_criteria_are_the_protocol_values_and_configurable():
    rep = validate(BASE, W, tel(HOT), n_mc=1, rmse_limit_k=50.0, cold_limit_k=50.0)
    assert rep.passed and rep.rmse_limit_k == 50.0
    assert validate(BASE, W, tel(BASE), n_mc=1).rmse_limit_k == 2.0


def test_weather_must_cover_the_record():
    short = synthetic_weather("al_ain", "summer_clear", start="2026-08-05T05:00", days=1)
    with pytest.raises(ValueError):
        validate(BASE, short, tel(BASE), n_mc=1)


def test_report_states_verdict_note_and_rule():
    rep = validate(BASE, W, tel(HOT), n_mc=8, note="SYNTHETIC telemetry")
    md = render_markdown(rep, "x.csv")
    assert (
        "(FAIL)" in md
        and "SYNTHETIC telemetry" in md
        and "must not have been used for calibration" in md
    )


def test_cli_exit_codes_and_report(tmp_path, capsys):
    good, bad = tmp_path / "good.csv", tmp_path / "bad.csv"
    save_telemetry_csv(tel(BASE), good)
    save_telemetry_csv(tel(HOT), bad)
    common = ["--profile", "clearpath_jackal", "--site", "al_ain", "--samples", "64"]
    report = tmp_path / "r.md"
    assert cli.main(["validate", *common, "--telemetry", str(good), "--report", str(report)]) == 0
    assert "(PASS)" in report.read_text(encoding="utf-8")
    assert cli.main(["validate", *common, "--telemetry", str(bad)]) == 3
    assert "overall: FAIL" in capsys.readouterr().out
