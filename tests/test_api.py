from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from dhill.api.app import app

client = TestClient(app)
BASE = {"site": "abu_dhabi", "scenario": "summer_clear", "samples": 16}


def test_health_and_listings():
    assert client.get("/healthz").json() == {"status": "ok"}
    assert any(p["id"] == "ugv_medium_inspection" for p in client.get("/v1/profiles").json())
    assert len(client.get("/v1/sites").json()) >= 10
    assert "heatwave" in client.get("/v1/scenarios").json()
    assert "Dhill" in client.get("/").text


def test_envelope_decision():
    r = client.post("/v1/envelope", json={**BASE, "at": "2026-08-05T00:00"})
    assert r.status_code == 200
    body = r.json()
    assert body["action"] in {"GO", "DERATE", "PARK"} and body["evidence_level"] == "L0"


def test_forecast_and_schedule():
    r = client.post("/v1/forecast", json={**BASE, "step_min": 120})
    assert r.status_code == 200 and len(r.json()["slots"]) >= 8
    r = client.post(
        "/v1/schedule",
        json={
            **BASE,
            "robots": ["ugv_medium_inspection", "sidewalk_delivery_robot"],
            "demand_h": 6,
        },
    )
    assert r.status_code == 200
    assert r.json()["dhill"]["completed_work_h"] > 0


@pytest.mark.parametrize(
    "payload,code",
    [
        ({"profile": "nope"}, 404),
        ({"site": "mars"}, 404),
        ({"scenario": "blizzard"}, 404),
        ({"samples": 100000}, 422),
        ({"days": 99}, 422),
        ({"duration_h": 0.0}, 422),
        ({"profile_inline": {"id": "x"}}, 422),
    ],
)
def test_bad_inputs_rejected(payload, code):
    assert client.post("/v1/envelope", json={**BASE, **payload}).status_code == code


def test_api_key_enforced(monkeypatch):
    monkeypatch.setenv("DHILL_API_KEY", "s3cret")
    assert client.get("/v1/profiles").status_code == 401
    assert client.get("/v1/profiles", headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.get("/v1/profiles", headers={"X-API-Key": "s3cret"}).status_code == 200
    assert client.get("/healthz").status_code == 200


def test_audit_log_written(monkeypatch, tmp_path):
    log = tmp_path / "audit.jsonl"
    monkeypatch.setenv("DHILL_AUDIT_LOG", str(log))
    client.post("/v1/envelope", json={**BASE, "at": "2026-08-05T00:00"})
    rec = json.loads(log.read_text().splitlines()[0])
    assert rec["event"] == "envelope" and rec["profile"] == "ugv_medium_inspection"


def test_path_traversal_not_possible():
    r = client.post("/v1/envelope", json={**BASE, "profile": "../../etc/passwd"})
    assert r.status_code == 404
