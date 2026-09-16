"""95.21 (L1 c95j rep3) — a context is a name, not the message.

The nano's correction proposal carried `context_ref` = the WHOLE message. The evidence rule accepted it
(trivially in the text), `definition_entity_key(context, term)` minted a second entity beside
"local::acme-7", both definitions stayed active, nothing was superseded and the new session retrieved
the old one. A context that is the message itself, or that contains the proposal's own subject, names
no setting: it is dropped (local) at the protocol's entry. Positive: the degenerate context lands the
revision on the existing entity (prev reported, old row superseded). Variant: a context containing the
subject is dropped too. Preserve: a real context evidenced in the message is kept as it was.
"""
from __future__ import annotations

from hmgfu.learning_apply import DEFINITION_RELATION
from hmgfu.learning_state import run_learning_turn
from tests.test_v2_agent import make_agent

TEACH = "In this project, ACME-7 means Atlas Control Mesh."
FIX = "Correction: ACME-7 means Adaptive Cache Manager, not Atlas Control Mesh."


class Q:
    def __init__(self, envelope=None):
        self.extraction = {"memory_update": envelope} if envelope is not None else {}


def _env(text, value, context=None):
    start = text.index(value)
    p = {"kind": "domain_definition", "subject_ref": "ACME-7", "relation": DEFINITION_RELATION, "value": value,
         "evidence_refs": [f"turn:1#{start}-{start + len(value)}"]}
    if context is not None:
        p["context_ref"] = context
    return {"feedback": "none", "scope": "memory", "ambiguity": "none", "target_case_id": None, "proposals": [p]}


def _taught(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    engine.settings.set("interactive_learning_mode", "confirm")
    assert run_learning_turn(engine, "s1", TEACH, Q(_env(TEACH, "Atlas Control Mesh")), turn_id="1")["decision"]["action"] == "commit"
    return engine


def _defs(engine):
    st = engine.facts.assertions
    return sorted((a["value"], a.get("status", "active")) for a in st.history() if a["relation"] == DEFINITION_RELATION), \
        [e["name"] for e in st.entities(kind="definition")]


def test_the_whole_message_as_context_lands_on_the_existing_entity(tmp_path):
    """THE CONTRACT — fails before: a second entity, both definitions active."""
    engine = _taught(tmp_path)
    out = run_learning_turn(engine, "s1", FIX, Q(_env(FIX, "Adaptive Cache Manager", context=FIX)), turn_id="2")
    assert out["decision"]["action"] == "commit", out["decision"]
    hist, names = _defs(engine)
    assert names == ["local::acme-7"], names
    assert hist == [("Adaptive Cache Manager", "active"), ("Atlas Control Mesh", "superseded")], hist
    assert out["effects"][0]["effects"][0]["prev"] == "Atlas Control Mesh"


def test_a_context_containing_the_subject_is_dropped(tmp_path):
    engine = _taught(tmp_path)
    out = run_learning_turn(engine, "s1", FIX, Q(_env(FIX, "Adaptive Cache Manager", context="ACME-7 means")), turn_id="2")
    assert out["decision"]["action"] == "commit", out["decision"]
    assert _defs(engine)[1] == ["local::acme-7"]


def test_a_real_context_evidenced_in_the_message_is_kept(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    engine.settings.set("interactive_learning_mode", "confirm")
    text = "In proj-1, ACME-7 means Atlas Control Mesh."
    out = run_learning_turn(engine, "s1", text, Q(_env(text, "Atlas Control Mesh", context="proj-1")), turn_id="1")
    assert out["decision"]["action"] == "commit", out["decision"]
    assert _defs(engine)[1] == ["proj-1::acme-7"]
