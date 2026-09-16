"""THEORY v3 Phase 61a — the Regulator: the memory-lifecycle state machine (S), driven by a signal
hierarchy in which the USER's verdict dominates everything the system generates about itself.

INVARIANT I1 (anti-poisoning, STRUCTURAL not tuned): no accumulation of silent use + praise can
reach FACT; only an explicit user signal unlocks it, and a user CORRECTION is an ABSORBING transition
to SUPERSEDED that no counter can reverse. Proven arithmetically in tests/test_regulator_i1.py —
it holds by construction, independent of any model or data.

Signal hierarchy (strongest → weakest, THEORY_V3 B.3):
  correction  → absorbing → SUPERSEDED (a STATE, not a score delta)
  explicit    → +EXPLICIT_D, and unlocks CANDIDATE → FACT
  praise      → +PRAISE_D, total capped at PRAISE_CAP  (approval of tone ≠ verification of fact)
  silent_use  → +SILENT_D, total capped at SILENT_CAP  (silence is ambiguous, the weakest signal)

The confidence/state arithmetic below is PURE (no model, no DB) so I1 is unit-testable. Persistence
of the per-point signal ledger reuses learning.LearnedParams (bounded float store, key prefix 'lc:')
— no parallel table (Rule 5); the store's set_bounded enforces the caps at the storage layer.
This module is INERT in production until config.REGULATOR_ENABLED (gated on E.3).
"""

from __future__ import annotations

from typing import Optional

from . import config

# lifecycle states S
TEMP, CANDIDATE, FACT, SUPERSEDED, EVAPORATED = "temp", "candidate", "fact", "superseded", "evaporated"


def _L() -> dict:
    return config.LIFECYCLE


def confidence(ledger: dict) -> float:
    """Bounded confidence c from a signal ledger {silent, praise, explicit}. PURE. Correction is a
    STATE, not part of c (handled by state())."""
    L = _L()
    silent = min(ledger.get("silent", 0) * L["SILENT_D"], L["SILENT_CAP"])
    praise = min(ledger.get("praise", 0) * L["PRAISE_D"], L["PRAISE_CAP"])
    explicit = ledger.get("explicit", 0) * L["EXPLICIT_D"]
    return max(0.0, min(1.0, L["TEMP_C"] + silent + praise + explicit))


def state(ledger: dict) -> str:
    """Lifecycle state from the ledger. A correction is ABSORBING (→ SUPERSEDED). PURE. FACT requires
    BOTH c >= FACT_T AND at least one explicit user signal (the I1 gate)."""
    if ledger.get("correction"):
        return SUPERSEDED
    c = confidence(ledger)
    has_explicit = ledger.get("explicit", 0) >= 1
    if c >= _L()["FACT_T"] and has_explicit:
        return FACT
    if c >= _L()["CANDIDATE_T"]:
        return CANDIDATE
    return TEMP


def max_confidence_without_explicit() -> float:
    """The I1 ceiling: with zero explicit signals, c can never exceed this — and it is < FACT_T, so
    there is NO repetition/praise path to FACT. This is the anti-poisoning guarantee, as algebra."""
    L = _L()
    return L["TEMP_C"] + L["SILENT_CAP"] + L["PRAISE_CAP"]


# counters that feed confidence(), with their store bound (count s.t. count*Δ == cap)
_COUNTERS = ("silent", "praise", "explicit")


class Regulator:
    """Persistence-backed lifecycle owner. Reuses learning.LearnedParams (bounded float store) — the
    per-point ledger is a handful of `lc:<pid>:<counter>` keys; caps are enforced by set_bounded."""

    def __init__(self, learned_params):
        self.lp = learned_params

    def _key(self, pid: str, name: str) -> str:
        return f"lc:{pid}:{name}"

    def _cap_count(self, name: str) -> float:
        L = _L()
        if name == "silent":
            return L["SILENT_CAP"] / L["SILENT_D"]
        if name == "praise":
            return L["PRAISE_CAP"] / L["PRAISE_D"]
        return 1e9   # explicit is uncapped

    def ledger(self, pid: str) -> dict:
        led = {c: int(self.lp.get(self._key(pid, c), 0.0)) for c in _COUNTERS}
        led["correction"] = self.lp.get(self._key(pid, "correction"), 0.0) >= 1.0
        return led

    def transition(self, pid: str, signal_type: str) -> tuple:
        """Record ONE signal, persist the bounded ledger, return (c, state). The whole signal
        hierarchy runs through this one method (the single owner)."""
        if signal_type == "correction":
            self.lp.set_bounded(self._key(pid, "correction"), 1.0, 0.0, 1.0)   # absorbing
        elif signal_type in ("explicit", "praise", "silent_use"):
            name = "silent" if signal_type == "silent_use" else signal_type
            cur = self.lp.get(self._key(pid, name), 0.0)
            self.lp.set_bounded(self._key(pid, name), cur + 1.0, 0.0, self._cap_count(name))
        else:
            raise ValueError(f"unknown signal_type: {signal_type!r}")
        led = self.ledger(pid)
        return confidence(led), state(led)

    def evaluate(self, pid: str) -> tuple:
        led = self.ledger(pid)
        return confidence(led), state(led)
