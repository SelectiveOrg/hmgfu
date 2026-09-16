"""THEORY v3 Phase 61a — INVARIANT I1 proven arithmetically (no model, no DB, no Ollama).

I1: there is NO path from repetition + praise to FACT; only an explicit user signal unlocks it, and a
user correction is an ABSORBING transition to SUPERSEDED. This is the anti-poisoning guarantee stated
as a STRUCTURAL property — if these asserts hold, no amount of self-generated signal can promote a
lie, by construction. This test is the E.3 gate's deterministic first arm.
"""

from __future__ import annotations

from hmgfu import config
from hmgfu.regulator import (CANDIDATE, FACT, SUPERSEDED, TEMP, confidence,
                             max_confidence_without_explicit, state)


def _led(silent=0, praise=0, explicit=0, correction=False):
    return {"silent": silent, "praise": praise, "explicit": explicit, "correction": correction}


def test_i1_ceiling_without_explicit_is_below_fact():
    L = config.LIFECYCLE
    ceiling = max_confidence_without_explicit()
    assert ceiling == L["TEMP_C"] + L["SILENT_CAP"] + L["PRAISE_CAP"]        # 0.40 + 0.10 + 0.10
    assert abs(ceiling - 0.60) < 1e-9
    assert ceiling < L["FACT_T"]                                             # 0.60 < 0.80 → I1 holds


def test_i1_a_lie_repeated_forty_times_never_reaches_fact():
    # 40 silent uses + 40 praises, ZERO explicit signals — the poisoning attempt
    led = _led(silent=40, praise=40, explicit=0)
    c = confidence(led)
    assert c <= max_confidence_without_explicit() + 1e-9   # caps hold: capped at 0.60
    assert abs(c - 0.60) < 1e-9                             # 0.40 + 0.10(silent cap) + 0.10(praise cap)
    assert state(led) == CANDIDATE                          # stalls at CANDIDATE, NEVER FACT
    assert state(led) != FACT


def test_i1_praise_alone_is_capped_and_never_fact():
    # praise caps at +PRAISE_CAP → 0.50 = CANDIDATE_T, so it MAY reach CANDIDATE (intended, B.1) but
    # NEVER FACT (the I1 guarantee). Even praise + silent together stay CANDIDATE.
    assert confidence(_led(praise=1000)) <= 0.40 + config.LIFECYCLE["PRAISE_CAP"] + 1e-9
    assert state(_led(praise=1000)) != FACT
    assert state(_led(praise=1000, silent=1000)) != FACT    # 0.60 < 0.80, no explicit → CANDIDATE, not FACT


def test_correction_is_absorbing_and_beats_any_count():
    # a fact with maximal accumulated non-explicit signal AND even an explicit confirmation...
    strong = _led(silent=40, praise=40, explicit=3)
    assert state(strong) == FACT                            # it IS a FACT before the correction
    # ...one user correction supersedes it, irreversibly — no counter can undo a STATE transition
    corrected = dict(strong); corrected["correction"] = True
    assert state(corrected) == SUPERSEDED
    # piling on more silent/praise/explicit after the correction changes nothing
    corrected["silent"] += 999; corrected["praise"] += 999; corrected["explicit"] += 9
    assert state(corrected) == SUPERSEDED                   # absorbing


def test_intended_path_one_explicit_plus_use_reaches_fact():
    # the designed route: the user's word (+0.30) corroborated by modest use → FACT
    led = _led(silent=10, explicit=1)                       # 0.40 + 0.10(silent) + 0.30(explicit) = 0.80
    assert abs(confidence(led) - 0.80) < 1e-9
    assert state(led) == FACT
    # but explicit signal is REQUIRED even at high c — c>=FACT_T without explicit is only CANDIDATE
    no_explicit = _led(silent=40, praise=40, explicit=0)
    assert confidence(no_explicit) < config.LIFECYCLE["FACT_T"]
    assert state(no_explicit) != FACT


def test_state_thresholds_are_monotone():
    assert state(_led()) == TEMP                            # birth c=0.40 < CANDIDATE_T(0.50)
    assert state(_led(silent=10)) == CANDIDATE              # 0.40 + 0.10 = 0.50 → CANDIDATE
    assert state(_led(explicit=2)) == FACT                  # 0.40 + 0.60 = 1.0, has explicit → FACT
