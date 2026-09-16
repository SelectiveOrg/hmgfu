"""Speech-act gate (Phase 62) — a question or a request is never a fact.

Autopsy finding: both stores held user QUESTIONS as facts/persons ("what is my name?" type=person,
"tell me the weather" type=fact) and then recalled them as evidence. The nano typer mislabels
them and 93% of points were typed by the regex fallback, so the gate must be deterministic and
sit at the write choke points (ingest type, canonical-fact apply, identity layering).

PT + EN. Deliberately narrow: "remember this: my cat is Nimbus" and "actually my favorite is
java" are statements and must pass.
"""

from __future__ import annotations

import re

_WH = (r"what|whats|what's|which|who|whom|whose|where|when|why|how|"
       r"qual|quais|quem|onde|quando|porque|por que|como|o que|oque")
_AUX = (r"do|does|did|is|are|am|was|were|can|could|would|will|should|shall|have|has|had|"
        r"sabes|sabe|lembras|lembra|podes|pode|tens|tem")
_REQUEST = (r"tell me|remind me|show me|give me|list|explain|describe|"
            r"diz[- ]me|lembra[- ]me|mostra[- ]me|conta[- ]me|fala[- ]me|"
            r"do you (?:know|remember|recall)|can you (?:tell|remind|say)|"
            r"lembras[- ]te|sabes|please (?:tell|check|search|find|look)")

_Q_START = re.compile(rf"^\s*(?:please\s+|hey\s+|ok\s+|so\s+|quick check[:,]?\s*|hi[,!]?\s+)*"
                      rf"(?:(?:{_WH})\b|(?:{_AUX})\s+(?:i|you|my|your|we|it|there|he|she|they|o|a|eu|tu)\b|"
                      rf"(?:{_REQUEST})\b)", re.IGNORECASE)
# J1 (95, judge-first): a wh-word opens a SUBORDINATE, not a question, when its clause ends at a comma and
# a new clause follows that opens with its own determiner / pronoun and no "?" ends the text. "Como me
# disseste ontem, o teu projeto e X." / "When I started, my project was Y." Structural, not lexical: the
# same wh-words, a clause boundary and a clause opener. "Como estas" (no comma-clause) stays a question.
# J1b: a CONCESSIVE opener is the same class of subordinator ("Embora o termo X descreva ..., a sigla Y nao e ...")
_CONCESSIVE = (r"although|even though|though|while|whereas|embora|apesar de|ainda que|mesmo que|se bem que|conquanto|"
               r"since|because|given that|porque|como|j[a\u00e1] que|visto que|dado que|uma vez que")   # J1c: causal subordinators too
_SUBORDINATE_OPENER = re.compile(
    rf"^\s*(?:{_WH})\b[^,?]{{2,240}},\s*(?:o|a|os|as|the|my|your|our|their|his|her|its|this|that|these|"
    rf"those|it|he|she|we|they|i|you|meu|minha|teu|tua|seu|sua|nosso|nossa|este|esta|esse|essa|ele|ela|"
    rf"eles|elas|eu|tu|nos|voc[eê])\b"
    rf"|^\s*(?:{_CONCESSIVE})\b[^,?]{{2,240}},\s*\S", re.IGNORECASE)     # J1b: a concessive is never a question
# statements that merely BEGIN with a request verb but then declare a fact: "remember this: my..."
_DECLARE_AFTER = re.compile(r"^\s*(?:(?:could|can|would|will|please|podes|pode|poderias)\s+(?:you\s+)?(?:please\s+)?)?"
                            r"(?:remember|note|save|store|keep in mind|lembra-te|lembra|anota|guarda|memoriza)\b[^:]{0,40}[:,]?\s*"
                            r"(?:that\s+|que\s+)?(?:my|i |i'm|i am|meu|minha|eu |o meu|a minha)", re.IGNORECASE)


def is_interrogative(text: str) -> bool:
    """True for questions and information requests (never durable facts). False for statements,
    corrections, directives and 'remember that my X is Y' declarations."""
    t = (text or "").strip()
    if not t:
        return False
    if _DECLARE_AFTER.search(t):
        return False
    if t.endswith("?") and not re.search(r"https?://\S*\?$", t):   # a URL's own '?' is not a question
        return True
    first_clause = re.split(r"[.!\n]", t, maxsplit=1)[0]
    if _SUBORDINATE_OPENER.search(first_clause):
        return False        # J1: the wh-word opens a subordinate; the main clause after the comma declares
    return bool(_Q_START.search(first_clause))


_SELF = re.compile(r"\b(my|i'm|i am|mine|myself|meu|minha|meus|minhas|eu|mim|comigo|"
                   r"about me|know me|remember me|of me|from me|sobre mim|de mim)\b", re.IGNORECASE)


_FIRST_PERSON = re.compile(r"\b(i|i'm|i'll|me|my|eu|meu|minha)\b", re.IGNORECASE)
_QUESTION_SENTENCE = re.compile(r"[^.!?\n]*\?")


def last_question(text: str):
    """The last question a reply asks, without the prose around it, or None."""
    found = _QUESTION_SENTENCE.findall(text or "")
    if not found:
        return None
    return " ".join(found[-1].replace("*", " ").split()).strip() or None


def offers_to_act(text: str) -> bool:
    """Does this reply END by asking the user whether the assistant should DO something?

    95.78 (D1): the harness registered a proposal only from a first-person promise ("I'll rewrite the
    widget"), so the same offer put as a question ("Would you like me to rewrite the widget?")
    registered nothing pending and the user's "yes" answered nothing — grammar decided whether their
    answer counted. Composed from the predicates that already define a question and a side effect, so
    it adds no vocabulary of its own beyond grammatical person."""
    tail = last_question(text)
    if not tail:
        return False
    return is_interrogative(tail) and bool(_FIRST_PERSON.search(tail)) and requests_side_effect(tail)


def refers_to_self(text: str) -> bool:
    """The user is talking about THEMSELVES ("what do you know about me", "my car") — such a turn
    must never lose its recalled autobiographical context to a router's needs_memory=False.
    A bare "tell me / show me" request does not count."""
    return bool(_SELF.search(text or ""))


_EFFECT = re.compile(r"\b(widget|dashboard|canvas|chart|graph|track|show me|display|create|build|make|write|save|"
                     r"run|execute|command|shell|bash|terminal|executa|corre|comando|"
                     r"file|script|app|page|skill|cria|criar|constr[oó]i|mostra|guarda|escreve|ficheiro|painel)\b",
                     re.IGNORECASE)


def requests_side_effect(text: str) -> bool:
    """Did the user ask for something to be MADE (widget, file, skill…)? A plain question never did —
    Phase 66.6: the live weather answer created an unasked widget carrying a fabricated value."""
    return bool(_EFFECT.search(text or ""))


_WORKSPACE = re.compile(r"\b(file|files|folder|directory|repo|repository|project|codebase|script|code|readme|"
                        r"module|function|class|bug in|run |install|build|compile|test suite|workspace|"
                        r"ficheiro|pasta|reposit[oó]rio|projeto|c[oó]digo)\b|[\w-]+\.(py|js|ts|json|md|txt|yml|toml)\b",
                        re.IGNORECASE)


_ACTION_OPENER = re.compile(r"^\s*(?:please\s+|por favor,?\s+)?(?:save|write|create|make|build|generate|read|open|list|show|"
                            r"display|run|execute|delete|remove|prepare|update|edit|rename|move|copy|"
                            r"cria|criar|faz|fazer|fa[c\u00e7]a|escreve|escrever|guarda|guardar|gera|gerar|l[e\u00ea]|abre|lista|mostra|corre|executa|"   # 95.47c: the PT "make"
                            r"apaga|remove|prepara|atualiza|edita|renomeia|move|copia)\b", re.IGNORECASE)


# 95.78 (D3): the CHANGING half of the action verbs above — the ones that leave the world different.
# The reading half (read, open, list, show, display) is deliberately absent: a step that asks to look
# at something is settled by a receipt that looked.
_CHANGES = re.compile(r"\b(write|writes|writing|rewrite|rewrites|rewriting|save|saves|saving|create|creates|creating|"
                      r"make|makes|making|build|builds|building|generate|generates|generating|update|updates|updating|"
                      r"edit|edits|editing|delete|deletes|deleting|remove|removes|removing|rename|renames|renaming|"
                      r"move|moves|moving|copy|copies|copying|deploy|deploys|deploying|install|installs|installing|"
                      r"escrev\w*|guarda\w*|cria\w*|faz|fazer|gera\w*|atualiza\w*|edita\w*|apaga\w*|remove\w*|"
                      r"renomeia\w*|move\w*|copia\w*|instala\w*)\b", re.IGNORECASE)


def changes_the_world(text: str) -> bool:
    """Does this step ask for something to be different afterwards? Used to refuse a READ receipt as
    proof of it (95.78 D3): a `bash cat` of an unrelated file closed a step that said "write the code",
    because the generic branch matched on a word the two happened to share."""
    return bool(_CHANGES.search(text or ""))


def is_action_request(clause: str) -> bool:
    """95.44: an imperative that asks for an action on a workspace artefact ("Save the name of my main
    project into a file called trabalho.txt") states nothing about the user -- it is not declarative."""
    return bool(_ACTION_OPENER.match(clause or "")) and refers_to_workspace(clause or "")


def refers_to_workspace(text: str) -> bool:
    """67.6: the ACTIVE WORKSPACE block is offered only when the user talks about files/code/the project —
    a UI complaint about THIS chat ("it's not clickable") must not be bound to the workspace project."""
    return bool(_WORKSPACE.search(text or ""))


_SUGGEST = re.compile(r"\b(maybe|perhaps|could you|can you|would you|you could|you can|you might|if you want|"
                      r"what if|how about|talvez|se calhar|podias|podes|poderias|pode ser|que tal)\b", re.IGNORECASE)
# X7b: an effect DEFERRED to the user's confirmation is a proposal by construction (permission-first, Phase 67)
_DEFERRAL = re.compile(r"\b(?:(?:but |mas )?(?:only |s[o\u00f3] )?(?:after|once|when|depois de|depois que|quando|assim que) (?:i|eu) "
                       r"(?:confirm|say so|give the go|approve|confirmar|disser|der o sinal|aprovar)|"
                       r"wait for my (?:confirmation|go|approval|ok|word)|hold off until i (?:give the word|say so|confirm)|until i say so|"
                       r"(?:fica|fico|fique|ficar)?\s*(?:[a\u00e0]\s+)?espera[r]?\s+(?:pela|a|da|de|pelo)\s+minha\s+(?:confirma[c\u00e7][a\u00e3]o|aprova[c\u00e7][a\u00e3]o|ordem|luz verde)|"
                       r"s[o\u00f3] (?:com|ap[o\u00f3]s) a minha (?:confirma[c\u00e7][a\u00e3]o|ordem)|s[o\u00f3] quando eu (?:mandar|disser|confirmar)|at[e\u00e9] eu (?:mandar|dizer|confirmar)|"
                       r"with my confirmation first|"
                       r"(?:n[a\u00e3]o\s+)?(?:avances|avan[c\u00e7]ar|prossigas|prosseguir|continues|continuar|fa[c\u00e7]as nada)\s+sem\s+(?:a\s+|o\s+)?(?:minha|meu)\s+(?:luz verde|autoriza[c\u00e7][a\u00e3]o|ordem|confirma[c\u00e7][a\u00e3]o|aval|sinal|ok)|"
                       r"(?:don'?t|do not|never)\s+(?:proceed|go ahead|continue|start|act)\s+without\s+my\s+(?:go-?ahead|approval|green light|say-?so|ok|word|confirmation))\b", re.IGNORECASE)   # 95.53; 95.71: "sem a minha luz verde"


def is_deferred_to_confirmation(text: str) -> bool:
    """X7b: the user asks for an effect but defers it to their own confirmation -- proposed, not executed."""
    return bool(_DEFERRAL.search(text or ""))


def is_suggestion(text: str) -> bool:
    """A suggestion ("you can maybe create a widget…") asks for a PROPOSAL, not an execution — the user's
    permission-first rule (Phase 67). An order ("create a widget…") executes. 95.25: judged by CLAUSE --
    a cue in a granting clause ("podes escrever o ficheiro:") does not govern the order that follows
    ("escreve-o com ..."); the message is a suggestion only if every effect-requesting clause carries a cue."""
    if is_deferred_to_confirmation(text):          # X7b: deferred to the user's confirmation = proposed
        return True
    text = text or ""
    clauses = [c for c in re.split(r"[.:;!?\n]+", text) if c.strip()]
    effect_clauses = [c for c in clauses if requests_side_effect(c)]
    if effect_clauses:
        return all(_SUGGEST.search(c) for c in effect_clauses)
    return bool(_SUGGEST.search(text))


# 95.50: the absolute-negation adverbials are negations too ("under no circumstances write to ...")
_ABS_NEG = r"under no circumstances|in no case|on no account|by no means|never ever|em circunst[a\u00e2]ncia alguma|em caso algum|de forma alguma|de maneira nenhuma|de modo algum|jamais"
_PROHIBIT = re.compile(r"\b(?:do not|don'?t|never|please don'?t|no need to|n[aã]o|nunca|" + _ABS_NEG + r")\s+(?:\w+\s+){0,2}?"
                       r"(?:create|make|build|write|save|generate|delete|remove|run|execute|install|modify|change|touch|"
                       r"cri(?:es|e|ar)|fa[cç]as?|escrev(?:as|a|er)|guard(?:es|e|ar)|apag(?:ues|ue|ar)|instal(?:es|e|ar)|"
                       r"constr(?:uas|ua|uir)|alter(?:es|e|ar)|mex(?:as|a|er))\b|"
                       r"\b(?:just|only|apenas|s[oó]|somente)\s+(?:answer|reply|explain|tell me|respond[ea]|explic[ae])\b|"
                       r"\bno (?:widgets?|files?|ficheiros?|arquivos?)\b", re.IGNORECASE)


def prohibits_effect(text: str) -> bool:
    """70.5 (M1.3): the user forbids effects this turn ("do not create a widget", "just answer", "não cries nenhum
    ficheiro") — a prohibition is turn STATE that closes authority regardless of router pins or keywords."""
    return bool(_PROHIBIT.search(text or ""))


# 73.4: a standing rule is STATED as standing — the language-neutral precondition for creating a new one
_STANDING_CUE = re.compile(
    r"\b(always|every (?:time|reply|answer|message|response)|each (?:reply|answer|message|response)|from now on|"
    r"in (?:every|each|all) (?:reply|answer|message|response)s?|at the (?:end|start|beginning) of (?:every|each|all|your)|"
    r"whenever|never again|stop (?:doing|adding|ending|starting)|sempre|a partir de agora|de agora em diante|"
    r"em (?:cada|todas? as?) respostas?|no (?:fim|final|in[ií]cio) de (?:cada|todas?)|todas as vezes|nunca mais|"
    r"para de|deixa de|d[ée]s de)\b", re.IGNORECASE)


def has_standing_cue(text: str) -> bool:
    return bool(_STANDING_CUE.search(text or ""))
