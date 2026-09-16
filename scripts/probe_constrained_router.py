"""Phase 57 P1 evidence: grammar-constrained router vs loose-json on LIVE gemma4:12b.

Runs the SAME router prompt N times per input, CONSTRAINED (Ollama format=<router schema>) vs
LOOSE (format="json"), and measures the WELL-FORMED rate: all required fields present, every enum
valid, every requested tool inside the live catalog. This proves the decode-time guarantee is
real on our Ollama 0.31.1 (a dropped field / off-catalog tool should be impossible constrained).

Run:  .venv/Scripts/python scripts/probe_constrained_router.py
Does NOT touch any DB — pure router calls.
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

CATALOG = {
    "bash": {"description": "run a shell command"},
    "memory_search": {"description": "search the relational memory"},
    "create_widget": {"description": "create a canvas widget"},
    "gog_status": {"description": "check Google connection status"},
    "brave_web_search": {"description": "search the live web"},
}
NAMES = list(CATALOG)
SCHEMA = router_schema(NAMES)
CATALOG_TEXT = catalog_json(CATALOG)
CLOCK = "RUNTIME CLOCK: now_local=2026-07-05T18:00:00+02:00 local_time=18:00:00 local_date=2026-07-05"

PROMPTS = [
    ("EN action", "run the shell command echo hello"),
    ("PT action", "pesquise na sua memoria pelo codigo exato ORCA-7"),
    ("EN greeting", "hello there"),
    ("PT time", "que horas sao agora?"),
    ("PT canvas", "crie um widget de nota chamado Teste com o texto pronto"),
]
N = 8
REQUIRED = ["conversation_act", "action_requested", "requested_tools", "freshness",
            "needs_memory", "runtime_context_keys", "runtime_context_sufficient"]
ACTS = {"greeting", "question", "instruction", "feedback", "statement"}
FRESH = {"none", "historical", "current"}


def well_formed(obj) -> tuple:
    """(ok, reason). Checks structure a valid route MUST have."""
    if not isinstance(obj, dict):
        return False, "not a dict"
    for f in REQUIRED:
        if f not in obj:
            return False, f"missing {f}"
    if obj.get("conversation_act") not in ACTS:
        return False, f"bad act {obj.get('conversation_act')!r}"
    if obj.get("freshness") not in FRESH:
        return False, f"bad freshness {obj.get('freshness')!r}"
    if not isinstance(obj.get("action_requested"), bool):
        return False, "action_requested not bool"
    tools = obj.get("requested_tools")
    if not isinstance(tools, list):
        return False, "requested_tools not list"
    off = [t for t in tools if t not in CATALOG]
    if off:
        return False, f"off-catalog tool {off}"
    return True, "ok"


def run(client, text, constrained):
    reply = client.chat(
        config.CHAT_MODEL,
        [{"role": "system", "content": CLOCK + "\n" + ROUTE_PROMPT
          + "\nRUNTIME TOOL CATALOG:\n" + CATALOG_TEXT},
         {"role": "user", "content": text}],
        json_mode=True, temperature=0.0,
        format_schema=SCHEMA if constrained else None,
    )
    return well_formed(parse_nano_json(reply) or reply)


def main() -> int:
    client = OllamaClient()
    if not client.available():
        print("FAIL: Ollama not reachable")
        return 1
    print(f"model={config.CHAT_MODEL}  N={N}/prompt  catalog={NAMES}\n")
    totals = {"constrained": [0, 0], "loose": [0, 0]}
    for label, text in PROMPTS:
        for mode, key in (("constrained", "constrained"), ("loose", "loose")):
            ok_n, fails = 0, []
            for _ in range(N):
                try:
                    ok, reason = run(client, text, mode == "constrained")
                except Exception as exc:
                    ok, reason = False, f"err {type(exc).__name__}"
                ok_n += 1 if ok else 0
                if not ok:
                    fails.append(reason)
                totals[key][0] += 1 if ok else 0
                totals[key][1] += 1
            tag = "CONSTRAINED" if mode == "constrained" else "loose-json  "
            note = "" if not fails else f"  fails={fails[:3]}"
            print(f"  [{label:11}] {tag}: {ok_n}/{N} well-formed{note}")
        print()
    client.close()
    c, l = totals["constrained"], totals["loose"]
    print(f"=== TOTAL well-formed ===")
    print(f"  CONSTRAINED: {c[0]}/{c[1]} ({100*c[0]//max(1,c[1])}%)")
    print(f"  loose-json : {l[0]}/{l[1]} ({100*l[0]//max(1,l[1])}%)")
    print("PROBE:", "PASS" if c[0] == c[1] else f"PARTIAL ({c[0]}/{c[1]} constrained)")
    return 0 if c[0] == c[1] else 1


if __name__ == "__main__":
    raise SystemExit(main())
