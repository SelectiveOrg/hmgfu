"""Phase 72.5 — write-side precision/coverage on a sealed multilingual set (scripts/oracles/write_set_v1.json).

Each item: {"id", "lang", "text", "expect": {slot: value}} — `expect` is the set of CURRENT first-person facts the
message asserts (empty for questions, quotes, fiction, hypotheticals, past). A fresh FactStore per item.
  precision = asserted (key,value) pairs that are expected / all asserted pairs
  coverage  = expected pairs that were asserted / all expected pairs
Both with a percentile bootstrap 95% CI over items. Errors are listed per item (false writes are the dangerous class).
An optional `<set>.errata.json` (items whose sealed expectation was found inconsistent AFTER sealing) is reported as a SECOND,
clearly-labelled figure; the sealed figure always comes first and the sealed file is never edited.
No production data, no model (regex path only unless --mapper), versioned output (M0.1).
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from _bench_paths import SCRATCH, write_versioned  # noqa: E402
from hmgfu.facts import FactStore  # noqa: E402


SPANS = None       # 84.3: a callable(text) -> dets from the span extractor when --spans is given
OPEN_SLOTS = True  # 84.2: --open-slots off = the regex writes closed slots only
MAPPER = None      # 84.1: a callable(text) -> det | None bound from the production ProviderRegistry when --mapper is given


def bind_production_mapper(role: str):
    """84.1: the SAME mapper production binds (`agent.py`: `registry_mapper(ProviderRegistry(settings, client))`), on a
    throwaway settings DB so the live one is never touched."""
    from hmgfu.ollama_client import OllamaClient
    from hmgfu.providers import ProviderRegistry
    from hmgfu.settings import Settings
    from hmgfu.slots import registry_mapper
    os.makedirs(SCRATCH, exist_ok=True)
    settings = Settings(os.path.join(SCRATCH, f"writeset_settings_{os.getpid()}.db"))
    client = OllamaClient()
    if not client.available():
        raise SystemExit("FAIL: Ollama unreachable — the mapper needs the production model")
    reg = ProviderRegistry(settings, client)
    return registry_mapper(reg, role), settings.get(f"{role}_model") or settings.get("nano_model")


def bind_span_extractor(role: str):
    """84.3: the span-extractor contract on a provider role, same registry construction as production."""
    from hmgfu.fact_spans import registry_span_extractor
    from hmgfu.ollama_client import OllamaClient
    from hmgfu.providers import ProviderRegistry
    from hmgfu.settings import Settings
    os.makedirs(SCRATCH, exist_ok=True)
    settings = Settings(os.path.join(SCRATCH, f"writeset_settings_{os.getpid()}.db"))
    client = OllamaClient()
    if not client.available():
        raise SystemExit("FAIL: Ollama unreachable")
    return registry_span_extractor(ProviderRegistry(settings, client), role), settings.get(f"{role}_model") or settings.get("nano_model")


def run_item(item: dict, expect_override: dict | None = None) -> dict:
    os.makedirs(SCRATCH, exist_ok=True)
    folder = tempfile.mkdtemp(prefix="writeset_", dir=SCRATCH)
    st = FactStore(os.path.join(folder, "f.db"))
    if MAPPER is not None:
        st.bind_mapper(MAPPER)
    st.open_slot_regex_writes = OPEN_SLOTS
    st.use_mapper = SPANS is None
    for prior in item.get("prior", []):
        st.apply_all(prior, "user_explicit")
    before = {f["key"]: f["value"] for f in st.active()}
    changes = st.apply_all(item["text"], "user_explicit")
    if SPANS is not None:                                           # 84.3: the span extractor adds what the regex missed
        from hmgfu.fact_spans import apply_spans
        changes += apply_spans(st, item["text"], "user_explicit", SPANS, skip_keys=[c["key"] for c in changes if c.get("key")],
                               skip_values=[c.get("value") for c in changes if c.get("value")])   # 90.G2, as the tail does
    paths = {c["key"]: c.get("path", "regex") for c in changes if c.get("key")}
    after = {f["key"]: f["value"] for f in st.active()}
    # 91.AA: the temporal row each assertion carries, so a right value with a WRONG DATE is visible
    dated = {a.get("relation"): a.get("valid_from") for a in st.assertions.active()}
    st._db.close()
    asserted = {k: v for k, v in after.items() if before.get(k) != v}
    cleared = {k for k in before if k not in after}
    expected = expect_override if expect_override is not None else item.get("expect", {})
    exp_clear = set(item.get("expect_clear", []))
    tp = sum(1 for k, v in asserted.items() if expected.get(k, "").lower() == (v or "").lower())
    fp = len(asserted) - tp
    fn = sum(1 for k, v in expected.items() if (asserted.get(k) or "").lower() != v.lower())
    clear_ok = exp_clear <= cleared
    want_from = item.get("expect_valid_from") or {}
    bad_dates = {k: {"want": v, "got": dated.get(k)} for k, v in want_from.items() if dated.get(k) != v}
    return {"id": item["id"], "bad_dates": bad_dates, "lang": item.get("lang"), "tp": tp, "fp": fp, "fn": fn, "clear_ok": clear_ok,
            "asserted": asserted, "expected": expected, "paths": paths,
            "false_writes": {k: v for k, v in asserted.items() if expected.get(k, "").lower() != (v or "").lower()},
            "missed": {k: v for k, v in expected.items() if (asserted.get(k) or "").lower() != v.lower()}}


def _ratio(rows, num, den):
    n = sum(r[num] for r in rows); d = sum(r[den[0]] for r in rows) + sum(r[den[1]] for r in rows)
    return n / d if d else 1.0


def bootstrap(rows, num, den, seed=20260905, n=2000):
    rng = random.Random(seed)
    vals = []
    for _ in range(n):
        sample = [rows[rng.randrange(len(rows))] for _ in rows]
        vals.append(_ratio(sample, num, den))
    vals.sort()
    return vals[int(0.025 * n)], vals[int(0.975 * n)]


def _figures(rows):
    precision = _ratio(rows, "tp", ("tp", "fp")); coverage = _ratio(rows, "tp", ("tp", "fn"))
    p_lo, p_hi = bootstrap(rows, "tp", ("tp", "fp")); c_lo, c_hi = bootstrap(rows, "tp", ("tp", "fn"))
    return {"n": len(rows), "precision": precision, "precision_ci": [p_lo, p_hi], "coverage": coverage, "coverage_ci": [c_lo, c_hi],
            "false_writes": sum(r["fp"] for r in rows), "misses": sum(r["fn"] for r in rows)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default=os.path.join(ROOT, "scripts", "oracles", "write_set_v1.json"))
    ap.add_argument("--mapper", nargs="?", const="nano", default=None,
                    help="84.1: bind the PRODUCTION model mapper (role, default nano) — the write side as it runs in production")
    ap.add_argument("--open-slots", choices=["on", "off"], default="on", help="84.2: open-slot regex writes (default on = today)")
    ap.add_argument("--spans", nargs="?", const="nano", default=None, help="84.3: the span-extractor contract (role nano | chat)")
    args = ap.parse_args()
    global MAPPER, OPEN_SLOTS, SPANS
    OPEN_SLOTS = args.open_slots == "on"
    spans_model = None
    if args.spans:
        SPANS, spans_model = bind_span_extractor(args.spans)
        print(f"SPANS ON: role {args.spans} · model {spans_model}")
    mapper_model = None
    if args.mapper:
        MAPPER, mapper_model = bind_production_mapper(args.mapper)
        print(f"MAPPER ON: role {args.mapper} · model {mapper_model}")
    items = json.load(open(args.set, encoding="utf-8"))["items"]
    rows = [run_item(it) for it in items]
    fig = _figures(rows)
    precision, coverage = fig["precision"], fig["coverage"]
    (p_lo, p_hi), (c_lo, c_hi) = fig["precision_ci"], fig["coverage_ci"]
    errata_path = args.set[:-5] + ".errata.json"
    errata = json.load(open(errata_path, encoding="utf-8"))["items"] if os.path.exists(errata_path) else {}
    adjusted = None
    if errata:
        adj_rows = [run_item(it, errata[it["id"]]["expect"]) if it["id"] in errata else r for it, r in zip(items, rows)]
        adjusted = _figures(adj_rows)
    by_lang = {}
    for r in rows:
        b = by_lang.setdefault(r["lang"], {"tp": 0, "fp": 0, "fn": 0})
        for k in ("tp", "fp", "fn"):
            b[k] += r[k]
    for r in rows:
        if r["fp"] or r["fn"] or not r["clear_ok"]:
            print(("FALSE-WRITE " if r["fp"] else "MISS        "), r["id"], "| false:", json.dumps(r["false_writes"], ensure_ascii=False),
                  "| missed:", json.dumps(r["missed"], ensure_ascii=False))
    for r in rows:                                   # 91.AA: a right value with a wrong date
        if r.get("bad_dates"):
            print("WRONG-DATE  ", r["id"], "|", json.dumps(r["bad_dates"], ensure_ascii=False))
    by_path = {"regex": {"tp": 0, "fp": 0}, "mapper": {"tp": 0, "fp": 0}, "spans": {"tp": 0, "fp": 0}}
    for r in rows:
        for k, v in r["asserted"].items():
            ok = r["expected"].get(k, "").lower() == (v or "").lower()
            by_path.setdefault(r["paths"].get(k, "regex"), {"tp": 0, "fp": 0})["tp" if ok else "fp"] += 1
    label = (f"mapper={args.mapper}:{mapper_model}" if args.mapper else (f"spans={args.spans}:{spans_model}" if args.spans else "regex-only")) \
        + (" open-slots off" if not OPEN_SLOTS else "")
    print(f"\nWRITE SET (sealed) [{label}] n={len(rows)} · PRECISION {precision:.3f} [{p_lo:.3f}, {p_hi:.3f}] · COVERAGE {coverage:.3f} [{c_lo:.3f}, {c_hi:.3f}]")
    print("  by path: " + " · ".join(f"{p} tp {c['tp']} fp {c['fp']}" for p, c in by_path.items()))
    if adjusted:
        print(f"WRITE SET (errata-adjusted, {len(errata)} items: {', '.join(sorted(errata))}) · PRECISION {adjusted['precision']:.3f} "
              f"[{adjusted['precision_ci'][0]:.3f}, {adjusted['precision_ci'][1]:.3f}] · COVERAGE {adjusted['coverage']:.3f} "
              f"[{adjusted['coverage_ci'][0]:.3f}, {adjusted['coverage_ci'][1]:.3f}]")
    for lang, b in sorted(by_lang.items()):
        pr = b["tp"] / (b["tp"] + b["fp"]) if (b["tp"] + b["fp"]) else 1.0
        cv = b["tp"] / (b["tp"] + b["fn"]) if (b["tp"] + b["fn"]) else 1.0
        print(f"  {lang}: precision {pr:.3f} coverage {cv:.3f} (tp {b['tp']} fp {b['fp']} fn {b['fn']})")
    summary = {**fig, "by_lang": by_lang, "by_path": by_path, "mapper": label, "errata_adjusted": adjusted, "errata_items": sorted(errata)}
    print("versioned:", write_versioned("write_set", {"summary": summary, "results": rows}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
