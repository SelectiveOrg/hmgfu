"""Phase 73.2 — the router is its own provider role (default = the chat model) and its tool list is capped."""
from __future__ import annotations

from hmgfu.extraction_schema import _sanitise
from hmgfu.providers import ROLES
from hmgfu.turn_router import MAX_REQUESTED_TOOLS, classify_turn, router_schema
from tests.test_v2_agent import make_agent


def test_router_role_defaults_to_the_chat_model(tmp_path):
    eng, _ = make_agent(tmp_path, [{"content": "x", "tool_calls": []}])
    assert "router" in ROLES
    assert eng.settings.get("router_model") == eng.settings.get("chat_model")      # behaviour unchanged by default
    assert eng.settings.get("router_provider") == eng.settings.get("chat_provider")


def test_classify_turn_uses_the_router_role():
    seen = []
    def chat(role, messages, **kw):
        seen.append(role)
        return '{"conversation_act": "question", "action_requested": false, "requested_tools": [], "freshness": "none"}'
    out = classify_turn(chat, lambda s: __import__("json").loads(s), "what is my name?", "", "[]", "", "", router_schema(["a"]))
    assert seen == ["router"] and out["conversation_act"] == "question"


def test_requested_tools_are_capped_in_schema_and_sanitiser():
    schema = router_schema(["memory_search", "bash", "list_files", "write_file", "plan_task"])
    assert schema["properties"]["requested_tools"]["maxItems"] == MAX_REQUESTED_TOOLS
    raw = {"conversation_act": "instruction", "requested_tools": ["memory_search", "bash", "list_files", "write_file", "plan_task"]}
    out = _sanitise(raw, allowed_tools=["memory_search", "bash", "list_files", "write_file", "plan_task"])
    assert len(out["requested_tools"]) <= MAX_REQUESTED_TOOLS


def test_classify_turn_disables_native_thinking():
    """73.2: a grammar-constrained classification runs with think=False (the model default cost 6–70 s per route)."""
    seen = {}
    def chat(role, messages, **kw):
        seen.update(kw)
        return '{"conversation_act": "greeting", "action_requested": false, "requested_tools": [], "freshness": "none"}'
    classify_turn(chat, lambda s: __import__("json").loads(s), "olá", "", "[]", "", "", router_schema(["a"]))
    assert seen.get("think") is False and seen.get("json_mode") is True



def test_provider_drops_think_for_models_without_the_capability():
    from hmgfu.providers import OllamaProvider
    class FakeClient:
        base_url = "http://x"
        def capabilities(self, model):
            return ["completion", "thinking"] if model == "thinker" else ["completion"]
    prov = OllamaProvider.__new__(OllamaProvider)
    prov.client = FakeClient()
    assert prov._thinks("thinker") is True and prov._thinks("plain") is False
    assert prov._thinks("plain") is False                      # cached, no second probe needed


def test_structured_calls_pass_think_false():
    import inspect
    from hmgfu import grader, grounding, runtime_context, slots, turn_router
    for mod, needle in ((slots, "format_schema=schema, think=False"), (grader, "_CHAT_CORRECTION_SCHEMA, think=False"),
                        (turn_router, "temperature=0.5, think=False"), (grounding, "temperature=0.2, think=False")):
        assert needle in inspect.getsource(mod), mod.__name__
    assert "think=False" in inspect.getsource(runtime_context.ground_reply)
    assert inspect.getsource(grader).count("think=False") >= 2



def test_route_runs_concurrently_and_merges():
    """73.2(a″): the router future is started before the nano call and folded in afterwards."""
    import time
    from hmgfu.turn_router import merge_route, start_route
    def slow_chat(role, messages, **kw):
        time.sleep(0.2)
        return '{"conversation_act": "question", "action_requested": false, "requested_tools": ["memory_search"], "freshness": "none"}'
    t0 = time.perf_counter()
    fut = start_route(slow_chat, lambda s: __import__("json").loads(s), "what is my name?", "", "[]", "", "", router_schema(["memory_search"]))
    assert time.perf_counter() - t0 < 0.1                  # returned immediately
    raw = {"conversation_act": "statement", "requested_tools": [], "keywords": ["name"]}
    out = merge_route(raw, fut)
    assert out["conversation_act"] == "question" and out["requested_tools"] == ["memory_search"] and out["keywords"] == ["name"]


def test_worker_calls_are_attributed_to_the_turn(tmp_path):
    import contextvars
    from concurrent.futures import ThreadPoolExecutor
    from hmgfu.turn_timing import TurnTimer, instrument
    eng, _ = make_agent(tmp_path, [{"content": "x", "tool_calls": []}])
    class _Resp:
        def json(self): return {"eval_count": 1}
    class _Inner:
        def post(self, url, **kw): return _Resp()
    class Holder: pass
    h = Holder(); h._client = _Inner(); instrument(h)
    timer = TurnTimer(eng)
    with ThreadPoolExecutor(max_workers=1) as ex:
        ex.submit(contextvars.copy_context().run, h._client.post, "http://x/api/embed", json={"model": "bge-m3"}).result()
    s = timer.finish()
    assert s["model_calls"] == 1 and s["background_calls"] == 0



def test_router_classification_survives_a_failed_nano_extraction():
    """73.4: nano unparseable/timed out → heuristic fallback, but the router's route is still folded in."""
    from hmgfu.sensitizer import Sensitizer
    s = Sensitizer(client=object(), enabled=True)
    def role_chat(role, messages, **kw):
        if role == "nano":
            raise RuntimeError("nano timed out")
        return {"content": '{"conversation_act": "question", "action_requested": true, "requested_tools": ["memory_search"], "freshness": "none"}'}
    s.bind_role_chat(role_chat)
    s.bind_action_catalog(type("Cat", (), {"schemas": {"memory_search": {"description": "search"}}})())
    out = s.extract("what is my name?", route=True)
    assert out["conversation_act"] == "question" and out["requested_tools"] == ["memory_search"]
    assert out["extractor"] == "fallback+router" and out["keywords"]



def test_new_standing_directive_requires_standing_language():
    """73.4: the thinking-free router invented an output_suffix on 'share with me the link…'; a NEW standing rule needs
    standing-rule language in the user's words. Changes to an active kind and clears keep the old rules."""
    from hmgfu.directives import is_blocked_directive_change
    hallucinated = {"kind": "output_suffix", "value": "For more detailed information, visit [XYZ Car Tracking Services]"}
    assert is_blocked_directive_change(hallucinated, [], False, "instruction", text="share with me the link to track my car location") is True
    genuine = {"kind": "conversation_closer", "value": "a short joke"}
    assert is_blocked_directive_change(genuine, [], False, "instruction", text="from now on end every reply with a joke") is False
    assert is_blocked_directive_change(genuine, [], False, "instruction", text="a partir de agora termina sempre com uma piada") is False
    assert is_blocked_directive_change({"kind": "conversation_closer", "clear": True}, [], False, "instruction", text="stop that") is False
    assert is_blocked_directive_change(hallucinated, [], False, "instruction") is False        # no text → old behaviour
    tool_rule = {"kind": "tool_rule:brave_search", "value": "getting weather"}
    assert is_blocked_directive_change(tool_rule, [], False, "instruction", text="use brave search for weather") is False
