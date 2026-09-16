"""Phase 92.E2 (completion) — occurrence of a value is not a request for a format, and a macro is derived.

The independent verification of the first E2 delivery found two gaps, both reproduced before this
change (`reports/codex_review_92e2/probe.py`):

  * F1. `directive_candidate_supported` accepted a literal format whenever its value appeared
    ANYWHERE in the message. So a candidate `output_prefix=none` survived "Never start your replies
    with the word none" (the instruction NEGATES it) and "…; none of your guesses should replace
    evidence" (an incidental mention). Presence is not authorisation: the plan asks for evidence that
    a format was REQUESTED, with its scope and modality.
  * F2. Derived points were separated by `source in (assistant, dream) AND type != "macro"`, so the
    SAME invented expansion went to the labelled derived section as a message and straight into
    `relevantFacts` as a macro. A macro is a consolidation: it may say WHERE to look, it may not
    stand in as proof.

Neither is fixed with a phrase list, and the legitimate positives are kept: an explicitly requested
`none` prefix still works, and a content spec is still exempt from the literal test.
"""

from __future__ import annotations

import pytest

from hmgfu.directives import DirectiveStore
from hmgfu.models import MemoryPoint, QueryPoint, RetrievedMemory
from hmgfu.retrieve import organise_for_injection
from hmgfu.store import HMGGraph

CAND = {"kind": "output_prefix", "value": "none", "instruction": "x", "fallback_text": ""}


def _apply(tmp_path, text, name):
    st = DirectiveStore(str(tmp_path / name))
    st.apply(text, "user_explicit", detected=dict(CAND, instruction=text))
    return {d["kind"]: d.get("value") for d in st.active()}, st


# --- F1: a format has to be REQUESTED -------------------------------------------------------------
@pytest.mark.parametrize("text,why", [
    ("Never start your replies with the word none.", "the instruction negates the format"),
    ("Do not start your replies with the word none.", "the instruction negates the format"),
    ("Always search memory when unsure; none of your guesses should replace evidence.",
     "an incidental mention of the value is not a request"),
    ("for now on always use memory search when you are not sure of the unswer",
     "a search policy is not a format request"),
])
def test_a_value_that_merely_occurs_does_not_authorise_a_format(tmp_path, text, why):
    kinds, st = _apply(tmp_path, text, "a.db")
    assert "output_prefix" not in kinds, f"{why}: {kinds}"
    assert st.enforce("Answer.") == "Answer.", why


@pytest.mark.parametrize("text", [
    "Always start your replies with the word none.",
    "Please begin every reply with none.",
])
def test_a_format_the_user_really_requested_is_still_kept(tmp_path, text):
    """The protection must not be vacuous: an explicitly requested `none` survives."""
    kinds, st = _apply(tmp_path, text, "b.db")
    assert kinds.get("output_prefix") == "none"
    assert st.enforce("Answer.").startswith("none")


def test_a_content_spec_is_still_exempt_from_the_literal_test(tmp_path):
    st = DirectiveStore(str(tmp_path / "c.db"))
    text = "always finish your replies with something funny"
    st.apply(text, "user_explicit", detected={"kind": "conversation_closer", "value": "a short joke",
                                              "instruction": text, "fallback_text": ""})
    assert {d["kind"]: d.get("value") for d in st.active()}.get("conversation_closer") == "a short joke"


# --- F2: a macro is derived too -------------------------------------------------------------------
def _sections(tmp_path, point_type):
    g = HMGGraph(str(tmp_path / f"g_{point_type}.db"))
    p = MemoryPoint(type=point_type, content="Earlier discussion of ACME-7.",
                    summary="ACME-7 means Invented Expansion.", title="consolidation",
                    source="dream", embedding=[0.0] * 8)
    g.save_point(p)
    q = QueryPoint(text="what does ACME-7 stand for?", conversation_act="question")
    inj = organise_for_injection([RetrievedMemory(point=p, score=1.0, reason="semantic")],
                                 g, canonical=[], query=q)
    g.close()
    return {k: v for k, v in inj.items() if isinstance(v, list) and v}


@pytest.mark.parametrize("point_type", ["message", "macro"])
def test_a_derived_claim_is_separated_whatever_its_type(tmp_path, point_type):
    """The same invented expansion must not change status by being stored as a macro."""
    sections = _sections(tmp_path, point_type)
    assert "relevantFacts" not in sections, f"a derived {point_type} reached the authoritative section"
    assert "userIdentity" not in sections, f"a derived {point_type} reached identity"
    assert sections.get("assistantSaid"), f"the derived {point_type} was lost instead of labelled"


def test_a_macro_keeps_its_pattern_marker(tmp_path):
    """It may still say WHERE to look; it just may not stand in as proof."""
    assert any("[pattern]" in line for line in _sections(tmp_path, "macro")["assistantSaid"])


def test_a_user_point_is_not_moved_to_the_derived_section(tmp_path):
    g = HMGGraph(str(tmp_path / "u.db"))
    p = MemoryPoint(type="message", content="ACME-7 means Atlas Control Mesh.",
                    summary="definition", source="user", embedding=[0.0] * 8)
    g.save_point(p)
    q = QueryPoint(text="what does ACME-7 stand for?", conversation_act="question")
    inj = organise_for_injection([RetrievedMemory(point=p, score=1.0, reason="semantic")],
                                 g, canonical=[], query=q)
    g.close()
    assert not inj.get("assistantSaid"), "the user's own words were labelled as derived"
