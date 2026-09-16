"""P-AUDIT auditor — compares the tagged turn log against the committed beat sheet and applies the
PRE-COMMITTED bars. Ground truth = beat sheet is_correction (the grader never saw it).

  correction-recall = detected / total, over is_correction=True beats            bar >= 0.90
  ghost-corrections = # is_correction=False beats the grader flagged as correction  bar <= 1

Also reports the FULL matrix by correction STYLE (a passing global recall can hide all-implicits
failing) and the false-positive breakdown by non-correction KIND (ghost/praise/silence).

  python scripts/paudit_audit.py --log scratch/paudit_log.jsonl --beatsheet scripts/paudit_beatsheet.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RECALL_BAR = 0.90
GHOST_BAR = 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True)
    ap.add_argument("--beatsheet", default=str(Path(__file__).with_name("paudit_beatsheet.json")))
    args = ap.parse_args()

    sheet = json.loads(Path(args.beatsheet).read_text(encoding="utf-8"))
    beats = {b["id"]: b for b in sheet["beats"]}
    records = [json.loads(line) for line in Path(args.log).read_text(encoding="utf-8").splitlines() if line.strip()]

    # de-dup by beat_id keeping the LAST record (a re-run appends; the last is authoritative)
    by_beat = {}
    for r in records:
        by_beat[r.get("beat_id")] = r

    errors = [r for r in by_beat.values() if r.get("error")]
    missing = [bid for bid in beats if bid not in by_beat]

    # source-aware: with the flag ON and no action turns, correction_source=="nano" means the CHAT
    # call fell back to nano (VRAM contamination) — those turns do NOT measure the chat perceiver.
    corr = {"all": [0, 0], "chat": [0, 0]}          # [detected, total] per scope
    style_hit = defaultdict(lambda: [0, 0])          # style -> [chat_hit, chat_tot] (chat-source only)
    ghost_hits, ghost_chat_hits = [], []
    kind_fp = defaultdict(int)
    kind_tot = defaultdict(int)
    fn_beats = []
    nano_fallback = []                               # beats where the strong perceiver fell back to nano

    for bid, b in beats.items():
        r = by_beat.get(bid)
        if r is None or r.get("error"):
            continue
        detected = bool(r.get("correction_detected"))
        source = r.get("correction_source")
        if source == "nano":
            nano_fallback.append(bid)
        if b["is_correction"]:
            corr["all"][1] += 1
            corr["all"][0] += int(detected)
            if source == "chat":
                corr["chat"][1] += 1
                corr["chat"][0] += int(detected)
                style = b.get("style", "?")
                style_hit[style][1] += 1
                style_hit[style][0] += int(detected)
            elif not detected:
                fn_beats.append((bid, b.get("style"), "nano-fallback"))
            if not detected and source == "chat":
                fn_beats.append((bid, b.get("style"), b.get("target")))
        else:
            kind = b.get("kind", "?")
            kind_tot[kind] += 1
            if detected:
                ghost_hits.append((bid, kind, source))
                kind_fp[kind] += 1
                if source == "chat":
                    ghost_chat_hits.append((bid, kind))

    recall_all = corr["all"][0] / corr["all"][1] if corr["all"][1] else 0.0
    recall_chat = corr["chat"][0] / corr["chat"][1] if corr["chat"][1] else 0.0
    ghost_chat = len(ghost_chat_hits)

    print("=== P-AUDIT-2 — chat-perceiver grader audit (ground truth = committed beat sheet) ===")
    print(f"beats {len(beats)} | logged {len(by_beat)} | missing {len(missing)} | errors {len(errors)}")
    print(f"CONTAMINATION (chat→nano fallback, VRAM): {len(nano_fallback)} turns {nano_fallback}")
    print(f"\nCORRECTION-RECALL (chat-source, the valid measurement): {corr['chat'][0]}/{corr['chat'][1]} "
          f"= {recall_chat:.3f}   (bar >= {RECALL_BAR})")
    print(f"  as-run incl. nano fallbacks: {corr['all'][0]}/{corr['all'][1]} = {recall_all:.3f}")
    print("  by style (chat-source):")
    for style in ("explicit", "implicit", "buried", "mixed"):
        hit, tot = style_hit.get(style, [0, 0])
        print(f"    {style:9s}: {hit}/{tot} = {(hit / tot) if tot else float('nan'):.3f}")
    if fn_beats:
        print(f"  MISSED / fell-back: {fn_beats}")
    print(f"\nGHOST-CORRECTIONS (chat-source): {ghost_chat}   (bar <= {GHOST_BAR})")
    if ghost_hits:
        print(f"  all ghost hits (bid,kind,source): {ghost_hits}")
    print("  false-positive by kind (any source):")
    for kind in ("ghost", "praise", "silence", "setup"):
        if kind_tot.get(kind):
            print(f"    {kind:8s}: {kind_fp.get(kind, 0)}/{kind_tot[kind]}")

    clean = not missing and not errors and not nano_fallback
    recall_pass = recall_chat >= RECALL_BAR
    ghost_pass = ghost_chat <= GHOST_BAR
    print("\n=== DECISION (pre-committed bars, on the chat perceiver) ===")
    print(f"  correction-recall >= {RECALL_BAR}: {recall_pass} ({recall_chat:.3f})")
    print(f"  ghost-corrections <= {GHOST_BAR}: {ghost_pass} ({ghost_chat})")
    print(f"  clean (no missing/errors/contamination): {clean}")
    if not clean:
        print(f"  => INCONCLUSIVE — {len(nano_fallback)} correction/non-correction turns fell back to nano "
              "(infra, not the perceiver). Re-run those beats on a stable Ollama before deciding.")
    elif recall_pass and ghost_pass:
        print("  => PASS — flip of HMGFU_REGULATOR_ENABLED AUTHORIZED (with post-flip observation window).")
    else:
        print("  => FAIL — do NOT flip. Per-style autopsy before any 3rd iteration (Rule 13); "
              "repeat P-AUDIT with a NEW beat sheet (never tune the failed one, Rule 3).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
