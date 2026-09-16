"""Phase 90.M3 — does what the LEDGER refuses still survive, and is it recovered with the right status?

For each DEV case (`scripts/oracles/status_v1.json`): say one sentence in session A, then ask a question in a NEW session B on the
same memory, and record the three layers separately, so a failure can be attributed:

  1. STORED    — is the sentence in the episodes (`memory_points`) and/or the ledger? (the ledger may legitimately refuse it)
  2. RETRIEVED — did the value reach the reader for the B question (injected context or the ledger lines)?
  3. STATUS    — does the reply present it with the right status: a fact as current, a wish/proposal as a wish, an activity as an
                 activity, and never a value listed in `must_not_say_as_current` as the user's current state?

The three-way distinction the user asked for falls out of those columns: `not stored` (1 fails), `stored but not retrieved`
(1 holds, 2 fails), `retrieved but misinterpreted` (1 and 2 hold, 3 fails). Reuses the say-do runner's engine, sessions and turn
wrapper; no new module and no change to any write path. Throwaway clone per case."""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _bench_paths import SCRATCH, write_versioned  # noqa: E402
import bench_say_do as sd  # noqa: E402
from hmgfu.turn_tail import wait_for_tail  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# a value is presented AS CURRENT when it follows a present-tense possession/state frame; a wish frame is the opposite
_CURRENT = r"(?:is|są|é|are|work(?:s|ing)? (?:at|on)|trabalh[ao]s?|mora|live[s]?|current(?:ly)?|principal|main)"
_WISH = (r"(?:want|wants|wanted|wish|would like|looking to|hoping|hope|plan|plans|interest(?:ed)? in|thinking of|"
         r"quer|queres|queria|quer[ií]amos|querem|gostar(?:ia|íamos)|interesse|pretend[ea]|deseja|propos|proposed|"
         r"suggest(?:ed)?|sugeriu|should|dev[ií]amos|mencionou)")


def _says_as_current(reply: str, value: str) -> bool:
    """The value appears within a present-state frame and NOT inside a wish frame in the same clause."""
    if not value:
        return False
    low, val = reply.lower(), value.lower()
    for clause in re.split(r"[,.;:!?\n]+", low):        # judge the CLAUSE that carries the value, not a fixed window
        if val not in clause:
            continue
        if re.search(_WISH, clause):
            continue                                    # the value is framed as a wish here
        if re.search(_CURRENT, clause):
            return True
    return False


def _mentions(reply: str, value: str) -> bool:
    return bool(value) and value.lower() in (reply or "").lower()


def _sections_carrying(injected: str, value: str) -> list:
    """90.N1 layer 3: which SECTION HEADING of the rendered injection carries the value. The heading is itself a status
    claim ('Active projects and goals'), so a value can change status between the point and the reader without any
    model rewriting the words."""
    out, heading = [], "(no heading)"
    for line in (injected or "").splitlines():
        s = line.strip()
        if s.endswith(":") and not s.startswith("-"):
            heading = s[:-1]
        elif value and value.lower() in s.lower():
            out.append((heading, s[:160]))
    return out


def _trace(case, clone, injected, reply):
    """90.N1: original message -> points/summaries -> context actually delivered -> reply, one case, verbatim."""
    val = case["value"] or ""
    print(f"\n===== TRACE {case['id']} ({case['class']}, {case['lang']})")
    print(f"  L1 MESSAGE   {case['say']!r}")
    con = sqlite3.connect(clone); con.row_factory = sqlite3.Row
    rows = con.execute("SELECT id, type, layer, source, title, summary, content FROM memory_points "
                       "WHERE content LIKE ? OR summary LIKE ? OR title LIKE ? ORDER BY timestamp DESC LIMIT 12",
                       (f"%{val}%", f"%{val}%", f"%{val}%")).fetchall()
    con.close()
    print(f"  L2 POINTS    {len(rows)} carrying {val!r}")
    for r in rows:
        print(f"     · type={r['type']:9} layer={str(r['layer'])[:14]:14} source={r['source']:14} title={str(r['title'])[:46]!r}")
        print(f"       summary={str(r['summary'])[:110]!r}")
        print(f"       content={str(r['content'])[:110]!r}")
    secs = _sections_carrying(injected, val)
    print(f"  L3 DELIVERED {len(secs)} line(s) carrying {val!r}, under:")
    for h, s in secs:
        print(f"     · [{h}] {s!r}")
    print(f"  L4 REPLY     {reply[:300]!r}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--oracle", default=os.path.join(ROOT, "scripts", "oracles", "status_v1.json"))
    ap.add_argument("--only", default=None)
    ap.add_argument("--db", default=None)
    ap.add_argument("--trace", action="store_true", help="90.N1: print the four layers verbatim for each case")
    ap.add_argument("--reps", type=int, default=1, help="90.N4: repeat each case N times — a single reader run is too "
                                                        "noisy to attribute a flip to a change")
    args = ap.parse_args()
    cases = json.load(open(args.oracle, encoding="utf-8"))["cases"]
    if args.only:
        keep = set(args.only.split(",")); cases = [c for c in cases if c["id"] in keep]
    rows = []
    cases = [c for _ in range(args.reps) for c in cases]
    for c in cases:
        clone = os.path.join(SCRATCH, f"status_{c['id']}_{os.getpid()}_{len(rows)}.db"); sd.clone_live(clone, args.db)
        e = sd.fresh_engine(clone, None)
        sa = sd.new_session(e, f"{c['id']}-{len(rows)}-A")
        before = {r["key"]: r["value"] for r in e.facts.active()}
        sd.turn(e, sa, c["say"]); wait_for_tail(e)
        after = {r["key"]: r["value"] for r in e.facts.active()}
        ledger_delta = {k: after[k] for k in after if before.get(k) != after.get(k)}
        con = sqlite3.connect(clone)
        key = (c["value"] or c["say"].split()[-1]).strip(".")
        episodes = con.execute("SELECT COUNT(*) FROM memory_points WHERE content LIKE ?", (f"%{key}%",)).fetchone()[0]
        con.close()
        sb = sd.new_session(e, f"{c['id']}-{len(rows)}-B")
        r = sd.turn(e, sb, c["ask"]); wait_for_tail(e)
        reply, injected = r.get("response") or "", r.get("injected_context") or ""
        stored = bool(episodes) or bool(ledger_delta)
        retrieved = _mentions(injected, c["value"]) or _mentions(json.dumps(after, ensure_ascii=False), c["value"])
        as_current = _says_as_current(reply, c["value"])
        forbidden = [v for v in c["must_not_say_as_current"] if _says_as_current(reply, v)]
        exp = c["expect_status"]
        if exp == "fact":
            status_ok = as_current and not forbidden
        elif exp in ("wish", "activity"):
            status_ok = _mentions(reply, c["value"]) and not forbidden and (exp == "activity" or not as_current)
        else:                                            # absent
            status_ok = not forbidden and not _mentions(reply, c["value"])
        needs_retrieval = exp != "absent"                # a value the reply must NOT use need not be retrieved
        layer = "OK" if (stored and (retrieved or not needs_retrieval) and status_ok) else (
            "not stored" if not stored else "stored but not retrieved" if (needs_retrieval and not retrieved)
            else "retrieved but misinterpreted")
        if args.trace:
            _trace(c, clone, injected, reply)
        rows.append({"id": c["id"], "class": c["class"], "lang": c["lang"], "say": c["say"], "ask": c["ask"],
                     "value": c["value"], "expect_status": exp, "ledger_delta": ledger_delta, "episodes": episodes,
                     "stored": stored, "retrieved": retrieved, "as_current": as_current, "forbidden_as_current": forbidden,
                     "status_ok": status_ok, "layer": layer, "reply": reply[:260]})
        print(f"[{layer:26}] {c['id']} {c['class']:15} {c['lang']} · stored={int(stored)} (episodes {episodes}, ledger {ledger_delta or '{}'}) "
              f"retrieved={int(retrieved)} status_ok={int(status_ok)} as_current={int(as_current)} forbidden={forbidden}")
        print(f"      say  {c['say'][:80]!r}\n      ask  {c['ask'][:60]!r} → {reply[:150]!r}")
        e.graph.close()
    from collections import Counter
    print("\nEPISODE/STATUS DIAGNOSTIC", f"{sum(1 for r in rows if r['layer'] == 'OK')}/{len(rows)}")
    print("  layers:", dict(Counter(r["layer"] for r in rows)))
    for cls in sorted({r["class"] for r in rows}):
        sub = [r for r in rows if r["class"] == cls]
        print(f"  {cls:16} OK {sum(1 for r in sub if r['layer'] == 'OK')}/{len(sub)} · " +
              ", ".join(f"{r['id']}:{r['layer'].split()[0]}" for r in sub))
    print("versioned:", write_versioned("episode_status", {"rows": rows}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
