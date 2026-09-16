"""Utterance analysis for the fact ledger — sentence MODALITIES (Phase 69.4 → Phase 72.1 / Fu-R object C).

Each sentence of a message gets one modality:
  assert      the user states something about themselves NOW → may become canon
  cite        someone else's words ("my friend said 'my name is Oscar'") → never the user's fact
  hypothesis  "if my favorite color were…", "suppose…", "hypothetically" → not a fact
  fiction     "for a character in my novel…" → not a fact; the marker CARRIES OVER to the next sentence
              ("For a fictional character. My name is Oscar.") until a reality cue ("anyway, my real name is…")
  past        dated/past-tense clauses ("in 2010 I lived in Lisbon", "back then…") → history, not current
  question    interrogative → never a fact
  intent      a PROPOSAL or an INTENTION of the speaker ("we should work on X", "I want to work on X", "vou trabalhar no X")
              → never a fact: wanting or proposing is not being. A speech-act idiom whose complement IS the assertion
              ("I want to tell you my name is X", "quero dizer, o meu nome é X") stays an assertion (90.L).
"since <year>" / "desde <ano>" is CURRENT with a `valid_from` (Codex 68/69 finding: it was dropped as past).
"""
from __future__ import annotations

import re
from typing import List, Optional

from .speech_act import is_interrogative

MODALITIES = ("assert", "cite", "hypothesis", "fiction", "past", "question", "intent")
# 90.M: a modality is a property of the CLAUSE. A contrastive coordinator starts a new claim, so "I want to work on X, but I
# currently work at Y" is an intention AND a fact, and "In 2019 I lived in Lisbon, but I live in Valencia now." is a past clause AND
# a current one. Without this the first clause's modality silences a valid fact sharing the sentence.
_SENT_PLAIN = re.compile(r"(?<=[.!?;:])(?<!\b[^\W\d_]\.)\s+|\n+")   # 95.14: "h." is an initial, not a boundary   # 91.V3: the split WITHOUT the contrastive alternative
_SENT = re.compile(r"(?<=[.!?;:])(?<!\b[^\W\d_]\.)\s+|\n+|\s*,?\s+(?=(?:but|mas|por[eé]m|contudo|no entanto|however|whereas|ao passo que)\s+"
                   r"(?:\S+\s+){2,}\S)", re.IGNORECASE)   # a CLAUSE follows, not a bare noun ("everything but coffee")
_QUOTE_D = re.compile(r"[\"“”«]([^\"“”»]{3,200})[\"“”»]")
_QUOTE_S = re.compile(r"(?<![\w])'([^']{3,200})'(?![\w])")          # single quotes, not apostrophes
_SPEECH_CUE = re.compile(r"\b(said|says|saying|told|tells|wrote|writes|quot(?:e|es|ed|ing)|dialogue|dialog|character|"
                         r"friend|colleague|disse|diz|dizia|escreveu|personagem|amig[oa]|colega)\b", re.IGNORECASE)
# 77.5: "if there's one dish I love, it's matapa" / "se há um prato que adoro, é matapa" is an ASSERTION idiom, not a hypothesis
_HYPO = re.compile(r"^\s*(?:(?:if|se)(?!\s+(?:there(?:'s| is)\s+(?:one|a single)|h[aá]\s+uma?)\b)|imagine|imagina|imaginemos|suponha|sup[oõ]e|suppose|supposing|hypothetically|what if|let'?s (?:say|pretend|imagine|assume)|pretend|digamos)\b|"
                   r"\b(hypothetical(?:ly)?|hipot[eé]tic[oa](?:mente)?|for (?:a|the|my) (?:dialogue|script|example)|"
                   r"para (?:um|o|a)(?: meu| minha)? (?:di[aá]logo|exemplo))\b", re.IGNORECASE)
_FICTION = re.compile(r"\b(for (?:a|the|my|this) (?:story|novel|book|character|fictional \w+|screenplay|play|game)|"
                      # 77.5 (B): the nominal frame — "in the novel I'm writing", "no romance que escrevo", "no meu livro"
                      r"(?:in|no|na|em)\s+(?:the|my|this|a|o|meu|minha|este|esta|um|uma)?\s*(?:novel|story|short story|screenplay|book|romance|hist[oó]ria|livro|conto|pe[cç]a)\b|"
                      r"fictional|fiction|role-?play|personagem|para (?:um|o|a|uma|este|esta)(?: meu| minha)? (?:hist[oó]ria|romance|livro|"
                      r"personagem|pe[cç]a|jogo)|de fic[cç][aã]o)\b", re.IGNORECASE)
_PAST = re.compile(r"\b(?:in|em|no ano de)\s+(?:19|20)\d{2}\b|"
                   r"\b(back then|at the time|at that time|used to|lived in|worked at|was my|were my|"
                   r"na altura|naquela altura|antigamente|dantes|outrora|noutros tempos|h[aá] uns anos|costumava|morava|morei|trabalhava|era o meu|era a minha)\b",
                   re.IGNORECASE)
_SINCE = re.compile(r"\b(?:since|desde|a partir de)\s+((?:19|20)\d{2})\b", re.IGNORECASE)
# 77.5 (E): "used to be X, now it's Y" — the sentence asserts the CURRENT value (the detector's transition form reads both)
_TRANSITION = re.compile(r"\b(?:used to be|was|were|era|eram|costumava ser|foi)\b[^.!?;]{0,60}?\b(?:but\s+|mas\s+)?"
                         r"(?:now|nowadays|these days|today|currently|agora|hoje|a[ct]ualmente)\b", re.IGNORECASE)
_SAYS_COLON = re.compile(r"\b(says?|said|tells?|told|diz|disse|dizem|afirma)\s*:\s*(.+)$", re.IGNORECASE)
_SAYS_INTRO = re.compile(r"\b(says?|said|tells?|told|diz|disse|dizem|afirma)\s*:\s*$", re.IGNORECASE)   # splitter cut after ':'
# reported speech with a complementiser — "my colleague says that his…", "o meu colega diz que…" (never first person)
_REPORTED = re.compile(r"^(?!\s*(?:i|eu)\b)(?!.*\b(?:i|eu)\s+(?:told|said|disse|digo)\b).*\b(?:(says?|said|tells?|told|diz|disse|dizem|afirmam?|contou|conta)"
                       r"\s+(?:me|us|nos|-me)?\s*(?:that|que)\b"
                       r"|(swears?|swore|claims?|insists?|assures?|jura|juram|garante|garantem|assegura|alega|alegam|sustenta)"   # 95.70: the
                       r"\s+(?:me|us|nos|-me)?\s*(?:(?:that|que)\b|(?=[A-Z][\w-]*\s+\w)))"                                       # newer governors
                       r"|^\s*(?:segundo|according to|de acordo com|conforme|per)\s+(?:o |a |os |as |the |my |our |o meu |a minha )?[\w'-]+(?:\s+[\w'-]+){0,2}\s*,", re.IGNORECASE)   # 95.70: the citation frame
_REAL = re.compile(r"\b(my real name|real name|actually|anyway|in real life|in reality|na verdade|na realidade|na vida real|a s[eé]rio|realmente|"
                   r"o meu nome verdadeiro|nome verdadeiro)\b", re.IGNORECASE)
# only DISCOURSE markers are stripped from an assert sentence — "my real name is X" carries the fact itself
_REAL_MARKER = re.compile(r"^\s*(?:anyway|actually|in real life|in reality|na verdade|na realidade|na vida real|a s[eé]rio|realmente)\b[\s,:;-]*", re.IGNORECASE)
# 91.S2: English puts the same discourse marker BETWEEN the subject and the verb — "I actually live in X" is the
# correction "Actually, I live in X", and it was writing nothing while the fronted form wrote (audit P2). Anchored to
# the subject pronoun so it can only remove a marker, never a word that carries the fact ("my real name is X").
_REAL_MARKER_MID = re.compile(r"^(\s*(?:i|we|eu|n[oó]s)\s+)(?:actually|really|in fact|truly|na verdade|realmente)\s+", re.IGNORECASE)
# 83.3: preference IDIOMS whose form is conditional or imperative but whose meaning is a present assertion (reserved set v5)
# 90.L: a proposal or an intention, anchored to the SPEAKER (or clause-initial in PT, where the subject is dropped). The guard
# excludes the speech-act idioms whose complement IS the assertion — "I want to tell you my name is X", "quero dizer, o meu nome é X".
_SPEECH_ACT = r"(?!\s+(?:say|tell|mention|add|note|repeat|dizer|contar|referir|acrescentar|repetir))"
_INTENT = re.compile(
    r"(?:\b(?:i|we|eu|n[oó]s)\b(?:['’](?:m|re))?\s+(?:\w+\s+){0,2}?"
    r"(?:should|ought\s+to|want\s+to|wanna|would\s+like\s+to|plan\s+to|planning\s+to|intend\s+to|going\s+to|gonna|could|"
    r"quero|queria|gostava\s+de|gostaria\s+de|pretendo|pretendemos|planeio|tenciono|vou|vamos|dev[ií]amos|devemos|devia|devias)\b"
    + _SPEECH_ACT + r")"
    r"|(?:^\s*(?:let'?s|let\s+us|vamos|vou|quero|queria|gostava\s+de|gostaria\s+de|pretendo|planeio|tenciono|dev[ií]amos|"
    r"devemos|devia)\b" + _SPEECH_ACT + r")",
    re.IGNORECASE)
_PREF_IDIOM = re.compile(r"\b(?:if i had to (?:pick|choose)\b|se tivesse de escolher\b|nothing beats\b|n[aã]o h[aá] \w+ que bata\b|"
                         r"give me\s+.+?\s+over any other\b|d[aá]-me\s+.+?\s+em vez de\b|i could eat\s+.+?\s+every\b|comia\s+.+?\s+todos os dias\b)", re.IGNORECASE)
_IDIOM_NOT_FICTION = re.compile(r"\bin my book\s*[.!?]?\s*$", re.IGNORECASE)          # "… in my book" = in my opinion
# 83.3: "forget what I said:" / "esquece o que disse:" introduces the user's OWN words, not a citation
_SELF_SAID = re.compile(r"\b(?:what i|o que(?: eu)?|esquece o que|forget what i|ignore what i|ignora o que)\s+(?:said|disse|told you|te disse)\s*:?\s*$", re.IGNORECASE)
_PAST_CUE_Q = re.compile(r"\b(before|previously|used to|earlier|formerly|in (?:19|20)\d{2}|last year|antes|antigamente|"
                         r"anteriormente|em (?:19|20)\d{2}|no ano passado|dantes)\b", re.IGNORECASE)


def _unreal(s: str, carry: Optional[str]) -> bool:
    """91.S1 — the sentence is NOT the user's own claim about the world: fiction, a supposition, or reported speech.

    Audit finding (reports/codex_execution_audit_20260909, P1): `_SINCE` decided the modality before fiction and
    hypothesis were ever tested, so "In my novel, I have lived in Lichinga since 2022." and "Suppose I have lived in
    Lichinga since 2022." both wrote Lichinga into the real ledger. A date QUALIFIES a claim; it never creates one.
    This reuses the cues that already exist rather than adding an exception for the word "novel".
    """
    if carry in ("fiction", "hypothesis") and not _REAL.search(s):
        return True                      # 91.V3: the frame was opened in an EARLIER sentence and not revoked
    return bool((_FICTION.search(s) and not _IDIOM_NOT_FICTION.search(s)) or _HYPO.search(s) or _REPORTED.search(s)
                or carry == "cite" or _SAYS_COLON.search(s)
                or (_SPEECH_CUE.search(s) and (_QUOTE_D.search(s) or _QUOTE_S.search(s))))


# 91.S2 — "that's wrong; it's actually Lichinga": a correction that names no attribute. Reading the shape is an
# utterance question; WHICH slot it refers to is the store's, from its own history. The frame is deliberately tight —
# only punctuation and a correction adverb may sit between the cue and the replacement — because a loose gap let it
# skip over the attribute and capture a NEGATION as a value ("Isso está errado, o meu nome não é esse." wrote
# `identity.name = "não é esse"`, caught by test_v66 before this shipped).
_BARE_CORRECTION = re.compile(
    r"^\s*(?:that(?:'s|’s| is)\s+(?:wrong|incorrect|not\s+right)|that\s+is\s+incorrect|no|n[ãa]o|"
    r"isso\s+est[áa]\s+errado|est[áa]\s+errado|errado)\b[,;:.\s]*"
    r"(?:(?:na\s+verdade|actually|in\s+fact|realmente)\b[,;:\s]*)?"
    r"(?:it(?:'s|’s| is)|[ée]|s[ãa]o)\s+(?:(?:actually|na\s+verdade|realmente|in\s+fact)\s+)?"
    r"(?:(?:o|a|os|as|the)\s+)?([\w'À-ÿ-]+(?:\s+[\w'À-ÿ-]+){0,3})\s*[.!?]?\s*$", re.IGNORECASE)
# a possessor makes the claim someone else's; the apostrophe must belong to a NOUN ("it's" is a contraction)
_ANY_POSSESSOR = re.compile(r"\b(?!(?:it|that|he|she|there|what|who|here|one|let)\b)[\w À-ÿ-]*?[\wÀ-ÿ]+(?:'s|’s)\s"
                            r"|\bd[oa]s?\s+(?:meu|minha|nosso|nossa)\b", re.IGNORECASE)
_ANY_NEGATION = re.compile(r"\b(?:not|n[ãa]o|never|nunca|isn'?t|aren'?t|n't)\b", re.IGNORECASE)


def bare_correction(text: str) -> Optional[str]:
    """The replacement value of a correction that names no attribute, no possessor and no negation — else None."""
    s = (text or "").strip()
    m = _BARE_CORRECTION.match(s)
    if not m or _ANY_POSSESSOR.search(s):
        return None
    value = m.group(1).strip(" .,;:")
    if _ANY_NEGATION.search(value) or _ANY_NEGATION.search(s[:m.start(1)].replace(s.split()[0], "", 1)):
        return None                      # "não é esse" is a denial, not a replacement
    return value or None


# ---- 91.Z step 1: PROPOSITIONAL SCOPE -------------------------------------------------------------
# A modality was assigned per SENTENCE, so "I deny that my dog is called Green." was classified assert
# and reached the ledger as a claim. A denial, a doubt or a report is a GOVERNING CLAUSE, and the
# proposition it governs must carry the status the governor licenses -- not the sentence's.
#
# The verb class below is what distinguishes a COMPLEMENT clause from a RELATIVE clause: without it
# "the car that I bought is blue" would be torn in half. It is the definition of the construction, not
# a list of sentences from a report -- the decision itself is made by the predicates that already
# exist (negation, hedge, person) plus one closed class of verbs whose complement is not endorsed.
_CTV = (r"say|says|said|saying|tell|tells|telling|told|know|knows|knew|think|thinks|thought|"
        r"believe|believes|believed|confirm|confirms|confirmed|mention|mentions|mentioned|"
        r"claim|claims|claimed|hear|hears|heard|read|reads|write|writes|wrote|admit|admits|admitted|"
        r"insist|insists|insisted|suppose|supposes|supposed|remember|remembers|remembered|"
        r"forget|forgets|forgot|note|notes|noted|add|adds|added|repeat|repeats|repeated|"
        r"clarify|clarifies|clarified|deny|denies|denied|doubt|doubts|doubted|dispute|disputes|disputed|"
        # the epistemic verbs must be GOVERNORS too, or _EPISTEMIC never gets a chance to judge them
        r"assume|assumes|assumed|suspect|suspects|suspected|imagine|imagines|imagined|reckon|reckons|"
        r"guess|guesses|guessed|challenge|challenges|challenged|accept|accepts|accepted|"
        r"presumo|presume|presumiu|presumir|suponho|imagino|desconfio|aceito|aceita|aceitar|"
        r"refuse|refuses|refused|contest|contests|contested|reject|rejects|rejected|pretend|pretends|pretended|"
        r"digo|diz|disse|dizer|conto|conta|contou|sei|sabe|sabia|penso|pensa|pensou|acho|acha|achou|"
        r"acredito|acredita|acreditou|confirmo|confirma|confirmou|refiro|refere|referiu|"
        r"afirmo|afirma|afirmou|ouvi|ouviu|li|leu|escrevi|escreveu|admito|admite|admitiu|"
        r"insisto|insiste|insistiu|lembro|lembra|lembrou|esqueci|esqueceu|acrescento|acrescenta|"
        r"nego|nega|negou|negar|duvido|duvida|duvidou|duvidar|contesto|contesta|contestar|"
        r"recuso|recusa|recusar|rejeito|rejeita|rejeitar|esclareco|esclarece|"
        # third person plural of the same verbs -- a paradigm, not a sample
        r"dizem|disseram|contam|contaram|sabem|sabiam|pensam|pensaram|acham|acharam|"
        r"acreditam|acreditaram|confirmam|confirmaram|referem|referiram|afirmam|afirmaram|"
        r"ouviram|leram|escreveram|admitem|admitiram|insistem|insistiram|lembram|lembraram|"
        r"negam|negaram|duvidam|duvidaram|contestam|contestaram|recusam|recusaram|"
        r"rejeitam|rejeitaram|informaram|avisaram|mencionaram")
_GOVERNED = re.compile(r"^(?P<gov>(?:(?!\b(?:that|que)\b).){0,90}?\b(?:" + _CTV + r")\b"
                       r"(?:-(?:me|nos|lhe|lhes|te|se))?(?:\s+\S+){0,6}?\s+(?:that|que)\s+)"
                       r"(?P<prop>\S.*)$", re.IGNORECASE)
# a COPULAR governor predicates truth or certainty of the complement with an ADJECTIVE, so the
# complement-taking verb class cannot see it: "It is not true that P", "I am not sure that P"
_COPULA_GOV = re.compile(r"^(?P<gov>[^,]{0,60}?\b(?:true|false|untrue|certain|sure|clear|obvious|likely|verdade|falso|certo|claro|[oó]bvio|certeza)\b[^,]{0,24}?\s+(?:that|que|de que)\s+)(?P<prop>\S.*)$",
                         re.IGNORECASE)
# "the claim that P", "the idea that P": a NOUN takes the complement, and the verb governing that
# noun decides whether P is endorsed -- challenging a claim denies it, accepting one asserts it
_NOUN_COMPLEMENT = re.compile(r"^(?P<gov>[^,]{0,60}?\b(?:claim|idea|notion|suggestion|allegation|story|rumour|rumor|idei[ao]|alega[cç][aã]o|sugest[aã]o|boato)s?\s+(?:that|que)\s+)(?P<prop>\S.*)$", re.IGNORECASE)
_BARE_NEG_GOV = re.compile(r"^(?P<gov>\s*(?:not|n[aã]o)\s+(?:that|que)\s+)(?P<prop>\S.*)$", re.IGNORECASE)
# verbs whose complement the speaker explicitly does NOT endorse
_ATTITUDE_NEG = re.compile(r"\b(?:deny|denies|denied|doubt|doubts|doubted|dispute|disputes|disputed|refuse|refuses|refused|"
                           r"challenge|challenges|challenged|"
                           r"contest|contests|contested|reject|rejects|rejected|pretend|pretends|pretended|"
                           r"nego|nega|negou|negar|duvido|duvida|duvidou|duvidar|contesto|contesta|contestar|"
                           r"recuso|recusa|recusar|rejeito|rejeita|rejeitar)\b", re.IGNORECASE)
# falsity denies the complement without using a negation particle
_UNTRUE = re.compile(r"\b(?:false|untrue|incorrect|wrong|falso|mentira|incorrect[oa])\b", re.IGNORECASE)
_NEG_GOV = re.compile(r"\b(?:not|never|no|cannot|n[aã]o|nunca|jamais)\b|n't\b", re.IGNORECASE)
NEGATION = _NEG_GOV          # 93.Q2: the one closed class of negation particles, named
# so a judge of REPLIES reuses it instead of inventing a second, divergent list.
_HEDGE_GOV = re.compile(r"\b(?:maybe|perhaps|probably|possibly|not sure|unsure|(?:might|may|could|would)(?!\s+(?:you|voc[eê]|tu)\b)|"
                        r"talvez|provavelmente|se calhar|poderia|podia|deveria|"
                        r"acho que|penso que|julgo que)\b", re.IGNORECASE)
_SELF_GOV = re.compile(r"^\s*(?:i|we|eu|n[oó]s)\b|^\s*(?:you|voc[eê]|tu)\s+(?:should|must|need|deves?|deve|precisa)"
                       r"|^\s*(?:it\s+is|it.s|this\s+is|isso\s+[eé]|[eé]\s+verdade)\b",   # impersonal copula: the user asserts it
                       re.IGNORECASE)
# an imperative carries no subject, only politeness or modal framing, before its verb
_IMPERATIVE_FRAME = re.compile(r"\b(?:please|kindly|just|could|can|would|will|do|you|por favor|se faz favor|podes|pode|podias|poderias|faz favor)\b|[^\w\s]", re.IGNORECASE)
# a second predicate inside the governor whose subject is NOT the user: "I say SHE CLAIMED that ..."
_OTHER_VOICE = re.compile(r"\b(?:he|she|they|it|ele|ela|eles|elas)\s+(?:\w+\s+){0,2}?(?:" + _CTV + r")\b"
                          r"|(?<=\s)[A-Z][a-z]+\s+(?:\w+\s+){0,2}?(?:" + _CTV + r")\b")
# the PASSIVE makes the user the recipient of a report, never its source
_PASSIVE_REPORT = re.compile(r"\b(?:was|were|been|being|am|is|are|fui|foi|fomos|foram)\s+(?:\w+\s+){0,2}?(?:told|informed|advised|assured|warned|reminded|dito|informad[oa]|avisad[oa])\b"
                             r"|\b(?:disseram|contaram|informaram|avisaram)(?:-me|-nos)?\b", re.IGNORECASE)
# the speaker marks the complement as INFERRED rather than known
_EPISTEMIC = re.compile(r"\b(?:suppose|supposes|supposed|guess|guesses|guessed|assume|assumes|assumed|"
                        r"suspect|suspects|suspected|imagine|imagines|imagined|reckon|reckons|reckoned|"
                        r"presumo|presume|presumiu|presumir|suponho|supoe|supor|imagino|imagina|imaginar|calculo|desconfio|desconfia)\b", re.IGNORECASE)
# the user RECEIVED the proposition, so its source is external -- the passive of the same idea
_RECEPTION = re.compile(r"\b(?:hear|hears|heard|read|reads|learn|learns|learned|learnt|see|sees|saw|"
                        r"ouvi|ouve|ouviu|li|le|leu|soube|sabia por|vi|viu)\b", re.IGNORECASE)
# an intention the speaker did NOT carry out -- distinguished from 90.L by TENSE, so a present
# speech act ("I want to tell you that my name is X") remains an assertion
_PAST_INTENT = re.compile(r"\b(?:was|were|had|have|has)\s+(?:just\s+)?(?:going|about)\s+to\b|"
                          r"\bia\s+\w+|\bestava\s+(?:para|prestes\s+a)\b", re.IGNORECASE)
# a connector opens a clause without governing it (the distinction 91.X2 drew for the subject)
_LEAD_CONNECTOR = re.compile(r"^(?:(?:but|and|so|or|then|also|however|though|yet|besides|anyway|actually|well|"
                             r"mas|e|ou|ent[aã]o|tamb[eé]m|por[eé]m|contudo|no entanto|ali[aá]s|enfim|bem)[,\s]+)+", re.IGNORECASE)


def _self_voice(gov: str) -> bool:
    """Whether the governing clause is spoken in the USER's voice.

    Anchoring on the first character read "Since 2019 I have said that ..." as somebody else's
    report, so the subject is looked for in the material BEFORE the governing verb, which a temporal
    adjunct does not displace. An IMPERATIVE has no subject at all ("Remember that ...", "Please
    remember that ...", "Could you remember that ..."): it is addressed by the user to the assistant,
    so its complement is the user's own claim -- the sealed write sets caught this when four such
    sentences stopped being written."""
    verb = re.search(r"\b(?:" + _CTV + r")\b", gov, re.IGNORECASE)
    head = gov[:verb.start()] if verb else gov
    if re.search(r"\b(?:i|we|eu|n[oó]s)\b", head, re.IGNORECASE) or _SELF_GOV.match(gov):
        return True
    return not _IMPERATIVE_FRAME.sub(" ", head).strip()      # nothing but politeness => imperative


def _licensed(gov: str) -> str:
    """The modality a governing clause licenses FOR ITS COMPLEMENT.

    The default is `assert`: a plain first-person speech act asserts what follows, which is why
    "I know that X", "I can confirm that X" and "I am telling you that X" are the user's own claims.
    A governor disqualifies its complement when it DENIES or DOUBTS it, when it is NEGATED or HEDGED,
    or when the voice is not the user's -- an assertion inside a citation is never the user's own."""
    gov = _LEAD_CONNECTOR.sub("", gov or "").lstrip()   # 91.Z: judge the governor, not the connector
    if (_ATTITUDE_NEG.search(gov) or _NEG_GOV.search(gov) or _HEDGE_GOV.search(gov)
            or _EPISTEMIC.search(gov) or _UNTRUE.search(gov)):
        return "hypothesis"
    if _PAST_INTENT.search(gov):
        return "intent"                  # an intention is not a fact (90.L, by tense)
    if _PASSIVE_REPORT.search(gov) or _RECEPTION.search(gov) or _OTHER_VOICE.search(gov) or not _self_voice(gov):
        return "cite"
    return "assert"


# 91.AA2: a clause boundary -- where an independent proposition can begin. Used ONLY to find where the
# GOVERNOR starts, never to split a value or a complement, so coordination inside a value is untouched.
_CLAUSE_BREAK = re.compile(r"[,;:]\s*(?:and|but|so|e|mas|ent[aã]o)?\s*|\s+(?:and|but|e|mas)\s+", re.IGNORECASE)
# the conjunction that joins a prefix to the governor is part of the JOIN, not of the proposition
_TRAILING_JOIN = re.compile(r"[\s,;:]*(?:\b(?:and|but|so|e|mas|ent[aã]o)\b)?[\s,;:]*$", re.IGNORECASE)
# 91.AA2: a boundary that starts a NEW first-person claim, so a proposition does not swallow the
# independent clause that FOLLOWS it. Same shape as fact_detect._CLAUSE_SPLIT, which production
# already relies on: it fires only before a new claim, never inside a coordinated value.
_TAIL_CLAIM = re.compile(r"\s*[,;]?\s+(?:and|but|e|mas)\s+(?=(?:my|i\b|eu\b|o meu|a minha|n[oó]s)\b)",
                         re.IGNORECASE)


def _governor_start(gov: str) -> int:
    """Index where the governing clause itself begins: the LAST clause boundary before its verb."""
    verb = None
    for vm in re.finditer(r"\b(?:" + _CTV + r")\b", gov, re.IGNORECASE):
        verb = vm
    anchor = verb.start() if verb else len(gov)
    cut = 0
    for bm in _CLAUSE_BREAK.finditer(gov):
        if bm.end() <= anchor:
            cut = bm.end()
    return cut


def governed_split(text: str):
    """(prefixes, proposition, modality). `prefixes` are the independent propositions standing before
    the governors; each is classified in its own right by the caller, so a fact stated alongside a
    denial is neither lost nor tainted by it."""
    prop, worst, depth, pres = (text or "").strip(), "assert", 0, []
    while depth < 4:
        m = _GOVERNED.match(prop) or _NOUN_COMPLEMENT.match(prop) or _COPULA_GOV.match(prop) or _BARE_NEG_GOV.match(prop)
        if not m:
            break
        gov = m.group("gov")
        cut = _governor_start(gov)
        if cut:
            pres.append(_TRAILING_JOIN.sub("", gov[:cut]).strip())
        lic = _licensed(gov[cut:])
        if worst == "assert":
            worst = lic
        prop, depth = m.group("prop").strip(), depth + 1
    tail = _TAIL_CLAIM.search(prop)
    if tail and worst != "assert":       # the governor scopes only up to the next independent claim
        pres.append(_TRAILING_JOIN.sub("", prop[tail.end():]).strip())
        prop = prop[:tail.start()].strip()
    if worst == "assert" and _HEDGE_GOV.match(prop):
        worst = "hypothesis"
    return pres, prop, worst


def governed_proposition(text: str):
    """(proposition, modality) after peeling every governing clause. Kept for existing callers."""
    _, prop, modality = governed_split(text)
    return prop, modality

def sentence_modalities(text: str) -> List[dict]:
    """[{text, modality, valid_from}] per sentence, with fiction/hypothesis carry-over to the next sentence."""
    out: List[dict] = []
    carry: Optional[str] = None
    # 91.V3: a TRANSITION frame ("used to be X but now Y") is ONE claim about ONE attribute and it spans the
    # coordinator — splitting there destroyed it (caught by the DEV modality diagnostic, m28, not by a unit test).
    splitter = _SENT_PLAIN if _TRANSITION.search(text or "") else _SENT
    for sent in splitter.split((text or "").strip()):
        s = sent.strip()
        if not s:
            continue
        valid_from = None
        governed = False     # 91.Z: a status taken from a GOVERNOR is about THIS proposition only
        if _PREF_IDIOM.search(s):                                    # 83.3: form ≠ meaning — a preference stated as an idiom
            m = "assert"
        elif is_interrogative(s):
            m = "question"
        elif _INTENT.search(s):                                      # 90.L: a proposal or an intention is never a fact
            m = "intent"
        elif _SINCE.search(s) and not _unreal(s, carry):              # 91.S1: a date qualifies a claim, it never makes one
            m, valid_from = "assert", f"{_SINCE.search(s).group(1)}-01-01"
        elif _TRANSITION.search(s):                                  # 77.5: "used to be X, now Y" is current
            m = "assert"
        elif _PAST.search(s):
            m = "past"
        elif _SAYS_INTRO.search(s) and not _SELF_SAID.search(s):     # "the hero says:" — the NEXT sentence is the citation,
            carry = "cite"                                           # whatever frame introduces it ("In the book, …" — 77.5)
            continue
        elif _SELF_SAID.search(s):                                   # 83.3: "esquece o que disse:" — the user's own correction follows
            continue
        elif _FICTION.search(s) and not _IDIOM_NOT_FICTION.search(s):
            m = "fiction"
        elif _HYPO.search(s):
            m = "hypothesis"
        elif carry == "cite":
            m = "cite"
        elif _SAYS_COLON.search(s):                                  # "the hero says: my name is Kael" — reported speech
            out.append({"text": _SAYS_COLON.search(s).group(2).strip(), "modality": "cite", "valid_from": None})
            s = s[:_SAYS_COLON.search(s).start()].strip()
            m = "assert"
        elif _REPORTED.search(s):                                    # "o meu colega diz que a comida favorita dele é frango"
            m = "cite"
        elif _SPEECH_CUE.search(s) and (_QUOTE_D.search(s) or _QUOTE_S.search(s)):
            for q in _QUOTE_D.findall(s) + _QUOTE_S.findall(s):
                out.append({"text": q.strip(), "modality": "cite", "valid_from": None})
            s = re.sub(r"\s{2,}", " ", _QUOTE_S.sub(" ", _QUOTE_D.sub(" ", s))).strip()
            m = "assert"
        elif carry in ("fiction", "hypothesis") and not _REAL.search(s):
            m = carry
        else:
            m = "assert"
        if m == "assert":
            pres, prop, lic = governed_split(s)          # 91.Z/91.AA2: the ledger sees each PROPOSITION
            if prop != s or lic != "assert":             # the status its governor chain licenses
                s, m, governed = prop, lic, True
                if _SINCE.search(s):                     # TIME is re-read on the proposition itself
                    valid_from = f"{_SINCE.search(s).group(1)}-01-01"
            for pre in pres:                        # 91.AA2: an independent proposition before the
                out.extend(sentence_modalities(pre))  # governor keeps its own status, not the governor's
        if m == "assert":
            s = _REAL_MARKER_MID.sub(r"\1", _REAL_MARKER.sub("", s)).strip() or s
        carry = m if (m in ("fiction", "hypothesis") and not governed) else None   # 91.Z: a denial never carries
        if s:
            out.append({"text": s, "modality": m, "valid_from": valid_from})
    return out


def declarative_clauses(text: str) -> List[dict]:
    """The sentences the ledger may learn from (modality assert), with their `valid_from`. 95.44: an
    action request ("Save ... into a file called X") asserts nothing about the user and is left out."""
    from .speech_act import is_action_request
    return [c for c in sentence_modalities(text) if c["modality"] == "assert" and not is_action_request(c["text"])]


def declarative_text(text: str) -> str:
    """Compatibility view: the assert sentences joined."""
    return " ".join(c["text"] for c in declarative_clauses(text))


def valid_from_of(text: str) -> Optional[str]:
    return next((c["valid_from"] for c in declarative_clauses(text) if c.get("valid_from")), None)


def past_cue(text: str) -> bool:
    """A question about the PAST ('where did I live before?') — history lines belong in the context (72.3)."""
    return bool(_PAST_CUE_Q.search(text or ""))
