"""Phase 90.G1 — reproduce the after-proposal interaction on ONE clone: the proposal_yes exchange in session A, then the plan_restart request
in a NEW session B on the same memory. Records for turn B1: the route the sensitizer produced, the tools offered, the plan's status and
origin, the tool trace, whether the injected context carries the proposal exchange, and the route exemplars the clone holds. A probe;
reusable as the regression check for the fix (compare B1 with and without session A)."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _bench_paths import SCRATCH, write_versioned  # noqa: E402
import bench_say_do as sd  # noqa: E402
from hmgfu.turn_tail import wait_for_tail  # noqa: E402

REQUEST = ("Plan and create three text files note1.txt, note2.txt and note3.txt in the workspace, each containing one line: "
           "'hmg say-do test'. Declare the plan first, then do it step by step.")
SUGGESTION = "you can maybe create a widget to keep links, like a storage for links i can click"


def snapshot(e, sid, r, label):
    md = (e.sessions.history(sid)[-1].get("metadata") or {})
    plan = r.get("plan") or {}
    inj = r.get("injected_context") or ""
    return {"label": label, "response": (r.get("response") or "")[:240], "tools_offered": r.get("tools_offered"),
            "tool_trace": [(t["name"], t.get("blocked"), t.get("failed")) for t in r["tool_trace"]],
            "plan_status": plan.get("status"), "plan_authorization": plan.get("authorization"), "plan_title": plan.get("title"),
            "saydo": md.get("saydo"), "route_in_context": {"shall_i_go_ahead": "shall i go ahead" in inj.lower(), "widget": "widget" in inj.lower(),
                                                          "proposal_words": sum(inj.lower().count(w) for w in ("proposal", "propose", "shall i"))},
            "injected_head": inj[:600]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="C:/Users/nora/hmg-fu/hmgfu.db")
    ap.add_argument("--skip-a", action="store_true", help="control: run B without the proposal session")
    ap.add_argument("--h1", action="store_true", help="after B, delete the learned route exemplars and ask again in a new session (H-A1)")
    args = ap.parse_args()
    clone = os.path.join(SCRATCH, f"after_proposal_{os.getpid()}.db"); sd.clone_live(clone, args.db)
    shutil.rmtree(sd.WORKSPACE, ignore_errors=True); sd.WORKSPACE.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(clone); n0 = con.execute("select count(*) from route_exemplars").fetchone()[0]; con.close()
    out = {"control": args.skip_a, "route_exemplars_before": n0}
    e = sd.fresh_engine(clone, None)
    routes = {}
    _orig = e.sensitizer.extract
    def _cap(text, *a, **k):                       # capture the route the sensitizer produced for each turn
        out = _orig(text, *a, **k)
        try:
            routes[text[:60]] = {f: out.get(f) for f in ("action_requested", "requested_tools", "conversation_act", "needs_memory", "route_source", "extractor")}
        except Exception:
            pass
        return out
    e.sensitizer.extract = _cap
    out_routes = routes
    if not args.skip_a:
        sa = sd.new_session(e, "A-proposal")
        ra1 = sd.turn(e, sa, SUGGESTION); wait_for_tail(e)
        ra2 = sd.turn(e, sa, "yes please"); wait_for_tail(e)
        out["A1"] = snapshot(e, sa, ra1, "A1 suggestion"); out["A2"] = snapshot(e, sa, ra2, "A2 yes")
    con = sqlite3.connect(clone)
    n1 = con.execute("select count(*) from route_exemplars").fetchone()[0]
    cols = [c[1] for c in con.execute("pragma table_info(route_exemplars)")]
    new_ex = con.execute("select * from route_exemplars order by rowid desc limit 3").fetchall()
    con.close()
    out["route_exemplars_after_A"] = n1
    out["route_exemplars_newest"] = [dict(zip(cols, r)) for r in new_ex]
    for r in out["route_exemplars_newest"]:
        for k in list(r):
            if k in ("embedding",): r[k] = f"<{len(r[k] or b'')} bytes>"
            elif isinstance(r[k], str) and len(r[k]) > 160: r[k] = r[k][:160]
    sb = sd.new_session(e, "B-request")
    e.settings.set("agent_max_iterations", 3)
    rb = sd.turn(e, sb, REQUEST); wait_for_tail(e)
    out["B1"] = snapshot(e, sb, rb, "B1 imperative request")
    files = sorted(p.name for p in sd.WORKSPACE.glob("note*.txt"))
    out["files_after_B1"] = files
    out["routes"] = out_routes
    if not args.skip_a and args.h1:                # H-A1: the learned route exemplar is the carrier → remove it and ask again in a new session
        e.graph.close()
        con = sqlite3.connect(clone); con.execute("delete from route_exemplars"); con.commit(); con.close()
        shutil.rmtree(sd.WORKSPACE, ignore_errors=True); sd.WORKSPACE.mkdir(parents=True, exist_ok=True)
        e = sd.fresh_engine(clone, None); e.settings.set("agent_max_iterations", 3)
        _o2 = e.sensitizer.extract
        def _cap2(text, *a, **k):
            o = _o2(text, *a, **k); routes["C:" + text[:56]] = {f: o.get(f) for f in ("action_requested", "requested_tools", "conversation_act", "route_source")}; return o
        e.sensitizer.extract = _cap2
        sc = sd.new_session(e, "C-request-no-exemplar")
        rc = sd.turn(e, sc, REQUEST); wait_for_tail(e)
        out["C1_after_deleting_exemplar"] = snapshot(e, sc, rc, "C1 same request, exemplar deleted")
        out["files_after_C1"] = sorted(p.name for p in sd.WORKSPACE.glob("note*.txt"))
    print(json.dumps(out, ensure_ascii=False, indent=1)[:6000])
    print("versioned:", write_versioned("after_proposal", out))
    e.graph.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
