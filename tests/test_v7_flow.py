"""Sequential interleaved execution flow (PA3 lastBlockByTurn): thinking→tool→thinking→tool→text."""

from tests.test_v2_agent import make_agent


def _event_kinds(events):
    return [e["type"] for e in events]


def test_reasoning_emitted_as_thinking_before_tools(tmp_path):
    # round 1: reasoning + a tool; round 2: more reasoning + a tool; round 3: final answer
    engine, fake = make_agent(tmp_path, [
        {"content": "I should check the memory first.",
         "tool_calls": [{"name": "memory_timeline", "arguments": {"limit": 2}}]},
        {"content": "Now I will note it down.",
         "tool_calls": [{"name": "create_widget",
                         "arguments": {"type": "note", "title": "N", "props": {"text": "hi"}}}]},
        {"content": "All set — here is your answer.", "tool_calls": []},
    ])
    events = []
    result = engine.agent_chat("do a two-step thing", emit=lambda ev: events.append(ev))
    kinds = _event_kinds(events)
    # the model's per-round reasoning surfaces as thinking, IN SEQUENCE with the tools
    seq = [k for k in kinds if k in ("thinking", "tool_call", "text", "done")]
    assert seq == ["thinking", "tool_call", "thinking", "tool_call", "text", "done"], seq
    # final answer is clean (no reasoning leaked, no residual thinking marker)
    assert result["response"] == "All set — here is your answer."
    # reasoning persisted for restore
    hist = engine.sessions.history(result["session_id"])
    assert "check the memory first" in hist[1]["metadata"]["thinking"]


def test_thinking_tags_extracted_mid_loop(tmp_path):
    engine, fake = make_agent(tmp_path, [
        {"content": "<thinking>weigh the options</thinking>Let me search.",
         "tool_calls": [{"name": "memory_search", "arguments": {"query": "x"}}]},
        {"content": "Done.", "tool_calls": []},
    ])
    events = []
    engine.agent_chat("q", emit=lambda ev: events.append(ev))
    thinking = [e for e in events if e["type"] == "thinking"]
    assert thinking, "reasoning should surface as a thinking event"
    assert "weigh the options" in thinking[0]["text"]      # <thinking> content
    assert "Let me search" in thinking[0]["text"]          # preamble-before-tool


def test_recalling_is_status_not_thinking(tmp_path):
    engine, fake = make_agent(tmp_path, [{"content": "hi", "tool_calls": []}])
    events = []
    engine.agent_chat("hello", emit=lambda ev: events.append(ev))
    # "Recalling memories" is an ephemeral status, NOT a thinking card
    recalling = [e for e in events if e.get("text") == "Recalling memories"]
    assert recalling and recalling[0]["type"] == "status"
    # a plain-answer turn produces no thinking card at all
    assert not [e for e in events if e["type"] == "thinking"]


def test_silent_tool_round_gets_system_narration(tmp_path):
    """Doctrine: model goes straight to a tool with EMPTY content → the system narrates."""
    engine, fake = make_agent(tmp_path, [
        {"content": "", "tool_calls": [{"name": "memory_search", "arguments": {"query": "dog name"}}]},
        {"content": "Found it.", "tool_calls": []},
    ])
    events = []
    engine.agent_chat("what's my dog's name?", emit=lambda ev: events.append(ev))
    kinds = [e["type"] for e in events if e["type"] in ("thinking", "tool_call", "text")]
    assert kinds[0] == "thinking", "every tool round must OPEN with a thinking block"
    first = next(e for e in events if e["type"] == "thinking")
    assert 'Searching memory for "dog name"' in first["text"]   # derived, honest narration


def test_narration_includes_plan_step():
    from hmgfu.thinking import narrate_tool_calls
    plan = {"title": "t", "steps": [{"text": "find the data", "status": "done"},
                                    {"text": "write the report", "status": "active"}]}
    text = narrate_tool_calls([{"name": "write_file", "arguments": {"path": "report.md"}}], plan)
    assert text.startswith("Step 2/2 — write the report:")
    assert "Writing report.md" in text


def test_model_reasoning_preferred_over_narration(tmp_path):
    engine, fake = make_agent(tmp_path, [
        {"content": "I need to check the timeline first.",
         "tool_calls": [{"name": "memory_timeline", "arguments": {"limit": 2}}]},
        {"content": "Done.", "tool_calls": []},
    ])
    events = []
    engine.agent_chat("q", emit=lambda ev: events.append(ev))
    first = next(e for e in events if e["type"] == "thinking")
    assert first["text"] == "I need to check the timeline first."   # genuine, not derived


def test_no_duplicate_final_thinking(tmp_path):
    # model puts <thinking> ONLY in the final answer → exactly one thinking event, clean reply
    engine, fake = make_agent(tmp_path, [
        {"content": "<thinking>just answer</thinking>The sky is blue.", "tool_calls": []},
    ])
    events = []
    result = engine.agent_chat("color of sky?", emit=lambda ev: events.append(ev))
    thinking = [e for e in events if e["type"] == "thinking"]
    assert len(thinking) == 1 and "just answer" in thinking[0]["text"]
    assert result["response"] == "The sky is blue."         # thinking stripped from answer
