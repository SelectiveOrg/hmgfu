"""93.Q2 - what a decision DOES to the three stores, apart from what decides it.

Split out of `learning_state`, which reached its module ceiling, along the seam that was already
there: nothing in this file reads a case row or an engine. It takes a decision and some proposals and
writes -- or refuses to write -- through FactStore, AssertionStore and DirectiveStore, which is the
whole of the plan's adapter layer.

`learning_state` imports these names straight back, so every existing caller keeps working.
"""
from __future__ import annotations

import re

import json
from typing import Optional

from .models import now_iso


DEFINITION_RELATION = "definition.meaning"


def definition_entity_key(context_ref: str, term: str) -> str:
    """The deterministic identity of a defined term: (context, term).

    AssertionStore supersedes per entity_id+relation, so every term needs its OWN entity -- sharing
    one entity per project would make each new definition erase the last. The term keeps its readable
    form: case is folded and surrounding space trimmed, but accents and internal punctuation are left
    alone, because collapsing them without evidence would merge terms the user may distinguish."""
    ctx = (context_ref or "local").strip() or "local"
    return f"{ctx}::{(term or '').strip().casefold()}"


def _canonical_key(proposal: dict):
    """95.2: the slot id a proposal's subject resolves to, or None. `relation` may already be a slot id;
    otherwise the subject text goes through the same `normalise_key` every other path uses."""
    from .slots import SLOTS, normalise_key
    for ref in (proposal.get("relation"), proposal.get("subject_ref")):
        ref = str(ref or "").strip()
        if not ref:
            continue
        key = normalise_key(ref)
        if key in SLOTS:
            return key
    return None


def apply_decision(decision, proposals, *, facts=None, assertions=None, directives=None,
                   text: str = "", session: str = "", source: str = "user_explicit") -> list:
    """Apply the writes a decision authorises; one receipt per effect, empty when nothing is authorised."""
    action = decision.get("action") if isinstance(decision, dict) else getattr(decision, "action", None)
    if action != "commit":
        return []
    op = (decision.get("operation") if isinstance(decision, dict) else None) or "assert"
    out = []
    for p in proposals or []:
        kind = p.get("kind")
        # 95.2: the proposal already names subject and value. When the subject is a CANONICAL slot
        # (project.main, identity.name, ...), write it through the one canonical writer -- row, history,
        # assertion and supersession in one transaction -- instead of re-parsing the text with a regex
        # that a correction ("Correcao: o projeto principal chama-se Vega, nao Nimbus") does not match.
        # L2 failed 0/3 in both arms exactly here. A term that is no slot keeps its definition path.
        canonical = _canonical_key(p) if facts is not None and kind in ("personal_fact", "domain_definition") else None
        if canonical and str(p.get("value") or "").strip():
            change = facts._apply_one({"key": canonical, "value": str(p.get("value")).strip(),
                                       "path": "protocol"}, text or "", source)
            out.append({"kind": kind, "target": canonical, "canonical": canonical if change else None,
                        "effects": [change] if change else [], "applied": bool(change)})
            continue
        if kind == "personal_fact" and facts is not None:
            changes = facts.apply_all(text or "", source, session=session)
            out.append({"kind": kind, "target": p.get("relation"), "effects": changes,
                        "applied": bool(changes)})
        elif kind == "domain_definition" and assertions is not None:
            eid = assertions.upsert_entity(
                "definition", definition_entity_key(p.get("context_ref"), p.get("subject_ref")))
            if op in ("retract", "revoke"):
                assertions.retract(eid, DEFINITION_RELATION)
                out.append({"kind": kind, "target": eid, "operation": op, "applied": True})
            else:
                value = str(p.get("value") or "")
                prior = [a["value"] for a in assertions.active(entity_id=eid) if a.get("relation") == DEFINITION_RELATION]
                aid = assertions.assert_(eid, DEFINITION_RELATION, value, source_span=(text or "")[:500])
                # 95.18: a REVISION reports what it superseded, as the canonical path does (has_supersession reads it)
                prev = next((v for v in prior if v.strip().lower() != value.strip().lower()), None)
                out.append({"kind": kind, "target": eid, "assertion_id": aid, "applied": True,
                            "effects": [{"key": "definition:" + eid, "value": value, "prev": prev,
                                         "subject": str(p.get("subject_ref") or "")}] if prev else []})
            assertions.commit()                 # 95.11: this revision is durable NOW, not at the next canonical write
        elif kind == "behavior_policy" and directives is not None:
            # 93.C: a policy about HOW to answer is a response_style, not a tool rule -- the old default
            # filed every one under `tool_rule:memory_search`, where no style could be read back.
            act = directives.apply(text or "", source, detected={
                "kind": p.get("relation") or "response_style",
                "value": str(p.get("value") or ""), "instruction": (text or "")[:500],
                "condition": str(p.get("condition") or ""), "fallback_text": ""})
            out.append({"kind": kind, "target": p.get("relation"), "effects": act,
                        "applied": bool(act)})
    return out


def deliver_question(state, case_id: str, *, turn_id: str, reply: str = "") -> bool:
    """Record that this turn ASKED the pending question. True when it counts.

    93.R4: `_persist` opened an asking case without a `question_turn_id`, so `question_delivered`
    stayed false and the next turn's "yes" earned nothing -- correctly, since a candidate without a
    delivered question earns nothing. Nothing delivered it either, so the chain could never close.

    `reply` is checked when given: marking delivery without delivering would be the same lie in the
    other direction, a case believing it asked something the user never saw. The first turn to ask
    keeps the mark; a later echo does not move it, and this records only -- it decides nothing."""
    if not case_id:
        return False
    row = state._db.execute("SELECT session_id, payload_json, question_turn_id FROM learning_cases "
                            "WHERE id=?", (case_id,)).fetchone()
    if row is None or row[2]:
        return bool(row and row[2])                  # unknown case, or already asked: keep the first
    question = (json.loads(row[1] or "{}") or {}).get("question") or ""
    if reply and question and question not in reply:
        return False                                 # the user never saw it: it was not asked
    state._db.execute("UPDATE learning_cases SET question_turn_id=?, updated_at=? WHERE id=?",
                      (str(turn_id), now_iso(), case_id))
    state._db.commit()
    return True


_DEFINES = r"\s+(?:means|stands for|refers to|is defined as|significa|quer dizer|define-se como)\s+"   # definitional predicates only ("is" would take any predicate)
_DEF_END = r"(?=\s*(?:[,;.!?]|\s+(?:not|n[a\u00e3]o)\b|$))"


def ledger_grounded_proposals(assertions, text: str) -> list:
    """95.20: a REVISION of a term the ledger already defines, read from the message itself: the term
    (an existing definition entity) + a definitional predicate + a meaning that differs from the
    current one. Returns [] for a first definition (the perceiver's job), a restatement, or no term."""
    import re
    if assertions is None or not (text or "").strip():
        return []
    out = []
    for ent in assertions.entities(kind="definition"):
        ctx, _, term = (ent.get("name") or "").partition("::")
        if len(term) < 2:
            continue
        m = re.search(r"\b" + re.escape(term) + _DEFINES + r"(.+?)" + _DEF_END, text, re.IGNORECASE)
        if not m:
            continue
        value = m.group(1).strip().strip("*'\"`")
        current = next((a.get("value") for a in assertions.active(entity_id=ent["id"])
                        if a.get("relation") == DEFINITION_RELATION), None)
        if not value or current is None or value.casefold() == str(current).casefold():
            continue
        start = text.find(m.group(1).strip())
        out.append({"kind": "domain_definition", "subject_ref": term, "context_ref": ctx if ctx != "local" else None,
                    "relation": DEFINITION_RELATION, "value": value,
                    "evidence_refs": [f"turn:{{turn}}#{start}-{start + len(m.group(1).strip())}"]})
    return out


def stated_definitions(text: str) -> list:
    """95.67: the definitions the message STATES of code-like terms (KLM-3, PXD-4 -- unknowns' own identifier shape),
    read from the message itself whether or not the ledger knows the term: term + a definitional predicate + the
    meaning. The evidence is the meaning's span; the caller sets the envelope's ambiguity from its clause's modality."""
    import re
    from .unknowns import _CODE_TERM
    out, seen = [], set()
    for m in _CODE_TERM.finditer(text or ""):
        term = m.group(0)
        if term in seen:
            continue
        seen.add(term)
        d = re.search(r"\b" + re.escape(term) + _DEFINES + r"(.+?)" + _DEF_END, text, re.IGNORECASE)
        if not d:
            continue
        value = d.group(1).strip().strip("*'\"`")
        if not value or len(value.split()) > 8:
            continue
        start = text.find(d.group(1).strip())
        out.append({"kind": "domain_definition", "subject_ref": term, "context_ref": None, "relation": DEFINITION_RELATION,
                    "value": value, "evidence_refs": [f"turn:{{turn}}#{start}-{start + len(d.group(1).strip())}"]})
    return out


_DENIED_DEF = re.compile(r"\b([A-Z][A-Z0-9]{1,}-\d+)\b\s+(?:has|had|have)?\s*(?:never(?: once)?|not|no longer|nunca|n[a\u00e3]o|jamais)\s+"
                         r"(?:meant|means|stood for|stands for|significa|significou|quer dizer|quis dizer|referred to|refers to)\s+(.+?)" + _DEF_END, re.IGNORECASE)


def denied_definition(text: str):
    """95.62c: (term, denied meaning) when the message DENIES a definition ("MRD-2 has never once meant Manual Reset
    Dial"), else None. What the ledger holds for the term decides what the denial can do."""
    m = _DENIED_DEF.search(text or "")
    return (m.group(1), m.group(2).strip().strip("*'\"`")) if m else None


def held_definition(assertions, term: str):
    """The active meaning the ledger holds for `term`, or None."""
    if assertions is None:
        return None
    for ent in assertions.entities(kind="definition"):
        if (ent.get("name") or "").partition("::")[2].casefold() == term.casefold():
            return next((a.get("value") for a in assertions.active(entity_id=ent["id"]) if a.get("relation") == DEFINITION_RELATION), None)
    return None


# 95.43: a negated copula right after the subject fragment -- both word orders, one closed pattern
_NEG_COPULA_AFTER = re.compile(r"^\s*(?:(?:is|was|are|were|'s)\s+(?:no longer|not|no more|never)\b|isn'?t\b|wasn'?t\b|aren'?t\b|"
                               r"(?:j[a\u00e1]\s+)?n[a\u00e3]o\s+(?:[e\u00e9]|era|s[a\u00e3]o|foi)\b(?:\s+mais)?)", re.IGNORECASE)



def _is_the_message(value, said: str) -> bool:
    """95.45: a value that is the whole message (or the whole clause it sits in) is not a value."""
    v = " ".join(str(value or "").split()).casefold().rstrip(".!?")
    if not v or len(v.split()) < 4:
        return False
    from .utterance import sentence_modalities
    clauses = [" ".join(c["text"].split()).casefold().rstrip(".!?") for c in sentence_modalities(said or "")]
    return v == " ".join(str(said or "").split()).casefold().rstrip(".!?") or v in clauses


def ledger_grounded_denials(facts, text: str, proposals=None) -> list:
    """95.45: a DENIAL the ledger can see -- an active canonical value that appears in the message under a
    negated copula ("Kestrel is no longer the name of my main project", "O Kestrel ja nao e o nome do meu
    projeto principal"), with no other value proposed for that slot -- is a proposal whose evidence is
    negated, so the protocol asks what it is now and writes nothing. Formulation-independent: it reads
    the ledger and one closed grammatical pattern."""
    import re
    from .fact_detect import detect_facts
    from .learning_evidence import _modality_of
    from .slots import attribute_tokens, base_slot, label_for, normalise_key, value_in_text
    if facts is None or not (text or "").strip():
        return []
    taken = {str(p.get("relation") or "") for p in (proposals or []) if p.get("value")}
    taken |= {base_slot(normalise_key(d["key"])) for d in detect_facts(text) if d.get("value")}   # 95.45b: a stated
    toks = set(re.findall(r"[\w-]+", (text or "").casefold()))                                   # replacement = correction
    out = []
    for f in facts.active():
        key, value = f.get("key"), str(f.get("value") or "")
        if not key or not value or key in taken or base_slot(key) in taken or not value_in_text(value, text):
            continue
        if _modality_of(value, text) != "negated":
            continue
        start = text.casefold().find(value.casefold())
        said = sorted(attribute_tokens(key) & toks, key=len, reverse=True)       # 95.45b: the word the message uses
        out.append({"kind": "personal_fact", "subject_ref": (said[0] if said else None) or label_for(key) or key,
                    "relation": key, "value": value,
                    "evidence_refs": [f"turn:{{turn}}#{start}-{start + len(value)}"], "denial": True})
    return out


def read_definition(assertions, context_ref: str, term: str):
    """The current definition of a term in a context, with its assertion id -- or None.

    Identity is resolved exactly as the write resolved it: `upsert_entity` is idempotent on the
    (context, term) key, so a restart or a new session finds the same entity instead of guessing by
    similarity. Only an ACTIVE assertion is returned; a superseded one is history, not the answer."""
    eid = assertions.upsert_entity("definition", definition_entity_key(context_ref, term))
    for a in assertions.active(entity_id=eid):
        if a.get("relation") == DEFINITION_RELATION and a.get("status", "active") == "active":
            return {"value": a.get("value"), "assertion_id": a.get("id"), "entity_id": eid}
    return None



# --- 92.E4: the turn entry -------------------------------------------------------------------------
