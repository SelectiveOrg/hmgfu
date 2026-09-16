"""93.R4 — what a confirmed commit EARNS: the examples mode `adapt` may offer perception.

Moved out of `learning_state`, which reached the module ceiling, because this is a separate
question: the store keeps cases and routes authorised proposals, while these three answer what
an example is, which ones may be shown, and why none of them authorises anything. Behaviour is
unchanged and `learning_state` re-exports the names, so existing imports keep working.
"""
from __future__ import annotations


EXAMPLE_MARKER = "learning:interpretation"


def derive_example(case: dict, decision, proposals) -> dict:
    """The example a CONFIRMED commit earns, or {} when it earns none.

    Only a human confirmation or correction mints one. The model's own reply, a tool result, a dream
    or generic praise are not confirmations, so a decision that did not commit -- or a case whose
    question was never delivered -- produces nothing."""
    action = decision.get("action") if isinstance(decision, dict) else getattr(decision, "action", None)
    if action != "commit" or not case:
        return {}
    if case.get("state") == "invalidated":
        return {}
    if not case.get("question_delivered") and not case.get("teaching_was_explicit"):
        return {}                      # no delivered question and no explicit teaching: nothing confirmed
    props = list(proposals or [])
    if not props:
        return {}
    p = props[0]
    return {"marker": EXAMPLE_MARKER, "case_id": case.get("id"),
            "expression": case.get("expression") or "",   # 92.E5c: the USER's wording or nothing
            "context_ref": p.get("context_ref"), "subject_ref": p.get("subject_ref"),
            "interpretation": p.get("relation"), "value": p.get("value"),
            "scope": p.get("context_ref") or "local",
            "evidence_refs": list(p.get("evidence_refs") or []),
            "revision": case.get("revision")}


def eligible_examples(examples, *, context_ref: str, revoked_cases=(), limit=None) -> list:
    """The examples that may be shown for this turn: same context, not revoked, newest first.

    Capped at MAX_EXAMPLES_PER_INTERPRETATION. Beyond MAX_ACTIVE_EXAMPLES the OLDEST become
    ineligible -- a documented policy, and deliberately not a deletion, so the proof survives."""
    from .learning_protocol import MAX_ACTIVE_EXAMPLES, MAX_EXAMPLES_PER_INTERPRETATION
    limit = MAX_EXAMPLES_PER_INTERPRETATION if limit is None else limit
    revoked = set(revoked_cases or ())
    live = [e for e in (examples or [])
            if e.get("marker") == EXAMPLE_MARKER
            and e.get("case_id") not in revoked
            and (e.get("context_ref") or "local") == (context_ref or "local")]
    live = live[-MAX_ACTIVE_EXAMPLES:]          # past the cap the oldest stop being offered
    return list(reversed(live))[:limit]


def example_is_advisory(example: dict) -> bool:
    """An example informs INTERPRETATION and nothing else.

    Stated as a predicate so a caller cannot quietly treat one as an authorisation: it carries no
    action, no tool, and no canonical write. Instructions inside its text are data, not commands."""
    return bool(example) and example.get("marker") == EXAMPLE_MARKER and not any(
        k in example for k in ("action", "tool", "authorises", "canonical"))
