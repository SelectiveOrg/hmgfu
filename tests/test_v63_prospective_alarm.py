"""Phase 77.6 — prospective alarm: due time triggers fire WITHOUT a turn (frozen clock), leave a notification that is
delivered exactly once (by the next turn or by the UI ack), never a condition trigger, never twice; the ticker thread
runs single-flight with an injected clock; the setting is bounded."""
from __future__ import annotations

import time

import pytest

from hmgfu.prospective import ProspectiveStore, begin_turn, render_late
from hmgfu.prospective_alarm import AlarmTicker, fire_due, start_ticker, stop_ticker

NOW = "2026-09-05T14:30:00+02:00"


class _Settings:
    def __init__(self, **kw): self.d = {"prospective_enabled": True, "prospective_tick_s": 30, **kw}
    def get(self, k): return self.d.get(k)


class _Runtime:
    def __init__(self, now): self.now_local = now


class _Engine:
    def __init__(self, tmp_path, name="p.db", **kw):
        self.prospective = ProspectiveStore(str(tmp_path / name))
        self.settings = _Settings(**kw)
        self.events = []
    def _emit(self, ev): self.events.append(ev)


def _set(e, text, turn, now=NOW):
    return begin_turn(e, "s", text, _Runtime(now), turn)


def test_fire_due_fires_exactly_what_is_due_never_twice_never_a_condition(tmp_path):
    e = _Engine(tmp_path)
    _set(e, "remind me in 5 minutes to stretch", 1)
    _set(e, "remind me in 60 minutes to call Rui", 2)
    _set(e, "remind me to send the invoice when Nelson replies", 3)
    assert len(e.prospective.pending()) == 3
    assert fire_due(e, "2026-09-05T14:34:59+02:00") == []                             # not yet
    fired = fire_due(e, "2026-09-05T14:35:00+02:00")
    assert [f["text"] for f in fired] == ["stretch"] and fired[0]["fired_turn"] is None   # no turn fired it
    assert fire_due(e, "2026-09-05T14:36:00+02:00") == []                              # never twice
    assert [t["text"] for t in e.prospective.pending()] == ["call Rui", "send the invoice"]  # the condition one waits for a message
    fired = fire_due(e, "2026-09-05T16:00:00+02:00")
    assert [f["text"] for f in fired] == ["call Rui"]
    assert [n["text"] for n in e.prospective.undelivered()] == ["stretch", "call Rui"]
    assert all(n["fired_by"] == "ticker" for n in e.prospective.undelivered())
    e2 = _Engine(tmp_path, "off.db", prospective_enabled=False)
    _set(e2, "remind me in 5 minutes to stretch", 1)
    assert fire_due(e2, "2026-09-05T16:00:00+02:00") == []                             # setting off: nothing fires


def test_next_turn_delivers_once_and_ui_ack_delivers_the_rest(tmp_path):
    e = _Engine(tmp_path)
    _set(e, "remind me in 5 minutes to stretch", 1)
    fire_due(e, "2026-09-05T14:40:00+02:00")
    block = _set(e, "hello again", 2, now="2026-09-05T14:41:00+02:00")
    assert "came DUE while no conversation was open" in block and "stretch" in block
    assert e.events[-1]["type"] == "prospective_fired" and e.events[-1]["by"] == "ticker"
    assert e.prospective.undelivered() == [] and e.prospective.notifications()[0]["delivered_by"] == "turn:2"
    assert _set(e, "and now?", 3, now="2026-09-05T14:42:00+02:00") == ""                # delivered once, not again
    _set(e, "remind me in 5 minutes to breathe", 4)
    fire_due(e, "2026-09-05T14:50:00+02:00")
    ids = [n["id"] for n in e.prospective.undelivered()]
    assert e.prospective.mark_delivered(ids, "ui") == 1 and e.prospective.mark_delivered(ids, "ui") == 0
    assert _set(e, "anything?", 5, now="2026-09-05T14:51:00+02:00") == ""                # acked in the UI → the turn stays silent
    assert "breathe" in render_late(e.prospective.notifications(1))


def test_turn_fire_still_wins_when_the_turn_arrives_first(tmp_path):
    e = _Engine(tmp_path)
    _set(e, "remind me in 5 minutes to stretch", 1)
    block = _set(e, "hi", 2, now="2026-09-05T14:40:00+02:00")                          # the turn fires it (75.2 path)
    assert "DUE NOW" in block and e.prospective.pending() == [] and e.prospective.undelivered() == []   # no notification for a turn fire
    assert fire_due(e, "2026-09-05T14:41:00+02:00") == []                              # the ticker finds nothing left


def test_ticker_thread_single_flight_with_injected_clock(tmp_path):
    e = _Engine(tmp_path, prospective_tick_s=0.05)
    _set(e, "remind me in 5 minutes to stretch", 1)
    clock = {"now": "2026-09-05T14:31:00+02:00"}
    t = AlarmTicker(e, clock=lambda: clock["now"]).start()
    assert t.start() is t and t.alive                                                  # single-flight: the same thread
    time.sleep(0.3)
    assert t.fired == 0 and t.ticks >= 2                                               # ticking, nothing due
    clock["now"] = "2026-09-05T14:36:00+02:00"
    deadline = time.time() + 3
    while t.fired == 0 and time.time() < deadline:
        time.sleep(0.05)
    assert t.fired == 1 and [n["text"] for n in e.prospective.undelivered()] == ["stretch"]
    t.stop(); assert not t.alive
    e.settings.d["prospective_tick_s"] = 0                                             # 0 = idle: the loop keeps waiting, fires nothing
    _set(e, "remind me in 1 minutes to blink", 2, now="2026-09-05T14:36:00+02:00")
    t2 = start_ticker(e); assert start_ticker(e) is t2
    time.sleep(0.2); assert t2.fired == 0
    stop_ticker(e); assert not t2.alive


def test_setting_is_bounded(tmp_path):
    from hmgfu.settings import Settings
    s = Settings(str(tmp_path / "s.db"))
    assert s.get("prospective_tick_s") == 30
    s.set("prospective_tick_s", 0); assert s.get("prospective_tick_s") == 0
    with pytest.raises(ValueError):
        s.set("prospective_tick_s", 4000)


def test_api_routes_list_and_ack_notifications(tmp_path):
    from types import SimpleNamespace
    from fastapi.testclient import TestClient
    from hmgfu import runtime
    from hmgfu.api import app
    e = _Engine(tmp_path, "api.db")
    _set(e, "remind me in 5 minutes to stretch", 1)
    fire_due(e, "2026-09-05T14:40:00+02:00")
    saved = runtime._engine
    runtime.set_engine(SimpleNamespace(prospective=e.prospective, settings=e.settings, _alarm_ticker=None))
    try:
        c = TestClient(app)
        r = c.get("/api/prospective/notifications").json()
        assert len(r["undelivered"]) == 1 and r["notifications"][0]["text"] == "stretch" and r["ticker"]["alive"] is False
        assert c.post("/api/prospective/notifications/ack", json={"ids": [r["undelivered"][0]["id"]]}).json() == {"ok": True, "delivered": 1}
        assert c.get("/api/prospective/notifications").json()["undelivered"] == []
    finally:
        runtime.set_engine(saved)
