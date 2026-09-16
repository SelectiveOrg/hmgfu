"""95.32 (N4, candidate 0/3) — a pet is an entity by its role, not by its name.

The assertion mirror keyed the pet entity by the name value, so renaming the cat (Sol → Lua) became a
clear of the old entity plus a new entity — an undue write and a split history. Positive: after the
rename one pet entity holds Lua active and Sol superseded. Negative: a second cat (.2) is another
entity. Preserve: the canonical fact still moves Sol → Lua with prev; a dog and a cat stay apart.
"""
from __future__ import annotations

from tests.test_v2_agent import make_agent


def _defs(engine, relation):
    st = engine.facts.assertions
    return sorted((a["entity_id"], a["value"], a.get("status", "active")) for a in st.history() if a["relation"] == relation)


def test_a_rename_supersedes_inside_the_same_entity(tmp_path):
    """THE CONTRACT — fails before: two pet entities, the old one cleared."""
    engine, _ = make_agent(tmp_path, [])
    engine.facts.apply_all("A minha gata chama-se Sol.", "user", session="s1")
    engine.facts.apply_all("Correcao: a minha gata ja nao se chama Sol, chama-se Lua.", "user", session="s1")
    rows = _defs(engine, "pet.cat.name")
    entities = {e for e, _, _ in rows}
    assert len(entities) == 1, rows
    assert {(v, s) for _, v, s in rows} == {("Sol", "superseded"), ("Lua", "active")}, rows
    assert ("pet.cat.name", "Lua") in [(f["key"], f["value"]) for f in engine.facts.active()]


def test_a_second_cat_is_another_entity(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    engine.facts.apply_all("Temos duas gatas: a Sol e a Lua.", "user", session="s1") or \
        engine.facts.apply_all("A minha gata chama-se Sol. Tenho uma segunda gata, chama-se Lua.", "user", session="s1")
    keys = {f["key"] for f in engine.facts.active() if f["key"].startswith("pet.cat")}
    assert len(keys) >= 1
    ents = {e for e, _, _ in _defs(engine, "pet.cat.name")}
    assert len(ents) == len(keys), (keys, ents)


def test_a_dog_and_a_cat_stay_apart(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    engine.facts.apply_all("My dog is called Rex.", "user", session="s1")
    engine.facts.apply_all("My cat is called Sol.", "user", session="s1")
    dog = {e for e, _, _ in _defs(engine, "pet.dog.name")}
    cat = {e for e, _, _ in _defs(engine, "pet.cat.name")}
    assert dog and cat and not (dog & cat)
