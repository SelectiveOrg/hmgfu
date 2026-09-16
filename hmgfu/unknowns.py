"""What the user asked about that the ledger does not hold -- asked for, never guessed (95.27, 95.35).

Ledger-grounded, no phrase list: a canonical slot about the user with no active value, or a code-like
term with no definition, is asked for (UNKNOWN_SUFFIX); a value the ledger holds for ANOTHER attribute,
put forward for the unknown one, is re-asked once with the contract stated (UNKNOWN_REASK). saydo.enforce
is the single consumer; the names are re-exported there for compatibility."""
from __future__ import annotations

import re

UNKNOWN_SUFFIX = "\n\n(I have no record of your {label}. What is it? Tell me and I will keep it.)"   # 95.27
UNKNOWN_REASK = ("The user's {label} is not on record. Say so and ask for it. Do not mention any name or value "
                 "from other records in that answer.")                                              # 95.35/95.35b
_POSSESSED = re.compile(r"\b(?:my|our|meu|minha|meus|minhas|nosso|nossa)\s+([\w-]+)")     # 95.42: "a minha empresa" -> empresa
_CODE_TERM = re.compile(r"\b[A-Z][A-Z0-9]{1,}-\d+\b")                  # an identifier shape (KLM-3, RXQ-10), not a phrase


def unknown_asked(engine, user_message: str):
    """95.27: the label of what the user asked about that the ledger does not hold, or None -- a canonical
    slot about themselves with no active value, or a code-like term with no definition."""
    from .speech_act import is_interrogative, refers_to_self
    from .slots import SLOTS, mentions_attribute
    msg = user_message or ""
    if not is_interrogative(msg):
        return None
    facts = getattr(engine, "facts", None)
    if refers_to_self(msg) and facts is not None:
        from .slots import attribute_tokens
        held = {f["key"] for f in facts.active()}
        toks = set(re.findall(r"[\w-]+", msg.casefold()))
        verbs = set(re.findall(r"\b(?:eu|i|we|n[o\u00f3]s)\s+([\w-]+)", msg.casefold()))   # 95.69: "eu trabalho" is a verb --
        heads = set(re.findall(r"\b(?:o|a|os|as|the|my|our|meu|minha|nosso|nossa|um|uma|an?)\s+([\w-]+)", msg.casefold()))
        if any(attribute_tokens(k) & (heads - verbs) for k in SLOTS):                     # it yields to a determiner-headed noun
            toks -= verbs
        owned = set(_POSSESSED.findall(msg.casefold()))                # 95.42: the heads the user names as theirs
        matched = [(bool(attribute_tokens(key) & owned), max((len(t) for t in attribute_tokens(key) & toks), default=0), key)
                   for key in SLOTS if mentions_attribute(key, msg)]
        if matched:
            best = max(matched)[2]                                    # a named-as-mine head first, then specificity
            if best not in held:                                      # 95.27/95.42: a held slot answers ITSELF only
                return SLOTS[best].get("label") or best
    assertions = getattr(facts, "assertions", None)
    defined = {(e.get("name") or "").partition("::")[2] for e in assertions.entities(kind="definition")} if assertions is not None else set()
    for term in _CODE_TERM.findall(msg):
        if term.casefold() not in defined:
            return term
    return None


_CLAUSE_SPLIT = re.compile(r"([.!?\n]+)")


def _pending_values(engine, label: str, session_id) -> list:
    """95.48: the values of the session's pending (unconfirmed) proposals about the asked term or slot."""
    facts = getattr(engine, "facts", None)
    if facts is None or not session_id:
        return []
    try:
        from .learning_state import LearningState
        case = LearningState(conn=facts._db).active_question(session_id)
    except Exception:
        return []
    want = (label or "").casefold()
    return [str(p.get("value")) for p in ((case or {}).get("proposals") or []) if p.get("value")
            and (want in str(p.get("subject_ref") or "").casefold() or want in str(p.get("relation") or "").casefold())]


def _offers(engine, reply: str, label: str, session_id=None) -> list:
    """95.35/95.35b: the (clause, value) pairs where a clause naming the ASKED attribute carries an active
    value of ANOTHER slot -- a guess or a distraction in any wording, own attribute named or not. 95.48:
    the value of a proposal the protocol is still asking about is an offer too."""
    from .slots import SLOTS, attribute_tokens, base_slot, value_in_text
    key = next((k for k, spec in SLOTS.items() if spec.get("label") == label), None)
    pending = _pending_values(engine, label, session_id)
    if (key is None and not pending) or getattr(engine, "facts", None) is None:
        return []
    asked = attribute_tokens(key) if key else {t for t in re.findall(r"[\w-]+", (label or "").casefold())}
    others = ([f["value"] for f in engine.facts.active() if f.get("value") and base_slot(f["key"]) != base_slot(key)] if key else []) + pending
    out = []
    for clause in _CLAUSE_SPLIT.split(reply or "")[::2]:
        if asked & set(re.findall(r"[\w-]+", clause.casefold())):
            out.extend((clause, v) for v in others if value_in_text(v, clause))
    return out


def offered_for_unknown(engine, reply: str, label: str, session_id=None):
    """The first other-record (or pending-proposal, 95.48) value a clause about the unknown carries, or None."""
    hits = _offers(engine, reply, label, session_id)
    return hits[0][1] if hits else None


def without_offers(engine, reply: str, label: str, session_id=None) -> str:
    """95.35b: the reply with every offending clause removed (its delimiter goes with it)."""
    bad = {c for c, _v in _offers(engine, reply, label, session_id)}
    parts = _CLAUSE_SPLIT.split(reply or "")
    kept = [parts[i] + (parts[i + 1] if i + 1 < len(parts) else "") for i in range(0, len(parts), 2) if parts[i] not in bad]
    return re.sub(r"[ \t]+\n", "\n", "".join(kept)).strip()
