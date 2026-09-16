"""93.V — run the 24 pre-registered episodes in ONE build, and record only what happened.

Deliberately split from the judging. This file produces raw material — every reply, every store
delta, every tool call, every timing — and judges nothing. `judge_validation.py` then applies the
declared oracles to BOTH arms' artefacts with one set of judges, in one build.

That split is what makes the comparison fair. The baseline arm runs in a git worktree at an older
commit, where the new judges do not exist and the old ones differ; if each arm judged itself, a
change in the judge would be indistinguishable from a change in the system. So the runner imports
nothing from this phase's work: `bench_say_do` and the engine, and a local snapshot/delta so it does
not even depend on `learning_oracle` being present.

    python scripts/run_validation.py <arm-name> [repetition]

Writes outputs/validation/<arm>-rep<N>.json. Fixtures are identical across arms by construction:
the episode list is copied into the worktree, the bases are built from it, and nothing is read from
the developer's own history.
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts")); sys.path.insert(0, ROOT)
import bench_say_do as sd  # noqa: E402
from validation_episodes import EPISODES, PRIOR  # noqa: E402
from hmgfu.turn_tail import wait_for_tail  # noqa: E402

OUT = os.path.join(ROOT, "outputs", "validation")


def _snapshot(engine) -> dict:
    """Every write-visible store. Local on purpose: the baseline tree need not have the same helper."""
    try:
        facts = {r["key"]: r.get("value") for r in engine.facts.active()}
    except Exception:
        facts = {}
    try:
        assertions = {f"{r.get('entity_id')}|{r.get('relation')}": r.get("value")
                      for r in engine.facts.assertions.active()}
    except Exception:
        assertions = {}
    try:
        directives = {r["kind"]: r.get("value") for r in engine.directives.active()}
    except Exception:
        directives = {}
    try:
        names = {e["id"]: e.get("name") or "" for e in engine.facts.assertions.entities()}
    except Exception:
        names = {}
    return {"facts": facts, "assertions": assertions, "directives": directives, "names": names}


def _delta(before: dict, after: dict) -> list:
    out = []
    for store in ("facts", "assertions", "directives"):
        b, a = before.get(store, {}), after.get(store, {})
        for key in sorted(set(a) | set(b)):
            if b.get(key) != a.get(key):
                out.append([store, str(key), b.get(key), a.get(key)])
    return out


def _turn(engine, sid, message):
    before = _snapshot(engine)
    t0 = time.time()
    r = sd.turn(engine, sid, message)
    wait_for_tail(engine)
    after = _snapshot(engine)
    return {"message": message, "reply": r.get("response") or "",
            "tools": [t.get("name") for t in (r.get("tool_trace") or [])],
            "tool_failures": [t.get("name") for t in (r.get("tool_trace") or [])
                              if t.get("failed") or t.get("blocked")],
            "secs": round(time.time() - t0, 2), "changes": _delta(before, after),
            "names": after.get("names", {})}


def run_episode(ep: dict, arm: str, rep: int) -> dict:
    db = os.path.join(sd.SCRATCH if hasattr(sd, "SCRATCH") else OUT,
                      f"val_{arm}_{rep}_{ep['id']}_{os.getpid()}.db")
    os.makedirs(os.path.dirname(db), exist_ok=True)
    if os.path.exists(db):
        os.remove(db)
    sqlite3.connect(db).close()
    engine = sd.fresh_engine(db, None)
    engine.settings.set("interactive_learning_mode", "confirm")

    steps = []
    if ep["base"] == "conflicting":
        prior_sid = sd.new_session(engine, f"val-{ep['id']}-prior")
        for line in PRIOR:
            sd.turn(engine, prior_sid, line)
        wait_for_tail(engine)

    sid = sd.new_session(engine, f"val-{ep['id']}")
    for message in ep["steps"]:
        steps.append(_turn(engine, sid, message))
    ask_sid = sd.new_session(engine, f"val-{ep['id']}-new") if ep.get("new_session") else sid
    final = _turn(engine, ask_sid, ep["ask"])
    steps.append(final)
    out = {"id": ep["id"], "family": ep["family"], "lang": ep["lang"], "base": ep["base"],
           "new_session": bool(ep.get("new_session")), "steps": steps,
           "secs": round(sum(s["secs"] for s in steps), 2)}
    print(f"  {ep['id']:6} {ep['lang']} {ep['base']:12} {out['secs']:6.1f}s  "
          f"{len(final['reply']):4} chars  {len(final['changes'])} changes", flush=True)
    return out


def main() -> int:
    arm = sys.argv[1] if len(sys.argv) > 1 else "candidate"
    rep = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    only = sys.argv[3].split(",") if len(sys.argv) > 3 else None
    episodes = [e for e in EPISODES if not only or e["id"] in only]
    os.makedirs(OUT, exist_ok=True)
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()
    print(f"arm={arm} rep={rep} head={head} episodes={len(episodes)}", flush=True)
    t0 = time.time()
    rows = [run_episode(ep, arm, rep) for ep in episodes]
    payload = {"arm": arm, "rep": rep, "head": head, "episodes": rows,
               "wall_secs": round(time.time() - t0, 1),
               "model": str(getattr(sd, "CHAT_MODEL", "")) or os.environ.get("HMGFU_BENCH_CHAT_MODEL", "")}
    path = os.path.join(OUT, f"{arm}-rep{rep}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
    print(f"\n{len(rows)} episodes in {payload['wall_secs']}s -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
