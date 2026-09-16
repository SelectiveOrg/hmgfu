"""93.P1 (F2) — confirming a pending proposal must apply THAT proposal.

Reproduced by the independent review and again here, deterministically, with no model. A case is
awaiting, its question was delivered, and it holds a complete proposal: `ACME-7 = Atlas Control Mesh`.
The next turn is a confirmation — `feedback=confirm`, the right `target_case_id`, and NO proposals,
because the user is agreeing to something already proposed rather than teaching it again.

What happened: `decide` consulted the pending case and returned `commit`, but `apply_decision`
received only THIS turn's proposals — an empty list — so no adapter ran, `effects` came back empty,
and the receipt still said `committed`. `_persist` then wrote the payload with `proposals: []`,
erasing the very proposal that had just been confirmed.

The rules these tests hold, in the order they matter:

  * a confirmation applies the PRESERVED proposal, with its original evidence and the revision it was
    given against — the fact is never re-extracted from the word "yes", which is not the sentence the
    user taught;
  * the stored case keeps its proposal after being confirmed; a case that forgets what it committed
    cannot be audited;
  * `committed` is reported only when something was actually applied — the receipt has been wrong in
    exactly this way before, and an honest receipt is the whole point of 92.E3;
  * and none of this loosens a refusal: a rejection writes nothing, a moved revision loses, and a
    confirmation in another session does not reach this case.
"""
from __future__ import annotations

import json

import pytest

from hmgfu.learning_state import LearningState, run_learning_turn

TERM, MEANING = "ACME-7", "Atlas Control Mesh"
TAUGHT = f"In this project, {TERM} means {MEANING}."
PROPOSAL = {"kind": "domain_definition", "subject_ref": TERM, "context_ref": "project terminology",
            "value": MEANING, "evidence_refs": ["turn:1#30-48"]}
QUESTION = f"Is {TERM} the name you use for {MEANING} in this project?"


class _Query:
    def __init__(self, envelope):
        self.extraction = {"memory_update": envelope}


@pytest.fixture()
def engine(tmp_path):
    """A real engine on a throwaway base: the stores decide, not a stub."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import bench_say_do as sd

    db = str(tmp_path / "s.db")
    open(db, "wb").close()
    e = sd.fresh_engine(db, None)
    e.settings.set("interactive_learning_mode", "confirm")
    return e


def _awaiting(engine, session="s1", revision=None):
    """A case that asked a specific question about a complete proposal, and was delivered."""
    from hmgfu.learning_state import _db_path_of, store_revision

    state = LearningState(_db_path_of(engine.facts._db))
    rev = store_revision(engine.facts) if revision is None else revision
    case_id = state.open_case(session, rev, {"question": QUESTION, "proposals": [PROPOSAL],
                                             "expression": TAUGHT},
                              state="awaiting", question_turn_id="1")
    state.close()
    return case_id


def _definitions(engine):
    from hmgfu.learning_state import DEFINITION_RELATION
    return [a for a in engine.facts.assertions.active() if a.get("relation") == DEFINITION_RELATION]


def _confirm(engine, case_id, session="s1", text="yes", feedback="confirm"):
    return run_learning_turn(engine, session, text,
                             _Query({"feedback": feedback, "scope": "memory", "ambiguity": "none",
                                     "target_case_id": case_id, "proposals": []}),
                             turn_id="2")


def test_a_confirmation_writes_the_proposal_that_was_pending(engine):
    case_id = _awaiting(engine)
    out = _confirm(engine, case_id)
    assert out["decision"]["action"] == "commit"
    assert out["effects"], "the confirmed proposal never reached an adapter"
    assert any(d.get("value") == MEANING for d in _definitions(engine))


def test_the_receipt_says_committed_only_when_something_was_applied(engine):
    out = _confirm(engine, _awaiting(engine))
    assert out["receipt"]["status"] == "committed"
    assert out["receipt"]["available_for_reading"] is True


def test_the_case_keeps_the_proposal_it_committed(engine):
    from hmgfu.learning_state import _db_path_of

    case_id = _awaiting(engine)
    _confirm(engine, case_id)
    state = LearningState(_db_path_of(engine.facts._db), create=False)
    row = state._db.execute("SELECT state, payload_json FROM learning_cases WHERE id=?",
                            (case_id,)).fetchone()
    state.close()
    assert row[0] == "committed"
    assert json.loads(row[1])["proposals"], "the case forgot what it committed"


def test_the_fact_is_not_re_extracted_from_the_word_yes(engine):
    """"yes" is not the sentence the user taught, and must never be treated as one."""
    _confirm(engine, _awaiting(engine))
    values = [d.get("value") for d in _definitions(engine)]
    assert MEANING in values and not any("yes" == str(v).strip().lower() for v in values)


def test_a_rejection_writes_nothing(engine):
    out = _confirm(engine, _awaiting(engine), feedback="reject", text="no")
    assert out["decision"]["action"] != "commit"
    assert not _definitions(engine)


def test_an_uncertain_answer_writes_nothing(engine):
    out = _confirm(engine, _awaiting(engine), feedback="uncertain", text="maybe")
    assert out["decision"]["action"] != "commit"
    assert not _definitions(engine)


def test_a_confirmation_from_another_session_does_not_reach_this_case(engine):
    case_id = _awaiting(engine, session="s1")
    _confirm(engine, case_id, session="OTHER")
    assert not _definitions(engine), "another conversation approved this one's proposal"


def test_a_moved_revision_loses_rather_than_overwriting(engine):
    """The store changed under the question: the answer was given against a world that moved."""
    case_id = _awaiting(engine, revision=0)
    engine.facts.apply("My dog is called Green.", "user_explicit")
    out = _confirm(engine, case_id)
    assert out["decision"]["action"] != "commit" or not out["effects"]
