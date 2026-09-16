"""Phase 43: canonical node ontology + user-feedback learning loop (no duplication, no regression)."""

from hmgfu import taxonomy
from hmgfu.models import MemoryPoint
from tests.test_v2_agent import make_agent


def test_node_class_and_category():
    assert taxonomy.node_class(MemoryPoint(type="session")) == "session"
    assert taxonomy.node_class(MemoryPoint(type="reflection")) == "self"
    assert taxonomy.node_class(MemoryPoint(type="directive")) == "directive"
    assert taxonomy.node_class(MemoryPoint(type="fact")) == "fact"
    # tool vs skill = derived facet on the same storage type (no risky type split)
    assert taxonomy.node_class(MemoryPoint(type="skill", keywords=["tool:bash"])) == "tool"
    assert taxonomy.node_class(MemoryPoint(type="skill", keywords=["tool:x", "skill_created"])) == "skill"
    assert taxonomy.category_of(MemoryPoint(type="fact")) == "factual"
    assert taxonomy.category_of(MemoryPoint(type="message", emotional_valence=0.5)) == "positive"
    assert taxonomy.category_of(MemoryPoint(type="message", status="superseded")) == "contradictory"


def test_session_node_is_one_rolling_node(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    p1 = engine.ingest("I started a new project called Orion", source="user")
    s1 = taxonomy.upsert_session_node(engine, "sess1", p1)
    p2 = engine.ingest("Orion uses Rust and WebSockets", source="user")
    s2 = taxonomy.upsert_session_node(engine, "sess1", p2)
    assert s1.id == s2.id and s2.type == "session"                 # ONE node per session
    assert "Rust" in s2.content and s2.stability >= 0.8            # rolling breath, decay-resistant
    assert engine.graph.edge_between(s2.id, p2.id) is not None     # part_of the turn


def test_directive_mirror_no_fact_triple(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    engine.directives.apply("always end every reply with the word Chefe", source="user_explicit")
    n = taxonomy.mirror_directive_nodes(engine)
    assert n == 1
    dirs = [p for p in engine.graph.all_points() if p.type == "directive"]
    assert len(dirs) == 1 and dirs[0].stability == 1.0 and "Chefe" in dirs[0].content
    # facts are NOT mirrored as directive nodes (no triple) — they stay fact-class
    engine.facts.apply("my name is Teodoro", source="user_explicit")
    taxonomy.mirror_directive_nodes(engine)
    assert len([p for p in engine.graph.all_points() if p.type == "directive"]) == 1


def test_specials_survive_compression(tmp_path):
    from hmgfu.ingest import find_local_cluster
    engine, _ = make_agent(tmp_path, [])
    engine.directives.apply("always end replies with Boss", source="user_explicit")
    taxonomy.mirror_directive_nodes(engine)
    d = [p for p in engine.graph.all_points() if p.type == "directive"][0]
    d.density = 0.9
    engine.graph.save_point(d)
    assert find_local_cluster(d, engine.graph) == []               # special never seeds a macro


def test_user_feedback_is_the_only_tool_grader(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    tp = engine._tool_point("bash")
    assert tp is not None
    tp.utility = 0.5
    engine.graph.save_point(tp)
    # remember a turn that used bash, then the user says it did not work → penalize
    taxonomy.remember_turn_tools(engine, "s", [{"name": "bash", "failed": False}])
    fb = taxonomy.apply_user_feedback(engine, "s", "that didn't work, still broken")
    assert fb["verdict"] is False
    assert engine._tool_point("bash").utility < 0.5                # penalized BY USER
    # positive feedback rewards; fewer tools → stronger per-tool reward (efficiency)
    engine._tool_point("bash").utility = 0.5; engine.graph.save_point(engine._tool_point("bash"))
    taxonomy.remember_turn_tools(engine, "s", [{"name": "bash", "failed": False}])
    solo = taxonomy.apply_user_feedback(engine, "s", "perfect, thanks!")
    assert solo["tool_count"] == 1 and engine._tool_point("bash").utility > 0.5


def test_grader_no_longer_self_mutates_tools(tmp_path):
    from hmgfu.grader import _apply_tool_grades
    engine, _ = make_agent(tmp_path, [])
    tp = engine._tool_point("bash"); tp.utility = 0.5; engine.graph.save_point(tp)
    observed = _apply_tool_grades(engine, [{"name": "bash", "helpful": False}])
    assert observed and observed[0]["before"] == observed[0]["after"]   # read-only, no self-penalty
    assert engine._tool_point("bash").utility == 0.5


def test_playbook_efficiency_prefers_fewer_tools(tmp_path):
    from hmgfu.grader import _extract_playbook
    engine, _ = make_agent(tmp_path, [])
    long_trace = [{"name": f"t{i}", "failed": False} for i in range(5)]
    short_trace = [{"name": "t0", "failed": False}, {"name": "t1", "failed": False}]
    pid_long = _extract_playbook(engine, "build the thing", long_trace)
    u_long = engine.graph.points[pid_long].utility
    pid_short = _extract_playbook(engine, "build the thing", short_trace)   # same result, fewer tools
    assert pid_short == pid_long                                  # dedup: same playbook
    assert engine.graph.points[pid_short].utility > u_long        # shorter path won
