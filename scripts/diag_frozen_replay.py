"""93.R3 — is the omitted envelope sampling, or context? Replay the FROZEN request, byte for byte.

Everything measured so far compared turns, and a turn is not a request: `classify_turn` puts the
runtime clock in the system message, so two runs of the same sentence send different bytes. The
independent review was right that "identical turns" was never shown, and that a probe which swaps a
module in the working tree can leave running code overwritten. This does neither — it captures the
request the router actually made, then calls the model again with exactly those bytes.

Three arms, each recording the sha256 of the request it sent:

  * **frozen**      the captured request, replayed unchanged N times. If the answers differ here, the
                    variance is in the model call itself, and no amount of prompt work will remove it.
  * **clock**       the same request with only the clock line rewritten. If frozen is stable and this
                    is not, a single moving token is enough to flip the decision.
  * **fresh**       a whole turn per repetition, as the product runs it — the upper bound that
                    includes every other source of difference.

What each outcome licenses is written in the report, not inferred afterwards.

    python scripts/diag_frozen_replay.py [repetitions]
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts")); sys.path.insert(0, ROOT)
from _bench_paths import SCRATCH, write_versioned  # noqa: E402
import bench_say_do as sd  # noqa: E402
from hmgfu import turn_router  # noqa: E402

TEACH = "In this project, ACME-7 means Atlas Control Mesh."
RUNTIME_HEADER = "=== AUTHORITATIVE RUNTIME CONTEXT"
BASE_INSTANT = "2026-09-11T12:20:00+00:00"     # the clock arm moves from here, a minute a step
CLOCK = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)(:[0-5]\d)?\b")


def _digest(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def _envelope(reply: str):
    try:
        return (json.loads(reply) or {}).get("memory_update")
    except Exception:
        return "__unparsed__"


def capture(engine, sid):
    """Run one real turn and keep the exact request the router sent."""
    seen = {}
    original = turn_router.classify_turn

    def spy(chat, parse, *a, **kw):
        def grab(role, messages, **kwargs):
            reply = chat(role, messages, **kwargs)
            seen.setdefault("first", {"role": role, "messages": messages, "kwargs": kwargs,
                                      "reply": reply})
            return reply
        return original(grab, parse, *a, **kw)

    turn_router.classify_turn = spy
    try:
        sd.turn(engine, sid, TEACH)
    finally:
        turn_router.classify_turn = original
    return seen.get("first")


def replay(engine, request, reps, mutate=None) -> list:
    """Send the captured request again, optionally mutating it, and record what came back."""
    out = []
    for i in range(reps):
        messages = json.loads(json.dumps(request["messages"]))
        if mutate is not None:
            messages = mutate(messages, i)
        payload = {"role": request["role"], "messages": messages, "kwargs": request["kwargs"]}
        reply = engine.sensitizer._chat(request["role"], messages, **request["kwargs"])
        out.append({"request_sha": _digest(payload), "envelope": _envelope(reply),
                    "raw_sha": hashlib.sha256((reply or "").encode()).hexdigest()[:16],
                    "raw_head": (reply or "")[:120]})
    return out


def _move_clock(messages, i):
    """Replace the runtime block with one built for a DIFFERENT, coherent instant.

    93.RR2: rewriting one regex match moved `now_local` while `local_time`, `now_utc` and
    `unix_seconds` stayed behind, so the arm sent a contradictory context and measured that rather
    than the passage of time. The block is regenerated whole, from a controlled instant."""
    from datetime import datetime, timedelta

    from hmgfu.runtime_context import RuntimeContext, router_prompt

    msgs = json.loads(json.dumps(messages))
    content = msgs[0]["content"]
    start = content.find(RUNTIME_HEADER)
    if start < 0:
        return msgs                                  # no runtime block to move: leave it untouched
    end = content.find(chr(10) + chr(10), start)
    end = len(content) if end < 0 else end
    moved = router_prompt(RuntimeContext.capture(
        datetime.fromisoformat(BASE_INSTANT) + timedelta(minutes=i + 1)))
    msgs[0]["content"] = content[:start] + moved + content[end:]
    return msgs


def main() -> int:
    reps = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 8
    os.makedirs(SCRATCH, exist_ok=True)
    db = os.path.join(SCRATCH, f"frozen_{os.getpid()}.db")
    if os.path.exists(db):
        os.remove(db)
    sqlite3.connect(db).close()
    e = sd.fresh_engine(db, None)
    e.settings.set("interactive_learning_mode", "confirm")
    request = capture(e, sd.new_session(e, "frozen-capture"))
    if not request:
        print("no router request captured — nothing to replay")
        return 1
    print(f"captured request: {_digest(request)} "
          f"({len(json.dumps(request['messages']))} chars, kwargs={sorted(request['kwargs'])})")
    print(f"clock line present: {bool(CLOCK.search(request['messages'][0]['content']))}")

    arms = {"frozen": replay(e, request, reps),
            "clock": replay(e, request, reps, mutate=_move_clock)}
    fresh = []
    for i in range(reps):
        got = capture(e, sd.new_session(e, f"frozen-fresh-{i}"))
        # 93.RR2: hash the REQUEST only, exactly as the replay arms do -- `_digest(got)` included the
        # reply, so `distinct_requests` measured a different thing here than in the other arms.
        fresh.append({"request_sha": _digest({"role": got["role"], "messages": got["messages"],
                                              "kwargs": got["kwargs"]}) if got else "",
                      "envelope": _envelope(got["reply"]) if got else None})
    arms["fresh"] = fresh

    print()
    summary = {}
    for name, rows in arms.items():
        hit = sum(1 for r in rows if isinstance(r["envelope"], dict))
        shas = {r["request_sha"] for r in rows}
        summary[name] = {"envelopes": hit, "n": len(rows), "distinct_requests": len(shas)}
        print(f"{name:7} envelope in {hit}/{len(rows)}   distinct requests sent: {len(shas)}")
    print("\nfrozen varying  -> the variance is in the model call, not in the prompt")
    print("frozen stable, clock varying -> one moving token flips the decision")
    print("both stable, fresh varying   -> something else in the turn differs")
    print("versioned:", write_versioned("frozen_replay", {"arms": arms, "summary": summary,
                                                          "request_sha": _digest(request)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
