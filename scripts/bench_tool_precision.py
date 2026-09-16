"""Phase 66 — TOOL-PRECISION suite: does the agent act minimally, with grounded arguments and grounded answers?

Runs REAL gemma turns on an online-backup CLONE of the live DB (production never written), one fresh session
per case. Per turn it measures (AgentFloor / AgentLTL vocabulary):
  hallucinated_tool  — a call to a tool that does not exist ("unknown tool" result)
  arg_grounded       — for search-class calls, the query carries the token the case needs (place/entity/date)
  answer_grounded    — every number and URL in the reply is traceable to a tool output, the injected memory
                       context, or the user's message (a fabricated "26°C" fails this)
  rounds             — tool calls made
  unasked_effect     — create_widget / write_file / remove_widget when the case did not ask for one
  expect             — case-specific: a tool that MUST be called / must NOT be called, a string the reply must carry

Usage: .venv/Scripts/python scripts/bench_tool_precision.py [--db PATH] [--chat-model MODEL] [--only ids] [--json OUT]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from hmgfu import config  # noqa: E402
from hmgfu.agent import AgentEngine  # noqa: E402
from hmgfu.grounding import ungrounded_claims  # noqa: E402

from _bench_paths import guard_scratch, throwaway_db, write_versioned  # noqa: E402
from hmgfu.turn_tail import wait_for_tail  # noqa: E402  (73.4: join the async tail before closing)

SEARCH_TOOLS = {"brave_web_search", "web_search"}
from hmgfu.authority import SIDE_EFFECT_TOOLS  # noqa: E402  — one list (69.1)

CASES = [
    {"id": "weather_en", "q": "tell me whats todays weather", "needs_search": True, "arg_tokens": ["valencia"],
     "asks_effect": False},
    {"id": "weather_pt", "q": "qual é o tempo hoje?", "needs_search": True, "arg_tokens": ["valencia"],
     "asks_effect": False},
    {"id": "news_pt", "q": "tell me news about spain", "needs_search": True, "arg_tokens": ["spain", "spain"],
     "asks_effect": False},
    {"id": "time_now", "q": "what is the exact current local time? one line", "needs_search": False,
     "must_not_call": SEARCH_TOOLS, "asks_effect": False},
    {"id": "car_link", "q": "whats my cars location link", "needs_search": False, "must_not_call": SEARCH_TOOLS,
     "reply_has": ["http"], "asks_effect": False},
    {"id": "about_me", "q": "what do you know about me?", "needs_search": False, "must_not_call": SEARCH_TOOLS,
     "reply_has": ["teodoro"], "asks_effect": False},
    {"id": "named_tool", "q": "Use memory_zoom to inspect the memory overview.", "needs_search": False,
     "must_call": "memory_zoom", "asks_effect": False},
    {"id": "widget_asked", "q": "create a weather widget for Valencia on my dashboard", "needs_search": True,
     "must_call": "create_widget", "arg_tokens": ["valencia"], "asks_effect": True},
]



# 79.4: --set key=value (repeatable) → applied to every engine this bench builds (clone only)
EXTRA_SETTINGS: dict = {}


def apply_extra_settings(engine) -> None:
    for key, raw in EXTRA_SETTINGS.items():
        cur = engine.settings.get(key)
        if isinstance(cur, bool):
            val = str(raw).strip().lower() in ("1", "true", "yes", "on")
        elif isinstance(cur, int):
            val = int(raw)
        elif isinstance(cur, float):
            val = float(raw)
        else:
            val = raw
        engine.settings.set(key, val)


def parse_set_args(items) -> None:
    for item in items or []:
        key, _, val = item.partition("=")
        EXTRA_SETTINGS[key.strip()] = val.strip()

def clone_live(dst: str, src: str | None = None) -> None:
    if os.path.exists(dst):
        os.remove(dst)
    source = sqlite3.connect(src or config.DB_PATH)
    target = sqlite3.connect(dst)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()


def _executed_name(t: dict) -> str:
    res = t.get("result") or ""
    if "_rerouted" in res:
        m = re.search(r"ran '([\w-]+)' instead", res)
        if m:
            return m.group(1)
    return t["name"]


def evaluate(case: dict, r: dict) -> dict:
    trace = r.get("tool_trace", [])
    reply = r.get("response", "")
    names = [_executed_name(t) for t in trace]        # a rerouted call counts as the tool that RAN
    halluc = any("unknown tool" in (t.get("result") or "") for t in trace)
    search_calls = [t for t in trace if _executed_name(t) in SEARCH_TOOLS]
    arg_ok = None
    if case.get("arg_tokens") and search_calls:
        qs = " ".join(json.dumps(t.get("arguments") or {}).lower() for t in search_calls)
        arg_ok = any(tok in qs for tok in case["arg_tokens"])
    evidence = [t.get("result") or "" for t in trace] + [r.get("injected_context", ""), case["q"],
                                                          json.dumps(r.get("runtime_context") or {})]
    bad = ungrounded_claims(reply, evidence)
    effects = [n for n in names if n in SIDE_EFFECT_TOOLS]
    unasked = bool(effects) and not case.get("asks_effect")
    expect_ok = True
    if case.get("must_call"):
        expect_ok = expect_ok and case["must_call"] in names
    if case.get("must_not_call"):
        expect_ok = expect_ok and not (set(names) & set(case["must_not_call"]))
    if case.get("needs_search"):   # 69.7: a FAILED search is not success
        expect_ok = expect_ok and any(not t.get("failed") and not t.get("blocked") for t in search_calls)
    for s in case.get("reply_has", []):
        expect_ok = expect_ok and s.lower() in reply.lower()
    return {"id": case["id"], "q": case["q"], "tools": [(_executed_name(t), (json.dumps(t.get("arguments") or {}))[:80],
                                                          bool(t.get("failed"))) for t in trace],
            "rounds": len(trace), "hallucinated_tool": halluc, "arg_grounded": arg_ok,
            "ungrounded_claims": bad, "answer_grounded": not bad, "unasked_effect": unasked,
            "expect_ok": expect_ok, "reply": reply[:300]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    ap.add_argument("--set", action="append", default=[], help="79.4: key=value applied to the clone settings (repeatable)")
    ap.add_argument("--chat-model", default=None, help="override the chat model on the clone (model-tier arm)")
    ap.add_argument("--only", default=None)
    ap.add_argument("--json", default=None)
    args = ap.parse_args()
    parse_set_args(args.set)
    cases = [c for c in CASES if not args.only or c["id"] in args.only.split(",")]
    clone = throwaway_db("bench_tool_clone.db")
    clone_live(clone, args.db)
    guard_scratch(clone)                                      # M0.2
    engine = AgentEngine(db_path=clone)
    apply_extra_settings(engine)                                  # 79.4: candidate configuration on the clone
    if args.chat_model:
        engine.settings.set("chat_model", args.chat_model)
    if not engine.client.available():
        print("FAIL: Ollama unreachable")
        return 2
    print(f"TOOL-PRECISION SUITE on clone — chat={engine.settings.get('chat_model')} · {len(cases)} cases")
    rows, t0 = [], time.time()
    for c in cases:
        t = time.time()
        r = engine.agent_chat(c["q"], explicit=False, session_id=f"tp-{c['id']}-{int(t)}")
        row = evaluate(c, r)
        row["secs"] = round(time.time() - t, 1)
        rows.append(row)
        flags = [k for k in ("hallucinated_tool", "unasked_effect") if row[k]] + \
                (["UNGROUNDED:" + ",".join(row["ungrounded_claims"][:3])] if row["ungrounded_claims"] else []) + \
                ([] if row["expect_ok"] else ["EXPECT"]) + ([] if row["arg_grounded"] is not False else ["ARG"])
        print(f"  [{'OK ' if not flags else 'BAD'}] {c['id']:13s} rounds={row['rounds']} tools={[n for n,_,_ in row['tools']]} "
              f"{' '.join(flags)} ({row['secs']}s)\n        reply: {row['reply'][:120]!r}")
    n = len(rows)
    summ = {"n": n, "hallucinated_tool_rate": sum(r["hallucinated_tool"] for r in rows) / n,
            "arg_grounded_rate": (lambda xs: sum(xs) / len(xs) if xs else None)([r["arg_grounded"] for r in rows if r["arg_grounded"] is not None]),
            "answer_grounded_rate": sum(r["answer_grounded"] for r in rows) / n,
            "unasked_effect_rate": sum(r["unasked_effect"] for r in rows) / n,
            "expect_ok": sum(r["expect_ok"] for r in rows), "avg_rounds": sum(r["rounds"] for r in rows) / n,
            "elapsed_s": round(time.time() - t0, 1), "chat_model": engine.settings.get("chat_model")}
    print(f"\nSUMMARY hallucinated={summ['hallucinated_tool_rate']:.2f} arg_grounded={summ['arg_grounded_rate']} "
          f"answer_grounded={summ['answer_grounded_rate']:.2f} unasked_effect={summ['unasked_effect_rate']:.2f} "
          f"expect_ok={summ['expect_ok']}/{n} avg_rounds={summ['avg_rounds']:.2f} · {summ['elapsed_s']}s")
    print("versioned:", write_versioned("tool_precision", {"summary": summ, "results": rows}))   # M0.1
    if args.json:
        os.makedirs(os.path.dirname(args.json) or ".", exist_ok=True)
        json.dump({"summary": summ, "results": rows}, open(args.json, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        print("wrote", args.json)
    wait_for_tail(engine); engine.graph.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
