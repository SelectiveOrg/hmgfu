"""Phase 90.K — identity integrity in the attribute→slot mapping. Live defect (90.J): the extractor listed the attribute
"preference" for "These days I prefer kizomba." and `normalise_key` returned `identity.name`, so a stated preference overwrote the
user's NAME. Cause: the attribute's content tokens are empty (every token is a noise word) and the content-equality branch matched
the one alias whose content tokens are also empty — "name". An attribute with no discriminative content must never match a slot by
that coincidence; valid aliases, including the exact alias "name", must keep working. Deterministic: no model call."""
from __future__ import annotations

from hmgfu import slots
from hmgfu.fact_spans import extract_spans
from hmgfu.slots import SLOTS, _NOISE, _tokens, is_slot, normalise_key


def _fake(facts):
    return lambda prompt, schema: {"facts": facts}


def test_the_live_defect_a_preference_is_not_a_name():
    for attr in ("preference", "preferred", "my preference", "the current preference"):
        assert normalise_key(attr) != "identity.name", attr
        assert not is_slot(normalise_key(attr)), attr


def test_no_noise_only_attribute_reaches_a_slot_unless_it_is_itself_an_alias():
    exact = {tuple(_tokens(a)) for spec in SLOTS.values() for a in spec["aliases"]}
    for w in sorted(_NOISE):
        key = normalise_key(w)
        if tuple(_tokens(w)) in exact:
            continue                                   # "name" IS an alias of identity.name — a legitimate exact match
        assert not is_slot(key), (w, key)
    # combinations of noise words are equally empty of content
    for attr in ("my current", "the current", "of the", "meu", "minha", "o meu", "a minha", "your current preference"):
        assert not is_slot(normalise_key(attr)), attr


def test_empty_whitespace_and_unknown_attributes_stay_open():
    for attr in ("", "   ", "\t", None):
        key = normalise_key(attr)
        assert key.startswith("open.") and not is_slot(key), (attr, key)
    for attr in ("blorf", "quantum widget", "xyzzy of the thing"):
        assert not is_slot(normalise_key(attr)), attr


def test_every_alias_of_every_slot_still_resolves():
    for sid, spec in SLOTS.items():
        for alias in spec["aliases"]:
            assert normalise_key(alias) == sid, (alias, sid, normalise_key(alias))
            assert normalise_key(alias.upper()) == sid, alias


def test_a_stated_preference_never_overwrites_the_name_on_the_write_path():
    for attr in ("preference", "preferred", "my current"):
        dets = extract_spans("These days I prefer kizomba.", _fake([{"attribute": attr, "value": "kizomba"}]))
        assert [(d["key"], d["value"]) for d in dets] == [], (attr, dets)
    # an explicitly named identity still writes
    dets = extract_spans("My name is Zélia Mutemba.", _fake([{"attribute": "name", "value": "Zélia Mutemba"}]))
    assert [(d["key"], d["value"]) for d in dets] == [("identity.name", "Zélia Mutemba")]


def test_the_value_class_path_still_rescues_a_bare_preference():
    dets = extract_spans("Ultimamente prefiro chá de gengibre.", _fake([{"attribute": "preference", "value": "chá de gengibre"}]))
    assert [(d["key"], d["value"]) for d in dets] == [("pref.drink", "chá de gengibre")]


def test_the_production_regex_path_never_replaces_the_name_with_a_preference(tmp_path):
    """The defect reached PRODUCTION, not just the candidate: the regex detector emits the raw attribute and the store
    normalises it, so "My preference is kizomba." rewrote `identity.name` on today's defaults (verified against the pre-fix
    code). The name must survive; the un-named preference lands on an open key."""
    from hmgfu.facts import FactStore
    store = FactStore(str(tmp_path / "f.db"))
    store.apply_all("My name is Teodoro H. Ferreira.", "user_explicit")
    store.apply_all("My preference is kizomba.", "user_explicit")
    ledger = {r["key"]: r["value"] for r in store.active()}
    assert ledger["identity.name"] == "Teodoro H. Ferreira"
    assert "kizomba" not in ledger.get("identity.name", "")
    for text in ("A minha preferência é kizomba.", "My current is the blue one.", "My favourite is kizomba."):
        store.apply_all(text, "user_explicit")
    assert {r["key"]: r["value"] for r in store.active()}["identity.name"] == "Teodoro H. Ferreira"
