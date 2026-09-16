"""Phase 91.S2 — "that's wrong; it's actually Lichinga" must correct the slot it refers to, or nothing at all.

From the independent audit (`reports/codex_execution_audit_20260909/ANALISE_E_PLANO.md` §3, P2): a correction that
does not repeat the attribute is not incorporated, in English or Portuguese. The audit is explicit that a regex with
no memory cannot be asked to find the antecedent on its own — but the fact store HAS the antecedent: its own
append-only history says which slot was written last.

The contract this fixes, and its limits, both come from the audit: update ONLY when the corrected slot is unique;
otherwise leave it alone and let the reader ask. So the tests below are half capability and half refusal — a bare
correction after two different writes in the same message must change nothing, and a bare "that's wrong" with no
replacement value must change nothing either. Preserving the old value is a correct outcome; guessing is not.
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


REFERENCE_CORRECTIONS = [
    ("I live in Nacala.", "That is incorrect; it's actually Lichinga.", "identity.location", "Lichinga"),
    ("I live in Nacala.", "That's wrong, it's Lichinga.", "identity.location", "Lichinga"),
    ("Moro em Nacala.", "Isso está errado; na verdade é Lichinga.", "identity.location", "Lichinga"),
    ("O meu projeto principal é o Kuvala.", "Isso está errado; é o Mapiko.", "project.main", "Mapiko"),
    ("My favourite colour is teal.", "No, it's amber.", "pref.color", "amber"),
]


@pytest.mark.parametrize("first,correction,key,value", REFERENCE_CORRECTIONS)
def test_a_bare_correction_updates_the_slot_it_refers_to(tmp_path, first, correction, key, value):
    got = _active(_store(tmp_path, first, correction))
    assert got.get(key) == value, got


def test_the_history_keeps_the_superseded_value(tmp_path):
    """A correction revises; it does not erase what was said."""
    st = _store(tmp_path, "I live in Nacala.", "That is incorrect; it's actually Lichinga.")
    assert _active(st).get("identity.location") == "Lichinga"
    assert any(h.get("prev") == "Nacala" or h.get("value") == "Nacala" for h in st.history("identity.location"))


def test_an_ambiguous_antecedent_changes_nothing(tmp_path):
    """Two slots written in the same message: which one is "it"? The honest answer is to leave both alone."""
    got = _active(_store(tmp_path, "I live in Nacala and my favourite colour is teal.",
                         "That is incorrect; it's actually Lichinga."))
    assert got.get("identity.location") == "Nacala", got
    assert got.get("pref.color") == "teal", got
    assert "Lichinga" not in str(got), got


def test_a_correction_with_no_replacement_changes_nothing(tmp_path):
    got = _active(_store(tmp_path, "I live in Nacala.", "That is incorrect."))
    assert got.get("identity.location") == "Nacala", got


def test_a_bare_correction_with_no_previous_write_changes_nothing(tmp_path):
    got = _active(_store(tmp_path, "That is incorrect; it's actually Lichinga."))
    assert got == {} or "Lichinga" not in str(got), got


def test_a_correction_naming_its_attribute_still_wins(tmp_path):
    """The explicit form must keep working — and must not be hijacked by the antecedent rule."""
    got = _active(_store(tmp_path, "I live in Nacala.", "My favourite colour is teal.",
                         "Actually, I live in Lichinga."))
    assert got.get("identity.location") == "Lichinga" and got.get("pref.color") == "teal", got


def test_a_third_party_correction_is_not_the_users(tmp_path):
    got = _active(_store(tmp_path, "I live in Nacala.", "My sister's city is wrong; it's actually Lichinga."))
    assert got.get("identity.location") == "Nacala", got


def test_an_intention_is_not_a_correction(tmp_path):
    got = _active(_store(tmp_path, "I live in Nacala.", "I want it to be Lichinga."))
    assert got.get("identity.location") == "Nacala", got
