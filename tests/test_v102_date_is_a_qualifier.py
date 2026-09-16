"""Phase 91.S1 — a date is a QUALIFIER, not a licence to turn fiction, a supposition or a citation into a fact.

Reproduced from the independent audit (`reports/codex_execution_audit_20260909/ANALISE_E_PLANO.md` §3, P1):
`sentence_modalities` tests `since/desde <year>` BEFORE `_FICTION` and `_HYPO` (`utterance.py:95`), so after
"I live in Nacala" both of these write Lichinga into the real ledger:

    In my novel, I have lived in Lichinga since 2022.
    Suppose I have lived in Lichinga since 2022.

The audit also showed the frame completion of 90.O made this reachable for `identity.location`, which is why that
completion must not be adopted until this is fixed. The repair belongs to the semantic contract — the date stops
deciding the modality and only supplies `valid_from` — not to an exception for the word "novel".

The legitimate dated assertion must keep working, with its date, in both languages: that is the other half of the
claim, and the reason a blanket block would be a worse bug than the one it fixes.
"""

from __future__ import annotations

import pytest

from hmgfu.facts import FactStore
from hmgfu.utterance import sentence_modalities, valid_from_of


def _active(tmp_path, *messages):
    st = FactStore(str(tmp_path / "f.db"))
    for m in messages:
        st.apply_all(m, "user_explicit")
    return {f["key"]: f["value"] for f in st.active()}


NOT_FACTS = [
    ("In my novel, I have lived in Lichinga since 2022.", "fiction"),
    ("In my story, I have worked at Zenvira since 2021.", "fiction"),
    ("No meu romance, moro em Lichinga desde 2022.", "fiction, pt"),
    ("Suppose I have lived in Lichinga since 2022.", "hypothesis"),
    ("Imagine I have lived in Lichinga since 2022.", "hypothesis"),
    ("Suponha que moro em Lichinga desde 2022.", "hypothesis, pt"),
    ("My friend says 'I have lived in Lichinga since 2022'.", "citation"),
]


@pytest.mark.parametrize("text,kind", NOT_FACTS)
def test_a_date_does_not_promote_a_non_assertion(tmp_path, text, kind):
    """The earlier value must survive: the sentence teaches the ledger nothing."""
    got = _active(tmp_path, "I live in Nacala.", text)
    assert got.get("identity.location") == "Nacala", f"{kind}: {got}"
    assert "Lichinga" not in str(got) and "Zenvira" not in str(got), f"{kind}: {got}"
    assert sentence_modalities(text)[-1]["modality"] != "assert", kind


DATED_FACTS = [
    ("I have lived in Lichinga since 2022.", "identity.location", "Lichinga", "2022-01-01"),
    ("Moro em Lichinga desde 2022.", "identity.location", "Lichinga", "2022-01-01"),
    ("Desde 2021 trabalho na Chire.", "identity.company", "Chire", "2021-01-01"),
]


@pytest.mark.parametrize("text,key,value,valid_from", DATED_FACTS)
def test_the_legitimate_dated_assertion_still_writes_with_its_date(tmp_path, text, key, value, valid_from):
    assert _active(tmp_path, "I live in Nacala.", text).get(key) == value
    assert valid_from_of(text) == valid_from


def test_the_date_still_qualifies_a_correction_sequence(tmp_path):
    """A dated assertion supersedes an earlier value, which is what the date is FOR."""
    got = _active(tmp_path, "I live in Nacala.", "I have lived in Lichinga since 2022.")
    assert got.get("identity.location") == "Lichinga"


def test_fiction_then_a_real_correction_in_the_same_message(tmp_path):
    """Clause scope: the novel sentence teaches nothing, the assertion beside it still does."""
    got = _active(tmp_path, "I live in Nacala.",
                  "In my novel, I have lived in Lichinga since 2022. Actually, I live in Chimoio now.")
    assert got.get("identity.location") == "Chimoio", got
