"""Phase 91.AA — every independent proposition survives, with its own status and its own date.

Three defects the third review found, each kept here so it cannot return:

  * 91.Z's complement extraction kept only the governed proposition, so an assertion standing BEFORE
    the governor was discarded: "My name is Ana, and I can confirm that my dog is called Green." lost
    the name. Worse, the whole prefix counted as part of the governor, so "Ana and I know" matched the
    proper-name branch and the user's OWN name was read as a third-party speaker.
  * `_resolve` took `valid_from_of(original)` ONCE for the message, so two dated sentences both got
    the FIRST date -- right rows, wrong metadata, invisible to any check comparing key and value.
  * uncertainty was recognised verb by verb: "cannot" (univerbated negation), a modal hedge, an
    epistemic verb that was never segmented, and a NOUN-complement frame all wrote through.
"""

from __future__ import annotations

import pytest

from hmgfu.facts import FactStore
from hmgfu.utterance import governed_split, sentence_modalities


def _store(tmp_path, *prior, name="f.db"):
    st = FactStore(str(tmp_path / name))
    for p in prior:
        st.apply_all(p, "user_explicit", session="s")
    return st


def _after(st, text):
    st.apply_all(text, "user_explicit", session="s")
    return {f["key"]: f["value"] for f in st.active()}


# --- every independent proposition survives, in either order and with or without a comma ----------
@pytest.mark.parametrize("text,name,dog", [
    ("My name is Ana and my dog is called Green.", "Ana", "Green"),
    ("My name is Ana and I know that my dog is called Green.", "Ana", "Green"),
    ("My name is Ana, and I can confirm that my dog is called Green.", "Ana", "Green"),
    ("I can confirm that my dog is called Green, and my name is Ana.", "Ana", "Green"),
    ("My name is Ana and I deny that my dog is called Green.", "Ana", "Rex"),
    ("My name is Ana. I deny that my dog is called Green.", "Ana", "Rex"),
    ("I deny that my dog is called Green, and my name is Ana.", "Ana", "Rex"),
    ("O meu nome é Ana e nego que o meu cão chama-se Green.", "Ana", "Rex"),
])
def test_an_independent_proposition_is_never_discarded(tmp_path, text, name, dog):
    st = _store(tmp_path, "My name is Bento.", "My dog is called Rex.")
    got = _after(st, text)
    assert got.get("identity.name") == name and got.get("pet.dog.name") == dog


def test_coordination_inside_a_value_is_not_split(tmp_path):
    """The governor starts at the LAST clause boundary, so "black and white" stays whole."""
    st = _store(tmp_path, "My favourite colour is red.")
    got = _after(st, "My favourite colour is black and white and I confirm that my dog is called Green.")
    assert got.get("pref.color") == "black and white" and got.get("pet.dog.name") == "Green"


# --- each fact keeps the date of the clause that licensed it --------------------------------------
@pytest.mark.parametrize("text", [
    "Since 2018 my base is Tete. Since 2023 my employer is Acme.",
    "Since 2023 my employer is Acme. Since 2018 my base is Tete.",
])
def test_each_fact_keeps_its_own_valid_from(tmp_path, text):
    st = _store(tmp_path)
    st.apply_all(text, "user_explicit", session="s")
    dated = {a["relation"]: a.get("valid_from") for a in st.assertions.active()}
    assert dated.get("identity.location") == "2018-01-01"
    assert dated.get("identity.company") == "2023-01-01"


# --- uncertainty by class, each paired with the positive that must still be recognised ------------
@pytest.mark.parametrize("negative,positive", [
    ("I cannot confirm that my dog is called Green.", "I can confirm that my dog is called Green."),
    ("I can't confirm that my dog is called Green.", "I can confirm that my dog is called Green."),
    ("I assume that my dog is called Green.", "I know that my dog is called Green."),
    ("I suspect that my dog is called Green.", "I know that my dog is called Green."),
    ("I might say that my dog is called Green.", "I say that my dog is called Green."),
    ("I could say that my dog is called Green.", "I say that my dog is called Green."),
    ("I challenge the claim that my dog is called Green.", "I accept the claim that my dog is called Green."),
    ("Presumo que o meu cão chama-se Green.", "Confirmo que o meu cão chama-se Green."),
])
def test_uncertainty_blocks_and_its_positive_still_writes(tmp_path, negative, positive):
    st = _store(tmp_path, "My dog is called Rex.")
    assert _after(st, negative).get("pet.dog.name") == "Rex", negative
    st2 = _store(tmp_path, "My dog is called Rex.", name="second.db")
    assert _after(st2, positive).get("pet.dog.name") == "Green", positive


def test_a_polite_request_is_not_a_hedge():
    """A modal hedges the SPEAKER's assertion; the same modal with a second-person subject asks."""
    assert sentence_modalities("Could you remember that Green is my dog?")[0]["modality"] == "assert"
    assert sentence_modalities("I could say that Green is my dog.")[0]["modality"] == "hypothesis"


def test_a_quoted_citation_never_reaches_the_write_path(tmp_path):
    """The licensed text is what every downstream consumer sees, the model mapper included."""
    st = _store(tmp_path)
    got = _after(st, 'My cousin said "my name is Rita".')
    assert "identity.name" not in got and "family.sister_name" not in got


def test_governed_split_reports_the_prefixes():
    pres, prop, modality = governed_split("My name is Ana and I deny that my dog is called Green.")
    assert pres == ["My name is Ana"] and modality == "hypothesis"
    assert prop == "my dog is called Green."
