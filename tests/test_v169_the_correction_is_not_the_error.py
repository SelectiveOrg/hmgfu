"""95.1 — the sentence that sustains a correction cannot be invalidated as if it were the error.

The user's coherence contract, verbatim in shape. Reproduced 3/3 in the learning chain (94.8c, L1):
after "Correction: ACME-7 means Adaptive Cache Manager, not Atlas Control Mesh", the two points the
system superseded were the user's teaching message (right) and THE CORRECTION ITSELF (wrong), while
the assistant's echo of the old value stayed active.

Cause, read from the code rather than inferred: `fu_math.contradiction_heuristic` takes its negation
cue from the CONCATENATION of both texts. A correction that says "B, not A" therefore carries a
negation into every pair it is part of — including its pair with the `user_explicit` fact the grader
ingests from it ("ACME-7 means Adaptive Cache Manager"). That fact is newer, so `infer_resolution`
makes it the winner and the correction the loser, and `mark_tension` supersedes the loser because
the winner is user_explicit. The point that AGREES with the winner is demoted as if it contradicted it.

Component fixture (allowed for component tests; the natural-flow proof is the chain). The texts are
the real ones from the episode database. `tmp_path` keeps the graph off any real file.
"""
from __future__ import annotations

import pytest

from hmgfu import config, fu_math
from hmgfu.dream import infer_resolution, mark_tension
from hmgfu.models import MemoryPoint
from hmgfu.store import HMGGraph

A, B = "Atlas Control Mesh", "Adaptive Cache Manager"


def _graph(tmp_path):
    return HMGGraph(db_path=str(tmp_path / "v169.db"))


def _point(graph, content, source, ts, ptype="message"):
    p = MemoryPoint(type=ptype, content=content, source=source, timestamp=ts,
                    topics=["ACME-7"], entities=["ACME-7"])
    graph.save_point(p)
    return p


def _contradiction(a, b):
    return {"a": a.id, "b": b.id, "score": 0.9, "resolution": infer_resolution(a, b)}


def test_the_mechanism_the_negation_cue_leaks_across_the_pair(tmp_path):
    """Documents the cause: the fact and the correction that CREATED it score as a contradiction."""
    g = _graph(tmp_path)
    fact = _point(g, f"ACME-7 means {B}", "user_explicit", "2026-09-13T00:02:00+00:00", "fact")
    corr = _point(g, f"Correction: ACME-7 means {B}, not {A}.", "user", "2026-09-13T00:01:00+00:00")
    assert fu_math.contradiction_heuristic(fact, corr) > config.CONTRADICTION_MIN_SCORE
    assert infer_resolution(fact, corr)["loser"] == corr.id           # the newer fact wins


def test_the_correction_that_sustains_the_winner_is_not_superseded(tmp_path):
    """THE CONTRACT. Fails before the fix: the correction is demoted as if it were the error."""
    g = _graph(tmp_path)
    fact = _point(g, f"ACME-7 means {B}", "user_explicit", "2026-09-13T00:02:00+00:00", "fact")
    corr = _point(g, f"Correction: ACME-7 means {B}, not {A}.", "user", "2026-09-13T00:01:00+00:00")
    mark_tension(_contradiction(fact, corr), g, agrees_with=B)
    assert g.points[corr.id].status == "active", "the sentence sustaining the correction was invalidated"


def test_the_old_teaching_is_still_superseded(tmp_path):
    """The control: the behaviour that was right must not change."""
    g = _graph(tmp_path)
    fact = _point(g, f"ACME-7 means {B}", "user_explicit", "2026-09-13T00:02:00+00:00", "fact")
    old = _point(g, f"In this project, ACME-7 means {A}.", "user", "2026-09-13T00:00:00+00:00")
    mark_tension(_contradiction(fact, old), g, agrees_with=B)
    assert g.points[old.id].status == "superseded"


def test_the_assistants_echo_of_the_old_value_is_superseded_too(tmp_path):
    """The derived answer that carries only the old value is the error, and must lose."""
    g = _graph(tmp_path)
    fact = _point(g, f"ACME-7 means {B}", "user_explicit", "2026-09-13T00:02:00+00:00", "fact")
    echo = _point(g, f"Understood. I've noted that ACME-7 refers to the {A} within this project.",
                  "assistant", "2026-09-13T00:00:30+00:00")
    mark_tension(_contradiction(fact, echo), g, agrees_with=B)
    assert g.points[echo.id].status == "superseded"


def test_a_history_that_names_both_values_survives(tmp_path):
    """'Was A, is now B' agrees with B. Preserve history; do not present it as the error."""
    g = _graph(tmp_path)
    fact = _point(g, f"ACME-7 means {B}", "user_explicit", "2026-09-13T00:02:00+00:00", "fact")
    hist = _point(g, f"ACME-7 used to mean {A}; it now means {B}.", "assistant",
                  "2026-09-13T00:01:30+00:00")
    mark_tension(_contradiction(fact, hist), g, agrees_with=B)
    assert g.points[hist.id].status == "active"
