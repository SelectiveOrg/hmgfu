"""73.3 (M6 → product): user-fact questions are answered from the user's own words — assistant echoes never seed
the answer context; other turns keep every memory."""
from __future__ import annotations

from hmgfu.models import MemoryPoint, QueryPoint, RetrievedMemory
from hmgfu.retrieve import organise_for_injection, user_fact_question
from hmgfu.store import HMGGraph
from hmgfu.facts import FactStore


def _rm(p, reason="semantic"):
    return RetrievedMemory(point=p, edge=None, score=0.8, reason=reason)


def test_user_fact_question_is_decided_by_the_ledger_vocabulary(tmp_path):
    st = FactStore(str(tmp_path / "f.db"))
    st.apply_all("My name is Ana", "user_explicit")
    assert user_fact_question(QueryPoint(text="what is my name?", conversation_act="question"), st) is True
    assert user_fact_question(QueryPoint(text="qual é o meu nome?", conversation_act="question"), st) is True
    assert user_fact_question(QueryPoint(text="what is the weather in Valencia?", conversation_act="question"), st) is False
    assert user_fact_question(QueryPoint(text="my name is Ana", conversation_act="statement"), st) is False
    assert user_fact_question(QueryPoint(text="what is my name?", conversation_act="question"), None) is False


def test_echo_free_drops_assistant_and_dream_lines_but_keeps_history(tmp_path):
    g = HMGGraph(str(tmp_path / "g.db"))
    user = MemoryPoint(type="message", content="my name is Ana", summary="", source="user", embedding=[0.1] * 4)
    echo = MemoryPoint(type="message", content="Your name is Ana.", summary="", source="assistant", embedding=[0.1] * 4)
    dream = MemoryPoint(type="macro", content="The user is called Ana", summary="", source="dream", embedding=[0.1] * 4)
    hist = MemoryPoint(type="message", content="You said your name was Ana", summary="", source="assistant", embedding=[0.1] * 4)
    for p in (user, echo, dream, hist):
        g.save_point(p)
    items = [_rm(user), _rm(echo), _rm(dream), _rm(hist, reason="history[active]")]
    kept = organise_for_injection(items, g, echo_free=True)
    flat = " ".join(" ".join(v) for v in kept.values() if isinstance(v, list))
    assert "my name is Ana" in flat and "Your name is Ana." not in flat and "called Ana" not in flat
    assert "You said your name was Ana" in flat                      # timeline entries are the user's line, kept
    all_lines = organise_for_injection(items, g, echo_free=False)
    assert "Your name is Ana." in " ".join(" ".join(v) for v in all_lines.values() if isinstance(v, list))



def test_mapper_requires_the_attribute_to_be_named():
    """74.3: the model mapper wrote family.mother_name=Echo from a sentence that never mentions a mother."""
    from hmgfu.slots import map_to_slot
    hallucinate = lambda p, s: {"slot": "family.mother_name", "value": "Echo", "op": "set"}
    assert map_to_slot("For Echo I am writing everything in Kotlin.", hallucinate) is None
    grounded = lambda p, s: {"slot": "family.mother_name", "value": "Ana", "op": "set"}
    assert map_to_slot("a minha mãe chama-se Ana", grounded) == {"key": "family.mother_name", "value": "Ana"}
    alias = lambda p, s: {"slot": "identity.alias", "value": "Zee", "op": "set"}
    assert map_to_slot("people call me Zee", alias) == {"key": "identity.alias", "value": "Zee"}


def test_relatives_attribute_is_an_open_key_not_the_relatives_name():
    from hmgfu.slots import normalise_key
    assert normalise_key("sister's favorite food").startswith("open.")
    assert normalise_key("my brother's favorite color").startswith("open.")
    assert normalise_key("sister's name") == "family.sister_name"
    assert normalise_key("my brother") == "family.brother_name"
    assert normalise_key("favorite food") == "pref.food"


def test_stale_exclusion_is_attribute_gated(tmp_path):
    """74.3: once 'Echo' was a superseded mother's name, every memory mentioning project Echo vanished from the context."""
    from hmgfu.models import MemoryPoint
    from hmgfu.retrieve import organise_for_injection
    from hmgfu.store import HMGGraph
    g = HMGGraph(str(tmp_path / "g.db"))
    project = MemoryPoint(type="message", content="For Echo I am writing everything in Kotlin.", summary="", source="user", embedding=[0.1] * 4)
    mother = MemoryPoint(type="message", content="my mother's name is Echo", summary="", source="user", embedding=[0.1] * 4)
    for p in (project, mother):
        g.save_point(p)
    items = [_rm(project), _rm(mother)]
    inj = organise_for_injection(items, g, superseded=[("family.mother_name", "Echo")])
    flat = " ".join(" ".join(v) for v in inj.values() if isinstance(v, list))
    assert "Kotlin" in flat                                   # the project line stays: it says nothing about a mother
    assert "mother's name is Echo" not in flat                # the stale mother line goes
