"""Phase 69.6/69.7 — argument completion keeps explicit place/time; widget grounding fills what is missing;
benchmark oracles reject failed searches and negated/past/uncertain truths."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from hmgfu.deixis import complete_query, ground_widget_props

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


def test_complete_query_keeps_explicit_place_and_relative_time():
    facts = [{"key": "identity.location", "value": "Quelimane"}]
    rt = SimpleNamespace(local_date="2026-09-05")
    q, added = complete_query("Lisbon weather tomorrow", "Weather for Lisbon tomorrow", rt, facts)
    assert "Quelimane" not in q and "2026-09-05" not in q and "2026-09-06" in q and added == ["date"]
    q, added = complete_query("weather today", "what is the weather today?", rt, facts)
    assert "Quelimane" in q and "2026-09-05" in q and added == ["location", "date"]
    q, added = complete_query("weather in Aveiro", "weather in Aveiro please", rt, facts)
    assert "Quelimane" not in q


def test_widget_grounding_adds_only_missing_values():
    props = {"text": "car link: https://example.test/car"}
    assert ground_widget_props(props, ["car link: https://example.test/car", "profile link: https://example.test/profile"])
    assert "https://example.test/profile" in props["text"] and props["text"].count("https://example.test/car") == 1
    rows = {"rows": [{"name": "car", "url": "https://example.test/car"}]}
    assert ground_widget_props(rows, ["car link: https://example.test/car", "profile link: https://example.test/profile"])
    assert len(rows["rows"]) == 2 and not ground_widget_props(rows, ["car link: https://example.test/car"])


def test_tool_bench_requires_a_successful_search():
    from bench_tool_precision import evaluate
    case = {"id": "failed_search", "q": "Weather for Chimoio", "needs_search": True, "arg_tokens": ["chimoio"], "asks_effect": False}
    r = {"response": "I cannot get the weather.", "tool_trace": [{"name": "brave_web_search", "arguments": {"query": "chimoio"},
                                                                 "failed": True, "blocked": False, "result": '{"error": "offline"}'}]}
    assert not evaluate(case, r)["expect_ok"]
    r["tool_trace"][0]["failed"] = False
    r["tool_trace"][0]["result"] = "Chimoio: 24°C"
    assert evaluate(case, {**r, "response": "Chimoio is 24°C."})["expect_ok"]


def test_truth_bench_present_rejects_negated_past_and_uncertain_clauses():
    from bench_recall_truth import _present
    assert _present("Java was my old preference.", ["Java"]) == []
    assert _present("I do not know whether Java is current.", ["Java"]) == []
    assert _present("Java is not my favorite language.", ["Java"]) == []
    assert _present("Your favorite language is Java, not Python.", ["Java"]) == ["Java"]     # the asserted clause counts
    assert _present("Your favorite programming language is Java.", ["Java"]) == ["Java"]
    # 74.4: historical markers reject the value only when ADJACENT to it — narration elsewhere in the clause is not a retraction
    assert _present("You started project Echo because the old spreadsheet kept breaking.", ["Echo"]) == ["Echo"]
    assert _present("You were working on Atlas when you met Nelson.", ["Atlas"]) == ["Atlas"]
    assert _present("Your favorite color was amber.", ["amber"]) == []
    assert _present("A sua cor favorita era burgundy.", ["burgundy"]) == []
    assert _present("It used to be Java.", ["Java"]) == []
    assert _present("the previous colour amber", ["amber"]) == []
    assert _present("Your previous colour was amber; now it is burgundy.", ["burgundy"]) == ["burgundy"]
    # 74.4b: a contraction needs its apostrophe; "no" is a retraction only as an opener or in "no longer/more/idea"
    assert _present("You started project Atlas because a client asked for it.", ["Atlas"]) == ["Atlas"]
    assert _present("You started Delta because the school had no site at all.", ["Delta"]) == ["Delta"]
    assert _present("No, your favorite color is amber.", ["amber"]) == ["amber"]          # the asserted clause still counts
    assert _present("No, it is not Java.", ["Java"]) == []
    assert _present("Java is no longer my favorite.", ["Java"]) == []
    assert _present("It isn't Java.", ["Java"]) == []
    assert _present("A escola não tinha site, por isso começaste o Delta.", ["Delta"]) == ["Delta"]
    assert _present("A tua cor favorita não é amber.", ["amber"]) == []


def test_truth_bench_present_keeps_dotted_values_and_grounding_reads_escaped_units():
    from bench_recall_truth import _present
    ctx = "Your car location link is http://49.13.201.0/ui/sharing/abc. Your name is Teodoro."
    assert _present(ctx, ["49.13.201.0"]) == ["49.13.201.0"]
    import json
    from hmgfu.grounding import ungrounded_claims
    assert ungrounded_claims("It is 64°F today", [json.dumps({"snippet": "High 64°F, low 50°F"})]) == []
    assert ungrounded_claims("It is 27°C", ["Temperatura: 27&deg;C"]) == []
    assert ungrounded_claims("It is 27°C", [json.dumps({"snippet": "humidity 27%"})]) == ["27°C"]
