"""Phase 92.E3 — the three adapters, and the identity that keeps definitions apart.

The plan's hardest requirement here is not "store a definition": it is that `AssertionStore`
supersedes per `entity_id + relation`, so if every definition in a project shared one entity, each new
definition would silently erase the previous one. Identity is therefore (context, term), and these
tests exist to prove both halves of that: two terms in one project coexist, and the same term in two
projects does not collide.

They also prove the adapters never act on a decision that was not a commit — which is what keeps an
unresolved conflict or an unsupported proposal from reaching a store at all.
"""

from __future__ import annotations

import pytest

from hmgfu.assertions import AssertionStore
from hmgfu.directives import DirectiveStore
from hmgfu.learning_protocol import decide
from hmgfu.learning_state import (DEFINITION_RELATION, apply_decision, definition_entity_key,
                                  read_definition)

COMMIT = {"action": "commit", "operation": "assert"}


def _defn(term, value, context="proj-1"):
    return {"kind": "domain_definition", "subject_ref": term, "context_ref": context,
            "relation": DEFINITION_RELATION, "value": value, "evidence_refs": ["turn:1#0-10"]}


def _store(tmp_path, name="a.db"):
    return AssertionStore(str(tmp_path / name))


# --- identity ------------------------------------------------------------------------------------
def test_the_identity_of_a_term_is_context_plus_term():
    assert definition_entity_key("proj-1", "ACME-7") != definition_entity_key("proj-2", "ACME-7")
    assert definition_entity_key("proj-1", "ACME-7") == definition_entity_key("proj-1", " acme-7 ")


def test_two_definitions_in_one_project_do_not_supersede_each_other(tmp_path):
    st = _store(tmp_path)
    apply_decision(COMMIT, [_defn("ACME-7", "Atlas Control Mesh")], assertions=st, text="t")
    apply_decision(COMMIT, [_defn("BETA-2", "Basic Event Transport")], assertions=st, text="t")
    assert read_definition(st, "proj-1", "ACME-7")["value"] == "Atlas Control Mesh"
    assert read_definition(st, "proj-1", "BETA-2")["value"] == "Basic Event Transport"


def test_the_same_term_in_two_projects_does_not_collide(tmp_path):
    st = _store(tmp_path)
    apply_decision(COMMIT, [_defn("ACME-7", "Atlas Control Mesh", "proj-1")], assertions=st, text="t")
    apply_decision(COMMIT, [_defn("ACME-7", "Automated Cluster Manager", "proj-2")], assertions=st, text="t")
    assert read_definition(st, "proj-1", "ACME-7")["value"] == "Atlas Control Mesh"
    assert read_definition(st, "proj-2", "ACME-7")["value"] == "Automated Cluster Manager"


def test_a_later_definition_of_the_same_term_supersedes_the_earlier_one(tmp_path):
    st = _store(tmp_path)
    apply_decision(COMMIT, [_defn("ACME-7", "Atlas Control Mesh")], assertions=st, text="t")
    apply_decision(COMMIT, [_defn("ACME-7", "Atlas Control Mesh, generation 7")], assertions=st, text="t")
    assert read_definition(st, "proj-1", "ACME-7")["value"] == "Atlas Control Mesh, generation 7"


def test_a_definition_survives_a_restart(tmp_path):
    st = _store(tmp_path)
    apply_decision(COMMIT, [_defn("ACME-7", "Atlas Control Mesh")], assertions=st, text="t")
    again = _store(tmp_path)                       # a new store over the same file, as a new session would
    assert read_definition(again, "proj-1", "ACME-7")["value"] == "Atlas Control Mesh"


def test_an_unknown_term_reads_as_absent_not_as_a_guess(tmp_path):
    assert read_definition(_store(tmp_path), "proj-1", "NEVER-TAUGHT") is None


# --- the adapters act only on a commit ------------------------------------------------------------
@pytest.mark.parametrize("action", ["ask", "defer", "reject", "pass_through", "protocol_unavailable",
                                    "invalidate"])
def test_nothing_is_written_unless_the_decision_was_a_commit(tmp_path, action):
    st = _store(tmp_path)
    assert apply_decision({"action": action}, [_defn("ACME-7", "X")], assertions=st, text="t") == []
    assert read_definition(st, "proj-1", "ACME-7") is None


def test_an_unsupported_proposal_never_reaches_a_store(tmp_path):
    """End to end through the controller: an invented reference decides pass_through, so nothing writes."""
    st = _store(tmp_path)
    snap = {"session_id": "s1", "store_revision": 1, "evidence": {}}
    d = decide(snap, {"feedback": "none", "scope": "memory", "ambiguity": "none",
                      "target_case_id": None,
                      "proposals": [dict(_defn("ACME-7", "X"), evidence_refs=["invented:1"])]})
    assert d.action == "pass_through"
    assert apply_decision(d, [_defn("ACME-7", "X")], assertions=st, text="t") == []
    assert read_definition(st, "proj-1", "ACME-7") is None


# --- the behaviour adapter writes a TYPED policy, not a format ------------------------------------
def test_a_policy_is_stored_as_a_tool_rule_not_as_a_format(tmp_path):
    d = DirectiveStore(str(tmp_path / "d.db"))
    text = "always use memory search when you are not sure of the answer"
    apply_decision(COMMIT, [{"kind": "behavior_policy", "relation": "tool_rule:memory_search",
                             "value": "you are not sure of the answer",
                             "evidence_refs": ["turn:1#0-10"]}], directives=d, text=text)
    kinds = {x["kind"]: x.get("value") for x in d.active()}
    assert "tool_rule:memory_search" in kinds
    assert "output_prefix" not in kinds
