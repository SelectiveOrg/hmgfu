"""95.5 — self-thoughts, reflections and consolidation never become the user's facts (guide §5).

Listed in the inventory from 94.8c (a reflection "the user is stating a fact ..." was demoted alongside
the teaching — which is CORRECT, it is a derivative of A). The other half of the contract needs
evidence, not a change: an assistant reflection that ASSERTS a user attribute must (a) never enter the
canonical facts or assertions, (b) never be layered as identity/world-model, and (c) be delivered under
`assistantSaid`, not as a user fact. The code already claims all three (taxonomy.py Phase 48 doctrine,
retrieve.py 92.E2); a contract that is claimed and inert has happened five times in this project, so
each claim is exercised here in both directions. If these pass unchanged, 95.5 closes as VERIFIED.
"""
from __future__ import annotations

import pytest

from hmgfu.models import RetrievedMemory
from hmgfu.retrieve import organise_for_injection
from hmgfu.taxonomy import episodic_repair_layer
from tests.test_v2_agent import make_agent

CLAIM = "The user's main project is Vega, so I should treat Vega as their primary focus."


def test_a_reflection_writes_no_user_fact(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    before_facts = {f["key"] for f in engine.facts.active()}
    before_assertions = len(engine.facts.assertions.history())
    p = engine.ingest(CLAIM, source="assistant", mtype="reflection")
    assert p.source == "assistant" and p.type == "reflection"
    assert {f["key"] for f in engine.facts.active()} == before_facts
    assert len(engine.facts.assertions.history()) == before_assertions


def test_a_reflection_is_layered_as_an_episode_never_identity(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    p = engine.ingest(CLAIM, source="assistant", mtype="reflection")
    assert episodic_repair_layer(p) == "L1_session"
    assert engine.graph.points[p.id].layer not in ("L3_identity", "L4_world_model", "L5_deep_pattern")


def test_a_reflection_is_delivered_as_the_assistants_not_the_users(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    p = engine.ingest(CLAIM, source="assistant", mtype="reflection")
    inj = organise_for_injection([RetrievedMemory(point=p, score=0.9, reason="")], engine.graph)
    joined = " ".join(inj.get("assistantSaid", []))
    assert "Vega" in joined, inj
    for section in ("userIdentity", "relevantFacts", "activeProjects"):
        assert not any("Vega" in line for line in inj.get(section, [])), (section, inj.get(section))


def test_the_users_own_statement_is_still_a_user_fact(tmp_path):
    """The control: the same claim in the user's words IS a fact, exactly as before."""
    engine, _ = make_agent(tmp_path, [])
    changes = engine.facts.apply_all("O meu projeto principal chama-se Vega.", "user", session="s1")
    assert changes and changes[0]["key"] == "project.main" and changes[0]["value"] == "Vega"


def test_a_reflection_that_names_a_value_is_not_treated_as_a_correction(tmp_path):
    """A self-thought must not retract or supersede the user's ledger."""
    engine, _ = make_agent(tmp_path, [])
    engine.facts.apply_all("O meu projeto principal chama-se Nimbus.", "user", session="s1")
    engine.ingest("Actually the user's main project is Vega, not Nimbus.", source="assistant",
                  mtype="reflection")
    assert {f["key"]: f["value"] for f in engine.facts.active()}.get("project.main") == "Nimbus"
    assert engine.facts.superseded_values() == []
