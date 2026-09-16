"""Phase 69.4 — the ledger learns only asserted, present, first-person clauses; species pets; last-wins;
compound values; subject-bound updates; attribute-aware supersession; mapper relation check. Own reproductions
of the Phase 68 write-side findings (F01/F02)."""

from __future__ import annotations

from hmgfu.facts import FactStore, supersede_stale_nodes
from hmgfu.models import MemoryPoint
from hmgfu.slots import map_to_slot, relation_conflict
from hmgfu.utterance import declarative_text
from tests.test_v2_agent import make_agent


def _facts(st):
    return {f["key"]: f["value"] for f in st.active()}


def _store(tmp_path, *messages):
    tmp_path.mkdir(parents=True, exist_ok=True)
    st = FactStore(str(tmp_path / "f.db"))
    for m in messages:
        st.apply_all(m, "user_explicit")
    return st


def test_declarative_text_vetoes():
    assert declarative_text("I live in Chimoio. What do you know about that city?") == "I live in Chimoio."
    assert declarative_text('My friend said "my name is Oscar".') == "My friend said ."
    assert declarative_text("If my favorite color is violet, then use that in an example.") == ""
    assert declarative_text("In 2010 I lived in Lisbon; back then my favorite color is blue.") == ""
    assert declarative_text("My name is Nadia Costa, I live in Quelimane, and my dog is Bento.") != ""


def test_mixed_assertion_question_writes_the_assertion(tmp_path):
    assert _facts(_store(tmp_path, "I live in Chimoio. What do you know about that city?")) == {"identity.location": "Chimoio"}


def test_quoted_hypothetical_and_past_do_not_write(tmp_path):
    st = _store(tmp_path, "My name is Nadia Costa.", 'For a dialogue I am writing, my friend says "my name is Oscar". That is his name, not mine.')
    assert _facts(st)["identity.name"] == "Nadia Costa"
    st.apply_all("If my favorite color is violet, then use that in an example; this is hypothetical.", "user_explicit")
    assert "pref.color" not in _facts(st)
    st.apply_all("I live in Chimoio.", "user_explicit")
    st.apply_all("In 2010 I lived in Lisbon; back then my favorite color is blue.", "user_explicit")
    assert _facts(st)["identity.location"] == "Chimoio" and "pref.color" not in _facts(st)


def test_last_wins_and_compound_values(tmp_path):
    assert _facts(_store(tmp_path, "My favorite color is red, but my favorite color is blue."))["pref.color"] == "blue"
    assert _facts(_store(tmp_path / "b", "My favorite color is black and white."))["pref.color"] == "black and white"


def test_species_pets_and_selector_retraction(tmp_path):
    st = _store(tmp_path, "My cat is Mica and my dog is Bento.")
    assert _facts(st) == {"pet.cat.name": "Mica", "pet.dog.name": "Bento"}
    st.apply_all("I no longer have a dog.", "user_explicit")
    assert _facts(st) == {"pet.cat.name": "Mica"}
    st2 = _store(tmp_path / "pt", "A minha gata chama-se Luna e o meu cão é Rex.")
    assert _facts(st2) == {"pet.cat.name": "Luna", "pet.dog.name": "Rex"}
    assert _facts(_store(tmp_path / "gen", "My pet is Tiko."))["pet.name"] == "Tiko"        # compat: unspecified species


def test_portuguese_multi_fact_and_update_form_subject(tmp_path):
    st = _store(tmp_path, "A minha cor favorita é âmbar e a minha bebida favorita é chá de hibisco.")
    assert _facts(st) == {"pref.color": "âmbar", "pref.drink": "chá de hibisco"}
    st2 = _store(tmp_path / "u", "Here is the link for my car location: https://example.test/car",
                 "Here is the new recipe: https://example.test/soup")
    assert _facts(st2) == {"asset.car_location_link": "https://example.test/car", "open.recipe": "https://example.test/soup"}
    st2.apply_all("Here's the updated link: https://example.test/new", "user_explicit")
    assert _facts(st2)["asset.car_location_link"] == "https://example.test/new"           # generic subject still binds


def test_mapper_relation_conflict():
    assert relation_conflict("family.mother_name", "A minha cor favorita é âmbar.")
    assert not relation_conflict("family.partner_name", "The person I share my life with is Ana.")
    assert map_to_slot("A minha cor favorita é âmbar.", lambda *_: {"slot": "family.mother_name", "value": "âmbar", "op": "set"}) is None


def test_supersession_respects_attribute_and_retired_values(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    engine.facts.apply_all("My favorite color is blue.")
    car = MemoryPoint(content="My car is blue", summary="My car is blue", type="fact", source="user_explicit")
    engine.graph.save_point(car)
    engine.facts.apply_all("My favorite color is green.")
    supersede_stale_nodes(engine.facts, engine.graph)
    assert car.status == "active"                                                            # another attribute
    engine.facts.apply_all("My dog is Teca.")
    pet = MemoryPoint(content="My dog is Teca", summary="My dog is Teca", type="fact", source="user_explicit")
    engine.graph.save_point(pet)
    engine.facts.apply_all("I no longer have a dog.")
    supersede_stale_nodes(engine.facts, engine.graph)
    assert pet.status != "active"                                                            # retired value demoted
