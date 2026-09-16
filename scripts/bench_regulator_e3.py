"""E.3 — the Regulator gate. Deterministic (no LLM, no GPU, no DB) longitudinal replay with EMBEDDED
user corrections + post-correction probes. Decides whether the signal HIERARCHY beats plain counters.

THREE ARMS (Trailblazer's anti-vacuity design — arm (b) MUST be able to poison):
  (a) FULL     — the real Regulator: I1 active. Caps (silent/praise) + FACT requires an explicit
                 user signal + correction is ABSORBING (→ SUPERSEDED). regulator.state().
  (b) COUNTERS — I1 DISABLED so it CAN poison: UNCAPPED confidence (repetition alone reaches FACT),
                 NO explicit requirement, correction NOT absorbing. If we left the caps/gate on here
                 the comparison is vacuous ((a)==(b) by construction) — the whole point is to show how
                 bad pure counters get.
  (c) OFF      — v2 baseline: every asserted value is a FACT immediately; a correction supersedes it
                 via the existing deterministic path (the proven leg). No promotion gate at all.

METRICS (all deterministic):
  Poison Rate        — fraction of concepts whose SERVED value is a FACT with ZERO explicit signal
                       (a thing the system convinced itself of). I1 target ~0 for (a).
  CPR                — Correction Persistence Rate: over correction scenarios, fraction whose served
                       value == the user's corrected value (denominator = the post-correction probes).
  Promotion Precision— of values that reached FACT, fraction that are legitimate (never a lie / never
                       later corrected).

THE REAL CLAIM (Trailblazer): (a) ≫ (b) on POISON RATE. (a) and (b) may tie on CPR if both ride the
existing supersession, but only the explicit gate moves Poison Rate. Run:
  .venv/Scripts/python scripts/bench_regulator_e3.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hmgfu import config, regulator   # noqa: E402

L = config.LIFECYCLE
_RANK = {regulator.FACT: 3, regulator.CANDIDATE: 2, regulator.TEMP: 1, regulator.SUPERSEDED: 0}


def _c_uncapped(led: dict) -> float:
    """Arm-(b) confidence: NO caps → repetition alone can climb to FACT (the poisoning path)."""
    return max(0.0, min(1.0, L["TEMP_C"] + led.get("silent", 0) * L["SILENT_D"]
                        + led.get("praise", 0) * L["PRAISE_D"] + led.get("explicit", 0) * L["EXPLICIT_D"]))


def state_a(led):   # FULL — I1 (caps + explicit gate + absorbing correction)
    return regulator.state(led)


def state_b(led):   # COUNTERS — uncapped, no explicit gate, correction NOT absorbing (ignores 'corrected')
    c = _c_uncapped(led)
    return regulator.FACT if c >= L["FACT_T"] else (regulator.CANDIDATE if c >= L["CANDIDATE_T"] else regulator.TEMP)


def state_c(led):   # OFF — asserted ⇒ fact; a user correction supersedes (existing v2 path)
    return regulator.SUPERSEDED if led.get("corrected") else regulator.FACT


def served(values: dict, state_fn):
    """The value a concept serves under an arm: highest non-superseded state, tie-break by confidence."""
    best, best_key = None, (-1, -1.0)
    for val, led in values.items():
        st = state_fn(led)
        if st == regulator.SUPERSEDED:
            continue
        key = (_RANK[st], _c_uncapped(led))
        if key > best_key:
            best, best_key = val, key
    return best


# --- scenario generator (deterministic; each concept = {value: ledger} + truth + kind) --------------
def _led(silent=0, praise=0, explicit=0, corrected=False):
    return {"silent": silent, "praise": praise, "explicit": explicit, "corrected": corrected}


def scenarios(m: int = 20):
    """m of each: POISON (a self-asserted lie repeated+praised, no explicit), CORRECTION (value A
    heavily repeated, user corrects to B with an explicit signal), TRUE (user states a fact)."""
    out = []
    for i in range(m):
        # POISON: the system convinced itself — 40 silent uses + 10 praises, ZERO explicit user signal
        out.append({"kind": "poison", "corrected_to": None,
                    "values": {"LIE": _led(silent=40, praise=10, explicit=0)}})
        # CORRECTION: A repeated 40× (no explicit), then user CORRECTS to B (explicit + some use).
        # In arm (a)/(c) A is absorbing-superseded; in arm (b) A is NOT superseded (correction is weak).
        out.append({"kind": "correction", "corrected_to": "B",
                    "values": {"A": _led(silent=40, praise=5, explicit=0, corrected=True),
                               "B": _led(silent=10, explicit=1)}})
        # TRUE: the intended path — user states it (explicit) + modest use → a legitimate FACT
        out.append({"kind": "true", "corrected_to": None,
                    "values": {"FACT_V": _led(silent=10, explicit=1)}})
    return out


def run_arm(scn, state_fn):
    poison_hits = fact_promotions = fact_legit = 0
    cpr_num = cpr_den = 0
    served_facts = 0
    for s in scn:
        srv = served(s["values"], state_fn)
        srv_led = s["values"].get(srv) if srv else None
        srv_state = state_fn(srv_led) if srv_led is not None else None
        # Poison: the SERVED value is a FACT that never had an explicit user signal
        if srv_state == regulator.FACT:
            served_facts += 1
            if srv_led.get("explicit", 0) == 0:
                poison_hits += 1
        # CPR: on correction scenarios, is the served value the user's corrected value?
        if s["kind"] == "correction":
            cpr_den += 1
            if srv == s["corrected_to"]:
                cpr_num += 1
        # Promotion precision: over ALL values that reached FACT, fraction legit (explicit>0 & not corrected)
        for val, led in s["values"].items():
            if state_fn(led) == regulator.FACT:
                fact_promotions += 1
                if led.get("explicit", 0) > 0 and not led.get("corrected"):
                    fact_legit += 1
    return {
        "poison_rate": poison_hits / served_facts if served_facts else 0.0,
        "cpr": cpr_num / cpr_den if cpr_den else 0.0,
        "promotion_precision": fact_legit / fact_promotions if fact_promotions else 1.0,
        "served_facts": served_facts, "fact_promotions": fact_promotions, "cpr_den": cpr_den,
    }


def main() -> int:
    m = int(os.environ.get("E3_M", "20"))
    scn = scenarios(m)
    print(f"=== E.3 Regulator gate (deterministic, {len(scn)} concepts: {m} poison / {m} correction / {m} true) ===")
    print(f"config: TEMP_C {L['TEMP_C']} CANDIDATE_T {L['CANDIDATE_T']} FACT_T {L['FACT_T']} "
          f"EXPLICIT_D {L['EXPLICIT_D']} SILENT_CAP {L['SILENT_CAP']} PRAISE_CAP {L['PRAISE_CAP']}\n")
    arms = {"(a) FULL": state_a, "(b) COUNTERS": state_b, "(c) OFF": state_c}
    res = {name: run_arm(scn, fn) for name, fn in arms.items()}
    print(f"{'arm':>14} | {'POISON RATE':>11} | {'CPR':>6} | {'PROMO PREC':>10} | served_facts")
    for name, r in res.items():
        print(f"{name:>14} | {r['poison_rate']:>11.3f} | {r['cpr']:>6.3f} | "
              f"{r['promotion_precision']:>10.3f} | {r['served_facts']}")
    a, b, c = res["(a) FULL"], res["(b) COUNTERS"], res["(c) OFF"]
    print("\n=== VERDICT (Gate 1, pre-registered) ===")
    print(f"  Poison Rate: (a) {a['poison_rate']:.3f}  vs  (b) {b['poison_rate']:.3f}  vs  (c) {c['poison_rate']:.3f}")
    print(f"  CPR:         (a) {a['cpr']:.3f}  vs  (b) {b['cpr']:.3f}  vs  (c) {c['cpr']:.3f}")
    beats_b = a["poison_rate"] < b["poison_rate"] - 1e-9        # the real claim: (a) ≪ (b) on poison
    beats_c = a["poison_rate"] < c["poison_rate"] - 1e-9 or a["cpr"] >= c["cpr"] - 1e-9
    hierarchy_alive = beats_b and a["poison_rate"] <= 0.001 and a["cpr"] >= 0.95
    print(f"  → hierarchy beats counters on Poison Rate: {beats_b}; (a) Poison~0 & CPR>=0.95: "
          f"{a['poison_rate'] <= 0.001 and a['cpr'] >= 0.95}")
    print(f"  → REGULATOR SURVIVES E.3: {hierarchy_alive}  "
          f"({'promote behind HMGFU_REGULATOR_ENABLED' if hierarchy_alive else 'record as dead weight, retire'})")
    print("  (If (a)==(b) on Poison Rate the arm-(b) I1-disable failed — the test would be vacuous.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
