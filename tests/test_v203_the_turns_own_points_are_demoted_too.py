"""95.22 — a derived memory is not BORN current when its evidence has already been superseded.

L4 c95k rep3: the demotion trigger runs BEFORE the reply, while the assistant's reply, its step
narration and the reflections are ingested in the TAIL; the narration "Step 1/1 — Update the user's
primary project name in memory from Nimbus: Searching memory for …" was ingested after the demotion
and stayed active — stale at birth. The user's directive: the rule must hold for late and repeated
ingestion, for definitions as for canonical facts, and must never invalidate the correction.

One rule, `born_stale`, at the ingest choke point and in `supersede_stale_nodes`. Positive: the
assistant's reply carrying only the old value ends superseded (engine turn). Late: a reflection
ingested minutes after the correction is born superseded. Repeated: the same stale text ingested
twice is superseded both times. Definition: after a definition revision, "ACME-7 means <old>" is born
superseded and "ACME-7 means <new>" is born active. Preserve: a reply carrying both values (a
history) stays active; the correction message itself stays active; a turn that supersedes nothing
demotes nothing; the tail pass still runs on a turn that superseded.
"""
from __future__ import annotations

from hmgfu.fact_nodes import born_stale, stale_pairs
from hmgfu.learning_apply import DEFINITION_RELATION, apply_decision
from tests.test_v2_agent import make_agent


def _points_like(engine, needle):
    return [(p.source, p.status) for p in engine.graph.all_points() if needle.casefold() in (p.content or "").casefold()]


def _corrected(tmp_path, replies):
    engine, _ = make_agent(tmp_path, [{"content": r, "tool_calls": []} for r in replies])
    engine.settings.set("grader_enabled", False)
    engine.agent_chat("My main project is Nimbus.")
    engine.agent_chat("Correction: my main project is Vega, not Nimbus.")
    assert ("project.main", "Vega") in [(f["key"], f["value"]) for f in engine.facts.active()], engine.facts.active()
    return engine


def test_the_assistant_reply_carrying_only_the_old_value_ends_superseded(tmp_path):
    """THE CONTRACT — fails before: the reply point is ingested after the demotion and stays active."""
    engine = _corrected(tmp_path, ["Noted: your main project is Nimbus.",
                                   "Updating the main project in memory from Nimbus: searching memory for the record."])
    assert not [s for s in _points_like(engine, "from Nimbus") if s[1] == "active"], _points_like(engine, "from Nimbus")


def test_a_late_reflection_is_born_superseded(tmp_path):
    engine = _corrected(tmp_path, ["Noted.", "Updated to Vega, no longer Nimbus."])
    late = engine.ingest("The user is stating a definition: the main project is Nimbus.", source="assistant", mtype="reflection")
    assert late.status == "superseded", late.status


def test_the_same_stale_text_ingested_twice_is_superseded_both_times(tmp_path):
    engine = _corrected(tmp_path, ["Noted.", "Updated to Vega, no longer Nimbus."])
    first = engine.ingest("Your main project is Nimbus.", source="assistant", mtype="message")
    second = engine.ingest("Your main project is Nimbus.", source="assistant", mtype="message")
    assert first.status == "superseded" and second.status == "superseded", (first.status, second.status)
    assert not [s for s in _points_like(engine, "project is Nimbus") if s[1] == "active" and s[0] == "assistant"]


def test_a_definition_revision_makes_the_old_meaning_stale_at_birth(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    st = engine.facts.assertions
    prop = lambda v: [{"kind": "domain_definition", "subject_ref": "ACME-7", "relation": DEFINITION_RELATION,
                       "value": v, "evidence_refs": ["turn:1#0-1"]}]
    apply_decision({"action": "commit"}, prop("Atlas Control Mesh"), facts=engine.facts, assertions=st, text="ACME-7 means Atlas Control Mesh.")
    apply_decision({"action": "commit"}, prop("Adaptive Cache Manager"), facts=engine.facts, assertions=st, text="Correction: ACME-7 means Adaptive Cache Manager.")
    assert ("term:acme-7", "Atlas Control Mesh", "Adaptive Cache Manager") in stale_pairs(engine.facts)
    old = engine.ingest("ACME-7 stands for Atlas Control Mesh in this project.", source="assistant", mtype="message")
    new = engine.ingest("ACME-7 means Adaptive Cache Manager.", source="user_explicit", mtype="fact")
    assert old.status == "superseded" and new.status == "active", (old.status, new.status)
    assert not born_stale(engine.facts, "BETA-9 means Atlas Control Mesh")   # another term is not ACME-7


def test_a_reply_carrying_both_values_is_a_history_and_stays(tmp_path):
    engine = _corrected(tmp_path, ["Noted: your main project is Nimbus.",
                                   "Updated: your main project is Vega now, no longer Nimbus."])
    assert [s for s in _points_like(engine, "no longer Nimbus") if s[1] == "active"]


def test_the_correction_itself_is_never_invalidated(tmp_path):
    engine = _corrected(tmp_path, ["Noted.", "Updated."])
    assert [s for s in _points_like(engine, "Correction: my main project is Vega") if s[1] == "active" and s[0] in ("user", "user_explicit")]


def test_a_turn_that_supersedes_nothing_demotes_nothing(tmp_path):
    engine, _ = make_agent(tmp_path, [
        {"content": "Noted: your main project is Nimbus.", "tool_calls": []},
        {"content": "Nimbus is a fine name for a project.", "tool_calls": []},
    ])
    engine.settings.set("grader_enabled", False)
    engine.agent_chat("My main project is Nimbus.")
    engine.agent_chat("Do you like the name?")
    assert all(s[1] == "active" for s in _points_like(engine, "Nimbus")), _points_like(engine, "Nimbus")
