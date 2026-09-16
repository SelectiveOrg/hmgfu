"""Seed a throwaway demo graph with points across the REAL lifecycle states, so the hex viz can be
screenshotted showing TEMP (dashed empty) / CANDIDATE (partial) / FACT (volume + internal-hexes from
the ledger) / SUPERSEDED (faded). Ledger signals are written via the real regulator.transition — no
faked state. Run: python scripts/seed_viz_demo.py"""

import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["HMGFU_REGULATOR_ENABLED"] = "1"

from hmgfu.agent import AgentEngine   # noqa: E402

DB = str(Path(__file__).resolve().parents[1] / "scratch" / "hmgfu_viz_demo.db")
if os.path.exists(DB):
    os.remove(DB)
Path(DB).parent.mkdir(exist_ok=True)

e = AgentEngine(db_path=DB)
FACTS = [
    "o meu nome e Ana", "moro em valencia", "trabalho na area de TI", "gosto de xima com caril",
    "tenho um cao chamado Rex", "o meu carro e um Toyota", "estudei na universidade eduardo mondlane",
    "sou do signo de leao", "toco viola nos tempos livres", "a minha cor favorita e azul",
    "nasci em 1994", "o meu apelido e Vidal",
]
pts = [e.ingest(f, source="user") for f in FACTS]

# TEMP: pts[0:4] left with an empty ledger (c = TEMP_C = 0.40 → temp)
# CANDIDATE: one explicit each (c = 0.70 → candidate)
for p in pts[4:8]:
    e.regulator.transition(p.id, "explicit")
# FACT: two explicit + some silent/praise (c = 1.0, explicit≥1 → fact; ledger drives the internal-hexes)
for p in pts[8:11]:
    e.regulator.transition(p.id, "explicit")
    e.regulator.transition(p.id, "explicit")
    for _ in range(3):
        e.regulator.transition(p.id, "silent_use")
    e.regulator.transition(p.id, "praise")
# SUPERSEDED (direct correction signal, no ingested successor — a real case: the link is absent)
e.regulator.transition(pts[11].id, "correction")

# SUPERSEDED with a REAL successor (B2): ingest wrong + right, then run the ACTUAL supersede
# machinery (dream.mark_tension writes the `contradiction` FuEdge + flips the loser's status) and
# record the absorbing correction signal. The viz derives `superseded_by` from that real edge —
# no faked field; this is exactly what grader._apply_correction does on a live correction.
from hmgfu.dream import mark_tension   # noqa: E402
wrong = e.ingest("o meu carro e um Toyota vermelho", source="user", mtype="fact")
right = e.ingest("o meu carro e um Honda azul", source="user_explicit", mtype="fact")
mark_tension({"a": wrong.id, "b": right.id, "score": 0.9,
              "resolution": {"winner": right.id, "loser": wrong.id}}, e.graph)
if e.graph.points[wrong.id].status == "superseded":
    e.regulator.transition(wrong.id, "correction")

for p in pts + [wrong, right]:
    c, st = e.regulator.evaluate(p.id)
    print(f"  {st:11s} c={c:.2f}  {(p.summary or p.title or '')[:40]}")
print(f"seeded {len(pts) + 2} points → {DB}")
