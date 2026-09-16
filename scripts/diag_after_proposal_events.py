"""Phase 90.G1 — same A→B1 shape as diag_after_proposal, plus the say-do EVENTS of turn B1 (proposed / executed_intent /
proposed_unconfirmed …), the tool calls the model attempted (blocked or not), and the turn's effects-allowed flag, so we can see whether
the explicit-order re-ask fired and what the model did on it. Probe only; throwaway clone."""
from __future__ import annotations

import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _bench_paths import SCRATCH, write_versioned  # noqa: E402
import bench_say_do as sd  # noqa: E402
from hmgfu.turn_tail import wait_for_tail  # noqa: E402

REQUEST = ("Plan and create three text files note1.txt, note2.txt and note3.txt in the workspace, each containing one line: "
           "'hmg say-do test'. Declare the plan first, then do it step by step.")


def main() -> int:
    clone = os.path.join(SCRATCH, f"ap_events_{os.getpid()}.db"); sd.clone_live(clone, None)
    shutil.rmtree(sd.WORKSPACE, ignore_errors=True); sd.WORKSPACE.mkdir(parents=True, exist_ok=True)
    e = sd.fresh_engine(clone, None)
    events = []
    orig_emit = e._emit
    def cap(ev):
        if isinstance(ev, dict) and ev.get("type") in ("saydo", "plan_update", "tool", "tool_call", "tool_result", "grounding", "authority", "blocked"):
            events.append({k: (str(v)[:120] if not isinstance(v, (int, float, bool, type(None))) else v) for k, v in ev.items()})
        return orig_emit(ev)
    e._emit = cap
    chat_calls = []
    orig_chat = e.sensitizer._chat
    sa = sd.new_session(e, "A"); sd.turn(e, sa, "you can maybe create a widget to keep links, like a storage for links i can click"); wait_for_tail(e)
    sd.turn(e, sa, "yes please"); wait_for_tail(e)
    events.clear()
    sb = sd.new_session(e, "B"); e.settings.set("agent_max_iterations", 3)
    rb = sd.turn(e, sb, REQUEST); wait_for_tail(e)
    out = {"effects_allowed": getattr(e, "_turn_effects_allowed", None), "unconfirmed_effects": getattr(e, "_turn_unconfirmed_effects", None),
           "proposed_flag": getattr(e, "_turn_proposed", None), "tool_trace": [(t["name"], t.get("blocked"), t.get("failed"), str(t.get("result"))[:80]) for t in rb["tool_trace"]],
           "response": (rb.get("response") or "")[:300], "plan": {k: (rb.get("plan") or {}).get(k) for k in ("status", "title", "authorization")},
           "saydo_events": [ev for ev in events if ev.get("type") == "saydo"], "other_events": [ev for ev in events if ev.get("type") != "saydo"][:20],
           "files": sorted(p.name for p in sd.WORKSPACE.glob("note*.txt"))}
    print(json.dumps(out, ensure_ascii=False, indent=1)[:5000])
    print("versioned:", write_versioned("after_proposal_events", out))
    e.graph.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
