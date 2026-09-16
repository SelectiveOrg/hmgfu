"""95.30 (X1, 0/3 both arms) + 95.34 (N4 rep1) — a reference to an attribute is not its value, a value
does not begin with the cue that introduces it, and the PT rename of a pet is read.

X1: "Write a file project.txt … containing the name of my main project." → the span extractor proposed
project.main = "My Main Project" (the attribute's own words), overwriting Orca in every rep of both
arms. N4 rep1: pet.cat.name = "chama-se Lua" was written with the cue inside the value (on HEAD the span
writer refuses that shape outright and writes NOTHING, so the value is lost either way). And the run's own PT rename
("a minha gata já não se chama Sol, chama-se Lua") had no mould, so only the perceiver read it.
Positive: the reference is refused at both writers, the cue is stripped by the one cleaner, the rename
writes the NEW name under the species key and supersedes the old one. Negative: a real value under the
same attribute still writes. Preserve: an English rename and an EN pet form are unchanged.
"""
from __future__ import annotations

from hmgfu.facts import FactStore
from hmgfu.fact_spans import apply_spans, extract_spans
from hmgfu.slots import is_reference_to_attribute

X1 = "Write a file project.txt in the workspace containing the name of my main project."
N4 = "A minha gata já não se chama Sol, chama-se Lua."


def _fake(facts):
    return lambda prompt, schema: {"facts": facts}


def _spans(store, text, facts):
    return [(c.get("key"), c.get("value")) for c in
            apply_spans(store, text, "user_explicit", lambda t: extract_spans(t, _fake(facts)))]


def test_a_reference_is_made_of_the_attributes_own_words_only():
    """THE CONTRACT (slots) — fails before: the function does not exist."""
    assert is_reference_to_attribute("project.main", "My Main Project")
    assert is_reference_to_attribute("pet.cat.name", "my cat")
    assert not is_reference_to_attribute("project.main", "Orca")
    assert not is_reference_to_attribute("project.main", "Project Omega")     # one word of its own
    assert not is_reference_to_attribute("identity.name", "")


def test_the_span_writer_refuses_the_reference_and_keeps_a_value(tmp_path):
    """X1 — fails before: project.main = 'My Main Project' overwrote Orca."""
    store = FactStore(str(tmp_path / "f.db"))
    assert _spans(store, "My main project is called Orca.", [{"attribute": "main project", "value": "Orca"}]) == [("project.main", "Orca")]
    assert _spans(store, X1, [{"attribute": "main project", "value": "My Main Project"}]) == []
    assert [(f["key"], f["value"]) for f in store.active()] == [("project.main", "Orca")]


def test_the_introducing_cue_is_not_part_of_the_value(tmp_path):
    """N4 rep1 — fails before: pet.cat.name = 'chama-se Lua'."""
    store = FactStore(str(tmp_path / "f.db"))
    assert _spans(store, N4, [{"attribute": "cat name", "value": "chama-se Lua"}]) == [("pet.cat.name", "Lua")]


def test_the_pt_rename_is_read_and_supersedes(tmp_path):
    """N4 — fails before: the regex path detects nothing in the PT rename."""
    store = FactStore(str(tmp_path / "f.db"))
    store.apply_all("A minha gata chama-se Sol.", "user_explicit")
    assert [(f["key"], f["value"]) for f in store.active()] == [("pet.cat.name", "Sol")]
    assert [(c.get("key"), c.get("value")) for c in store.apply_all(N4, "user_explicit")] == [("pet.cat.name", "Lua")]
    assert [(f["key"], f["value"]) for f in store.active()] == [("pet.cat.name", "Lua")]


def test_english_forms_are_unchanged(tmp_path):
    store = FactStore(str(tmp_path / "f.db"))
    store.apply_all("My cat is called Sol.", "user_explicit")
    store.apply_all("My cat is called Lua now.", "user_explicit")
    assert [(f["key"], f["value"]) for f in store.active()] == [("pet.cat.name", "Lua")]


def test_the_mapper_refuses_the_reference_too(tmp_path):
    """95.30b (X1 on 4ca1846, 0/3; reproduced offline with the live nano) — fails before: the fallback
    mapper's result joins `found` after the guard loop, checked only by name_value_ok, so the
    attribute's own words overwrite Orca. The refusal belongs in the mapper's own grounding gate."""
    from hmgfu.slots import map_to_slot
    fake = lambda prompt, schema: {"slot": "project.main", "value": "My Main Project", "op": "set"}
    assert map_to_slot(X1, fake) is None
    assert map_to_slot("My main project is called Orca.", lambda p, s: {"slot": "project.main", "value": "Orca", "op": "set"}) == {"key": "project.main", "value": "Orca"}
    store = FactStore(str(tmp_path / "f.db"))
    store.apply_all("My main project is called Orca.", "user_explicit")
    store.bind_mapper(lambda text: map_to_slot(text, fake))
    store.use_mapper = True
    assert store.apply_all(X1, "user_explicit") == []
    assert [(f["key"], f["value"]) for f in store.active()] == [("project.main", "Orca")]
