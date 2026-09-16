"""Phase 79.1 — routing AGREEMENT on the sealed set (`scripts/oracles/routing_v1.json`).

`--record` calls the production router ONCE per turn on the reference model (the chat model, gemma4:12b) and stores its
route as `reference` inside the oracle file (committed before any candidate is measured). Without `--record`, the same call
is made for a candidate — `--model <ollama model>` (the router ROLE on a throwaway clone; the chat model is untouched) or
`--bypass` (79.3: the deterministic pre-router; turns it does not claim count as "fell through", never as disagreement) —
and compared with the reference per turn: DECISION agreement = all of {action_requested, requested_tools (as a set),
conversation_act, needs_memory} equal; per-field agreement for those plus freshness, feedback_polarity, directive kind.
Same prompt, catalog (the clone engine's live tool registry), standing directives (the clone's) and schema as production;
learned routing exemplars fixed to NONE so the measurement does not depend on the live route memory. Route p50/p95 reported.
Versioned output; the live DB is only cloned.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from _bench_paths import SCRATCH, write_versioned  # noqa: E402
from bench_recall_truth import clone_live  # noqa: E402
from hmgfu import config  # noqa: E402
from hmgfu.agent import AgentEngine  # noqa: E402
from hmgfu.runtime_context import RuntimeContext  # noqa: E402
from hmgfu.sensitizer import parse_nano_json  # noqa: E402
from hmgfu.turn_router import catalog_json, classify_turn, router_schema  # noqa: E402

ORACLE = os.path.join(ROOT, "scripts", "oracles", "routing_v1.json")
DECISION = ("action_requested", "requested_tools", "conversation_act", "needs_memory")
FIELDS = DECISION + ("freshness", "feedback_polarity", "directive_kind")


def normalise(route: dict) -> dict:
    r = route or {}
    d = r.get("directive")
    return {"action_requested": bool(r.get("action_requested")),
            "requested_tools": sorted({str(t) for t in (r.get("requested_tools") or [])}),
            "conversation_act": str(r.get("conversation_act") or ""),
            "needs_memory": bool(r.get("needs_memory", True)),
            "freshness": str(r.get("freshness") or "none"),
            "feedback_polarity": r.get("feedback_polarity") or None,
            "directive_kind": (d.get("kind") if isinstance(d, dict) else None)}


def admits(entry: dict, route: dict) -> bool:
    """81.4: one author-adjudicated admissible entry vs a normalised route — absent key = wildcard, list = any-of,
    requested_tools as a set (order-free)."""
    for key, want in entry.items():
        got = route.get(key)
        if key == "requested_tools":
            if sorted({str(t) for t in (want or [])}) != sorted({str(t) for t in (got or [])}):
                return False
        elif isinstance(want, list):
            if got not in want:
                return False
        elif got != want:
            return False
    return True


def judge_admissible(route: dict, admissible: list) -> dict:
    """Decision = some entry admits the route; per field = the route's value appears in some entry (wildcards admit)."""
    per = {}
    for f in FIELDS:
        vals = [e[f] for e in admissible if f in e]
        per[f] = True if not vals else any(admits({f: v}, route) for v in vals)
    return {"decision": any(admits(e, route) for e in admissible), "agree": per}


def route_once(engine, text: str, runtime_prompt: str, catalog_text: str, directives_text: str, schema: dict) -> tuple:
    t0 = time.perf_counter()
    out = classify_turn(lambda role, msgs, **kw: engine.registry.chat_for_role(role, msgs, **kw)["content"],
                        parse_nano_json, text, runtime_prompt, catalog_text, directives_text, "", schema)
    return normalise(out), (time.perf_counter() - t0) * 1000.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", action="store_true", help="record the REFERENCE routes (reference model = the chat model)")
    ap.add_argument("--model", default=None, help="candidate router model (router role on the clone)")
    ap.add_argument("--bypass", action="store_true", help="79.3: measure the deterministic pre-router against the reference")
    ap.add_argument("--knn", action="store_true", help="89.2: the nearest-exemplar router alone (unclaimed turns = fell through)")
    ap.add_argument("--knn-combined", action="store_true", help="89.2: kNN first, the model router on the turns it does not claim")
    ap.add_argument("--knn-k", type=int, default=3); ap.add_argument("--knn-min-sim", type=float, default=0.80)
    ap.add_argument("--only", default=None, help="comma-separated turn ids")
    ap.add_argument("--db", default=None, help="source DB to clone (default: live)")
    ap.add_argument("--oracle", default=ORACLE, help="81.4: a routing set (reference) or a reserved DECISION set (admissible)")
    args = ap.parse_args()
    oracle = json.load(open(args.oracle, encoding="utf-8"))
    turns = oracle["turns"]
    admissible_set = any("admissible" in t for t in turns)
    if admissible_set and args.record:
        print("FAIL: --record is refused on an author-adjudicated decision set (its labels are not a model's to overwrite)"); return 2
    if args.only:
        keep = set(args.only.split(","))
        turns = [t for t in turns if t["id"] in keep]
    os.makedirs(SCRATCH, exist_ok=True)
    clone = os.path.join(SCRATCH, f"routing_agreement_clone_{os.getpid()}.db")   # one clone per run (candidates may run concurrently)
    clone_live(clone, args.db)
    engine = AgentEngine(db_path=clone)
    for key, val in {"grader_enabled": False, "tail_async": False, "full_dream_every_n_turns": 0,
                     "mini_dream_every_n_turns": 0, "runbooks_enabled": False, "prospective_enabled": False}.items():
        engine.settings.set(key, val)
    if args.model:
        engine.settings.set("router_model", args.model)
    router_model = engine.settings.get("router_model")
    if not engine.client.available():
        print("FAIL: Ollama unreachable"); return 1
    catalog = engine.sensitizer._action_catalog()
    catalog_text = catalog_json(catalog)
    directives_text = engine.sensitizer._directives_text()
    schema = router_schema(list(catalog))
    runtime_prompt = RuntimeContext.capture().prompt_block()
    rows, lat = [], []
    if args.bypass:
        from hmgfu.pre_router import pre_route
    knn_base = None
    if args.knn or args.knn_combined:
        from hmgfu.knn_router import ExemplarBase, knn_route
        knn_base = ExemplarBase(engine.embed, str(engine.settings.get("embed_model") or ""))
    knn_claimed = 0
    for i, t in enumerate(turns):
        ref = t.get("reference")
        if args.record:
            route, ms = route_once(engine, t["text"], runtime_prompt, catalog_text, directives_text, schema)
            t["reference"] = route; t["reference_model"] = router_model; t["reference_ms"] = round(ms, 1)
            lat.append(ms)
            rows.append({"id": t["id"], "class": t["class"], "route": route, "ms": round(ms, 1)})
        else:
            if ref is None and not t.get("admissible"):
                print(f"FAIL: turn {t['id']} has no reference — run --record first"); return 1
            if args.bypass:
                t0 = time.perf_counter()
                got = pre_route(t["text"], list(catalog), engine.facts)
                ms = (time.perf_counter() - t0) * 1000.0
                if got is None:
                    rows.append({"id": t["id"], "class": t["class"], "claimed": False, "ms": round(ms, 2)}); continue
                route = normalise(got)
            elif knn_base is not None:
                t0 = time.perf_counter()
                got = knn_route(engine.embed(t["text"]), knn_base, k=args.knn_k, min_sim=args.knn_min_sim, exclude_text=t["text"])   # leave-one-out on a base set
                ms = (time.perf_counter() - t0) * 1000.0
                if got is None and not args.knn_combined:
                    rows.append({"id": t["id"], "class": t["class"], "claimed": False, "ms": round(ms, 2)}); continue
                if got is not None:
                    knn_claimed += 1
                    route = normalise(got); route["_source"] = "knn"
                else:
                    route, ms = route_once(engine, t["text"], runtime_prompt, catalog_text, directives_text, schema)
                    route["_source"] = "model"
            else:
                route, ms = route_once(engine, t["text"], runtime_prompt, catalog_text, directives_text, schema)
            lat.append(ms)
            if t.get("admissible"):
                j = judge_admissible(route, t["admissible"])
                rows.append({"id": t["id"], "class": t["class"], "claimed": True, "route": route, "admissible": t["admissible"],
                             "agree": j["agree"], "decision": j["decision"], "ms": round(ms, 1)})
                continue
            agree = {f: route[f] == ref[f] for f in FIELDS}
            rows.append({"id": t["id"], "class": t["class"], "claimed": True, "route": route, "reference": ref, "agree": agree,
                         "decision": all(agree[f] for f in DECISION), "ms": round(ms, 1)})
        if (i + 1) % 20 == 0:
            print(f"   {i + 1}/{len(turns)}")
    if args.record:
        oracle["reference_model"] = router_model
        oracle["recorded_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        json.dump(oracle, open(args.oracle, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        sha = hashlib.md5(open(args.oracle, "rb").read()).hexdigest()[:12]
        print(f"RECORDED reference routes for {len(rows)} turns on {router_model} · route p50 {statistics.median(lat):.0f} ms · "
              f"p95 {sorted(lat)[int(0.95 * (len(lat) - 1))]:.0f} ms · oracle md5 {sha}")
        print("versioned:", write_versioned("routing_reference", {"model": router_model, "rows": rows}))
        return 0
    claimed = [r for r in rows if r.get("claimed")]
    n = len(claimed)
    label = ("bypass" if args.bypass else (f"knn(k={args.knn_k},min_sim={args.knn_min_sim})" if args.knn else
             (f"knn+model(k={args.knn_k},min_sim={args.knn_min_sim})" if args.knn_combined else f"model={router_model}"))) + (" vs AUTHOR-ADMISSIBLE" if admissible_set else " vs reference")
    if knn_base is not None:
        kc = [r for r in rows if r.get("claimed") and (r.get("route") or {}).get("_source") == "knn"]
        print(f"  kNN claimed {knn_claimed}/{len(rows)} · correct on its claims {sum(1 for r in kc if r['decision'])}/{len(kc)}")
    label += f" [{os.path.basename(args.oracle)} md5 {hashlib.md5(open(args.oracle, 'rb').read()).hexdigest()[:12]}]"
    dec = sum(1 for r in claimed if r["decision"]) / n if n else 0.0
    per = {f: (sum(1 for r in claimed if r["agree"][f]) / n if n else 0.0) for f in FIELDS}
    print(f"\nROUTING AGREEMENT [{label}] claimed {n}/{len(rows)} · DECISION {dec:.3f} · " +
          " · ".join(f"{f} {per[f]:.3f}" for f in FIELDS) +
          (f" · route p50 {statistics.median(lat):.0f} ms p95 {sorted(lat)[int(0.95 * (len(lat) - 1))]:.0f} ms" if lat else ""))
    by_class = {}
    for r in claimed:
        by_class.setdefault(r["class"], []).append(r["decision"])
    print("  by class: " + " · ".join(f"{c} {sum(v)}/{len(v)}" for c, v in sorted(by_class.items())))
    for r in claimed:
        if not r["decision"]:
            if "admissible" in r:
                got = {f: r["route"][f] for f in DECISION + ("directive_kind",)}
                print(f"  [NOT ADMISSIBLE] {r['id']} {r['class']:>18} got {got} · admissible {r['admissible']}")
                continue
            diff = {f: (r["route"][f], r["reference"][f]) for f in DECISION if not r["agree"][f]}
            print(f"  [DISAGREE] {r['id']} {r['class']:>18} {diff}")
    print("versioned:", write_versioned("routing_agreement", {"label": label, "decision": dec, "per_field": per, "claimed": n,
                                                             "total": len(rows), "rows": rows}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
