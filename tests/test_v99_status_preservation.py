"""Phase 90.N — the STATUS of a claim must survive from the message to the delivered context.

Traced defect (s06, `outputs/evidence_90_N1_trace.txt`): "We should work on Mapiko." is stored with the nano's
`type=task`, and `retrieve.organise_for_injection` files goal/project/task points under the section rendered as
**"Active projects and goals"**. The user's words stay verbatim, but the HEADING above them asserts the value is an
active project — the proposal becomes an activity two layers BEFORE the reader.

The gate reuses the modality contract of 90.L (`utterance.declarative_clauses`) at the choke point where the other
type gates already live (`ingest.ingest_memory`): a message with NO assertive clause is an episode, never a
goal/project/task. It must not block a legitimate update — an acceptance or an explicit start still types normally.
"""

from __future__ import annotations

import pytest

from hmgfu.heuristic_extract import heuristic_extract
from hmgfu.ingest import ingest_memory
from hmgfu.retrieve import RetrievedMemory, organise_for_injection
from tests.test_v2_agent import make_agent

PROPOSALS = [
    "We should work on Mapiko.",                 # en, the traced case
    "Devíamos trabalhar no Mapiko.",             # pt
    "Let's work on Mapiko.",                     # en, clause-initial
    "Vamos trabalhar no Mapiko.",                # pt, clause-initial
    "I want to work on Mapiko.",                 # en, volitive
    "Quero trabalhar no Mapiko.",                # pt, volitive
    "I plan to work on Mapiko.",                 # en, planning
]
ASSERTIONS = [
    "We are working on Mapiko.",                 # the activity, asserted
    "Estamos a trabalhar no Mapiko.",            # pt
    "My main project is Mapiko.",                # the durable state
    "We started Mapiko yesterday.",              # the explicit start
    "I want to work on Mapiko, but my main project is Kuvala.",   # mixed: an assertion shares the message
]


def _ingest(engine, text, claimed_type):
    """The nano's classification is simulated verbatim: the only thing under test is the gate."""
    extracted = dict(heuristic_extract(text))
    extracted["type"] = claimed_type
    return ingest_memory(text, source="user", graph=engine.graph, sensitizer=engine.sensitizer,
                         embed=engine.embed, extracted=extracted)


@pytest.mark.parametrize("text", PROPOSALS)
@pytest.mark.parametrize("claimed", ["task", "goal", "project"])
def test_a_proposal_or_wish_is_never_stored_as_an_active_project(tmp_path, text, claimed):
    engine, _ = make_agent(tmp_path, [])
    assert _ingest(engine, text, claimed).type == "message"


@pytest.mark.parametrize("text", ASSERTIONS)
def test_an_assertion_keeps_its_type_so_legitimate_updates_still_land(tmp_path, text):
    engine, _ = make_agent(tmp_path, [])
    assert _ingest(engine, text, "task").type == "task"


def test_the_proposal_acceptance_start_sequence_ends_in_an_active_project(tmp_path):
    """Protecting against a false claim must not block the legitimate update that follows it."""
    engine, _ = make_agent(tmp_path, [])
    assert _ingest(engine, "We should work on Mapiko.", "task").type == "message"          # proposal
    assert _ingest(engine, "Let's do it.", "task").type == "message"                       # acceptance
    assert _ingest(engine, "We are working on Mapiko now.", "task").type == "task"         # explicit start


def test_the_delivered_context_does_not_file_a_proposal_under_active_projects(tmp_path):
    """The layer the trace indicted: the section HEADING is itself a status claim."""
    engine, _ = make_agent(tmp_path, [])
    proposal = _ingest(engine, "We should work on Mapiko.", "task")
    started = _ingest(engine, "We are working on Kuvala.", "task")
    injection = organise_for_injection(
        [RetrievedMemory(point=p, score=1.0, reason="semantic") for p in (proposal, started)], engine.graph)
    active = " ".join(injection["activeProjects"])
    assert "Mapiko" not in active and "Kuvala" in active
    assert any("Mapiko" in line for section in injection.values() if isinstance(section, list) for line in section)


def test_a_proposal_is_tagged_and_delivered_under_a_heading_that_states_its_status(tmp_path):
    """90.N iteration 2. Refusing the activity claim must not delete the information: the 13/16 re-scoring showed the
    proposal stopped being offered at all once it left `activeProjects`. It is tagged with the same keyword mechanism
    the store already uses for questions and ephemeral observations, and delivered under its own heading."""
    from hmgfu.context_render import render_injection
    engine, _ = make_agent(tmp_path, [])
    proposal = _ingest(engine, "We should work on Mapiko.", "task")
    started = _ingest(engine, "We are working on Kuvala.", "task")
    assert "_intent" in proposal.keywords and "_intent" not in started.keywords
    injection = organise_for_injection(
        [RetrievedMemory(point=p, score=1.0, reason="semantic") for p in (proposal, started)], engine.graph)
    assert any("Mapiko" in line for line in injection["proposals"])
    assert "Mapiko" not in " ".join(injection["activeProjects"])
    assert "Kuvala" in " ".join(injection["activeProjects"])
    text = render_injection(injection)
    assert "Mapiko" in text and "Proposals, wishes and plans" in text
    heading, mapiko = text.index("Proposals, wishes and plans"), text.index("Mapiko")
    assert heading < mapiko                      # the status is stated BEFORE the sentence it qualifies


NOT_PROPOSALS = [
    ("In 2019 I lived in Lisbon.", "past"),
    ("For a story I am writing: my name is Oscar.", "fiction"),
    ("My friend says 'my project is Mapiko'.", "citation"),
]


@pytest.mark.parametrize("text,kind", NOT_PROPOSALS)
def test_only_an_intention_is_tagged_a_proposal(tmp_path, text, kind):
    """A past, fiction or citation clause also has no assertion — it is NOT a proposal, and must never render under
    the proposals heading. Found by sweeping the modalities before trusting the tag, not by a failing run."""
    engine, _ = make_agent(tmp_path, [])
    assert "_intent" not in _ingest(engine, text, "message").keywords, kind
