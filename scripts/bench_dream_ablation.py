"""Phase 76.3 — dreams ON vs OFF, measured (pre-registered in ROADMAP 76.3): does the dream change recall, and what
does it cost in context tokens per question?

Arms on two corpora, each built the way its bench builds it today (dreams OFF):
  relational  arm F engine on the sealed relational corpus (bench_relational.build_engine) — Hit@12 on the 60 questions,
              context truth, context TOKENS per question (len(context) // 4)
  truth       a clone of the live DB (bench_recall_truth.clone_live) — CONTEXT truth on the 17 queries, tokens per query
Then ONE full dream is applied to the same engine (`engine.dream()` — the production entry point; nano OFF so the
structural effect is measured, not the summariser's prose) and the same measurements repeat: OFF vs ON, paired per
question. Optional `--budget S` / `--region` measure the budgeted dream instead of the unbudgeted one.
Decision rule (pre-registered): dreams stay on the default path only if recall is unchanged (paired CI on Hit / truth
including 0) AND tokens per question fall by a reported x%; otherwise they leave the default path and the number says why.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from _bench_paths import guard_scratch, throwaway_db, write_versioned  # noqa: E402
import bench_relational as br  # noqa: E402
from bench_recall_truth import _present, clone_live  # noqa: E402
from hmgfu.agent import AgentEngine  # noqa: E402
from hmgfu.retrieve import build_llm_context, make_query_point, retrieve_memory, user_fact_question  # noqa: E402
from hmgfu.utterance import past_cue  # noqa: E402


def measure_relational(e, id_map, corpus) -> list:
    rows = []
    for qd in corpus["questions"]:
        gold = {id_map[g] for g in qd["gold"]}
        q = make_query_point(qd["text"], e.embed, e.sensitizer)
        got = br.retrieve_for("f", e, q)
        ctx = br.context_for("f", e, q, got, qd["text"])
        rows.append({"id": qd["id"], "hit": gold <= {r.point.id for r in got}, "ctx_truth": bool(_present(ctx, qd["truth"])) if qd["truth"] else None,
                     "tokens": len(ctx) // 4, "macros_in_ctx": ctx.count("Pattern over")})
    return rows


def measure_truth(e, cases) -> list:
    rows = []
    for c in cases:
        for qtext in c["queries"]:
            q, retrieved, _ = e.retrieve(qtext, limit=e.settings.get("retrieval_limit"))
            canonical = e.facts.render_lines() + (e.facts.render_history_lines() if past_cue(qtext) else [])
            ctx, _ = build_llm_context(q, e.graph, retrieved=retrieved, token_budget=e.settings.get("token_budget"), canonical=canonical,
                                       superseded=e.facts.superseded_values(), reverted=e.facts.reverted_values(),
                                       echo_free=user_fact_question(q, e.facts))
            rows.append({"id": c["id"], "text": qtext, "ctx_truth": bool(_present(ctx, c["truth"])) and not _present(ctx, c.get("stale", [])),
                         "tokens": len(ctx) // 4, "macros_in_ctx": ctx.count("Pattern over")})
    return rows


def paired(a: list, b: list, key: str):
    from bench_relational import paired_ci
    return paired_ci([float(x[key]) for x in b], [float(x[key]) for x in a])   # ON − OFF


def summarise(name: str, off: list, on: list, report) -> dict:
    tok_off = statistics.mean(r["tokens"] for r in off); tok_on = statistics.mean(r["tokens"] for r in on)
    out = {"n": len(off), "tokens_off": round(tok_off, 1), "tokens_on": round(tok_on, 1),
           "tokens_delta_pct": round(100.0 * (tok_on - tok_off) / max(1.0, tok_off), 1),
           "macros_in_ctx_off": sum(r["macros_in_ctx"] for r in off), "macros_in_ctx_on": sum(r["macros_in_ctx"] for r in on),
           "dream": report.summary}
    for key in ("hit", "ctx_truth"):
        if key in off[0] and off[0][key] is not None:
            a = [r for r in off if r[key] is not None]; b = [r for r in on if r[key] is not None]
            out[f"{key}_off"] = round(statistics.mean(r[key] for r in a), 3); out[f"{key}_on"] = round(statistics.mean(r[key] for r in b), 3)
            out[f"{key}_on_minus_off_ci"] = paired(a, b, key)
    print(f"[dream:{name}] " + " · ".join(f"{k} {v}" for k, v in out.items() if k != "dream") + f"\n   dream: {report.summary[:200]}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=0, help="dream_budget_s for the ON arm, whole seconds (0 = unbudgeted)")
    ap.add_argument("--region", action="store_true", help="dream_region_only for the ON arm")
    ap.add_argument("--only", default="relational,truth")
    args = ap.parse_args()
    t0 = time.time()
    results = {"budget_s": args.budget, "region_only": args.region}
    if "relational" in args.only:
        corpus = json.load(open(br.SET, encoding="utf-8"))
        e, id_map, _ = br.build_engine("dream_abl", corpus)
        e.settings.set("nano_dream_enabled", False); e.settings.set("dream_budget_s", args.budget); e.settings.set("dream_region_only", args.region)
        off = measure_relational(e, id_map, corpus)
        report = e.dream()
        on = measure_relational(e, id_map, corpus)
        results["relational"] = summarise("relational", off, on, report)
        e.graph.close()
    if "truth" in args.only:
        clone = throwaway_db("bench_dream_truth_clone.db")
        clone_live(clone); guard_scratch(clone)
        e = AgentEngine(db_path=clone)
        e.sensitizer.enabled = False
        for k, v in {"grader_enabled": False, "tail_async": False, "nano_dream_enabled": False, "dream_budget_s": args.budget, "dream_region_only": args.region}.items():
            e.settings.set(k, v)
        cases = json.load(open(os.path.join(ROOT, "scripts", "truth_set.json"), encoding="utf-8"))["cases"]
        off = measure_truth(e, cases)
        report = e.dream()
        on = measure_truth(e, cases)
        results["truth"] = summarise("truth", off, on, report)
        e.graph.close()
    results["elapsed_s"] = round(time.time() - t0, 1)
    print("versioned:", write_versioned("dream_ablation", results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
