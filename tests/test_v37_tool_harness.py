"""Phase 66 — harnessed tool use: grounding gate, argument deixis, tool rules, unknown-tool reroute,
side-effect guard, question caps. Deterministic (fake provider + fake embedder)."""

from __future__ import annotations

import json
from types import SimpleNamespace

from hmgfu.deixis import complete_query
from hmgfu.directives import DirectiveStore, detect_tool_rule, resolve_tool_name
from hmgfu.grounding import ungrounded_claims
from hmgfu.speech_act import requests_side_effect
from tests.test_v2_agent import make_agent


def test_ungrounded_numbers_and_urls_are_detected():
    ev = ["Mostly sunny. Patchy fog. Hot with highs near 90.", "Your favorite drink is ginger tea"]
    assert ungrounded_claims("It is 26°C with clear skies in Valencia.", ev) == ["26°C"]   # 69.3: unit travels
    assert ungrounded_claims("Highs near 90 today.", ev) == []
    assert ungrounded_claims("See http://198.51.100.7/x", ev) == ["http://198.51.100.7/x"]
    assert ungrounded_claims("Here are 3 things: first, second, third.", ev) == []   # counting numbers pass


def test_deixis_completes_place_and_date_only_when_missing():
    rt = SimpleNamespace(local_date="2026-09-04")
    facts = [{"key": "identity.location", "value": "Valencia City, Spain"}]
    q, added = complete_query("tell me whats todays weather", "tell me whats todays weather", rt, facts)
    assert q == "tell me whats todays weather Valencia City 2026-09-04" and added == ["location", "date"]
    q, added = complete_query("weather in Aveiro", "whats the weather in Aveiro today", rt, facts)
    assert "Valencia" not in q and added == ["date"]                    # the user named a place
    q, added = complete_query("python asyncio tutorial", "find a python asyncio tutorial", rt, facts)
    assert added == []                                                   # not local, not time-bound


def test_tool_rule_detection_resolution_and_stop():
    det = detect_tool_rule("for now on always use brave search to valencia weather search, or for todays weather request")
    assert det["kind"] == "tool_rule:brave_search" and "weather" in det["value"]
    assert detect_tool_rule("from now  on please use brave search for getting weather")["kind"] == "tool_rule:brave_search"
    assert detect_tool_rule("use brave search for searching in internet") is None      # one-off, not standing
    assert detect_tool_rule("stop using brave search") == {"kind": "tool_rule:brave_search", "clear": True}
    assert resolve_tool_name("brave_search", ["brave_web_search", "bash", "memory_search"]) == "brave_web_search"


def test_tool_rule_store_render_and_match(tmp_path):
    ds = DirectiveStore(str(tmp_path / "d.db"))
    assert ds.apply("from now on always use brave search for weather", "user_explicit")["kind"] == "tool_rule:brave_search"
    assert ds.apply("from now on always use brave search for weather", "user_explicit") is None   # restatement
    block = ds.render_block(first_turn=False, suppress_generated=True, tool_names=["brave_web_search", "bash"])
    assert "STANDING TOOL RULE" in block and "`brave_web_search`" in block and "brave_search'" not in block
    assert ds.tool_rules_for("tell me whats todays weather", ["brave_web_search", "bash"]) == ["brave_web_search"]
    assert ds.tool_rules_for("what is my name?", ["brave_web_search"]) == []
    assert ds.enforce("hi") == "hi"                                                           # no text effect
    assert ds.apply("stop using brave search", "user_explicit") == {"kind": "tool_rule:brave_search", "cleared": True}
    assert ds.active() == []


def test_tool_rule_memory_survives_action_turn_and_is_forced(tmp_path):
    engine, _ = make_agent(tmp_path, [{"content": "Searched.", "tool_calls": []},
                                      {"content": "Weather: highs near 30 per results.", "tool_calls": []}])
    engine.facts.apply("I live in Valencia", "user_explicit")
    # the user's June rule, stored as a MEMORY; startup migration turns it into a directive + tags it
    rule = engine.ingest("from now on always use brave search for weather", source="user_explicit")
    assert "_tool_rule" in rule.keywords
    from hmgfu.hygiene import migrate_tool_rules
    migrate_tool_rules(engine)
    assert any(d["kind"] == "tool_rule:brave_search" for d in engine.directives.active())
    from hmgfu.turn_events import plan_turn_actions
    q = SimpleNamespace(requested_tools=["brave_web_search"], action_requested=True, extractor="nano",
                        needs_memory=False, conversation_act="question")
    kept = [SimpleNamespace(point=rule)]
    requested, forced, retrieved = plan_turn_actions(engine, q, "tell me whats todays weather",
                                                     ["brave_web_search", "bash"], kept)
    assert "brave_web_search" in forced                     # the user's own rule = a named tool
    assert retrieved == kept                                # the rule memory survived the action turn


def test_side_effect_request_predicate_and_guard(tmp_path):
    assert requests_side_effect("create a weather widget for Valencia") and not requests_side_effect("tell me whats todays weather")
    engine, _ = make_agent(tmp_path, [
        {"content": "", "tool_calls": [{"name": "create_widget", "arguments": {"type": "weather", "title": "W", "props": {}}}]},
        {"content": "It is sunny per the results.", "tool_calls": []},
    ])
    r = engine.agent_chat("tell me whats todays weather", explicit=False)
    cw = [t for t in r["tool_trace"] if t["name"] == "create_widget"]
    assert cw and cw[0]["blocked"] and "confirmation" in cw[0]["result"]


def test_question_caps_and_grounding_gate_flags_fabricated_number(tmp_path):
    engine, _ = make_agent(tmp_path, [
        {"content": "", "tool_calls": [{"name": "brave_web_search", "arguments": {"query": "weather"}}]},
        {"content": "It is 26°C with clear skies.", "tool_calls": []},
        {"content": "It is 26°C with clear skies.", "tool_calls": []},      # the re-ask still invents it
    ])
    engine.facts.apply("I live in Valencia", "user_explicit")

    def question_router(text, **k):            # the live router classifies this as a question
        from hmgfu.sensitizer import heuristic_extract
        e = heuristic_extract(text)
        e.update({"conversation_act": "question", "extractor": "nano", "needs_memory": False})
        return e
    engine.sensitizer.extract = question_router
    r = engine.agent_chat("tell me whats todays weather", explicit=False)
    assert engine._turn_iteration_cap == engine.settings.get("question_max_iterations")
    assert "unverified: 26" in r["response"]                # gate flagged the fabricated value
    call = [t for t in r["tool_trace"] if t["name"] == "brave_web_search"][0]
    assert "Valencia" in json.dumps(call["arguments"])         # deixis completed the query


def test_clock_reading_does_not_ground_a_bare_number():
    from hmgfu.grounding import ungrounded_claims
    assert ungrounded_claims("It is 26°C with clear skies.", ["Local time 14:26:32, 2026-09-04"]) == ["26°C"]
    assert ungrounded_claims("It is 14:26 now.", ["Local time 14:26:32"]) == []          # time-shaped claim: grounded
    assert ungrounded_claims("It is 26°C.", ["Search result: Valencia 26°C sunny"]) == []  # tool result: grounded
