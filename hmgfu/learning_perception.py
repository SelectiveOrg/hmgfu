"""93.R4 — what PERCEPTION reads from the learning state: confirmed meanings, and the open question.

Split out of the sensitizer, which reached its module ceiling. The sensitizer assembles the
router's context; deciding what the case store has to offer it is a separate job, and keeping it
here means the reads can be tested without building a sensitizer at all.

Nothing here authorises anything: a confirmed interpretation says how to READ a new wording, and
an outstanding question says what a bare yes would be answering.
"""
from __future__ import annotations

import json
import logging

from .turn_router import reraise_if_ours

log = logging.getLogger("hmgfu.learning_perception")


def learning_on(engine) -> bool:
    """Whether the envelope belongs in this turn's contract at all."""
    if engine is None:
        return False
    try:
        return str(engine.settings.get("interactive_learning_mode") or "off").lower() in (
            "confirm", "adapt")
    except Exception as exc:
        reraise_if_ours(exc)
        return False


def pending_question(engine, session_id: str) -> str:
    """The question this session was ASKED and has not answered, or "".

    Delivered only: a question the user never saw cannot be what a bare yes answers, and another
    session's question is not this one's."""
    if engine is None or not session_id:
        return ""
    try:
        from .learning_state import LearningState, _db_path_of
        state = LearningState(_db_path_of(engine.facts._db), create=False)
        try:
            case = state.active_question(session_id)
        finally:
            state.close()
    except Exception as exc:
        reraise_if_ours(exc)
        return ""
    if not case or not case.get("question_delivered"):
        return ""
    return str(case.get("question") or "")


def pending_needs(engine, session_id: str) -> str:
    """WHICH property the outstanding question is asking for, or "" when it asks for a confirmation.

    93.Q2: `question_for` asks two different questions and only one of them can be answered with a
    word. The case has recorded which since 93.P3; this is that field, read the same way and under
    the same guards, so no new state exists to keep in step."""
    if engine is None or not session_id:
        return ""
    try:
        from .learning_state import LearningState, _db_path_of
        state = LearningState(_db_path_of(engine.facts._db), create=False)
        try:
            case = state.active_question(session_id)
        finally:
            state.close()
    except Exception as exc:
        reraise_if_ours(exc)
        return ""
    if not case or not case.get("question_delivered"):
        return ""
    return str(case.get("needs") or "")


def confirmed_examples(engine) -> str:
    """Up to two confirmed interpretations, or "" in every mode except adapt."""
    if engine is None:
        return ""
    try:
        if str(engine.settings.get("interactive_learning_mode") or "off").lower() != "adapt":
            return ""
        from .learning_examples import (derive_example, eligible_examples,
                                        example_is_advisory)
        from .learning_state import LearningState
        st = LearningState(conn=engine.facts._db, create=False)
        if not st._has_table():
            return ""
        rows = st._db.execute("SELECT id, revision, payload_json FROM learning_cases "
                              "WHERE state='committed' ORDER BY rowid DESC LIMIT 40").fetchall()
        made = []
        for cid, rev, payload in rows:
            data = json.loads(payload or "{}")
            for p in data.get("proposals") or []:
                made.append(derive_example(
                    {"id": cid, "state": "committed", "revision": rev, "question_delivered": True,
                     "teaching_was_explicit": True, "expression": data.get("expression") or ""},
                    {"action": "commit"}, [p]))
        picked = eligible_examples([e for e in made if e],
                                   context_ref=(made[0] or {}).get("context_ref") if made else None)
        return chr(10).join(
            f"- \"{(e.get('expression') or '').strip()}\" was confirmed to define "
            f"{e.get('subject_ref')} as {e.get('value')} (in {e.get('scope')})"
            for e in picked if example_is_advisory(e))
    except Exception as exc:
        reraise_if_ours(exc)
        log.warning("learning examples unavailable (%s)", exc)
        return ""
