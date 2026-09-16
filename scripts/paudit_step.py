"""P-AUDIT turn driver — runs a batch of simulator turns through the LIVE agent on a THROWAWAY DB and
records, per turn, whether the grader classified it as a CORRECTION. The Regulator flag stays OFF
(config default) so this is pure grader-perception (the correction machinery runs regardless — see
grader.py:102). Production hmgfu.db is NEVER touched (throwaway DB in scratch/).

Reads a turns file: [{beat_id, is_correction, style, kind, message}, ...] and APPENDS to the tagged log
one record per turn: {beat_id, is_correction, style, kind, message, reply, correction_detected,
conflicts_marked, ingested, error}. The grader never sees the beat labels — it only sees the message.
State (graph + session) persists across invocations via the throwaway DB + fixed session_id, so I can
drive the audit in small adaptive batches.

  python scripts/paudit_step.py --db scratch/paudit.db --session paudit --turns scratch/turns.json \
      --log scratch/paudit_log.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hmgfu import config          # noqa: E402
from hmgfu.agent import AgentEngine   # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--session", default="paudit")
    ap.add_argument("--turns", required=True, help="JSON file: list of {beat_id,is_correction,style,kind,message}")
    ap.add_argument("--log", required=True, help="JSONL log to APPEND to")
    args = ap.parse_args()

    # HARD GUARD: never run against the production DB.
    prod = Path(config.DB_PATH).resolve()
    if Path(args.db).resolve() == prod:
        print(f"REFUSING: --db is the production DB {prod}", file=sys.stderr)
        return 2

    turns = json.loads(Path(args.turns).read_text(encoding="utf-8"))
    if config.REGULATOR_ENABLED:
        print("NOTE: REGULATOR_ENABLED is True — audit still valid (grader is decoupled) but flag "
              "should be OFF for a clean shadow run.", file=sys.stderr)

    engine = AgentEngine(db_path=args.db)
    # audit at PRODUCTION grader config (the thing under test); grader_enabled defaults True.
    if not engine.settings.get("grader_enabled"):
        engine.settings.set("grader_enabled", True)
    # P-AUDIT-2 STABILITY (VRAM): under 4-model pressure the extra gemma4:12b correction call thrashed
    # the embedder out of VRAM (empty-embed failures + silent chat→nano fallback, seen via
    # correction_source). Free the nano sensitizer (qwen ~2GB GPU) — it is NOT on the correction path
    # (the correction is read from the raw message + reply by the chat model); it only affects ingest
    # extraction quality. This is a harness-side isolation, documented — it does not change the metric.
    try:
        engine.sensitizer.enabled = False
    except Exception:
        pass

    log_path = Path(args.log)
    out = []
    for t in turns:
        rec = {"beat_id": t.get("beat_id"), "is_correction": bool(t.get("is_correction")),
               "style": t.get("style"), "kind": t.get("kind"), "message": t.get("message"),
               "reply": None, "correction_detected": None, "conflicts_marked": None,
               "ingested": None, "error": None}
        try:
            result = engine.agent_chat(t["message"], explicit=False, session_id=args.session)
            grade = (result or {}).get("grade") or {}
            corr = grade.get("correction")
            rec["reply"] = (result or {}).get("response")
            rec["correction_detected"] = bool(corr)
            rec["conflicts_marked"] = (corr or {}).get("conflicts_marked")
            rec["ingested"] = (corr or {}).get("ingested")
            rec["grade_source"] = grade.get("source")
            rec["correction_source"] = grade.get("correction_source")   # P-AUDIT-2: chat | nano
        except Exception as exc:   # a turn error must not abort the run; record it
            rec["error"] = f"{type(exc).__name__}: {exc}"
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        out.append(rec)

    # compact echo for the live simulator (me) to adapt the next batch
    for rec in out:
        reply = (rec["reply"] or rec["error"] or "")[:220].replace("\n", " ")
        flag = "CORR!" if rec["correction_detected"] else ("err" if rec["error"] else "-")
        src = rec.get("correction_source") or "?"
        print(f"[{rec['beat_id']}|gt_corr={int(rec['is_correction'])}|grader={flag}|{src}] {reply}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
