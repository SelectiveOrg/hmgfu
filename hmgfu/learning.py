"""Learned parameters — the self-tuning layer (Phase 56).

Closes the audit gap "the parameters don't learn": grader outcomes now adapt the retrieval
scoring math, and dream near-miss stats adapt the wormhole gates. Every learned value is
BOUNDED (hard clamps around the config baseline), PERSISTED (SQLite `learned_params`, same DB)
and INSPECTABLE (GET /api/learning) — self-growing, never a hidden prompt patch (Rule 10).

Design: config.py stays the immutable BASELINE (single source of truth for defaults); this
module stores small multiplicative/absolute deviations learned from experience. Deleting the
`learned_params` rows restores stock behaviour exactly.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from typing import Dict, Optional

from . import config
from .models import now_iso

log = logging.getLogger("hmgfu.learning")

# hard multiplier bounds for memory-score weight learning: learning can re-balance the design,
# never invert it (a weight can shrink to half or grow by half, no sign flips, no runaway).
WEIGHT_MULT_MIN = 0.5
WEIGHT_MULT_MAX = 1.5
LEARNING_RATE = 0.02
# grade → learning signal around the neutral 0.5 (cited reinforces, unused suppresses)
GRADE_SIGNAL = {"cited": 0.5, "implied": 0.1, "unused": -0.5}


class LearnedParams:
    """Bounded persisted key→float store. One table for every learned tunable in the system
    (memory-score multipliers, wormhole gate offsets, …) so learning state has ONE home."""

    def __init__(self, db_path: Optional[str] = None):
        self._lock = threading.RLock()
        self._db = sqlite3.connect(db_path or config.DB_PATH, check_same_thread=False)
        self._db.execute("CREATE TABLE IF NOT EXISTS learned_params ("
                         "key TEXT PRIMARY KEY, value REAL, updated_at TEXT)")
        self._db.commit()
        self._cache: Dict[str, float] = {
            k: v for k, v in self._db.execute("SELECT key, value FROM learned_params")
        }

    def get(self, key: str, default: float) -> float:
        with self._lock:
            return self._cache.get(key, default)

    def set_bounded(self, key: str, value: float, lo: float, hi: float) -> float:
        """Clamp into [lo, hi], persist, return the stored value."""
        value = max(lo, min(hi, float(value)))
        with self._lock:
            self._cache[key] = value
            self._db.execute("INSERT OR REPLACE INTO learned_params VALUES (?, ?, ?)",
                             (key, value, now_iso()))
            self._db.commit()
        return value

    def bump(self, key: str, delta: float, lo: float, hi: float, default: float = 0.0) -> float:
        return self.set_bounded(key, self.get(key, default) + delta, lo, hi)

    def all(self) -> Dict[str, float]:
        with self._lock:
            return dict(self._cache)

    def reset(self, prefix: str = "") -> int:
        """Remove learned values (optionally by prefix) — restores config baseline."""
        with self._lock:
            keys = [k for k in self._cache if k.startswith(prefix)]
            for k in keys:
                self._cache.pop(k, None)
                self._db.execute("DELETE FROM learned_params WHERE key=?", (k,))
            self._db.commit()
        return len(keys)

    def close(self) -> None:
        with self._lock:
            self._db.close()


class WeightLearner:
    """Online, bounded adaptation of config.MEMORY_SCORE_WEIGHTS from grader outcomes.

    Credit assignment: for each graded recalled memory, each score COMPONENT that contributed
    strongly to a CITED memory gets its weight multiplier nudged up (that signal earns trust);
    components that keep surfacing UNUSED memories get nudged down. Penalty terms learn in the
    opposite direction (a high-penalty memory cited anyway → the penalty is too strong).
    Multipliers live in [0.5, 1.5] — learning re-balances, never redesigns (see module doc)."""

    PREFIX = "msw:"

    def __init__(self, params: LearnedParams):
        self._params = params

    def multipliers(self) -> Dict[str, float]:
        return {k: self._params.get(self.PREFIX + k, 1.0) for k in config.MEMORY_SCORE_WEIGHTS}

    def weights(self) -> Dict[str, float]:
        """Effective weights = config baseline × learned multiplier, RE-BALANCED (73.3): the positive components keep
        the baseline's total mass, so learning shifts weight between signals but can never shrink every signal at
        once — 270 'unused' updates on ledger-answered turns had halved the semantic weight and retrieval returned
        nothing at the absolute min_score. Penalty terms are bounded on their own and not rescaled."""
        raw = {k: base * self._params.get(self.PREFIX + k, 1.0) for k, base in config.MEMORY_SCORE_WEIGHTS.items()}
        pos = [k for k in raw if not k.endswith("Penalty")]
        base_mass = sum(config.MEMORY_SCORE_WEIGHTS[k] for k in pos)
        raw_mass = sum(raw[k] for k in pos)
        scale = base_mass / raw_mass if raw_mass > 0 else 1.0
        return {k: (v * scale if k in pos else v) for k, v in raw.items()}

    def update_count(self) -> int:
        return int(self._params.get(self.PREFIX + "_updates", 0.0))

    def learn_from_grades(self, query, retrieved, memory_grades) -> int:
        """Apply one bounded learning step per graded memory. Returns memories learned from."""
        from . import fu_math
        learned = 0
        # 73.3: 'unused' is informative only in CONTRAST with something cited/implied in the same turn. A turn
        # answered from the canonical ledger cites no memory at all — that says nothing about which SIGNAL
        # surfaced the wrong memories, so no negative credit is assigned.
        contrast = any((GRADE_SIGNAL.get(str(g.get("grade"))) or 0.0) > 0.0 for g in memory_grades)
        for grade in memory_grades:
            try:
                index = int(grade.get("index"))
            except (TypeError, ValueError):
                continue
            if not 0 <= index < len(retrieved):
                continue
            signal = GRADE_SIGNAL.get(str(grade.get("grade")))
            if signal is None or (signal < 0.0 and not contrast):
                continue
            comps = fu_math.memory_score_components(query, retrieved[index].point, retrieved[index].edge,
                                                    getattr(retrieved[index], "path_relevance", 1.0))
            for key in config.MEMORY_SCORE_WEIGHTS:
                contribution = comps.get(key, 0.0)
                if contribution <= 0.0:
                    continue                    # a silent component takes no credit or blame
                direction = -1.0 if key.endswith("Penalty") else 1.0
                self._params.bump(self.PREFIX + key,
                                  direction * LEARNING_RATE * signal * contribution,
                                  WEIGHT_MULT_MIN, WEIGHT_MULT_MAX, default=1.0)
            learned += 1
        if learned:
            self._params.set_bounded(self.PREFIX + "_updates",
                                     self._params.get(self.PREFIX + "_updates", 0.0) + learned,
                                     0.0, 1e12)
        return learned

    def snapshot(self) -> dict:
        """Inspection payload for /api/learning (Rule 10: nothing hidden)."""
        return {
            "updates": self.update_count(),
            "weights": {
                k: {"base": base,
                    "multiplier": round(self._params.get(self.PREFIX + k, 1.0), 4),
                    "effective": round(self.weights()[k], 4)}          # 73.3: the re-balanced value actually used
                for k, base in config.MEMORY_SCORE_WEIGHTS.items()
            },
        }


# --- wormhole gate calibration (Phase 56 gap 3) -------------------------------------------
# The analogical self-organisation layer had NEVER fired in production (0 wormholes / 59 dreams):
# config gates were tuned on synthetic data. Instead of hand-picking new constants (that would be
# the same mistake), the calibrator adapts the RELAXABLE gates from real near-miss evidence:
# a dream that creates nothing but sees near-misses relaxes the most-binding gate one bounded
# step; a dream that over-creates tightens back toward the config baseline. The nano analogical
# veto stays untouched as the semantic quality gate.
WH_PREFIX = "wh:"
WH_BOUNDS = {"minAnalogy": (0.50, 0.85), "minSemantic": (0.30, 0.60), "minDensity": (0.30, 0.60)}
WH_STEP = {"minAnalogy": 0.05, "minSemantic": 0.03, "minDensity": 0.05}
WH_RELAX_AFTER = 2          # consecutive dry dreams (with near-misses) before one relax step
WH_TARGET_MAX = 2           # wormholes per dream above this → tighten one step back


class WormholeCalibrator:
    """Bounded self-tuning of the wormhole creation gates from dream near-miss statistics."""

    def __init__(self, params: LearnedParams):
        self._params = params

    def effective(self) -> dict:
        """config.WORMHOLE with the learned gate values overlaid (stock until calibrated)."""
        eff = dict(config.WORMHOLE)
        for key in WH_BOUNDS:
            eff[key] = self._params.get(WH_PREFIX + key, config.WORMHOLE[key])
        return eff

    def observe(self, near_misses: Dict[str, int], created: int) -> Optional[str]:
        """One call per full dream loop. Returns a human-readable insight when it adapts."""
        streak_key = WH_PREFIX + "_dry_streak"
        if created > WH_TARGET_MAX:
            # over-firing: revert the loosest learned gate one step toward the config baseline
            key = min(WH_BOUNDS, key=lambda k: self._params.get(WH_PREFIX + k, config.WORMHOLE[k])
                      - config.WORMHOLE[k])
            lo, _ = WH_BOUNDS[key]
            value = self._params.set_bounded(
                WH_PREFIX + key,
                self._params.get(WH_PREFIX + key, config.WORMHOLE[key]) + WH_STEP[key],
                lo, config.WORMHOLE[key])       # never stricter than the baseline
            self._params.set_bounded(streak_key, 0.0, 0.0, 1e9)
            return f"wormhole calibration: {created} created > target — tightened {key} to {value:.2f}"
        if created > 0:
            self._params.set_bounded(streak_key, 0.0, 0.0, 1e9)
            return None
        if not any(near_misses.values()):
            return None                          # dry but no evidence — nothing to learn from
        streak = self._params.bump(streak_key, 1.0, 0.0, 1e9)
        if streak < WH_RELAX_AFTER:
            return None
        key = max(near_misses, key=lambda k: near_misses.get(k, 0))
        lo, _ = WH_BOUNDS[key]
        value = self._params.set_bounded(
            WH_PREFIX + key,
            self._params.get(WH_PREFIX + key, config.WORMHOLE[key]) - WH_STEP[key],
            lo, config.WORMHOLE[key])
        self._params.set_bounded(streak_key, 0.0, 0.0, 1e9)
        return (f"wormhole calibration: {sum(near_misses.values())} near-misses "
                f"(binding gate {key}) — relaxed {key} to {value:.2f}")
