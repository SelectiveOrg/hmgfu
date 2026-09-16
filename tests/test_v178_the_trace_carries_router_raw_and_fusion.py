"""95.10 — the same execution can be followed from the raw router and the nano/router fusion onward.

Method §6 step 2 asks for the first failing link on ONE execution: router raw → nano/router fusion →
protocol → write → validity → retrieval → context → reply → reinforcement. The trace (94.8) carries
every stage from the protocol onward and none before it: `merge_route` folds the router's
classification into the nano extraction and `_sanitise` then rebuilds the dict from a fixed key set,
so neither the raw classification nor the pre-fusion snapshot survives to any emitter.

The change is additive and visible: `merge_route(raw, future, on_fused=None)` hands the pre-fusion
snapshot, the router's raw result and the fused dict to an optional callback; the sensitizer stores
them as `_last_route_trace`; the engine emits `router_raw` and `fusion` events right after retrieval
and clears the slot. Test instance only in effect — the events are trace, not behaviour.
"""
from __future__ import annotations

from concurrent.futures import Future

import pytest

from hmgfu.turn_router import merge_route
from tests.test_v2_agent import make_agent


def _future(value):
    f = Future()
    f.set_result(value)
    return f


def test_merge_route_hands_both_stages_to_the_callback():
    seen = {}
    raw = {"keywords": ["acme"], "intent": "statement", "utility": 0.5}
    router = {"conversation_act": "instruction", "intent": "task", "memory_update": {"ambiguity": "none"}}
    fused = merge_route(dict(raw), _future(router), on_fused=lambda nano, rr, out: seen.update(
        nano=nano, router=rr, fused=out))
    assert seen["nano"] == raw                                 # the snapshot BEFORE the fold
    assert seen["router"] == router                            # the router's own words
    assert seen["fused"] is fused and fused["intent"] == "task"  # what the protocol will see


def test_merge_route_without_a_callback_is_unchanged():
    raw = {"keywords": ["acme"], "intent": "statement"}
    out = merge_route(dict(raw), _future({"intent": "task"}))
    assert out["intent"] == "task" and out["keywords"] == ["acme"]


def test_a_failed_router_still_reports_the_snapshot_and_no_router():
    seen = {}
    f = Future(); f.set_exception(RuntimeError("router down"))
    merge_route({"intent": "statement"}, f, on_fused=lambda nano, rr, out: seen.update(nano=nano, router=rr))
    assert seen["nano"] == {"intent": "statement"} and seen["router"] is None


def test_the_engine_emits_router_raw_and_fusion_when_the_sensitizer_recorded_them(tmp_path):
    engine, _ = make_agent(tmp_path, [{"content": "ok", "tool_calls": []}])
    events = []
    real = engine.sensitizer.extract

    def extract(text, *a, **k):
        out = real(text, *a, **k)
        if k.get("route"):                 # only the QUERY extraction routes; the tail's ingest does not
            engine.sensitizer._last_route_trace = {"nano": {"intent": "statement"},
                                                   "router": {"intent": "task"},
                                                   "fused": {"intent": "task"}}
        return out

    engine.sensitizer.extract = extract
    engine.agent_chat("write notes.md containing HELLO", session_id=None, emit=events.append)
    kinds = [e.get("type") for e in events]
    assert "router_raw" in kinds and "fusion" in kinds, kinds
    rr = next(e for e in events if e["type"] == "router_raw")
    assert rr["router"] == {"intent": "task"} and rr["nano"] == {"intent": "statement"}
    assert engine.sensitizer._last_route_trace is None        # one turn, one trace


def test_no_routing_no_events(tmp_path):
    """NEGATIVE — the fake sensitizer never routes, so nothing is emitted for these stages."""
    engine, _ = make_agent(tmp_path, [{"content": "ok", "tool_calls": []}])
    events = []
    engine.agent_chat("hello there", session_id=None, emit=events.append)
    assert not [e for e in events if e.get("type") in ("router_raw", "fusion")]
