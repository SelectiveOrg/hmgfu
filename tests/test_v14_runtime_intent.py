from datetime import datetime, timezone

from hmgfu.models import QueryPoint
from hmgfu.runtime_context import RuntimeContext
from hmgfu.sensitizer import _sanitise
from hmgfu.toolsys import retrieve_tools_for_turn
from tests.conftest import fake_embed
from tests.test_v2_agent import make_agent


def test_runtime_context_is_exact_dynamic_and_machine_readable():
    fixed = datetime(2026, 7, 5, 10, 11, 12, tzinfo=timezone.utc)
    ctx = RuntimeContext.capture(fixed)
    assert ctx.now_utc == "2026-07-05T10:11:12+00:00"
    assert ctx.local_date == "2026-07-05"
    assert '"unix_seconds":' in ctx.prompt_block()
    assert "training-time dates" in ctx.prompt_block()


def test_dynamic_query_signal_selects_catalog_tool_without_phrase_policy(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    q = QueryPoint(
        text="Execute isto agora", embedding=fake_embed("Execute isto agora"),
        intent="task", conversation_act="instruction", action_requested=True,
        requested_tools=["bash"],
    )
    names = [s["name"] for s in retrieve_tools_for_turn(engine.tools, engine, q, max_tools=4)]
    assert names[0] == "bash"


def test_semantic_instruction_recovers_action_when_route_omits_tool(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    q = QueryPoint(
        text="run shell command echo hi", embedding=fake_embed("run shell command echo hi"),
        intent="task", conversation_act="instruction", action_requested=False,
    )
    names = [s["name"] for s in retrieve_tools_for_turn(engine.tools, engine, q, max_tools=4)]
    assert names[0] == "bash"


def test_schema_default_preexecutes_safe_named_hierarchy_tool(tmp_path):
    engine, _ = make_agent(tmp_path, [{"content": "overview ready", "tool_calls": []}])
    result = engine.agent_chat("Use memory_zoom to inspect the memory overview.")
    assert result["tool_trace"][0]["name"] == "memory_zoom"
    assert result["tool_trace"][0]["arguments"] == {"scope": "overview"}


def test_runtime_sufficient_route_rejects_redundant_live_web_tool():
    routed = _sanitise({
        "action_requested": True,
        "requested_tools": ["brave_web_search"],
        "runtime_context_keys": ["now_local", "utc_offset"],
        "runtime_context_sufficient": True,
    }, {"brave_web_search"})
    assert routed["runtime_context_keys"] == ["now_local", "utc_offset"]
    assert routed["runtime_context_sufficient"] is True
    assert routed["requested_tools"] == []
    assert routed["action_requested"] is False


def test_multilingual_directive_signal_is_applied_without_text_regex(tmp_path):
    engine, _ = make_agent(tmp_path, [{"content": "Tudo bem.", "tool_calls": []}])
    engine.sensitizer.extract = lambda text, runtime_context=None, route=False: {
        "title": "directive", "summary": text, "type": "message", "keywords": [],
        "entities": [], "topics": [], "emotional_valence": 0.0,
        "emotional_intensity": 0.0, "importance": 0.5, "confidence": 0.9,
        "novelty": 0.5, "utility": 0.5, "intent": "task", "extractor": "nano",
        "conversation_act": "instruction", "action_requested": False,
        "requested_tools": [], "freshness": "none", "needs_memory": False,
        "directive": {"kind": "conversation_opener", "value": "short_joke",
                      "instruction": "Comece a primeira resposta com uma piada curta.",
                      "fallback_text": "Por que o nó atravessou a grade? Para criar uma conexão!"},
    }
    result = engine.agent_chat(
        "De agora em diante, comece cada conversa com uma piada curta.", explicit=True
    )
    assert result["response"].startswith("Por que o nó atravessou")
