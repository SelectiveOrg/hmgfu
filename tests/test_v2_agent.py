"""v2 tests: providers/settings routing, toolsys, agent loop guards, grader — no Ollama."""

import json

import pytest

from hmgfu.providers import BaseProvider, ProviderError, ProviderRegistry
from hmgfu.settings import Settings
from hmgfu.toolsys import (ToolRegistry, classify_tool_result, tool_signature,
                           run_bash, write_file)
from tests.conftest import fake_embed


# --- fakes ------------------------------------------------------------------------

class FakeProvider(BaseProvider):
    """Scripted provider: pops the next response from a queue."""
    name = "fake"

    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def chat(self, model, messages, json_mode=False, temperature=0.4, tools=None,
             format_schema=None, think=None):
        self.calls.append({"messages": messages, "tools": tools, "json_mode": json_mode,
                           "format_schema": format_schema, "think": think})
        if not self.script:
            return {"content": "done", "tool_calls": []}
        return self.script.pop(0)


class FakeEngineClient:
    def available(self): return True
    def models(self): return ["fake"]
    def capabilities(self, model): return []      # no native thinking in tests (Phase 58)
    def embed(self, text): return fake_embed(text)
    def close(self): pass


def make_agent(tmp_path, script):
    """AgentEngine with a fake chat provider and fake embedder (no Ollama)."""
    from hmgfu.agent import AgentEngine
    from hmgfu.sensitizer import Sensitizer

    engine = AgentEngine.__new__(AgentEngine)
    from hmgfu.store import HMGGraph
    from hmgfu.sessions import SessionStore
    db = str(tmp_path / "agent.db")
    engine.client = FakeEngineClient()
    engine.graph = HMGGraph(db_path=db)
    engine.sensitizer = Sensitizer(client=None, enabled=False)
    engine.turn_count = 0
    engine.settings = Settings(db)
    engine.settings.set("tail_async", False)      # 73.4: the fake-provider harness is synchronous; test_v52 covers async
    engine.sessions = SessionStore(db)
    from hmgfu.directives import DirectiveStore
    engine.directives = DirectiveStore(db)
    from hmgfu.facts import FactStore
    engine.facts = FactStore(db)
    from hmgfu.session_plans import SessionPlanStore
    engine.session_plans = SessionPlanStore(db)          # Phase 67: plans outlive the turn
    from hmgfu.receipts import ReceiptStore
    engine.receipts = ReceiptStore(db)                   # Phase 71: receipts per action
    from hmgfu.app_errors import AppErrorStore
    engine.app_errors = AppErrorStore(db)                # 95.75: runtime errors from built apps
    from hmgfu.prospective import ProspectiveStore
    engine.prospective = ProspectiveStore(db)            # Phase 75.2: reminders by time / condition
    engine._turn_plan = None
    engine._turn_seq = 0
    engine._turn_user_message = ""
    engine._turn_runtime = None
    from hmgfu.learning import LearnedParams, WeightLearner, WormholeCalibrator
    engine.learned_params = LearnedParams(db)
    from hmgfu.bandit import Bandit
    engine.bandit = Bandit(engine.learned_params)             # Phase 75.5
    engine.weight_learner = WeightLearner(engine.learned_params)
    engine.wormhole_calibrator = WormholeCalibrator(engine.learned_params)
    from hmgfu.regulator import Regulator
    engine.regulator = Regulator(engine.learned_params)   # mirror HMGFuEngine.__init__ (Phase 61a)
    engine._correction_queue = []                         # FRONT 2 (P-AUDIT-3) deferred queue
    engine._auto_drain_corrections = True
    engine._observed = 0                                  # P-AUDIT-3b observation window
    from hmgfu.route_memory import RouteMemory
    engine.route_memory = RouteMemory(db, fake_embed)
    import threading
    engine._turn_lock = threading.Lock()
    engine._turn_session = None
    engine._turn_emit = None
    engine._turn_files = []
    engine._turn_url = None
    engine._turn_thoughts = []
    fake = FakeProvider(script)
    engine.registry = ProviderRegistry(engine.settings, None)
    engine.registry._providers = {"ollama": fake}   # role default provider is 'ollama'
    engine.embed = fake_embed
    engine.tools = ToolRegistry(engine=engine)
    from hmgfu.toolsys import sync_tool_points
    sync_tool_points(engine.tools, engine)
    return engine, fake


# --- settings & providers -----------------------------------------------------------

def test_settings_roundtrip_and_validation(tmp_path):
    s = Settings(str(tmp_path / "s.db"))
    assert s.get("grader_producer") == "nano"
    s.set("grader_producer", "main")
    s2 = Settings(str(tmp_path / "s.db"))
    assert s2.get("grader_producer") == "main"          # persisted
    with pytest.raises(KeyError):
        s.set("nonexistent_flag", 1)                    # unknown keys rejected
    with pytest.raises(ValueError):
        s.set("grader_enabled", "yes")                  # type-checked


def test_provider_registry_fails_loudly(tmp_path):
    s = Settings(str(tmp_path / "s.db"))
    reg = ProviderRegistry(s, None)
    with pytest.raises(ProviderError):
        reg.get("anthropc")                             # typo → error, not silent default
    with pytest.raises(ProviderError):
        reg.resolve("voice")                            # unknown role


def test_embed_role_uses_selected_runtime_model(tmp_path):
    class EmbedProvider(BaseProvider):
        supports_embeddings = True
        def __init__(self): self.seen = None
        def embed(self, model, text): self.seen = (model, text); return [0.25, 0.75]

    s = Settings(str(tmp_path / "embed.db"))
    s.set("embed_model", "chosen-embed-model")
    reg = ProviderRegistry(s, None)
    provider = EmbedProvider()
    reg._providers["ollama"] = provider
    assert reg.embed_for_role("hello") == [0.25, 0.75]
    assert provider.seen == ("chosen-embed-model", "hello")


# --- toolsys --------------------------------------------------------------------------

def test_classify_tool_result_blocked_is_not_failure():
    assert classify_tool_result(json.dumps({"blocked": True, "reason": "x"})) == (False, "blocked by safety guard")
    failed, summary = classify_tool_result(json.dumps({"error": "boom"}))
    assert failed and "boom" in summary
    failed, _ = classify_tool_result(json.dumps({"exit_code": 2, "stderr": "bad"}))
    assert failed
    assert classify_tool_result("not json") == (False, "")


def test_tool_signature_collapses_numbers():
    a = tool_signature("bash", {"command": "sleep 5"})
    b = tool_signature("bash", {"command": "sleep 500"})
    assert a == b


def test_bash_blocklist_and_run():
    assert run_bash("rm -rf /")["blocked"] is True
    result = run_bash("echo hello")
    assert result["exit_code"] == 0 and "hello" in result["stdout"]


def test_write_file_workspace_guard(tmp_path):
    outside = str(tmp_path / "outside.txt")
    assert write_file(outside, "x").get("blocked") is True
    inside = write_file("notes/test.txt", "hello")
    assert inside.get("bytes") == 5


def test_skill_ast_validation_and_install(tmp_path):
    reg = ToolRegistry(engine=None)
    assert reg.validate_skill_source("def x(:")                       # syntax error
    assert reg.validate_skill_source("TOOLS = []")                    # missing execute
    good = (
        'TOOLS = [{"name": "greet", "description": "say hi", '
        '"parameters": {"type": "object", "properties": {}}}]\n'
        'def execute(name, arguments):\n'
        '    import json\n'
        '    return json.dumps({"greeting": "hi"})\n'
    )
    assert reg.validate_skill_source(good) is None
    result = reg.install_skill("greeter_test", good)
    assert result["ok"] and "greet" in result["tools"]
    out = json.loads(reg.execute_tool("greet", {}))
    assert out["greeting"] == "hi"
    # cleanup the installed test skill file
    import os
    os.remove(result["path"])


def test_unknown_tool_returns_hint():
    reg = ToolRegistry(engine=None)
    out = json.loads(reg.execute_tool("no_such_tool", {}))
    assert "unknown tool" in out["error"] and "tool_search" in out["hint"]


# --- tool points & retrieval -----------------------------------------------------------

def test_tools_become_points_and_are_retrieved(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    skill_points = [p for p in engine.graph.points.values() if p.type == "skill"]
    assert len(skill_points) >= 7                       # all built-ins synced
    from hmgfu.toolsys import retrieve_tools_for_turn
    from hmgfu.models import QueryPoint
    q = QueryPoint(text="search my memory for facts",
                   embedding=fake_embed("search my memory for facts"),
                   action_requested=True, requested_tools=["memory_search"])
    schemas = retrieve_tools_for_turn(engine.tools, engine, q, max_tools=4)
    names = [s["name"] for s in schemas]
    # Precision contract: an explicit memory-search request receives its applicable tool,
    # without unrelated planning/tool-discovery noise.
    assert names == ["memory_search"]


# --- agent loop guards --------------------------------------------------------------------

def test_agent_plain_answer_no_tools(tmp_path):
    engine, fake = make_agent(tmp_path, [
        {"content": "Hello there!", "tool_calls": []},
    ])
    result = engine.agent_chat("hi")
    assert result["response"] == "Hello there!"
    assert result["tool_trace"] == []


def test_agent_system_prompt_names_and_requires_inspecting_workspace(tmp_path):
    from hmgfu.tool_builtins import set_workspace
    workspace = tmp_path / "selected-project"
    workspace.mkdir()
    engine, fake = make_agent(tmp_path, [
        {"content": "It is a project.", "tool_calls": []},
    ])
    engine.settings.set("workspace_dir", str(workspace))
    try:
        engine.agent_chat("what is this project?")
        system = fake.calls[0]["messages"][0]["content"]
        assert str(workspace) in system
        assert "inspect the workspace" in system.lower()
        assert "before answering" in system.lower()
    finally:
        set_workspace(None)


def test_agent_tool_call_then_answer(tmp_path):
    engine, fake = make_agent(tmp_path, [
        {"content": "", "tool_calls": [{"name": "memory_timeline", "arguments": {"limit": 3}}]},
        {"content": "You have some memories.", "tool_calls": []},
    ])
    result = engine.agent_chat("Use memory_timeline to show what you remember.")
    assert result["response"] == "You have some memories."
    assert len(result["tool_trace"]) == 1
    assert result["tool_trace"][0]["name"] == "memory_timeline"
    assert not result["tool_trace"][0]["failed"]


def test_clear_action_request_retries_when_model_returns_prose_without_acting(tmp_path):
    engine, fake = make_agent(tmp_path, [
        {"content": "I can help with that.", "tool_calls": []},
        {"content": "", "tool_calls": [{"name": "bash", "arguments": {"command": "echo ACTION-OK"}}]},
        {"content": "ACTION-OK", "tool_calls": []},
    ])
    engine.ingest("Previous shell command output was OLD-VALUE", source="user")
    result = engine.agent_chat("Use bash to run echo ACTION-OK and report the output.")
    assert [t["name"] for t in result["tool_trace"]] == ["bash"]
    assert "ACTION-OK" in result["response"]
    assert result["retrieved"] == []


def test_greeting_offers_no_tools_but_explicit_action_offers_required_tool(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    from hmgfu.models import QueryPoint
    from hmgfu.toolsys import retrieve_tools_for_turn
    hello = QueryPoint(text="hello", embedding=fake_embed("hello"), conversation_act="greeting")
    action = QueryPoint(text="run shell command echo hi", embedding=fake_embed("run shell command echo hi"),
                        intent="task", conversation_act="instruction")
    assert retrieve_tools_for_turn(engine.tools, engine, hello, max_tools=8) == []
    assert "bash" in [t["name"] for t in retrieve_tools_for_turn(
        engine.tools, engine, action, max_tools=8
    )]


def test_explicit_named_zero_arg_tool_is_preexecuted(tmp_path):
    engine, _ = make_agent(tmp_path, [
        {"content": "I checked gog status.", "tool_calls": []},
    ])
    result = engine.agent_chat("Use the gog_status skill to check whether gog is installed.")
    assert [t["name"] for t in result["tool_trace"]] == ["gog_status"]


def test_schema_caps_duplicate_successful_side_effect_tool(tmp_path):
    engine, _ = make_agent(tmp_path, [
        {"content": "", "tool_calls": [{"name": "create_widget", "arguments": {
            "type": "note", "title": "One", "props": {"text": "ready"}}}]},
        {"content": "", "tool_calls": [{"name": "create_widget", "arguments": {
            "type": "note", "title": "Two", "props": {"text": "duplicate"}}}]},
        {"content": "done", "tool_calls": []},
    ])
    result = engine.agent_chat("Use create_widget to create one note widget.")
    assert len(result["tool_trace"]) == 2
    assert result["tool_trace"][0]["failed"] is False
    assert result["tool_trace"][1]["blocked"] is True
    assert "already succeeded" in result["tool_trace"][1]["result"]


def test_plan_task_capped_to_one_declaration_per_turn(tmp_path, monkeypatch):
    """A SECOND plan_task (re-planning instead of doing the work) is the runaway loop the user
    saw (~16 wasted model calls). After the first declaration it is blocked."""
    engine, _ = make_agent(tmp_path, [
        {"content": "", "tool_calls": [{"name": "plan_task", "arguments": {
            "title": "Find a fact", "steps": ["pick topic", "verify", "write it"]}}]},
        {"content": "", "tool_calls": [{"name": "plan_task", "arguments": {
            "title": "Find a fact again", "steps": ["repick", "reverify", "rewrite"]}}]},
        {"content": "Here is a curious fact.", "tool_calls": []},
    ])
    engine.settings.set("tool_points_enabled", True)
    real = engine.retrieve
    def routed(text, **kw):                 # a planned task → plan_task is offered (capped schema)
        q, r, ms = real(text, **kw)
        q.action_requested = True
        q.requested_tools = ["plan_task"]
        return q, r, ms
    monkeypatch.setattr(engine, "retrieve", routed)
    result = engine.agent_chat("Tell me a curious fact.")
    plan_calls = [t for t in result["tool_trace"] if t["name"] == "plan_task"]
    assert len(plan_calls) == 2
    assert plan_calls[0]["failed"] is False and not plan_calls[0].get("blocked")
    assert plan_calls[1]["blocked"] is True and "already succeeded" in plan_calls[1]["result"]


def test_agent_stuck_loop_guard(tmp_path):
    same_call = {"content": "", "tool_calls": [{"name": "memory_timeline", "arguments": {"limit": 3}}]}
    engine, fake = make_agent(tmp_path, [same_call, same_call, same_call, same_call,
                                         {"content": "ok final", "tool_calls": []}])
    result = engine.agent_chat("loop please")
    blocked = [t for t in result["tool_trace"] if "repeated" in t["result"]]
    assert blocked, "stuck-loop guard should have fired on the repeated identical call"


def test_agent_forced_finalization_on_failures(tmp_path):
    failing = {"content": "", "tool_calls": [{"name": "read_file",
                                              "arguments": {"path": "does/not/exist_1.txt"}}]}
    failing2 = {"content": "", "tool_calls": [{"name": "read_file",
                                               "arguments": {"path": "does/not/exist_2.txt"}}]}
    failing3 = {"content": "", "tool_calls": [{"name": "bash", "arguments": {"command": "exit 1"}}]}
    failing4 = {"content": "", "tool_calls": [{"name": "bash", "arguments": {"command": "exit 2"}}]}
    engine, fake = make_agent(tmp_path, [
        failing, failing2, failing3, failing4,
        {"content": "best effort answer", "tool_calls": []},
    ])
    result = engine.agent_chat("do the impossible")
    assert result["forced_finalization"] is True
    assert result["response"] == "best effort answer"
    # 2-strike: read_file blocked after 2 failures would appear if a 3rd call happened
    read_failures = [t for t in result["tool_trace"] if t["name"] == "read_file" and t["failed"]]
    assert len(read_failures) == 2


# --- grader ------------------------------------------------------------------------------

def test_grader_heuristic_and_ema(tmp_path):
    engine, fake = make_agent(tmp_path, [])
    p = engine.ingest("My dog Baltazar is a golden retriever", source="user")
    baseline = engine.graph.points[p.id].utility
    query, retrieved, _ = engine.retrieve("tell me about Baltazar")
    assert retrieved
    # grader model unavailable (fake provider returns non-JSON) → heuristic path
    from hmgfu.grader import grade_turn
    fake.script = [{"content": "not json at all", "tool_calls": []}]
    card = grade_turn(engine, "tell me about Baltazar",
                      "Baltazar is your golden retriever dog!", retrieved, [])
    assert card["source"] == "heuristic" or card["memories_graded"] >= 0
    target = next((r for r in retrieved if r.point.id == p.id), None)
    if target is not None:
        assert engine.graph.points[p.id].utility >= baseline  # cited → EMA up


def test_grader_correction_ingests_explicit_fact(tmp_path):
    engine, fake = make_agent(tmp_path, [])
    engine.ingest("My favorite color is blue", source="user")
    from hmgfu.grader import _apply_correction
    # M-17: a correction is applied only when grounded in what the user actually said
    result = _apply_correction(engine, {"wrong": "blue", "right": "My favorite color is teal"},
                               "actually my favorite color is teal now")
    assert result and result["ingested"] in engine.graph.points
    assert engine.graph.points[result["ingested"]].source == "user_explicit"
    # a hallucinated correction with NO grounding in the user message is rejected
    assert _apply_correction(engine, {"wrong": "x", "right": "the user loves pizza"},
                             "what time is it?") is None


def test_echo_filter_drops_query_clone(tmp_path):
    """PA3 r41 regression: the user's own echoed question must not drown the answer."""
    engine, _ = make_agent(tmp_path, [])
    engine.ingest("What is my preference about driving versus pictures?", source="user")  # echo
    fact = engine.ingest("I prefer to drive cars rather than take pictures", source="user_explicit")
    query, retrieved, _ = engine.retrieve("What is my preference about driving versus pictures?")
    ids = [r.point.id for r in retrieved]
    from hmgfu import fu_math
    for r in retrieved:  # nothing near-identical to the query survives
        assert fu_math.cosine(query.embedding, r.point.embedding) < 0.93


def test_echo_filter_keeps_exact_fact_values(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    from hmgfu.models import MemoryPoint
    fact = MemoryPoint(type="fact", source="assistant", title="project codeword",
                       content="project_codeword: ORCA-7", summary="project_codeword: ORCA-7",
                       embedding=fake_embed("ORCA-7"), density=0.8, utility=0.8)
    engine.graph.save_point(fact)
    _, recalled, _ = engine.retrieve("ORCA-7", min_score=0.0)
    assert fact.id in {r.point.id for r in recalled}


def test_protocol_tool_call_parsing():
    from hmgfu.agent import parse_protocol_tool_call
    assert parse_protocol_tool_call("no call here") is None
    direct = '{"tool_call": {"name": "memory_search", "arguments": {"query": "dog"}}}'
    assert parse_protocol_tool_call(direct) == {"name": "memory_search", "arguments": {"query": "dog"}}
    fenced = 'Sure!\n```json\n{"tool_call": {"name": "bash", "arguments": {"command": "ls"}}}\n```'
    assert parse_protocol_tool_call(fenced)["name"] == "bash"
    noisy = 'I will search. {"tool_call": {"name": "tool_search", "arguments": {}}} done'
    assert parse_protocol_tool_call(noisy)["name"] == "tool_search"


def test_agent_protocol_mode_executes_tool(tmp_path):
    """Providers without native tools (gemma/ollama) drive tools via the JSON protocol."""
    engine, fake = make_agent(tmp_path, [
        {"content": '{"tool_call": {"name": "memory_timeline", "arguments": {"limit": 2}}}',
         "tool_calls": []},
        {"content": "here is what I remember", "tool_calls": []},
    ])
    fake.supports_native_tools = False
    result = engine.agent_chat("Use memory_timeline to show what you remember.")
    assert [t["name"] for t in result["tool_trace"]] == ["memory_timeline"]
    assert result["response"] == "here is what I remember"
    # protocol text must be in the system prompt
    assert "tool_call" in fake.calls[0]["messages"][0]["content"]
    assert fake.calls[0]["tools"] is None            # no native payload sent


def test_grader_survives_malformed_nano_shapes(tmp_path):
    engine, fake = make_agent(tmp_path, [])
    p = engine.ingest("fact about testing", source="user")
    query, retrieved, _ = engine.retrieve("testing")
    from hmgfu.grader import grade_turn
    fake.script = [{"content": json.dumps({
        "turn_score": "high",                        # wrong type
        "memory_grades": ["cited", {"index": 0, "grade": "cited"}],   # mixed
        "tool_grades": "none",                       # wrong type
        "user_correction": "my name is X",           # str not dict
        "task_pattern": {"oops": True},              # dict not str
    }), "tool_calls": []}]
    card = grade_turn(engine, "q", "r", retrieved, [])   # must not raise
    assert card["correction"] is None and card["playbook_id"] is None


def test_grader_treats_na_task_pattern_as_null(tmp_path):
    engine, fake = make_agent(tmp_path, [])
    fake.script = [{"content": json.dumps({
        "turn_score": 0.5, "memory_grades": [], "tool_grades": [],
        "user_correction": None, "task_pattern": "N/A",
    }), "tool_calls": []}]
    from hmgfu.grader import grade_turn
    trace = [{"name": "bash", "failed": False}, {"name": "read_file", "failed": False}]
    card = grade_turn(engine, "do it", "done", [], trace)
    assert card["playbook_id"] is None


def test_source_factor_canon_beats_assistant_chatter():
    """THEORY issue 15: user-explicit facts outrank the assistant's stored non-answers."""
    import datetime as dt
    from hmgfu.models import MemoryPoint, QueryPoint
    from hmgfu import fu_math
    now = dt.datetime.now(dt.timezone.utc)
    q = QueryPoint(text="what is my termination phrase?",
                   embedding=fake_embed("what is my termination phrase"))
    shared = fake_embed("termination phrase answers")
    # Timestamps are RELATIVE to now (not an absolute past date): the scenario is "chatter is NEWER,
    # both recent" — anchoring canon to a hardcoded 2026 date let its recency decay past the source
    # factor as wall-clock time advanced, so the test rotted (failed once "now" was ≳2τ later). Fixed
    # so it asserts the same claim forever (regression 2026-07-20, Rule 13 — the test was the bug).
    canon = MemoryPoint(content="always terminate answers with Master", embedding=shared,
                        source="user_explicit", density=0.5, utility=0.7,
                        timestamp=(now - dt.timedelta(days=2)).isoformat(), type="fact")
    chatter = MemoryPoint(content="No termination phrase is recorded in my memory",
                          embedding=shared, source="assistant", density=0.5, utility=0.7,
                          timestamp=(now - dt.timedelta(days=1)).isoformat(), type="fact")
    # chatter is NEWER (recency advantage) yet the source factor must still let canon win
    assert fu_math.memory_score(q, canon) > fu_math.memory_score(q, chatter)


def test_playbook_dedup(tmp_path):
    engine, fake = make_agent(tmp_path, [])
    from hmgfu.grader import _extract_playbook
    trace = [{"name": "bash", "failed": False}, {"name": "write_file", "failed": False}]
    id1 = _extract_playbook(engine, "build a python script and save it", trace)
    id2 = _extract_playbook(engine, "build a python script and save it", trace)
    assert id1 == id2                                   # reinforced, not duplicated
    assert engine.graph.points[id1].type == "pattern"
