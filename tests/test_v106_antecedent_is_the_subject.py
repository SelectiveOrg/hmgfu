"""Phase 91.V1/V2 — "last write" is not "the subject being corrected", and a referential candidate is still a candidate.

Independent verification (`reports/codex_verify_phase91/VERIFICACAO.md`) reproduced two defects introduced by my own
91.S2 change, both confirmed here before any fix:

    I live in Nacala. / My favourite colour is teal. / I live in Nacala. / That's wrong, it's Lichinga.
        -> the COLOUR became Lichinga; the city stayed Nacala. Restating a value writes no history row, so
           `history[-1]` was still the colour.

    My name is Amaro. / The answer to the puzzle is forty. / No, it's forty two.   -> identity.name = "forty two"
    My name is Amaro. / No, it's raining.                                          -> identity.name = "raining"

The control at `44a30c3`, before the referential path existed, corrupts none of these — so this was a net loss of
three cases for one gain, and the loss is mine.

Two contracts are being restored:
  1. the antecedent is the slot the PREVIOUS UTTERANCE WAS ABOUT, and only when the store still holds what that
     utterance asserted (a supported antecedent). Not unique, or not supported -> write nothing;
  2. a referential candidate goes through the SAME validations as every other candidate — value shape, ownership,
     modality, slot plausibility — instead of returning early past them.
"""

from __future__ import annotations

import pytest

from hmgfu.facts import FactStore


def _store(tmp_path, *messages):
    st = FactStore(str(tmp_path / "f.db"))
    for m in messages:
        st.apply_all(m, "user_explicit")
    return st


def _active(st):
    return {f["key"]: f["value"] for f in st.active()}


def test_a_restated_subject_is_still_the_antecedent(tmp_path):
    """The verification's first sequence: restating the city writes no row, but it IS what "that" refers to."""
    got = _active(_store(tmp_path, "I live in Nacala.", "My favourite colour is teal.", "I live in Nacala.",
                         "That's wrong, it's Lichinga."))
    assert got.get("identity.location") == "Lichinga", got
    assert got.get("pref.color") == "teal", got


def test_a_turn_with_no_fact_leaves_no_antecedent(tmp_path):
    """"The answer to the puzzle is forty." is not about the user's name; a correction after it must not touch it."""
    got = _active(_store(tmp_path, "My name is Amaro.", "The answer to the puzzle is forty.", "No, it's forty two."))
    assert got.get("identity.name") == "Amaro", got


def test_the_referential_value_still_faces_the_value_contract(tmp_path):
    """"raining" is not a name — the referential candidate must meet the same bar as any other."""
    got = _active(_store(tmp_path, "My name is Amaro.", "No, it's raining."))
    assert got.get("identity.name") == "Amaro", got


def test_competing_antecedents_change_nothing(tmp_path):
    got = _active(_store(tmp_path, "I live in Nacala and my favourite colour is teal.",
                         "That is incorrect; it's actually Lichinga."))
    assert got.get("identity.location") == "Nacala" and got.get("pref.color") == "teal", got


def test_a_subject_change_moves_the_antecedent(tmp_path):
    """The correction follows the conversation: after the colour is the subject, "it" is the colour."""
    got = _active(_store(tmp_path, "I live in Nacala.", "My favourite colour is teal.", "No, it's amber."))
    assert got.get("pref.color") == "amber" and got.get("identity.location") == "Nacala", got


KEPT = [
    (["I live in Nacala.", "That's wrong, it's Lichinga."], "identity.location", "Lichinga"),
    (["Moro em Nacala.", "Isso está errado; na verdade é Lichinga."], "identity.location", "Lichinga"),
    (["O meu projeto principal é o Kuvala.", "Isso está errado; é o Mapiko."], "project.main", "Mapiko"),
]


@pytest.mark.parametrize("turns,key,value", KEPT)
def test_the_simple_correction_is_preserved(tmp_path, turns, key, value):
    """The gain must survive the fix: this is the case the whole mechanism exists for."""
    assert _active(_store(tmp_path, *turns)).get(key) == value


def test_a_reiteration_writes_nothing_new(tmp_path):
    st = _store(tmp_path, "I live in Nacala.", "I live in Nacala.")
    assert _active(st).get("identity.location") == "Nacala"
    assert len([h for h in st.history("identity.location") if h.get("value") == "Nacala"]) == 1


def test_a_correction_in_a_later_session_still_needs_a_supported_antecedent(tmp_path):
    """A different session on the same memory: the antecedent must still be held by the store, not merely remembered."""
    st = _store(tmp_path, "I live in Nacala.")
    st2 = FactStore(str(tmp_path / "f.db"))          # a fresh reader of the same memory, as a new session would be
    st2.apply_all("That's wrong, it's Lichinga.", "user_explicit")
    assert _active(st2).get("identity.location") == "Nacala", _active(st2)


def test_the_family_relation_and_the_temporal_fact_are_untouched(tmp_path):
    got = _active(_store(tmp_path, "My sister's name is Ana.", "I have lived in Tete since 2022."))
    assert got.get("family.sister_name") == "Ana" and got.get("identity.location") == "Tete", got
