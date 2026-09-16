"""Phase 58 — confirm the Ollama `think` API + bug #15260 LIVE on our stack before building.

Research (docs/MODEL_NOTES.md) claims: (a) `think` is a top-level /api/chat param, reasoning
returns in message.thinking; (b) BUG #15260 — think:false + format=<schema> SILENTLY DROPS the
schema → prose. This probe verifies both on OUR Ollama 0.31.1 + the actual model, so the build
rests on evidence not a blog post.

Run: .venv/Scripts/python scripts/probe_think_api.py [model]   (default gemma4:12b)
"""

from __future__ import annotations

import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx  # noqa: E402

from hmgfu import config  # noqa: E402

MODEL = sys.argv[1] if len(sys.argv) > 1 else config.CHAT_MODEL
BASE = "http://127.0.0.1:11434"
SCHEMA = {"type": "object", "properties": {"act": {"type": "string",
          "enum": ["greeting", "question", "task"]}, "urgent": {"type": "boolean"}},
          "required": ["act", "urgent"]}
MSG = [{"role": "user", "content": "Run the shell command echo hi and tell me if it's urgent."}]


def call(think, fmt, label):
    payload = {"model": MODEL, "messages": MSG, "stream": False, "options": {"temperature": 0.0}}
    if think is not None:
        payload["think"] = think
    if fmt is not None:
        payload["format"] = fmt
    try:
        r = httpx.post(f"{BASE}/api/chat", json=payload, timeout=180.0)
        r.raise_for_status()
        msg = r.json().get("message", {})
        content = (msg.get("content") or "").strip()
        thinking = (msg.get("thinking") or "").strip()
        is_json = False
        try:
            obj = json.loads(content)
            is_json = isinstance(obj, dict) and "act" in obj
        except Exception:
            is_json = False
        print(f"\n[{label}]  think={think} format={'schema' if fmt else None}")
        print(f"   message.thinking present: {'YES (' + str(len(thinking)) + ' chars)' if thinking else 'no'}")
        print(f"   content valid schema-JSON: {is_json}")
        print(f"   content[:90]: {content[:90]!r}")
        return is_json, bool(thinking)
    except Exception as exc:
        print(f"\n[{label}]  ERROR: {type(exc).__name__}: {exc}")
        return None, None


def main() -> int:
    print(f"model={MODEL}  ollama={BASE}")
    # 1. thinking on, no format -> expect message.thinking populated, content = free answer
    call(True, None, "1 think=true, no format")
    # 2. thinking off, no format -> expect no thinking, content = free answer
    call(False, None, "2 think=false, no format")
    # 3. OMIT think + format=schema -> expect valid schema JSON (the router's correct config)
    ok3, _ = call(None, SCHEMA, "3 OMIT think + format (router)")
    # 4. think=false + format=schema -> #15260: expect the schema SILENTLY DROPPED (prose, not JSON)
    ok4, _ = call(False, SCHEMA, "4 think=false + format (#15260 trap)")

    print("\n=== VERDICT ===")
    print(f"  router config (omit think + format) yields valid JSON: {ok3}")
    print(f"  #15260 reproduced (think:false+format DROPS schema): "
          f"{ok4 is False}  (True = bug present on our stack → router must OMIT think)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
