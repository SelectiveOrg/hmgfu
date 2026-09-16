"""Phase 80.2 — nano off the pre-reply path: with nano=False the extraction makes only the router call and is tagged
heuristic+router; the tail's enrich step runs the nano once and keeps the turn's route fields; OFF = today's path."""
from __future__ import annotations

from types import SimpleNamespace

from hmgfu.sensitizer import Sensitizer
from hmgfu.turn_tail import enrich_for_ingest

NANO_JSON = ('{"title": "Amber colour", "summary": "The user prefers amber.", "type": "fact", "keywords": ["amber", "colour"], '
             '"entities": ["amber"], "topics": ["preferences"], "intent": "statement", "conversation_act": "statement", '
             '"emotional_valence": 0.2, "emotional_intensity": 0.1, "importance": 0.6, "confidence": 0.8, "novelty": 0.5, "utility": 0.5}')
ROUTE_JSON = ('{"conversation_act": "statement", "action_requested": false, "requested_tools": [], "freshness": "none", '
              '"needs_memory": true, "runtime_context_keys": [], "runtime_context_sufficient": true, "directive": null}')


def _sens(calls):
    s = Sensitizer(client=None, enabled=True)
    s.enabled = True; s.extract_enabled = True
    s.bind_role_chat(lambda role, messages, **kw: (calls.append(role), {"content": ROUTE_JSON if role == "router" else NANO_JSON})[1])
    return s


def test_nano_false_makes_only_the_router_call_and_keeps_the_route():
    calls = []
    s = _sens(calls)
    out = s.extract("My favourite colour is amber.", route=True, nano=False)
    assert calls == ["router"] and out["extractor"] == "heuristic+router"
    assert out["conversation_act"] == "statement" and out["needs_memory"] is True and out["keywords"]
    assert out["summary"] == "My favourite colour is amber."                          # the user's words, not a paraphrase


def test_nano_true_is_todays_path():
    calls = []
    s = _sens(calls)
    out = s.extract("My favourite colour is amber.", route=True, nano=True)
    assert sorted(calls) == ["nano", "router"] and out["extractor"] == "nano"


def test_tail_enrich_runs_the_nano_once_and_keeps_the_route_fields():
    calls = []
    s = _sens(calls)
    pre = s.extract("My favourite colour is amber.", route=True, nano=False)
    calls.clear()
    engine = SimpleNamespace(settings=SimpleNamespace(get=lambda k: {"nano_in_tail": True}.get(k)), sensitizer=s)
    full = enrich_for_ingest(engine, pre, "My favourite colour is amber.")
    assert calls == ["nano"] and full["extractor"] == "nano" and full["summary"] == "The user prefers amber."
    assert full["conversation_act"] == pre["conversation_act"] and full["needs_memory"] == pre["needs_memory"]
    off = SimpleNamespace(settings=SimpleNamespace(get=lambda k: {"nano_in_tail": False}.get(k)), sensitizer=s)
    assert enrich_for_ingest(off, pre, "x") is pre                                    # OFF: untouched
    assert enrich_for_ingest(engine, {"extractor": "nano", "summary": "s"}, "x")["summary"] == "s"   # already nano: untouched


def test_setting_default_off(tmp_path):
    from hmgfu.settings import Settings
    assert Settings(str(tmp_path / "s.db")).get("nano_in_tail") is False
