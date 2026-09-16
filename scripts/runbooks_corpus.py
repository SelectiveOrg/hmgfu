"""Phase 75.1 — the sealed runbook set (`scripts/oracles/runbooks_v1.json`), deterministic, written BEFORE the bench runs.

12 executed plans (title + steps + the tool per step + outcome) as they would be finalized by sessions; for each, 3
paraphrased later requests in PT/EN that should surface THAT runbook (gold = plan id); 12 unrelated requests (chat,
user-fact questions, unrelated tasks) that must surface none. Hit@1 = the gold runbook is the top match; a false
surfacing = any runbook shown on an unrelated request.
"""
from __future__ import annotations

import hashlib
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "scripts", "oracles", "runbooks_v1.json")

PLANS = [
    ("p01", "Build the links widget", [("write the html for the links page", "write_file"), ("create the links widget", "create_widget")], "done",
     ["make me a widget with my links", "cria o widget dos links outra vez", "I want the links widget rebuilt on the canvas"]),
    ("p02", "Back up the notes folder", [("list the notes files", "bash"), ("copy the notes to backup/", "bash"), ("verify the backup sizes", "bash")], "done",
     ["back up my notes again", "faz backup da pasta de notas", "copy the notes folder to the backup location"]),
    ("p03", "Convert the CSV report to markdown", [("read report.csv", "read_file"), ("write report.md with a table", "write_file")], "done",
     ["turn the csv report into markdown", "converte o relatório csv para markdown", "I need report.csv as a markdown table"]),
    ("p04", "Set up the weekly review note", [("create weekly_review.md with the template", "write_file"), ("add the three standing questions", "write_file")], "done",
     ["prepare this week's review note", "prepara a nota da revisão semanal", "start the weekly review file for me"]),
    ("p05", "Rename the screenshots by date", [("list the screenshots", "bash"), ("rename each file to its date", "bash")], "partial",
     ["rename my screenshots by their date again", "renomeia as capturas de ecrã pela data", "put the date in the screenshot file names"]),
    ("p06", "Publish the reading list widget", [("write reading_list.html", "write_file"), ("create the reading list widget", "create_widget")], "done",
     ["show my reading list as a widget", "cria um widget com a minha lista de leitura", "I want the reading list on the canvas"]),
    ("p07", "Clean the downloads folder", [("list files older than 30 days", "bash"), ("move them to downloads/old", "bash")], "done",
     ["tidy up my downloads folder", "limpa a pasta de downloads", "move the old downloads out of the way"]),
    ("p08", "Draft the invoice for the clinic", [("read the hours log", "read_file"), ("write invoice_clinic.md", "write_file")], "done",
     ["draft the clinic invoice again", "faz a factura para a clínica", "prepare an invoice for the clinic from my hours"]),
    ("p09", "Summarise the meeting notes", [("read meeting_notes.md", "read_file"), ("write meeting_summary.md", "write_file")], "done",
     ["summarise today's meeting notes", "resume as notas da reunião", "give me a summary file of the meeting notes"]),
    ("p10", "Check disk usage and report", [("run the disk usage command", "bash"), ("write disk_report.md", "write_file")], "done",
     ["check how full the disk is and write it down", "verifica o espaço em disco e faz um relatório", "disk usage report please"]),
    ("p11", "Create the grocery list widget", [("write grocery.html", "write_file"), ("create the grocery widget", "create_widget")], "failed",
     ["make the grocery list widget", "cria o widget da lista de compras", "I want a grocery list on the canvas"]),
    ("p12", "Archive last month's logs", [("list last month's log files", "bash"), ("compress them into logs_archive.zip", "bash"), ("delete the originals", "bash")], "done",
     ["archive the logs from last month", "arquiva os logs do mês passado", "zip up last month's log files"]),
]

# v2 (75.1b): the user's ORIGINAL request that produced each plan — in the language the user used that day
REQUESTS = {
    "p01": "make a widget with my links", "p02": "faz um backup da minha pasta de notas",
    "p03": "convert report.csv into a markdown table", "p04": "prepara a minha nota de revisão semanal",
    "p05": "rename the screenshots so the date is in the name", "p06": "quero a minha lista de leitura como widget",
    "p07": "clean out the downloads folder", "p08": "faz a factura da clínica a partir do registo de horas",
    "p09": "summarise the meeting notes into a file", "p10": "vê o espaço em disco e escreve um relatório",
    "p11": "create a grocery list widget", "p12": "arquiva os logs do mês passado num zip",
}

UNRELATED = [
    "what is my favourite colour?", "qual é o nome do meu irmão?", "tell me a joke about cats", "bom dia, como estás?",
    "what did I say about the printer last week?", "how tall is Mount Kilimanjaro?", "explain what a mutex is",
    "translate 'good night' to Portuguese", "what is the weather like today in Valencia?", "quem é o presidente de Spain?",
    "remind me what my dog is called", "how many days until December?",
]


def build(version: str = "v1") -> dict:
    plans = [{"id": pid, "title": title, "steps": [{"text": t, "tool": tool} for t, tool in steps], "status": status,
              "requests": reqs, **({"request": REQUESTS[pid]} if version == "v2" else {})}
             for pid, title, steps, status, reqs in PLANS]
    return {"version": f"runbooks_{version}", "plans": plans, "unrelated": UNRELATED,
            "n_requests": sum(len(p["requests"]) for p in plans), "n_unrelated": len(UNRELATED)}


if __name__ == "__main__":
    import sys
    version = sys.argv[1] if len(sys.argv) > 1 else "v1"
    data = build(version)
    out = OUT.replace("runbooks_v1", f"runbooks_{version}")
    blob = json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(blob)
    OUT = out
    print(OUT, "plans", len(data["plans"]), "requests", data["n_requests"], "unrelated", data["n_unrelated"],
          "sha", hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12])
