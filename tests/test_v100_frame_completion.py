"""Phase 90.O — the DEV set `learn_v1` failed three conversations, all at the WRITE side, and all for the same reason:
an alternation inside an existing mould stops one form short of the frame it already recognises.

  employer   `fact_moulds` already reads "I work at X **as a Y**" (compound, writes company + job) and the negative
             "I no longer work at X" — but not the plain positive "I work at X."
  location   the home frame already reads "I am living in X", "residing in X" and the present perfect "my home has
             been X" — but not "I have lived in X (since 2022)".

The hypothesis under test is therefore NOT "add a sentence": it is that these are incomplete alternations, and
completing them adds the missing writes WITHOUT adding an undue one. The negatives below are the other half of the
claim — a third party, an intention, a question and a dated past must still write nothing.
"""

from __future__ import annotations

import pytest

from hmgfu.facts import FactStore


def _active(tmp_path, *messages):
    st = FactStore(str(tmp_path / "f.db"))
    for m in messages:
        st.apply_all(m, "user_explicit")
    return {f["key"]: f["value"] for f in st.active()}


WRITES = [
    ("I work at Kuvala.", "identity.company", "Kuvala"),
    ("I work for Kuvala.", "identity.company", "Kuvala"),
    ("Trabalho na Kuvala.", "identity.company", "Kuvala"),
    ("Eu trabalho na Kuvala.", "identity.company", "Kuvala"),
    ("I have lived in Tete since 2022.", "identity.location", "Tete"),
    ("I've lived in Tete since 2022.", "identity.location", "Tete"),
]


@pytest.mark.parametrize("text,key,value", WRITES)
def test_the_frame_completes(tmp_path, text, key, value):
    assert _active(tmp_path, text).get(key) == value, text


SILENT = [
    ("My brother works at Mapiko.", "third party"),
    ("O meu irmão trabalha na Mapiko.", "third party"),
    ("I want to work at Mapiko.", "intention"),
    ("We should work at Mapiko.", "proposal"),
    ("Do I work at Mapiko?", "question"),
    ("Until 2021 I worked at Mapiko.", "dated past"),
    ("For a story I am writing: I work at Mapiko.", "fiction"),
    ("My friend says 'I work at Mapiko'.", "citation"),
    ("I have lived in Aveiro, but not since 2019.", "negated"),
]


@pytest.mark.parametrize("text,kind", SILENT)
def test_the_completion_adds_no_undue_write(tmp_path, text, kind):
    got = _active(tmp_path, text)
    assert "Mapiko" not in str(got) and "Aveiro" not in str(got), f"{kind}: {got}"


def test_the_correction_sequence_still_supersedes(tmp_path):
    """The frame must behave like the ones beside it: a later assertion replaces the earlier value."""
    got = _active(tmp_path, "I work at Kuvala.", "Actually, I work at Mapiko now.")
    assert got.get("identity.company") == "Mapiko"
    got = _active(tmp_path, "I have lived in Tete since 2022.", "I live in Valencia now.")
    assert got.get("identity.location") == "Valencia"


AMBIGUOUS = [
    ("Trabalho no projeto Mapiko.", "pt: an explicit project noun must win over the employer frame"),
    ("Trabalho no projecto Mapiko.", "pt, European spelling"),
    ("I work on the Mapiko project.", "en: 'work on' is the project frame, not the employer one"),
    ("Estou a trabalhar no Mapiko.", "pt: an activity, not an employer"),
]


@pytest.mark.parametrize("text,why", AMBIGUOUS)
def test_the_employer_frame_never_swallows_a_project(tmp_path, text, why):
    assert _active(tmp_path, text).get("identity.company") is None, why
