"""Outcome-driven choice (Phase 75.5) — a BOUNDED Thompson-sampling bandit over a SMALL set of discrete arms at a
decision site where the system otherwise always takes the argmax. State = Beta(α, β) per (site, arm), persisted in the
same `learned_params` table as every other learned quantity (bounded, resettable, visible in /api/learning_stats);
deleting the rows restores stock behaviour. Rewards are OUTCOMES the system already records (a receipt's success, a
plan followed to `done`), never the model's self-assessment. Setting `bandit_enabled` (default OFF until the gate):
when off, `choose` returns the site's default arm and records nothing."""
from __future__ import annotations

import random
from typing import Dict, List, Optional

PREFIX = "bandit:"
PRIOR = 1.0                  # Beta(1, 1): uniform; every arm starts equally plausible
MAX_COUNT = 500.0            # bounded memory: α + β never exceeds this — the bandit keeps adapting, never freezes


class Bandit:
    def __init__(self, params, rng: Optional[random.Random] = None):
        self._params = params
        self._rng = rng or random.Random()

    def _ab(self, site: str, arm: str) -> tuple:
        a = self._params.get(f"{PREFIX}{site}:{arm}:a", PRIOR)
        b = self._params.get(f"{PREFIX}{site}:{arm}:b", PRIOR)
        return a, b

    def choose(self, site: str, arms: List[str], default: Optional[str] = None, enabled: bool = True) -> str:
        """Thompson sampling: draw one Beta sample per arm, take the max. Off → the default (first) arm."""
        if not arms:
            raise ValueError("no arms")
        if not enabled:
            return default if default in arms else arms[0]
        best, best_draw = arms[0], -1.0
        for arm in arms:
            a, b = self._ab(site, arm)
            draw = self._rng.betavariate(a, b)
            if draw > best_draw:
                best, best_draw = arm, draw
        return best

    def reward(self, site: str, arm: str, outcome: float) -> None:
        """outcome ∈ [0, 1]: 1 = the choice paid off, 0 = it did not. Bounded: the pair (α, β) is rescaled when it
        grows past MAX_COUNT so old evidence fades and the arm can still be re-learned."""
        outcome = min(1.0, max(0.0, float(outcome)))
        a, b = self._ab(site, arm)
        a, b = a + outcome, b + (1.0 - outcome)
        if a + b > MAX_COUNT:
            scale = MAX_COUNT / (a + b)
            a, b = max(PRIOR, a * scale), max(PRIOR, b * scale)
            if a + b > MAX_COUNT:                       # the prior clamp on the small side can overshoot: take it off the big side
                if a >= b:
                    a = MAX_COUNT - b
                else:
                    b = MAX_COUNT - a
        self._params.set_bounded(f"{PREFIX}{site}:{arm}:a", a, PRIOR, MAX_COUNT)
        self._params.set_bounded(f"{PREFIX}{site}:{arm}:b", b, PRIOR, MAX_COUNT)

    def estimate(self, site: str, arm: str) -> float:
        a, b = self._ab(site, arm)
        return a / (a + b)

    def snapshot(self) -> Dict[str, dict]:
        """Every (site, arm) with its mean and pull count — for /api/learning_stats (Rule 10)."""
        out: Dict[str, dict] = {}
        for key, val in self._params.all().items():
            if not key.startswith(PREFIX) or not key.endswith(":a"):
                continue
            site_arm = key[len(PREFIX):-2]
            site, _, arm = site_arm.rpartition(":")
            a, b = self._ab(site, arm)
            out.setdefault(site, {})[arm] = {"mean": round(a / (a + b), 3), "pulls": round(a + b - 2 * PRIOR, 1)}
        return out

    def reset(self) -> int:
        return self._params.reset(PREFIX)
