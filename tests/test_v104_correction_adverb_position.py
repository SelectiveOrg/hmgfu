"""Phase 91.S2 (first half) — a correction adverb must not depend on sitting at the front of the sentence.

From the independent audit (`reports/codex_execution_audit_20260909/ANALISE_E_PLANO.md` §3, P2): a correction phrased
"I actually live in Lichinga" failed even though it names the attribute explicitly. Reproduced deterministically:

    "Actually, I live in Lichinga."   -> writes Lichinga
    "I actually live in Lichinga."    -> writes nothing

So this half of the finding is NOT the antecedent problem the audit expected — no memory of "that is incorrect" is
needed, because the sentence names the attribute. The store already strips discourse markers from an assertion
(`_REAL_MARKER`), but only when they sit at the START. English puts them between the subject and the verb.

The negatives matter as much: "my real name is X" carries the fact in those words and must keep writing, and an
intention with the same adverb must stay an intention.
"""

from __future__ import annotations

import pytest

from hmgfu.facts import FactStore


def _active(tmp_path, *messages):
    st = FactStore(str(tmp_path / "f.db"))
    for m in messages:
        st.apply_all(m, "user_explicit")
    return {f["key"]: f["value"] for f in st.active()}


CORRECTIONS = [
    ("I actually live in Lichinga.", "identity.location", "Lichinga"),
    ("That is incorrect; I actually live in Lichinga.", "identity.location", "Lichinga"),
    ("I really live in Lichinga.", "identity.location", "Lichinga"),
    ("Eu na verdade moro em Lichinga.", "identity.location", "Lichinga"),
    ("Eu realmente moro em Lichinga.", "identity.location", "Lichinga"),
]


@pytest.mark.parametrize("text,key,value", CORRECTIONS)
def test_the_adverb_may_sit_between_subject_and_verb(tmp_path, text, key, value):
    assert _active(tmp_path, "I live in Nacala.", text).get(key) == value


@pytest.mark.xfail(reason="91.S2 limit, left visible instead of widened: the employer frame added in 90.O reads only "
                          "the singular subject, so 'We actually work at Chire.' strips the adverb correctly and then "
                          "matches nothing. That asymmetry belongs to the frame completion — which is NOT adopted — "
                          "and widening it here would be adding a rule to pass a test.", strict=True)
def test_the_plural_subject_is_a_known_gap_of_the_unadopted_frame(tmp_path):
    assert _active(tmp_path, "We actually work at Chire.").get("identity.company") == "Chire"


def test_the_front_position_still_works(tmp_path):
    assert _active(tmp_path, "I live in Nacala.", "Actually, I live in Lichinga.").get("identity.location") == "Lichinga"


def test_a_real_name_still_carries_its_own_fact(tmp_path):
    """"real name" is the attribute, not a discourse marker — stripping it would delete the fact."""
    assert _active(tmp_path, "My real name is Nadia Costa.").get("identity.name") == "Nadia Costa"


def test_an_intention_with_the_same_adverb_stays_an_intention(tmp_path):
    got = _active(tmp_path, "I live in Nacala.", "I actually want to move to Lichinga.")
    assert got.get("identity.location") == "Nacala", got
    assert "Lichinga" not in str(got), got


def test_a_third_partys_correction_is_still_theirs(tmp_path):
    got = _active(tmp_path, "I live in Nacala.", "My sister actually lives in Lichinga.")
    assert got.get("identity.location") == "Nacala", got
