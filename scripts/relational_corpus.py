"""Phase 74.0/74.1 — a DETERMINISTIC synthetic multi-session diary with gold ids, for the relational bench.

Why synthetic: the relational claim ("the memory lives in the interval") needs questions whose answer is NOT the
semantically closest message — the answer is the message RELATED by time, cause or entity to the one the question
names. Only a corpus built from an explicit event graph gives exact gold ids for that. The diary is written by one
first-person user (PT/EN mixed, like the real one), ~40 sessions over ~6 months, and contains:

  * projects with start/end and reasons, people met while working on them, places, tools;
  * dated events linked by cause ("started X because Y") and co-occurrence ("met Z while working on X");
  * explicit corrections ("actually my favourite drink is …") and IMPLICIT revisions (a later statement changes a value
    without saying it is a change — STALE-style);
  * independent facts that must SURVIVE every revision (non-interference);
  * semantically close distractors at the wrong time.

Question families (each with gold message ids, and where relevant the CURRENT truth values and STALE values):
  relational · temporal (before/after) · implicit_revision · non_interference · distractor
Everything is derived from one seed; the sealed JSON is committed before the harness runs (Rule 12).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import random
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PEOPLE = ["Rui", "Marta", "Celso", "Inês", "Dário", "Yara", "Nelson", "Sónia"]
PROJECTS = [("Atlas", "a data pipeline for the clinic"), ("Bolt", "the delivery app"), ("Cora", "the school website"),
            ("Delta", "a farm sensor network"), ("Echo", "the podcast studio")]
PLACES = ["Valencia", "Matola", "Aveiro", "Nampula", "Quelimane", "Inhambane"]
TOOLS = ["Rust", "Go", "Python", "TypeScript", "Kotlin"]
DRINKS = ["ginger tea", "hibiscus tea", "black coffee", "maheu", "passion fruit juice"]
COLORS = ["teal", "amber", "chartreuse", "burgundy", "navy"]
FOODS = ["matapa", "xima com caril", "peri-peri chicken", "badjia", "mucapata"]


def _iso(d: dt.date, hour: int) -> str:
    return dt.datetime(d.year, d.month, d.day, hour, 0, 0, tzinfo=dt.timezone.utc).isoformat()


def build(seed: int = 74) -> dict:
    rng = random.Random(seed)
    start = dt.date(2026, 2, 2)
    messages, questions = [], []
    counter = [0]

    def say(day: int, text: str, kind: str, tags: dict | None = None) -> str:
        counter[0] += 1
        mid = f"m{counter[0]:03d}"
        d = start + dt.timedelta(days=day)
        messages.append({"id": mid, "session": f"s{day // 4:02d}", "day": day, "ts": _iso(d, 9 + (counter[0] % 9)),
                         "text": text, "kind": kind, **(tags or {})})
        return mid

    def ask(family: str, text: str, gold: list, truth=None, stale=None, note: str = ""):
        questions.append({"id": f"q{len(questions) + 1:03d}", "family": family, "text": text, "gold": gold,
                          "truth": truth or [], "stale": stale or [], "note": note})

    # --- projects: start (with a reason), a person met while on it, a place, a tool; sequential over ~6 months
    projects = rng.sample(PROJECTS, 4)
    people = rng.sample(PEOPLE, 8)
    places = rng.sample(PLACES, 4)
    tools = rng.sample(TOOLS, 4)
    day = 0
    project_log = []
    for i, (name, what) in enumerate(projects):
        reason = ["the old spreadsheet kept breaking", "a client asked for it", "my brother needed it for his shop",
                  "the school had no site at all"][i]
        m_start = say(day, f"I started project {name}, {what}, because {reason}.", "event", {"project": name})
        m_tool = say(day + 3, f"For {name} I am writing everything in {tools[i]}.", "fact", {"project": name})
        m_met = say(day + 9, f"Met {people[2 * i]} today while working on {name}; they run a shop in {places[i]}.",
                    "event", {"project": name, "person": people[2 * i], "place": places[i]})
        m_other = say(day + 14, f"{people[2 * i + 1]} joined me on {name} to help with the testing.", "event",
                      {"project": name, "person": people[2 * i + 1]})
        m_blocker = say(day + 20, f"{name} got stuck for a week because the {['printer', 'server', 'API key', 'sensor']
                                     [i]} failed.", "event", {"project": name})
        m_done = say(day + 34, f"Finished {name} today. Next I want something completely different.", "event",
                     {"project": name})
        project_log.append(dict(name=name, what=what, tool=tools[i], start=m_start, tool_msg=m_tool, met=m_met,
                                person=people[2 * i], helper=people[2 * i + 1], place=places[i], blocker=m_blocker,
                                done=m_done, day=day, other=m_other))
        # distractor: the same person mentioned in an unrelated context on a different project period
        say(day + 30, f"Had lunch with {people[2 * i]} — we talked about football, nothing about work.", "distractor",
            {"person": people[2 * i]})
        day += 40

    # --- preferences with explicit correction, implicit revision, and independent facts
    drinks = rng.sample(DRINKS, 3); colors = rng.sample(COLORS, 3); foods = rng.sample(FOODS, 2); city = rng.sample(PLACES, 2)
    m_d1 = say(5, f"My favorite drink is {drinks[0]}.", "fact", {"slot": "drink"})
    m_c1 = say(6, f"A minha cor favorita é {colors[0]}.", "fact", {"slot": "color"})
    m_food = say(7, f"My favorite food is {foods[0]}.", "fact", {"slot": "food"})              # independent, never revised
    m_live1 = say(8, f"I live in {city[0]}.", "fact", {"slot": "city"})
    m_d2 = say(61, f"Actually my favorite drink is {drinks[1]} now, not {drinks[0]}.", "correction", {"slot": "drink"})
    m_c2 = say(95, f"Comprei tinta {colors[1]} para o quarto — é a minha cor favorita.", "implicit", {"slot": "color"})
    m_live2 = say(130, f"Since March I live in {city[1]}; the commute to {city[0]} was killing me.", "implicit", {"slot": "city"})
    m_d3 = say(150, f"Ordered {drinks[2]} again — it has been my favorite drink for weeks now.", "implicit", {"slot": "drink"})
    # distractors for preferences: other people's preferences, hypotheticals
    say(70, f"{people[3]} says their favorite drink is {drinks[0]}.", "distractor")
    say(100, f"If my favorite color were {colors[2]} I would repaint the car.", "distractor")
    say(140, f"My sister's favorite food is {foods[1]}.", "distractor")

    # --- filler: ~120 unrelated first-person diary lines spread over the same days, so k matters (distractor mass)
    topics = ["Went for a run along the bay this morning.", "Fixed the kitchen tap, finally.",
              "Watched a documentary about deep-sea fish.", "Called my aunt; she is well.",
              "The power went out for two hours tonight.", "Tried a new bakery near the office.",
              "Read forty pages of a history book before bed.", "Cleaned the balcony and repotted the basil.",
              "Traffic was terrible on the way back.", "Backed up my photos to the external drive.",
              "Fui ao mercado comprar peixe fresco.", "Choveu toda a tarde, fiquei em casa.",
              "Reorganizei a estante da sala.", "Tomei café com um vizinho novo.",
              "Ajustei os travões da bicicleta.", "Assisti ao jogo com amigos, empate.",
              "Planted tomatoes in the back garden.", "The cat next door keeps visiting.",
              "Renewed my library card.", "Long walk after dinner, clear sky."]
    for k in range(120):
        d = (k * 13) % 155
        say(d, topics[k % len(topics)] + ("" if k < len(topics) else f" (day {d})"), "filler")
    messages.sort(key=lambda m: (m["day"], m["id"]))

    # ---------------- questions ----------------
    for p in project_log:
        ask("relational", f"Who helped me test {p['name']}?", [p["other"]], truth=[p["helper"]])
        ask("relational", f"Which place is linked to project {p['name']}?", [p["met"]], truth=[p["place"]],
            note="the place appears only in the meeting message")
        ask("temporal", f"O que bloqueou o {p['name']} antes de terminar?", [p["blocker"]],
            truth=[["printer", "server", "API key", "sensor"][projects.index((p["name"], p["what"]))]])
        ask("relational", f"What project was I working on when I met {p['person']}?", [p["start"], p["met"]],
            truth=[p["name"]], note="gold = the project start + the meeting; the meeting alone names it too")
        ask("relational", f"Why did I start {p['name']}?", [p["start"]], truth=[p["name"]])
        ask("relational", f"Which language was I using when {p['helper']} joined me?", [p["tool_msg"], p["other"]],
            truth=[p["tool"]], note="answer lives in a DIFFERENT message than the one naming the helper")
        ask("relational", f"Where does {p['person']} run their shop?", [p["met"]], truth=[p["place"]])
        ask("temporal", f"What blocked {p['name']} before it was finished?", [p["blocker"]],
            truth=[["printer", "server", "API key", "sensor"][projects.index((p["name"], p["what"]))]])
        ask("relational", f"Em que projecto estava quando conheci {p['person']}?", [p["start"], p["met"]], truth=[p["name"]])
    # temporal ordering across projects
    for a, b in zip(project_log, project_log[1:]):
        ask("temporal", f"What did I work on right before {b['name']}?", [a["start"], a["done"]], truth=[a["name"]])
        ask("temporal", f"Which project came after {a['name']}?", [b["start"]], truth=[b["name"]])
    ask("temporal", f"What was the first project I started this year?", [project_log[0]["start"]], truth=[project_log[0]["name"]])
    ask("temporal", f"What was the last project I finished?", [project_log[-1]["done"]], truth=[project_log[-1]["name"]])
    # implicit revisions: the CURRENT value after an unannounced change; stale = the earlier values
    ask("implicit_revision", "What is my favorite drink?", [m_d3], truth=[drinks[2]], stale=[drinks[0], drinks[1]])
    ask("implicit_revision", "Qual é a minha cor favorita?", [m_c2], truth=[colors[1]], stale=[colors[0]])
    ask("implicit_revision", "Where do I live?", [m_live2], truth=[city[1]], stale=[city[0]])
    ask("implicit_revision", "What is my favourite colour?", [m_c2], truth=[colors[1]], stale=[colors[0]])
    ask("implicit_revision", "Which drink do I like most these days?", [m_d3], truth=[drinks[2]], stale=[drinks[0], drinks[1]])
    # temporal before/after on revised slots (history is the answer here — superseded values are CORRECT)
    ask("temporal", f"What was my favorite drink before I switched to {drinks[1]}?", [m_d1], truth=[drinks[0]])
    ask("temporal", "Where did I live before?", [m_live1], truth=[city[0]])
    ask("temporal", "Qual era a minha cor favorita antes?", [m_c1], truth=[colors[0]])
    # non-interference: independent facts must survive every revision around them
    ask("non_interference", "What is my favorite food?", [m_food], truth=[foods[0]], stale=[foods[1]])
    ask("non_interference", "Qual é a minha comida favorita?", [m_food], truth=[foods[0]], stale=[foods[1]])
    ask("non_interference", f"Which language did I use for {project_log[0]['name']}?", [project_log[0]["tool_msg"]],
        truth=[project_log[0]["tool"]])
    ask("non_interference", f"Which language did I use for {project_log[-1]['name']}?", [project_log[-1]["tool_msg"]],
        truth=[project_log[-1]["tool"]])
    # distractor family: the closest text is the wrong one
    ask("distractor", f"What did {people[0]} and I talk about at lunch?", [messages[[m['kind'] for m in messages].index('distractor')]["id"]],
        truth=["football"], note="the lunch message, not the project meeting")
    ask("distractor", f"Whose favorite drink is {drinks[0]}?", [next(m["id"] for m in messages if m["kind"] == "distractor" and drinks[0] in m["text"])],
        truth=[people[3]], stale=["my"], note="a third person's preference, not the user's")
    ask("distractor", f"Is {colors[2]} my favorite color?", [m_c2], truth=[colors[1]], stale=[colors[2]],
        note="a hypothetical about the user's own color; the current value answers")
    ask("distractor", "What is my sister's favorite food?", [next(m["id"] for m in messages if "sister" in m["text"])],
        truth=[foods[1]], note="the sister's, not the user's")
    return {"_doc": "Phase 74 relational corpus v1 — deterministic (seed %d), sealed before the first run. Every question "
                    "carries GOLD message ids; truth/stale are the CURRENT value / retired values where relevant." % seed,
            "seed": seed, "messages": messages, "questions": questions,
            "families": {f: sum(1 for q in questions if q["family"] == f) for f in
                         ("relational", "temporal", "implicit_revision", "non_interference", "distractor")}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=74)
    ap.add_argument("--out", default=os.path.join(ROOT, "scripts", "oracles", "relational_v1.json"))
    args = ap.parse_args()
    doc = build(args.seed)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1, ensure_ascii=False)
    print(f"messages {len(doc['messages'])} · questions {len(doc['questions'])} · families {doc['families']} → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
