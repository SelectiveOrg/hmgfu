"""Phase 91.V3 — modality must not depend on sentence boundaries or on punctuation.

Independent verification (`reports/codex_verify_phase91/VERIFICACAO.md`), reproduced here before the fix:

    In my novel. I have lived in Lichinga since 2022.        -> identity.location = Lichinga
    Imagine this situation. I have lived in Lichinga since 2022.  -> identity.location = Lichinga

The frame IS detected ("In my novel." is `fiction`, and the store already carries it to the next sentence), but
`_SINCE` decides before the carry is ever consulted — the same ordering defect as 91.S1, one layer out. The 91.S1
`_unreal` predicate checked an inherited CITATION and not an inherited fiction or hypothesis.

Second half: `I want to work on Zenvira but I live in Lichinga now` does not update the city, because the clause split
added in 90.M requires a COMMA before the contrastive coordinator. The ROADMAP claimed independence from punctuation
that the implementation never had.

The negatives matter as much as the capability: the escape from a carried frame ("actually", "in real life") must keep
working, and "but" as a preposition must not manufacture a clause.
"""

from __future__ import annotations

import pytest

from hmgfu.facts import FactStore
from hmgfu.utterance import sentence_modalities


def _active(tmp_path, *messages):
    st = FactStore(str(tmp_path / "f.db"))
    for m in messages:
        st.apply_all(m, "user_explicit")
    return {f["key"]: f["value"] for f in st.active()}


CARRIED = [
    ("In my novel. I have lived in Lichinga since 2022.", "fiction across sentences"),
    ("Imagine this situation. I have lived in Lichinga since 2022.", "hypothesis across sentences"),
    ("In my story. I work at Zenvira since 2021.", "fiction, employer"),
    ("No meu romance. Moro em Lichinga desde 2022.", "fiction across sentences, pt"),
    ("Suppose the following. I have lived in Lichinga since 2022.", "hypothesis, other cue"),
]


@pytest.mark.parametrize("text,kind", CARRIED)
def test_a_carried_frame_survives_a_date_in_the_next_sentence(tmp_path, text, kind):
    got = _active(tmp_path, "I live in Nacala.", text)
    assert got.get("identity.location") == "Nacala", f"{kind}: {got}"
    assert "Lichinga" not in str(got) and "Zenvira" not in str(got), f"{kind}: {got}"


def test_the_escape_from_a_carried_frame_still_works(tmp_path):
    """"actually" breaks the fiction — the user is speaking about the real world again."""
    got = _active(tmp_path, "I live in Nacala.", "In my novel. Actually, I live in Lichinga.")
    assert got.get("identity.location") == "Lichinga", got


MIXED = [
    ("I want to work on Zenvira but I live in Lichinga now.", "identity.location", "Lichinga"),
    ("I want to work on Zenvira, but I live in Lichinga now.", "identity.location", "Lichinga"),
    ("Quero trabalhar no Zenvira mas moro em Lichinga agora.", "identity.location", "Lichinga"),
]


@pytest.mark.parametrize("text,key,value", MIXED)
def test_a_contrastive_clause_does_not_need_a_comma(tmp_path, text, key, value):
    assert _active(tmp_path, "I live in Nacala.", text).get(key) == value


NOT_CLAUSES = [
    ("I like everything but coffee.", "but as a preposition"),
    ("My favourite drink is nothing but water.", "idiom"),
]


@pytest.mark.parametrize("text,kind", NOT_CLAUSES)
def test_but_as_a_preposition_does_not_manufacture_a_claim(tmp_path, text, kind):
    got = _active(tmp_path, text)
    assert "identity.location" not in got, f"{kind}: {got}"
    assert all("but" not in str(v).lower() for v in got.values()), f"{kind}: {got}"


def test_the_one_sentence_fiction_case_is_still_fixed(tmp_path):
    """The 91.S1 gain must survive."""
    got = _active(tmp_path, "I live in Nacala.", "In my novel, I have lived in Lichinga since 2022.")
    assert got.get("identity.location") == "Nacala", got


def test_the_legitimate_dated_assertion_is_still_written(tmp_path):
    assert _active(tmp_path, "I have lived in Tete since 2022.").get("identity.location") == "Tete"
    assert [m["modality"] for m in sentence_modalities("I have lived in Tete since 2022.")] == ["assert"]


def test_a_longer_noun_phrase_after_but_still_manufactures_no_fact(tmp_path):
    """The split is by CLAUSE SHAPE, so a long noun phrase may be split off — it must still teach nothing."""
    got = _active(tmp_path, "I like everything but strong black coffee.")
    assert not got or all("coffee" not in str(v).lower() for v in got.values()), got


TRANSITIONS = [
    ("My project used to be Kuvala but now it is HMG.", "project.main", "HMG"),
    ("I used to live in Nacala but now I live in Lichinga.", "identity.location", "Lichinga"),
    ("O meu projeto era o Kuvala mas agora é o HMG.", "project.main", "HMG"),
]


@pytest.mark.parametrize("text,key,value", TRANSITIONS)
def test_a_transition_frame_spans_the_coordinator(tmp_path, text, key, value):
    """"used to be X but now Y" is ONE claim about ONE attribute: the contrastive split must not cut it in half.
    Caught by the DEV modality diagnostic (m28) after the comma-independent split, not by a unit test."""
    assert _active(tmp_path, text).get(key) == value
