"""Hardening of the REST service: bounds, limits, headers, failure modes and the committed OpenAPI file."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dhill.api import app as appmod

client = TestClient(appmod.app)
BASE = {"site": "abu_dhabi", "scenario": "summer_clear", "samples": 8}
ROOT = Path(__file__).parents[1]


@pytest.fixture(autouse=True)
def _reset():
    appmod._hits.clear()
    yield
    appmod._hits.clear()


def test_time_fields_are_validated():
    r = client.post("/v1/envelope", json={**BASE, "at": "tomorrow morning"})
    assert r.status_code == 422
    r = client.post("/v1/envelope", json={**BASE, "start": "2026-13-45; DROP"})
    assert r.status_code == 422


def test_unknown_mode_is_a_client_error_not_a_crash():
    r = client.post("/v1/envelope", json={**BASE, "mode": "fly", "at": "2026-08-05T00:00"})
    assert 400 <= r.status_code < 500


def test_large_body_is_refused():
    big = {**BASE, "profile_inline": {"x": "a" * (appmod.MAX_BODY_BYTES + 10)}}
    r = client.post("/v1/envelope", json=big)
    assert r.status_code == 413


def test_rate_limit_returns_429_with_retry_after(monkeypatch):
    monkeypatch.setattr(appmod, "RATE_PER_MIN", 3)
    codes = [client.get("/v1/version").status_code for _ in range(5)]
    assert codes[:3] == [200, 200, 200] and codes[3:] == [429, 429]
    assert client.get("/v1/version").headers["Retry-After"] == "60"
    assert client.get("/healthz").status_code == 200  # liveness is never limited


def test_rate_limit_window_slides():
    assert not appmod.rate_limited("c", now=0.0)
    old = appmod.RATE_PER_MIN
    try:
        appmod.RATE_PER_MIN = 1
        assert appmod.rate_limited("c", now=1.0)
        assert not appmod.rate_limited("c", now=70.0)
    finally:
        appmod.RATE_PER_MIN = old


def test_busy_server_answers_503(monkeypatch):
    sem = threading.BoundedSemaphore(1)
    sem.acquire()
    monkeypatch.setattr(appmod, "_active", sem)
    r = client.post("/v1/envelope", json={**BASE, "at": "2026-08-05T00:00"})
    assert r.status_code == 503 and r.headers["Retry-After"] == "5"


def test_security_headers():
    page = client.get("/")
    assert page.headers["Content-Security-Policy"].startswith("default-src 'none'")
    assert page.headers["X-Content-Type-Options"] == "nosniff"
    assert page.headers["X-Frame-Options"] == "DENY"
    v = client.get("/v1/version")
    assert v.headers["Cache-Control"] == "no-store"


def test_audit_log_failure_does_not_fail_the_request(monkeypatch):
    monkeypatch.setenv("DHILL_AUDIT_LOG", "/nonexistent-directory/audit.jsonl")
    r = client.post("/v1/envelope", json={**BASE, "at": "2026-08-05T00:00"})
    assert r.status_code == 200


def test_api_key_is_enforced_when_set(monkeypatch):
    monkeypatch.setenv("DHILL_API_KEY", "secret-value")
    assert client.get("/v1/version").status_code == 401
    assert client.get("/v1/version", headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.get("/v1/version", headers={"X-API-Key": "secret-value"}).status_code == 200


def test_committed_openapi_file_is_current():
    committed = json.loads((ROOT / "docs" / "openapi.json").read_text(encoding="utf-8"))
    assert committed == appmod.app.openapi()
