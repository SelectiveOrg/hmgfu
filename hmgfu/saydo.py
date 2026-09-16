"""Say-do gate (Phase 67.2) — every claim in a reply is a contract checked against the turn's telemetry.

Live failures this closes: "I'll take a look at the project structure…" (intent, no tool, turn over);
"I've updated your car location link in my records" (execution claim, no ledger write).

Three claim classes, one deterministic pass after the tool loop:
  INTENT    — "I'll / let me / I'm going to / vou …" with NO tool this turn:
              read-only intents (look, check, inspect, read, search) are executed NOW (one more loop pass);
              side-effecting or multi-step intents become a PROPOSAL (session plan) + a one-line question.
  EXECUTION — "I've updated / created / saved …" must match a committed transaction this turn
              (ledger write, directive change, successful side-effect tool); otherwise the reply is
              corrected to the truth.
  VALUE     — numbers/URLs: grounding.py (Phase 66.2).
Deterministic, fail-soft, setting `saydo_gate_enabled`.
"""

from __future__ import annotations

import re
from typing import Optional

_INTENT = re.compile(r"\b(i'?ll|i will|let me(?! know)|i'?m going to|i am going to|i'?m (?:getting )?start(?:ing|ed)|i can take a look|i can check|"
                     r"vou|deixa-me|deixe-me|posso ver|posso verificar)\b", re.IGNORECASE)
_READ_ONLY = re.compile(r"\b(look|check|inspect|read|search|find|see|review|list|verify|ver|verificar|"
                        r"procurar|consultar|analisar|analyze|analyse|investigate|identify)\b", re.IGNORECASE)
# 69.3: execution claims are typed — each class must match the transaction that would make it true
_CLAIM_VERBS = {
    "remove": r"deleted|removed|erased|cleared|forgot|forgotten|apaguei|removi|retirei|esqueci|eliminei|apagad[oa]s?|removid[oa]s?",
    "create": r"created|built|set up|installed|written|wrote|generated|criei|constru[ií]|escrevi|instalei|gerei|criad[oa]s?",
    "update": r"updated|changed|corrected|modified|edited|atualizei|alterei|corrigi|modifiquei|editei|atualizad[oa]s?",
    "memory": r"saved|stored|recorded|noted|remembered|memori[sz]ed|added|guardei|registei|registrei|anotei|memorizei|adicionei|guardad[oa]s?",
    "complete": r"completed|finished|conclu[ií]d?[oa]?s?|terminei|terminad[oa]s?|acabei",
}
_ALL_VERBS = "|".join(_CLAIM_VERBS.values())
_EXEC = re.compile(r"\b(?:i'?ve|i have|i just|j[aá])\s+(?:successfully\s+|also\s+|now\s+)?(" + _ALL_VERBS + r")\b"
                   r"|\b(?:has|have|was|were|is|are)\s+(?:been\s+)?(?:successfully\s+|now\s+)?(" + _ALL_VERBS + r")\b"
                   r"|\b(?:foi|foram|est[a\u00e1]|est[a\u00e3]o|ficou|ficaram)\s+(?:devidamente\s+|agora\s+|j[a\u00e1]\s+)?(" + _ALL_VERBS + r")\b"   # 95.38: PT auxiliary passive
                   r"|\b(criei|constru[ií]|escrevi|instalei|gerei|atualizei|alterei|corrigi|modifiquei|editei|apaguei|"
                   r"removi|retirei|esqueci|eliminei|guardei|registei|registrei|anotei|memorizei|adicionei)\b", re.IGNORECASE)
# a promise about REMEMBERING is fulfilled by the memory write side, never by a tool — it is not an intent
_MEMORY_PROMISE = re.compile(r"\b(remember|note (?:that|this|it|down)|noted|keep (?:that|this|it|the)\b[^.!?]{0,40}?"
                             r"(?:in mind|clear|straight|separate)|bear (?:that|this) in mind|"
                             r"make sure to remember|guardar|anotar|registar|registrar|memorizar|lembrar|ter (?:isso|isto) em mente|"
                             r"manter (?:isso|isto) em mente)\b", re.IGNORECASE)


_COORD = re.compile(r"\b(?:and|e|,)\s+(?:then\s+|also\s+|depois\s+)?(" + _ALL_VERBS + r")\b", re.IGNORECASE)


def exec_claims(reply: str):
    """The claim CLASSES asserted by the reply ('remove', 'create', 'update', 'memory')."""
    out = set()
    for sent in re.split(r"(?<=[.!?])\s+|\n+", reply or ""):
        verbs = [next((g for g in m.groups() if g), "") for m in _EXEC.finditer(sent)]
        if verbs:   # coordinated claims share the subject: "I've deleted the files and updated the link"
            verbs += _COORD.findall(sent)
        for verb in verbs:
            for cls, pat in _CLAIM_VERBS.items():
                if re.fullmatch(pat, verb, re.IGNORECASE):
                    out.add(cls)
    return out


def without_unsupported_claims(reply: str, classes) -> str:
    """95.41: the sentences that claim an effect of a class no receipt supports leave the reply."""
    kept = []
    for sent in re.split(r"(?<=[.!?])\s+|\n+", reply or ""):
        verbs = [next((g for g in m.groups() if g), "") for m in _EXEC.finditer(sent)]
        if any(re.fullmatch(_CLAIM_VERBS[c], v, re.IGNORECASE) for c in classes for v in verbs if c in _CLAIM_VERBS):
            continue
        kept.append(sent)
    return " ".join(x for x in kept if x.strip()).strip()


def _ops(tx: dict, *kinds: str) -> list:
    """The operations of these kinds that ACTUALLY happened this turn, each with its own target."""
    return [o for o in (tx.get("operations") or []) if o.get("op") in kinds and o.get("target")]


def _supported_legacy(cls: str, tx: dict) -> bool:
    """The pre-93 rule, for summaries built by hand rather than by `transactions_of`.

    Kept because a caller that never carried operations must keep behaving exactly as it did; it is
    strictly weaker, since a boolean cannot tell a write from a removal."""
    facts, directive, effects = tx.get("facts", 0), tx.get("directive", False), tx.get("effects", 0)
    if cls == "remove":
        return bool(tx.get("retractions") or tx.get("effects_remove"))
    if cls == "create" or cls == "complete":
        return bool(effects)
    if cls == "update":
        return bool(facts or directive or effects or tx.get("plan_ops"))
    return bool(facts or directive or tx.get("episode"))


def _supported(cls: str, tx: dict) -> bool:
    """93.A: a claim is supported by an operation of ITS OWN kind, never by activity in general.

    The real conversation of 2026-09-11 removed `output_prefix` and was told it had claimed falsely,
    because the summary only knew that *a* directive had changed. The opposite error is the one to
    avoid while fixing it: if "something changed" supported `remove`, every write would prove every
    removal. Hence operations with targets, and `remove` asks for a removal."""
    if "operations" not in tx:
        return _supported_legacy(cls, tx)
    if cls == "remove":
        return bool(_ops(tx, "remove"))
    if cls == "create" or cls == "complete":           # "I've completed the files" needs an effect
        return bool(_ops(tx, "create"))
    if cls == "update":                                # the weakest claim: something really changed
        return bool(_ops(tx, "create", "update", "remove"))
    # memory: the ledger, a definition, a directive, or the episode itself
    return bool(tx.get("episode")) or bool([o for o in _ops(tx, "create", "update", "remove")
                                            if not o["target"].startswith("tool:")])


from .authority import is_side_effect   # 69.1: one effect list, mutating shell included
from .unknowns import UNKNOWN_REASK, UNKNOWN_SUFFIX, offered_for_unknown, unknown_asked, without_offers   # noqa: F401 (re-exports; 95.27/95.35 live there)

READ_ONLY_REASK = ("You said you would {intent}. Do it NOW with your tools (list_files, read_file, memory_search, "
                   "brave_web_search…), then give the answer. Never end a reply with a promise.")
from .offers import PROPOSAL_SUFFIX, proposal_suffix as _proposal_suffix  # noqa: F401 (moved 95.78)
CLARIFICATION_SUFFIX = "\n\nWhat would you like me to do?"        # 95.6c: nothing pending, so the turn asks
def _stand(reply: str, suffix: str, trace, report: dict):
    """95.36: a suffix saydo appends is recorded so it can stand on the FINAL reply (keep_guarantee)."""
    return reply.rstrip() + suffix, trace, {**report, "appended": suffix}


def keep_guarantee(reply: str, report) -> str:
    """95.36: re-apply what saydo appended if a later stage (grounding repair, claims, directives)
    replaced the reply; never twice."""
    suffix = (report or {}).get("appended") if isinstance(report, dict) else None
    return reply if not suffix or suffix.strip() in (reply or "") else (reply or "").rstrip() + suffix


PLAN_TOOLS = {"plan_task", "update_plan"}
EXPLICIT_REASK = ("The user gave you an explicit instruction and you said you would {intent}. Do it NOW with your tools "
                  "(write_file, create_widget, bash, memory_search…), then report what you did. Never end a reply with a promise.")   # 90.G1
APPROVED_REASK = ("The user already APPROVED the plan '{title}'. You said you would {intent} — do it NOW with the "
                  "tools (create_widget, write_file, bash…), call update_plan as steps complete, then report. "
                  "Do not ask for permission again and never end a reply with a promise.")
from .saydo_corrections import CORRECTION, PLAN_CORRECTION, REJECTED_CORRECTION, correction_for   # noqa: E402,F401 (95.56b: one place)


def _fulfilled(new_steps, required) -> bool:
    """A re-ask counts as execution only if a REQUIRED step tool ran unblocked (72.6c: a read-only `bash` after
    'continue' used to pass as 'executed_intent' while note3.txt was never written)."""
    work = [t for t in new_steps if not t.get("blocked") and t.get("name") not in PLAN_TOOLS]
    if not work:
        return False
    return any(t.get("name") in set(required) for t in work) if required else True


def _describe(args) -> str:
    if not isinstance(args, dict):
        return ""
    for k in ("title", "name", "path", "query", "command"):
        if args.get(k):
            return str(args[k])[:60]
    return ", ".join(f"{k}={str(v)[:20]}" for k, v in list(args.items())[:3])


_NEGATED_INTENT = re.compile(r"\b(?:i'?ll|i will|let me|vou)\s+(?:never|not|nunca|n[a\u00e3]o|jamais)\b|"
                             r"\b(?:never|nunca|n[a\u00e3]o|jamais)\s+(?:vou|i'?ll|i will)\b", re.IGNORECASE)   # 95.66: both orders

def _intent_sentence(reply: str) -> Optional[str]:
    for sent in re.split(r"(?<=[.!?])\s+|\n+", reply or ""):
        if _INTENT.search(sent) and not _MEMORY_PROMISE.search(sent) and not _NEGATED_INTENT.search(sent):   # 69.3; 95.66: a negated promise promises nothing
            return sent.strip()
    return None


def classify(reply: str, tool_trace, transactions: dict) -> dict:
    """transactions = {'facts', 'retractions', 'directive', 'effects', 'effects_remove', 'episode'}.
    A failed or blocked tool is NOT an action; each execution claim class needs its own transaction."""
    intent = _intent_sentence(reply)
    # 93.B: a turn also acts WITHOUT a tool. Removing a directive, writing a fact or committing through
    # the protocol are actions, and counting only the tool trace turned a promise about something the
    # turn had just done into a permanent task. The episode alone is not an action: every turn has one.
    acted = any(not t.get("failed") and not t.get("blocked") for t in (tool_trace or [])) or any(
        not o["target"].startswith("plan:")          # planning is not doing (the module's own rule)
        for o in _ops(transactions or {}, "create", "update", "remove"))
    claims = exec_claims(reply)
    unsupported = sorted(c for c in claims if not _supported(c, transactions or {}))
    return {
        "intent": intent,
        "intent_no_action": bool(intent) and not acted,
        "read_only": bool(intent and _READ_ONLY.search(intent)),
        "exec_claim": bool(claims),
        "false_exec_claim": bool(unsupported),
        "unsupported_claims": unsupported,
    }


_RETRACTIONS = ("retract", "revoke")


def _removes(t: dict) -> bool:
    from .authority import tool_removes            # 95.56a: the op of an effect is what the tool DID
    return tool_removes(t["name"], t.get("arguments"))


def _operation_list(ok, effects, fact_changes, directive_change, files_written, learning_effects) -> list:
    """Every change this turn as (op, target). 93.A: the receipt says WHAT was done to WHICH thing."""
    ops = []
    for c in fact_changes or []:
        key = c.get("key") or c.get("slot") or c.get("attribute") or ""
        ops.append({"op": "remove" if c.get("cleared") else "update", "target": f"fact:{key or '?'}"})
    if directive_change:
        d = directive_change if isinstance(directive_change, dict) else {}
        ops.append({"op": "remove" if d.get("cleared") else "update",
                    "target": f"directive:{d.get('kind') or '?'}"})
    for t in effects:
        ops.append({"op": "remove" if _removes(t) else "create",
                    "target": f"tool:{t['name']}"})
    for t in ok:
        if t["name"] in ("plan_task", "update_plan"):
            ops.append({"op": "update", "target": f"plan:{t['name']}"})
    for _ in range(int(files_written or 0)):
        ops.append({"op": "create", "target": "file:written"})
    # 93.A: the learning protocol's own effects. An effect that did not apply is not an operation --
    # a blocked or refused write proves exactly as much as no write at all.
    for eff in learning_effects or []:
        if not eff.get("applied"):
            continue
        op = "remove" if str(eff.get("operation") or "") in _RETRACTIONS else "update"
        ops.append({"op": op, "target": f"{eff.get('kind') or 'learning'}:{eff.get('target') or '?'}"})
    return ops


def transactions_of(tool_trace, fact_changes, directive_change, files_written: int = 0,
                    episode: bool = False, learning_effects=None) -> dict:
    ok = [t for t in (tool_trace or []) if not t.get("failed") and not t.get("blocked")]
    effects = [t for t in ok if is_side_effect(t["name"], t.get("arguments"))]
    return {"facts": sum(1 for c in (fact_changes or []) if not c.get("cleared")),
            "retractions": sum(1 for c in (fact_changes or []) if c.get("cleared")),
            "directive": bool(directive_change),
            "effects": len(effects) + int(files_written or 0),
            "effects_remove": sum(1 for t in effects if _removes(t)),
            "plan_ops": sum(1 for t in ok if t["name"] in ("plan_task", "update_plan")),
            "episode": bool(episode),
            "operations": _operation_list(ok, effects, fact_changes, directive_change,
                                          files_written, learning_effects)}


def _named_as_not_done(reply: str, step: str) -> bool:
    """95.4b-ii: naming the rejected step counts as honesty only in a sentence that NEGATES it --
    "noted your sequence 1234567890" names the step while claiming it (E5 c95b, 3/3)."""
    from .utterance import _NEG_GOV                  # the one negation-cue rule the ledger already uses
    return any(step[:40] in s and _NEG_GOV.search(s) for s in re.split(r"(?<=[.!?;:])\s+|\n+", reply or ""))


def _settled_referent(engine, session_id: str, reply: str, c: dict):
    """95.4b-ii: a turn that executed nothing and has no live plan REPORTS ("did you finish?"): its claims are about the
    session's last settled plan (its rejected steps bind the reply; the receipts its done steps cite support what they
    did). 95.63: with no settled plan the referent is the session's LAST TURN WITH RECEIPTS (X2's report turn)."""
    store = getattr(engine, "session_plans", None)
    last = store.get(session_id) if store is not None and hasattr(store, "get") else None
    receipts = getattr(engine, "receipts", None)
    settled = bool(last) and last.get("status") in ("done", "partial", "failed")
    if settled:
        ids = [rid for st in last.get("steps", []) if st.get("status") == "done" for rid in st.get("evidence", [])]
        rows = receipts.by_ids(ids) if ids and receipts is not None and hasattr(receipts, "by_ids") else []
    else:
        rows = receipts.for_session(session_id) if receipts is not None and hasattr(receipts, "for_session") else []
        seq = max((r.get("turn_seq") or 0 for r in rows), default=0); rows = [r for r in rows if r.get("turn_seq") == seq]
    done = [{"name": r["tool"], "arguments": r.get("args") or {}} for r in rows if r.get("status") in ("ok", "already_present")]
    if c.get("false_exec_claim") and done:
        tx = transactions_of(done, [], None); prior = classify(reply, done, tx)
        c = {**c, "false_exec_claim": prior["false_exec_claim"], "unsupported_claims": prior["unsupported_claims"],
             "referent_ops": tx["operations"]}                     # 95.63: the correction names what the referent did
    return (last if settled else None), c


def enforce(engine, reply: str, tool_trace, transactions: dict, session_id: str, user_message: str,
            rerun, turn_seq: int) -> tuple:
    """95.78 (D1): whatever the gate decides about the CLAIMS, a reply that ends by offering to act
    leaves that offer pending, so the user's next yes has an addressee. The decision is unchanged."""
    from .offers import with_offer_registered
    return with_offer_registered(engine, session_id, turn_seq,
                                 _decide(engine, reply, tool_trace, transactions, session_id,
                                         user_message, rerun, turn_seq))


def _decide(engine, reply: str, tool_trace, transactions: dict, session_id: str, user_message: str,
            rerun, turn_seq: int) -> tuple:
    """Returns (reply, tool_trace, report). `rerun(instruction)` runs one more tool-loop pass and returns
    (reply, tool_trace) — provided by the agent so this module stays free of provider details."""
    if not engine.settings.get("saydo_gate_enabled"):
        return reply, tool_trace, None
    executed = [t for t in tool_trace if not t.get("blocked")]
    unconfirmed = list(getattr(engine, "_turn_unconfirmed_effects", []) or [])
    from .session_plans import propose
    from .plans import clarification_turn
    clarification = clarification_turn(engine, session_id)   # 95.6b/95.6c: a bare "yes" or a question, nothing pending
    if unconfirmed and not executed and not clarification and not engine.session_plans.pending(session_id):
        # the model tried a side effect on a SUGGESTION turn: the harness proposes it (deterministic)
        steps = [f"{u['name']}: {_describe(u['arguments'])}" for u in unconfirmed[:12]]
        # 94.4: the reply about to go out IS the proposal the user will answer, so the plan records it
        suffix = _proposal_suffix(steps)
        # 94.4: the reply about to go out IS the proposal the user answers, and it now names the step,
        # so what is shown and what is stored agree by construction rather than by a later guess.
        propose(engine, session_id, steps[0][:80], steps, shown=reply + suffix)
        engine._emit({"type": "saydo", "ok": True, "action": "proposed_unconfirmed", "turn_seq": turn_seq})
        return _stand(reply, suffix, tool_trace, {"turn_seq": turn_seq, "action": "proposed_unconfirmed"})
    if getattr(engine, "_turn_proposed", False) and engine.session_plans.pending(session_id):
        # a proposal was made this turn (plan_task status=proposed, or forced on a suggestion): the reply must ask
        asks = "?" in reply[-160:]
        engine._emit({"type": "saydo", "ok": True, "action": "proposed_plan", "turn_seq": turn_seq})
        report = {"turn_seq": turn_seq, "action": "proposed_plan"}
        return (reply, tool_trace, report) if asks else _stand(reply, PROPOSAL_SUFFIX, tool_trace, report)
    c = classify(reply, [t for t in executed if t.get("name") not in PLAN_TOOLS], transactions)
    plan = engine._turn_plan
    work = [t for t in executed if t.get("name") not in PLAN_TOOLS]        # planning is not doing
    if plan is None and not work:
        plan, c = _settled_referent(engine, session_id, reply, c)          # 95.4b-ii: a report turn
    report = {"turn_seq": turn_seq, **{k: v for k, v in c.items() if k not in ("intent", "referent_ops")}}
    open_steps = [st["text"] for st in (plan or {}).get("steps", []) if st.get("status") in ("active", "pending")]
    # 95.4b: a plan holding a REJECTED step was only partly done, however well the rest went. A reply
    # that claims completion without itself naming that step as not done is corrected (c954 rep2:
    # "I've completed both steps" over a rejected '1234567890').
    rejected = [st["text"] for st in (plan or {}).get("steps", []) if st.get("status") == "rejected"]
    if rejected and "complete" in exec_claims(reply) and not any(_named_as_not_done(reply, r) for r in rejected):
        reply = reply.rstrip() + REJECTED_CORRECTION.format(step=rejected[0][:80])
        report = {**report, "rejected_step_claimed": rejected[0][:80]}
        engine._emit({"type": "saydo", "ok": False, "action": "rejected_step_claimed", "turn_seq": turn_seq})
    from .session_plans import is_continuation
    if plan is not None and open_steps and not work and (c["intent_no_action"] or is_continuation(user_message)):
        # an APPROVED/active plan is the permission: a promise (or "continue") must become execution, never a
        # re-proposal or an apology
        try:
            required = (list(getattr(engine, "_turn_step_tools", []) or [])
                        or [t["name"] for t in executed if t.get("name") not in PLAN_TOOLS] or None)
            new_reply, new_trace = rerun(APPROVED_REASK.format(title=plan.get("title", "plan"),
                                                               intent=(c["intent"] or open_steps[0]).rstrip(".")),
                                         required=required)
            if _fulfilled(new_trace[len(tool_trace):], required):
                engine._emit({"type": "saydo", "ok": True, "action": "executed_intent", "turn_seq": turn_seq})
                return new_reply, new_trace, {**report, "action": "executed_intent"}
            reply, tool_trace = (new_reply or reply), new_trace         # keep what it did say/do, but never the claim
        except Exception:
            pass
        engine._emit({"type": "saydo", "ok": False, "action": "unfulfilled_plan_step", "turn_seq": turn_seq})
        c2 = classify(reply, [t for t in tool_trace if not t.get("blocked") and t.get("name") not in PLAN_TOOLS], transactions)
        if c2["exec_claim"] or c2["false_exec_claim"]:                  # "all steps complete" with no receipt → corrected
            reply = reply.rstrip() + PLAN_CORRECTION.format(step=open_steps[0][:80])
            report = {**report, "false_exec_claim": True, "unsupported_claims": c2.get("unsupported_claims", [])}
        elif c2["intent_no_action"] and not work:                        # 90.2: a promise that stayed a promise says so — the step is open
            reply = reply.rstrip() + PLAN_CORRECTION.format(step=open_steps[0][:80])
        return reply, tool_trace, {**report, "action": "unfulfilled_plan_step"}     # plan stays active, re-pins
    label = unknown_asked(engine, user_message)                        # 95.27/95.59: what the answer STATES is judged first
    if label and offered_for_unknown(engine, reply, label, session_id):   # 95.35/95.48: a held or pending value, offered
        try:
            new_reply, _nt = rerun(UNKNOWN_REASK.format(label=label))
            if new_reply and not offered_for_unknown(engine, new_reply, label, session_id):
                reply = new_reply
                engine._emit({"type": "saydo", "ok": True, "action": "reasked_unknown", "turn_seq": turn_seq})
        except Exception:                                              # fail-soft: the drop below still stands
            pass
        if offered_for_unknown(engine, reply, label, session_id):      # 95.35b: still carried -> that clause is not published
            reply = without_offers(engine, reply, label, session_id)
            engine._emit({"type": "saydo", "ok": True, "action": "dropped_offer", "turn_seq": turn_seq})
    if label and "?" not in reply[-160:]:
        engine._emit({"type": "saydo", "ok": True, "action": "asked_unknown", "turn_seq": turn_seq})
        return _stand(reply, UNKNOWN_SUFFIX.format(label=label), tool_trace, {**report, "action": "asked_unknown"})
    if c["intent_no_action"]:
        # 90.G1: on an EXPLICIT order a promise is re-asked to execute like a read-only intent; suggestions are proposed
        explicit = bool(getattr(engine, "_turn_effects_allowed", False)) and not c["read_only"]
        if c["read_only"] or explicit:
            try:
                instr = READ_ONLY_REASK if c["read_only"] else EXPLICIT_REASK
                new_reply, new_trace = rerun(instr.format(intent=c["intent"].rstrip(".")))
                if new_trace:                                  # it acted this time
                    engine._emit({"type": "saydo", "ok": True, "action": "executed_intent", "turn_seq": turn_seq})
                    return new_reply, new_trace, {**report, "action": "executed_intent"}
            except Exception:                                  # fail-soft: fall through to a proposal
                pass
        if clarification:                              # 95.6b: the promise answers nothing pending -- no plan is born
            engine._emit({"type": "saydo", "ok": True, "action": "clarification", "turn_seq": turn_seq})
            asks = "?" in reply[-160:]                 # 95.6c: a clarification ASKS (E8 rep1 delivered an imperative)
            rep = {**report, "action": "clarification"}
            return (reply, tool_trace, rep) if asks else _stand(reply, CLARIFICATION_SUFFIX, tool_trace, rep)
        title = re.sub(r"^(i'?ll|i will|let me|i'?m going to|i am going to|vou|deixa-me)\s+", "",
                       c["intent"], flags=re.IGNORECASE).rstrip(".").strip() or "Proposed action"
        propose(engine, session_id, title[:80], [title[:120]])
        engine._emit({"type": "saydo", "ok": True, "action": "proposed", "turn_seq": turn_seq})
        return _stand(reply, PROPOSAL_SUFFIX, tool_trace, {**report, "action": "proposed"})
    if c["false_exec_claim"] and not report.get("rejected_step_claimed"):   # 95.4b-ii: the specific correction stands alone
        engine._emit({"type": "saydo", "ok": False, "action": "corrected_claim", "turn_seq": turn_seq})
        reply = without_unsupported_claims(reply, c.get("unsupported_claims") or [])    # 95.41: the claim leaves
        ops = _ops(transactions or {}, "create", "update", "remove") or c.get("referent_ops") or []   # 95.56b/95.63: the
        return _stand(reply, correction_for(c.get("unsupported_claims") or [], ops), tool_trace, {**report, "action": "corrected_claim"})   # is true
    from .speech_act import is_deferred_to_confirmation
    if is_deferred_to_confirmation(user_message) and not engine.session_plans.pending(session_id):   # X7c: the user's
        title = re.sub(r"\s*[,;]?\s*(?:but|mas)\s+.*$", "", user_message.strip(), flags=re.IGNORECASE)[:120]   # deferred order
        propose(engine, session_id, title[:80], [title])                                            # IS the proposal
        engine._emit({"type": "saydo", "ok": True, "action": "proposed_deferred", "turn_seq": turn_seq})
        return _stand(reply, _proposal_suffix([title]), tool_trace, {**report, "action": "proposed_deferred"})
    return reply, tool_trace, report if (c["exec_claim"] or c["intent"]) else None
