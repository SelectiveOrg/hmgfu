"""Phase 73.0 — turn timing and the model-call ledger (instrumentation only; no behaviour change)."""
from __future__ import annotations

import threading

from hmgfu.turn_timing import LedgeredClient, TurnTimer, call_index, calls_since, instrument
from tests.test_v2_agent import make_agent


class _Resp:
    def __init__(self, body):
        self._body = body
    def json(self):
        return self._body
    def raise_for_status(self):
        return None


class _Inner:
    def __init__(self):
        self.posted = []
    def post(self, url, **kw):
        self.posted.append(url)
        return _Resp({"message": {"content": "hi"}, "prompt_eval_count": 7, "eval_count": 5})


def test_ledger_records_kind_model_tokens_and_is_idempotent():
    class Holder:
        pass
    h = Holder(); h._client = _Inner()
    assert instrument(h) is True and instrument(h) is False            # wrapped once
    assert isinstance(h._client, LedgeredClient)
    i0 = call_index()
    h._client.post("http://x/api/chat", json={"model": "gemma4:12b", "messages": []})
    h._client.post("http://x/api/embed", json={"model": "bge-m3", "input": "a"})
    calls = calls_since(i0)
    assert [c["kind"] for c in calls] == ["chat", "embed"]
    assert calls[0]["model"] == "gemma4:12b" and calls[0]["prompt_tokens"] == 7 and calls[0]["eval_tokens"] == 5
    assert calls[0]["thread"] and calls[0]["ok"] is True          # owner token or thread name


def test_turn_timer_stages_and_role_classification(tmp_path):
    eng, _ = make_agent(tmp_path, [{"content": "Hi!", "tool_calls": []}])
    eng.settings.set("chat_model", "gemma4:12b")
    timer = TurnTimer(eng)
    class Holder:
        pass
    h = Holder(); h._client = _Inner(); instrument(h)
    h._client.post("http://x/api/chat", json={"model": "gemma4:12b"})
    h._client.post("http://x/api/chat", json={"model": eng.settings.get("nano_model")})
    h._client.post("http://x/api/embed", json={"model": "bge-m3"})
    timer.mark("retrieve"); timer.mark("chat"); timer.mark_reply(); timer.mark("ingest")
    s = timer.finish()
    assert set(s["stages"]) == {"retrieve", "chat", "ingest"} and s["reply_ms"] is not None
    assert s["calls"] == {"chat": 1, "nano": 1, "embed": 1, "other": 0} and s["model_calls"] == 3
    assert s["tokens"] == {"prompt": 21, "eval": 15} and s["background_calls"] == 0


def test_turn_carries_timings_in_response_and_metadata(tmp_path):
    eng, _ = make_agent(tmp_path, [{"content": "Hello!", "tool_calls": []}])
    eng.settings.set("thinking_mode", "off")
    r = eng.agent_chat("hello there")
    t = r["timings"]
    assert t["total_ms"] >= 0 and t["reply_ms"] is not None and "retrieve" in t["stages"] and "chat" in t["stages"]
    hist = eng.sessions.history(r["session_id"]) if hasattr(eng.sessions, "history") else []
    if hist:
        md = next((m.get("metadata") for m in hist if m.get("role") == "assistant"), None)
        assert md and md.get("timings", {}).get("total_ms") is not None



def test_ingest_reuses_the_turn_extraction_and_embedding(tmp_path):
    """73.2(a′): the user message is extracted and embedded ONCE per turn — at routing — and ingest reuses both."""
    eng, _ = make_agent(tmp_path, [{"content": "Hello!", "tool_calls": []}])
    eng.settings.set("thinking_mode", "off")
    seen = {"extract": [], "embed": []}
    orig_extract, orig_embed = eng.sensitizer.extract, eng.embed
    def spy_extract(text, *a, **k):
        seen["extract"].append(text)
        return orig_extract(text, *a, **k)
    def spy_embed(text):
        seen["embed"].append(text)
        return orig_embed(text)
    eng.sensitizer.extract, eng.embed = spy_extract, spy_embed
    msg = "my favourite planet is Saturn"
    eng.agent_chat(msg)
    # the user text is extracted ONCE (routing) and embedded ONCE (the query) — ingest reused both
    assert seen["extract"].count(msg) == 1 and seen["embed"].count(msg) == 1
    # no text is embedded twice in one turn
    assert len(seen["embed"]) == len(set(seen["embed"]))


def test_stuck_signature_keeps_digits_inside_strings():
    """73.2(e): three different files with the same content are three different calls; a paging loop still collapses."""
    from hmgfu.toolsys import tool_signature
    sigs = {tool_signature("write_file", {"path": f"note{i}.txt", "content": "hmg say-do test"}) for i in (1, 2, 3)}
    assert len(sigs) == 3
    assert tool_signature("list", {"offset": 10}) == tool_signature("list", {"offset": 20})      # numeric args collapse
    assert tool_signature("write_file", {"path": "a.txt", "content": "x"}) == tool_signature("write_file", {"path": "a.txt", "content": "x"})
