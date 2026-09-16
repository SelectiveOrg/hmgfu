"""Phase 90.A — autopsy of the write side on the Phase 88 sample (DEV; nothing here touches a reserved verdict).

Sampling rule, fixed before reading (docs/PROPOSAL_PHASE90_DIAGNOSTIC_CYCLE.md §90.A): the Phase 88 items are qi 40–79 of the five
LongMemEval categories; their USER turns are pooled per category and 4 are drawn per category — the longest, the shortest and two at
random with seed 20260907 — 20 calls; plus the two live DEV cases (a synthetic URL stands in for the user's private link). Each turn
runs through the production write path exactly as the harness/tail does — regex `facts.apply_all`, then the span extractor with the
same filters `fact_spans.apply_spans` applies — with every intermediate list recorded, and is classified with the closed list:
  nothing_memorable · duplicate · legitimate_outside_profile_contract · extraction_failure · correct_rejection · incorrect_rejection ·
  persistence_failure · insufficient_evidence
The classification is the author's, from the recorded path, and is printed with the evidence so it can be disputed.

Gap declared (not papered over): the Phase 88 artefacts do not say WHICH three user turns produced the three ledger writes
(`INGEST_COST` is an aggregate); finding them means re-running the extractor over all 1,691 user turns (~20 min GPU) — offered as
an option, not done here. Throwaway DB only (clone of the live DB under scratch/, guarded)."""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _bench_paths import SCRATCH, write_versioned  # noqa: E402
from bench_longmemeval_e2 import DATA, session_turns  # noqa: E402
from bench_recall_truth import clone_live  # noqa: E402
from hmgfu.agent import AgentEngine  # noqa: E402

CATS = ["knowledge-update", "multi-session", "single-session-user", "temporal-reasoning", "single-session-assistant"]
SEED = 20260907
LIVE_CASES = [  # the two real DEV cases from the 2026-09-07 session analysis, private values replaced by synthetic equivalents
    {"id": "live_updated_link", "text": "heres the updated link: http://198.51.100.7/ui/sharing/0123456789abcdef0123456789abcdef",
     "expect": "asset.car_location_link should move to the new URL (the previous link was the car location link)"},
    {"id": "live_working_on_hmg", "text": "we are actually working on HMG, this memory system of yours",
     "expect": "project.main should become HMG (a correction of the stale 'java project' macro)"},
]


def sample_turns(data) -> list:
    by_cat = {}
    for item in data:
        cat = "abstention" if str(item.get("question_id", "")).endswith("_abs") else item["question_type"]
        by_cat.setdefault(cat, []).append(item)
    rng = random.Random(SEED)
    out = []
    for cat in CATS:
        items = by_cat.get(cat, [])[40:80]
        pool = []
        for qi, q in enumerate(items, start=40):
            for iso, human, role, txt, _ in session_turns(q):
                if role == "user" and txt.strip():
                    pool.append({"cat": cat, "qi": qi, "iso": iso, "text": txt})
        if not pool:
            continue
        by_len = sorted(pool, key=lambda t: len(t["text"]))
        chosen = [by_len[-1], by_len[0]]
        rest = [t for t in pool if t is not by_len[-1] and t is not by_len[0]]
        chosen += rng.sample(rest, min(2, len(rest)))
        for i, t in enumerate(chosen):
            t["id"] = f"{cat[:2]}{t['qi']}_{['longest', 'shortest', 'rand1', 'rand2'][i]}"
        out += chosen
    return out


def trace_write_path(engine, text: str, extractor) -> dict:
    """The production write path with every step recorded: regex → declarative clauses → third-party filter → extractor → gates."""
    from hmgfu.facts import name_value_ok
    from hmgfu.fact_spans import base_slot
    from hmgfu.utterance import declarative_clauses, valid_from_of
    from hmgfu.value_gate import third_party_sentence
    rec = {"text": text[:400], "chars": len(text)}
    before = {r["key"]: r["value"] for r in engine.facts.active()}
    regex_changes = engine.facts.apply_all(text, "user_explicit")
    rec["regex_writes"] = [{"key": c.get("key"), "value": str(c.get("value"))[:60], "op": c.get("op")} for c in regex_changes if c.get("key")]
    clauses = declarative_clauses(text)
    rec["declarative_clauses"] = len(clauses)
    kept = [c["text"] for c in clauses if not third_party_sentence(c["text"])]
    rec["third_party_dropped"] = len(clauses) - len(kept)
    decl = " ".join(kept)
    rec["declarative_chars"] = len(decl)
    rec["valid_from"] = valid_from_of(text)
    if not decl.strip():
        rec["extractor"] = "not called (no declarative first-person sentence)"
        rec["after_writes"] = []
        return rec
    t0 = time.perf_counter()
    try:
        raw = extractor(decl)
        rec["extractor_error"] = None
    except Exception as exc:
        raw, rec["extractor_error"] = [], f"{type(exc).__name__}: {exc}"[:160]
    rec["extractor_s"] = round(time.perf_counter() - t0, 2)
    rec["extractor_raw"] = [{"key": d.get("key"), "value": str(d.get("value"))[:60]} for d in raw][:8]
    skip_bases = {base_slot(c["key"]) for c in regex_changes if c.get("key")}
    filt = []
    for d in raw:
        why = None
        if base_slot(d["key"]) in skip_bases:
            why = "slot family already written by the regex this message"
        elif not name_value_ok(d["key"], d["value"]):
            why = "name-shape gate"
        filt.append({"key": d.get("key"), "value": str(d.get("value"))[:60], "dropped": why})
    rec["extractor_filtered"] = filt[:8]
    writes = []
    for d in [x for x in raw if base_slot(x["key"]) not in skip_bases and name_value_ok(x["key"], x["value"])]:
        if rec["valid_from"]:
            d["valid_from"] = rec["valid_from"]
        ch = engine.facts._apply_one(d, decl, "user_explicit")
        writes.append({"key": d.get("key"), "value": str(d.get("value"))[:60], "stored": bool(ch),
                       "reason_if_not": None if ch else "store rejected (value gate / same value / modality)"})
    rec["after_writes"] = writes
    after = {r["key"]: r["value"] for r in engine.facts.active()}
    rec["ledger_delta"] = {k: str(after[k])[:60] for k in after if before.get(k) != after.get(k)}
    return rec


def classify(rec: dict) -> str:
    if rec.get("ledger_delta"):
        return "written (see delta)"
    if rec.get("extractor_error"):
        return "extraction_failure"
    if rec.get("extractor") and "not called" in rec["extractor"]:
        return "nothing_memorable" if rec["chars"] < 120 or rec["third_party_dropped"] == 0 else "insufficient_evidence"
    raw = rec.get("extractor_raw") or []
    if not raw:
        return "nothing_memorable" if rec["declarative_chars"] < 200 else "insufficient_evidence"
    if any(f.get("dropped") == "slot family already written by the regex this message" for f in rec.get("extractor_filtered", [])):
        return "duplicate"
    if any(w.get("stored") is False for w in rec.get("after_writes", [])):
        return "correct_rejection_or_persistence_failure (inspect)"
    return "legitimate_outside_profile_contract"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", default="chat", help="span-extractor role, as Phase 88's candidate (chat) or production's nano")
    ap.add_argument("--db", default=None)
    ap.add_argument("--only-live", action="store_true", help="run only the two live DEV cases")
    args = ap.parse_args()
    os.makedirs(SCRATCH, exist_ok=True)
    clone = os.path.join(SCRATCH, f"write_autopsy_{os.getpid()}.db"); clone_live(clone, args.db)
    engine = AgentEngine(db_path=clone)
    for key, val in {"grader_enabled": False, "tail_async": False, "full_dream_every_n_turns": 0, "mini_dream_every_n_turns": 0}.items():
        engine.settings.set(key, val)
    engine.facts.open_slot_regex_writes = bool(engine.settings.get("open_slot_regex_writes"))
    engine.facts.use_mapper = engine.settings.get("fact_mapper_mode") == "fallback"
    from hmgfu.fact_spans import registry_span_extractor
    extractor = registry_span_extractor(engine.registry, args.role)
    turns = [] if args.only_live else sample_turns(json.load(open(DATA, encoding="utf-8")))
    turns += [{"cat": "LIVE-DEV", "qi": None, "id": c["id"], "text": c["text"], "expect": c["expect"]} for c in LIVE_CASES]
    print(f"WRITE AUTOPSY — {len(turns)} turns (rule: longest/shortest/2 random per category, seed {SEED}, items qi 40–79) + {len(LIVE_CASES)} live DEV cases · "
          f"extractor role {args.role} · mapper mode {engine.settings.get('fact_mapper_mode')} · open slots {engine.settings.get('open_slot_regex_writes')}")
    rows = []
    for t in turns:
        rec = trace_write_path(engine, t["text"], extractor)
        rec.update({"id": t["id"], "cat": t["cat"], "qi": t["qi"], "expect": t.get("expect")})
        rec["class"] = classify(rec)
        rows.append(rec)
        print(f"\n[{rec['class']}] {t['id']} ({t['cat']}, {rec['chars']} chars) {t['text'][:90]!r}")
        print(f"   regex writes {rec['regex_writes']} · clauses {rec['declarative_clauses']} (third-party dropped {rec['third_party_dropped']}) · "
              f"extractor {rec.get('extractor') or ('%.1fs' % rec.get('extractor_s', 0))} raw {rec.get('extractor_raw')} · filtered {[(f['key'], f['dropped']) for f in rec.get('extractor_filtered', []) if f['dropped']]}")
        print(f"   after-extractor writes {rec['after_writes']} · ledger delta {rec.get('ledger_delta')}")
        if t.get("expect"):
            print(f"   EXPECTED: {t['expect']}")
    from collections import Counter
    print("\nCLASSES:", dict(Counter(r["class"] for r in rows)))
    print("GAP: the Phase 88 artefacts do not identify the 3 writing turns; reproducing them = 1,691 extractor calls (~20 min GPU) — not run.")
    print("versioned:", write_versioned("write_autopsy", {"rows": rows, "seed": SEED, "role": args.role}))
    engine.graph.close()
    try:
        os.remove(clone)
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
