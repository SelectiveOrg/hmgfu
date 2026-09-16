"""Closed fact-slot schema (Phase 62) — ONE key per real-world attribute.

Root cause the autopsy found in BOTH PA3 and hmg-fu: fact keys were minted by an extractor
(LLM or regex), so one attribute fragmented into many spellings ("favorite_language",
"favorite_programming_language", "user:fav_language", "language:favorite", ...). Supersession
is keyed, so a correction retired only its own spelling and the others stayed "live".

This module is the single vocabulary. Every fact write (regex path, model path, legacy import)
passes its raw attribute through `normalise_key`, which returns a slot id from the closed
schema or a cleaned open-world key — never an invented spelling. `slot_schema()` is the
enum the constrained-decoding mapper is allowed to choose from (`map_to_slot`).
"""

from __future__ import annotations

import re
from typing import Callable, Dict, List, Optional

# id -> (label used in prompts/UI, aliases). Aliases are matched after normalisation
# (lower, no possessive, no "my"/"user:", morphology folded), first exact then token-subset.
SLOTS: Dict[str, dict] = {
    "identity.name":        {"label": "name",              "aliases": ["name", "full name", "real name", "nome", "nome completo"]},
    "identity.alias":       {"label": "preferred form of address",
                             "aliases": ["alias", "nickname", "greeting", "greeting preference",
                                         "call me", "alcunha", "tratamento"]},
    "identity.location":    {"label": "home city",
                             "aliases": ["location", "city", "home", "home city", "live in", "where i live",
                                         "cidade", "localizacao", "onde moro", "residence", "base", "home base", "casa", "town"]},
    "identity.birthday":    {"label": "birthday", "aliases": ["birthday", "date of birth", "aniversario"]},
    "identity.job":         {"label": "job",
                             "aliases": ["job", "job title", "profession", "occupation", "work as",
                                         "profissao", "trabalho", "cargo", "funcao", "posicao", "role"]},
    "identity.company":     {"label": "company", "aliases": ["company", "employer", "empresa", "entidade patronal", "empregador", "firm"]},
    "family.brother_name":  {"label": "brother's name",
                             "aliases": ["brother", "brother name", "brothers name", "irmao"]},
    "family.sister_name":   {"label": "sister's name", "aliases": ["sister", "sister name", "irma"]},
    "family.partner_name":  {"label": "partner's name",
                             "aliases": ["partner", "wife", "husband", "girlfriend", "boyfriend",
                                         "esposa", "marido", "mulher", "namorada", "namorado"]},
    "family.mother_name":   {"label": "mother's name", "aliases": ["mother", "mom", "mum", "mae"]},
    "family.father_name":   {"label": "father's name", "aliases": ["father", "dad", "pai"]},
    "pet.name":             {"label": "pet's name",
                             "aliases": ["pet", "pet name", "animal de estimacao", "animal"]},
    "pet.dog.name":         {"label": "dog's name",
                             "aliases": ["dog", "dog name", "dogs name", "cao", "cadela", "cachorro"]},   # 69.4 species
    "pet.cat.name":         {"label": "cat's name", "aliases": ["cat", "cat name", "cats name", "gato", "gata"]},
    "pet.species":          {"label": "pet species", "aliases": ["pet species", "kind of pet"]},
    "pref.language":        {"label": "favorite programming language",
                             "aliases": ["favorite language", "favorite programming language",
                                         "programming language", "preferred language", "language",
                                         "linguagem favorita", "linguagem de programacao", "go-to language", "language of choice",
                                         "linguagem de eleicao", "linguagem"]},
    "pref.color":           {"label": "favorite color",
                             "aliases": ["favorite color", "color", "cor favorita", "cor"]},
    "pref.food":            {"label": "favorite food",
                             "aliases": ["favorite food", "food", "dish", "meal", "comida favorita", "comida", "prato favorito", "prato"]},
    "pref.drink":           {"label": "favorite drink", "aliases": ["favorite drink", "drink", "bebida"]},
    "pref.music":           {"label": "favorite music", "aliases": ["favorite music", "music", "musica"]},
    "pref.team":            {"label": "favorite team", "aliases": ["favorite team", "team", "equipa"]},
    "pref.media":           {"label": "media preference",
                             "aliases": ["media preference", "preference media", "driving preference"]},
    "project.main":         {"label": "main project",
                             # 90.H3 (H-C): the extractor contract's own phrasing — "what they are currently working on" — names this slot
                             "aliases": ["project", "main project", "projeto", "working on", "trabalhar em"]},
    "asset.car":            {"label": "car", "aliases": ["car", "vehicle", "carro"]},
    "asset.car_location_link": {"label": "car location link",
                                "aliases": ["car location", "car location link", "link for car location",
                                            "link car location", "localizacao da viatura", "car link",
                                            "vehicle link", "viatura link", "carro link", "viatura"]},
    "misc.lucky_number":    {"label": "lucky number", "aliases": ["lucky number", "numero da sorte"]},
    "misc.timezone":        {"label": "timezone", "aliases": ["timezone", "time zone", "fuso horario"]},
}

_MORPH = {
    "favourite": "favorite", "fav": "favorite", "favarorite": "favorite", "favorites": "favorite",
    "colour": "color", "colours": "color", "colors": "color",
    "languages": "language", "lang": "language", "langs": "language", "prog": "programming",
    "dogs": "dog", "cats": "cat", "pets": "pet", "brothers": "brother", "sisters": "sister",
    # 90.M: European Portuguese spelling is a NORMALISATION, like favourite/colour above — the 1990 agreement dropped a silent
    # c/p before t/ç (projecto→projeto, acto→ato, directo→direto…). Only the pairs whose Brazilian form is in the slot
    # vocabulary matter; today that is exactly one of the 136 alias tokens (test v98 enumerates the family so a new alias is covered).
    "projecto": "projeto", "projectos": "projeto", "projetos": "projeto",
    "programming language": "programming language",
}
_NOISE = {"name", "is", "the", "of", "current", "now", "my", "user", "your", "favourite_name",
          "de", "o", "a", "do", "da", "meu", "minha", "preferred", "preference", "for", "located"}
_ACCENT = str.maketrans("áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ", "aaaaeeiooouc" + "AAAAEEIOOOUC")


def _tokens(raw: str) -> List[str]:
    s = (raw or "").translate(_ACCENT).lower()
    s = re.sub(r"^(user|agent|profile)\s*[:.]\s*", "", s)
    s = s.replace("'s", "").replace("’s", "")
    s = re.sub(r"[_:./\-]+", " ", s)
    s = re.sub(r"\bmy\b", " ", s)
    toks = [_MORPH.get(t, t) for t in re.findall(r"[a-z0-9]+", s)]
    return [t for t in toks if t]


_ALIAS_INDEX: List[tuple] = []          # (slot_id, alias_tokens, alias_content_tokens)
for _sid, _spec in SLOTS.items():
    for _alias in _spec["aliases"]:
        _at = _tokens(_alias)
        _ALIAS_INDEX.append((_sid, _at, [t for t in _at if t not in _NOISE]))
# longer aliases first so "favorite programming language" beats "language"
_ALIAS_INDEX.sort(key=lambda x: -len(x[1]))


_ORDINAL = re.compile(r"^(.+)\.(\d+)$")
# 74.3: a relative named together with an attribute word is the RELATIVE's attribute (never the relative's name slot)
_RELATIVES = {"sister", "brother", "mother", "mom", "mum", "father", "dad", "wife", "husband", "partner", "girlfriend",
              "boyfriend", "irma", "irmao", "mae", "pai", "esposa", "marido", "mulher", "namorada", "namorado", "cousin",
              "primo", "prima", "aunt", "uncle", "tia", "tio", "friend", "amigo", "amiga", "colleague", "colega"}
_ATTRIBUTE_WORDS = {"favorite", "color", "food", "drink", "language", "music", "team", "job", "city", "birthday", "car",
                    "comida", "cor", "bebida", "linguagem", "musica", "equipa", "profissao", "cidade", "aniversario",
                    "carro", "prato", "hobby", "book", "livro", "film", "filme"}


def base_slot(key: str) -> str:
    """'pet.dog.name.2' → 'pet.dog.name' (72.3 cardinality ordinal); other keys unchanged."""
    m = _ORDINAL.match(key or "")
    return m.group(1) if m and m.group(1) in SLOTS else (key or "")


def normalise_key(raw: str) -> str:
    """Raw attribute text (any spelling, any language of the schema) → slot id, else a cleaned
    open-world key `open.<tokens>`. Deterministic, no model."""
    raw = (raw or "").strip()
    if raw in SLOTS or raw.startswith("open.") or base_slot(raw) in SLOTS:
        return raw                              # idempotent: an already-normalised key is final
    toks = _tokens(raw)
    content = [t for t in toks if t not in _NOISE]
    if not toks:
        return "open.unknown"
    for sid, at, ac in _ALIAS_INDEX:
        # 90.K: an attribute whose tokens are ALL noise has no content to match on — `content == ac` would then match the one
        # alias whose content is also empty ("name" → identity.name), so "preference"/"my current" silently overwrote the user's
        # NAME. Exact alias-token equality still resolves those aliases ("name" → identity.name); content equality now requires
        # actual content on both sides.
        if toks == at or (content and content == ac):
            return sid
    tokset = set(content)
    if tokset & _RELATIVES and tokset & _ATTRIBUTE_WORDS:
        return "open." + "_".join(content)[:60]     # 74.3: "sister's favorite food" is the sister's attribute, not her name
    for sid, at, ac in _ALIAS_INDEX:
        if ac and set(ac) <= tokset:
            return sid
    return "open." + "_".join(content or toks)[:60]


# Value-class inference for a BARE "my favorite is X" (no attribute named): the value's class
# decides the slot. Small closed lists; anything else stays an open key rather than a guess.
_LANGUAGES = {"python", "rust", "java", "javascript", "typescript", "go", "golang", "c", "c++", "cpp", "c#",
              "csharp", "ruby", "php", "swift", "kotlin", "scala", "elixir", "erlang", "haskell", "lua",
              "perl", "r", "julia", "dart", "sql", "bash", "zig", "nim", "clojure", "ocaml", "f#", "matlab"}
_COLORS = {"red", "blue", "green", "teal", "yellow", "orange", "purple", "violet", "pink", "black", "white",
           "grey", "gray", "brown", "cyan", "magenta", "chartreuse", "indigo", "turquoise", "gold", "silver",
           "azul", "verde", "vermelho", "amarelo", "roxo", "preto", "branco", "laranja", "rosa", "cinzento"}


_DRINK_WORDS = {"tea", "chá", "cha", "coffee", "café", "cafe", "espresso", "expresso", "latte", "juice", "sumo", "beer", "cerveja", "wine",
                "vinho", "water", "água", "agua", "soda", "milk", "leite", "cocktail", "whisky", "rum", "gin", "vodka", "lemonade", "limonada"}
_FOOD_WORDS = {"xima", "matapa", "prawns", "camarão", "camarao", "rice", "arroz", "chicken", "frango", "fish", "peixe", "badjias", "chamussas",
               "pizza", "pasta", "soup", "sopa", "bread", "pão", "pao", "beans", "feijão", "feijao", "salad", "salada", "curry", "caril",
               "meat", "carne", "steak", "bife", "burger", "sandwich", "sandes", "cake", "bolo", "chocolate", "noodles", "sushi", "tacos"}


def infer_slot_from_value(value: str) -> Optional[str]:
    v = (value or "").strip().lower()
    if v in _LANGUAGES:
        return "pref.language"
    if v in _COLORS:
        return "pref.color"
    toks = re.findall(r"[\w\u00C0-\u00FF-]+", v)
    if toks and toks[-1] in _COLORS:
        return "pref.color"                                # 83.3: "mustard yellow", "olive green"
    if any(t in _DRINK_WORDS for t in toks):
        return "pref.drink"
    if any(t in _FOOD_WORDS for t in toks):
        return "pref.food"
    return None


def value_in_text(value: str, text: str) -> bool:
    """Whole-token, accent/case-insensitive containment: is `value` literally present in `text`?
    Used to GROUND every model-proposed value (audit C1: the mapper accepted 'Alice' for a colour
    sentence) and to match stale values without substring accidents (audit H: 'Rust' ⊂ 'Trust')."""
    v = " ".join(re.findall(r"[a-z0-9]+", (value or "").translate(_ACCENT).lower()))
    t = " " + " ".join(re.findall(r"[a-z0-9]+", (text or "").translate(_ACCENT).lower())) + " "
    if not v:
        return False
    if re.match(r"https?://", (value or "").strip(), re.IGNORECASE):
        return (value or "").strip().lower().rstrip("?.,;)") in (text or "").lower()
    return (" " + v + " ") in t


_ATTR_STOPWORDS = {"where", "with", "link", "for", "kind", "form", "address", "real", "full", "home"}
# for ATTRIBUTE matching "name" is a real cue (unlike key normalisation, where it is noise)
_ATTR_IGNORE = _NOISE - {"name"}


def attribute_tokens(key: str) -> set:
    """Content tokens that name the attribute of `key` (its label + aliases; an open key's own words)."""
    spec = SLOTS.get(key)
    if spec is None:
        return {t for t in _tokens(key.split(".", 1)[-1]) if t not in _ATTR_IGNORE and len(t) >= 3}
    toks = set()
    for alias in [spec["label"]] + list(spec["aliases"]):
        toks.update(t for t in _tokens(alias) if t not in _ATTR_IGNORE and len(t) >= 3 and t not in _ATTR_STOPWORDS)
    return toks


def relation_in_clause(slot: str, text: str, value: str) -> bool:
    """72.3: the mapper's relation cue and its value must sit in the SAME clause. True when they do, or when the
    text names the relation nowhere (a pure paraphrase the mapper is for); False when the relation is named in
    another clause than the value ("my mother's name is Ana and my favorite color is amber" → amber≠mother)."""
    from .fact_detect import _split_clauses
    cues = attribute_tokens(slot)
    clauses = _split_clauses(text or "") or [text or ""]
    named_anywhere = any(set(_tokens(c)) & cues for c in clauses)
    if not named_anywhere:
        return True
    return any(value_in_text(value, c) and (set(_tokens(c)) & cues) for c in clauses)


def is_reference_to_attribute(key: str, value: str) -> bool:
    """95.30: "my main project" is a REFERENCE to project.main, not its value -- every content word of
    the value is one of the attribute's own tokens (or a possessive). A name, a place, a title has at
    least one word of its own."""
    words = [w for w in re.findall(r"[^\W\d_]+", (value or "").casefold()) if len(w) > 1]
    if not words:
        return False
    own = attribute_tokens(key) | {"my", "our", "the", "meu", "minha", "nosso", "nossa", "o", "a", "de", "do", "da"}
    return all(w in own or w.rstrip("s") in own for w in words)


def mentions_attribute(key: str, text: str) -> bool:
    """Does `text` talk about the slot's attribute? Whole tokens, with inflections of the longer cue words
    ("lived"/"living" ↔ "live", "cidades" ↔ "cidade") — 72.6g: the stale-node gate missed "you lived in Chimoio"."""
    attr = attribute_tokens(key)
    if not attr:
        return True
    toks = set(_tokens(text))
    if toks & attr:
        return True
    stems = {a for a in attr if len(a) >= 4}
    return any(t.startswith(a) for t in toks for a in stems)


def relation_conflict(slot: str, text: str) -> bool:
    """True when `text` names a DIFFERENT slot's attribute and none of `slot`'s — the model mapper's relation is
    then unsupported by the words (69.4: 'A minha cor favorita é âmbar' can never be family.mother_name)."""
    words = set(_tokens(text))
    if words & attribute_tokens(slot):
        return False
    own_family = slot.split(".", 1)[0]
    for other in SLOTS:
        if other != slot and words & attribute_tokens(other) and not (
                other.split(".", 1)[0] == own_family == "pet"):
            return True
    return False


def label_for(key: str) -> str:
    m = _ORDINAL.match(key or "")
    if m and m.group(1) in SLOTS:
        return f"{_label_base(m.group(1))} ({m.group(2)})"
    return _label_base(key)


def _label_base(key: str) -> str:
    spec = SLOTS.get(key)
    if spec:
        return spec["label"]
    return key.split(".", 1)[-1].replace("_", " ")


def is_slot(key: str) -> bool:
    if base_slot(key) != key:
        return base_slot(key) in SLOTS
    return _is_slot_base(key)


def _is_slot_base(key: str) -> bool:
    return key in SLOTS


def slot_schema() -> dict:
    """JSON schema for the constrained-decoding mapper: the model may only choose a slot id from
    the closed vocabulary (or 'none'); it can never mint a key."""
    return {
        "type": "object",
        "properties": {
            "slot": {"type": "string", "enum": list(SLOTS.keys()) + ["none"]},
            "value": {"type": "string"},
            "op": {"type": "string", "enum": ["set", "clear", "none"]},
        },
        "required": ["slot", "value", "op"],
    }


MAP_PROMPT = (
    "You extract at most ONE durable personal attribute the USER states about THEMSELVES "
    "(name, where they live, pet's name, favorite language/color/food, family names, job...). "
    "Return JSON {slot, value, op}. op='set' with the literal value when the user states or "
    "corrects a fact ('my dog is Rex', 'actually I live in Aveiro', 'call me Trailblazer'). "
    "op='clear' when the user retracts a value ('I no longer have a dog'). op='none' with "
    "slot='none' for questions, requests, greetings, opinions, weather, tasks, or anything "
    "not a durable fact about the user. Never invent a value; copy it from the message."
)


def map_to_slot(text: str, chat_json: Callable[[str, dict], Optional[dict]]) -> Optional[dict]:
    """Model-backed mapper for statements the regex path did not catch. `chat_json(prompt, schema)`
    must return a dict or None (provider-agnostic; the caller binds the role). Output is
    validated against the closed schema — an unknown slot or empty value is dropped."""
    try:
        out = chat_json(MAP_PROMPT + "\n\nUSER MESSAGE:\n" + text.strip(), slot_schema())
    except Exception:   # the mapper is advisory; a model failure must never break the turn
        return None
    if not isinstance(out, dict):
        return None
    slot, value, op = out.get("slot"), (out.get("value") or "").strip(), out.get("op")
    if op not in ("set", "clear") or slot not in SLOTS or not value or len(value) > 80:
        return None
    if not value_in_text(value, text):
        return None                      # GROUNDING (audit C1): a value the user never said is not a fact
    if is_reference_to_attribute(slot, value):
        return None                      # 95.30b: "my main project" is the attribute, not its value (X1 on 4ca1846)
    if slot.startswith("family.") and set(_tokens(text)) & _ATTRIBUTE_WORDS:
        return None                      # 77.5 (H): "my sister's favourite food is X" is the sister's attribute, never her name
    if not mentions_attribute(slot, text):
        return None                      # 74.3: the text must NAME the attribute — "For Echo I am writing in Kotlin" is
                                         # not a mother's name however grounded the value is (precision before recall)
    if relation_conflict(slot, text):
        return None                      # 69.4: the text names ANOTHER attribute ("cor") and none of this slot's
    if not relation_in_clause(slot, text, value):
        return None                      # 72.3: relation cue and value must share a clause
    if op == "set":
        return {"key": slot, "value": value}
    return {"key": slot, "clear_value": value}


def registry_mapper(registry, role: str = "nano"):
    """Bind `map_to_slot` to a provider role (default: the cheap nano). Constrained decoding via
    `format_schema`; the enum is the closed slot vocabulary. Returns a callable(text) -> det|None."""
    import json

    def chat_json(prompt: str, schema: dict):
        out = registry.chat_for_role(role, [{"role": "user", "content": prompt}], json_mode=True,
                                     temperature=0.0, format_schema=schema, think=False)   # 73.2: grammar, no reasoning
        content = out.get("content") if isinstance(out, dict) else out
        return json.loads(content) if isinstance(content, str) else content

    return lambda text: map_to_slot(text, chat_json)
