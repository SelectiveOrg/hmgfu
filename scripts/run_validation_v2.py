"""94.7 — run the NEW pre-registered set, and record only what happened.

Same split as 93.V and for the same reason: this file produces raw material and judges nothing.
`judge_validation_v2.py` applies the declared oracles afterwards, so a change in a judge can never be
mistaken for a change in the system.

It is a separate runner rather than a flag on `run_validation.py` because it has to observe three
things the old one never did, and the frozen 93.V path must keep behaving byte-for-byte as it did when
its numbers were measured (Rule 11):

  * **what was offered, not just what ran.** `offered` cannot be read from the result — it is a local
    in `agent.py`. It CAN be read from the turn's own `context_pack` event, which since 94.5 reports
    REGISTERED and WITHHELD. `agent_chat` already takes an `emit` hook, so this needs no production
    change: the runner passes a collector and reads the trace the system already emits.
  * **the plan, whole.** Status, every step's status and evidence, and the authorisation record —
    which is what condition (a) is about: an invalid step must EXIT (clarify / revise / abandon)
    without losing the authorisation or renumbering the receipts.
  * **the artefact.** An episode that asks for a file is judged by reading the file. "write_file was
    called" is not "the file is right", and the user's instruction is explicit about the difference.

Isolation, unchanged from 93.V and extended: a throwaway DB per episode, and now a throwaway WORKSPACE
per episode too, so one episode's notes.md cannot satisfy another's post-condition.

    python scripts/run_validation_v2.py <arm> [rep] [id,id,...]

Writes outputs/validation_v2/<arm>-rep<N>.json.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts")); sys.path.insert(0, ROOT)
import bench_say_do as sd  # noqa: E402
from run_validation import _delta, _snapshot  # noqa: E402  (Rule 5: one definition of a store delta)
# 94.8: VAL_SET=chains runs the two pre-registered chains with the same runner; unset = the v2 set,
# exactly as before. One runner, one judge, two fixtures (Rule 5).
SET = os.environ.get("VAL_SET", "v2")
if SET == "chains":
    from validation_chains import EPISODES, PRIOR, WORKSPACE_SEED  # noqa: E402
elif SET == "v3":                      # 95: the first reserved gate-2 set (57a8918); DEV since 2026-09-13 (decision (a))
    from validation_episodes_v3 import EPISODES, PRIOR, WORKSPACE_SEED  # noqa: E402
elif SET == "v4":                      # 95: the second reserved gate-2 set (0e7525c); DEV since 2026-09-14 17:56
    from validation_episodes_v4 import EPISODES, PRIOR, WORKSPACE_SEED  # noqa: E402
elif SET == "v5":                      # 95: the third reserved gate-2 set, DEV since 2026-09-15 00:40
    from validation_episodes_v5 import EPISODES, PRIOR, WORKSPACE_SEED  # noqa: E402
elif SET == "v6":                      # 95: the fourth reserved gate-2 set, DEV since 2026-09-16 01:36
    from validation_episodes_v6 import EPISODES, PRIOR, WORKSPACE_SEED  # noqa: E402
elif SET == "v7":                      # 95: the fifth reserved gate-2 set, drafted blind; run only after 13/13 x3
    from validation_episodes_v7 import EPISODES, PRIOR, WORKSPACE_SEED  # noqa: E402
else:
    from validation_episodes_v2 import EPISODES, PRIOR, WORKSPACE_SEED  # noqa: E402
from hmgfu.turn_tail import wait_for_tail  # noqa: E402

OUT = os.path.join(ROOT, "outputs", "validation_v2" if SET == "v2" else f"validation_{SET}")


def _utilities(engine, values, keep=()) -> dict:
    """94.8: utility of every active point whose text carries one of `values` -- the "A gets no undue
    reinforcement" check compares this before and after the turn that answered B."""
    out = {}
    for p in engine.graph.all_points():
        if p.status != "active":
            continue
        text = (p.content + " " + (p.summary or "")).casefold()
        if any(str(v).casefold() in text for v in values):
            out[p.id] = {"utility": round(p.utility, 4), "type": p.type, "text": text[:80],
                         "has_new": any(str(v).casefold() in text for v in keep)}
    return out


def _receipts(db_path: str) -> list:
    """94.8: authorisation is per call and lives on the RECEIPT (not on the plan -- that was the
    instrument fault behind the withdrawn finding iii). Read straight from the episode DB."""
    try:
        c = sqlite3.connect(db_path)
        return [{"turn_seq": r[0], "tool": r[1], "effect": r[2], "authorization": r[3], "status": r[4]}
                for r in c.execute("SELECT turn_seq, tool, effect, authorization, status FROM receipts")]
    except sqlite3.Error:
        return []
WORK = os.path.join(sd.SCRATCH, "val_v2_workspaces")


def _plan_record(plan) -> dict:
    """The plan as the judge needs to see it. Whole, not summarised: condition (a) asks whether the
    authorisation and the receipts SURVIVED an exit, which cannot be read off a status alone."""
    if not isinstance(plan, dict):
        return {}
    return {
        "status": plan.get("status"),
        "title": plan.get("title"),
        "authorization": plan.get("authorization") if isinstance(plan.get("authorization"), dict) else None,
        "steps": [{"text": s.get("text", ""), "status": s.get("status"),
                   "note": s.get("note", ""), "evidence": s.get("evidence") or []}
                  for s in (plan.get("steps") or [])],
        "tools_used": plan.get("tools_used") or [],
    }


def _turn(engine, sid, message) -> dict:
    events: list = []
    before = _snapshot(engine)
    t0 = time.time()
    r = sd.turn(engine, sid, message, emit=events.append)
    wait_for_tail(engine)
    after = _snapshot(engine)

    packs = [e for e in events if e.get("type") == "context_pack"]
    pack = packs[-1] if packs else {}
    # 94.8: the whole event trace, trimmed -- router raw, nano/router fusion, protocol decisions,
    # writes, delivered context -- so one execution can be followed end to end from the record.
    event_trace = [{"type": e.get("type"), "data": json.dumps(e, ensure_ascii=False, default=str)[:600]}
                   for e in events]
    offered = sorted({t["name"] for t in (pack.get("tools") or []) + (pack.get("skills") or [])})
    trace = r.get("tool_trace") or []
    return {
        "message": message,
        "reply": r.get("response") or "",
        "tools": [t.get("name") for t in trace],
        "tools_ok": [t.get("name") for t in trace if not t.get("failed") and not t.get("blocked")],
        "tool_failures": [t.get("name") for t in trace if t.get("failed")],
        "tools_blocked": [t.get("name") for t in trace if t.get("blocked")],
        # 94.5's three states, from the system's own trace rather than re-derived here
        "offered": offered,
        "withheld": pack.get("withheld") or [],
        "registered": pack.get("registered"),
        "plan": _plan_record(r.get("plan")),
        "trace": event_trace,
        "secs": round(time.time() - t0, 2),
        "changes": _delta(before, after),
        "names": after.get("names", {}),
    }


def _workspace(ep_id: str) -> str:
    """A throwaway workspace per episode — X1's notes.md must not satisfy X3's plan.md."""
    path = os.path.join(WORK, ep_id)
    if os.path.exists(path):
        shutil.rmtree(path, ignore_errors=True)
    os.makedirs(path, exist_ok=True)
    for name, body in WORKSPACE_SEED.items():
        with open(os.path.join(path, name), "w", encoding="utf-8") as fh:
            fh.write(body)
    return path


def _artifacts(path: str) -> dict:
    """Every file the episode left behind, read. The judge checks CONTENT, not that a tool was called."""
    out = {}
    for root, _dirs, files in os.walk(path):
        for name in files:
            full = os.path.join(root, name)
            rel = os.path.relpath(full, path).replace("\\", "/")
            try:
                if os.path.getsize(full) > 200_000:
                    out[rel] = "(too large to record)"
                    continue
                with open(full, encoding="utf-8", errors="replace") as fh:
                    out[rel] = fh.read()[:8000]
            except OSError as exc:
                out[rel] = f"(unreadable: {exc})"
    return out


def run_episode(ep: dict, arm: str, rep: int) -> dict:
    db = os.path.join(sd.SCRATCH, f"valv2_{arm}_{rep}_{ep['id']}_{os.getpid()}.db")
    os.makedirs(os.path.dirname(db), exist_ok=True)
    if os.path.exists(db):
        os.remove(db)
    sqlite3.connect(db).close()
    workspace = _workspace(ep["id"])
    engine = sd.fresh_engine(db, None)
    engine.settings.set("interactive_learning_mode", "confirm")
    engine.settings.set("workspace_dir", workspace)      # after fresh_engine, which sets the shared one
    if ep.get("grader"):
        # 94.8: the app's effective configuration. bench_say_do turns the grader OFF for speed; a
        # claim about reinforcement is a claim ABOUT the grader and cannot be tested with it off.
        engine.settings.set("grader_enabled", True)
    watch = [v for v in (ep["expect"].get("not_reinforced") or [])]
    demote = [v for v in (ep["expect"].get("demoted") or [])]        # 95.2b: statuses at the end
    # the NEW values the episode allows: a point carrying one as well is a history/correction, not the old answer
    keep = [str(v) for r in (ep["expect"].get("allowed") or []) for v in [r.get("value")]
            if v and str(v) not in demote and str(v) not in watch]

    if ep["base"] == "conflicting":
        prior_sid = sd.new_session(engine, f"v2-{ep['id']}-prior")
        for line in PRIOR:
            sd.turn(engine, prior_sid, line)
        wait_for_tail(engine)

    sid = sd.new_session(engine, f"v2-{ep['id']}")
    steps = [_turn(engine, sid, message) for message in ep["steps"]]
    ask_sid = sd.new_session(engine, f"v2-{ep['id']}-new") if ep.get("new_session") else sid
    util_before = _utilities(engine, watch, keep) if watch else {}
    final = _turn(engine, ask_sid, ep["ask"])
    steps.append(final)
    util_after = _utilities(engine, watch, keep) if watch else {}
    stale = [{"status": p.status, "source": p.source, "text": (p.content or "")[:400],
              "has_new": any(v.casefold() in (p.content or "").casefold() for v in keep)}
             for p in engine.graph.all_points()
             if demote and any(str(v).casefold() in (p.content or "").casefold() for v in demote)
             and p.source in ("user", "assistant", "system")] if demote else []

    try:
        widgets = [{"title": w.get("title", ""), "type": w.get("type", ""),
                    "props": json.dumps(w.get("props") or {}, ensure_ascii=False, default=str)[:400]}
                   for s in {sid, ask_sid} for w in engine.sessions.widgets(s)]
    except Exception:
        widgets = []

    out = {"id": ep["id"], "axis": ep["axis"], "lang": ep["lang"], "base": ep["base"],
           "new_session": bool(ep.get("new_session")), "steps": steps,
           "artifacts": _artifacts(workspace), "widgets": widgets,
           "seeded": sorted(WORKSPACE_SEED),
           "receipts": _receipts(db), "utility_before": util_before, "utility_after": util_after,
           "stale_points": stale,
           "secs": round(sum(s["secs"] for s in steps), 2)}
    print(f"  {ep['id']:4} {ep['axis']:9} {ep['lang']} {ep['base']:12} {out['secs']:6.1f}s  "
          f"{len(final['reply']):4} chars  {len(final['changes'])} changes  "
          f"{len(out['artifacts'])} files  {len(widgets)} widgets", flush=True)
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
    payload = {"arm": arm, "rep": rep, "head": head, "set": SET, "episodes": rows,
               "wall_secs": round(time.time() - t0, 1),
               "model": str(getattr(sd, "CHAT_MODEL", "")) or os.environ.get("HMGFU_BENCH_CHAT_MODEL", "")}
    path = os.path.join(OUT, f"{arm}-rep{rep}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
    print(f"\n{len(rows)} episodes in {payload['wall_secs']}s -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
