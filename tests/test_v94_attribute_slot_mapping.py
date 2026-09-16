"""Phase 90.H3 (H-C) — the extractor's contract vocabulary must map to the slots it names: `SPAN_PROMPT` asks for "what they are
currently working on", so an attribute phrased that way is the main project. Negatives keep precision: descriptions, third-party
attributes, tasks/plans/activities stay open keys (no write); hedged or predicate-shaped values are still rejected."""
from __future__ import annotations

from hmgfu.fact_spans import extract_spans
from hmgfu.slots import is_slot, normalise_key


def _fake(facts):
    return lambda prompt, schema: {"facts": facts}


def test_contract_phrases_for_the_project_map_to_project_main():
    for attr in ("working on", "currently working on", "what I am working on", "what we are working on", "current project", "main project"):
        assert normalise_key(attr) == "project.main", attr
    dets = extract_spans("we are actually working on HMG, this memory system of yours",
                         _fake([{"attribute": "working on", "value": "HMG"}]))
    assert [(d["key"], d["value"]) for d in dets] == [("project.main", "HMG")]


def test_descriptions_third_parties_and_activities_stay_open():
    for attr in ("memory system", "where they live", "task", "activity", "plan for today", "hobby", "what I did today", "working hours"):
        k = normalise_key(attr)
        assert not is_slot(k), (attr, k)
    # a relative's / someone else's project is dropped at the extractor (third-party attribute), whatever the alias index says
    assert extract_spans("my brother is working on HMG", _fake([{"attribute": "their project", "value": "HMG"}])) == []
    # an open key never writes on the spans path
    assert extract_spans("we are working on HMG", _fake([{"attribute": "memory system", "value": "HMG"}])) == []
    # a third-party SENTENCE never reaches the extractor on the production path (apply_spans drops it before the model call)
    from hmgfu.facts import FactStore
    from hmgfu.fact_spans import apply_spans
    import tempfile, os
    store = FactStore(os.path.join(tempfile.mkdtemp(), "f.db"))
    extractor = lambda text: extract_spans(text, _fake([{"attribute": "working on", "value": "HMG"}]))
    assert apply_spans(store, "my colleague is working on HMG", "user_explicit", extractor) == []


def test_hedged_or_predicate_values_are_still_rejected():
    assert extract_spans("maybe I'll work on HMG", _fake([{"attribute": "working on", "value": "maybe HMG"}])) == []
    assert extract_spans("we are working on it", _fake([{"attribute": "working on", "value": "it"}])) == []
    assert extract_spans("we are working on the weather report for tomorrow",
                         _fake([{"attribute": "working on", "value": "the weather report for tomorrow"}])) == []
