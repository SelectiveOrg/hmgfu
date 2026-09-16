"""Phase 75.4 — the sealed self-recall set (`scripts/oracles/selfrecall_v1.json`), deterministic, written BEFORE the bench runs.

10 problems the agent worked on: the user's request (turn N), the agent's own REFLECTION on how it solved it (stored as a
`reflection` node — the LLM's reasoning, source=assistant), then two later paraphrased requests of the same problem
(turn N+k) on which that reflection should come back (gold = problem id). 6 user-fact questions on which NO reflection
may enter the answer context (the M6 echo-free rule must cover reflections). Recall = the gold reflection is in the
recalled set; leak = any reflection in the answer context of a user-fact question.
"""
from __future__ import annotations

import hashlib
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "scripts", "oracles", "selfrecall_v1.json")

PROBLEMS = [
    ("r01", "The CSV export from the bank has dates in two formats and the import script breaks on them.",
     "The bank CSV mixes dd/mm/yyyy and yyyy-mm-dd; parsing each row with a two-format fallback and normalising to ISO before the import fixed every failure — the naive single-format parse was the culprit, not the encoding.",
     ["the bank csv import is failing on the dates again", "o script de importação do banco volta a rebentar nas datas"]),
    ("r02", "The weather widget keeps showing yesterday's forecast.",
     "The widget cached the first forecast response and never refreshed because the cache key had no date in it; adding the local date to the cache key and refreshing at 06:00 solved the stale forecast.",
     ["why does the weather widget show old data", "o widget do tempo mostra a previsão de ontem outra vez"]),
    ("r03", "I need to merge three contact lists without duplicates.",
     "Merging contact lists by exact email produced duplicates because of case and trailing spaces; lowercasing and trimming emails before the merge, then keeping the most complete record per email, removed them all.",
     ["merge these contact lists and remove the duplicates", "junta as listas de contactos sem duplicados"]),
    ("r04", "Back up my photos folder to the external drive every week.",
     "A weekly photo backup with a plain copy re-copied everything each time; using a sync that compares size and modification time made the weekly run take minutes instead of an hour and skipped unchanged files.",
     ["set up the weekly photo backup to the external drive", "faz o backup semanal das fotos para o disco externo"]),
    ("r05", "Summarise the meeting notes into action items.",
     "Meeting notes mix decisions and chatter; extracting only lines with an owner and a verb, then grouping by owner, gave a clean action-item list the user accepted without edits.",
     ["turn today's meeting notes into action items", "resume as notas da reunião em acções"]),
    ("r06", "Convert the invoice PDF into a spreadsheet.",
     "The invoice PDF had a two-column layout that broke text extraction; extracting by table regions instead of raw text kept quantities aligned with descriptions and the totals matched.",
     ["extract the invoice pdf into a spreadsheet", "converte a factura em pdf para uma folha de cálculo"]),
    ("r07", "The shell script for renaming screenshots skips files with spaces.",
     "Files with spaces were skipped because the loop split on whitespace; quoting the variable and iterating over the glob directly renamed every screenshot, spaces included.",
     ["the screenshot rename script misses some files", "o script de renomear capturas salta ficheiros com espaços"]),
    ("r08", "Draft a polite reminder email to the clinic about the unpaid invoice.",
     "A reminder to the clinic worked best short: invoice number, amount, due date, one sentence asking for a payment date, no apology; the user sent it as drafted.",
     ["write the payment reminder to the clinic again", "escreve o lembrete de pagamento para a clínica"]),
    ("r09", "Plan the week's meals with what is in the fridge.",
     "Meal planning from the fridge inventory works when perishables are used first and each dinner reuses one ingredient from the previous day; the plan needed only two extra items.",
     ["plan this week's meals from the fridge", "planeia as refeições da semana com o que há no frigorífico"]),
    ("r10", "Check the disk usage and clean the downloads folder.",
     "Disk usage was dominated by the downloads folder's old installers; listing files older than 30 days and moving them to an archive folder recovered most of the space without deleting anything.",
     ["disk is full again, check what is taking space", "verifica o espaço em disco e limpa os downloads"]),
]

USER_FACT_QUESTIONS = [
    "what is my name?", "qual é a minha cor favorita?", "where do I live?", "what is my dog's name?",
    "qual é a minha linguagem de programação favorita?", "what is my brother's name?",
]

FACTS = ["My name is Teodoro.", "A minha cor favorita é chartreuse.", "I live in Valencia.", "My dog's name is Green.",
         "A minha linguagem de programação favorita é Java.", "My brother's name is Babys."]


def build() -> dict:
    return {"version": "selfrecall_v1",
            "problems": [{"id": pid, "request": req, "reflection": refl, "later": later} for pid, req, refl, later in PROBLEMS],
            "user_fact_questions": USER_FACT_QUESTIONS, "facts": FACTS}


if __name__ == "__main__":
    data = build()
    blob = json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(blob)
    print(OUT, "problems", len(data["problems"]), "later", sum(len(p["later"]) for p in data["problems"]),
          "user-fact", len(USER_FACT_QUESTIONS), "sha", hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12])
