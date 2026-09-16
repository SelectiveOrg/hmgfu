"""Phase 83.3 — the sentence MOULDS the fact detector recognises, in one module (pattern tables only; the algorithm stays
in `fact_detect`). The tables that lived in `fact_detect` moved here unchanged (62–77.5); the families below them are
the moulds the reserved set v5 showed missing (81.4): introductions, aliases, relocation verbs, job and company frames,
birthdays, preference frames, pets, family appositions, colon lists, topic prefixes. Every value is copied from the
user's words — a mould that would need an inferred word ("I teach maths" → "maths teacher") is deliberately absent.
"""
from __future__ import annotations

import re

from .slots import infer_slot_from_value

_VALUE = r"((?:[A-Z][a-z]?\.|[\w'/-]+)(?:\s+(?:[A-Z][a-z]?\.|[\w'/-]+)){0,5})"
# R2 (95.12): the LEADING twin of the trailing-hedge strip in fact_detect._clean_value (83.2) --
# "my real name is actually X" put "actually" into the value and the name-shape gate rejected the name.
LEADING_HEDGE = re.compile(r"^(?:(?:actually|really|in fact|honestly|na verdade|afinal|realmente|de facto)\s+)+", re.IGNORECASE)
# 95.30/95.34: the cue that INTRODUCES a value is not part of it ("chama-se Lua" -> "Lua"); one cleaner, every producer
LEADING_CUE = re.compile(r"^(?:chama-se|chamo-me|is called|called|named|means|significa|quer dizer|is|\u00e9|e)\s+", re.IGNORECASE)
# 95.39: definite-article siblings ("the main project is called X" / "o projeto principal chama-se X"); WEAK like the colon form
COPULA_EN = r"is called|is named|is now called|is known as|is referred to as|goes by|answers to|is|are|=|isn'?t|is not|aren'?t|are not"   # 95.51: one class
_THE_IS = re.compile(r"(?<!\bof )\bthe\s+([a-z][\w' -]{1,30}?)\s+(?:" + COPULA_EN + r")\s+" + _VALUE, re.IGNORECASE)
_MARKED_HEAD = re.compile(r"\b(?:my|our|meu|minha|nosso|nossa|of|do|da|de|dos|das)\b|'s\b", re.IGNORECASE)   # 95.39: someone's
_THE_IS_PT = re.compile(r"\b(?<!\bd)(?:o|a)\s+([a-z\u00C0-\u00FF][\w' \u00C0-\u00FF]{1,60}?)\s+(?:chama-se|chamam-se|passou a chamar-se|\u00e9 agora|\u00e9)\s+" + _VALUE, re.IGNORECASE)
# PT rename of a pet: "a minha gata ja nao se chama Sol, chama-se Lua" -> the species key, value Lua
_PET_RENAME_PT = re.compile(r"\b(?:o |a )?(?:meu|minha|nosso|nossa)\s+(c[a\u00e3]o|cadela|cachorro|gat[oa])\s+"
                            r"(?:(?:j[a\u00e1] )?n[a\u00e3]o se chama|deixou de se chamar|j[a\u00e1] n[a\u00e3]o [e\u00e9])\s+[^,;.]+?[,;]\s*"   # 95.52: the retirement
                            r"(?:agora\s+)?(?:chama-se|passou a chamar-se|[e\u00e9])\s+" + _VALUE, re.IGNORECASE)

# "I live in <place>", "call me / start calling me <alias>", "<Name> my dog|cat", "my dog|cat <Name>"
_FORM_PATTERNS = (
    # 77.5 (C): the negation may sit INSIDE the cue ("I no longer live in", "já não moro em") — see the neg window
    (re.compile(r"\b(?:i (?:no longer |don't |do not |never )?live in|i'm living in|i am living in|i(?:'ve| have) been living in|"
                r"i'm based in|i am based in|(?:eu )?(?:j[aá] )?(?:n[aã]o )?(?:moro|vivo|resido|estou|estamos|est[aá]s)\s+(?:em|na|no|nas|nos))\s+" + _VALUE, re.IGNORECASE),   # 95.68: estar em
     "identity.location"),
    # 77.5 (F): a move, or "home is <place> (now)"
    (re.compile(r"\b(?:(?:i|we)(?:'ve| have)? (?:just |recently )?moved to|mudei-me para|mud[aá]mo-nos para|mudei para|mud[aá]mos para|"
                r"(?:my |our )?home is(?: now)?(?: in)?)\s+" + _VALUE, re.IGNORECASE),
     "identity.location"),
    (re.compile(r"\b(?:call me|calling me|cham(?:a|em|ar)-me|trat(?:a|em|ar)-me por|me cham(?:e|em) de)\s+" + _VALUE, re.IGNORECASE),
     "identity.alias"),
    (re.compile(r"\b(?:i work as(?: an?)?|trabalho como|sou (?:um |uma )?(?=\w+(?:ista|eiro|eira|or|ora|ente|ico|ica)\b))\s*" + _VALUE, re.IGNORECASE),
     "identity.job"),
    # 77.5 (E): birthday, programming language, team — verb/noun frames that name the attribute by the verb itself
    (re.compile(r"\b(?:my birthday (?:is|falls) on|my birthday is|i was born on|fa[cç]o anos (?:a|em|no dia)|"
                r"o meu anivers[aá]rio [eé] (?:a|em|no dia)|nasci (?:a|em|no dia))\s+(?:the\s+)?" + _VALUE, re.IGNORECASE),
     "identity.birthday"),
    (re.compile(r"\b(?:i (?:mostly |mainly |usually |now |still )?(?:code|program|develop|write code)(?: mostly| mainly| mainly)? in|"
                r"programo(?: sobretudo| principalmente| mais| agora)? em|escrevo c[oó]digo em|codifico em)\s+" + _VALUE, re.IGNORECASE),
     "pref.language"),
    (re.compile(r"\bi(?:'m| am) an?\s+" + _VALUE + r"\s+(?:supporter|fan)\b", re.IGNORECASE), "pref.team"),
    (re.compile(r"\b(?:(?:sou|somos) (?:adept[oa]s?|f[aã]s?|torcedora?s?|s[oó]ci[oa]s?) d[oa]s?|tor[cç]o pel[oa]s?)\s+" + _VALUE, re.IGNORECASE),
     "pref.team"),
)

# 77.5 (E): frames that name the ATTRIBUTE and the value; the attribute goes through the slot schema like "my X is Y"
_ATTR_FORMS = (
    re.compile(r"\b([a-z\u00C0-\u00FF]+)-wise\b[^.!?;]{0,30}?\bi\s+(?:always\s+|usually\s+|mostly\s+)?(?:go for|pick|choose|prefer|opt for)\s+" + _VALUE, re.IGNORECASE),
    re.compile(r"\b(?:a|o)\s+([a-z\u00C0-\u00FF]+(?:\s+[a-z\u00C0-\u00FF]+)?)\s+(?:de\s+)?que\s+(?:eu\s+)?(?:mais\s+)?"
               r"(?:gosto|prefiro|ou[cç]o|oi[cç]o|adoro|uso|escolho|como|bebo|leio|vejo)(?:\s+mais)?\s+(?:é|e)\s+(?:o |a )?" + _VALUE, re.IGNORECASE),
    re.compile(r"\bthe\s+([a-z]+(?:\s+[a-z]+)?)\s+(?:that\s+)?i\s+(?:like|love|prefer|enjoy|drink|eat|use|listen to|play|watch|read)\s+(?:the\s+)?most\s+is\s+(?:the\s+)?" + _VALUE, re.IGNORECASE),
    re.compile(r"\b(?:one|a single)\s+([a-z]+)\s+(?:that\s+)?i\s+(?:love|adore|like|prefer|enjoy)\s*,?\s*(?:it'?s|it is|that'?s)\s+(?:the\s+)?" + _VALUE, re.IGNORECASE),
)
# 77.5 (E): "my favourite colour used to be teal, now it's amber" — ONE construction: the new value supersedes the old
_TRANSITION_FORM = re.compile(r"\b(?:(?:o |a )?(?:my|meu|minha|the)\s+)([a-z\u00C0-\u00FF][\w' \u00C0-\u00FF-]{1,40}?)\s+(?:used to be|was|era|costumava ser)\s+(?:the |o |a )?"
                              + _VALUE + r"\s*[,;]?\s*(?:but |mas |and |e )?(?:now|nowadays|these days|today|currently|agora|hoje|a[ct]ualmente)\s+"
                              r"(?:it'?s|it is|is|é|e)\s+(?:the |o |a )?" + _VALUE, re.IGNORECASE)
# 69.4 species-aware pets: (pattern, value_group, species_group) → pet.dog.name / pet.cat.name / pet.name
_PET_FORMS = (
    (_PET_RENAME_PT, 2, 1),                                # 95.34: the rename names the species and the NEW name
    (re.compile(r"\b(?:my|our) (dog|cat|pet)(?: is called| is named| is| answers to| goes by|,)?\s+" + _VALUE, re.IGNORECASE), 2, 1),
    (re.compile(r"^\s*([A-Z][\w'-]+(?:\s+[A-Z][\w'-]+){0,2})\s*,?\s+(?:is )?my (dog|cat|pet)\b"), 1, 2),
    (re.compile(r"\b(?:o |a )?(?:meu|minha|nosso|nossa)\s+(c[aã]o|cadela|cachorro|gat[oa]|animal)\s+(?:chama-se|é|e|=)\s+" + _VALUE,
                re.IGNORECASE), 2, 1),
    # 77.5 (D): the "have" frame — "we have a dog at home, his name is Bolt" / "temos um cão em casa, chama-se Faísca"
    (re.compile(r"\b(?:i have|we have|i've got|we've got|tenho|temos)\s+(?:a |an |um |uma )?(dog|cat|pet|c[aã]o|cadela|cachorro|gat[oa])\b[^.!?;]{0,25}?"
                r"(?:(?:his|her|its|the|o|a)\s+)?(?:name is|named|called|chama-se|chamad[oa])\s+" + _VALUE, re.IGNORECASE), 2, 1),
)
# 77.5 (D): "I have two dogs, Bolt and Kika" — two values, two entities (the store's cardinality rule assigns .2)
_PET_ENUM = re.compile(r"\b(?:i have|we have|i've got|we've got|tenho|temos)\s+(?:two|three|dois|duas|tr[eê]s)\s+"
                       r"(dogs|cats|pets|c[aã]es|cadelas|cachorros|gat[oa]s)\s*[,:]?\s*(?:o |a |the )?" + _VALUE +
                       r"\s+(?:and|e)\s+(?:o |a )?" + _VALUE, re.IGNORECASE)
_SPECIES = {"dog": "pet.dog.name", "cao": "pet.dog.name", "cão": "pet.dog.name", "cadela": "pet.dog.name",
            "cachorro": "pet.dog.name", "cat": "pet.cat.name", "gato": "pet.cat.name", "gata": "pet.cat.name",
            "dogs": "pet.dog.name", "caes": "pet.dog.name", "cães": "pet.dog.name", "cadelas": "pet.dog.name",
            "cachorros": "pet.dog.name", "cats": "pet.cat.name", "gatos": "pet.cat.name", "gatas": "pet.cat.name"}

# ---------------------------------------------------------------- 83.3: unseen moulds -------------------------------
_NAME = r"([A-Z\u00C0-\u00DD][\w'-]+(?:\s+(?:[A-Z\u00C0-\u00DD][\w'.-]+|d[aoe]s?|e|van|von|del|di))*)"
_SPECIES.update({"kitten": "pet.cat.name", "puppy": "pet.dog.name", "gatinho": "pet.cat.name", "gatinha": "pet.cat.name",
                 "cachorrinho": "pet.dog.name", "cachorrinha": "pet.dog.name"})
_FORM_PATTERNS = _FORM_PATTERNS + (
    # identity.name — introductions
    (re.compile(r"\b(?i:let me introduce myself(?: properly)?|allow me to introduce myself|deixa-me apresentar-me(?: como deve ser)?|"
                r"permite-me que me apresente)\s*[:,]?\s+" + _NAME), "identity.name"),
    (re.compile(r"\b(?i:the name'?s|the name is|o nome [eé])\s+" + _NAME), "identity.name"),
    (re.compile(r"\b(?i:for your records|for the record|para os (?:teus|seus|vossos) registos)\s*[:,]?\s*(?i:full name|nome completo|name|nome)?\s*[:,]?\s*" + _NAME), "identity.name"),
    (re.compile(r"\b(?i:full name|nome completo)\s*:\s*" + _NAME), "identity.name"),
    (re.compile(r"^\s*(?i:hi|hello|hey|ol[aá])\b[^.!?]{0,12}?,?\s+" + _NAME + r"\s+(?i:here)\b"), "identity.name"),
    (re.compile(r"\b(?i:aqui [eé] [oa]|daqui [eé] [oa]|fala [oa])\s+" + _NAME), "identity.name"),
    (re.compile(r"\b(?i:i am|i'm|eu sou|sou|chamo-me)\s+([A-Z\u00C0-\u00DD][\w'-]+)\s*,\s*(?i:that'?s my (?:actual|real) name|[eé] mesmo o meu nome|that is my name)"), "identity.name", True),
    # identity.alias
    (re.compile(r"\b(?:friends|people|everyone|everybody|os amigos|toda a gente|todos)\s+(?:call me|tratam-me por|chamam-me)\s+" + _VALUE, re.IGNORECASE), "identity.alias"),
    (re.compile(r"\b(?:address me as|refer to me as|trat(?:a|em|ar|as)-me por|tratam-me por)\s+" + _VALUE, re.IGNORECASE), "identity.alias"),
    (re.compile(r"\b(?:i go by|i now go by|sou conhecid[oa] por|sou conhecid[oa] como|known as|go by the name(?: of)?)\s+" + _VALUE, re.IGNORECASE), "identity.alias"),
    (re.compile(r"\b(?:chama-me|call me)\s+(?:s[oó]|just|only|simply|apenas)\s+" + _VALUE, re.IGNORECASE), "identity.alias"),
    # identity.location — relocation verbs, home frames
    (re.compile(r"\b(?:(?:i|we)(?:'ve| have)? settled in|assentei(?: de vez)? em|assent[aá]mos(?: de vez)? em|(?:i|we) relocated to|mudei de casa para|"
                r"mud[aá]mos de casa para|(?:i(?:'m| am) |we(?:'re| are) )?(?:currently |now )?(?:residing|living|based) in|resido em|residimos em|"
                r"estou a viver em|estamos a viver em|a viver em|(?:i|we)(?:'ve| have) lived in|(?:i(?:'m| am) )?based out of|(?:my |our )?home base is(?: now| still)?|"
                r"(?:a|o) (?:minha|nossa) base(?: agora| hoje)? [eé]|(?:my|our) home has been|(?:a|o) (?:minha|nossa) casa(?: agora)? [eé])\s+" + _VALUE, re.IGNORECASE), "identity.location"),
    # identity.job
    (re.compile(r"\b(?:i earn my living as|ganho a vida como|by profession i(?:'m| am)|de profiss[aã]o sou|my job title is|o meu cargo [eé]|"
                r"i(?:'m| am) employed as|i(?:'m| am) working as|estou a trabalhar como)\s+(?:an?\s+|um\s+|uma\s+)?" + _VALUE, re.IGNORECASE), "identity.job"),
    # identity.company — 90.O: the plain positive of the frame the compound ("I work at X as a Y") and the
    # retraction ("I no longer work at X") already read. `_NAME` keeps it to proper nouns, and the PT branch will not
    # fire on the project idiom ("trabalho no projeto X"), which EN separates by preposition ("work at" vs "work on").
    (re.compile(r"\b(?i:i(?:'m| am) employed at|i work at|i work for|"
                r"trabalho n[oa](?!\s*(?:projet|project))|trabalho para [oa]?)\s+" + _NAME),
     "identity.company"),
    # identity.birthday
    (re.compile(r"\b(?:i celebrate my birthday (?:every|on)|fa[cç]o anos todos os dias|my birthday falls on|celebro o meu anivers[aá]rio a)\s+(?:the\s+)?" + _VALUE, re.IGNORECASE), "identity.birthday"),
    # pref.language
    (re.compile(r"\b(?:i write most of my code in|escrevo a maior parte do meu c[oó]digo em|i mostly write|desenvolvo(?: sobretudo| principalmente| mais)? em|"
                r"i develop(?: mostly| mainly)? in|i(?:'m| am) most productive in)\s+" + _VALUE, re.IGNORECASE), "pref.language"),
    (re.compile(r"\b(?:sou|trabalho como) (?:programador|programadora|developer|engenheir[oa]|dev) de\s+" + _VALUE, re.IGNORECASE), "pref.language"),
    # pref.music / pref.team
    (re.compile(r"\b(?:the music i listen to most is|a m[uú]sica que mais oi[cç]o [eé]|a m[uú]sica que mais ou[cç]o [eé])\s+" + _VALUE, re.IGNORECASE), "pref.music"),
    (re.compile(r"\b(?i:i support)\s+" + _NAME), "pref.team"),
    # pref.food
    (re.compile(r"\b(?:give me|d[aá]-me)\s+" + _VALUE + r"\s+(?:over any other|em vez de qualquer outra|above any other|instead of any other)\b", re.IGNORECASE), "pref.food"),
    (re.compile(r"\bi could eat\s+" + _VALUE + r"\s+every\b", re.IGNORECASE), "pref.food"),
    (re.compile(r"\bcomia\s+" + _VALUE + r"\s+todos os dias\b", re.IGNORECASE), "pref.food"),
    # pref.drink
    (re.compile(r"\b(?:i only drink|s[oó] bebo|i always drink|bebo sempre|i only ever drink)\s+" + _VALUE, re.IGNORECASE), "pref.drink"),
)
# multi-slot frames: (pattern, [(slot, group), ...])
MULTI_MOULDS = (
    # 83.4 sequences: a relocation chain across sentences — the LAST place is the current one
    (re.compile(r"\b(?i:(?:i|we) moved to|mudei-me para|mud[aá]mo-nos para|mudei para)\s+" + _NAME + r"\.?\s+(?i:then|depois)\s+(?i:to|para)\s+" + _NAME +
                r"\.?\s+(?i:now i'?m in|now i am in|now i live in|now we'?re in|agora estou em|agora moro em|agora vivo em|agora estamos em)\s+" + _NAME),
     [("identity.location", 3)]),
    (re.compile(r"\b(?:i(?:'m| am) employed at|i work at|i work for|trabalho n[oa]|trabalho para [oa]?)\s+(.+?)\s+(?:as an?|as|como)\s+(?:um |uma )?" + _VALUE, re.IGNORECASE),
     [("identity.company", 1), ("identity.job", 2)]),
    (re.compile(r"\b(?i:name|nome)\s+" + _NAME + r"\s*,\s*(?i:city|cidade)\s+" + _NAME + r"\s*,\s*(?i:job|profiss[aã]o|profession)\s+" + _VALUE),
     [("identity.name", 1), ("identity.location", 2), ("identity.job", 3)]),
    (re.compile(r"\b(?i:(?:i|we) moved from)\s+" + _NAME + r"\s+(?i:to)\s+" + _NAME), [("identity.location", 2)]),
    (re.compile(r"\b(?i:mudei-me|mud[aá]mo-nos|mudei|mud[aá]mos) (?i:de)\s+" + _NAME + r"\s+(?i:para)\s+" + _NAME), [("identity.location", 2)]),
    (re.compile(r"\b(?i:(?:we|i)(?:'ve| have)? made)\s+" + _NAME + r"\s+(?i:(?:our|my) home)\b"), [("identity.location", 1)]),
    (re.compile(r"\b(?i:(?:fizemos|fiz) de)\s+" + _NAME + r"\s+(?i:a (?:nossa|minha) casa)\b"), [("identity.location", 1)]),
)
# species frames: (pattern, species_group, value_group, ordinal)
SPECIES_MOULDS = (
    (re.compile(r"\b(?:we|i) adopted an? (kitten|puppy|cat|dog)\b[^.!?]{0,30}?\bnamed (?:her|him|it)\s+" + _VALUE, re.IGNORECASE), 1, 2, False),
    (re.compile(r"\badopt[aá]mos (?:uma|um) (gatinh[oa]|cachorrinh[oa]|c[aã]o|gat[oa]|cadela)\b[^.!?]{0,30}?\bcham[aá]mos-lhe\s+" + _VALUE, re.IGNORECASE), 1, 2, False),
    (re.compile(r"\bthe (dog|cat) (?:we|i) have\b[^.!?]{0,20}?\b(?:answers to|goes by|is called)\s+" + _VALUE, re.IGNORECASE), 1, 2, False),
    (re.compile(r"\b[oa] (c[aã]o|gat[oa]|cadela) que (?:temos|tenho)\b[^.!?]{0,20}?\b(?:responde por|chama-se)\s+" + _VALUE, re.IGNORECASE), 1, 2, False),
    (re.compile(r"\b(?:i|we) got a second (dog|cat)\b[^.!?]{0,12}?\b(?:her|his|its) name is\s+" + _VALUE, re.IGNORECASE), 1, 2, True),
    (re.compile(r"\b(?:tenho|temos) (?:um segundo|uma segunda) (c[aã]o|gat[oa]|cadela)\b[^.!?]{0,12}?\bchama-se\s+" + _VALUE, re.IGNORECASE), 1, 2, True),
    (re.compile(r"\b(?i:my|our|o meu|a minha)\s+(?i:(dog|cat|c[aã]o|gat[oa]|cadela))\s+([A-Z\u00C0-\u00DD][\w'-]+)\b(?!\s*(?i:is called|is named|chama-se|,\s*(?:is|é)\s+my))"), 1, 2, False),
)
# slots whose values end at a complement ("nurse at the hospital", "Pemba in January"); food/drink/colour values keep their prepositions
PREP_CUT_SLOTS = {"identity.location", "identity.alias", "identity.job", "identity.birthday", "identity.company", "identity.name",
                  "pref.language", "pref.team"}
# "with my wife Telma" — the relation names the slot, the capitalised word is the name
FAMILY_APPOSITION = re.compile(r"\b(?i:my|a minha|o meu)\s+(?i:(wife|husband|partner|sister|brother|mother|father|esposa|mulher|marido|irm[aã]|irm[aã]o|m[aã]e|pai))\s+"
                               r"([A-Z\u00C0-\u00DD][\w'-]+)\b(?!\s*(?i:is|é|are|chama-se|=|'s|’s))")
FAMILY_SLOT = {"wife": "family.partner_name", "husband": "family.partner_name", "partner": "family.partner_name", "esposa": "family.partner_name",
               "mulher": "family.partner_name", "marido": "family.partner_name", "sister": "family.sister_name", "irmã": "family.sister_name",
               "irma": "family.sister_name", "brother": "family.brother_name", "irmão": "family.brother_name", "irmao": "family.brother_name",
               "mother": "family.mother_name", "mãe": "family.mother_name", "mae": "family.mother_name", "father": "family.father_name", "pai": "family.father_name"}
# attribute-naming frames: (pattern, attr_group, value_group)
ATTR_VALUE_MOULDS = (
    # 83.4 sequences: "my favourite colour was teal, then amber, and today it's indigo" — the last value is current
    (re.compile(r"\b(?:my|a minha|o meu)\s+([a-z\u00C0-\u00FF][\w' \u00C0-\u00FF-]{1,40}?)\s+(?:was|used to be|foi|era)\s+(?:the |o |a )?" + _VALUE +
                r"(?:\s*,\s*(?:then|depois)\s+(?:the |o |a )?" + _VALUE + r")+\s*,?\s*(?:and|e)?\s*(?:today|now|hoje|agora)\s+(?:it'?s|it is|is|[eé])\s+(?:the |o |a )?" + _VALUE,
                re.IGNORECASE), 1, 4),
    (re.compile(r"^\s*(cor|comida|bebida|m[uú]sica|equipa|linguagem|colou?r|food|drink|music|team|language)\s+(?:favorit[ao]|preferid[ao]|favou?rite)?\s*:\s*" + _VALUE, re.IGNORECASE), 1, 2),
    (re.compile(r"\bif i had to (?:pick|choose) (?:one|a|a single)\s+(\w+)\b[^.!?]*?\bit would be\s+" + _VALUE, re.IGNORECASE), 1, 2),
    (re.compile(r"\bse tivesse de escolher (?:uma|um)\s+(\w+)\b[^.!?]*?\bseria\s+(?:o |a )?" + _VALUE, re.IGNORECASE), 1, 2),
    (re.compile(r"\bn[aã]o h[aá]\s+(\w+)\s+que\s+(?:bata|ganhe [aà]|supere)\s+(?:o |a )?" + _VALUE, re.IGNORECASE), 1, 2),
    (re.compile(r"^\s*(?:o |a )?" + _VALUE + r"\s+(?:is|[eé]) (?:the|a|o)\s+(\w+)\s+(?:i|que|a que)\b[^.!?]*?\b(?:keep coming back to|volto sempre|always (?:come|go) back to)", re.IGNORECASE), 2, 1),
    (re.compile(r"^\s*" + _VALUE + r"\s+[eé] a minha\s+([a-z\u00C0-\u00FF]+(?: de elei[cç][aã]o| favorita| preferida)?)\s*[.!]?\s*$", re.IGNORECASE), 2, 1),
)
# value-inferred frames: the value's class decides the slot (colour / language / drink / food), else nothing is written
INFER_MOULDS = (
    re.compile(r"\bnothing beats\s+" + _VALUE, re.IGNORECASE),
    re.compile(r"\b(?:i (?:always|usually) order|pe[cç]o sempre|costumo pedir)\s+" + _VALUE, re.IGNORECASE),
)
_JOBS = (r"nurse|midwife|teacher|engineer|developer|programmer|accountant|electrician|plumber|driver|welder|lawyer|doctor|farmer|mechanic|"
         r"pilot|chef|cook|cashier|teller|analyst|designer|architect|journalist|scientist|student|carpenter|painter|dentist|pharmacist|"
         r"physiotherapist|translator|consultant|manager|secretary|receptionist|firefighter|soldier|sailor|fisherman|tailor|baker|butcher|"
         r"barber|hairdresser|photographer|writer|editor|librarian|economist|statistician|surveyor|geologist|biologist|chemist|physicist|"
         r"mathematician|researcher|professor|lecturer|coach|trainer|guard|cleaner|gardener|waiter|waitress|bartender|freelancer|entrepreneur|"
         r"paramedic|surgeon|vet|veterinarian|optician|auditor|banker|broker|clerk|technician|operator|foreman|miner|tutor")
JOB_COPULA = re.compile(r"\bi(?:'m| am) an?\s+(?:[\w+#.-]+\s+)?(" + _JOBS + r")\b", re.IGNORECASE)
LANG_COPULA = re.compile(r"\bi(?:'m| am) an?\s+([\w+#.-]+)\s+(?:developer|programmer|dev|engineer|coder)\b", re.IGNORECASE)
# a topic prefix scopes the message: "Food-wise, my weakness is badjias" / "Em termos de comida, …" / "Em música, é só amapiano"
TOPIC_PREFIX = re.compile(r"^\s*(?:(\w+)-wise|em termos de (\w+)|em (\w+)|quanto a (\w+)|as for (\w+)|when it comes to (\w+))\s*,?\s+", re.IGNORECASE)
TOPIC_VALUE = (
    (re.compile(r"\b(?:i(?:'m| am) all about|it'?s all about|[eé] s[oó]|my weakness is|a minha fraqueza (?:[eé]|s[aã]o)|my thing is)\s+" + _VALUE, re.IGNORECASE), None),
)
# 83.5 retirements by VALUE: (pattern, slot, value_group) → clear_value — only that value is retired
RETRACT_VALUE_MOULDS = (
    (re.compile(r"\b(?i:i no longer work (?:at|for)|i don'?t work (?:at|for)(?: anymore| any more)?|i stopped working (?:at|for)|i left|"
                r"j[aá] n[aã]o trabalho n[oa]|j[aá] n[aã]o trabalho para [oa]?|deixei de trabalhar n[oa]|sa[ií] d[oa])\s+" + _NAME), "identity.company", 1),
    (re.compile(r"\b(?i:don'?t call me|do not call me|stop calling me|please don'?t call me|n[aã]o me chames|n[aã]o me chame|n[aã]o me trates por|"
                r"para de me chamar|parem de me chamar)\s+" + _VALUE), "identity.alias", 1),
)
_APPOSITION_ATTR = re.compile(r"^(?:dog|cat|pet|c[aã]o|gat[oa]|cadela|wife|husband|partner|sister|brother|mother|father|son|daughter|esposa|marido|"
                              r"irm[aã]o?|m[aã]e|pai|filh[oa]|friend|amig[oa]|colleague|colega|boss|chefe)\s+[A-Z\u00C0-\u00DD]")


def apposition(attr: str) -> bool:
    """"dog Simba", "sister Dércia": the attribute head names a relation and the next word is a name — the sentence
    predicates something about that person or pet; its value is not a new name."""
    return bool(_APPOSITION_ATTR.match((attr or "").strip()))


def split_job_language(val: str):
    """"programador de Kotlin" / "Kotlin developer" → (job, language) when the tail/head is a programming language."""
    m = re.match(r"^(.+?)\s+(?:de|em|in)\s+([\w+#.-]+)$", val or "")
    if m and infer_slot_from_value(m.group(2)) == "pref.language":
        return m.group(1), m.group(2)
    return val, None
