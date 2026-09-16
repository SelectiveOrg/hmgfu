"""Probe the FULL causal chain for ornith's failing proactive action turns (bench L8/L9/L10/L23).

For each prompt, capture: router classification (action_requested/requested_tools/conversation_act)
→ offered tools → requested_actions → is_action_turn → the `think` value sent → ornith's RAW reply
(content + message.thinking) → what parse_text_tool_call recovers. This tells us WHICH layer drops
the call (classification vs thinking vs emission-format parsing) so the fix targets the true cause.

Serial (one local GPU). Read-only clone of the live DB — never writes production. Run:
  HMGFU_BENCH_CHAT_MODEL=ornith:9b .venv/Scripts/python scripts/probe_action_turns.py
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hmgfu import config, thinking          # noqa: E402
from hmgfu.agent import AgentEngine         # noqa: E402
from hmgfu.tool_protocol import parse_text_tool_call  # noqa: E402

MODEL = os.environ.get("HMGFU_BENCH_CHAT_MODEL", "ornith:9b")
SCRATCH = ROOT / "scratch"
CLONE = SCRATCH / "probe_action_turns.db"
WS = SCRATCH / "probe_action_workspace"

CAP: dict = {}


def main() -> int:
    SCRATCH.mkdir(exist_ok=True)
    if CLONE.exists():
        CLONE.unlink()
    src, dst = sqlite3.connect(config.DB_PATH), sqlite3.connect(CLONE)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    if WS.exists():
        shutil.rmtree(WS)
    WS.mkdir(parents=True)
    (WS / "PROJECT_ID.md").write_text("# Benchmark Workspace\n\nMarker: HMG-LIVE-BENCH-51\n",
                                      encoding="utf-8")

    engine = AgentEngine(db_path=str(CLONE))
    if not engine.client.available():
        print("FAIL: Ollama unreachable")
        return 1
    engine.settings.update({
        "chat_provider": "ollama", "chat_model": MODEL,
        "workspace_dir": str(WS), "grader_enabled": False,
        "mini_dream_every_n_turns": 0, "full_dream_every_n_turns": 0,
        "retrieval_limit": 12, "agent_max_iterations": 6,
    })
    engine._apply_nano_gates()

    # (1) capture the router's classification for the turn
    real_retrieve = engine.retrieve
    def retrieve(text, **kw):
        q, r, ms = real_retrieve(text, **kw)
        CAP["router"] = {"action_requested": getattr(q, "action_requested", None),
                         "requested_tools": list(getattr(q, "requested_tools", []) or []),
                         "conversation_act": getattr(q, "conversation_act", None),
                         "intent": getattr(q, "intent", None),
                         "directive": getattr(q, "directive", None)}
        CAP["query_point"] = q
        return q, r, ms
    engine.retrieve = retrieve

    def tool_scores(q):
        """Semantic score of each registered tool against the query (the retrieve_tools_for_turn
        gate uses these): shows whether bash/read_file cleared the 0.44 'question' bar (L8)."""
        from hmgfu import fu_math
        w = engine.weight_learner.weights()
        out = []
        for p in engine.graph.points.values():
            if p.type != "skill" or p.status != "active":
                continue
            name = next((k[5:] for k in p.keywords if k.startswith("tool:")), None)
            if name and name in engine.tools.schemas:
                out.append((round(fu_math.memory_score(q, p, weights=w), 3), name))
        return sorted(out, reverse=True)[:6]

    # (2) capture is_action_turn + the think value the turn resolves to
    real_turn_thinking = thinking.turn_thinking
    def turn_thinking(mode, is_action_turn, provider, chat_model, client):
        think, directive = real_turn_thinking(mode, is_action_turn, provider, chat_model, client)
        CAP["thinking"] = {"mode": mode, "is_action_turn": is_action_turn, "think": think,
                           "native_directive_empty": directive == ""}
        return think, directive
    thinking.turn_thinking = turn_thinking

    # (3) capture the RAW model reply (content + native thinking) + the `think` kwarg actually sent,
    #     and what the text-recovery parser extracts from that raw content
    real_chat_for_role = engine.registry.chat_for_role
    def chat_for_role(role, messages, **kw):
        res = real_chat_for_role(role, messages, **kw)
        if role == "chat":
            tools = kw.get("tools") or []
            content = res.get("content", "") if isinstance(res, dict) else str(res)
            CAP.setdefault("chat_calls", []).append({
                "think_sent": kw.get("think"),
                "native_tool_calls": [t.get("name") for t in (res.get("tool_calls") or [])]
                if isinstance(res, dict) else [],
                "thinking_len": len(res.get("thinking", "") or "") if isinstance(res, dict) else 0,
                "content": content,
                "recovered": parse_text_tool_call(content, tools),
                "offered": [t.get("name") for t in tools],
            })
        return res
    engine.registry.chat_for_role = chat_for_role

    prompts = {
        "L8/L9 workspace-inspect":
            "Inspect the selected project folder before answering. What is its exact benchmark marker?",
        "L10 widget-create":
            "Create a note widget titled Live Benchmark with text 'proactive widget complete'.",
        "CTRL greeting (L2 — must stay tool-free)":
            "hello",
        "CTRL identity-question (L3 — must stay tool-free)":
            "Do you know me? State only facts you are confident are current.",
    }
    for label, prompt in prompts.items():
        CAP.clear()
        CAP["chat_calls"] = []
        print("\n" + "=" * 78)
        print(f"### {label}\n    prompt: {prompt}")
        result = engine.agent_chat(prompt)
        print(f"  ROUTER:   {CAP.get('router')}")
        print(f"  THINKING: {CAP.get('thinking')}")
        for i, c in enumerate(CAP.get("chat_calls", [])):
            print(f"  CHAT[{i}] think_sent={c['think_sent']} native_calls={c['native_tool_calls']} "
                  f"thinking_len={c['thinking_len']} offered={c['offered']}")
            print(f"          recovered={c['recovered']}")
            print(f"          content={c['content'][:400]!r}")
        print("  TOOL_TRACE:")
        for t in result.get("tool_trace", []):
            print(f"    - {t['name']} failed={t.get('failed')} blocked={t.get('blocked')} "
                  f"args={t.get('arguments')}")
            print(f"        result={str(t.get('result'))[:200]!r}")
        qp = CAP.get("query_point")
        if qp is not None:
            print(f"  TOOL_SCORES (vs query): {tool_scores(qp)}")
        used = sorted({t["name"] for t in result.get("tool_trace", [])
                       if not t.get("failed") and not t.get("blocked")})
        print(f"  TOOLS USED (final): {used}")

    engine.graph.close()
    engine.client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
