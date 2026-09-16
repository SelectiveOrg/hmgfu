"""First-class canonical facts: detection, keyed supersession, verbatim injection, node demotion."""

from hmgfu.facts import FactStore, detect_fact
from hmgfu.retrieve import make_query_point, build_llm_context
from tests.test_v2_agent import make_agent


def test_detect_fact_cases():
    assert detect_fact("my name is Sebastian") == {"key": "name", "value": "Sebastian", "supersedes": None, "trusted": True}   # R2: explicit form is trusted
    assert detect_fact("Correction: I'm not Sebastian. My name is Teodoro Ferreira.") == \
        {"key": "name", "value": "Teodoro Ferreira", "supersedes": "Sebastian", "trusted": True}
    assert detect_fact("my favorite color is teal") == \
        {"key": "favorite_color", "value": "teal", "supersedes": None}
    # Phase 62: "call me X" is a FORM OF ADDRESS (closed slot identity.alias), not the legal name
    assert detect_fact("call me Teo") == {"key": "identity.alias", "value": "Teo", "supersedes": None}
    assert detect_fact("I'm not Sebastian") == {"key": "name", "clear_value": "Sebastian"}
    assert detect_fact("what is my name?") is None
    assert detect_fact("I am tired") is None            # transient, not a durable fact


def test_keyed_supersession_and_persistence(tmp_path):
    s = FactStore(str(tmp_path / "f.db"))
    s.apply("my name is Sebastian")
    assert s.active()[0]["value"] == "Sebastian"
    r = s.apply("actually my name is Teodoro Ferreira")   # new value supersedes
    assert r["value"] == "Teodoro Ferreira" and r["prev"] == "Sebastian"
    active = s.active()
    assert len(active) == 1 and active[0]["value"] == "Teodoro Ferreira"
    # survives a restart
    s2 = FactStore(str(tmp_path / "f.db"))
    assert s2.active()[0]["value"] == "Teodoro Ferreira"
    assert s2.active()[0]["prev"] == "Sebastian"


def test_render_lines_state_current_value_only(tmp_path):
    s = FactStore(str(tmp_path / "f.db"))
    s.apply("my name is Sebastian")
    s.apply("my name is Teodoro")
    lines = s.render_lines()
    # CURRENT value only — the superseded name must NOT appear (bench L4: it leaked into answers)
    assert lines == ["Your name is Teodoro"]
    assert not any("sebastian" in line.lower() for line in lines)


def test_agent_correction_supersedes_stale_nodes_and_injects_canonical(tmp_path):
    """The full Sebastian scenario, deterministically (fake model)."""
    engine, fake = make_agent(tmp_path, [
        {"content": "Noted.", "tool_calls": []},
        {"content": "Understood.", "tool_calls": []},
        {"content": "Your name is Teodoro.", "tool_calls": []},
    ])
    engine.agent_chat("Remember: my name is Sebastian.", explicit=True)
    engine.agent_chat("Correction: I'm not Sebastian. My name is Teodoro Ferreira.", explicit=True)
    # canonical fact now says Teodoro (corrected from Sebastian)
    assert engine.facts.active()[0]["value"] == "Teodoro Ferreira"
    # the stale "Sebastian" episodic node is demoted out of recall
    seb_active = [p for p in engine.graph.points.values()
                  if "sebastian" in p.content.lower() and p.status == "active"
                  and p.type not in ("skill",)]
    # any remaining active Sebastian node must ALSO contain the correction (the correction msg)
    assert all("teodoro" in p.content.lower() for p in seb_active)
    # the injected context carries the current canonical value verbatim at the front — and does
    # NOT volunteer the superseded name anywhere (bench L4 leak fix)
    q = make_query_point("what is my name?", engine.embed, engine.sensitizer)
    ctx, _ = build_llm_context(q, engine.graph, canonical=engine.facts.render_lines(),
                               superseded=engine.facts.superseded_values())
    assert "Your name is Teodoro Ferreira" in ctx
    assert "sebastian" not in ctx.lower()      # neither the canonical line NOR a recalled memory
    assert ctx.index("Teodoro Ferreira") < ctx.index("Recent context") if "Recent context" in ctx else True


def test_value_capture_keeps_initials():
    """Live-db regression: 'Teodoro H. Ferreira' must not truncate at the initial's period."""
    assert detect_fact("My name is Teodoro H. Ferreira.") == \
        {"key": "name", "value": "Teodoro H. Ferreira", "supersedes": None, "trusted": True}   # R2: explicit form is trusted


def test_negation_only_clears_matching_value(tmp_path):
    s = FactStore(str(tmp_path / "f.db"))
    s.apply("my name is Sebastian")
    s.apply("I'm not Sebastian")               # negation matching the stored value → clears it
    assert s.active() == []
    # negation NOT matching current value is a no-op
    s.apply("my name is Teo")
    s.apply("I'm not Bob")
    assert s.active()[0]["value"] == "Teo"


def test_supersede_named_stale_targets_the_named_value(tmp_path):
    """B6: a correction NAMES the stale value → supersede the fact asserting it directly (the
    same-attribute swap dream.contradiction_heuristic misses), I1-safe, without cutting a
    coincidental mention of that value on a different subject."""
    from hmgfu.facts import supersede_named_stale
    engine, _ = make_agent(tmp_path, [])
    stale = engine.ingest("my favorite color is blue", source="user")
    other = engine.ingest("the ocean looks blue today", source="user")   # same value, other subject
    winner = engine.ingest("my favorite color is green", source="user_explicit")
    res = supersede_named_stale(engine.graph, winner, "blue", "green")
    assert res["ambiguous"] is None
    assert stale.id in res["superseded"]                       # the named stale fact IS superseded
    assert engine.graph.points[stale.id].status == "superseded"
    assert other.id not in res["superseded"]                   # subject guard: coincidence protected
    assert engine.graph.points[other.id].status == "active"
    assert engine.graph.points[winner.id].status == "active"   # I1: the user_explicit winner never falls


def test_apply_correction_supersedes_named_stale_and_signals(tmp_path, monkeypatch):
    """B6 end-to-end: _apply_correction supersedes the named stale fact AND (Regulator on) records the
    absorbing correction signal — even for a value swap the contradiction heuristic misses."""
    from hmgfu import config
    from hmgfu.grader import _apply_correction
    monkeypatch.setattr(config, "REGULATOR_ENABLED", True)
    engine, _ = make_agent(tmp_path, [])
    stale = engine.ingest("my favorite color is blue", source="user")
    applied = _apply_correction(engine, {"right": "my favorite color is green", "wrong": "blue"},
                                "no, it is not blue, my favorite color is green")
    assert applied and engine.graph.points[stale.id].status == "superseded"
    assert engine.regulator.evaluate(stale.id)[1] == "superseded"   # absorbing correction signal fired


def test_apply_correction_maputo_beira_location_swap(tmp_path, monkeypatch):
    """B6: the Valencia↔Aveiro location value-swap supersedes end-to-end through _apply_correction —
    the same mechanism as blue↔green on a different attribute (proves generality once the correction
    reaches _apply_correction; the router's action-gate is a separate upstream concern)."""
    from hmgfu import config
    from hmgfu.grader import _apply_correction
    monkeypatch.setattr(config, "REGULATOR_ENABLED", True)
    engine, _ = make_agent(tmp_path, [])
    stale = engine.ingest("moro em Valencia", source="user")
    applied = _apply_correction(engine, {"right": "Aveiro", "wrong": "Valencia"},
                                "não, isso está errado, eu não moro em Valencia, moro na Aveiro")
    assert applied and engine.graph.points[stale.id].status == "superseded"
    assert engine.regulator.evaluate(stale.id)[1] == "superseded"


def test_supersede_named_stale_value_only_right_uses_context(tmp_path):
    """The live case: the perceiver returns `right` as a BARE value ("verde"), so the winner node
    carries no subject — the subject must come from the correction message context. The stale fact is
    still matched; an unrelated same-value node is still protected."""
    from hmgfu.facts import supersede_named_stale
    engine, _ = make_agent(tmp_path, [])
    stale = engine.ingest("my favorite color is blue", source="user")
    decoy = engine.ingest("the ocean looks blue today", source="user")
    winner = engine.ingest("green", source="user_explicit")               # sparse: value only
    res = supersede_named_stale(engine.graph, winner, "blue", "green",
                                context="no, my favorite color is not blue, it is green")
    assert res["superseded"] == [stale.id] and decoy.id not in res["superseded"]   # subject from context


def test_supersede_named_stale_unique_bearer_rephrased_subject(tmp_path):
    """The correction may REPHRASE the subject ("sou de Aveiro" vs stored "moro em Valencia"), sharing only
    the value — a UNIQUE bearer of the old value is still an unambiguous target (the live Valencia case)."""
    from hmgfu.facts import supersede_named_stale
    engine, _ = make_agent(tmp_path, [])
    stale = engine.ingest("moro em Valencia", source="user")
    winner = engine.ingest("Aveiro", source="user_explicit")
    res = supersede_named_stale(engine.graph, winner, "Valencia", "Aveiro",
                                context="não, eu não sou de Valencia, sou da Aveiro")
    assert res["superseded"] == [stale.id] and res["ambiguous"] is None


def test_supersede_named_stale_ambiguous_multiple_bearers_does_not_fire(tmp_path):
    """Absorbing → na dúvida não disparar: many bearers of the old value + no subject to pick one → fire
    nothing and flag it (the value alone can't resolve to a single existing fact)."""
    from hmgfu.facts import supersede_named_stale
    engine, _ = make_agent(tmp_path, [])
    engine.ingest("my shirt is blue", source="user")
    engine.ingest("the door is blue", source="user")
    winner = engine.ingest("green", source="user_explicit")
    res = supersede_named_stale(engine.graph, winner, "blue", "green", context="not blue, green")
    assert res["superseded"] == [] and res["ambiguous"] == "ambiguous_subject"


def test_supersede_named_stale_no_target_does_not_fire(tmp_path):
    """Absorbing → na dúvida não disparar: a correction whose `wrong` value matches NO existing fact
    supersedes nothing and returns the reason for the log (the target must resolve to a stored fact)."""
    from hmgfu.facts import supersede_named_stale
    engine, _ = make_agent(tmp_path, [])
    engine.ingest("my favorite color is blue", source="user")
    winner = engine.ingest("my favorite sport is tennis", source="user_explicit")
    res = supersede_named_stale(engine.graph, winner, "chess", "tennis",
                                context="actually my favorite sport is tennis not chess")
    assert res["superseded"] == [] and res["ambiguous"] == "no_target"    # 'chess' is not a stored fact
    assert engine.graph.active_points()                                   # nothing was wrongly cut
