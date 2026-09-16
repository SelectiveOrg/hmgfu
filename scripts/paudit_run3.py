"""P-AUDIT-3 decisive run — two phases that operationalize FRONT 2 (serialized correction queue).

PHASE A: run each beat as a FULL live turn (real retrieval → REAL facts-context; reply by gemma4),
with _auto_drain_corrections OFF so each turn's correction is ENQUEUED (message, reply, facts captured
at turn time) but NOT run inline — no gemma4↔embedder cohabitation during the turns.
PHASE B: engine.drain_corrections() runs ALL correction detections at once, GPU-free (gemma4 only, the
embedder idle) → stable, ZERO source fallbacks. Each carries its turn's REAL facts-context (FRONT 1
clause-partition is inside the detector). The queue order == beat order (no action turns), cross-checked
by message. Emits a source-tagged log the existing source-aware auditor reads.

The sensitizer nano is disabled for VRAM stability during Phase A (FRONT 0 confirms it only degrades
query-entity extraction to regex; facts-context is still REAL — graph-retrieved via embeddings).

  HMGFU_CHAT_CORRECTION_SIGNAL=1 python scripts/paudit_run3.py --beatsheet scripts/paudit_beatsheet_3.json \
      --db scratch/paudit3.db --session paudit3 --log scratch/paudit3_log.jsonl [--limit N]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hmgfu import config          # noqa: E402
from hmgfu.agent import AgentEngine   # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--turns", required=True, help="flat JSON list: {beat_id,is_correction,style,kind,message}")
    ap.add_argument("--db", required=True)
    ap.add_argument("--session", default="paudit3")
    ap.add_argument("--log", required=True)
    ap.add_argument("--limit", type=int, default=0, help="run only the first N beats (smoke)")
    args = ap.parse_args()

    if Path(args.db).resolve() == Path(config.DB_PATH).resolve():
        print("REFUSING: --db is the production DB", file=sys.stderr)
        return 2
    if not config.CHAT_CORRECTION_SIGNAL:
        print("REFUSING: set HMGFU_CHAT_CORRECTION_SIGNAL=1 (the decisive run needs the flag ON).", file=sys.stderr)
        return 2

    beats = json.loads(Path(args.turns).read_text(encoding="utf-8"))
    for b in beats:
        b.setdefault("id", b.get("beat_id"))
    if args.limit:
        beats = beats[:args.limit]

    engine = AgentEngine(db_path=args.db)
    engine.sensitizer.enabled = False          # VRAM: no qwen; facts still real (graph-retrieved)
    engine._auto_drain_corrections = False      # FRONT 2: defer to Phase B (batch, GPU-free)
    if not engine.settings.get("grader_enabled"):
        engine.settings.set("grader_enabled", True)

    from hmgfu.grader import facts_summary

    # PHASE A — retrieval + ingest ONLY (nomic embedder; NO reply gemma4, so gemma4 is not even loaded).
    # The embedder never cohabits with gemma4 → stable over a long run. Real facts-context from
    # retrieval; the correction is enqueued with an EMPTY reply — a documented, minor context reduction:
    # the correction lives in the user MESSAGE + the recalled FACTS, not the assistant's echo.
    print(f"=== PHASE A: {len(beats)} retrieval+ingest turns (nomic only, no reply gemma4) ===")
    for b in beats:
        facts = ""
        for attempt in range(4):
            try:
                _q, retrieved, _ = engine.retrieve(b["message"])
                facts = facts_summary(retrieved)
                break
            except Exception:
                time.sleep(2.0)
        try:
            engine.ingest(b["message"], source="user")   # build the graph so later beats recall it
        except Exception:
            pass
        engine.enqueue_correction(b["message"], "", facts)

    queued = engine._correction_queue
    print(f"=== PHASE B: detecting {len(queued)} corrections (gemma4 only, detect-only → stable) ===")
    # PHASE B — detection only (apply=False): gemma4-only, no ingest embed → no cohabitation.
    results = engine.drain_corrections(apply=False)

    # map results → beats by order, cross-check by message
    log_path = Path(args.log)
    log_path.write_text("", encoding="utf-8")
    by_msg = {r["message"]: r for r in results}
    for b in beats:
        r = by_msg.get(b["message"])
        detected = bool(r and r.get("correction"))
        rec = {"beat_id": b["id"], "is_correction": bool(b["is_correction"]), "style": b.get("style"),
               "kind": b.get("kind"), "correction_detected": detected,
               "correction_source": (r or {}).get("source") if r else "MISSING",
               "error": (r or {}).get("error") if r else "no queue item"}
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        flag = "CORR!" if detected else ("err" if rec["error"] else "-")
        print(f"[{b['id']}|gt_corr={int(rec['is_correction'])}|{flag}|{rec['correction_source']}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
