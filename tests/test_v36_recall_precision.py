"""Phase 65 — recall precision and use: questions are not answers, memory is never forced, replies are
stored without directive decoration, user words render verbatim, the heuristic grader is strict."""

from __future__ import annotations

from hmgfu.grader import _heuristic_grades
from hmgfu.hygiene import is_content_free_chatter, retype_stored_questions
from hmgfu.ingest import ingest_memory
from hmgfu.models import MemoryPoint
from hmgfu.retrieve import RetrievedMemory, make_query_point, organise_for_injection, retrieve_memory
from hmgfu.speech_act import refers_to_self
from hmgfu.taxonomy import is_user_grounded
from tests.test_v2_agent import make_agent


def _pt(content, source="assistant", type_="message", keywords=(), entities=(), summary=""):
    return MemoryPoint(type=type_, content=content, summary=summary, source=source,
                       keywords=list(keywords), entities=list(entities), embedding=[0.1] * 4)


def test_user_question_points_leave_the_recall_pool(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    q = ingest_memory("do you know me?", source="user", graph=engine.graph,
                      sensitizer=engine.sensitizer, embed=engine.embed)
    assert "_question" in q.keywords
    stmt = ingest_memory("my dog is Rex and I live in Aveiro", source="user", graph=engine.graph,
                         sensitizer=engine.sensitizer, embed=engine.embed)
    qp = make_query_point("do you know me and my dog?", engine.embed, engine.sensitizer)
    ids = [r.point.id for r in retrieve_memory(qp, engine.graph, min_score=0.0)]
    assert q.id not in ids and stmt.id in ids


def test_retype_tags_every_stored_user_interrogative(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    p = _pt("what is my name?", source="user", type_="task")
    engine.graph.save_point(p)
    assert retype_stored_questions(engine.graph) == 1
    assert "_question" in engine.graph.points[p.id].keywords and engine.graph.points[p.id].layer == "L1_session"


def test_user_authored_points_render_verbatim_not_nano_summary():
    p = _pt("u want you from now on start calling me Trailblazer", source="user", type_="concept",
            summary="A new era of innovation is about to begin.", entities=["Trailblazer"])
    p.layer = "L5_deep_pattern"
    inj = organise_for_injection([RetrievedMemory(point=p, edge=None, score=0.5, reason="x")], graph=None)
    lines = " ".join(inj["userIdentity"])
    assert "calling me Trailblazer" in lines and "new era" not in lines


def test_memory_actions_are_offered_but_never_forced(tmp_path):
    # provider answers in prose without calling the pinned memory_search: no "ACTION REQUIRED" retry
    engine, _ = make_agent(tmp_path, [{"content": "You are Amara.", "tool_calls": []}])
    engine.facts.apply("my name is Amara", source="user_explicit")
    engine.sensitizer.extract = lambda text, **k: _pinned(text)     # router pins memory_search as an action
    r = engine.agent_chat("tell me without any search, what do you know about me.", explicit=False)
    assert r["tool_trace"] == [] and "Amara" in r["response"]


def _pinned(text):
    from hmgfu.sensitizer import heuristic_extract
    e = heuristic_extract(text)
    e.update({"action_requested": True, "requested_tools": ["memory_search"], "needs_memory": False,
              "extractor": "nano", "conversation_act": "question"})
    return e


def test_self_referring_turn_keeps_memories_despite_needs_memory_false():
    assert refers_to_self("what do you know about me?") and refers_to_self("whats my cars location link")
    assert refers_to_self("qual é a minha cor favorita") and not refers_to_self("what is the weather in Aveiro")


def test_reply_is_stored_without_directive_decoration(tmp_path):
    engine, _ = make_agent(tmp_path, [{"content": "Your name is Amara.", "tool_calls": []}])
    engine.directives.apply("from now on always end your replies with a short joke", "user")
    engine.agent_chat("what is my name?", explicit=False)
    stored = [p.content for p in engine.graph.points.values() if p.source == "assistant"]
    assert all("joke" not in c.lower() and "why did" not in c.lower() for c in stored)


def test_heuristic_grader_needs_two_distinctive_tokens_outside_the_question():
    junk = _pt("I don't recognize the person.", keywords=["person", "recognize"])
    real = _pt("Teodoro lives in Valencia with his dog Green", keywords=["Valencia", "Green", "Teodoro"],
               entities=["Teodoro", "Valencia", "Green"])
    q = _pt("what is my name?", source="user", keywords=["_question", "name"])
    ret = [RetrievedMemory(point=x, edge=None, score=0.4, reason="") for x in (junk, real, q)]
    grades = {g["index"]: g["grade"] for g in _heuristic_grades(
        "You are Teodoro, you live in Valencia and your dog is Green. I recognize the person.",
        ret, user_message="do you recognize the person?")}
    assert grades == {0: "unused", 1: "cited", 2: "unused"}


def test_grounded_and_chatter_predicates():
    assert is_content_free_chatter(_pt("I'm ready to help with any questions you have."))
    assert not is_content_free_chatter(_pt("Your favorite programming language is Java.", entities=["Java"]))
    assert not is_user_grounded(_pt("what is my name?", source="user", keywords=["_question"]))
    assert is_user_grounded(_pt("my dog is Rex", source="user"))
    assert not is_user_grounded(_pt("I'm here to assist.", source="assistant"))


def test_router_pinned_external_tool_is_not_forced_on_a_self_question(tmp_path):
    engine, _ = make_agent(tmp_path, [{"content": "Your car link is http://198.51.100.7/x", "tool_calls": []}])
    engine.facts.apply("here is the link for my car location: http://198.51.100.7/x", source="user_explicit")

    def pinned(text, **k):
        from hmgfu.sensitizer import heuristic_extract
        e = heuristic_extract(text)
        e.update({"action_requested": True, "requested_tools": ["brave_web_search"], "needs_memory": False,
                  "extractor": "nano", "conversation_act": "question"})
        return e
    engine.sensitizer.extract = pinned
    r = engine.agent_chat("whats my cars location link", explicit=False)
    assert r["tool_trace"] == [] and "198.51.100.7" in r["response"]      # first prose answer survives


def test_named_tool_is_still_forced_on_a_self_question(tmp_path):
    engine, _ = make_agent(tmp_path, [{"content": "overview ready", "tool_calls": []}])
    r = engine.agent_chat("Use memory_zoom to inspect the memory overview about me.")
    assert r["tool_trace"] and r["tool_trace"][0]["name"] == "memory_zoom"
