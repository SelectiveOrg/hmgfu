"""Deterministic fact DETECTION (Phase 62.10 split from facts.py at the 400-line ceiling).

Regex forms only — every value is copied from the user's words (grounded by construction).
`detect_facts` returns EVERY fact in an utterance, evaluated per clause so that
"my cat is Luna and my dog is Rex" yields both values (cardinality itself is a Phase 64 item).
The store (`facts.FactStore`) normalises keys through `slots.normalise_key`.
"""

from __future__ import annotations

import re
from typing import List, Optional

from .fact_moulds import (_ATTR_FORMS, _FORM_PATTERNS, _MARKED_HEAD, _PET_ENUM, _PET_FORMS, _SPECIES, _THE_IS, _THE_IS_PT, _TRANSITION_FORM, _VALUE, COPULA_EN, LEADING_CUE, LEADING_HEDGE,   # 83.3: the tables
                          ATTR_VALUE_MOULDS, FAMILY_APPOSITION, FAMILY_SLOT, INFER_MOULDS, JOB_COPULA, LANG_COPULA, MULTI_MOULDS,
                          PREP_CUT_SLOTS, RETRACT_VALUE_MOULDS, SPECIES_MOULDS, TOPIC_PREFIX, TOPIC_VALUE, apposition, split_job_language)
from .slots import infer_slot_from_value, is_slot, normalise_key
from .value_gate import (clause_asserted, clause_attr, clause_subject, hedged, is_attribute_value, is_connector,  # 83.1:
                         third_party_attr)                                    # hedges, third parties; 91.X2: clause shape

# "my <attr> is <value>" (value <= 6 tokens, initials allowed); 77.5: "-" in the attribute, more copulas, no genitive subject
_MY_IS = re.compile(r"(?<!\bof )\bmy\s+([a-z][\w' -]{1,30}?)\s+(?:" + COPULA_EN + r"|has always been|was always|will always be)\s+" + _VALUE, re.IGNORECASE)   # 95.51
_NEG_COPULA = re.compile(r"(?:isn'?t|is not|aren'?t|are not)\s*$", re.IGNORECASE)
# 77.5: "my music taste: marrabenta" — a colon form; WEAK (the store keeps it only when it resolves to a closed slot)
_MY_COLON = re.compile(r"(?<!\bof )\bmy\s+([a-z][\w'-]*(?:\s+[\w'-]+){0,2})\s*:\s*(?!//)" + _VALUE, re.IGNORECASE)   # ≤3 words; never a URL's "://"
# EXPLICIT name declarations — trusted (the user is literally naming themselves).
_NAME_EXPLICIT = re.compile(r"\b(?:my name is|i am called|i'm called|my real name is|chamo-me)\s+" + _VALUE, re.IGNORECASE)
# Bare copula "I am <X>" — DANGEROUS (H-05): only a name-SHAPED <X> (_looks_like_name); "called" excluded, "not" KEPT (clears the name)
_NAME_COPULA = re.compile(r"\b(?:i am|i'm|(?:eu\s+)?sou(?:\s+[oa])?)\s+(?!called\b)" + _VALUE, re.IGNORECASE)   # PT "(eu) sou a Joana" (name-shape gated; 77.5 bare "sou")
# 77.5 (G): a fuller restatement of the SAME name later in the sentence wins — "I'm Petra, by the way — Petra Vidal"
_APPOSITION = r"(?:[—–\-:,]\s*)(?:(?:by the way|já agora|ja agora|a propósito|aliás)\s*)?[—–\-,:]?\s*{raw}((?:\s+[A-Z\u00C0-\u00DD][\w'.-]+){{1,3}})\b"
# Phase 62: only first-person declarative statements may reach the model-backed slot mapper
_DECLARATIVE_CUE = re.compile(r"\b(my|our|i am|i'm|i live|i work|i have|we have|call me|meu|minha|nosso|nossa|eu sou|sou|eu moro|moro|tenho|temos|chamo-me)\b",
                              re.IGNORECASE)
# 77.5: a verb-frame value ends before its complement ("nurse at the district hospital", "Python for work")
_PREP_CUT = re.compile(r"\s+(?:at|for|with|when|while|because|since|where|in|para|quando|porque|desde|com|onde|em|numa|num|na|no|nas|nos|daqui|de agora)\b.*$", re.IGNORECASE)
# PT "a minha <attr> (favorita) é <value>" — the Portuguese sibling of _MY_IS (69.4)
# 77.5 (H): a genitive "da minha irmã" / "do meu irmão" is a modifier, not the subject — "o prato favorito da minha irmã é X"
_MY_IS_PT = re.compile(r"\b(?:o |a )?(?<!\bda )(?<!\bdo )(?<!\bde )(?<!\bdas )(?<!\bdos )(?:meu|minha)\s+([a-z\u00C0-\u00FF][\w' \u00C0-\u00FF]{1,60}?)\s+(?:é|são|=|chama-se|chamam-se|sempre foi|foi sempre|será sempre)\s+" + _VALUE,
                       re.IGNORECASE)
# "(here is the) link/url ... (for|of|to) my <attr>: <URL>" / "link ... (da minha|do meu) <attr>: <URL>"
# — a URL value for a possessed attribute (the car-location link case). The URL is the value.
_LINK_FORM = re.compile(r"\b(?:link|url|endere[cç]o)\b[^:\n]{0,80}?\b(?:for|of|to|da minha|do meu|d[ao]s? meus?|"
                        r"d[ao]s? minhas?)\s+(?:my\s+|our\s+)?([a-zA-Z\u00C0-\u00FF]{3,20}(?:\s+[a-zA-Z\u00C0-\u00FF]{3,20})?)"
                        r"(?:\s*[:\s]\s*|\s+(?:é|is|=|is now|passou a ser|agora é|est[aá] agora em)\s+)(https?://\S+)", re.IGNORECASE)     # "… do meu carro é URL"
# possessive-first sibling: "(here is) my car location link: URL" / "o link da minha …" is covered above
# 77.5 (F): "… my car is parked at URL" / "o meu carro está estacionado em URL" — the URL locates the possessed asset
_LINK_FORM_POSS = re.compile(r"\b(?:my|our|o meu|a minha)\s+([a-zA-Z\u00C0-\u00FF]{3,20}(?:\s+[a-zA-Z\u00C0-\u00FF]{3,20})?)"
                             r"\s+(?:(?:link|url)\s*(?:[:\s]|is now|is|é|passou a ser)\s*|(?:is|est[aá]|fica)\s+(?:parked\s+|estacionad[oa]\s+)?(?:at|em|in|here at|aqui em)?\s*[:\s]*)(https?://\S+)",
                             re.IGNORECASE)
# a value that opens a complement clause or a prepositional phrase is an opinion, not an attribute
# ("my guess is that…", "my concern is about…", "a minha dúvida é sobre…")
_COMPLEMENT = re.compile(r"^(?:that|que|sobre|about|whether|if|se|to|de|para)\b", re.IGNORECASE)
# Retraction by SELECTOR (audit H): "I no longer have a dog" / "I don't have a cat anymore" / "já não tenho
# carro" clears the slot without the user repeating the stored value.
_RETRACT = re.compile(r"\b(?:i no longer have|i don't have|i do not have|i've no|ja nao tenho|já não tenho|"
                      r"nao tenho mais|não tenho mais|we no longer have|we don't have|we do not have|we've no|"
                      r"ja nao temos|já não temos|nao temos mais|não temos mais)\s+(?:a |an |any |um |uma |o |a )?([a-zA-Z\u00C0-\u00FF]{3,20})\b",
                      re.IGNORECASE)
# 67.5 update form: "here's the updated link: URL", "new number: 123", "atualizado: link ..." — no possessive,
# no attribute owner; the store resolves it to the single slot of the same VALUE TYPE when unambiguous.
_UPDATE_FORM = re.compile(r"\b(?:here'?s|here is|this is|aqui est[aá]|eis|o novo|a nova)\s+(?:the\s+|o\s+|a\s+)?"
                          r"(?:updated|new|correct|novo|nova|atualizado|atualizada)\s+([a-z][\w ]{2,30}?)\s*[:\-]\s*(\S+)",
                          re.IGNORECASE)
# "<value> is my <attr>['s name]" — e.g. "actually babys is my brothers name" (attr resolved by slots)
_V_IS_MY_ATTR = re.compile(r"\b" + _VALUE + r"\s+is my\s+([a-z][\w' -]{1,30}?)(?:'s|’s)?(?:\s+name)?\s*[.!?]?\s*$",
                           re.IGNORECASE)

_NEG_NEAR = re.compile(r"\b(?:not|no longer|never|n[aã]o|nunca)\b|n't\b", re.IGNORECASE)      # 77.5: PT negation words; 83.5: "Don't call me"
_TRAILING_NOT = re.compile(r"^\s*,?\s*(?:and\s+)?(?:not|n[aã]o|e n[aã]o)\s+([A-Z\u00C0-\u00DD][\w'-]+(?:\s+[A-Z\u00C0-\u00DD][\w'-]+)?)")

# ordinary words that follow "I am …" but are moods/states/actions, never names (H-05)
_NOT_NAME = {"not", "a", "an", "the", "here", "there", "good", "fine", "ok", "okay", "great",
             "tired", "happy", "sad", "busy", "ready", "sure", "sorry", "glad", "done", "late",
             "early", "hungry", "excited", "angry", "confident", "curious", "afraid", "worried",
             "very", "so", "really", "just", "still", "also", "now", "currently", "from", "in",
             "at", "on", "about", "back", "home", "out", "off", "up", "down", "one", "part",
             # 77.5 (A): states of a person or an animal that follow "my dog is …" / "my cat is …"
             "asleep", "awake", "sick", "ill", "thirsty", "outside", "inside", "gone", "lost", "missing", "dead", "alive",
             "old", "young", "big", "small", "cute", "lovely", "fat", "well", "unwell", "pregnant", "scared", "nervous",
             "doente", "cansado", "cansada", "feliz", "triste", "ocupado", "ocupada", "pronto", "pronta", "aqui", "ali",
             "bem", "mal", "velho", "velha", "novo", "nova", "dificil", "difícil", "facil", "fácil", "grande", "pequeno", "pequena"}
# lowercase tokens that may sit INSIDE a multi-word name ("Rute Machel dos Santos", "Maria de Lurdes")
_NAME_PARTICLES = {"de", "da", "do", "dos", "das", "e", "van", "von", "del", "della", "di", "la", "le", "du", "y", "bin", "ibn", "al"}


def _looks_like_name(value: str, strict: bool = True) -> bool:
    """Name-shape gate. STRICT (the bare copula and pet forms): every token capitalized (or an initial like 'H.'),
    the head not a mood/action word or gerund, at most 4 tokens — 'happy to be here', 'working on the project' fail.
    LENIENT (77.5, every NAME slot at the store): capitalised tokens with name particles between them ('Rute Machel
    dos Santos'), or ONE lowercase token that is not a state word ('mimi' passes; 'hungry again', '4 years old',
    'hard to spell for most people', 'difícil de pronunciar' do not)."""
    tokens = value.split()
    if not tokens or len(tokens) > (4 if strict else 5):
        return False
    head = tokens[0].lower()
    if head in _NOT_NAME or head.endswith("ing"):
        return False
    if strict:
        return all(t[:1].isupper() for t in tokens)
    if len(tokens) == 1:
        return not head[:1].isdigit() and not is_connector(head)   # 91.X2: 'but' is not a name
    return tokens[0][:1].isupper() and all(t[:1].isupper() or t.lower() in _NAME_PARTICLES for t in tokens)


_NAME_SLOT = re.compile(r"^(?:identity\.(?:name|alias)|family\.\w+_name|pet\.(?:\w+\.)?name)(?:\.\d+)?$")


def name_value_ok(key: str, value: str) -> bool:
    """77.5 (A): a NAME slot only takes a name-shaped value — 'my dog Rex is 4 years old' is a predicate about Rex,
    not a second name. Non-name slots are not gated here."""
    return not _NAME_SLOT.match(key or "") or _looks_like_name(value or "", strict=False)

# generic "my X is Y" where X is one of these is a mood/state, not a durable fact — skip
_TRANSIENT = {"name"}  # handled by the dedicated name path; avoid double-capture here
_VALUE_STOP = {"", "not", "a", "an", "the", "here", "there", "good", "fine", "ok", "okay", "wrong", "incorrect", "correct", "right", "what", "where", "which", "unknown", "for", "you", "them", "it", "this", "that", "me", "us",
               "esse", "essa", "isso", "este", "esta", "isto", "aquele", "aquela", "aquilo",   # 79.3: PT demonstratives are never values
               "tired", "happy", "sad", "busy", "ready", "sure", "not sure", "sorry"}
_ATTR_STOP = {"name", "friend", "guest", "problem", "point", "concern", "issue", "question",
              "job", "turn", "bad", "understanding", "apologies", "pleasure"}


# a value ends where the next clause begins; "and"/"e" cut ONLY before a new first-person claim (compound values survive, 69.4)
_CLAUSE_CUT = re.compile(r"\s+(?:(?:and|e)\s+(?=(?:my|i\b|meu|minha|eu\b|o meu|a minha|we\b|moro|vivo|resido|trabalho|sou|tenho|gosto|"
                         r"(?:o|a|os|as)\s+\w+\s+(?:dele|dela|deles|delas|é|são|chama-se)|the\s+\w+\s+(?:is|are)\b))|"
                         r"(?:so|but|because|then|always|from|that|which|when|while|since|"
                         r"don't|dont|do not|you|not|never|instead|please|"
                         r"mas|porque|entao|então|sempre|desde|nao|não|nunca)\b).*$", re.IGNORECASE)


def _plausible_open_fact(det: dict) -> bool:
    """An OPEN (non-schema) key is accepted from the regex only when it looks like an attribute
    (<=3 words, no digits) with a real value (not a function word). Anything else needs the
    model mapper or is dropped — better a missed open fact than 'last 3 emails = for'.
    77.5 (H): a RELATIVE's attribute ("sister's favorite food") is about someone else — not a user fact at all
    (a bare relative, "o meu primo é o Tino", still is: that is the user's cousin's name)."""
    from .slots import _ATTRIBUTE_WORDS, _RELATIVES, _tokens
    attr = det["key"].split(".", 1)[-1]
    val = (det.get("value") or det.get("clear_value") or "").strip()
    if re.search(r"\d", attr) or len(attr.split("_")) > 3:
        return False
    toks = set(_tokens(attr))
    if toks & _RELATIVES and toks & _ATTRIBUTE_WORDS:
        return False
    return len(val) >= 2 and val.lower() not in _VALUE_STOP


def _clean_value(v: str) -> str:
    v = v.strip().strip("'\"").strip()
    if re.match(r"https?://", v):
        return v.split()[0][:200]              # a URL is one opaque token
    v = _CLAUSE_CUT.sub("", v).strip()     # a value ends where the next clause begins (Phase 62)
    v = re.sub(r"^(?:called|named|chamad[oa]|de nome)\s+", "", v, flags=re.IGNORECASE)          # "called Mimi" → Mimi
    v = re.sub(r"^(?:a|o|um|uma|the|an)\s+(?=\S)", "", v)                                        # 83.2: "o índigo", "um Toyota Hilux", "o 27"
    v = LEADING_CUE.sub("", LEADING_HEDGE.sub("", v)).strip()      # 95.30: the introducing cue is not the value                                                            # R2: "actually X" -> X (leading twin of the trailing rule)
    v = _TRAILING_TIME.sub("", v).strip()                                                       # 77.5: "Quelimane há dois anos"
    # drop a trailing "instead"/"now"/"these days"
    v = re.sub(r"\s+(instead|now|actually|these days|nowadays|today|currently|hoje em dia|a[ct]ualmente|agora|anymore|any more|"
               r"mostly|mainly|sobretudo|principalmente|de corpo e alma|com orgulho|through and through|for good|de vez|lately|ultimamente)\s*$",
               "", v, flags=re.IGNORECASE).strip()                                                 # 83.2: trailing adverbs and idioms
    if len(v.split()) == 1 or len(v.split()[-1]) > 2:
        v = v.rstrip(".!?,;")                                                                        # 83.2: "Just call me T." → T; "week." → week
    return v[:80]


# 77.5 (F): a trailing TIME adverbial is not part of a value — "Aveiro o mês passado", "Quelimane há dois anos"
_TRAILING_TIME = re.compile(r"\s+(?:(?:o |no |a |na )?(?:m[eê]s|ano|semana|ver[aã]o|inverno) passad[oa]|"
                            r"last (?:month|year|week|spring|summer|autumn|fall|winter)|"
                            r"h[aá] (?:\d+|um|uma|dois|duas|tr[eê]s|quatro|cinco|v[aá]ri[oa]s|muit[oa]s|pouc[oa]s|alguns|algumas)\s+\w+|"
                            r"(?:for )?(?:\d+|a|an|two|three|four|five|several|many) (?:years?|months?|weeks?)(?: ago| now)?|"
                            r"recently|recentemente|ultimamente|lately)\s*$", re.IGNORECASE)


def detect_fact(text: str) -> Optional[dict]:
    """First detected fact (compatibility wrapper over `detect_facts`)."""
    found = detect_facts(text)
    return found[0] if found else None


def detect_facts(text: str) -> List[dict]:
    """ALL facts in the utterance (audit H: 'my name is X, I live in Y, and my dog is Z' is three
    writes). Each item: {key, value} | {key, clear_value} | {key, clear: True}. Multi-clause aware:
    an affirmed value wins over a negated one for the same key."""
    out: List[dict] = []
    for m in _RETRACT.finditer(text):
        out.append({"key": m.group(1).lower(), "clear": True})
    for clause in _split_clauses(text):
        out.extend(_detect_in_clause(clause))
    out.extend(_detect_moulds(text))                                       # 83.3 mould families; 83.4: last per key wins in the store
    topic = next((d["value"] for d in out if d["key"] == "_topic"), None)
    out = [d for d in out if d["key"] != "_topic"]
    if topic:                                                              # 83.3: "Food-wise, my weakness is badjias"
        for d in out:
            if not is_slot(normalise_key(d["key"])) and d.get("value"):
                d["key"] = topic
    seen: set = set()          # the same (key, value) reached through two surface forms = one fact
    return [d for d in out if not ((d["key"], d.get("value") or d.get("clear_value") or "") in seen
                                   or seen.add((d["key"], d.get("value") or d.get("clear_value") or "")))]


_CLAUSE_SPLIT = re.compile(r"\s*(?:[;,]\s*(?=(?:and\s+|e\s+)?(?:my|i\b|meu|minha|eu\b|o meu|a minha))|"   # 95.52: ";" too is a boundary only before a NEW claim
                           r"\s+(?:and|e|but|mas)\s+(?=(?:my|i\b|meu|minha|eu\b|o meu|a minha)))\s*", re.IGNORECASE)


def _split_clauses(text: str) -> List[str]:
    """Split only at boundaries that start a NEW first-person claim ("…, and my dog is Rex"), so
    values like "black and white" or "Teodoro H. Ferreira" are never cut."""
    parts = [p for p in _CLAUSE_SPLIT.split(text) if p and p.strip()]
    return parts or [text]


def _detect_in_clause(text: str) -> List[dict]:
    keys: dict = {}   # key -> {"pos": value|None, "neg": value|None}
    out: List[dict] = []
    # explicit declarations are trusted; the bare copula form must pass the name-shape gate
    for pattern, trusted in ((_NAME_EXPLICIT, True), (_NAME_COPULA, False)):
        for m in pattern.finditer(text):
            raw = _clean_value(m.group(1))
            if raw.lower() in _VALUE_STOP or len(raw) < 2 or raw.lower().startswith("not "):
                # "I'm not Sebastian" → negation of name=Sebastian
                neg = re.sub(r"^not\s+", "", raw, flags=re.IGNORECASE).strip()
                if neg and neg.lower() not in _VALUE_STOP:
                    keys.setdefault("name", {}).setdefault("neg", neg)
                continue
            if not trusted and not _looks_like_name(raw):
                continue   # "I am happy to be here" is NOT a name (H-05)
            if not is_attribute_value(raw) or hedged(text, m.start(), m.end()):
                continue   # 83.1: "my name is unusual", "maybe my name is …" are not names
            ext = re.search(_APPOSITION.format(raw=re.escape(raw)), text[m.end():])
            if ext and _looks_like_name(raw + ext.group(1)):
                raw = raw + ext.group(1)                                     # 77.5 (G): "I'm Petra, by the way — Petra Vidal"
            window = text[max(0, m.start() - 8):m.start()]
            keys.setdefault("name", {}).update({"neg" if _NEG_NEAR.search(window) else "pos": raw,
                                                **({"_trusted": True} if trusted else {})})   # R2: explicit form is trusted at the store too
    # Phase 62: common first-person declarative forms that are not "my X is Y" (closed-slot targets)
    for entry in _FORM_PATTERNS:
        pattern, slot, trusted = entry[0], entry[1], bool(entry[2]) if len(entry) > 2 else False
        for m in pattern.finditer(text):
            val = _clean_value(m.group(1))
            if slot in PREP_CUT_SLOTS:
                if _PREP_CUT.match(" " + val):
                    continue                                               # R2: a value that STARTS with a preposition is an anaphor, not a value
                val = _PREP_CUT.sub("", val).strip()                       # 77.5: the value ends before its complement
            if (len(val) >= 2 or m.group(1).strip().endswith(".")) and (trusted or val.lower() not in _VALUE_STOP):   # 83.2: "call me T."; 83.3: "I am Happy, that's my actual name"
                window = text[max(0, m.start() - 8):m.start(1)]             # 77.5 (C): the cue itself may carry the negation
                if slot == "identity.job":
                    val, lang = split_job_language(val)                      # 83.3: "programador de Kotlin" → job + language
                    if lang:
                        keys.setdefault("pref.language", {})["pos"] = lang
                keys.setdefault(slot, {})["neg" if _NEG_NEAR.search(window) else "pos"] = val
                if trusted:
                    keys[slot]["_trusted"] = True
    for pattern in _ATTR_FORMS:                                             # 77.5 (E): attribute-naming frames
        for m in pattern.finditer(text):
            attr = re.sub(r"\s+", "_", m.group(1).strip().lower())
            val = _clean_value(m.group(2))
            if attr not in _ATTR_STOP and len(val) >= 2 and val.lower() not in _VALUE_STOP and is_attribute_value(val):
                keys.setdefault(attr, {})["pos"] = val
    for m in _TRANSITION_FORM.finditer(text):                               # 77.5 (E): "used to be X, now it's Y"
        attr = re.sub(r"\s+", "_", m.group(1).strip().lower())
        old, new = _clean_value(m.group(2)), _clean_value(m.group(3))
        if attr not in _ATTR_STOP and len(new) >= 2 and new.lower() not in _VALUE_STOP:
            keys.setdefault(attr, {}).update(pos=new, neg=old or None)
    for pattern, vg, sg in _PET_FORMS:
        for m in pattern.finditer(text):
            val = _clean_value(m.group(vg))
            if len(val) >= 2 and val.lower() not in _VALUE_STOP and _looks_like_name(val):
                slot = _SPECIES.get(m.group(sg).lower(), "pet.name")
                window = text[max(0, m.start() - 8):m.start()]
                keys.setdefault(slot, {})["neg" if _NEG_NEAR.search(window) else "pos"] = val
    for m in list(_LINK_FORM.finditer(text)) + list(_LINK_FORM_POSS.finditer(text)):
        attr = re.sub(r"\s+", "_", m.group(1).strip().lower()) + "_link"
        keys.setdefault(attr, {})["pos"] = m.group(2).rstrip("?.,;)")
    for m in _UPDATE_FORM.finditer(text):
        attr = re.sub(r"\s+", "_", m.group(1).strip().lower())
        keys.setdefault(attr, {})["pos"] = _clean_value(m.group(2).rstrip("?.,;)"))
        keys[attr]["_update"] = True
    for m in _V_IS_MY_ATTR.finditer(text):
        attr = clause_attr(re.sub(r"\s+", "_", m.group(2).strip().lower()))          # 91.X2: "dog also" is the dog
        val = _clean_value(clause_subject(m.group(1)))     # 91.X2: the subject FIRST -- _CLAUSE_CUT keeps the
                                                          # left of a new clause, which is the bare connector
        if attr not in _ATTR_STOP and len(val) >= 2 and val.lower() not in _VALUE_STOP and not is_connector(val) and clause_asserted(m.group(1)):   # 91.Z: kept at the DETECTOR layer; it now DELEGATES to the single contract in utterance, so the parallel logic the review objected to is gone
            keys.setdefault(attr, {})["pos"] = val
    for m in (list(_MY_IS.finditer(text)) + list(_MY_IS_PT.finditer(text)) + list(_MY_COLON.finditer(text))
              + list(_THE_IS.finditer(text)) + list(_THE_IS_PT.finditer(text))):        # 95.39: article forms, weak
        attr = re.sub(r"\s+", "_", m.group(1).strip().lower())
        pre_negated = False
        if attr.rsplit("_", 1)[-1] in ("não", "nao", "nunca", "not", "never"):   # 79.3: "o meu nome NÃO é esse" — the negation
            attr = attr.rsplit("_", 1)[0]                                          # is not part of the attribute; it negates
            pre_negated = True
        attr = clause_attr(attr)                                                     # 83.3: "a minha base agora é Tete"
        if attr in _ATTR_STOP or attr in _TRANSIENT or apposition(m.group(1)):
            continue                                                       # 83.3: "my dog Simba is a rescue" — an apposition, not a name
        val = _clean_value(m.group(2))
        low = val.lower()
        if low in _VALUE_STOP or len(val) < 2 or _COMPLEMENT.match(m.group(2)):
            continue
        if third_party_attr(m.group(1)) or hedged(text, m.start(), m.end()):
            continue                                   # 83.1: "my neighbour's dog is Rex", "maybe my colour is teal, or maybe amber"
        if not is_attribute_value(re.sub(r"^not\s+", "", val, flags=re.IGNORECASE)):
            continue                                   # 83.1: "my battery is at 5 percent", "my internet is slow" are predicates
        if text[m.end():m.end() + 3] == "://":
            continue                                   # a bare URL scheme is never a value (the link forms own URLs)
        negated = pre_negated or low.startswith("not ") or _NEG_NEAR.search(m.group(2)[:6]) or \
            bool(_NEG_COPULA.search(text[m.start():m.start(2)]))       # 83.5: "my favourite colour isn't teal"
        val = re.sub(r"^not\s+", "", val, flags=re.IGNORECASE).strip()
        keys.setdefault(attr, {})["neg" if negated else "pos"] = val
        if m.re in (_THE_IS, _THE_IS_PT) and _MARKED_HEAD.search(m.group(1)):   # 95.39: an article form is the user's
            keys.pop(attr, None); continue                                  # own only when its head is unmarked
        if m.re is _MY_COLON or m.re is _THE_IS or m.re is _THE_IS_PT:
            keys[attr]["_weak"] = True                                      # 77.5/95.39: colon and article forms need a closed slot
    for key, v in keys.items():                       # 72.3: a trailing ", not X" / ", não X" names the value to retire
        if v.get("pos") and not v.get("neg"):
            m = _TRAILING_NOT.search(text[text.lower().find(v["pos"].lower()) + len(v["pos"]):] if v["pos"].lower() in text.lower() else "")
            if m:
                v["neg"] = m.group(1)
    for key, v in keys.items():
        if v.get("pos"):
            item = {"key": key, "value": v["pos"], "supersedes": v.get("neg")}
            if v.get("_update"):
                item["update"] = True
            if v.get("_weak"):
                item["weak"] = True
            if v.get("_trusted"):
                item["trusted"] = True                                     # 83.3: "I am Happy, that's my actual name"
            out.append(item)
        elif v.get("neg"):
            out.append({"key": key, "clear_value": v["neg"]})
    for m in _PET_ENUM.finditer(text):                                      # 77.5 (D): two named pets in one clause
        slot = _SPECIES.get(m.group(1).lower(), "pet.name")
        for val in (_clean_value(m.group(2)), _clean_value(m.group(3))):
            if _looks_like_name(val) and val.lower() not in _VALUE_STOP:
                out.append({"key": slot, "value": val, "supersedes": None})
    return out


def _detect_moulds(text: str) -> List[dict]:
    """83.3: the mould families of `fact_moulds` — multi-slot frames, species frames, family appositions, attribute-naming
    frames, value-inferred frames, and the topic prefix ("Food-wise, …" / "Em termos de comida, …") that re-keys an open
    attribute in the same message to the topic's slot."""
    out: List[dict] = []
    def push(key, val, trusted=False):
        val = _clean_value(val)
        if key.split(".2")[0] in PREP_CUT_SLOTS:
            val = _PREP_CUT.sub("", val).strip()
        if len(val) >= 2 and val.lower() not in _VALUE_STOP and (trusted or is_attribute_value(val)):
            item = {"key": key, "value": val, "supersedes": None}
            if trusted:
                item["trusted"] = True
            out.append(item)
    for pattern, slots in MULTI_MOULDS:
        for m in pattern.finditer(text):
            for slot, g in slots:
                if m.group(g):
                    push(slot, m.group(g))
    for pattern, sg, vg, ordinal in SPECIES_MOULDS:
        for m in pattern.finditer(text):
            slot = _SPECIES.get(m.group(sg).lower(), "pet.name") + (".2" if ordinal else "")
            if _looks_like_name(_clean_value(m.group(vg))):
                push(slot, m.group(vg))
    for m in FAMILY_APPOSITION.finditer(text):
        slot = FAMILY_SLOT.get(m.group(1).lower())
        if slot and _looks_like_name(m.group(2)):
            push(slot, m.group(2))
    for pattern, ag, vg in ATTR_VALUE_MOULDS:
        for m in pattern.finditer(text):
            key = normalise_key(m.group(ag).strip().lower())
            if is_slot(key):
                push(key, m.group(vg))
    for pattern in INFER_MOULDS:
        for m in pattern.finditer(text):
            val = _PREP_CUT.sub("", _clean_value(m.group(1))).strip()
            slot = infer_slot_from_value(val)
            if slot:
                push(slot, val)
    for pattern, slot, g in RETRACT_VALUE_MOULDS:                          # 83.5: retire ONE named value
        for m in pattern.finditer(text):
            val = _clean_value(m.group(g))
            if len(val) >= 2:
                out.append({"key": slot, "clear_value": val})
    for m in JOB_COPULA.finditer(text):
        push("identity.job", m.group(1))
    for m in LANG_COPULA.finditer(text):
        if infer_slot_from_value(m.group(1)) == "pref.language":
            push("pref.language", m.group(1))
    topic = None
    tm = TOPIC_PREFIX.match(text)
    if tm:
        word = next(g for g in tm.groups() if g)
        cand = normalise_key(word.lower())
        topic = cand if is_slot(cand) else None
    for pattern, fixed in TOPIC_VALUE:
        for m in pattern.finditer(text):
            slot = fixed or topic or infer_slot_from_value(_clean_value(m.group(1)))
            if slot:
                push(slot, m.group(1))
    if topic:
        out.append({"key": "_topic", "value": topic})                       # consumed by detect_facts: re-keys open attrs
    return out
