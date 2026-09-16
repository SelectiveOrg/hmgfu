"""Phase 84.3 — the SPAN-EXTRACTOR contract for the model-backed write path.

Two reserved sets showed the deterministic moulds' ceiling (coverage ~0.36–0.46) and 84.1 showed the single-slot model
mapper is inert (a small model hallucinates slots; a strong one answers `none` under the "at most ONE attribute" contract).
Here the model does only the LINGUISTIC part — list every first-person fact as {attribute in the user's own words, value
copied verbatim} — and the deterministic side keeps everything that protects precision: the slot comes from the closed
vocabulary (`normalise_key`, `infer_slot_from_value`), the value must be literally in the text (`value_in_text`), predicates
and hedges are rejected (`value_gate`), third-party possessors are dropped, modality is the store's (`utterance`), only CLOSED
slots are written, the regex's writes in the same message win and the extractor may only ADD slots. Runs in the turn TAIL
(after the reply) so the pre-reply path is untouched; the bench calls it directly.
"""
from __future__ import annotations

import json
import logging
from typing import Callable, List, Optional

import re

from .fact_detect import _VALUE_STOP, _clean_value
from .slots import _tokens, base_slot, infer_slot_from_value, is_slot, normalise_key, value_in_text
from .value_gate import is_attribute_value, third_party_attr, third_party_sentence

log = logging.getLogger("hmgfu.fact_spans")

SPAN_PROMPT = (
    "List every durable fact the USER states about THEMSELVES in the message — their name or nickname, where they live, "
    "their job or employer, their main project or what they are currently working on, birthday, a favourite (colour, food, "
    "drink, music, team, programming language) — a current preference the user states as their own (\"I prefer X\", "
    "\"prefiro X\", \"gosto de X\") counts as that favourite — the name of their own pet, the name of a family member, "
    "their car, a link or number they give as theirs, their timezone. "
    "For each fact give `attribute`: the attribute in the USER'S OWN WORDS as written in the message (for example "
    "\"favourite colour\", \"dog\", \"sister\", \"where I live\", \"employer\", \"nickname\", \"cor favorita\", \"cão\", "
    "\"empresa\"), and `value`: the value copied EXACTLY as written in the message, nothing added or translated. "
    "Do NOT list questions, hypotheticals, fiction, other people's facts, quotes, past facts, opinions, moods, states, "
    "plans, guesses or advice. If there is no such fact return an empty list. JSON only."
)
SPAN_SCHEMA = {
    "type": "object",
    "properties": {"facts": {"type": "array", "maxItems": 8, "items": {
        "type": "object", "properties": {"attribute": {"type": "string"}, "value": {"type": "string"}},
        "required": ["attribute", "value"]}}},
    "required": ["facts"],
}
_ORIGIN = {"from", "origin", "originally", "origem", "natural", "born", "nascido", "nascida", "nationality", "nacionalidade"}
_PROPER = re.compile(r"^(?:[A-Z][\w&.-]*|[A-Z]{2,})(?:\s+(?:[A-Z][\w&.-]*|d[aeo]s?|&))*$")
# "the name of my cat is Tigre" / "o nome do meu gato é Tigre": the NAME belongs to the possessed relation, not the user
_NAME_OF = re.compile(r"\b(?:name|nome)\s+(?:of|do|da|d[oa]s)\s+(?:my|our|meu|minha|nosso|nossa)\s+([a-zA-Z\u00C0-\u00FF]+)", re.IGNORECASE)
_RELATIVE_HEADS = {"sister", "brother", "mother", "mum", "mom", "father", "dad", "wife", "husband", "partner", "irmã", "irma", "irmão",
                   "irmao", "mãe", "mae", "pai", "esposa", "marido", "mulher", "namorada", "namorado", "dog", "cat", "cão", "cao", "gato",
                   "gata", "cadela", "pet"}


def extract_spans(text: str, chat_json: Callable[[str, dict], Optional[dict]]) -> List[dict]:
    """Model call + deterministic validation → [{key, value, path: 'spans'}] (closed slots only, grounded)."""
    try:
        out = chat_json(SPAN_PROMPT + "\n\nUSER MESSAGE:\n" + text.strip(), SPAN_SCHEMA)
    except Exception as exc:                          # advisory: a model failure never breaks the turn
        log.warning("span extractor failed (%s)", exc)
        return []
    facts = out.get("facts") if isinstance(out, dict) else None
    dets: List[dict] = []
    for f in facts or []:
        if not isinstance(f, dict):
            continue
        attr, val = str(f.get("attribute") or "").strip(), str(f.get("value") or "").strip().strip("'\"")
        if not attr or not val or len(val) > 80 or not value_in_text(val, text):
            continue                                  # GROUNDING: a value the user never wrote is not a fact
        val = _clean_value(val)                       # 84.3 DEV: "a Mazda BT-50" → Mazda BT-50 (the same cleaner as the regex path)
        if not val or third_party_attr(attr) or not is_attribute_value(val):
            continue                                  # "neighbour's dog"; predicate-shaped values
        if len(val) < 2 or val.lower() in _VALUE_STOP:
            continue                                  # 90.H1: the regex path's own value contract — a single character ("9") is not a value
        if set(_tokens(attr)) & _ORIGIN:
            continue                                  # 84.3 DEV: "I'm from Spain originally" — origin is not the home city
        key = normalise_key(attr.lower())
        if not is_slot(key):
            head_ok = any(t in _RELATIVE_HEADS for t in _tokens(attr))
            key = infer_slot_from_value(val) or (key if head_ok else key)
        if not is_slot(key):
            continue                                  # CLOSED slots only — open keys are the precision leak (84.2)
        if re.match(r"https?://", val, re.IGNORECASE) and not key.endswith("_link"):
            continue                                  # 84.3 DEV: a URL is only ever a *_link value
        if key == "identity.job" and _PROPER.match(val):
            key = "identity.company"                  # 84.3 DEV: "trabalho na EDM" — a proper name as "job" is the employer
        if key in ("identity.company", "project.main") and not val[:1].isupper():
            continue                                  # 90.G2/90.H3: an employer or a project is a NAME — "district hospital", "the weather report for
                                                      # tomorrow" describe a place or a task, they do not name one (the regex path is unchanged)
        if key == "identity.name":
            m = _NAME_OF.search(text)
            if m:                                     # 84.3 DEV: "o nome do meu gato é Tigre" names the cat, not the user
                key = normalise_key(m.group(1).lower())
                if not is_slot(key):
                    continue
        dets.append({"key": key, "value": val, "supersedes": None, "path": "spans"})
    return dets


def registry_span_extractor(registry, role: str = "nano") -> Callable[[str], List[dict]]:
    """Bind the extractor to a provider role (nano | chat) with grammar-constrained JSON, no reasoning."""
    def chat_json(prompt: str, schema: dict):
        out = registry.chat_for_role(role, [{"role": "user", "content": prompt}], json_mode=True, temperature=0.0,
                                     format_schema=schema, think=False)
        content = out.get("content") if isinstance(out, dict) else out
        return json.loads(content) if isinstance(content, str) else content
    return lambda text: extract_spans(text, chat_json)


def apply_spans(store, text: str, source: str, extractor: Callable[[str], List[dict]], skip_keys=(), skip_values=()) -> List[dict]:
    """Run the extractor on the message's DECLARATIVE sentences (the store's modality rules) and write what the regex did
    not: a key the regex wrote this message (`skip_keys`) is never overwritten; a VALUE the regex wrote this message
    (`skip_values`, 90.G2) is not a second fact under another slot ("Bernardo" is the name, not also a nickname); name slots
    keep the name-shape gate; cardinality assigns `.2` to a second pet of the same species. Returns the store's change records."""
    from .facts import _cardinality, name_value_ok
    from .utterance import declarative_clauses, valid_from_of
    decl = " ".join(c["text"] for c in declarative_clauses(text) if not third_party_sentence(c["text"]))   # 84.3: someone else's sentence never reaches the model
    if not decl.strip():
        return []
    valid_from = valid_from_of(text)
    skip_bases = {base_slot(k) for k in skip_keys}                   # 84.3 DEV: the regex handled that slot FAMILY this message
    skip_vals = {str(v).strip().lower() for v in skip_values if v}                 # 90.G2
    from .fact_detect import _clean_value                     # 95.30: one cleaner for regex and span values
    from .slots import is_reference_to_attribute
    raw = extractor(decl)
    for d in raw:
        d["value"] = _clean_value(str(d.get("value") or ""))
    dets = [d for d in raw if base_slot(d["key"]) not in skip_bases and name_value_ok(d["key"], d["value"])
            and d["value"].strip().lower() not in skip_vals and not is_reference_to_attribute(d["key"], d["value"])]
    seen: set = set()
    dets = [d for d in dets if not ((d["key"], d["value"].lower()) in seen or seen.add((d["key"], d["value"].lower())))]
    dets = _cardinality(dets, decl)
    changes = []
    for d in dets:
        if valid_from:
            d["valid_from"] = valid_from
        ch = store._apply_one(d, decl, source)
        if ch:
            changes.append(ch)
    return changes
