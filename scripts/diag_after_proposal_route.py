"""Phase 90.G1 — where is the route lost? Same A→B1 shape; for turn B1 records (1) the router future's result as merged by
`turn_router.merge_route`, (2) the sensitizer's pre-reply extraction (route=True call only), (3) the tool schemas offered by
`tool_points.retrieve_tools_for_turn` with the query point's requested_tools/action_requested, (4) the learned weights. Probe only."""
from __future__ import annotations

import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _bench_paths import SCRATCH, write_versioned  # noqa: E402
import bench_say_do as sd  # noqa: E402
from hmgfu import tool_points, turn_router  # noqa: E402
from hmgfu.turn_tail import wait_for_tail  # noqa: E402

REQUEST = ("Plan and create three text files note1.txt, note2.txt and note3.txt in the workspace, each containing one line: "
           "'hmg say-do test'. Declare the plan first, then do it step by step.")


def main() -> int:
    skip_a = "--skip-a" in sys.argv
    clone = os.path.join(SCRATCH, f"ap_route_{os.getpid()}.db"); sd.clone_live(clone, None)
    shutil.rmtree(sd.WORKSPACE, ignore_errors=True); sd.WORKSPACE.mkdir(parents=True, exist_ok=True)
    e = sd.fresh_engine(clone, None)
    rec = {"control": skip_a, "merge": [], "extract": [], "tools": []}
    om = turn_router.merge_route
    def cap_merge(raw, future):
        try:
            res = future.result(); rec["merge"].append({"router_result": {k: res.get(k) for k in ("action_requested", "requested_tools", "conversation_act")}})
        except Exception as exc:
            rec["merge"].append({"router_error": f"{type(exc).__name__}: {exc}"[:160]})
        return om(raw, future)
    turn_router.merge_route = cap_merge
    oe = e.sensitizer.extract
    def cap_extract(text, *a, **k):
        out = oe(text, *a, **k)
        if k.get("route") and text.startswith("Plan and create"):
            rec["extract"].append({k2: out.get(k2) for k2 in ("action_requested", "requested_tools", "conversation_act", "intent", "route_source", "extractor")})
        return out
    e.sensitizer.extract = cap_extract
    ot = tool_points.retrieve_tools_for_turn
    def cap_tools(registry, engine, qp, *a, **k):
        res = ot(registry, engine, qp, *a, **k)
        if qp.text.startswith("Plan and create"):
            rec["tools"].append({"qp_requested": list(qp.requested_tools), "qp_action": qp.action_requested, "qp_act": qp.conversation_act, "qp_intent": qp.intent,
                                 "offered": [t["name"] for t in res]})
        return res
    tool_points.retrieve_tools_for_turn = cap_tools
    import hmgfu.agent as ag
    if hasattr(ag, "retrieve_tools_for_turn"):
        ag.retrieve_tools_for_turn = cap_tools
    if not skip_a:
        sa = sd.new_session(e, "A"); sd.turn(e, sa, "you can maybe create a widget to keep links, like a storage for links i can click"); wait_for_tail(e)
        sd.turn(e, sa, "yes please"); wait_for_tail(e)
        rec["merge"].clear()
    rec["weights_before_B1"] = {k: round(v, 3) for k, v in (e.weight_learner.weights() or {}).items()} if hasattr(e, "weight_learner") else None
    sb = sd.new_session(e, "B"); e.settings.set("agent_max_iterations", 3)
    rb = sd.turn(e, sb, REQUEST); wait_for_tail(e)
    rec["B1"] = {"tools_offered": rb.get("tools_offered"), "tool_trace": [t["name"] for t in rb["tool_trace"]], "plan": (rb.get("plan") or {}).get("status"),
                 "files": sorted(p.name for p in sd.WORKSPACE.glob("note*.txt")), "response": (rb.get("response") or "")[:160]}
    print(json.dumps(rec, ensure_ascii=False, indent=1)[:4000])
    print("versioned:", write_versioned("after_proposal_route", rec))
    e.graph.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
