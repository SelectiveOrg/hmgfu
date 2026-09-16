"""Phase 78 — long-form excerpt policy: the query-matched sentence window, the echo test, byte-identical defaults,
the settings' bounds, and the section renderer still importable from retrieve (compatibility)."""
from __future__ import annotations

from types import SimpleNamespace

from hmgfu.context_render import excerpt_for_query, is_echo
from hmgfu.retrieve import _SECTION_ORDER, organise_for_injection, render_injection  # noqa: F401 (re-exports kept)
from hmgfu.models import MemoryPoint, QueryPoint, RetrievedMemory

LONG = ("I spent the morning at the market with my sister, buying vegetables for the week and a bag of oranges. "
        "We talked about her new job at the clinic for a while and about the long commute she now has every day. "
        "After lunch we walked along the river and looked at the boats being repaired near the old bridge. "
        "Then I finally adopted a dog from the shelter and named him Bolt. He is a two-year-old beagle with a torn ear. "
        "In the afternoon it rained so we stayed in and watched a film about mountaineers.")


def test_window_is_the_sentences_the_question_is_about():
    out = excerpt_for_query(LONG, "what is the name of the dog I adopted?", 160)
    assert "Bolt" in out and out.startswith("…") and "market" not in out
    out2 = excerpt_for_query(LONG, "what did we watch in the afternoon?", 120)
    assert "mountaineers" in out2 and out2.startswith("…") and not out2.endswith("…")
    assert excerpt_for_query("short memory.", "anything", 200) == "short memory."           # under budget: untouched


def test_no_overlap_keeps_the_head_and_marks_the_cut():
    out = excerpt_for_query(LONG, "quantos anos tem o carro?", 80)
    assert out.endswith("…") and out.startswith("I spent the morning") and len(out) <= 80
    assert excerpt_for_query(LONG, "", 80) == LONG[:79].rstrip() + "…"


def test_is_echo_only_for_a_restated_ledger_value_of_the_asked_attribute():
    p = SimpleNamespace(summary="", title="", content="Your dog's name is Bolt, as you told me.")
    pairs = [("pet.dog.name", "Bolt"), ("identity.location", "Valencia")]
    assert is_echo(p, "what is my dog called?", pairs)
    assert not is_echo(p, "where do I live?", pairs)                                            # another attribute
    assert not is_echo(SimpleNamespace(summary="", title="", content="The clinic moved to Matola."), "what is my dog called?", pairs)
    assert not is_echo(p, "what is my dog called?", [])                                         # no ledger → nothing to echo


def _mem(pid, content, source, ts):
    return RetrievedMemory(point=MemoryPoint(id=pid, content=content, summary="", title="", source=source, timestamp=ts,
                                            embedding=[0.0] * 4, layer="L1_session", type="message", keywords=[]), score=1.0)


def test_defaults_are_todays_output_and_the_candidate_changes_only_what_it_should():
    q = QueryPoint(text="what is the name of the dog I adopted?", embedding=[0.0] * 4, entities=[], topics=[], intent="question")
    q.conversation_act = "question"
    user = _mem("u1", LONG, "user", "2026-09-01T10:00:00+00:00")
    asst_echo = _mem("a1", "Your dog's name is Bolt.", "assistant", "2026-09-02T10:00:00+00:00")
    asst_new = _mem("a2", "The shelter said Bolt was vaccinated in March.", "assistant", "2026-09-03T10:00:00+00:00")
    graph = SimpleNamespace(points={})
    today = organise_for_injection([user, asst_echo, asst_new], graph, echo_free=True)                    # defaults
    rendered = " ".join(sum((today[k] for k, _ in _SECTION_ORDER), []))
    assert LONG[:200] in rendered and "named him Bolt" not in rendered                                    # head cut: the name is past 200 chars
    assert "vaccinated" not in rendered and "Your dog's name" not in rendered                              # all assistant memories dropped
    cand = organise_for_injection([user, asst_echo, asst_new], graph, echo_free=True, query=q, excerpt_chars=480,
                                  echo_scope="echoes", echo_pairs=[("pet.dog.name", "Bolt")])
    rendered2 = " ".join(sum((cand[k] for k, _ in _SECTION_ORDER), []))
    # the span with the name is in; BOTH assistant memories restate the asked attribute's ledger value → both are echoes here
    assert "named him Bolt" in rendered2 and "Your dog's name is Bolt" not in rendered2 and "vaccinated" not in rendered2
    q2 = QueryPoint(text="when was Bolt vaccinated?", embedding=[0.0] * 4, entities=[], topics=[], intent="question")
    kept = organise_for_injection([user, asst_echo, asst_new], graph, echo_free=True, query=q2, excerpt_chars=480,
                                  echo_scope="echoes", echo_pairs=[("pet.dog.name", "Bolt")])
    rendered3 = " ".join(sum((kept[k] for k, _ in _SECTION_ORDER), []))
    assert "vaccinated" in rendered3                                                                       # new information about Bolt stays when the question is not about the name
    plain = organise_for_injection([user], graph, query=q, excerpt_chars=200)
    plain_text = " ".join(sum((plain[k] for k, _ in _SECTION_ORDER), []))
    assert plain_text.startswith("…") and "Bolt" in plain_text                                              # 200 with a match: the span, not the head
    off = organise_for_injection([user], graph, query=q, excerpt_chars=0)                                   # the DEFAULT (0 = off): today's head cut
    off_text = " ".join(sum((off[k] for k, _ in _SECTION_ORDER), []))
    assert off_text == " ".join(sum((organise_for_injection([user], graph)[k] for k, _ in _SECTION_ORDER), []))


def test_settings_bounds_and_enum(tmp_path):
    import pytest
    from hmgfu.settings import Settings
    s = Settings(str(tmp_path / "s.db"))
    assert s.get("excerpt_max_chars") == 0 and s.get("echo_guard_scope") == "all"
    s.set("excerpt_max_chars", 480); s.set("echo_guard_scope", "echoes")
    with pytest.raises(ValueError):
        s.set("excerpt_max_chars", 4000)
    with pytest.raises(ValueError):
        s.set("echo_guard_scope", "none")
