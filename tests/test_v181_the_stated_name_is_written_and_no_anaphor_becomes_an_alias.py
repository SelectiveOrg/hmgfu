"""R2 / 95.12 — ANALYSIS F1: "the write happened, but not the write that was promised".

Reproduced on CPU with the real sentence: *"my real name is actually teodoro h. ferreira. and i want
you to start calling me with that name for now on"* writes `identity.alias = 'with'` and leaves
`identity.name` unchanged. Two links, both in the deterministic detector:

  1. `_NAME_EXPLICIT` captures the value right after "my real name is", so the hedge "actually" enters
     the value and the name-shape gate rejects it. `_clean_value` strips a TRAILING "actually"
     (83.2) and has no leading twin.
  2. the `calling me` mould captures "with that name for now on": a value that STARTS with a
     preposition is an anaphor, not a value. `_PREP_CUT` trims a preposition inside a value and is
     never applied at the value's start.

Invariant (guide §4 "compreender -> guardar"): the value stated is the value written; a reference to a
value ("that name") is not a value. Symmetric extensions of rules that exist; no new lists.
"""
from __future__ import annotations

import tempfile
import pathlib

import pytest

from hmgfu.facts import FactStore

F1 = ("my real name is actually teodoro h. ferreira. and i want you to start calling me with that "
      "name for now on")


def _store():
    return FactStore(str(pathlib.Path(tempfile.mkdtemp()) / "r2.db"))


def _active(fs):
    return {f["key"]: f["value"] for f in fs.active()}


def test_the_real_sentence_writes_the_name_and_no_junk_alias():
    """THE CONTRACT — fails before: alias='with', name untouched."""
    fs = _store()
    fs.apply_all("my name is Nora.", "user", session="s1")
    fs.apply_all(F1, "user", session="s1")
    a = _active(fs)
    assert a.get("identity.name", "").casefold() == "teodoro h. ferreira", a
    assert a.get("identity.alias", "").casefold() != "with", a


def test_a_leading_hedge_does_not_enter_the_name():
    fs = _store()
    fs.apply_all("my real name is actually Sebastian.", "user", session="s1")
    assert _active(fs).get("identity.name") == "Sebastian"


def test_a_value_that_starts_with_a_preposition_is_not_an_alias():
    """NEGATIVE — 'call me when you can' / 'call me with the results' name nothing."""
    fs = _store()
    fs.apply_all("call me when you can.", "user", session="s1")
    fs.apply_all("call me with the results tomorrow.", "user", session="s1")
    assert "identity.alias" not in _active(fs)


@pytest.mark.parametrize("text,alias", [("call me Teo from now on", "Teo"), ("Just call me T.", "T")])
def test_a_real_alias_is_still_written(text, alias):
    """PRESERVE — 83.2's cases."""
    fs = _store()
    fs.apply_all(text, "user", session="s1")
    assert _active(fs).get("identity.alias") == alias


def test_a_trailing_hedge_is_still_stripped():
    fs = _store()
    fs.apply_all("my name is Petra actually", "user", session="s1")
    assert _active(fs).get("identity.name") == "Petra"
