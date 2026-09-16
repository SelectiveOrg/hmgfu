"""Phase 90.M — a modality is a property of the CLAUSE, not of the whole sentence. A contrastive coordinator starts a new claim:
"I want to work on X, but I currently work at Y" carries an intention AND a fact, and the fact must survive. Proved against the
pre-90.L code: those sentences used to write the fact (the sentence was `assert`); after the intent modality the whole sentence
became `intent` and the fact was silenced. The same defect predates 90.L for other modalities — "In 2019 I lived in Lisbon, but I
live in Valencia now." was `past` end to end and wrote nothing. One clause split in the existing sentence splitter, no new mould."""
from __future__ import annotations

import os
import tempfile

from hmgfu.facts import FactStore
from hmgfu.utterance import sentence_modalities


def _ledger(text: str) -> dict:
    store = FactStore(os.path.join(tempfile.mkdtemp(), "f.db"))
    store.apply_all(text, "user_explicit")
    return {r["key"]: r["value"] for r in store.active()}


def test_an_intention_does_not_silence_a_fact_in_the_same_sentence():
    for text, key, value in [
        ("I plan to move to Aveiro, but I live in Valencia.", "identity.location", "Valencia"),
        ("I want to learn Rust, but my favourite language is Java.", "pref.language", "Java"),
        ("Vou mudar de casa, mas moro em Valencia.", "identity.location", "Valencia"),
    ]:
        mods = [m["modality"] for m in sentence_modalities(text)]
        assert mods == ["intent", "assert"], (text, mods)
        assert _ledger(text).get(key) == value, (text, _ledger(text))


def test_a_past_clause_does_not_silence_the_current_one():
    text = "In 2019 I lived in Lisbon, but I live in Valencia now."
    mods = [m["modality"] for m in sentence_modalities(text)]
    assert mods == ["past", "assert"], mods
    assert _ledger(text).get("identity.location") == "Valencia", _ledger(text)


def test_a_pure_intention_is_still_one_intent_clause():
    for text in ["I want to work on HMG now.", "Quero trabalhar no HMG agora.", "We should work on HMG."]:
        assert [m["modality"] for m in sentence_modalities(text)] == ["intent"], text
        assert _ledger(text) == {}, text


def test_plain_assertions_are_untouched():
    assert _ledger("My main project is Kuvala.")["project.main"] == "Kuvala"
    assert _ledger("O meu projeto principal é o Kuvala.")["project.main"] == "Kuvala"
    assert set(m["modality"] for m in sentence_modalities("My name is Teodoro H. Ferreira.")) == {"assert"}


def test_a_contrastive_correction_writes_no_wrong_value():
    assert "identity.name" not in _ledger("My name is not Rui, but Rui Silva.")   # unchanged: neither clause is a clean name claim
