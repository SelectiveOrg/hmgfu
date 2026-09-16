"""Phase 28: retroactive hygiene, ephemeral facts, web_search + unknown-tool recovery."""

import json

from hmgfu import fu_math
from hmgfu.hygiene import hygiene_pass, is_ephemeral
from hmgfu.models import QueryPoint
from tests.conftest import fake_embed
from tests.test_v2_agent import make_agent


def test_is_ephemeral_detection():
    assert is_ephemeral("The current weather in Valencia is approximately 27°C with scattered clouds.")
    assert is_ephemeral("wind speeds of about 13.9 km/h and humidity of 65%")
    assert is_ephemeral("the current price of bitcoin is $60,000")
    assert not is_ephemeral("My name is Teodoro Ferreira")
    assert not is_ephemeral("Valencia is the capital of Spain")   # durable geography


def test_hygiene_dedups_existing_pollution(tmp_path):
    """The live-trace scenario: old duplicate Sebastian facts predate the ingest dedup."""
    engine, _ = make_agent(tmp_path, [])
    ids = []
    for i in range(4):   # simulate pre-fix pollution: bypass ingest dedup via direct save
        p = engine.ingest(f"pollution seed {i}", source="user")     # unique seeds
        pt = engine.graph.points[p.id]
        pt.content = "Your name is Sebastian."
        pt.summary = "Your name is Sebastian."
        pt.type = "fact"
        pt.embedding = fake_embed("Your name is Sebastian.")
        pt.timestamp = f"2026-06-0{i+1}T00:00:00+00:00"
        engine.graph.save_point(pt)
        ids.append(p.id)
    report = hygiene_pass(engine)
    assert report["duplicates_superseded"] == 3          # 4 → 1 (newest kept)
    active = [i for i in ids if engine.graph.points[i].status == "active"]
    assert len(active) == 1
    assert engine.graph.points[active[0]].timestamp.startswith("2026-06-04")  # newest kept


def test_hygiene_reclassifies_assistant_facts_and_junk(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    a = engine.ingest("The current weather in Valencia is 27C sunny today ok", source="user")
    pa = engine.graph.points[a.id]; pa.source = "assistant"; pa.type = "fact"
    pa.keywords = [k for k in pa.keywords if k != "_ephemeral"]   # simulate pre-fix node
    engine.graph.save_point(pa)
    b = engine.ingest("junk seed content here", source="user")
    pb = engine.graph.points[b.id]
    pb.content = "You are currently living in your current location."
    pb.type = "fact"
    engine.graph.save_point(pb)
    report = hygiene_pass(engine)
    assert report["assistant_facts_reclassified"] >= 1
    assert engine.graph.points[a.id].type == "message"   # no longer canon
    assert engine.graph.points[b.id].status == "superseded"   # junk demoted
    assert report["ephemeral_tagged"] >= 1               # the weather line got tagged


def test_ephemeral_score_decays_in_hours(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    p = engine.ingest("The current weather in Valencia is 27°C with scattered clouds", source="user")
    pt = engine.graph.points[p.id]
    assert "_ephemeral" in pt.keywords                   # tagged at ingest
    q = QueryPoint(text="weather in Valencia", embedding=fake_embed("weather in Valencia"))
    fresh = fu_math.memory_score(q, pt)
    pt.timestamp = "2026-07-02T00:00:00+00:00"           # ~a day old
    stale = fu_math.memory_score(q, pt)
    assert stale < fresh * 0.15                          # a day-old weather fact is ~dead
    durable = engine.ingest("Valencia is the capital of Spain", source="user")
    assert "_ephemeral" not in engine.graph.points[durable.id].keywords


def test_hygiene_redacts_stale_macro_values(tmp_path):
    """A macro digest that baked in the OLD value gets rewritten to the corrected one."""
    engine, _ = make_agent(tmp_path, [])
    engine.facts.apply("my name is Sebastian")
    engine.facts.apply("actually my name is Teodoro")     # → prev=Sebastian, value=Teodoro
    m = engine.ingest("macro seed", source="dream", mtype="macro")
    pm = engine.graph.points[m.id]
    pm.type = "macro"
    pm.summary = "The person known as Sebastian has a green pet."
    pm.content = pm.summary
    engine.graph.save_point(pm)
    report = hygiene_pass(engine)
    assert report["macro_values_redacted"] == 1
    assert "Teodoro" in engine.graph.points[m.id].summary
    assert "Sebastian" not in engine.graph.points[m.id].summary


def test_web_search_unconfigured_is_honest(monkeypatch, tmp_path):
    from hmgfu import config
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "x.db"))  # empty vault
    from hmgfu.tool_builtins import run_web_search
    out = run_web_search("weather valencia")
    assert "error" in out and "NOT configured" in out["error"]
    assert "Do NOT answer from stale memories" in out["error"]


def test_unknown_tool_fuzzy_reroute(tmp_path, monkeypatch):
    from hmgfu import config
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "x.db"))
    engine, _ = make_agent(tmp_path, [])
    # brave_web_search is now the CANONICAL tool → dispatches directly, no reroute
    out = json.loads(engine.tools.execute_tool("brave_web_search", {"query": "weather"}))
    assert "_rerouted" not in out and "error" in out      # unconfigured, honestly reported
    # a misspelling still fuzzy-reroutes to the real tool
    out2 = json.loads(engine.tools.execute_tool("brave_web_serch", {"query": "weather"}))
    assert "_rerouted" in out2 and "brave_web_search" in out2["_rerouted"]
    # truly unknown → did-you-mean suggestions, no blind reroute
    out3 = json.loads(engine.tools.execute_tool("memory_serch", {"query": "x"}))
    assert "_rerouted" in out3 or "did you mean" in out3.get("hint", "")
