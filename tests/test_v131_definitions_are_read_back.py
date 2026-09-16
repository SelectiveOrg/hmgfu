"""92.E5R — a definition that is stored but never read back has not been learned.

Found live by `scripts/diag_learning_matrix.py`: teaching wrote `definition:a294782c ->
"Atlas Control Mesh"`, and a NEW session answered *"I'm not certain what ACME-7 refers to in your
specific context"*. The write path is wired; the read path is not. `retrieve.py` and
`context_render.py` never touch the assertion store, and `read_definition` has no product call site
at all -- it is used only by tests and one diagnostic.

An earlier run of the same matrix hid this: the assistant answered correctly while having stored
NOTHING, because the raw teaching message was retrieved episodically. Two opposite failures, one
lesson -- an answer is not evidence of a write, and a write is not evidence of an answer, so the
matrix now checks both and these tests pin the read side.

The provenance requirement (priority 6) is part of the contract, not decoration: a definition the
user confirmed must arrive LABELLED as such, so it cannot be mistaken for something the assistant
inferred, and a superseded one must not arrive at all.
"""
from __future__ import annotations

import pytest

from hmgfu.assertions import AssertionStore
from hmgfu.learning_state import DEFINITION_RELATION, definition_entity_key


@pytest.fixture()
def store(tmp_path):
    return AssertionStore(str(tmp_path / "a.db"))


def _define(st, context, term, meaning):
    eid = st.upsert_entity("definition", definition_entity_key(context, term))
    st.assert_(eid, DEFINITION_RELATION, meaning, source_span=f"{term} means {meaning}")
    return eid


def test_a_stored_definition_is_rendered_for_the_reply_context(store):
    _define(store, "project terminology", "ACME-7", "Atlas Control Mesh")
    lines = store.render_definition_lines(DEFINITION_RELATION)
    assert any("ACME-7" in ln and "Atlas Control Mesh" in ln for ln in lines), lines


def test_the_line_carries_its_context_and_says_the_user_confirmed_it(store):
    _define(store, "project terminology", "ACME-7", "Atlas Control Mesh")
    line = store.render_definition_lines(DEFINITION_RELATION)[0]
    assert "project terminology" in line
    assert "definition" in line.lower()


def test_a_superseded_definition_is_not_offered(store):
    """A correction must win here too: the old meaning is history, not an alternative."""
    _define(store, "project terminology", "ACME-7", "Atlas Control Mesh")
    _define(store, "project terminology", "ACME-7", "Atlas Control Mesh, generation 7")
    lines = store.render_definition_lines(DEFINITION_RELATION)
    assert len(lines) == 1
    assert "generation 7" in lines[0]


def test_two_terms_in_two_contexts_both_survive(store):
    _define(store, "proj-1", "ACME-7", "Atlas Control Mesh")
    _define(store, "proj-2", "ACME-7", "Automated Cluster Manager")
    lines = store.render_definition_lines(DEFINITION_RELATION)
    assert len(lines) == 2
    assert {"Atlas Control Mesh", "Automated Cluster Manager"} == {
        ln.rsplit(" means ", 1)[-1].split(" [")[0] for ln in lines}


def test_nothing_is_rendered_when_nothing_was_taught(store):
    assert store.render_definition_lines(DEFINITION_RELATION) == []


def test_other_relations_are_not_swept_up(store):
    """The discriminating half: this renders DEFINITIONS, not every assertion in the store."""
    eid = store.upsert_entity("pet", "dog")
    store.assert_(eid, "pet.dog.name", "Green")
    assert store.render_definition_lines(DEFINITION_RELATION) == []


def test_the_agent_puts_them_in_the_canonical_block():
    """The wiring itself: a stored definition must reach the lines the reply context is built from."""
    import inspect

    from hmgfu import agent

    src = inspect.getsource(agent)
    assert "render_definition_lines" in src, (
        "definitions must be injected where the canonical facts are, or they are write-only")
    assert "canonical=self.facts.render_lines()" in src
    assert "+ self.facts.assertions.render_definition_lines(" in src
