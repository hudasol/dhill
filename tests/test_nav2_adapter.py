"""Nav2 adapter mapping, chatter filter and the stale decision rule (no ROS needed)."""

from __future__ import annotations

import httpx
import pytest

from dhill.ros2_bridge.nav2_adapter import CommandFilter, DecisionClient, decision_to_command


def test_mapping_of_the_three_decisions():
    assert decision_to_command("GO", 1.0).kind == "run"
    d = decision_to_command("DERATE", 0.654)
    assert d.kind == "limit" and d.speed_limit_percent == 65.4
    assert decision_to_command("DERATE", 0.02).speed_limit_percent == 10.0
    assert decision_to_command("DERATE", 0.999).speed_limit_percent == 99.0
    assert decision_to_command("PARK", 0.0).kind == "park"
    with pytest.raises(ValueError):
        decision_to_command("RUN", 1.0)


def test_filter_suppresses_small_changes_but_not_kind_changes():
    f = CommandFilter(min_change_percent=5.0)
    assert f.update(decision_to_command("DERATE", 0.60)) is not None
    assert f.update(decision_to_command("DERATE", 0.62)) is None
    assert f.update(decision_to_command("DERATE", 0.70)) is not None
    assert f.update(decision_to_command("PARK", 0.0)) is not None
    assert f.update(decision_to_command("PARK", 0.0)) is None


def _client(handler, clock):
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return DecisionClient(
        "http://dhill.test", "ugv_medium_inspection", "al_ain", client=http, clock=clock
    )


def test_client_reads_a_decision_and_fails_safe_when_stale():
    state = {"up": True}
    now = {"t": 0.0}

    def handler(request: httpx.Request) -> httpx.Response:
        if not state["up"]:
            return httpx.Response(503)
        return httpx.Response(
            200,
            json={
                "action": "DERATE",
                "scale": 0.5,
                "evidence_level": "L0",
                "reasons": ["battery binds"],
            },
        )

    c = _client(handler, lambda: now["t"])
    cmd = c.current()
    assert cmd.kind == "limit" and cmd.speed_limit_percent == 50.0 and cmd.evidence_level == "L0"
    state["up"] = False
    now["t"] = 600.0
    with pytest.raises(httpx.HTTPError):  # recent decision: the caller keeps the last command
        c.current()
    now["t"] = 4000.0
    stale = c.current()
    assert stale.kind == "park" and stale.fail_safe


def test_client_that_never_succeeded_parks():
    c = _client(lambda r: httpx.Response(500), lambda: 0.0)
    assert c.current().kind == "park"
