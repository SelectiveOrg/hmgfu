"""93.P2 — what may authorise a write: the envelope, the six properties, and the binding.

Split out of `learning_protocol`, which reached its module ceiling, along the seam that was
already there: this file answers whether something MAY be written, the other decides what to do
about it. Keeping them apart also keeps the binding rule visible, which matters after it was
found validating proposals against themselves.

Nothing here writes anything, and nothing here trusts the model's own account: a reference is
checked against the real message, a modality against the real modality contract, and a subject or
context against the message or the stores — never against the proposal that claims them.
"""
from __future__ import annotations

import re
from typing import Optional

# the vocabulary a valid envelope may use. It lives with the validator that enforces it, and
# `learning_protocol` imports it back, so there is one definition and no import cycle.
MAX_PROPOSALS_PER_TURN = 4
FEEDBACK = ("none", "confirm", "reject", "uncertain", "correct", "retract",
            "approve_behavior", "complain", "resume_case")
SCOPES = ("memory", "behavior", "plan", "unclear")
KINDS = ("personal_fact", "domain_definition", "behavior_policy")
AMBIGUITY = ("none", "target", "relation", "value", "time", "contradictory", "unsupported")
EVIDENCE_REF = "turn"          # refs look like  turn:<turn_id>#<start>-<end>


def validate_envelope(env) -> Optional[str]:
    """None when the envelope is usable, else the reason it is not.

    Strict by construction: unknown keys are refused rather than ignored, because an envelope the
    schema does not understand is where guessing is least safe."""
    if not isinstance(env, dict):
        return "envelope is not an object"
    allowed = {"feedback", "target_case_id", "scope", "proposals", "ambiguity"}
    extra = set(env) - allowed
    if extra:
        return f"unknown fields: {sorted(extra)}"
    # 92.E4: a turn that simply TEACHES carries no feedback, and a model omitting the field is
    # behaving correctly. Absence therefore means "no feedback" -- which authorises nothing on its own
    # -- rather than making the envelope unusable. A field that is PRESENT but not a declared value is
    # still refused: that is a contract violation, not a silence.
    env.setdefault("feedback", "none")
    env.setdefault("scope", "unclear")
    if env.get("feedback") not in FEEDBACK:
        return "feedback is not one of the declared values"
    if env.get("scope") not in SCOPES:
        return "scope is not one of the declared values"
    if env.get("ambiguity", "none") not in AMBIGUITY:
        return "ambiguity is not one of the declared values"
    props = env.get("proposals") or []
    if not isinstance(props, list):
        return "proposals is not a list"
    if len(props) > MAX_PROPOSALS_PER_TURN:
        return f"more than {MAX_PROPOSALS_PER_TURN} proposals in one turn"
    for p in props:
        if not isinstance(p, dict):
            return "a proposal is not an object"
        if p.get("kind") not in KINDS:
            return "a proposal has no valid kind"
        # 93.X: a RETRACTION removes rather than sets, so it has no value to carry -- what it must
        # name is the thing to drop. Requiring a value here is why "please forget about ACME-7" could
        # never have been expressed at all: it was refused as malformed before any guard saw it.
        if env.get("feedback") == "retract":
            if not str(p.get("subject_ref") or "").strip():
                return "a retraction names nothing to retract"
        elif not str(p.get("value") or "").strip():
            return "a proposal has no value"
        # 95.58: a missing reference is not the envelope's shape -- since 93.Q2 the SYSTEM locates the span
        # and discards the model's; an unbound proposal is refused on its own by `evidence_problem`.
    tcid = env.get("target_case_id")
    if tcid is not None and not isinstance(tcid, str):
        return "target_case_id is neither null nor an id"
    return None


# 92.E3 — what a resolved reference must be before it may authorise a write. The caller resolves;
# anything it could not resolve is refused, because a model naming its own reference would otherwise
# authorise its own write.
_AUTHORISING_ORIGINS = ("user", "tool")


def evidence_problem(proposal: dict, resolved: dict, revision=None):
    """None when the proposal is supported, else the reason it is not.

    Checks the six properties the plan enumerates -- existence, origin, subject, context, modality
    and revision -- against what the CALLER resolved. An assistant reflection is evidence of what the
    assistant thought, never that the user confirmed it, so it cannot be the sole support."""
    refs = list(proposal.get("evidence_refs") or [])
    if not refs:
        return "no evidence reference"
    support = []
    for ref in refs:
        got = (resolved or {}).get(ref)
        if not isinstance(got, dict):
            return f"evidence reference does not resolve: {ref}"
        if not got.get("exists"):
            return f"evidence reference does not exist: {ref}"
        if got.get("origin") not in _AUTHORISING_ORIGINS:
            continue                       # a reflection may accompany, it may not authorise
        if got.get("origin") == "tool" and not got.get("source"):
            continue                       # a tool observation must name where it came from
        if proposal.get("subject_ref") and got.get("subject") != proposal["subject_ref"]:
            return f"evidence is about another subject: {ref}"
        from .learning_apply import _is_the_message
        if _is_the_message(proposal.get("value"), got.get("said") or ""):   # 95.45: a sentence is not a value
            return f"the value is the message, not a value: {ref}"
        if proposal.get("context_ref") and got.get("context") != proposal["context_ref"]:
            return f"evidence belongs to another context: {ref}"
        if got.get("modality") not in ("assert", None):
            return f"evidence is not asserted ({got.get('modality')}): {ref}"
        if revision is not None and got.get("revision") is not None and int(got["revision"]) != int(revision):
            return f"evidence revision moved: {ref}"
        support.append(ref)
    if not support:
        return "no reference of an authorising origin (a reflection cannot stand alone)"
    return None


# 92.E4 — resolving a reference is PURE: text in, descriptor out. It lives beside the decision it
# feeds, because the whole point is that the controller refuses what this could not resolve.
EVIDENCE_REF = "turn"          # refs look like  turn:<turn_id>#<start>-<end>


def attach_evidence(env, text: str, turn_id: str, pending=None):
    """Give each proposal the reference the SYSTEM can verify, rather than one the model asserts.

    The plan puts identifiers in the controller's hands: a model that cites can cite falsely. It
    proposes kind, subject, context, relation and VALUE; the span is located HERE, and a value that is
    nowhere in the message gets no reference and is refused downstream."""
    if not isinstance(env, dict):
        return env
    low = (text or "").casefold()
    for p in env.get("proposals") or []:
        if not isinstance(p, dict):
            continue
        # the model's own reference is DISCARDED, not trusted and not merely checked: a span it cites
        # could exist, be asserted, and still not be the value. Locating it here removes the surface.
        p.pop("evidence_refs", None)
        # 93.X: a retraction carries no value, so the span that must exist in the message is the
        # SUBJECT the user named. Everything downstream is unchanged -- the same binding rule reads
        # the same clause, and an unbound subject still authorises nothing.
        value = str(p.get("value") or "").strip()
        if (env or {}).get("feedback") == "retract":
            value = str(p.get("subject_ref") or "").strip()
        at = low.find(value.casefold()) if value else -1
        if at >= 0:
            p["evidence_refs"] = [f"{EVIDENCE_REF}:{turn_id}#{at}-{at + len(value)}"]
            continue
        # 93.Q2: the value may be the one the QUESTION preserved. An answer that fills a blank does
        # not repeat what it is answering about -- "my current project" carries no "Nimbus" -- and
        # looking only at this message meant the pendency could ask something it could never accept
        # an answer to. So the case's own words are searched too, and the reference names THAT turn:
        # the value keeps the provenance of the turn that stated it, the subject that of this one.
        case = answering_case(pending)
        said = str((case or {}).get("expression") or "")
        at = said.casefold().find(value.casefold()) if (case and value) else -1
        if at >= 0 and _case_turn(case):
            p["evidence_refs"] = [f"{EVIDENCE_REF}:{_case_turn(case)}#{at}-{at + len(value)}"]
    return env


def answering_case(pending, session_id=None):
    """The pending case a reply may draw its preserved value from, or None.

    93.Q2: an elliptical answer ("my current project") means nothing without the value the question
    preserved, so the case has to be readable as evidence. Every guard that made the case trustworthy
    is the guard on that: it is THIS session's, its question was really delivered, and it kept the
    user's own words. Nothing here authorises a subject -- 93.Q1 still requires that to be bound in
    the message that supplies it."""
    if not isinstance(pending, dict) or not pending.get("question_delivered"):
        return None
    if session_id is not None and pending.get("session_id") != session_id:
        return None
    return pending if str(pending.get("expression") or "").strip() else None


def _case_turn(pending) -> str:
    """The turn the pending case's words were said in, so a reference into it names a real turn."""
    return str((pending or {}).get("origin_turn_id") or (pending or {}).get("question_turn_id") or "")


def _bound(claim: str, text: str, known=None, partial: bool = False) -> bool:
    """Is this subject or context supported by something OUTSIDE the proposal that claims it?

    93.P2: `resolve_evidence` used to copy the subject and the context straight from the proposal into
    the descriptor that then validated that proposal, so `subject_ref=UNMENTIONED-ENTITY` proved
    itself as long as the VALUE happened to be in the message. Two independent sources are accepted,
    and neither is a list of phrases: the claim appears in the message the evidence cites, or the
    stores already hold it -- which is what a grounded contextual reference looks like, the user
    saying "the project" about a project the system knows. Anything else is unbound, and an unbound
    proposal is not promoted; it is something to ask about."""
    want = " ".join(str(claim or "").split()).casefold()
    if not want:
        return False
    if want in " ".join(str(text or "").split()).casefold():
        return True
    # 93.Q1: a known entity is a candidate for RESOLUTION, never an authorisation -- accepting a subject because the
    # stores hold it attached "Atlas Control Mesh" to BETA-2. Binding comes from the clause alone; `known` is not consulted.
    if not partial:
        return False
    # 93.Q1: EVERY content word of the claim must be in the text ("project" alone let "Project Omega Delivery" bind to a
    # sentence about Project Alpha). Stricter on purpose: an unproven scope is asked about, not assumed.
    said = set(re.findall(r"[^\W_]{4,}", str(text or "").casefold(), flags=re.UNICODE))
    words = re.findall(r"[^\W_]{4,}", want, flags=re.UNICODE)
    return bool(words) and all(w in said for w in words)


def resolve_evidence(env, text: str, turn_id: str, revision: int, *, tool_receipts=None,
                     known_subjects=None, pending=None) -> dict:
    """What each cited reference actually turns out to be. Unresolvable refs are simply absent.

    This is the half the controller cannot do, and the reason it exists: a model can write any string
    into evidence_refs, so something has to go and look. Existence is checked against the real
    message, modality against the real modality contract, and origin against where the span was
    found -- never against what the model called it."""
    from .utterance import sentence_modalities
    out = {}
    receipts = {str(r.get("id")): r for r in (tool_receipts or []) if isinstance(r, dict)}
    for p in (env or {}).get("proposals") or []:
        for ref in p.get("evidence_refs") or []:
            ref = str(ref)
            if ref in out:
                continue
            if ref in receipts:                      # a tool observation, and it names its source
                r = receipts[ref]
                out[ref] = {"exists": True, "origin": "tool", "source": r.get("tool"),
                            "subject": p.get("subject_ref"), "context": p.get("context_ref"),
                            "modality": "assert", "revision": revision}
                continue
            # 93.Q2: the preserved value lives in the case's turn, and only that turn. The SUBJECT
            # is still read from the message in front of us, so an answer cannot smuggle in an
            # entity nobody spoke about, and the modality is still that of the clause the value was
            # actually said in -- a value the user denied stays denied.
            case = answering_case(pending)
            if case and _case_turn(case) and _span_of(ref, _case_turn(case), case["expression"]):
                said = str(case["expression"])
                fragment, _ = _span_of(ref, _case_turn(case), said)
                out[ref] = {"exists": True, "origin": "user",
                            "subject": (p.get("subject_ref")
                                        if _bound(p.get("subject_ref"), text) else None),
                            "context": (p.get("context_ref")
                                        if _bound(p.get("context_ref"), f"{text} {said}",
                                                  partial=True) else None),
                            "modality": _modality_of(fragment, said), "revision": revision}
                continue
            span = _span_of(ref, turn_id, text)
            if span is None:
                continue                             # invented, or about a turn we cannot see: absent
            fragment, ok_subject = span
            # 92.E4: modality is a property of the clause IN CONTEXT, not of the fragment. Evaluating
            # the span alone read "ACME-7 means X" out of "I never said that ACME-7 means X" as an
            # assertion. The span is assertable only if it lies inside a clause the SAME utterance
            # contract that governs every other write here classified as assert.
            clauses = sentence_modalities(text or "")
            frag = fragment.strip().rstrip(".").casefold()
            holding = [c for c in clauses if frag and frag in c["text"].strip().casefold()]
            modality = _modality_of(fragment, text or "")
            # 93.P2: the value being locatable says nothing about WHOSE it is. Subject and context are
            # reported only when independently bound; unbound ones arrive as None and the comparison
            # in evidence_problem then refuses the proposal instead of confirming it to itself.
            # 93.Q1: the binding travels with the CLAUSE that carries the value, not the message.
            # Presence anywhere proved nothing: the same sentence could be filed under another
            # project, or its value pinned on a term defined in a different clause of the same
            # message. `holding` is that clause -- the one the modality was already read from.
            here = holding[0]["text"] if holding else (text or "")
            subject = p.get("subject_ref") if (ok_subject and _bound(p.get("subject_ref"), here)) else None
            # a CONTEXT is usually a label the user did not spell out ("project terminology" for "In
            # this project"), so sharing a content word with the message binds it; sharing none, as
            # an invented context does, does not.
            # a context is usually a label the user did not spell out ("project terminology" for "In
            # this project"), so sharing a content word with THAT CLAUSE binds it; a context named
            # from somewhere else in the message, or from nowhere, does not.
            # a context is a SCOPE: it can be set once and carry across the sentences that follow, so
            # it is looked for in the whole message -- but every word of it must really be there.
            context = p.get("context_ref") if _bound(p.get("context_ref"), text, partial=True) else None
            out[ref] = {"exists": True, "origin": "user", "subject": subject, "said": text,   # 95.45: what was said
                        "context": context, "modality": modality, "revision": revision}
    return out


def _modality_of(fragment: str, said: str) -> str:
    """The modality of the clause that HOLDS this fragment, in the utterance it was said in.

    The same rule `resolve_evidence` applies to the current message, named so the pending case is
    judged by it too: "I never said it is called Nimbus" preserves a denial, not a value."""
    from .utterance import sentence_modalities
    clauses = sentence_modalities(said or "")
    frag = str(fragment or "").strip().rstrip(".").casefold()
    holding = [c for c in clauses if frag and frag in c["text"].strip().casefold()]
    from .utterance import _NEG_GOV; from .learning_apply import _NEG_COPULA_AFTER   # 95.29 / 95.43
    low = holding[0]["text"].casefold() if holding else ""; at = low.find(frag)
    if holding and (_NEG_GOV.search(low[:at]) or _NEG_GOV.match(frag) or _NEG_COPULA_AFTER.match(low[at + len(frag):])):
        return "negated"                                  # a denied value: negation before it, on it, or its negated copula
    return holding[0]["modality"] if holding else next((c["modality"] for c in clauses), "assert")


def _span_of(ref: str, turn_id: str, text: str):
    """(fragment, subject_present) for a ref that really points into THIS message, else None."""
    if not ref.startswith(EVIDENCE_REF + ":") or "#" not in ref:
        return None
    body, _, rng = ref.partition("#")
    if body.split(":", 1)[1] != str(turn_id):
        return None                                  # a reference to another turn is not resolvable here
    try:
        start, _, end = rng.partition("-")
        s, e = int(start), int(end)
    except ValueError:
        return None
    if not (0 <= s < e <= len(text or "")):
        return None                                  # the span does not exist in the message it cites
    return (text[s:e], True)


def _pending_for_session(snapshot: dict) -> Optional[dict]:
    """The question this session is actually waiting on, if it was really delivered."""
    case = snapshot.get("pending_case")
    if not case or case.get("session_id") != snapshot.get("session_id"):
        return None                       # another session's pending case never consumes this answer
    if not case.get("question_delivered"):
        return None                       # a candidate stored without a visible question earns no yes
    return case


def known_subjects(facts) -> set:
    """What the stores already hold, so a grounded contextual reference can be recognised.

    93.P2: a subject the message does not spell out may still be one the system knows -- an entity it
    has a definition for, or a canonical slot. Reading them from the stores keeps the binding
    independent of the proposal, and adds no list of phrases anywhere."""
    out = set()
    try:
        for e in facts.assertions.entities():
            name = str(e.get("name") or "")
            out.add(name)
            if "::" in name:
                ctx, _, term = name.partition("::")
                out.update({ctx, term})
    except Exception:
        pass
    try:
        out.update(str(row.get("key") or "") for row in facts.active())
    except Exception:
        pass
    return {x for x in out if x}


def missing_property(proposal: dict, resolved: dict) -> Optional[str]:
    """Which of the six properties this proposal still lacks, or None when it is complete.

    93.P3: the live chain wrote a definition for the subject "the name of the project/entity being
    discussed" because a bare yes confirmed a proposal nothing had bound. Asking for a missing piece
    and asking someone to confirm an interpretation are different acts, and only the second can be
    answered with a word. Naming what is missing is what lets the two be told apart -- and it is read
    from the resolution that already checked them, not from a new judgement."""
    refs = [resolved.get(str(r)) for r in (proposal.get("evidence_refs") or [])]
    got = [r for r in refs if r]
    if not got:
        return "evidence"
    if proposal.get("subject_ref") and not any(r.get("subject") == proposal["subject_ref"] for r in got):
        return "subject"
    if proposal.get("context_ref") and not any(r.get("context") == proposal["context_ref"] for r in got):
        return "context"
    return None


def question_for(proposal: dict, missing: Optional[str]) -> str:
    """The question this case should deliver: fill in what is missing, or confirm what is complete.

    Built from the proposal's own fields, so it names something real and never echoes an unbound
    subject back at the user as though it were one."""
    value = str(proposal.get("value") or "").strip()
    subject = str(proposal.get("subject_ref") or "").strip()
    if missing == "subject":
        return (f"I do not want to record {value!r} against the wrong thing -- "
                f"what is it the name of?")
    if missing == "context":
        return f"Where does {value!r} apply -- which project or area should I file it under?"
    if missing:
        return f"I could not check {value!r} against what you wrote -- could you say it again in full?"
    return f"Should I record that {subject} is {value}?"


def question_for_turn(env, resolved) -> str:
    """The question this turn should ask: fill in what is missing, or confirm what is complete.

    93.P3: the fixed "Could you confirm that?" made every ask look like a request for agreement, so a
    bare yes confirmed a proposal whose subject nothing had bound. What is missing is read from the
    resolution that already checked it, and the question is built from the proposal's own fields."""
    props = (env or {}).get("proposals") or []
    if not props:
        return str((env or {}).get("question") or "Could you confirm that?")
    return question_for(props[0], missing_property(props[0], resolved or {}))


def needs_of(env, resolved):
    """What the case still lacks, recorded on it so a later bare answer knows which act it answers."""
    props = (env or {}).get("proposals") or []
    return missing_property(props[0], resolved or {}) if props else None
