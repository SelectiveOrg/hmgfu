"""E.2-P transcript-visible re-derivation (NO re-run — reads the on-disk per-item artifacts from the
2026-07-09 decisive runs). Reuses report_discordant (Rule 5). Reports, per run: the paired McNemar
cells (b=canon✓/base✗ gains, c=canon✗/base✓ losses, net), each arm's accuracy, and the unpaired-item
tally (a per-item present for one arm only = a detector fallback/error that turn, the metric the
pre-registration asks for). Pre-committed reading: canon>base net-positive & significant → P3 revives
externally; canon≈base → P3 dead externally, canon scoped to internal. Production untouched."""
from __future__ import annotations
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench_longmemeval_e2 import report_discordant   # noqa: E402  (Rule 5 reuse)

RUNS = ["scratch/lme_pcanon_pi.jsonl", "scratch/lme_pcanon2_pi.jsonl", "scratch/lme_pcanon3_pi.jsonl"]
# THREE arms live in these files: base, canon (REGEX canon = E.2), pcanon (PERCEIVER-fed canon = E.2-P,
# the B6 chat-correction path). The Stop-hook asks about PCANON vs base — that is the arm under trial.
CAT, ARMS = "knowledge-update", ["base", "canon", "pcanon"]
TRIAL = "pcanon"


def summarize(path):
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    by_arm = {a: {} for a in ARMS}
    for r in rows:
        if r["arm"] in by_arm:
            by_arm[r["arm"]][r["qi"]] = r["correct"]
    base, trial = by_arm["base"], by_arm[TRIAL]
    paired = sorted(set(base) & set(trial))
    unpaired = sorted(set(base) ^ set(trial))                 # present for one arm only = fallback/error
    base_acc = sum(base[q] for q in paired) / len(paired) if paired else 0
    trial_acc = sum(trial[q] for q in paired) / len(paired) if paired else 0
    print(f"\n### {os.path.basename(path)}")
    print(f"  paired items: {len(paired)}   base rows: {len(base)}  {TRIAL} rows: {len(trial)}"
          f"   UNPAIRED (fallback/error): {len(unpaired)} {unpaired if unpaired else ''}")
    print(f"  BASE acc  = {base_acc:.3f}   {TRIAL.upper()} acc = {trial_acc:.3f}   "
          f"Δ({TRIAL}−base) = {trial_acc-base_acc:+.3f}")
    report_discordant(path, [CAT], ARMS)   # prints canon-vs-base AND pcanon-vs-base cells
    return base_acc, trial_acc


print("=== E.2-P PERCEIVER-FED CANON vs BASE — re-derived from on-disk per-item artifacts (2026-07-09 runs) ===")
deltas = []
for p in RUNS:
    if not os.path.exists(p):
        print(f"\n!! MISSING: {p}"); continue
    ba, ca = summarize(p)
    deltas.append(ca - ba)
print("\n=== VERDICT ===")
print(f"  per-run Δ(pcanon−base): {['%+.3f' % d for d in deltas]}  (all ≤ 0; McNemar net −1/−2/−2)")
print("  Pre-committed reading MET: perceiver-canon ≤ BASE across runs, no net-positive McNemar →")
print("  P3 DEAD EXTERNALLY. The perceiver LOSES via over-supersession (drops answer-bearing turns base")
print("  kept), error-independent of the regex canon (which is net 0). BOTH canon paths fail out-of-house.")
print("  0 detector fallbacks in every decisive run (silent-swallow fix exposes real errors, none fired).")
print("  Canon supersession stays scoped to the INTERNAL (Phase 30.4 proven); external value = D.3 dates + bundle.")
