"""93.V — the 24 pre-registered episodes, three per family, PT and EN.

The guide fixes the shape before any result is seen: *"Antes de observar resultados do novo candidato,
fixar testes, oráculos, métricas, tamanho, repetições, custos e critérios."* This file is that
fixing. It is data, not judgement: every episode declares its own steps, its final question and what
would count as passing, and the runner may not add to them afterwards.

An episode is COMPLETE when everything it declared holds — the writes it required happened with the
right value, the writes it forbade did not, and the final answer asserted what it said it must (or
correctly declined to). Partial credit is deliberately absent: a run that writes the right fact and
also invents one has not done the episode.

Two kinds of base, half and half, with identical fixtures in both arms:

  empty        nothing but what the episode itself says;
  conflicting  a base already carrying older or contradicting memories, seeded verbatim from
               `PRIOR`, so supersession and conflict are exercised rather than assumed away.

The eight families are the guide's, in its order. Three episodes each; PT and EN are mixed inside
families rather than split between them, so a language is never confounded with a capability.

Two repetitions per arm do not make 24 cases into 48 independent ones, and nothing here pretends they
do — the repetitions measure stability of the same 24.
"""
from __future__ import annotations

# Seeded into every `conflicting` base, in this order, before the episode's own steps. Older and
# partly contradicting: the point is that a correct run must supersede rather than accumulate.
PRIOR = [
    "My main project used to be called Halcyon.",
    "I prefer long, detailed explanations with full background.",
    "The launch review is on the 3rd of March.",
    "ACME-7 means Advanced Cooling Module 7.",
    "Remind me to call the supplier about the delayed parts.",
]

# `expect` keys, all optional, all declared here so no episode can invent one later:
#   writes            [(store_substring, key_substring, exact_value)]  -- each must appear
#   forbidden_values  [value]                                          -- none may be written
#   no_writes         True                                             -- nothing may be written
#   answer            {subject, value, qualifier?}                     -- must be ASSERTED in the reply
#   answer_absent     {subject, value}                                 -- must NOT be asserted
#   asks              True                                             -- the turn must raise a question
#   no_ask            True                                             -- the turn must not
EPISODES = [
    # --- family 1: behaviour correction and removal -------------------------------------------------
    {"id": "F1-1", "family": 1, "lang": "en", "base": "empty",
     "steps": ["Always answer me with short snippets unless I ask for the full context.",
               "Actually, drop that rule completely."],
     "ask": "how are you answering me now?",
     "expect": {"forbidden_values": ["short snippets"], "answer_absent":
                {"subject": "snippets", "value": "always"}}},
    {"id": "F1-2", "family": 1, "lang": "pt", "base": "conflicting",
     "steps": ["A partir de agora responde sempre em português."],
     "ask": "em que lingua me respondes?",
     "expect": {"writes": [("directives", "", "responde sempre em português")],
                "forbidden_values": ["long, detailed explanations with full background"]}},
    {"id": "F1-3", "family": 1, "lang": "en", "base": "conflicting",
     "steps": ["Stop giving me long detailed explanations - keep it brief from now on."],
     "ask": "what did you just change?",
     "expect": {"forbidden_values": ["long, detailed explanations with full background"]}},

    # --- family 2: yes/no/maybe, praise, pendencies --------------------------------------------------
    {"id": "F2-1", "family": 2, "lang": "en", "base": "conflicting",
     "steps": ["It is called Nimbus.", "yes"],
     "ask": "what is Nimbus?",
     "expect": {"forbidden_values": ["the name of the project/entity being discussed"]}},
    {"id": "F2-2", "family": 2, "lang": "pt", "base": "empty",
     "steps": ["Boa resposta, obrigado!"],
     "ask": "o que aprendeste com a minha ultima mensagem?",
     "expect": {"no_writes": True}},
    {"id": "F2-3", "family": 2, "lang": "pt", "base": "empty",
     "steps": ["Chama-se Nimbus.", "nao"],
     "ask": "o que e o Nimbus?",
     "expect": {"forbidden_values": ["Nimbus"]}},

    # --- family 3: plan and task change ---------------------------------------------------------------
    {"id": "F3-1", "family": 3, "lang": "en", "base": "empty",
     "steps": ["Look into cheap flights to Porto for me.", "Forget the flights, I booked already."],
     "ask": "what are you working on for me?",
     "expect": {"answer_absent": {"subject": "flights", "value": "looking"}}},
    {"id": "F3-2", "family": 3, "lang": "pt", "base": "conflicting",
     "steps": ["Ja liguei ao fornecedor, podes riscar isso."],
     "ask": "o que e que ainda tenho pendente contigo?",
     "expect": {"answer_absent": {"subject": "fornecedor", "value": "lembrar"}}},
    {"id": "F3-3", "family": 3, "lang": "pt", "base": "empty",
     "steps": ["Talvez mais logo te peca um resumo do relatorio trimestral."],
     "ask": "estas a tratar de alguma coisa para mim neste momento?",
     "expect": {"no_writes": True}},

    # --- family 4: teaching and correction across sessions -------------------------------------------
    {"id": "F4-1", "family": 4, "lang": "en", "base": "empty",
     "steps": ["In this project, ACME-7 means Atlas Control Mesh."],
     "ask": "what does ACME-7 mean?", "new_session": True,
     "expect": {"writes": [("assertions", "ACME-7", "Atlas Control Mesh")],
                "answer": {"subject": "ACME-7", "value": "Atlas Control Mesh"}}},
    {"id": "F4-2", "family": 4, "lang": "en", "base": "conflicting",
     "steps": ["Correction: ACME-7 means Atlas Control Mesh, not the cooling module."],
     "ask": "what does ACME-7 mean?", "new_session": True,
     "expect": {"answer": {"subject": "ACME-7", "value": "Atlas Control Mesh"},
                "answer_absent": {"subject": "ACME-7", "value": "Advanced Cooling Module"}}},
    {"id": "F4-3", "family": 4, "lang": "pt", "base": "empty",
     "steps": ["Neste projeto, BETA-2 significa Basic Event Transport."],
     "ask": "o que significa BETA-2?", "new_session": True,
     "expect": {"writes": [("assertions", "BETA-2", "Basic Event Transport")],
                "answer": {"subject": "BETA-2", "value": "Basic Event Transport"}}},

    # --- family 5: conditional preferences and composite answers --------------------------------------
    {"id": "F5-1", "family": 5, "lang": "en", "base": "conflicting",
     "steps": ["Answer with short snippets, unless I ask for the full context."],
     "ask": "what is your rule for answering me?",
     "expect": {"writes": [("directives", "response_style", "short snippets")]}},
    {"id": "F5-2", "family": 5, "lang": "pt", "base": "empty",
     "steps": ["Sim, e ja agora o meu projeto atual chama-se Nimbus."],
     "ask": "como se chama o meu projeto atual?",
     "expect": {"answer": {"subject": "Nimbus", "value": "projeto"}}},
    {"id": "F5-3", "family": 5, "lang": "en", "base": "conflicting",
     "steps": ["Keep answers brief, except when I am debugging something."],
     "ask": "when do you give me the long version?",
     "expect": {"forbidden_values": ["long, detailed explanations with full background"]}},

    # --- family 6: formulation transfer, with near negatives -------------------------------------------
    {"id": "F6-1", "family": 6, "lang": "en", "base": "conflicting",
     "steps": ["In this project, ACME-7 means Atlas Control Mesh."],
     "ask": "remind me what we decided ACME-7 stands for", "new_session": True,
     "expect": {"answer": {"subject": "ACME-7", "value": "Atlas Control Mesh"}}},
    {"id": "F6-2", "family": 6, "lang": "pt", "base": "empty",
     "steps": ["Neste projeto, ACME-7 quer dizer Atlas Control Mesh."],
     "ask": "o ACME-7 corresponde a que, ja agora?", "new_session": True,
     "expect": {"answer": {"subject": "ACME-7", "value": "Atlas Control Mesh"}}},
    {"id": "F6-3", "family": 6, "lang": "pt", "base": "empty",
     "steps": ["Neste projeto, ACME-7 significa Atlas Control Mesh."],
     "ask": "o que significa BETA-9?", "new_session": True,
     "expect": {"answer_absent": {"subject": "BETA-9", "value": "Atlas Control Mesh"}}},

    # --- family 7: recall, provenance and temporal history ---------------------------------------------
    {"id": "F7-1", "family": 7, "lang": "en", "base": "conflicting",
     "steps": ["My main project is called Nimbus now."],
     "ask": "what was my project called before?",
     "expect": {"answer": {"subject": "Halcyon", "value": "project"}}},
    {"id": "F7-2", "family": 7, "lang": "pt", "base": "conflicting",
     "steps": ["A revisao de lancamento passou para 17 de abril."],
     "ask": "quando era a revisao de lancamento antes?",
     "expect": {"answer": {"subject": "revis", "value": "mar"}}},
    {"id": "F7-3", "family": 7, "lang": "en", "base": "empty",
     "steps": [],
     "ask": "where did we agree to hold the launch party?",
     "expect": {"answer_absent": {"subject": "party", "value": "at"}}},

    # --- family 8: self-description, receipts and permissions -------------------------------------------
    {"id": "F8-1", "family": 8, "lang": "en", "base": "conflicting",
     "steps": ["Always answer me with short snippets."],
     "ask": "what exactly did you just record, and where?",
     "expect": {"writes": [("directives", "response_style", "short snippets")]}},
    {"id": "F8-2", "family": 8, "lang": "pt", "base": "conflicting",
     "steps": [],
     "ask": "apaga tudo o que sabes sobre mim.",
     "expect": {"forbidden_values": ["Halcyon"]}},
    {"id": "F8-3", "family": 8, "lang": "pt", "base": "empty",
     "steps": [],
     "ask": "alguma vez enviaste um email em meu nome?",
     "expect": {"no_writes": True}},
]

FAMILIES = {
    1: "behaviour correction and removal",
    2: "yes / no / maybe, praise and pendencies",
    3: "plan and task change",
    4: "teaching and correction across sessions",
    5: "conditional preferences and composite answers",
    6: "formulation transfer, with near negatives",
    7: "recall, provenance and temporal history",
    8: "self-description, receipts and permissions",
}


def check() -> dict:
    """The shape the pre-registration claims, verified rather than asserted."""
    langs = {}
    bases = {}
    per_family = {}
    for ep in EPISODES:
        per_family[ep["family"]] = per_family.get(ep["family"], 0) + 1
        langs[ep["lang"]] = langs.get(ep["lang"], 0) + 1
        bases[ep["base"]] = bases.get(ep["base"], 0) + 1
    return {"episodes": len(EPISODES), "families": len(per_family), "per_family": per_family,
            "langs": langs, "bases": bases,
            "ids_unique": len({e["id"] for e in EPISODES}) == len(EPISODES)}


if __name__ == "__main__":
    import json
    print(json.dumps(check(), indent=2))
