"""Phase 86.1 — the aggregation cue and the per-question depth: precision on the sealed routing set and the write sets (no
first-person fact statement fires), the LongMemEval count/sum questions fire, plain recall does not; the setting is off by default."""
from __future__ import annotations

import json
import os
from types import SimpleNamespace

from hmgfu.query_depth import depth_for, is_aggregation

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_aggregation_questions_fire_and_plain_recall_does_not():
    for q in ["How many days did I take social media breaks in total?", "How much total money have I spent on bike-related expenses?",
              "How many different doctors did I visit?", "How many pages of the book have I read so far?",
              "Quantas vezes fui ao médico este ano?", "Quanto gastei no total em livros?", "How many weddings have I attended this year?"]:
        assert is_aggregation(q), q
    for q in ["What is my name?", "Where do I live these days?", "What's my dog called?", "Qual é a minha cor favorita?",
              "What time did I go to bed before the appointment?", "Remind me what I told you about my job.", "Onde é que eu trabalho?"]:
        assert not is_aggregation(q), q


def test_no_fact_statement_in_the_write_sets_fires():
    fired = []
    for v in (1, 2, 3, 4, 5, 6, 7):
        path = os.path.join(ROOT, "scripts", "oracles", f"write_set_v{v}.json")
        for it in json.load(open(path, encoding="utf-8"))["items"]:
            if it.get("expect") and is_aggregation(it["text"]):
                fired.append(it["text"])
    assert fired == [], fired[:5]


def test_routing_set_only_the_aggregations_fire():
    turns = json.load(open(os.path.join(ROOT, "scripts", "oracles", "routing_v1.json"), encoding="utf-8"))["turns"]
    fired = [t["text"] for t in turns if is_aggregation(t["text"])]
    assert all(("how many" in t.lower() or "quantos" in t.lower() or "quantas" in t.lower()) for t in fired), fired


def test_depth_off_by_default_and_on_when_set():
    s = SimpleNamespace(get=lambda k: {"retrieval_limit": 12, "retrieval_limit_aggregate": 0}[k])
    assert depth_for("How many weddings have I attended?", s) == 12
    assert depth_for("What is my name?", s) == 12
    s2 = SimpleNamespace(get=lambda k: {"retrieval_limit": 12, "retrieval_limit_aggregate": 20}[k])
    assert depth_for("How many weddings have I attended?", s2) == 20
    assert depth_for("What is my name?", s2) == 12
    assert depth_for("How many weddings have I attended?", s2, default=10) == 20 and depth_for("What is my name?", s2, default=10) == 10
