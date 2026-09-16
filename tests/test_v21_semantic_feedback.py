"""Phase 56 gap 2 — feedback classification is SEMANTIC (router polarity), not keyword lists.

The router judges "does this message react to my previous work, and how" by meaning in any
language; the old lexical cue lists survive ONLY as the offline fallback (no model routed the
turn). No Ollama — QueryPoints are constructed directly / via the sanitise path.
"""

from __future__ import annotations

from hmgfu import taxonomy
from hmgfu.models import QueryPoint
from hmgfu.sensitizer import _sanitise
from tests.test_v2_agent import make_agent


def _q(polarity="", extractor="nano", text="x"):
    return QueryPoint(text=text, feedback_polarity=polarity, extractor=extractor)


def test_router_polarity_is_primary_over_keywords():
    # the router judged NEGATIVE; the text happens to contain a positive keyword — semantic wins
    assert taxonomy.classify_feedback("perfect example of what NOT to do",
                                      query=_q("negative")) is False
    assert taxonomy.classify_feedback("hmm ok", query=_q("positive")) is True


def test_multilingual_feedback_without_any_keyword():
    # Portuguese praise that matches NO lexical cue — only the semantic router can catch it
    text = "isso ficou fantastico, adorei o resultado"
    assert taxonomy.classify_feedback(text) is None                    # lexical alone: blind
    assert taxonomy.classify_feedback(text, query=_q("positive")) is True   # semantic: caught


def test_model_routed_turn_without_polarity_is_not_feedback():
    # a model routed the turn and saw no feedback reaction — a stray keyword must NOT override
    # it (that would resurrect the static-lexical behaviour this phase removes)
    assert taxonomy.classify_feedback("the wrong file was mentioned in that doc",
                                      query=_q("", extractor="nano")) is None


def test_lexical_fallback_only_when_no_model_routed():
    # offline fallback extractor (no model) → the lexical scan still works (Rule 11)
    assert taxonomy.classify_feedback("that didn't work, still broken",
                                      query=_q("", extractor="fallback")) is False
    assert taxonomy.classify_feedback("perfect, thanks!", query=None) is True


def test_sanitise_normalises_polarity():
    assert _sanitise({"feedback_polarity": "Positive"})["feedback_polarity"] == "positive"
    assert _sanitise({"feedback_polarity": "meh"})["feedback_polarity"] == ""
    assert _sanitise({})["feedback_polarity"] == ""


def test_apply_user_feedback_uses_router_polarity(tmp_path):
    """End-to-end: PT praise with no lexical cue grades the previous turn's tool UP."""
    engine, _ = make_agent(tmp_path, [])
    tp = engine._tool_point("bash")
    tp.utility = 0.5
    engine.graph.save_point(tp)
    taxonomy.remember_turn_tools(engine, "s", [{"name": "bash", "failed": False}])
    fb = taxonomy.apply_user_feedback(engine, "s", "isso ficou fantastico, adorei",
                                      query=_q("positive"))
    assert fb is not None and fb["verdict"] is True
    assert engine._tool_point("bash").utility > 0.5
