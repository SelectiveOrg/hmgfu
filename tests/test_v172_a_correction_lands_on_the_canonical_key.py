"""95.2 — a committed proposal whose subject is a canonical slot writes the canonical fact.

Reproduced deterministically: after "O meu projeto principal chama-se Nimbus." (canonical `project.main`
= Nimbus via the slot regex), the correction "Correcao: o projeto principal chama-se Vega, nao Nimbus."
gives `FactStore.apply_all(...) == []` — the regex path re-parses the text and does not match it —
while the protocol commits the same statement as a `domain_definition` (L2 0/3 both arms: the
definition entity moved Nimbus→Vega, `facts.project.main` kept Nimbus, the reply was right only
because the definition was in context).

First failing link: the canonical writer ignores the STRUCTURED proposal the protocol already holds
(`subject_ref`, `value`) and re-derives from text. Invariant: B is applied to the subject and attribute
the user named (§4), through the one canonical writer (row + history + assertion + supersession in one
transaction), so `superseded_values()` sees it and node demotion has something to act on.

Change: in `learning_apply`, a committed `personal_fact` / `domain_definition` proposal whose
`subject_ref` (or `relation`) resolves to a SLOT via `slots.normalise_key` is written with
`facts._apply_one({"key", "value", "path": "protocol"}, text, source)` — the existing writer, no new
one. A subject that is not a slot (ACME-7) keeps the definition path untouched.
"""
from __future__ import annotations

import pytest

from hmgfu.learning_apply import apply_decision
from tests.test_v2_agent import make_agent

TEACH = "O meu projeto principal chama-se Nimbus."
CORR = "Correcao: o projeto principal chama-se Vega, nao Nimbus."


def _commit(engine, text, proposals, source="user"):
    return apply_decision(
        {"action": "commit", "operation": "assert"}, proposals, text=text, source=source,
        session="s1", facts=engine.facts, assertions=engine.facts.assertions,
        directives=engine.directives)


def test_the_regex_path_reads_the_correction_and_the_protocol_lands_on_the_same_key(tmp_path):
    """95.2's reproduction was that the regex did NOT match this correction -- WHY the protocol carries
    the write. 95.39 closed that gap (the definite-article form of a closed slot is the user's own), so
    the invariant kept here is that the two producers land on ONE canonical key, with no second row."""
    engine, _ = make_agent(tmp_path, [])
    assert engine.facts.apply_all(TEACH, "user", session="s1")
    assert [(c.get("key"), c.get("value")) for c in engine.facts.apply_all(CORR, "user", session="s1")] == [("project.main", "Vega")]
    _commit(engine, CORR, [{"kind": "domain_definition", "subject_ref": "projeto principal", "value": "Vega"}])
    assert [(f["key"], f["value"]) for f in engine.facts.active() if f["key"] == "project.main"] == [("project.main", "Vega")]


def test_a_definition_proposal_on_a_slot_subject_writes_the_canonical_key(tmp_path):
    """POSITIVE — fails before: the router said domain_definition, the slot is project.main."""
    engine, _ = make_agent(tmp_path, [])
    engine.facts.apply_all(TEACH, "user", session="s1")
    out = _commit(engine, CORR, [{"kind": "domain_definition", "subject_ref": "projeto principal",
                                  "value": "Vega"}])
    active = {f["key"]: f["value"] for f in engine.facts.active()}
    assert active.get("project.main") == "Vega", active
    assert ("project.main", "Nimbus") in [(k, v) for k, v in engine.facts.superseded_values()]
    assert any(e.get("canonical") == "project.main" for e in out), out


def test_a_personal_fact_proposal_on_a_slot_subject_writes_it_too(tmp_path):
    """VARIANT — the other kind the router may choose for the same sentence."""
    engine, _ = make_agent(tmp_path, [])
    engine.facts.apply_all(TEACH, "user", session="s1")
    _commit(engine, CORR, [{"kind": "personal_fact", "subject_ref": "projeto principal",
                            "relation": "project.main", "value": "Vega"}])
    active = {f["key"]: f["value"] for f in engine.facts.active()}
    assert active.get("project.main") == "Vega", active


def test_a_definition_of_a_term_that_is_no_slot_stays_a_definition(tmp_path):
    """NEGATIVE — ACME-7 is a term, not a canonical attribute; nothing canonical is written."""
    engine, _ = make_agent(tmp_path, [])
    out = _commit(engine, "In this project, ACME-7 means Atlas Control Mesh.",
                  [{"kind": "domain_definition", "subject_ref": "ACME-7", "value": "Atlas Control Mesh"}])
    assert not any(e.get("canonical") for e in out), out
    assert "project.main" not in {f["key"] for f in engine.facts.active()}
    assert any(e.get("assertion_id") for e in out)                    # the definition path, as before


def test_a_restated_value_writes_nothing_new(tmp_path):
    """PRESERVE — the canonical writer's own idempotence: Nimbus again is not a change."""
    engine, _ = make_agent(tmp_path, [])
    engine.facts.apply_all(TEACH, "user", session="s1")
    out = _commit(engine, TEACH, [{"kind": "personal_fact", "subject_ref": "projeto principal",
                                   "value": "Nimbus"}])
    assert engine.facts.superseded_values() == []
    assert not any(e.get("canonical") for e in out)


def test_the_same_value_elsewhere_is_untouched(tmp_path):
    """NEGATIVE — a different slot with the same value is not touched by the correction."""
    engine, _ = make_agent(tmp_path, [])
    engine.facts.apply_all(TEACH, "user", session="s1")
    engine.facts.apply_all("A minha empresa chama-se Nimbus.", "user", session="s1")
    _commit(engine, CORR, [{"kind": "domain_definition", "subject_ref": "projeto principal",
                            "value": "Vega"}])
    active = {f["key"]: f["value"] for f in engine.facts.active()}
    assert active.get("project.main") == "Vega"
    assert active.get("identity.company") == "Nimbus", active
