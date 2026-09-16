"""Phase 57 L24 end-to-end reproduction: WHY doesn't the PT directive-change supersede live?

Runs the bench L24 sequence on a REAL AgentEngine (throwaway db): set the EN opener (L15), then
state the PT change (L24). Captures the router's actual query fields (conversation_act,
action_requested, requested_tools, directive) AND whether is_blocked_directive_change fired, so we
fix the true runtime cause — not an assumption.

Run: .venv/Scripts/python scripts/probe_l24_e2e.py
"""

from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3  # noqa: E402

from hmgfu import config  # noqa: E402
from hmgfu.agent import AgentEngine  # noqa: E402
from hmgfu.directives import is_blocked_directive_change  # noqa: E402
from _bench_paths import throwaway_db  # noqa: E402

DB = throwaway_db("l24_e2e.db")
CLONE_PRODUCTION = "--clone" in sys.argv   # reproduce the bench's RICH graph (triggers recovery)
L15 = "From now on, always begin the first reply of every new conversation with a short joke."
L24 = "De agora em diante, comece cada nova conversa com uma piada curta."


def opener(engine):
    return next((d for d in engine.directives.active() if d["kind"] == "conversation_opener"), None)


def main() -> int:
    if os.path.exists(DB):
        os.remove(DB)
    if CLONE_PRODUCTION:                      # SQLite online backup — production stays read-only
        src, dst = sqlite3.connect(config.DB_PATH), sqlite3.connect(DB)
        src.backup(dst); dst.close(); src.close()
        print(f"cloned production ({config.DB_PATH}) → rich graph")
    engine = AgentEngine(db_path=DB)
    if not engine.client.available():
        print("FAIL: Ollama not reachable")
        return 1

    engine.agent_chat(L15, explicit=True)
    o15 = opener(engine)
    print(f"after L15 opener: value={o15 and o15['value']!r} instr={o15 and o15['instruction'][:40]!r}")

    captured = {}
    real = engine.retrieve
    def cap(text, **kw):
        q, r, ms = real(text, **kw)
        captured["q"] = q
        return q, r, ms
    engine.retrieve = cap

    engine.agent_chat(L24, explicit=True)
    q = captured.get("q")
    if q is not None:
        # replicate the agent's genuine-tool computation with a best-effort offered set
        offered = list(engine.tools.schemas)
        genuine = [n for n in (q.requested_tools or []) if n in offered]
        blocked = is_blocked_directive_change(q.directive, [o15] if o15 else [],
                                              bool(genuine), q.conversation_act)
        print(f"L24 router: act={q.conversation_act!r} action_requested={q.action_requested} "
              f"requested_tools={q.requested_tools}")
        print(f"L24 directive emitted: {q.directive}")
        print(f"L24 genuine_tool_turn={bool(genuine)} → is_blocked_directive_change={blocked}")
    o24 = opener(engine)
    print(f"after L24 opener: value={o24 and o24['value']!r} instr={o24 and o24['instruction'][:40]!r}")
    ok = bool(o24 and "De agora" in (o24.get("instruction") or ""))
    print("L24 SUPERSEDED:", "YES" if ok else "NO")
    engine.graph.close()
    engine.client.close()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
