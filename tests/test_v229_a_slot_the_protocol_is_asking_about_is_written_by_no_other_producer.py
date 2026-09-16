"""95.46 (N6 on b9bedb4, d95w13v4 rep1) — a slot the protocol is asking about is written by no other
producer this turn.

The protocol asked "Noted: main project is no longer Kestrel. What is it now?" and wrote nothing, and
the fallback mapper read the same denial as op=clear: project.main Kestrel -> None, the store revision
moved, and "Sure, go ahead" invalidated the case instead of asking again. Positive: with the asked slot
held, the mapper's clear (and a set) on it is dropped; the value stays until the user's answer.
Negative: without a hold the same clear still applies (existing behaviour); another slot is not held.
Wiring: the engine passes the decision's blocked relations as hold_keys.
"""
from __future__ import annotations

import inspect

from hmgfu.facts import FactStore
from hmgfu.slots import map_to_slot

DENY = "Kestrel is no longer the name of my main project."


def _store(tmp_path, out):
    store = FactStore(str(tmp_path / "f.db"))
    store.apply_all("My main project is called Kestrel.", "user_explicit", session="s1")
    store.apply_all("I live in Quelimane.", "user_explicit", session="s1")
    store.bind_mapper(lambda text: map_to_slot(text, lambda p, s: out))
    store.use_mapper = True
    return store


def test_a_held_slot_is_not_cleared_or_set_by_the_mapper(tmp_path):
    """THE CONTRACT — fails before: the mapper's clear lands on the slot the protocol is asking about."""
    store = _store(tmp_path, {"slot": "project.main", "value": "Kestrel", "op": "clear"})
    assert store.apply_all(DENY, "user_explicit", session="s1", hold_keys=["project.main"]) == []
    assert [(f["key"], f["value"]) for f in store.active() if f["key"] == "project.main"] == [("project.main", "Kestrel")]
    (tmp_path / "b").mkdir(exist_ok=True)
    store2 = _store(tmp_path / "b", {"slot": "project.main", "value": "Tamarin", "op": "set"})
    assert store2.apply_all("My main project is Tamarin now.", "user_explicit", session="s1", hold_keys=["project.main"]) == []


def test_without_a_hold_the_clear_applies_and_other_slots_are_not_held(tmp_path):
    store = _store(tmp_path, {"slot": "project.main", "value": "Kestrel", "op": "clear"})
    changes = store.apply_all(DENY, "user_explicit", session="s1")
    assert changes and changes[0].get("cleared")
    (tmp_path / "c").mkdir(exist_ok=True)
    store3 = _store(tmp_path / "c", {"slot": "identity.location", "value": "Tete", "op": "set"})
    assert [(c.get("key"), c.get("value")) for c in store3.apply_all("I live in Tete now.", "user_explicit", session="s1", hold_keys=["project.main"])] == [("identity.location", "Tete")]


def test_the_engine_holds_the_decisions_blocked_relations():
    from hmgfu import agent
    src = inspect.getsource(agent)
    assert "hold_keys=held" in src and '"blocked_proposals"' in src and 'dec.get("action") == "ask"' in src   # 95.46b: only an ASK holds
