"""Phase 79.3 — deterministic pre-router: claims only the two uniform classes, refuses everything else, and the
sensitizer uses it in place of the model router when bound (no route call)."""
from __future__ import annotations

from hmgfu.facts import FactStore
from hmgfu.pre_router import mentions_tool, pre_route

CATALOG = ["memory_search", "memory_zoom", "list_files", "write_file", "create_widget", "plan_task"]


def _facts(tmp_path):
    st = FactStore(str(tmp_path / "f.db"))
    for m in ("My name is Nadia Costa.", "I live in Valencia.", "My dog is Rex.", "My favourite colour is teal."):
        st.apply_all(m, "user_explicit")
    return st


def test_recall_questions_about_the_ledger_get_the_recall_route(tmp_path):
    f = _facts(tmp_path)
    for q in ("What is my name?", "What's my dog called?", "Qual era a minha cor favorita antes?", "Where do I live these days, my home?"):
        r = pre_route(q, CATALOG, f)
        assert r and r["action_requested"] and r["requested_tools"] == ["memory_search"] and r["conversation_act"] == "question" \
            and r["needs_memory"] and r["route_source"] == "bypass", q
    # a coverage limit, not a defect: the existing detectors do not recognise the verb form "Como me chamo?" as naming the
    # name attribute (production's user_fact_question has the same limit) — it falls through to the model router
    assert pre_route("Como me chamo?", CATALOG, f) is None
    # same limit for a bare "I" without a possessive: speech_act.refers_to_self does not count it — falls through (coverage)
    assert pre_route("Where did I live before I moved?", CATALOG, f) is None


def test_plain_fact_statements_get_the_statement_route(tmp_path):
    f = _facts(tmp_path)
    for s in ("My favourite colour is amber.", "A minha bebida favorita é chá de gengibre.", "I work as a nurse at the district hospital.",
              "Here is the updated link for my car location: https://example.test/car/9"):
        r = pre_route(s, CATALOG, f)
        assert r and not r["action_requested"] and r["requested_tools"] == [] and r["conversation_act"] == "statement" and r["needs_memory"], s


def test_everything_else_falls_through(tmp_path):
    f = _facts(tmp_path)
    for t in ("Remember that I live in Matola now.",                       # imperative opener → the reference says instruction
              "Actually my dog is called Kika, not Bolt.",                 # correction → instruction + memory_search
              "Corrijo: moro em Inhambane, não em Maxixe.",                # correction (PT) → falls through on the negation word
              "Isso está errado, o meu nome não é esse.",                  # negated statement → not a plain fact
              "Use memory_zoom to inspect the memory overview.",           # tool named
              "What files are in the workspace right now?",                # effect / workspace
              "Thanks, that's helpful.", "Good morning!", "ok",            # chatter: reference not uniform
              "What is the capital of Spain?",                        # world question, not about the ledger
              "How does your memory work?",                                # meta
              "From now on, end every reply with a short joke.",           # standing rule
              "What time is it now?",                                      # current
              "Plan how you would organise my notes into three files, but do not create anything yet.",
              "Yes, go ahead.", "I think I've been too hard on myself this week."):
        assert pre_route(t, CATALOG, f) is None, t
    assert mentions_tool("please run list_files here", CATALOG) and not mentions_tool("list my files", CATALOG)


def test_sensitizer_uses_the_bound_pre_router_instead_of_the_model_router(monkeypatch):
    from hmgfu.sensitizer import Sensitizer
    calls = []
    s = Sensitizer(client=None, enabled=True)
    s.enabled = True; s.extract_enabled = True

    def fake_chat(role, messages, **kw):
        calls.append(role)
        return {"content": '{"title": "t", "summary": "s", "type": "message", "keywords": [], "entities": [], "topics": [], '
                           '"intent": "statement", "conversation_act": "statement"}'}
    s.bind_role_chat(fake_chat)
    s.bind_pre_router(lambda text: {"action_requested": False, "requested_tools": [], "conversation_act": "statement",
                                    "needs_memory": True, "freshness": "none", "feedback_polarity": None, "directive": None,
                                    "route_source": "bypass"})
    out = s.extract("My favourite colour is amber.", route=True)
    assert "router" not in calls and calls == ["nano"]                 # the model router was never called
    assert out.get("conversation_act") == "statement"
    s.bind_pre_router(lambda text: None)                               # a refusal → the router runs as before
    calls.clear()
    s.extract("Use memory_zoom now.", route=True)
    assert "router" in calls


def test_skip_nano_makes_a_claimed_turn_free_of_model_calls():
    from hmgfu.sensitizer import Sensitizer
    calls = []
    s = Sensitizer(client=None, enabled=True)
    s.enabled = True; s.extract_enabled = True
    s.bind_role_chat(lambda role, messages, **kw: (calls.append(role), {"content": "{}"})[1])
    s.bind_pre_router(lambda text: {"action_requested": False, "requested_tools": [], "conversation_act": "statement",
                                    "needs_memory": True, "freshness": "none", "feedback_polarity": None, "directive": None,
                                    "route_source": "bypass", "skip_nano": True})
    out = s.extract("My favourite colour is amber.", route=True)
    assert calls == [] and out["extractor"] == "fallback+bypass" and out["conversation_act"] == "statement"
    assert out["keywords"] and out["summary"]                                     # heuristic fields present
    assert "skip_nano" not in out
