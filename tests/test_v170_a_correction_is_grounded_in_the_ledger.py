"""95.1b — the derivatives of a superseded value are demoted by the ledger's own supersession.

Located on one execution (c951 rep2, turn 2). The protocol committed the definition and the assertion
store superseded `ACME-7 · definition.meaning: Atlas Control Mesh → Adaptive Cache Manager` — subject,
attribute, old and new value all correct. Yet the assistant's echo *"I've noted that ACME-7 stands for
Atlas Control Mesh"* stayed active: the grader's `_apply_correction` fed `supersede_named_stale` the
nano's free PHRASE ("what the user said is wrong"), matched as a raw substring, so only points that
REPEAT the user's wording were demoted. Replayed on a copy of the real graph: with the phrase, no
further target; with the ledger's value, the echo and a system summary are demoted too.

Invariant: derivatives of a superseded value are demoted by the ledger's supersession (subject +
attribute + revision), not by lexical luck. The change grounds `wrong`/`right` from the assertions this
message superseded — the successor carries the message as `source_span`, the predecessor's `valid_to`
equals its `recorded_at` — and falls back to the phrase only when the store recorded nothing.

Component fixture (guide §7: fixtures prove components; the natural-flow proof is chain L1). The store
is driven the way `learning_apply` drives it, with the same relation and entity key.
"""
from __future__ import annotations

import pytest

from hmgfu.grader import _apply_correction
from hmgfu.learning_apply import DEFINITION_RELATION, definition_entity_key
from tests.test_v2_agent import make_agent

A, B = "Atlas Control Mesh", "Adaptive Cache Manager"
TEACH = f"In this project, ACME-7 means {A}."
CORR = f"Correction: ACME-7 means {B}, not {A}."
# the nano's phrase-shaped perception, exactly as the live run had it
PHRASE = {"right": f"ACME-7 means {B}", "wrong": f"ACME-7 means {A}"}


def _teach_then_correct(engine):
    """Drive the store as learning_apply does: teach A from TEACH, then B from CORR."""
    a = engine.facts.assertions
    eid = a.upsert_entity("definition", definition_entity_key(None, "ACME-7"))
    a.assert_(eid, DEFINITION_RELATION, A, source_span=TEACH[:500])
    a.assert_(eid, DEFINITION_RELATION, B, source_span=CORR[:500])
    # The assertion store shares FactStore's connection and does not own its commits (82.2): in a turn a
    # later FactStore write commits; a fixture has to, or the graph's own connection waits 30 s on the lock.
    engine.facts._db.commit()
    return eid


def _memories(engine):
    """The real derivative shapes from the episode DB, plus the negative and the variant."""
    return {
        "teach": engine.ingest(TEACH, source="user", mtype="message"),
        "echo": engine.ingest(f"Understood. I've noted that ACME-7 stands for the {A} within this project.",
                              source="assistant", mtype="message"),
        "summary": engine.ingest(f"The term 'ACME-7' is clarified to refer to the {A}.",
                                 source="system", mtype="session"),
        "other": engine.ingest(f"Project Halcyon runs on the {A} as its backbone.", source="user",
                               mtype="message"),
        "history": engine.ingest(f"ACME-7 used to mean {A}; it now means {B}.", source="assistant",
                                 mtype="message"),
        "corr": engine.ingest(CORR, source="user", mtype="message"),
    }


def _status(engine, p):
    return engine.graph.points[p.id].status


def test_a_paraphrased_echo_is_demoted_when_the_ledger_superseded_the_value(tmp_path):
    """POSITIVE — fails before: the echo says 'stands for', not 'means', and survives the phrase."""
    engine, _ = make_agent(tmp_path, [])
    _teach_then_correct(engine)
    m = _memories(engine)
    _apply_correction(engine, dict(PHRASE), CORR)
    assert _status(engine, m["echo"]) == "superseded", "the assistant's echo of A is still current"
    assert _status(engine, m["summary"]) == "superseded", "the system summary of A is still current"


def test_the_same_value_on_another_entity_is_untouched(tmp_path):
    """NEGATIVE — Halcyon's backbone is not ACME-7's definition."""
    engine, _ = make_agent(tmp_path, [])
    _teach_then_correct(engine)
    m = _memories(engine)
    _apply_correction(engine, dict(PHRASE), CORR)
    assert _status(engine, m["other"]) == "active"


def test_a_history_naming_both_values_survives(tmp_path):
    """VARIANT — 'was A, now B' agrees with B and is history, not the error."""
    engine, _ = make_agent(tmp_path, [])
    _teach_then_correct(engine)
    m = _memories(engine)
    _apply_correction(engine, dict(PHRASE), CORR)
    assert _status(engine, m["history"]) == "active"


def test_the_literal_repeat_is_still_demoted_and_the_correction_still_stands(tmp_path):
    """PRESERVE — what was right before (94.x, 95.1) must not change."""
    engine, _ = make_agent(tmp_path, [])
    _teach_then_correct(engine)
    m = _memories(engine)
    _apply_correction(engine, dict(PHRASE), CORR)
    assert _status(engine, m["teach"]) == "superseded"
    assert _status(engine, m["corr"]) == "active"


def test_without_a_ledger_supersession_the_phrase_is_still_used(tmp_path):
    """PRESERVE — when the protocol recorded nothing this turn, the previous behaviour holds."""
    engine, _ = make_agent(tmp_path, [])
    m = _memories(engine)                       # no assertion written from CORR
    _apply_correction(engine, dict(PHRASE), CORR)
    assert _status(engine, m["teach"]) == "superseded"      # the literal repeat, as before
    assert _status(engine, m["echo"]) == "active"           # and the phrase's known limit, unchanged


def test_the_grounding_is_reported_not_silent(tmp_path):
    """Rule 10: the result says which values it grounded on, so a run can prove the path fired."""
    engine, _ = make_agent(tmp_path, [])
    _teach_then_correct(engine)
    _memories(engine)
    out = _apply_correction(engine, dict(PHRASE), CORR)
    assert out and out.get("grounded") == [(A, B)]


# --- 95.1b-ii: a quoted subject is still the subject --------------------------------------------------
#
# Found by the positive test above: the system summary "The term 'ACME-7' is clarified to refer to the
# Atlas Control Mesh." stayed active after the echo was demoted. `_words` kept the leading apostrophe,
# so the quoted subject became the token "'acme" and never overlapped the subject set.

def test_a_quoted_subject_overlaps_the_subject_set():
    from hmgfu.fact_nodes import _words
    assert "acme" in _words("The term 'ACME-7' is clarified to refer to the Atlas Control Mesh.")
    assert "acme" in _words("Correction: ACME-7 means Adaptive Cache Manager.")


def test_an_inner_apostrophe_is_kept():
    """i've / user's are one token each, as before."""
    from hmgfu.fact_nodes import _words
    words = _words("I've noted the user's project.")
    assert "i've" in words and "user's" in words and "project" in words
