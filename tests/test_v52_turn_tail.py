"""Phase 73.2(a) — the post-reply tail: synchronous by default, on a worker with `tail_async`, joined by the next turn."""
from __future__ import annotations

from hmgfu.turn_tail import wait_for_tail
from tests.test_v2_agent import make_agent


def _hist_meta(eng, sid):
    for m in eng.sessions.history(sid):
        if m.get("role") == "assistant":
            return m.get("metadata") or {}
    return {}


def test_sync_tail_is_the_default_and_persists_everything(tmp_path):
    eng, _ = make_agent(tmp_path, [{"content": "Noted.", "tool_calls": []}])
    eng.settings.set("thinking_mode", "off")
    eng.settings.set("tail_async", False)                      # 73.4: default is now True; this test pins the sync path
    r = eng.agent_chat("my favourite planet is Saturn")
    assert r["timings"].get("tail") is None and "ingest" in r["timings"]["stages"]
    meta = _hist_meta(eng, r["session_id"])
    assert meta["timings"]["stages"].get("ingest") is not None
    assert any("saturn" in (p.content or "").lower() for p in eng.graph.points.values())


def test_async_tail_returns_first_then_completes_and_patches_metadata(tmp_path):
    eng, _ = make_agent(tmp_path, [{"content": "Noted.", "tool_calls": []}, {"content": "Yes.", "tool_calls": []}])
    eng.settings.set("thinking_mode", "off")
    eng.settings.set("tail_async", True)
    r = eng.agent_chat("my favourite planet is Saturn")
    assert r["timings"]["tail"] == "pending" and r["grade"] is None
    assert wait_for_tail(eng, timeout=30) in (True, False)
    assert not eng._tail_thread.is_alive()
    meta = _hist_meta(eng, r["session_id"])
    assert meta["timings"]["tail"] == "done" and "ingest" in meta["timings"]["stages"]
    assert any("saturn" in (p.content or "").lower() for p in eng.graph.points.values())
    # the next turn joins the previous tail before it starts (no half-ingested graph)
    r2 = eng.agent_chat("and my favourite moon is Titan", session_id=r["session_id"])
    assert r2["turn_seq"] == 2
    wait_for_tail(eng, timeout=30)
    assert any("titan" in (p.content or "").lower() for p in eng.graph.points.values())


def test_update_metadata_merges(tmp_path):
    eng, _ = make_agent(tmp_path, [{"content": "x", "tool_calls": []}])
    sid = eng.sessions.ensure_session(None)
    eng.sessions.save_message(sid, "assistant", "hi", 1, metadata={"a": 1})
    assert eng.sessions.update_metadata(sid, 1, {"b": 2}) is True
    assert _hist_meta(eng, sid) == {"a": 1, "b": 2}
    assert eng.sessions.update_metadata(sid, 9, {"b": 2}) is False
