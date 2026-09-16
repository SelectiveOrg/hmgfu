"""95.39 (L4, c95w11d rep1) — a definite-article form of a CLOSED slot is the user's own attribute.

"Correcao: o projeto principal chama-se Vega, nao Nimbus." was never read by the regex (no
possessive), the live nano mapper is silent on it 5/5, and every earlier L4 pass came from the learning
protocol's definition commit, which depends on the perceiver proposing. Positive: the PT and EN article
forms write the closed slot and retire the old value; the store supersedes. Negative: a third party's
attribute is not the user's; an open head does not become a fact (the colon form's own rule); the
possessive forms are unchanged.
"""
from __future__ import annotations

from hmgfu.facts import FactStore
from hmgfu.fact_detect import detect_facts

PT = "Correcao: o projeto principal chama-se Vega, nao Nimbus."
EN = "Correction: the main project is called Vega, not Nimbus."


def _pairs(dets):
    return [(d["key"], d["value"], d.get("supersedes")) for d in dets]


def test_the_article_forms_are_read_with_the_value_to_retire():
    """THE CONTRACT — fails before: nothing is detected."""
    assert _pairs(detect_facts(PT)) == [("projeto_principal", "Vega", "Nimbus")]
    assert _pairs(detect_facts(EN)) == [("main_project", "Vega", "Nimbus")]
    assert all(d.get("weak") for d in detect_facts(PT) + detect_facts(EN))


def test_the_store_supersedes_on_the_article_form(tmp_path):
    for first, second in (("O meu projeto principal chama-se Nimbus.", PT), ("My main project is called Nimbus.", EN)):
        store = FactStore(str(tmp_path / f"{len(first)}.db"))
        store.apply_all(first, "user_explicit", session="s1")
        assert [(c.get("key"), c.get("value")) for c in store.apply_all(second, "user_explicit", session="s1")] == [("project.main", "Vega")]
        assert [(f["key"], f["value"]) for f in store.active()] == [("project.main", "Vega")]


def test_a_third_party_and_an_open_head_write_nothing(tmp_path):
    assert detect_facts("O projeto principal do Rui chama-se Atlas.") == []
    store = FactStore(str(tmp_path / "o.db"))
    assert store.apply_all("The weather is grey today.", "user_explicit", session="s1") == []
    assert store.apply_all("A reuniao e amanha.", "user_explicit", session="s1") == []
    assert store.active() == []


def test_the_possessive_forms_are_unchanged():
    assert _pairs(detect_facts("O meu projeto principal chama-se Vega, nao Nimbus.")) == [("projeto_principal", "Vega", "Nimbus")]
    assert _pairs(detect_facts("My main project is called Orca now, not Marlin."))[0][:2] == ("main_project", "Orca")
