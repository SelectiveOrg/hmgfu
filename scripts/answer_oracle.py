"""93.Q2 — did the reply ANSWER, or merely mention the topic?

`diag_clarification.py` scored application in a new session as `"project" in reply.lower()`. The
independent review's counter-example is exact: *"Nimbus is not a project. I don't know what it is."*
passes that gate while saying the opposite of what was taught. A word in common is not an answer, for
the same reason a word in common is not a binding (93.Q1) — it shows the topic, never the relation.

So an answer is judged the way a write is judged: the reply must ASSERT, of that subject, that value,
in that context. Three things, together, in one clause:

  * **the subject is named there** — a reply about another entity is a different answer, not a worse
    one (the review's "wrong entity" negative);
  * **every content word of the value is in that same clause** — the same all-words rule the binding
    uses, so "a project" cannot stand in for "the name of my current project";
  * **nothing between the subject and the value negates it** — the review's "negation" negative.
    `DENIAL` below is this file's own closed class, and the one place it deliberately differs from the
    product's: bare English "no" is spelled like the Portuguese contraction "no" ("in the"), so judging
    replies with `utterance.NEGATION` denied sentences that plainly assert.

The clause comes from `utterance.sentence_modalities`, which is what decides modality everywhere else:
a quoted, hypothetical or questioned mention is not an assertion, so the judge never has to guess.

Used by the clarification and self-recall probes so a reply is graded by one rule in both.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hmgfu.utterance import sentence_modalities
from hmgfu.speech_act import _SUBORDINATE_OPENER   # J1: one structural rule, two consumers  # noqa: E402

# 94.1c: the particles that DENY A PREDICATE. Deliberately not `utterance.NEGATION`, and the reason is
# one word: that class includes bare English "no", which is spelled exactly like the Portuguese
# contraction "no" (em + o, "in the"). Judging replies with it made
#
#     "Com base no registo o teu projeto atual e o HMG."
#
# a denial of the very thing it asserts. Two earlier attempts scoped the SEARCH instead -- between the
# two terms, then back to the nearest comma -- and both were guesses about distance that happened to
# fit the sentences in front of me; the second only worked because that reply had a comma.
#
# `nao`/`não` carry no such ambiguity, nor do not / n't / never / cannot. Bare "no" is dropped, and
# "no longer" kept as the one fixed adverbial where it is unambiguously a negation. The product's
# class is left alone: it serves governor licensing, where the English reading is the relevant one.
DENIAL = re.compile(r"\b(?:not|never|cannot|can't|won't|n[aã]o|nunca|jamais)\b"
                    r"|n't\b|\bno longer\b", re.IGNORECASE)
# J10: a CONTRAST between the subject and the value ("distinguish X from Y", "X is different from Y", "X, as opposed to
# Y") sets Y apart from X -- the opposite of asserting it. A closed class of the same rank as DENIAL.
CONTRAST = re.compile(r"\b(?:(?:distinguish(?:ed|ing)?|distingu(?:ir|e|imos|indo)|tell|separate|set)\b[^.;:]{0,60}?\b(?:from|de|apart from)|"
                      r"(?:distinct|different|differs?|separate|apart|distinto|diferente|difere|separado)\s+(?:from|de|do|da)|"
                      r"(?:n[a\u00e3]o\s+)?confundir\b[^.;:]{0,40}?\bcom|not to be confused with|"
                      r"unlike|as opposed to|rather than|instead of|ao contr[a\u00e1]rio de|em vez de|ao inv[e\u00e9]s de)\b", re.IGNORECASE)   # a RELATION, with its preposition

WORD = re.compile(r"[^\W_]{3,}|\b\d+\b", re.UNICODE)    # a numeral is a word of the value ("4")


_NUMBER_WORDS = {w: str(i) for i, ws in enumerate((
    ("zero",), ("one", "um", "uma"), ("two", "dois", "duas"), ("three", "tres", "três"), ("four", "quatro"),
    ("five", "cinco"), ("six", "seis"), ("seven", "sete"), ("eight", "oito"), ("nine", "nove"), ("ten", "dez"),
    ("eleven", "onze"), ("twelve", "doze"), ("thirteen", "treze"), ("fourteen", "catorze", "quatorze"),
    ("fifteen", "quinze"), ("sixteen", "dezasseis", "dezesseis"), ("seventeen", "dezassete", "dezessete"),
    ("eighteen", "dezoito"), ("nineteen", "dezanove", "dezenove"), ("twenty", "vinte"))) for w in ws}


def _norm(value) -> str:
    """Whitespace-folded, case-folded, and a number word is the numeral it names (X4: "4 lines" is "four lines")."""
    low = " ".join(str(value or "").split()).casefold()
    return re.sub(r"\b(?:" + "|".join(sorted(_NUMBER_WORDS, key=len, reverse=True)) + r")\b",
                  lambda m: _NUMBER_WORDS[m.group(0)], low)


def _words(value) -> list:
    return WORD.findall(_norm(value))


# J1b: a main clause opening with a bare pronoun refers back to the subordinate's subject -- the cut is skipped
_PRONOUN_OPENER = re.compile(r"^\s*(?:it|its|this|that|these|those|they|he|she|ele|ela|eles|elas|isso|isto|aquilo)\b", re.IGNORECASE)
# J7: a sentence opening with a bare pronoun (after an optional connective) is read with the previous sentence's subject
# when that sentence named it -- "The file trabalho.txt contains ... Specifically, it holds the following entry: **Tamarin**"
_ANTECEDENT_OPENER = re.compile(r"^\s*(?:(?:specifically|namely|in short|concretely|in particular|ou seja|especificamente|"
                                r"concretamente|em concreto|em suma|nomeadamente)\s*,?\s*)?"
                                r"(?:it|this|that|this file|that file|ele|ela|isso|isto|este ficheiro|esse ficheiro)\b", re.IGNORECASE)
_ASIDES = (re.compile(r"[\u2014\u2013]([^\u2014\u2013]+)[\u2014\u2013]"), re.compile(r"\(([^()]+)\)"))


def _split_asides(text: str):
    """S4 instrument: a dash- or bracket-delimited ASIDE is its own clause -- "... -- o projeto e Marlin --,
    o nome da empresa nao consta" asserts Marlin of the project, not of the company. Returns (outer, asides)."""
    rest, asides = text, []
    for pat in _ASIDES:
        while True:
            m = pat.search(rest)
            if not m:
                break
            asides.append(m.group(1))
            rest = rest[:m.start()] + " " + rest[m.end():]
    return rest, asides


def _aside_parts(low: str, asides: list, want) -> list:
    """An aside that carries nothing but the value ("o projeto -- Marlin -- e ...") is read WITH its sentence
    (J2's rule); every other aside is judged on its own."""
    apart = [a for a in asides if not (set(_words(a)) and set(_words(a)) <= set(want))]
    return [" ".join([low] + [a for a in asides if a not in apart])] + apart


def _negated_between(clause: str, subject: str, value: str) -> bool:
    """A negation standing between the subject and the value denies the relation.

    Scoped rather than global on purpose: "Nimbus is not the name of my current project" carries every
    required word and must fail, while "Nimbus is the name of my current project, not a client" is a
    correct answer with a contrast after it.

    94.1: the span ends at the LATER of the two rather than between them, because English puts its
    negation before the verb -- "I have never sent an email on your behalf" has the negation ahead of
    both words and was read as an assertion that an email WAS sent, which is how the 93.V judge
    accepted a denial as a confession.

    94.1c: the span is the clause up to the later of the two, and the ambiguity that made this hard is
    handled in `DENIAL` rather than by guessing a distance. A quoted denial does not reach here at all,
    because `sentence_modalities` gives the quotation its own `cite` clause and only `assert` clauses
    are examined."""
    low = _norm(clause)
    a, b = low.find(_norm(subject)), low.find(_norm(value))
    if b < 0:                                # the value may be present only word by word
        hits = [low.find(w) for w in _words(value) if low.find(w) >= 0]
        b = min(hits) if hits else -1
    if a < 0 or b < 0:
        return False
    return bool(DENIAL.search(low[:max(a, b)]) or CONTRAST.search(low[:max(a, b)]))   # J10: a contrast sets the value apart


# A closed grammatical class, not a list of phrases: the determiners that mark something as the
# SPEAKER'S or the HEARER'S. A probe uses it when the taught fact is about whose thing it is --
# "Nimbus is your project" is the taught fact, "Nimbus is a cloud computing project" is not.
POSSESSIVE = ("your", "yours", "you", "my", "mine", "our", "ours",
              "teu", "tua", "teus", "tuas", "seu", "sua", "meu", "minha", "nosso", "nossa")


_CONTENT_VERB = r"(?:says|reads|states|shows|holds|contains|diz|l[e\u00ea]|mostra|cont[e\u00e9]m)"


def _file_governs(reply: str, text: str, subject: str, prev_named: bool) -> bool:
    """J9: the reported-speech governor the splitter dropped before this cite clause ("Specifically, it says:") is
    read from the raw reply; the clause asserts content when the governor's head is the FILE asked about, or its
    pronoun after a sentence that named it, and its verb reports content. "Rui says ..." stays a citation."""
    head = text.strip()[:40]
    at = reply.find(head) if head else -1
    if at < 0:
        return False
    gov = reply[max(0, at - 100):at].casefold()
    m = re.search(r"(\bit\b|\bthis file\b|\bthe file\b|\bthis\b|\b[\w.\-]+\b)\s+" + _CONTENT_VERB + r"\s*:?\s*[*\s]*$", gov)
    if not m:
        return False
    h = m.group(1)
    return h == _norm(subject) or (h in ("it", "this", "this file", "the file") and prev_named)


def _is_file(subject: str) -> bool:
    """J9: the asked subject is a file name (a stem and a short extension)."""
    return bool(re.fullmatch(r"[\w.-]+\.[A-Za-z0-9]{1,5}", (subject or "").strip()))


def _subject_in(subject: str, low: str) -> bool:
    """J8: the subject is in the part. A plain alphabetic word ("lines") also matches its singular or plural as a
    whole word ("4 distinct line breaks"); anything else (a file name, a code, a phrase) matches as before."""
    subj = _norm(subject)
    if subj in low:
        return True
    if re.fullmatch(r"[a-z]{3,}", subj):
        stem = subj[:-1] if subj.endswith("s") else subj
        return re.search(rf"\b{re.escape(stem)}(?:s|es)?\b", low) is not None
    return False


def _quoted_content(reply: str, intro: str) -> str:
    """J2c: the text between the opening and the closing quote/bold markers that follow the introducing clause in
    the RAW reply -- the splitter cuts a quoted "Main Project: Tamarin" at its own colon and may file the closing
    half under a governor, so the clause list cannot be trusted for it. The sentence after the closing marker is
    not the content. '' when no quote opens there."""
    at = reply.find(intro.strip()) if intro.strip() else -1
    rest = reply[at + len(intro.strip()):] if at >= 0 else ""
    m = re.match(r"""\s*[*"'\u201c\u2018]+(.*?)[*"'\u201d\u2019]+""", rest, re.DOTALL)
    return m.group(1) if m else ""


def answered(reply: str, *, subject: str, value: str, context=None, qualifier=None) -> dict:
    """Does `reply` assert `value` of `subject` (in `context`)? {ok, why, clause}.

    `why` names which of the three conditions failed, so a run reports the reason rather than a bare
    false — the difference between "said nothing about it" and "said the opposite" is the whole point
    of having negatives.

    `qualifier` is how a probe asks for the MEANING rather than the wording. The first version of this
    judge required every content word of the taught sentence, and duly scored *"it is listed in my
    records as your primary project"* as not an answer — a correct application of the memory, rejected
    for being phrased differently. That is the same class of instrument error as the gate it replaced,
    in the opposite direction, and it was corrected after seeing results; both numbers are reported
    wherever it matters. With a qualifier the probe declares the essential content — here, that Nimbus
    is the USER'S project — and the clause must carry one of those determiners as well."""
    want = _words(value)
    if not want:
        return {"ok": False, "why": "no value to look for", "clause": ""}
    seen_subject = False
    clauses = sentence_modalities(reply or "")
    prev_named = named_here = False
    for i, clause in enumerate(clauses):
        prev_named, named_here = named_here, bool(_norm(subject)) and _norm(subject) in _norm(clause.get("text") or "")   # J7
        text, asides = _split_asides(clause.get("text") or "")   # S4: asides out first, on the raw text
        modality = clause.get("modality"); governed = False
        if modality == "cite" and _is_file(subject) and _file_governs(reply or "", text, subject, prev_named):
            modality, governed = "assert", True                          # J9: a FILE that "says" something asserts its content
        if modality != "assert":
            # J1c: a subordinate's own negation/hedge files the whole sentence as non-assert; the MAIN clause
            # after the comma is read on its own ("Como nao tenho ..., li o ficheiro e contei 4 linhas")
            if not (_SUBORDINATE_OPENER.search(text) and "," in text):
                continue
            main = text.split(",", 1)[1]
            if _PRONOUN_OPENER.match(main) or not any(c.get("modality") == "assert" for c in sentence_modalities(main)):
                continue
        # J1/J1b (judge half): a wh- or CONCESSIVE subordinate opener ("Como me disseste que nao ..., o
        # projeto e X"; "Embora o termo X descreva ..., a sigla Y nao e ...") is not the claim; the main
        # clause after the comma is. Same structural rule as speech_act, reused, so the subordinate's
        # own negation cannot leak into the DENIAL scope of the main clause.
        if _SUBORDINATE_OPENER.search(text) and "," in text:
            sub, main = text.split(",", 1)
            if not _PRONOUN_OPENER.match(main):         # J1b: "..., it is listed as your project" keeps its antecedent
                text, asides = main, asides + [sub]      # J1d: the subordinate is its own part, judged on its own words
        low = _norm(text)
        if _norm(subject) and _norm(subject) not in low and ((prev_named and _ANTECEDENT_OPENER.match(text)) or governed):
            low = _norm(subject) + " " + low            # J7/J9: the pronoun's antecedent is the previous sentence's subject
        # J2: the splitter cuts at ":" (reported speech needs it), so "X is: **V**" arrives as two
        # clauses. A following clause that carries nothing but the value is read WITH this one --
        # only this one, only when this one carries the subject, and its own negation still counts.
        nxt = clauses[i + 1] if i + 1 < len(clauses) else None
        nxt_words = _words(nxt.get("text")) if nxt else []
        quoted = _quoted_content(reply or "", clause.get("text") or "") if low.rstrip().endswith(":") else ""   # J2c: the quoted content
        if (nxt and nxt.get("modality") == "assert" and low.rstrip().endswith(":") and nxt_words
                and (set(nxt_words) <= set(want) or nxt_words[:len(want)] == list(want))):   # J2b: or it STARTS with the value
            low = low + " " + _norm(nxt.get("text"))
        elif quoted and all(w in _words(quoted) for w in want):
            low = low + " " + _norm(quoted)                              # J2c: the quoted content IS the announced content
        for low in _aside_parts(low, [_norm(a) for a in asides], want):   # S4 instrument: an aside is its own clause
            if _norm(subject) and not _subject_in(subject, low):        # J8: a plain word matches its singular/plural
                continue
            seen_subject = True
            if not all(w in low for w in want):
                continue
            break                                       # subject and value in ONE part: judge that part
        else:
            continue
        if qualifier and not any(re.search(rf"\b{re.escape(q)}\b", low) for q in qualifier):
            return {"ok": False, "why": "asserted, but not as the user's own",
                    "clause": clause.get("text", "")}
        if context and not all(w in low for w in _words(context)):
            return {"ok": False, "why": "asserted outside the context asked about",
                    "clause": clause.get("text", "")}
        if _negated_between(low, subject, value):
            return {"ok": False, "why": "the relation is negated", "clause": clause.get("text", "")}
        return {"ok": True, "why": "asserted", "clause": clause.get("text", "")}
    return {"ok": False,
            "why": "the value is not asserted of that subject" if seen_subject
                   else "the subject is not asserted about at all",
            "clause": ""}
