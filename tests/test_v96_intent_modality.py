"""Phase 90.L3 — intention and proposal are a MODALITY, not a fact. The store's modality contract had no deontic/volitive class,
so "we should work on X" and "I want to work on X" were `assert`; nothing was written for them only because no regex mould
produced a value — a side effect of the mould set, not a contract (90.J showed what happens when another path does produce one).
One class in the existing enum, one speaker-anchored cue; `declarative_clauses` keeps only `assert`, so every consumer inherits it.
A speech-act idiom whose complement IS the assertion ("I want to tell you my name is X") stays an assertion."""
from __future__ import annotations

import tempfile, os

from hmgfu.facts import FactStore
from hmgfu.utterance import MODALITIES, declarative_clauses, sentence_modalities

INTENT = [
    "We should work on HMG.", "Devíamos trabalhar no HMG.", "Devemos mudar de projecto.",
    "I want to work on HMG now.", "Quero trabalhar no HMG agora.",
    "I'm going to work on HMG tomorrow.", "Vou trabalhar no HMG amanhã.",
    "I plan to work on HMG.", "Pretendo mudar de projecto.", "Let's work on HMG.",
    "We could work on HMG instead.", "I would like to work on HMG.", "Gostava de trabalhar no HMG.",
]
ASSERT = [
    "My main project is Mapiko.", "O meu projeto principal é o Mapiko.",
    "Actually my main project is Mapiko, not Kuvala.", "From now on my project is HMG.",
    "My name is Zélia Mutemba.", "I live in Valencia.",
    "I want to tell you my name is Zélia Mutemba.", "Quero dizer, o meu nome é Zélia.",
]


def test_intent_is_a_modality_of_its_own():
    assert "intent" in MODALITIES
    for t in INTENT:
        mods = [m["modality"] for m in sentence_modalities(t)]
        assert mods == ["intent"], (t, mods)
        assert declarative_clauses(t) == [], t


def test_assertions_and_corrections_are_untouched():
    for t in ASSERT:
        mods = [m["modality"] for m in sentence_modalities(t)]
        assert mods == ["assert"], (t, mods)
        assert declarative_clauses(t), t


def test_the_write_path_inherits_it(tmp_path):
    store = FactStore(str(tmp_path / "f.db"))
    store.apply_all("My main project is Kuvala.", "user_explicit")
    base = {r["key"]: r["value"] for r in store.active()}
    for t in ["I want my main project to be HMG.", "We should make HMG the main project.",
              "Vou mudar: o meu projeto principal passa a ser o HMG.", "I plan to make my main project HMG."]:
        store.apply_all(t, "user_explicit")
        assert {r["key"]: r["value"] for r in store.active()} == base, t     # an intention writes nothing
    store.apply_all("My main project is HMG.", "user_explicit")              # the assertion still writes
    assert {r["key"]: r["value"] for r in store.active()}["project.main"] == "HMG"


def test_the_other_modalities_still_decide_first():
    assert [m["modality"] for m in sentence_modalities("Are we going to work on HMG?")] == ["question"]
    assert [m["modality"] for m in sentence_modalities("If I wanted to work on HMG I would need time.")] == ["hypothesis"]
    assert [m["modality"] for m in sentence_modalities("In 2019 I wanted to work on Kuvala.")] == ["past"]
