"""95.18 (L1 c95g rep3) — a definition revision the protocol wrote curates the fact node and demotes the
stale bearers by itself; the nano's perception is not the trigger.

Read from the three L1 episode DBs: in rep1/rep2 a `user_explicit fact` "ACME-7 means Adaptive Cache
Manager" exists and five old-value points are superseded — all written by the GRADER's
`_apply_correction` (the nano perceived a correction); in rep3 `correction: null` on every grade (the
95.7 miss), nothing was curated, the stale echo was reinforced (0.5 → 0.65) and the new session answered
"Atlas Control Mesh" while the ledger held revision 2. The deterministic signal existed: `assert_`
superseded the prior row. Positive (unit): a revision reports `prev`, and `has_supersession` reads it.
Positive (engine, grader off): after the correction turn the corrected definition is a user_explicit
fact and the teaching + echo are superseded. Negative: a first definition reports no prev and curates
nothing. Preserve: the grader's path does not curate the same pair twice.
"""
from __future__ import annotations

from hmgfu.fact_nodes import demote_after_supersession, has_supersession
from hmgfu.learning_apply import DEFINITION_RELATION, apply_decision
from tests.test_v2_agent import make_agent

TEACH = "In this project, ACME-7 means Atlas Control Mesh."
FIX = "Correction: ACME-7 means Adaptive Cache Manager, not Atlas Control Mesh."


def _prop(value):
    return [{"kind": "domain_definition", "subject_ref": "ACME-7", "context_ref": "this project",
             "relation": DEFINITION_RELATION, "value": value, "evidence_refs": ["turn:1#0-1"]}]


def test_a_revision_reports_the_prior_value_and_the_trigger_reads_it(tmp_path):
    """THE CONTRACT (unit) — fails before: the definition effect carries no prev."""
    engine, _ = make_agent(tmp_path, [])
    st = engine.facts.assertions
    first = apply_decision({"action": "commit"}, _prop("Atlas Control Mesh"), facts=engine.facts, assertions=st, text=TEACH)
    assert not has_supersession([], {"effects": first})
    second = apply_decision({"action": "commit"}, _prop("Adaptive Cache Manager"), facts=engine.facts, assertions=st, text=FIX)
    assert has_supersession([], {"effects": second}), second
    assert second[0]["effects"][0]["prev"] == "Atlas Control Mesh"


def test_the_revision_curates_the_winner_and_demotes_the_bearers(tmp_path):
    """THE CONTRACT (engine) — fails before: no user_explicit fact, teaching and echo stay active."""
    engine, _ = make_agent(tmp_path, [])
    engine.settings.set("grader_enabled", False)
    teach = engine.ingest(TEACH, source="user", mtype="message")
    echo = engine.ingest("Noted: ACME-7 stands for Atlas Control Mesh.", source="assistant", mtype="message")
    st = engine.facts.assertions
    apply_decision({"action": "commit"}, _prop("Atlas Control Mesh"), facts=engine.facts, assertions=st, text=TEACH)
    second = apply_decision({"action": "commit"}, _prop("Adaptive Cache Manager"), facts=engine.facts, assertions=st, text=FIX)
    out = demote_after_supersession(engine, FIX, {"effects": second})
    assert out and out[0]["prev"] == "Atlas Control Mesh", out
    winner = engine.graph.points[out[0]["winner"]]
    assert winner.source == "user_explicit" and winner.type == "fact" and "Adaptive Cache Manager" in winner.content
    assert engine.graph.points[teach.id].status == "superseded", engine.graph.points[teach.id].status
    assert engine.graph.points[echo.id].status == "superseded", engine.graph.points[echo.id].status
    assert engine.graph.points[winner.id].status == "active"


def test_a_first_definition_curates_nothing(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    first = apply_decision({"action": "commit"}, _prop("Atlas Control Mesh"), facts=engine.facts,
                           assertions=engine.facts.assertions, text=TEACH)
    assert demote_after_supersession(engine, TEACH, {"effects": first}) == []
    assert not [p for p in engine.graph.all_points() if p.type == "fact" and p.source == "user_explicit"]


def test_the_grader_does_not_curate_the_same_pair_twice(tmp_path):
    from hmgfu.grader import _apply_correction
    engine, _ = make_agent(tmp_path, [])
    st = engine.facts.assertions
    apply_decision({"action": "commit"}, _prop("Atlas Control Mesh"), facts=engine.facts, assertions=st, text=TEACH)
    second = apply_decision({"action": "commit"}, _prop("Adaptive Cache Manager"), facts=engine.facts, assertions=st, text=FIX)
    demote_after_supersession(engine, FIX, {"effects": second})
    before = len([p for p in engine.graph.all_points() if p.type == "fact" and p.source == "user_explicit"])
    res = _apply_correction(engine, {"wrong": "Atlas Control Mesh", "right": "ACME-7 means Adaptive Cache Manager"}, FIX)
    after = len([p for p in engine.graph.all_points() if p.type == "fact" and p.source == "user_explicit"])
    assert before == after == 1, (before, after)
    assert res and res.get("grounded"), res
