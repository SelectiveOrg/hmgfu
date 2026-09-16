"""P-AUDIT-2 clean re-measure — isolate the CHAT PERCEIVER. The full-turn run was infra-contaminated
(18/39 turns' correction call thrashed the embedder out of VRAM and fell back to nano). The thing under
test is just grader._detect_correction_via_chat + the _correction_grounded gate — exactly what decides
the correction signal in a live turn. Calling it directly (one gemma4 call per beat; no retrieval embed,
no reply generation, no gemma-cpu grade) keeps gemma4 resident → stable, removing the infra noise while
measuring the SAME function. Inputs are faithful: the beat's real message + the reply the full run
actually produced (from the log). Facts-context is [] (slightly conservative — with recalled facts the
perceiver could only do better). Emits a source-tagged log the existing auditor reads.

  HMGFU_CHAT_CORRECTION_SIGNAL=1 python scripts/paudit_isolate.py --beatsheet scripts/paudit_beatsheet_2.json \
      --fullrun scratch/paudit2_log.jsonl --db scratch/paudit2_isolate.db --log scratch/paudit2_iso_log.jsonl
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
from hmgfu.grader import _detect_correction_via_chat, _correction_grounded   # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--beatsheet", required=True)
    ap.add_argument("--fullrun", required=True, help="the full-run JSONL log (message + reply per beat)")
    ap.add_argument("--db", required=True)
    ap.add_argument("--log", required=True)
    args = ap.parse_args()

    if Path(args.db).resolve() == Path(config.DB_PATH).resolve():
        print(f"REFUSING: --db is the production DB", file=sys.stderr)
        return 2

    beats = json.loads(Path(args.beatsheet).read_text(encoding="utf-8"))["beats"]
    turn = {}
    for line in Path(args.fullrun).read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            turn[r.get("beat_id")] = {"message": r.get("message") or "", "reply": r.get("reply") or ""}

    engine = AgentEngine(db_path=args.db)
    engine.sensitizer.enabled = False   # keep only gemma4 in play → stable, no embedder churn

    log_path = Path(args.log)
    log_path.write_text("", encoding="utf-8")
    for b in beats:
        t = turn.get(b["id"], {"message": "", "reply": ""})
        msg, reply = t["message"], t["reply"]
        rec = {"beat_id": b["id"], "is_correction": bool(b["is_correction"]), "style": b.get("style"),
               "kind": b.get("kind"), "correction_detected": None, "correction_source": "chat", "error": None}
        corr, last = None, None
        for _ in range(3):   # beat-level retry (the chat call also retries internally)
            try:
                corr = _detect_correction_via_chat(engine, msg, reply, "")
                last = None
                break
            except Exception as exc:
                last = f"{type(exc).__name__}: {exc}"
        if last:
            rec["error"] = last
        else:
            rec["correction_detected"] = bool(corr is not None and _correction_grounded(corr, msg))
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        flag = "CORR!" if rec["correction_detected"] else ("err" if rec["error"] else "-")
        print(f"[{b['id']}|gt_corr={int(rec['is_correction'])}|{flag}] {rec['error'] or msg[:70]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
