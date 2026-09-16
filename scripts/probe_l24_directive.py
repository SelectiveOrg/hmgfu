"""Phase 57 L24 diagnosis: does the CONSTRAINED router emit a directive for a PT directive-change?

Reproduces the bench L24 setup: an EN opener ('a short joke') is already active, then the user
states the SAME rule in Portuguese ('comece cada conversa com uma piada curta'). We call the
constrained router N times and inspect the emitted `directive` field:
  - if it emits {conversation_opener, "uma piada..."} → the store/echo-guard is the issue;
  - if it returns null → the router judges the PT restatement redundant (needs a semantic detector).
Also probes WITHOUT the active-directive context to isolate whether that context suppresses it.

Run: .venv/Scripts/python scripts/probe_l24_directive.py
"""

from __future__ import annotations

import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hmgfu import config  # noqa: E402
from hmgfu.ollama_client import OllamaClient  # noqa: E402
from hmgfu.sensitizer import parse_nano_json  # noqa: E402
from hmgfu.turn_router import ROUTE_PROMPT, catalog_json, router_schema  # noqa: E402

CATALOG = {"bash": {"description": "run a shell command"},
           "memory_search": {"description": "search memory"},
           "create_widget": {"description": "create a widget"}}
SCHEMA = router_schema(list(CATALOG))
CATALOG_TEXT = catalog_json(CATALOG)
CLOCK = "RUNTIME CLOCK: now_local=2026-07-05T18:00:00+02:00"
ACTIVE = "\nACTIVE STANDING DIRECTIVES (context, currently in force):\n- conversation_opener: a short joke"
PT = "De agora em diante, comece cada nova conversa com uma piada curta."
N = 6


def call(client, with_active):
    sysmsg = CLOCK + "\n" + ROUTE_PROMPT + "\nRUNTIME TOOL CATALOG:\n" + CATALOG_TEXT
    if with_active:
        sysmsg += ACTIVE
    reply = client.chat(config.CHAT_MODEL,
                        [{"role": "system", "content": sysmsg}, {"role": "user", "content": PT}],
                        json_mode=True, temperature=0.0, format_schema=SCHEMA)
    obj = parse_nano_json(reply) or {}
    return obj.get("directive"), obj.get("conversation_act"), obj.get("action_requested")


def main() -> int:
    client = OllamaClient()
    if not client.available():
        print("FAIL: Ollama not reachable")
        return 1
    for label, with_active in (("WITH active-context (bench L24)", True),
                               ("WITHOUT active-context", False)):
        print(f"\n=== {label} ===")
        emitted = 0
        for i in range(N):
            d, act, action = call(client, with_active)
            has = isinstance(d, dict) and d.get("kind")
            emitted += 1 if has else 0
            print(f"  {i+1}: act={act!r} action={action} directive={json.dumps(d, ensure_ascii=False)[:120]}")
        print(f"  → emitted a directive object {emitted}/{N}")
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
