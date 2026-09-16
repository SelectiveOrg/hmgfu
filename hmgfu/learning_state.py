"""Pendencies, provenance and receipts for the learning protocol — NOT another ledger of truth.

Phase 92.E3. `learning_cases` records what was proposed, what question was actually delivered, what
the user answered and which store revision the answer was given against. The truth itself stays in
FactStore, AssertionStore and DirectiveStore: this table can say "the user confirmed revision 9 of
that assertion", never "the value is X".

Three invariants are enforced here rather than left to callers:

  * AT MOST ONE ACTIVE QUESTION PER SESSION, by a partial unique index, so two turns racing cannot
    both open one and a later "yes" cannot be ambiguous between them.
  * COMPARE-AND-SWAP on `revision`. An answer given against a revision that has since moved FAILS;
    it does not overwrite, and it does not resurrect an invalidated case.
  * The table follows the CALLER'S transaction when a connection is passed, exactly as AssertionStore
    does, so a case and the store revision it authorises commit together or not at all.

Created lazily: a legacy base opened with the protocol off never gains the table (plan §1.2).
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Optional

from . import config
from .learning_protocol import STATES
from .db import connect as db_connect
from .models import now_iso

_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS learning_cases ("
    "id TEXT PRIMARY KEY, session_id TEXT NOT NULL, state TEXT NOT NULL, revision INTEGER NOT NULL, "
    "created_at TEXT, updated_at TEXT, origin_turn_id TEXT, question_turn_id TEXT, payload_json TEXT)"
)
# the one-active-question invariant, enforced by the database and not by a convention
_ACTIVE_INDEX = ("CREATE UNIQUE INDEX IF NOT EXISTS learning_cases_one_active "
                 "ON learning_cases (session_id) WHERE state = 'awaiting'")


def _db_path_of(conn):
    """The file a connection is attached to, so the case table can open one of its own."""
    try:
        for row in conn.execute("PRAGMA database_list").fetchall():
            if row[1] == "main":
                return row[2]
    except Exception:
        pass
    return None


class CaseConflict(RuntimeError):
    """Raised when a compare-and-swap fails: the revision moved, or the case is gone/invalidated."""


class LearningState:
    def __init__(self, db_path: Optional[str] = None, conn=None, create: bool = True):
        """`conn` given: write on the CALLER's connection and never commit, so the case and the
        store revision it authorises are one transaction. `create=False` opens read-only against a
        base that may not have the table at all -- which is how the protocol stays absent when off."""
        self._owns = conn is None
        self._db = conn if conn is not None else db_connect(db_path or config.DB_PATH)
        self._ready = False
        if create:
            self.ensure()

    def ensure(self) -> None:
        """Idempotent, and safe to call after the engine was built with the mode off."""
        if self._ready:
            return
        if self._owns:
            self._db.execute(_SCHEMA)
            self._db.execute(_ACTIVE_INDEX)
            self._db.commit()
        else:
            # 92.E4: schema is NOT part of the caller's logical transaction. Running it on a shared
            # handle without committing held a write transaction open across the turn.
            path = _db_path_of(self._db)
            if path:
                own = db_connect(path)
                try:
                    own.execute(_SCHEMA)
                    own.execute(_ACTIVE_INDEX)
                    own.commit()
                finally:
                    own.close()
        self._ready = True

    def _has_table(self) -> bool:
        row = self._db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='learning_cases'").fetchone()
        return row is not None

    # -- writes ----------------------------------------------------------------------------------
    def open_case(self, session_id: str, revision: int, payload: dict, *, state: str = "proposed",
                  origin_turn_id: str = "", question_turn_id: str = "") -> str:
        """Create a case. An id is minted HERE, never accepted from a model."""
        if state not in STATES:
            raise ValueError(f"unknown state {state!r}")
        self.ensure()
        case_id = uuid.uuid4().hex[:16]
        now = now_iso()
        try:
            self._db.execute(
                "INSERT INTO learning_cases (id, session_id, state, revision, created_at, updated_at, "
                "origin_turn_id, question_turn_id, payload_json) VALUES (?,?,?,?,?,?,?,?,?)",
                (case_id, session_id, state, int(revision), now, now, origin_turn_id,
                 question_turn_id, json.dumps(payload, ensure_ascii=False)))
        except sqlite3.IntegrityError as exc:
            raise CaseConflict("this session already has an active question") from exc
        if self._owns:
            self._db.commit()
        return case_id

    def transition(self, case_id: str, *, expect_revision: int, to_state: str,
                   payload: Optional[dict] = None, question_turn_id: Optional[str] = None) -> None:
        """Compare-and-swap. The revision the answer was given against must still be the one stored."""
        if to_state not in STATES:
            raise ValueError(f"unknown state {to_state!r}")
        self.ensure()
        row = self._db.execute("SELECT state, revision, payload_json FROM learning_cases WHERE id=?",
                               (case_id,)).fetchone()
        if row is None:
            raise CaseConflict("no such case")
        state, revision, payload_json = row[0], row[1], row[2]
        if state == "invalidated":
            raise CaseConflict("the case was invalidated and cannot be resurrected")
        if int(revision) != int(expect_revision):
            raise CaseConflict(f"revision moved: stored {revision}, answered against {expect_revision}")
        merged = json.loads(payload_json or "{}")
        if payload:
            merged.update(payload)
        try:
            self._db.execute(
                "UPDATE learning_cases SET state=?, updated_at=?, payload_json=?, question_turn_id=COALESCE(?, question_turn_id) "
                "WHERE id=? AND revision=? AND state<>'invalidated'",
                (to_state, now_iso(), json.dumps(merged, ensure_ascii=False), question_turn_id,
                 case_id, int(expect_revision)))
        except sqlite3.IntegrityError as exc:
            raise CaseConflict("another case is already awaiting in this session") from exc
        if self._owns:
            self._db.commit()

    def bump_revision(self, case_id: str, revision: int) -> None:
        """Record the revision a committed case actually reached, for the receipt."""
        self.ensure()
        self._db.execute("UPDATE learning_cases SET revision=?, updated_at=? WHERE id=?",
                         (int(revision), now_iso(), case_id))
        if self._owns:
            self._db.commit()

    # -- reads -----------------------------------------------------------------------------------
    def active_question(self, session_id: str) -> Optional[dict]:
        """The question this session is waiting on, or None. Absent table means absent protocol."""
        if not self._has_table():
            return None
        row = self._db.execute(
            "SELECT id, session_id, state, revision, payload_json, question_turn_id, origin_turn_id FROM learning_cases "
            "WHERE session_id=? AND state='awaiting'", (session_id,)).fetchone()
        if row is None:
            return None
        payload = json.loads(row[4] or "{}")
        return {"id": row[0], "session_id": row[1], "state": row[2], "revision": row[3],
                "question_turn_id": row[5], "question_delivered": bool(row[5]),
                "origin_turn_id": row[6], **payload}

    def get(self, case_id: str) -> Optional[dict]:
        if not self._has_table():
            return None
        row = self._db.execute(
            "SELECT id, session_id, state, revision, payload_json FROM learning_cases WHERE id=?",
            (case_id,)).fetchone()
        if row is None:
            return None
        return {"id": row[0], "session_id": row[1], "state": row[2], "revision": row[3],
                **json.loads(row[4] or "{}")}

    def close(self) -> None:
        if self._owns:
            self._db.close()


# --- 92.E3 adapters: route an AUTHORISED proposal to the store that owns that kind of truth --------
#
#   personal_fact     -> FactStore, through its public entry. No synthetic sentence is rebuilt to
#                        re-run a regex, and trusted=True is never used to bypass a rejection.
#   domain_definition -> AssertionStore, one entity per (context, term).
#   behavior_policy   -> DirectiveStore, as a TYPED policy, never text appended to a reply.
#
    # The stores are INJECTED: the engine owns them, and only AssertionStore takes a shared connection
    # today -- a second FactStore on the same file would contend for the write lock, not share it.
    # The adapters decide nothing; they act only on `commit`, which keeps an unresolved conflict or an
    # unsupported proposal from reaching a store at all.
# 93.Q2: the write adapters live in `learning_apply` now, and are imported back so that every
# caller that has always found them here still does.
from .learning_apply import (DEFINITION_RELATION, apply_decision,  # noqa: E402,F401
                             definition_entity_key, deliver_question, read_definition)
# --- 92.E5: examples of confirmed interpretations (mode L) ----------------------------------------
# 93.R4: the examples live in their own module now; re-exported so existing imports keep working.
from .learning_evidence import known_subjects, question_for_turn, needs_of  # noqa: F401
from .learning_examples import (EXAMPLE_MARKER, derive_example, eligible_examples,  # noqa: F401
                                example_is_advisory)


EVIDENCE_REF = "turn"          # refs look like  turn:<turn_id>#<start>-<end>


def store_revision(facts) -> int:
    """A monotonic integer that changes whenever anything the protocol authorises could have moved.

    Used for compare-and-swap: an answer given against one revision must not land on another. It is
    deliberately cheap and derived from the stores themselves rather than kept as separate state."""
    try:
        a = facts._db.execute("SELECT COUNT(*) FROM fact_history").fetchone()[0]
        b = facts._db.execute("SELECT COUNT(*) FROM assertions").fetchone()[0]
        return int(a) + int(b)
    except Exception:
        return 0


def run_learning_turn(engine, session_id: str, text: str, query, *, source: str = "user_explicit",
                      turn_id: str = "", plan_pending: bool = False, tool_receipts=None):
    """Run one turn of the protocol. Returns None when the mode is off, so S is unchanged.

    Order follows the plan: snapshot BEFORE any approval is consumed, decision and commit BEFORE the
    reply context is built, and a receipt that reports what happened rather than what was intended.

    The case table uses its OWN connection. Writing case rows on the engine's handle without
    committing held a write transaction open for the rest of the turn. The cost is that a case and
    the store revision it authorises are no longer one transaction; that is recorded as pending, not
    quietly dropped."""
    from .learning_protocol import (answering_case, attach_evidence, decide, receipt,
                                    resolve_evidence)
    mode = str((engine.settings.get("interactive_learning_mode") or "off")).lower()
    if mode not in ("confirm", "adapt"):
        return None
    env = (getattr(query, "extraction", None) or {}).get("memory_update")
    facts = engine.facts
    for p in ((env or {}).get("proposals") or []):        # 95.21: a context is a NAME, not the message
        ctx, subj = " ".join(str(p.get("context_ref") or "").split()).casefold(), str(p.get("subject_ref") or "").casefold()
        if ctx and (ctx == " ".join((text or "").split()).casefold() or (subj and subj in ctx)):
            p["context_ref"] = None                        # the whole message / the subject itself names no setting
    from .learning_apply import ledger_grounded_denials  # 95.45: a denial the ledger can see is proposed as such
    denied = ledger_grounded_denials(facts, text, (env or {}).get("proposals"))
    if denied:
        env = {**(env or {}), "feedback": (env or {}).get("feedback") or "none", "scope": (env or {}).get("scope") or "memory",
               "ambiguity": (env or {}).get("ambiguity") or "none",
               "proposals": [dict(d, evidence_refs=[r.replace("{turn}", str(turn_id)) for r in d["evidence_refs"]]) for d in denied]
               + list((env or {}).get("proposals") or [])}
    if not ((env or {}).get("proposals") or []):          # 95.20: the perceiver returned no proposal --
        from .learning_apply import ledger_grounded_proposals, stated_definitions   # a revision of a term the ledger
        derived = ledger_grounded_proposals(getattr(facts, "assertions", None), text) or stated_definitions(text)   # defines,
        if derived:                                                     # or (95.67) a stated definition of a code-like term
            from .learning_evidence import _modality_of
            for p in derived:
                p["evidence_refs"] = [r.replace("{turn}", str(turn_id or "")) for r in p["evidence_refs"]]
            cited = any(_modality_of(str(p.get("value") or ""), text) not in ("assert", None) for p in derived)
            env = {"feedback": "none", "scope": "memory", "target_case_id": None, **(env or {}),
                   "ambiguity": "unsupported" if cited else (env or {}).get("ambiguity") or "none", "proposals": derived}
    if (env or {}).get("feedback") == "retract":          # 95.62c: a retraction that DENIES a value the ledger does not hold
        from .learning_apply import denied_definition, held_definition            # for the subject retracts nothing
        den = denied_definition(text)
        if den and str(held_definition(getattr(facts, "assertions", None), den[0]) or "").casefold() != den[1].casefold():
            env = {**env, "feedback": "none", "proposals": []}
    if (env or {}).get("feedback") == "retract":          # 95.62: a retraction that STATES a replacement is a correction
        from .learning_apply import _is_the_message
        from .learning_evidence import _modality_of
        from .utterance import _NEG_GOV                    # 95.62b: a value holding its subject or a negation is a CLAIM,
        for p in (env.get("proposals") or []):             # not a value -- a retraction carries none (93.X)
            v = str(p.get("value") or "") if isinstance(p, dict) else ""
            if v.strip() and (_NEG_GOV.search(v.casefold()) or (str(p.get("subject_ref") or "").strip()
                                                                  and str(p["subject_ref"]).strip().casefold() in v.casefold())):
                p["value"] = ""
        if any(str(p.get("value") or "").strip() and not _is_the_message(p.get("value"), text)
               and _modality_of(str(p["value"]), text) == "assert" for p in (env.get("proposals") or []) if isinstance(p, dict)):
            env = {**env, "feedback": "none"}              # the value binds (93.Q2) and supersedes; a bare retraction is unchanged
    state = LearningState(conn=facts._db)      # SHARED: the case and the assertion are one transaction
    try:
        rev = store_revision(facts)
        pending = state.active_question(session_id)
        # 93.P3: a bare answer to a question THIS session asked and delivered is recognised without
        # the model, as the standing goal allows when the pending case is unambiguous. It yields a
        # FEEDBACK only -- never a proposal -- so the write still comes from the proposal already on
        # the case, with the evidence it was given. A composite or qualified reply is not a bare
        # answer and goes to the model untouched; and a plan proposal waiting at the same time is the
        # ambiguity `begin_turn` already refuses, before this runs.
        if pending:
            from .learning_answer import simple_feedback
            answered = simple_feedback(text, pending)
            if answered and not ((env or {}).get("proposals") or []):
                env = dict(env or {}, feedback=answered, target_case_id=pending.get("id"))
                env.setdefault("scope", "memory")
                env.setdefault("ambiguity", "none")
        # 93.Q2: the model proposes a value, the SYSTEM locates it -- in this message, or in the
        # words the pending question preserved when the reply is an elliptical answer to it. The
        # case is filtered by session first, so another conversation's pendency evidences nothing.
        answering = answering_case(pending, session_id)
        env = attach_evidence(env, text, turn_id, pending=answering)
        resolved_evidence = resolve_evidence(env, text, turn_id, rev, tool_receipts=tool_receipts,
                                             known_subjects=known_subjects(facts),
                                             pending=answering)
        snapshot = {"session_id": session_id, "store_revision": rev, "pending_case": pending,
                    "plan_pending": bool(plan_pending),
                    "attempts": int((pending or {}).get("attempts") or 0),
                    "proposed_question": question_for_turn(env, resolved_evidence),
                    "needs": needs_of(env, resolved_evidence),
                    "praise_only": bool((env or {}).get("praise_only")),
                    "evidence": resolved_evidence}
        # an ABSENT envelope is protocol_unavailable, never an invented confirmation (plan sec.9)
        decision = decide(snapshot, env if isinstance(env, dict) else None)
        proposals = (env or {}).get("proposals") or []
        # 93.P1: confirming is not teaching again. When the turn approves a PENDING case and carries no
        # proposal of its own, the proposal that was actually confirmed is the one already stored --
        # with its original evidence and the wording the user taught. Re-deriving it from "yes" would
        # look for the value in a word that does not contain it, and `_persist` would then overwrite
        # the case with an empty list, erasing what it had just committed.
        applied, source_text = proposals, text
        if not proposals and decision["action"] == "commit" and pending:
            applied = list(pending.get("proposals") or [])
            source_text = str(pending.get("expression") or text)
        effects = apply_decision(decision, applied, facts=facts, assertions=facts.assertions,
                                 directives=engine.directives, text=source_text, session=session_id)
        case_id = _persist(state, decision, snapshot, applied, session_id, rev, turn_id, source_text)
        kind = (applied[0].get("kind") if applied else "")
        rec = receipt(decision["action"], kind=kind,
                      target=(decision.get("handled_targets") or [""])[0],
                      revision=store_revision(facts), available=bool(effects))
            # 92.E4: the protocol's writes are ONE transaction, committed HERE. Sharing the engine's
            # handle makes the case and the assertion atomic; leaving it open held the write lock for
            # the rest of the turn ("database is locked"). facts.apply_all commits itself, after this.
        facts._db.commit()
        return {"decision": decision, "effects": effects, "receipt": rec, "case_id": case_id,
                "question": decision.get("question"), "mode": mode, "db_path": _db_path_of(facts._db),
                "applied_proposals": applied}
    finally:
        pass


def _persist(state, decision, snapshot, proposals, session_id, revision, turn_id, text: str = ""):
    """Record the case. A question only counts as delivered once the caller says it was.

    92.E5c: `text` is the USER's sentence. An example carrying only a value pair cannot tell a router
    how a NEW wording of the same thing reads, which is what the C/L comparison measured and missed.
    The assistant's proposed question stays under `question`, unusable as a confirmed wording."""
    from .learning_protocol import next_state
    action = decision["action"]
    pending = snapshot.get("pending_case")
    # 93.Q2: `transition` MERGES this payload into the case, so a key present-but-empty erases what
    # the case was preserving. A bare "no" or "maybe" carries no proposal, no question and no needs,
    # and the probe's own case rows showed all three overwritten with emptiness -- a deferred case
    # that has forgotten its own question cannot be answered later by anyone. 93.P1 fixed exactly this
    # for `commit`; reject and defer went on writing the same emptiness. So only what this turn
    # actually produced is written, and `reason` alone always is, because it describes THIS
    # transition rather than the case's content.
    payload = {"reason": decision.get("reason")}
    if decision.get("blocked_all"):                          # 95.29: nothing is kept for a later "yes" to commit
        payload["blocked"], proposals = list(proposals or []), []
    for key, value in (("proposals", proposals), ("question", decision.get("question")),
                       ("expression", text or ""),
                       ("needs", snapshot.get("needs"))):    # 93.P3: which act a later answer answers
        if value:
            payload[key] = value
    try:
        if pending and action in ("commit", "reject", "defer", "invalidate", "ask"):
            state.transition(pending["id"], expect_revision=pending.get("revision", revision),
                             to_state=next_state(pending.get("state", "awaiting"), action),
                             payload=payload)
            return pending["id"]
        if action in ("ask", "commit", "defer") and (proposals or payload.get("blocked")):
            return state.open_case(session_id, revision, payload,
                                   state=next_state("proposed", action), origin_turn_id=turn_id)
    except CaseConflict:
        return None                       # a concurrent update wins; nothing is overwritten
    return None
