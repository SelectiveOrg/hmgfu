"""93.V — judge both arms' artefacts with ONE set of oracles, and report the pre-registered gate.

Separate from the runner on purpose. The baseline arm runs in a worktree at an older commit, where
the judges are older or absent; if each arm judged itself, a change in the judge would be
indistinguishable from a change in the system. So the running produced raw material only, and this
applies the same declared oracles to both.

Nothing here may add a criterion. Every check comes from the episode's own `expect`, fixed in
`validation_episodes.py` before any result was seen, and an episode is COMPLETE only when all of them
hold.

94.1: this docstring used to end "no partial credit, because a run that writes the right fact and also
invents one has not done the episode". That was FALSE of the code — REVIEW_93QV showed F5-1 passing
with the correct write plus `identity.name='INVENTED-PERSON'` and `why: []`, because nothing looked
at writes outside the episode's small `forbidden_values` list. An episode now gets that guarantee by
declaring `allowed`, which opts it into a strict check over every other write (reusing
`learning_oracle.undue_writes`). It is opt-in so the frozen 93.V set still scores as it was measured;
the frozen set therefore does NOT have this guarantee, and its published numbers should be read with
that in mind.

    python scripts/judge_validation.py outputs/validation/baseline-rep1.json ... --candidate ...
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts")); sys.path.insert(0, ROOT)
from answer_oracle import answered  # noqa: E402
from learning_oracle import undue_writes  # noqa: E402
from validation_episodes import EPISODES, FAMILIES  # noqa: E402

BY_ID = {e["id"]: e for e in EPISODES}


def _norm(value) -> str:
    return " ".join(str(value or "").split()).casefold()


def _wrote(changes, names, store_sub, key_sub, value) -> bool:
    """A change in that store whose key names the target and whose NEW value is exactly this.

    The key is matched against the readable entity name where there is one, because an assertion's
    key is an opaque `definition:<hash8>` and the identity lives in the entities table."""
    for store, key, _old, new in changes or []:
        if store_sub and store_sub not in str(store):
            continue
        entity = str(key).split("|", 1)[0]
        readable = f"{names.get(entity, '')} {key}"
        if key_sub and _norm(key_sub) not in _norm(readable):
            continue
        if _norm(new) == _norm(value):
            return True
        if "directives" in str(store) and _norm(value) and _norm(value) in _norm(new):   # J6: a directive holds the
            return True                                                                  # requested style in the user's words
    return False


def judge(row: dict) -> dict:
    """Everything the episode declared, checked. `why` lists what failed, in order."""
    ep = BY_ID[row["id"]]
    want = ep["expect"]
    steps, final = row["steps"], row["steps"][-1]
    changes = [c for s in steps for c in s["changes"]]
    names = final.get("names") or {}
    reply = final["reply"]
    why = []

    for store_sub, key_sub, value in want.get("writes") or []:
        if not _wrote(changes, names, store_sub, key_sub, value):
            why.append(f"did not write {value!r} to {store_sub}:{key_sub or '*'}")
    for value in want.get("forbidden_values") or []:
        if any(_norm(new) == _norm(value) for _s, _k, _o, new in changes):
            why.append(f"wrote the forbidden value {value!r}")
    if want.get("no_writes") and changes:
        why.append(f"wrote {len(changes)} change(s) where none was allowed")
    if want.get("answer"):
        got = answered(reply, **want["answer"])
        if not got["ok"]:
            why.append(f"the answer did not assert it ({got['why']})")
    if want.get("answer_absent"):
        got = answered(reply, **want["answer_absent"])
        if got["ok"]:
            why.append("the answer asserted something it must not have")
    # 94.1: every OTHER write, not just the forbidden values this episode happened to think of.
    # REVIEW_93QV showed F5-1 passing with the correct `response_style` write AND
    # `identity.name='INVENTED-PERSON'`, `why: []` -- while the docstring above claimed exactly that
    # could not happen. `allowed` is opt-in so the FROZEN 93.V set scores as it was measured (Rule 11),
    # and the meaning of "undue" is `learning_oracle`'s, not a second one grown here (Rule 5).
    if want.get("allowed") is not None:
        permitted = list(want["allowed"])
        for store_sub, key_sub, value in want.get("writes") or []:
            rule = {"value": value}
            if store_sub:
                rule["store"] = store_sub
            permitted.append(rule)
        for store, key, _old, new in undue_writes(changes, permitted):
            why.append(f"undue write: {store}.{key} = {new!r}")

    return {"id": row["id"], "family": row["family"], "lang": row["lang"], "base": row["base"],
            "complete": not why, "why": why, "secs": row["secs"],
            "turns": len(steps), "tool_failures": sum(len(s["tool_failures"]) for s in steps)}


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def summarise(payload) -> dict:
    verdicts = [judge(r) for r in payload["episodes"]]
    done = sum(1 for v in verdicts if v["complete"])
    return {"arm": payload["arm"], "rep": payload["rep"], "head": payload.get("head"),
            "complete": done, "n": len(verdicts), "verdicts": verdicts,
            "wall_secs": payload.get("wall_secs"),
            "median_secs": sorted(v["secs"] for v in verdicts)[len(verdicts) // 2] if verdicts else 0}


def main() -> int:
    paths = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not paths:
        print(__doc__)
        return 1
    runs = [summarise(load(p)) for p in paths]
    by_arm = {}
    for run in runs:
        by_arm.setdefault(run["arm"], []).append(run)

    for run in runs:
        print(f"\n== {run['arm']} rep{run['rep']}  ({run['head']})  "
              f"{run['complete']}/{run['n']} complete  median {run['median_secs']}s/episode  "
              f"wall {run['wall_secs']}s")
        for v in run["verdicts"]:
            mark = "ok " if v["complete"] else "XX "
            print(f"   {mark}{v['id']:6} {v['lang']} {v['base']:12} {'; '.join(v['why'])[:110]}")

    print("\n-- by family --")
    for fam, label in FAMILIES.items():
        line = f"  {fam} {label:48}"
        for arm, got in sorted(by_arm.items()):
            for run in got:
                n = [v for v in run["verdicts"] if v["family"] == fam]
                line += f"  {arm[:4]}r{run['rep']} {sum(1 for v in n if v['complete'])}/{len(n)}"
        print(line)

    print("\n-- the pre-registered gate --")
    base = by_arm.get("baseline") or []
    cand = by_arm.get("candidate") or []
    if not base or not cand:
        print("   both arms are needed before the gate means anything; "
              f"have baseline x{len(base)}, candidate x{len(cand)}")
        return 0
    for i, (b, c) in enumerate(zip(sorted(base, key=lambda r: r["rep"]),
                                   sorted(cand, key=lambda r: r["rep"])), start=1):
        gain = c["complete"] - b["complete"]
        print(f"   rep{i}: candidate {c['complete']}/{c['n']}  baseline {b['complete']}/{b['n']}  "
              f"paired gain {gain:+d}   >=20/24: {'YES' if c['complete'] >= 20 else 'NO'}   "
              f"gain > 0: {'YES' if gain > 0 else 'NO'}")
    lost = [v["id"] for c in cand for v in c["verdicts"] if not v["complete"]]
    print(f"   episodes the candidate did not complete: {sorted(set(lost))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
