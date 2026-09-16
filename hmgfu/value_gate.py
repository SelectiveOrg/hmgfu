"""Phase 83.1 — a VALUE is an attribute value, not a predicate (reserved-set v5 family i: 14 false writes on negatives).

"My battery is at 5 percent", "my flight is at 6", "my favourite is the one on the left", "my internet is slow", "my name
is unusual", "o meu plano é acabar até sexta" all fit the "my X is Y" mould and none states an attribute value. The gate
is lexical and deterministic: a value that opens with a preposition or adverbial, a determiner + pronoun/ordinal, a
state/quality adjective, or a Portuguese infinitive phrase is a predicate; a hedge cue around the claim ("maybe …, or
maybe …", "talvez", "acho que") makes it a guess; a possessor that is not a family relation ("my neighbour's dog") makes
it someone else's attribute. Used by `fact_detect` before any generic or explicit-name write.
"""
from __future__ import annotations

import re
from typing import Optional

_PREP_HEAD = {"at", "in", "on", "from", "to", "until", "till", "since", "into", "onto", "by", "às", "as", "ao", "aos", "em",
              "no", "na", "nos", "nas", "num", "numa", "para", "por", "com", "sem", "até", "ate", "desde", "sobre", "entre"}
_DET_PRON = re.compile(r"^(?:the|o|a|os|as)\s+(?:one|ones|da|do|dos|das|de|first|second|third|last|next|other|same|"
                       r"primeir[oa]|segund[oa]|terceir[oa]|[uú]ltim[oa]|outr[oa]|mesm[oa]|pr[oó]xim[oa])\b", re.IGNORECASE)
_STATE = {"slow", "fast", "hard", "easy", "unusual", "weird", "strange", "odd", "long", "short", "big", "small", "huge", "tiny",
          "difficult", "simple", "complicated", "quiet", "loud", "high", "low", "empty", "full", "lost", "gone", "dead", "alive",
          "old", "new", "stressful", "boring", "busy", "free", "late", "early", "fine", "great", "bad", "good", "ready", "broken",
          "off", "on", "over", "done", "flat", "dying", "expensive", "cheap", "hot", "cold", "wet", "dry", "sick", "tired", "happy",
          "sad", "angry", "wrong", "right", "true", "false", "better", "worse", "best", "worst", "terrible", "awful", "perfect",
          "lento", "lenta", "rápido", "rápida", "rapido", "rapida", "difícil", "dificil", "fácil", "facil", "invulgar", "estranho",
          "estranha", "comprido", "comprida", "curto", "curta", "grande", "pequeno", "pequena", "cheio", "cheia", "vazio", "vazia",
          "velho", "velha", "novo", "nova", "stressante", "chato", "chata", "ocupado", "ocupada", "livre", "atrasado", "atrasada",
          "pronto", "pronta", "partido", "partida", "avariado", "avariada", "caro", "cara", "barato", "barata", "quente", "frio",
          "fria", "doente", "cansado", "cansada", "feliz", "triste", "zangado", "zangada", "errado", "errada", "certo", "certa",
          "melhor", "pior", "péssimo", "péssima", "perfeito", "perfeita", "complicado", "complicada", "simples"}
_VERB_PT = re.compile(r"^[a-zà-ú]+(?:ar|er|ir)\s+(?:at[eé]|para|em|de|com|por|a|o|as|os|amanh[aã]|hoje|cedo|tarde|mais|menos)\b", re.IGNORECASE)
_HEDGE = re.compile(r"\b(?:maybe|perhaps|probably|possibly|i think|i guess|i suppose|not sure|talvez|provavelmente|se calhar|"
                    r"acho que|penso que|julgo que|n[aã]o tenho a certeza|qualquer coisa como|something like)\b", re.IGNORECASE)
_OR_HEDGE = re.compile(r"^\s*,?\s*(?:or|ou)\s+(?:maybe|perhaps|talvez|se calhar)\b", re.IGNORECASE)
_POSSESSOR = re.compile(r"^([a-zÀ-ÿ]+)(?:'s|’s)\s+", re.IGNORECASE)
_RELATIONS = {"sister", "brother", "mother", "mum", "mom", "father", "dad", "wife", "husband", "partner", "son", "daughter",
              "girlfriend", "boyfriend", "fiancée", "fiance", "fiancé", "spouse", "grandmother", "grandfather", "grandma",
              "grandpa", "aunt", "uncle", "cousin", "niece", "nephew", "dog", "cat", "pet", "kid", "child", "baby", "twin"}


_STATE_TAIL = {"to", "de", "for", "para", "at", "in", "em", "on", "than", "do", "que", "enough", "demais", "and", "e", "but", "mas",
               "again", "outra", "lately", "today", "hoje", "now", "agora", "as", "como"}
_PRON_HEAD = {"one", "ones", "da", "do", "dos", "das", "first", "second", "third", "last", "next", "other", "same",
              "primeiro", "primeira", "segundo", "segunda", "terceiro", "terceira", "outro", "outra", "mesmo", "mesma"}


def is_attribute_value(value: str) -> bool:
    """False for a predicate-shaped value; True for anything that could be an attribute value (names, colours, numbers, URLs…)."""
    v = (value or "").strip()
    if not v:
        return False
    toks = v.split()
    head = toks[0].lower().strip(".,;:")
    if head in _PREP_HEAD and len(toks) > 1:
        return False
    if _DET_PRON.match(v) or (head in _PRON_HEAD and len(toks) > 1):
        return False                                   # "the one on the left" — also after the article was stripped
    if head in _STATE and (len(toks) == 1 or toks[1].lower().strip(".,") in _STATE_TAIL):
        return False                                   # "slow", "hard to describe", "difícil de descrever" — but "cold hibiscus tea" is a drink
    if _VERB_PT.match(v):
        return False
    return True


def hedged(text: str, start: int, end: int) -> bool:
    """A hedge cue just before the claim, or an "or maybe" right after its value, makes the claim a guess — no write."""
    return bool(_HEDGE.search(text[max(0, start - 24):start])) or bool(_OR_HEDGE.match(text[end:end + 16]))


_ROLES = (r"neighbou?rs?|boss(?:es)?|chefes?|colleagues?|colegas?|friends?|amig[oa]s?|cousins?|prim[oa]s?|aunts?|tias?|uncles?|tios?|"
          r"nephews?|nieces?|sobrinh[oa]s?|teachers?|professor(?:a|es|as)?|landlords?|senhori[oa]s?|coworkers?|classmates?|roommates?|"
          r"manager|gerente|doctor|m[eé]dic[oa]|grandm(?:a|other)|grandpa|grandfather|av[oó]|avô|avó|in-?laws?|sogr[oa]s?")
_THIRD_PARTY_SUBJECT = re.compile(r"^\s*(?:(?:my|our|the|o meu|a minha|o nosso|a nossa|a|o|um|uma)\s+)?(?:" + _ROLES + r")\b(?:\s+[A-Z\u00C0-\u00DD]\w+)?\s+"
                                  r"(?:drives?|lives?|works?|is|are|has|have|likes?|prefers?|calls?|mora|vive|trabalha|conduz|anda|gosta|chama-se|é|tem|prefere)\b",
                                  re.IGNORECASE)
_THIRD_PARTY_POSSESSOR = re.compile(r"\b(?:" + _ROLES + r")(?:'s|’s)\s+\w|\b(?:d[oa]s?|de)\s+(?:meu|minha|nosso|nossa)\s+(?:" + _ROLES + r")\b", re.IGNORECASE)


def third_party_sentence(sentence: str) -> bool:
    """"Our neighbour Rui drives a Hilux", "my cousin's favourite drink is X", "a bebida favorita do meu primo é X",
    "Aunt Rosa lives in Gurué" — the sentence is about someone else (84.3)."""
    s = (sentence or "").strip()
    return bool(_THIRD_PARTY_SUBJECT.match(s)) or bool(_THIRD_PARTY_POSSESSOR.search(s))


_PRONOUN_POSSESSOR = re.compile(r"^(?:their|his|her|its|your|someone(?:'s)?|somebody(?:'s)?|dele|dela|deles|delas|teu|tua|seu|sua)\b", re.IGNORECASE)


# 91.S1: a relation licences the user to own that person's IDENTITY (`family.sister_name` is a fact about the user's
# family), not everything that person owns. The registry's family slots are all `*_name`, so the line is exactly there.
_RELATION_IDENTITY = re.compile(r"^(?:name|first name|full name|nome(?: pr[oó]prio| completo)?)\b", re.IGNORECASE)


def third_party_attr(attr: str) -> bool:
    """"neighbour's dog", "boss's car" — a possessor that is not a family relation or pet is not the user (83.1). 90.H3: a pronoun
    possessor that is not the user's ("their project", "his job", "o projecto dele") names someone else's attribute.
    91.S1: a RELATION's property is the relation's, not the user's — "my wife's lucky number" was normalising to the
    user's own `misc.lucky_number` and overwriting it (audit P1, and the reserved run of 90.O). Only the identity of
    that relation stays a fact about the user."""
    a = (attr or "").strip()
    if _PRONOUN_POSSESSOR.match(a):
        return True
    m = _POSSESSOR.match(a)
    if not m:
        return False
    if m.group(1).lower() not in _RELATIONS:
        return True
    rest = a[m.end():].strip()
    return not (rest == "" or bool(_RELATION_IDENTITY.match(rest)))


def utterance_subject(text: str) -> dict:
    """91.V1 — what an utterance is ABOUT: {slot: value} from its own detections, whether or not they change anything.
    A restated value writes no history row but is still the subject of the next "that's wrong"; a turn with no fact
    leaves no subject at all. Imported lazily to keep the module graph acyclic."""
    from .fact_detect import detect_facts
    from .slots import normalise_key
    from .utterance import declarative_text
    try:
        decl = declarative_text(text)
        return {normalise_key(d["key"]): d.get("value") for d in detect_facts(decl)} if decl else {}
    except Exception:
        return {}


def correction_antecedent(text: str, subject: Optional[dict], held: dict) -> list:
    """91.V1 — the slot a bare correction refers to ("that's wrong; it's actually Lichinga"), or None.

    `subject` is what the PREVIOUS utterance was about — {key: value} from its own detections — and `held` is what the
    store currently holds. The first version of this used the last row of the fact history, and the independent
    verification broke it three ways: restating a value writes no row, so "that" pointed at an older subject; a turn
    with no fact leaves no row at all; and history knows nothing of turns or sessions. Reproduced:
    `I live in Nacala. / My favourite colour is teal. / I live in Nacala. / That's wrong, it's Lichinga.` put Lichinga
    in the COLOUR.

    So the antecedent must be SUPPORTED: the previous utterance was about exactly one slot, and the store still holds
    the value that utterance asserted. Not unique, not supported, or nothing remembered -> return None and write
    nothing. The caller then runs this candidate through the ordinary validations, like any other.
    """
    from .utterance import bare_correction
    value = bare_correction(text)
    if not value or not is_attribute_value(value) or not subject or len(subject) != 1:
        return []
    key, asserted = next(iter(subject.items()))
    if not asserted or str(held.get(key, "")).strip().lower() != str(asserted).strip().lower():
        return []                        # the antecedent is no longer the state of the world: do not guess
    return [{"key": key, "value": value, "verbatim": (text or "").strip(), "by_reference": True}]

# 91.X2 — subject -> relation -> value. A clause OPENS with discourse connectors that are not part of
# the subject and CLOSES with adverbs that are not part of the attribute. Both are closed grammatical
# classes in EN and PT, so this is a rule about clauses, not a list of sentences. It replaces two
# ad-hoc lists that had grown inside fact_detect: five openers with a "take the last word" heuristic
# in the "<value> is my <attr>" mould, and six trailing adverbs in the "my <attr> is <value>" one.
_OPENER = (r"actually|but|and|so|or|then|also|though|however|yet|besides|well|ok|okay|anyway|"
           r"mas|por[eé]m|contudo|ent[aã]o|tamb[eé]m|tambem|bem|ali[aá]s|alias|enfim|ent[aã]o")
# these double as answers or NEGATIONS, so they only open a clause when a comma marks the discourse
# use ("no, green is my dog"). Stripping a bare "no"/"nao" would turn a denial into a claim.
_OPENER_COMMA = r"no|yes|sim|n[aã]o|nao|e|ou"
_OPENERS = re.compile(r"^(?:(?:(?:" + _OPENER + r")[,\s]+|(?:" + _OPENER_COMMA + r")\s*,\s*))+", re.IGNORECASE)
_COMPLEMENTIZER = re.compile(r"^.*\b(?:that|which|who|que|quem)\s+", re.IGNORECASE)
_TRAILING_ADVERB = re.compile(r"[_\s]+(?:also|too|as[_\s]well|now|today|currently|these[_\s]days|"
                              r"agora|hoje|tamb[eé]m|tambem|ainda)$", re.IGNORECASE)
_CONNECTOR = re.compile(r"^(?:" + _OPENER + r"|" + _OPENER_COMMA + r")$", re.IGNORECASE)


def clause_subject(value: str) -> str:
    """The subject of a copula is the head of ITS clause. Whatever a discourse connector or a
    complementizer puts in front belongs to the previous clause, not to the value:
    "but green" -> "green", "you should know that green" -> "green". A genuine multi-word value
    ("Teodoro H. Ferreira", "black and white") has neither and comes back untouched."""
    out = _OPENERS.sub("", value or "").strip()
    cut = _COMPLEMENTIZER.match(out)
    if cut:
        out = out[cut.end():].strip()
    return _OPENERS.sub("", out).strip()


def clause_attr(attr: str) -> str:
    """An adverb closing the clause is not part of the attribute: "dog also" is still the dog."""
    prev = None
    while prev != attr:
        prev, attr = attr, _TRAILING_ADVERB.sub("", attr or "")
    return attr


def is_connector(word: str) -> bool:
    """A discourse connector is never a name, whatever mould produced it (defence in depth: the
    single-token branch of the name-shape gate used to accept any non-numeric word)."""
    return bool(_CONNECTOR.match((word or "").strip()))

# 91.Y — a proposition embedded under a governing clause is NOT automatically the user's own claim.
# 91.X2's subject extraction cut through a complementizer and discarded the governing clause without
# preserving its semantic status, so "I never said that Green is my dog" became a claim that Green is
# the dog. Stripping a discourse connector and stripping a denial are not the same operation.
#
# The contract implemented here is the write-side counterpart of the modality contract stated in
# utterance.py: a subordinate proposition is asserted by the USER only when the clause governing it is
# an assertive speech act of the user's own. It is an ALLOW-LIST of that frame, not a deny-list of
# attitudes, so an unknown governing verb fails CLOSED -- a denial, a doubt, an intention, a report, a
# third-person subject or a question all leave the complement unasserted. That is the same discipline
# as _INTENT's _SPEECH_ACT guard in utterance.py, which already keeps "I want to tell you that my name
# is X" an assertion while "I want to be called X" is only an intention.
_ASSERTIVE_FRAME = re.compile(
    r"^(?:"
    r"(?:i|we|eu|n[oó]s)\s+(?:just\s+|also\s+|only\s+)?"
    r"(?:want\s+to|wanted\s+to|need\s+to|have\s+to|must|should|would\s+like\s+to|"
    r"quero|queria|preciso\s+de|devo|gostava\s+de|gostaria\s+de)?\s*"
    r"(?:tell\s+you|telling\s+you|say|saying|mention|mentioning|add|note|repeat|confirm|clarify|"
    r"dizer|digo|contar|conto|referir|refiro|acrescentar|repetir|confirmar|esclarecer)"
    r"|(?:you|voc[eê]|tu)\s+(?:should|must|need\s+to|deves?|deve|precisas?\s+de|tens?\s+de)\s+"
    r"(?:know|note|remember|understand|saber|notar|lembrar|perceber)"
    r"|(?:the\s+)?(?:truth|fact)\s+is|(?:a\s+)?verdade\s+[eé]"
    r")\b", re.IGNORECASE)
# derived from the existing _HEDGE inventory rather than restating it, so the two cannot drift apart
_HEDGE_LEAD = re.compile(r"^" + _HEDGE.pattern + r"[\s,]+", re.IGNORECASE)
# a governor that denies, questions or hedges never asserts its complement, whatever verb it uses
_UNASSERTIVE = re.compile(r"\b(?:not|never|n[aã]o|nunca|jamais)\b|n't\b|\?", re.IGNORECASE)


def clause_governor(value: str) -> str:
    """The material the subject extraction removes that actually GOVERNS the proposition: a clause
    ending in a complementizer, or a hedge. Bare discourse connectors are excluded -- they open a
    clause without governing it, which is why "Actually Green is my dog" is still a claim."""
    out = _OPENERS.sub("", value or "").strip()
    cut = _COMPLEMENTIZER.match(out)
    if cut:
        return out[:cut.end()].strip()
    hedge = _HEDGE_LEAD.match(out)
    return hedge.group(0).strip() if hedge else ""


def clause_asserted(value: str) -> bool:
    """Whether the user asserts the proposition whose subject `clause_subject` extracts.

    91.Z: this is now a DELEGATION. The judgement lives once, in `utterance.governed_proposition`,
    which classifies propositions for every write path at the choke point in `FactStore._resolve`.
    Keeping the name means existing callers and tests exercise the real contract instead of a
    second copy of it -- the parallel layer the 91.Y review objected to is gone, not duplicated."""
    from .utterance import governed_proposition          # local: utterance must stay import-light
    return governed_proposition(value or "")[1] == "assert"


# 92.E2 — is a router-supplied DIRECTIVE candidate supported by the instruction it claims to read?
# A literal format is text the user asked to see, so it must be quoted in the request; a content spec
# ("a short joke") is a description and never appears literally. Without this, a candidate outranked
# the local detectors and a search POLICY was persisted as an output_prefix with the value "none".
_LITERAL_DIRECTIVE = ("output_prefix", "output_suffix")


def directive_candidate_supported(det, text: str) -> bool:
    """Whether a directive candidate may stand against the text it was extracted from."""
    if not isinstance(det, dict) or not det.get("kind"):
        return False
    if det.get("clear"):
        return True                                   # a stop request carries no value to evidence
    value = str(det.get("value") or "").strip()
    if not value:
        return False                                  # no value: it cannot be a format at all
    if det["kind"] in _LITERAL_DIRECTIVE:
        req = format_request(text or "")              # a format must be REQUESTED, not merely mentioned
        return bool(req) and req[0] == det["kind"] and value.lower() in req[1].lower()
    return True


def format_request(text: str):
    """(kind, tail) where a LITERAL output format is actually requested, else None.

    92.E2: presence of a value is not authorisation. A request is a prefix/suffix cue standing in
    directive context and NOT negated -- "Never start your replies with the word none" carries the
    cue but refuses it, and "...; none of your guesses should replace evidence" carries no cue at
    all. The cues, the context test and the stop cues are directives.py's own, imported locally
    because directives imports this module at module level."""
    from .directives import _PREFIX_RE, _STOP_CUES, _SUFFIX_RE, _is_directive_context
    for kind, rx in (("output_suffix", _SUFFIX_RE), ("output_prefix", _PREFIX_RE)):
        for m in rx.finditer(text):
            if not _is_directive_context(text, m.start(), m.end()):
                continue
            if any(c in text[max(0, m.start() - 22):m.start()].lower() for c in _STOP_CUES):
                continue                              # the same clause that names the format refuses it
            return kind, text[m.end():]
    return None
