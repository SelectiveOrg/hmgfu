"""Phase 56 cross-model finding — recover a tool call emitted as TEXT, not a native call.

ornith:9b (Qwen3.5 agentic) sometimes narrates an action as an XML tag `<bash>ls -la</bash>`
instead of emitting a native Ollama function-call, so the action was silently dropped (bench
L8/L9). General fix: parse the JSON-protocol form AND the `<offered_tool>inner</offered_tool>`
form, in BOTH native and non-native mode. Deterministic — no Ollama.
"""

from __future__ import annotations

from hmgfu.tool_protocol import parse_fenced_tool_call, parse_hermes_tool_call, parse_text_tool_call
from tests.test_v2_agent import make_agent

BASH = {"name": "bash", "description": "run a shell command",
        "parameters": {"type": "object", "properties": {"command": {"type": "string"}},
                       "required": ["command"]}}
SEARCH = {"name": "memory_search", "description": "search memory",
          "parameters": {"type": "object", "properties": {"query": {"type": "string"},
                                                          "limit": {"type": "integer"}},
                         "required": ["query"]}}
WIDGET = {"name": "create_widget", "description": "make a widget",
          "parameters": {"type": "object", "properties": {"type": {"type": "string"},
                                                          "title": {"type": "string"}},
                         "required": ["type", "title"]}}


def test_xml_tag_maps_to_single_string_arg():
    assert parse_text_tool_call("<bash>ls -la</bash>", [BASH]) == \
        {"name": "bash", "arguments": {"command": "ls -la"}}
    assert parse_text_tool_call("Let me look.\n\n<bash>echo HI</bash>\nthanks", [BASH]) == \
        {"name": "bash", "arguments": {"command": "echo HI"}}
    assert parse_text_tool_call("<memory_search>ORCA-7</memory_search>", [SEARCH]) == \
        {"name": "memory_search", "arguments": {"query": "ORCA-7"}}


def test_hermes_qwen_tool_call_envelope():
    # Qwen name-first (ornith's exact shape) — full args, so a MULTI-ARG tool works here
    assert parse_hermes_tool_call(
        '<tool_call>{"name": "create_widget", "arguments": {"type": "note", "title": "T"}}</tool_call>',
        [WIDGET]) == {"name": "create_widget", "arguments": {"type": "note", "title": "T"}}
    # Hermes args-first order also parses
    assert parse_hermes_tool_call(
        '<tool_call>{"arguments": {"command": "ls -la"}, "name": "bash"}</tool_call>', [BASH]) == \
        {"name": "bash", "arguments": {"command": "ls -la"}}
    # leading <scratch_pad> reasoning is stripped; surrounding prose tolerated
    assert parse_hermes_tool_call(
        'Sure.\n<scratch_pad>let me run it</scratch_pad>\n<tool_call>{"name":"bash","arguments":{"command":"echo hi"}}</tool_call>\ndone',
        [BASH]) == {"name": "bash", "arguments": {"command": "echo hi"}}
    # OPEN/truncated tag (streaming cut) still recovers
    assert parse_hermes_tool_call('<tool_call>{"name": "bash", "arguments": {"command": "ls"}}',
                                  [BASH]) == {"name": "bash", "arguments": {"command": "ls"}}
    # arguments delivered as a JSON string
    assert parse_hermes_tool_call(
        '<tool_call>{"name": "bash", "arguments": "{\\"command\\": \\"pwd\\"}"}</tool_call>',
        [BASH]) == {"name": "bash", "arguments": {"command": "pwd"}}
    # gated: an envelope naming an UN-offered tool is rejected; prose without the tag is None
    assert parse_hermes_tool_call('<tool_call>{"name":"bash","arguments":{}}</tool_call>', [WIDGET]) is None
    assert parse_hermes_tool_call("just a normal answer, no tags", [BASH]) is None
    # and it is first in the chain used by parse_text_tool_call
    assert parse_text_tool_call('<tool_call>{"name":"bash","arguments":{"command":"x"}}</tool_call>',
                                [BASH]) == {"name": "bash", "arguments": {"command": "x"}}


def test_json_protocol_form_still_parsed():
    assert parse_text_tool_call('{"tool_call": {"name": "bash", "arguments": {"command": "x"}}}',
                                [BASH]) == {"name": "bash", "arguments": {"command": "x"}}


def test_markdown_code_fence_maps_to_tool_call():
    """ornith:9b (Qwen3.5 coder) narrates an action as a ```bash fence, not a native call (bench
    L21). Recover a shell fence → bash, and a ```json fence → its named tool."""
    # a plain shell fence → the shell tool
    assert parse_fenced_tool_call("```bash\necho hi\n```", [BASH]) == \
        {"name": "bash", "arguments": {"command": "echo hi"}}
    # ornith's EXACT bench L21 shape: opener + narration + fence
    orn = ("I told my wife she was drawing her eyebrows too high. She looked surprised.\n\n"
           "Vou executar o comando solicitado agora:\n\n```bash\necho PROATIVO\n```")
    assert parse_text_tool_call(orn, [BASH]) == {"name": "bash", "arguments": {"command": "echo PROATIVO"}}
    # ```sh / ```console with a leading `$ ` prompt also recover (prompt stripped)
    assert parse_fenced_tool_call("```sh\nls -la\n```", [BASH]) == \
        {"name": "bash", "arguments": {"command": "ls -la"}}
    assert parse_fenced_tool_call("```console\n$ pwd\n```", [BASH]) == \
        {"name": "bash", "arguments": {"command": "pwd"}}
    # a ```json fence carrying {name, arguments} → a MULTI-ARG tool (create_widget)
    assert parse_fenced_tool_call('```json\n{"name":"create_widget","arguments":{"type":"note","title":"T"}}\n```',
                                  [WIDGET]) == {"name": "create_widget", "arguments": {"type": "note", "title": "T"}}


def test_fenced_call_gated_and_no_false_positive():
    # a shell fence when bash is NOT offered → not executed (illustrative snippet in a chat reply)
    assert parse_fenced_tool_call("here's how:\n```bash\nrm -rf /\n```", [SEARCH]) is None
    assert parse_fenced_tool_call("```bash\nls\n```", None) is None       # no catalog → nothing
    # a JSON fence naming an UN-offered tool is rejected
    assert parse_fenced_tool_call('```json\n{"name":"bash","arguments":{"command":"x"}}\n```', [WIDGET]) is None
    # prose with no fence → None
    assert parse_fenced_tool_call("no code here at all", [BASH]) is None


def test_no_false_positive_on_prose_or_unoffered_or_multiarg():
    assert parse_text_tool_call("Sure, your name is Teodoro. How can I help?", [BASH]) is None
    assert parse_text_tool_call("<bash>ls</bash>", [SEARCH]) is None      # bash not offered
    assert parse_text_tool_call("<create_widget>hi</create_widget>", [WIDGET]) is None  # multi-arg → native only
    assert parse_text_tool_call("<bash>ls</bash>", None) is None         # no catalog → nothing


def test_agent_executes_texted_tool_call_in_native_mode(tmp_path, monkeypatch):
    """End-to-end: a NATIVE-mode turn whose reply carries `<bash>…</bash>` text (empty native
    tool_calls) still executes bash — the silently-dropped action is recovered."""
    engine, fake = make_agent(tmp_path, [
        {"content": "Let me check.\n\n<bash>echo HELLO</bash>", "tool_calls": []},
        {"content": "The output is HELLO.", "tool_calls": []},
    ])
    engine.settings.set("tool_points_enabled", True)
    real = engine.retrieve
    def routed(text, **kw):
        q, r, ms = real(text, **kw)
        q.action_requested = True
        q.requested_tools = ["bash"]
        return q, r, ms
    monkeypatch.setattr(engine, "retrieve", routed)
    result = engine.agent_chat("look at the workspace")
    assert "bash" in [t["name"] for t in result["tool_trace"]]        # recovered + executed


def test_agent_executes_fenced_bash_in_native_mode(tmp_path, monkeypatch):
    """End-to-end: a NATIVE-mode turn whose reply narrates a ```bash fence (empty native tool_calls)
    still executes bash — ornith's code-fence action is recovered, not dropped (bench L21)."""
    engine, fake = make_agent(tmp_path, [
        {"content": "Vou executar agora:\n\n```bash\necho PROATIVO\n```", "tool_calls": []},
        {"content": "Feito — a saída foi PROATIVO.", "tool_calls": []},
    ])
    engine.settings.set("tool_points_enabled", True)
    real = engine.retrieve
    def routed(text, **kw):
        q, r, ms = real(text, **kw)
        q.action_requested = True
        q.requested_tools = ["bash"]
        return q, r, ms
    monkeypatch.setattr(engine, "retrieve", routed)
    result = engine.agent_chat("corre um echo")
    assert "bash" in [t["name"] for t in result["tool_trace"]]        # fenced call recovered + executed
