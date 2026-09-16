"""93.Q2 — re-judge the clarification runs already on disk, before spending GPU again.

The review of 93.P asks for exactly this in that order: *"Reavalia respostas completas e alterações
exatas antes de repetir GPU; se os artefactos forem insuficientes, declarar essa lacuna."* The runs
were scored by `bool(changes)` and by `"project" in reply`, and both of those are recorded in the
artefacts alongside the raw material — the deltas and the replies — so the strict judges can be run
over them without touching a model.

It reports three numbers per run and, where the artefact cannot support a verdict, says so instead of
producing one. The 140-character truncation of `reply` is one such gap and it is named in the output:
a reply cut mid-sentence can be judged NO but never safely judged YES.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from answer_oracle import answered  # noqa: E402

RUNS = ROOT / "outputs" / "runs"
SUBJECT = "Nimbus"
# what the probe taught, in the words it taught it in
VALUE = "the name of my current project"
TRUNCATED_AT = 140


def _rows(path: Path) -> list:
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("rows") or []
    except Exception:
        return []


def _exact_writes(changes) -> list:
    """The changes that wrote EXACTLY the taught value, whichever adapter wrote them.

    An earlier draft of this file looked only for `definition.meaning` and reported 0/27, which was
    an instrument error of the same family it was built to catch: the runs DID write the right value,
    through the personal-fact adapter (`project.main = Nimbus`), and a judge that knows only one
    store cannot see it. What matters is that the value is exact and the key names the target — the
    store it landed in is reported, not required."""
    out = []
    for change in changes or []:
        store, key, _old, new = (list(change) + [None] * 4)[:4]
        if " ".join(str(new or "").split()).casefold() == SUBJECT.casefold():
            out.append((str(store), str(key), str(new)))
    return out


def judge(row: dict) -> dict:
    """What this recorded run supports, and what it cannot."""
    steps = row.get("steps") or []
    named = steps[2] if len(steps) > 2 else {}
    recall = steps[5] if len(steps) > 5 else {}
    reply = str(recall.get("reply") or "")
    verdict = answered(reply, subject=SUBJECT, value=VALUE)
    writes = _exact_writes(named.get("changes"))
    # the old gates, recomputed from the same artefact so the two can be compared line by line
    old_wrote = bool(named.get("changes"))
    old_applied = "project" in reply.lower()
    truncated = len(reply) >= TRUNCATED_AT
    return {"rep": row.get("rep"), "answer": row.get("answer"),
            "old_named_wrote": old_wrote, "old_applied": old_applied,
            "exact_writes": writes,
            # which mechanism actually wrote: `pass_through` means the ORDINARY ingest did it and the
            # clarification cycle was not what closed. That distinction is the whole finding.
            "action": named.get("action"), "bare_action": (steps[1] or {}).get("action"),
            "strict_named_wrote": bool(writes),
            "strict_applied": bool(verdict["ok"]),
            "why": verdict["why"],
            "unsupported": (truncated and not verdict["ok"]),
            "reply": reply}


def main() -> int:
    paths = sorted(RUNS.glob("*/clarification.json"))
    if not paths:
        print("no clarification artefacts on disk")
        return 1
    print(f"{len(paths)} clarification artefacts\n")
    totals = {"rows": 0, "old_wrote": 0, "strict_wrote": 0, "old_applied": 0, "strict_applied": 0,
              "unsupported": 0}
    for path in paths:
        rows = _rows(path)
        if not rows:
            continue
        verdicts = [judge(r) for r in rows]
        print(f"-- {path.parent.name}")
        for v in verdicts:
            totals["rows"] += 1
            for a, b in (("old_wrote", "old_named_wrote"), ("strict_wrote", "strict_named_wrote"),
                         ("old_applied", "old_applied"), ("strict_applied", "strict_applied")):
                totals[a] += bool(v[b])
            totals["unsupported"] += bool(v["unsupported"])
            flag = "" if v["old_applied"] == v["strict_applied"] else "   <-- the gates disagree"
            print(f"   rep {v['rep']} answer={str(v['answer']):6} "
                  f"wrote: old={int(v['old_named_wrote'])} strict={int(v['strict_named_wrote'])}  "
                  f"applied: old={int(v['old_applied'])} strict={int(v['strict_applied'])}"
                  f"  ({v['why']}){flag}")
            print(f"        the bare answer was {v['bare_action']}, the named answer "
                  f"{v['action']}")
            for store, key, new in v["exact_writes"]:
                print(f"        wrote {store}.{key} = {new!r}")
            if v["unsupported"]:
                print("        the recorded reply is truncated at 140 characters: a NO here is "
                      "supported, a YES could not have been")
    print(f"\nover {totals['rows']} recorded runs")
    print(f"  the named answer wrote something:  old {totals['old_wrote']}  "
          f"strict (EXACTLY the taught value) {totals['strict_wrote']}")
    print(f"  a new session applied it:          old {totals['old_applied']}  "
          f"strict (ASSERTED of Nimbus) {totals['strict_applied']}")
    print(f"  verdicts the artefact cannot support: {totals['unsupported']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
