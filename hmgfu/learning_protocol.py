"""The interactive learning controller — a PURE decision, so it can be tested without a model.

Phase 92.E3, per docs/INTERACTIVE_LEARNING_EXECUTION_V2.md §4. `decide` takes a snapshot of what the
turn already knows, an observation of what the user just did, and the proposals a perception step
offered, and returns what should happen. It performs NO database access, NO model call and NO tool
use: everything it needs is in its arguments, and everything it decides is in its return value. That
is what makes the enumerated transition table testable at all.

Three things this module deliberately does NOT do:

  * it never decides that something is true. It decides whether the user AUTHORISED a write, and
    which target that authorisation reaches. The stores remain the truth.
  * it never invents an identifier. Case ids come from the caller; a proposal naming a case the
    snapshot did not present is refused, because a model that can mint ids can confirm its own work.
  * it never treats a missing or malformed field as agreement. Absence is `protocol_unavailable`,
    which is a refusal to act, not a silent confirmation.

The envelope is validated strictly and separately (`validate_envelope`) so that a structurally valid
message still has to survive the decision, and a structurally invalid one never reaches it.
"""
from __future__ import annotations

import re

from typing import List, Optional

# limits, centralised and documented (plan §1.2). They are contract, not tuning knobs.
MAX_ATTEMPTS_PER_CASE = 2
MAX_EXAMPLES_PER_INTERPRETATION = 2
MAX_ACTIVE_EXAMPLES = 100

ACTIONS = ("pass_through", "ask", "commit", "reject", "defer", "invalidate", "protocol_unavailable")
STATES = ("proposed", "awaiting", "committed", "rejected", "deferred", "invalidated")


class Decision(dict):
    """A plain mapping so callers and tests can compare it literally."""

    @property
    def action(self) -> str:
        return self["action"]


def _d(action: str, reason: str, **kw) -> Decision:
    out = Decision(action=action, reason=reason, owner=kw.pop("owner", None),
                   handled_targets=kw.pop("handled_targets", []),
                   blocked_proposals=kw.pop("blocked_proposals", []),
                   independent_writes=kw.pop("independent_writes", []),
                   question=kw.pop("question", None), case_id=kw.pop("case_id", None))
    out.update(kw)
    return out


# 93.P2: the evidence half lives in its own module now; re-exported so existing imports work.
from .learning_evidence import (AMBIGUITY, EVIDENCE_REF, FEEDBACK, KINDS,  # noqa: E402,F401
                                MAX_PROPOSALS_PER_TURN, SCOPES, _AUTHORISING_ORIGINS, _bound,
                                _pending_for_session, _span_of, answering_case, attach_evidence,
                                evidence_problem, resolve_evidence,
                                validate_envelope)

def decide(snapshot: dict, env: dict) -> Decision:
    """The whole transition table of plan §4.1, as one pure function."""
    bad = validate_envelope(env)
    if bad:
        return _d("protocol_unavailable", bad)

    feedback = env["feedback"]
    scope = env["scope"]
    proposals = list(env.get("proposals") or [])
    ambiguity = env.get("ambiguity", "none")
    pending = _pending_for_session(snapshot)
    plan_pending = bool(snapshot.get("plan_pending"))
    resolved = snapshot.get("evidence") or {}

    # 95.29b/c: a denied value is a denial whatever else the perceiver says about the turn -- its
    # ambiguity flag or its feedback label. A fresh proposal whose evidence is negated is asked about
    # ("what is it now?") with every proposal blocked, before any reading can build a confirmation
    # question out of it or commit it as a retraction/correction.
    if proposals and not pending:
        for p in proposals:
            why = evidence_problem(p, resolved, snapshot.get("store_revision"))
            if why and "negated" in why:
                return _d("ask", f"the message denies a value and states no new one: {why}", owner="memory",
                          question=f"Noted: {p.get('subject_ref') or 'it'} is no longer {p.get('value')}. What is it now?",
                          blocked_proposals=[q.get("relation") for q in proposals], blocked_all=True)

    # 92.E3(B): an UNRESOLVED conflict blocks everything that writes, whatever the feedback says. A
    # classification of the feedback must not cancel a conflict signal. Refusals still pass, because
    # blocking the write is the point and swallowing a "no" would lose the user's answer.
    writes = feedback in ("confirm", "correct", "retract", "approve_behavior") or (
        feedback == "none" and proposals)
    if ambiguity != "none" and writes:
        if pending and feedback == "none":
            return _d("defer", "a question is already open for this session; the conflict waits",
                      case_id=pending["id"])
        if (snapshot.get("attempts") or 0) >= MAX_ATTEMPTS_PER_CASE:
            return _d("pass_through", "the clarification limit is reached and the conflict stands; "
                                      "the gap is explained instead of written")
        return _d("ask", f"unresolved {ambiguity}: nothing is written until it is settled",
                  owner="memory", case_id=(pending or {}).get("id"),
                  question=snapshot.get("proposed_question"),
                  blocked_proposals=[p.get("relation") for p in proposals])

    # --- feedback that refers to a case ---------------------------------------------------------
    if feedback in ("confirm", "reject", "correct", "retract", "approve_behavior", "resume_case"):
        target = env.get("target_case_id")
        if target and (not pending or pending.get("id") != target):
            return _d("protocol_unavailable",
                      "the answer names a case this session was not shown")
        # 93.X: `confirm`, `reject` and `resume_case` are ANSWERS -- without a question they mean
        # nothing, and that stays true below. A RETRACTION is a statement: the user can simply say it,
        # and it carries its own target. Lumping the two together is why "please forget about ACME-7"
        # wrote nothing three times while the reply said it had. It is supported the way a correction
        # is -- through `evidence_problem`, so an unbound target still authorises nothing.
        if feedback == "retract" and not pending and proposals:
            for p in proposals:
                why = evidence_problem(p, resolved)
                if why == "no evidence reference":          # 95.58: the message names no such target -- nothing to
                    return _d("pass_through", "the retraction names nothing said in this message",   # drop, and no
                              blocked_proposals=[q.get("relation") for q in proposals])          # question invented
                if why:
                    return _d("ask", f"the retraction is not supported: {why}", owner="memory",
                              question="Which record should I drop, and where did you say so?")
            return _d("commit", "retracts the target the user named", owner="memory",
                      handled_targets=[p.get("subject_ref") for p in proposals],
                      operation="retract")
        if not pending:
            # a bare "yes" with nothing pending must not approve anything, least of all a plan
            if plan_pending:
                return _d("pass_through", "no memory question is pending: the plan owns this feedback",
                          owner="plan")
            return _d("pass_through", "no pending case: nothing to confirm")
        if plan_pending and scope not in ("memory", "behavior"):
            return _d("ask", "a plan and a memory question are both pending; one yes cannot approve both",
                      owner="ambiguous", case_id=pending["id"],
                      question="Is that a yes to the memory update, or to the plan?")
        if pending.get("revision") != snapshot.get("store_revision"):
            return _d("invalidate", "the revision moved since the question was asked",
                      case_id=pending["id"])
        if pending.get("state") == "invalidated":
            return _d("invalidate", "the case was revoked and cannot be resurrected",
                      case_id=pending["id"])
        if feedback == "confirm":
            if not (pending.get("proposals") or []):      # 95.29: a yes does not supply the value that was asked for
                return _d("ask", "a confirmation supplies no value: the question stands", owner="memory",
                          case_id=pending["id"], question=pending.get("question"))
            return _d("commit", "confirmed exactly the proposition that was asked",
                      owner="memory", case_id=pending["id"],
                      handled_targets=pending.get("targets") or [])
        if feedback == "reject":
            return _d("reject", "rejected; the previous state is preserved",
                      owner="memory", case_id=pending["id"])
        if feedback == "retract":
            return _d("commit", "retracts only the target the question identified",
                      owner="memory", case_id=pending["id"],
                      handled_targets=pending.get("targets") or [], operation="retract")
        if feedback == "approve_behavior":
            return _d("commit", "behaviour approved through the behaviour adapter",
                      owner="behavior", case_id=pending["id"])
        if feedback == "resume_case":
            return _d("ask", "resuming the question that is still pertinent",
                      owner="memory", case_id=pending["id"], question=pending.get("question"))
        # correct: "no, it is Y" -- it writes, so its proposal needs support too
        for p in proposals:
            why = evidence_problem(p, resolved)
            if why:
                return _d("ask", f"the correction is not supported: {why}", owner="memory",
                          case_id=pending["id"], question="Which value should I record, and from where?")
        if len(proposals) != 1:
            return _d("ask", "the correction does not identify a single target",
                      owner="memory", case_id=pending["id"],
                      question="Which one should I change, and to what?")
        return _d("commit", "corrects the single identified target", owner="memory",
                  case_id=pending["id"], handled_targets=[proposals[0].get("relation")],
                  operation="correct")

    if feedback == "uncertain":
        return _d("defer", "uncertainty is not agreement and is not a refusal",
                  case_id=(pending or {}).get("id"))

    if feedback == "complain":
        targets = snapshot.get("complaint_targets") or []
        if len(targets) == 1:
            return _d("commit", "the complaint identifies one effect and its record",
                      owner="behavior", handled_targets=targets, operation="revoke")
        if not targets:
            return _d("pass_through", "a complaint with no identified effect changes nothing")
        return _d("ask", "several rules could have produced that effect",
                  owner="behavior", question="Which of those should I drop?")

    # --- no feedback: this turn may still teach something ----------------------------------------
    if snapshot.get("praise_only"):
        return _d("pass_through", "generic praise confirms no fact and trains nothing")

    if not proposals:
        return _d("pass_through", "nothing proposed")

    if ambiguity != "none":
        if pending:
            return _d("defer", "a question is already open for this session",
                      case_id=pending["id"])
        if (snapshot.get("attempts") or 0) >= MAX_ATTEMPTS_PER_CASE:
            return _d("pass_through", "the clarification limit for this case is reached; "
                                      "the gap is explained instead of asked again")
        return _d("ask", f"the proposal is ambiguous on {ambiguity}",
                  owner="memory", question=snapshot.get("proposed_question"),
                  blocked_proposals=[p.get("relation") for p in proposals])

    # 92.E3(A): every proposal must be supported by evidence the CALLER could resolve
    for p in proposals:
        why = evidence_problem(p, resolved, snapshot.get("store_revision"))   # a negated one was asked about above (95.29b)
        if why:
            return _d("pass_through", f"unsupported proposal: {why}",
                      blocked_proposals=[q.get("relation") for q in proposals])
    # a literal, fully evidenced teaching may be stored directly; an INFERENCE may not
    inferred = [p for p in proposals if p.get("operation") == "infer"]
    direct = [p for p in proposals if p.get("operation") != "infer"]
    if inferred and not direct:
        return _d("ask", "an inferred interpretation needs confirmation before it is stored",
                  owner="memory", question=snapshot.get("proposed_question"),
                  blocked_proposals=[p.get("relation") for p in inferred])
    return _d("commit", "explicit and evidenced: stored without a routine question",
              owner="memory", handled_targets=[p.get("relation") for p in direct],
              blocked_proposals=[p.get("relation") for p in inferred],
              independent_writes=[p.get("relation") for p in direct])


def next_state(current: str, action: str) -> str:
    """The case lifecycle, kept beside the decision so both are read together."""
    if current not in STATES:
        raise ValueError(f"unknown state {current!r}")
    table = {
        ("proposed", "ask"): "awaiting",
        ("proposed", "commit"): "committed",
        ("proposed", "reject"): "rejected",
        ("proposed", "defer"): "deferred",
        ("awaiting", "commit"): "committed",
        ("awaiting", "reject"): "rejected",
        ("awaiting", "defer"): "deferred",
        ("awaiting", "ask"): "awaiting",
        ("deferred", "ask"): "awaiting",
        ("deferred", "commit"): "committed",
    }
    if action == "invalidate":
        return "invalidated"
    return table.get((current, action), current)


def receipt(action: str, *, kind: str = "", target: str = "", revision=None,
            available: bool = False) -> dict:
    """An honest receipt: `received` is not `committed`, and availability is stated, not implied."""
    status = {"commit": "committed", "ask": "pending_clarification", "reject": "rejected",
              "defer": "received", "pass_through": "received", "invalidate": "invalidated",
              "protocol_unavailable": "unavailable"}.get(action, "received")
    out = {"status": status}
    if status == "committed":
        out.update({"kind": kind, "target": target, "revision": revision,
                    "available_for_reading": bool(available)})
    return out
