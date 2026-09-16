"""Phase 62 — closed fact slots + speech-act write gate (autopsy root causes, deterministic)."""

from __future__ import annotations

import pytest

from hmgfu.facts import FactStore
from hmgfu.slots import SLOTS, is_slot, label_for, map_to_slot, normalise_key, slot_schema
from hmgfu.speech_act import is_interrogative


@pytest.mark.parametrize("raw", [
    "favorite_language", "favorite_programming_language", "user:fav_language", "language:favorite",
    "user:Favourite Language name", "Favorite Programming Language name", "user:preferred_language",
    "favorite language", "linguagem favorita",
])
def test_every_language_spelling_collapses_to_one_slot(raw):
    assert normalise_key(raw) == "pref.language"


@pytest.mark.parametrize("raw,slot", [
    ("brother's name", "family.brother_name"), ("user:brother:name", "family.brother_name"),
    ("user:cat_name", "pet.cat.name"), ("dog", "pet.dog.name"), ("user:name", "identity.name"),
    ("where i live", "identity.location"), ("Favorite Colour name", "pref.color"),
    ("link_for_car_location", "asset.car_location_link"), ("cor favorita", "pref.color"),
])
def test_alias_families(raw, slot):
    assert normalise_key(raw) == slot


def test_normalise_key_is_idempotent_on_slot_ids_and_open_keys():
    for k in list(SLOTS) + ["open.nebula_outage_ticket", "open.favorite"]:
        assert normalise_key(k) == k


def test_unknown_attribute_becomes_cleaned_open_key_never_invented_spelling():
    assert normalise_key("nebula_outage_ticket") == "open.nebula_outage_ticket"
    assert normalise_key("Nebula Outage Ticket") == "open.nebula_outage_ticket"
    assert not is_slot("open.nebula_outage_ticket")
    assert label_for("pref.language") == "favorite programming language"


def test_slot_schema_is_closed_enum():
    enum = slot_schema()["properties"]["slot"]["enum"]
    assert set(enum) == set(SLOTS) | {"none"}


def test_mapper_rejects_unknown_slot_and_empty_value():
    assert map_to_slot("x", lambda p, s: {"slot": "made.up", "value": "v", "op": "set"}) is None
    assert map_to_slot("x", lambda p, s: {"slot": "pet.name", "value": "", "op": "set"}) is None
    assert map_to_slot("x", lambda p, s: {"slot": "none", "value": "", "op": "none"}) is None
    assert map_to_slot("my dog is Rex", lambda p, s: {"slot": "pet.dog.name", "value": "Rex", "op": "set"}) == \
        {"key": "pet.dog.name", "value": "Rex"}
    # 62.10 grounding: a value the user never uttered is rejected even with a valid slot
    assert map_to_slot("x", lambda p, s: {"slot": "pet.name", "value": "Rex", "op": "set"}) is None
    assert map_to_slot("x", lambda p, s: 1 / 0) is None      # model failure never breaks the turn


@pytest.mark.parametrize("text", [
    "what is my name", "whats my brothers name?", "tell me the weather",
    "remind me what my favorite color and pet are", "Do you know green?",
    "quick check: what is my name?", "qual é o meu nome", "please check and tell me the weather",
])
def test_questions_and_requests_are_interrogative(text):
    assert is_interrogative(text)


@pytest.mark.parametrize("text", [
    "my name is Teodoro", "actually my favarorite is java", "remember this: my cat is Nimbus",
    "Please remember that my favorite color is teal.", "Green my dog", "I live in Valencia",
    "call me Trailblazer", "for now on always tell me a joke", "I asked for current valencia weather",
])
def test_statements_pass_the_gate(text):
    assert not is_interrogative(text)


def test_factstore_keys_are_slots_and_supersession_crosses_spellings(tmp_path):
    fs = FactStore(str(tmp_path / "f.db"))
    assert fs.apply("my favourite language is Python")["key"] == "pref.language"
    r = fs.apply("actually my favorite programming language is Rust")
    assert {k: r[k] for k in ("key", "value", "prev")} == {"key": "pref.language", "value": "Rust", "prev": "Python"}   # 84.1: changes also carry `path`
    act = {f["key"]: f for f in fs.active()}
    assert list(act) == ["pref.language"]                       # ONE key, not two
    assert act["pref.language"]["label"] == "favorite programming language"
    assert fs.render_lines() == ["Your favorite programming language is Rust"]
    hist = fs.history("pref.language")
    assert [h["value"] for h in hist] == ["Python", "Rust"]     # full history kept
    assert fs.superseded_values() == [("pref.language", "Python")]


def test_factstore_never_stores_a_question(tmp_path):
    fs = FactStore(str(tmp_path / "f.db"))
    assert fs.apply("what is my name?") is None
    assert fs.apply("whats my brothers name?") is None
    assert fs.active() == []


def test_factstore_mapper_refines_open_key_and_fills_regex_gap(tmp_path):
    fs = FactStore(str(tmp_path / "f.db"))
    fs.bind_mapper(lambda text: {"key": "pref.language", "value": "java"}
                   if "java" in text else None)
    r = fs.apply("actually my favarorite is java")   # regex alone → open.favorite; mapper → slot
    assert r["key"] == "pref.language" and r["value"] == "java"
    r2 = fs.apply("what about java?")                # a question never reaches the mapper
    assert r2 is None


def test_legacy_rows_rekeyed_on_open(tmp_path):
    import sqlite3
    db = str(tmp_path / "f.db")
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE canonical_facts (key TEXT PRIMARY KEY, value TEXT, prev_value TEXT, "
              "source TEXT, updated_at TEXT, verbatim TEXT, source_turn_id TEXT)")
    c.execute("INSERT INTO canonical_facts VALUES ('favorite_language','Python',NULL,'user',"
              "'2026-06-20T18:00:00+00:00','x',NULL)")
    c.execute("INSERT INTO canonical_facts VALUES ('favorite_programming_language','Rust',NULL,'user',"
              "'2026-06-20T18:03:00+00:00','y',NULL)")
    c.commit(); c.close()
    fs = FactStore(db)
    act = fs.active()
    assert len(act) == 1 and act[0]["key"] == "pref.language" and act[0]["value"] == "Rust"
    assert act[0]["prev"] == "Python"


def test_link_form_captures_url_for_possessed_attribute(tmp_path):
    from hmgfu.facts import detect_fact
    pt = ("acesse esse link para identificar a localizacao da minha viatura: "
          "http://198.51.100.7/ui/sharing/0123456789abcdef?")          # RFC 5737 test address
    det = detect_fact(pt)
    assert det["value"].startswith("http://198.51.100.7/ui/sharing/")
    fs = FactStore(str(tmp_path / "f.db"))
    r = fs.apply(pt)
    assert r["key"] == "asset.car_location_link"
    assert fs.render_lines() == [f"Your car location link is {r['value']}"]
    en = fs.apply("here is the link to my dashboard: https://example.com/d?x=1 and more text")
    assert en["key"] == "open.dashboard_link" and en["value"] == "https://example.com/d?x=1"
