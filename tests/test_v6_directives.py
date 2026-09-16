"""First-class directives: detection, keyed supersession, injection, enforcement (bench B2)."""

from hmgfu.directives import DirectiveStore, detect_output_directive
from tests.test_v2_agent import make_agent


def test_detect_suffix_prefix_and_stop():
    assert detect_output_directive("always end every reply with the word Capitao") == \
        {"kind": "output_suffix", "value": "Capitao"}
    assert detect_output_directive("begin each response with Ahoy") == \
        {"kind": "output_prefix", "value": "Ahoy"}
    # stop + replacement → switch value
    d = detect_output_directive("stop ending replies with Capitao, use Chefe instead")
    assert d == {"kind": "output_suffix", "value": "Chefe"}
    # pure stop → clear
    assert detect_output_directive("stop ending your replies with Capitao") == \
        {"kind": "output_suffix", "clear": True}
    # not a directive
    assert detect_output_directive("what is the weather today?") is None
    # stopword guard: "end with the word" must not capture "word"
    assert detect_output_directive("end with the word Boss")["value"] == "Boss"
    # opener/closer `value` is now a readable CONTENT SPEC, not the bare 'short_joke' sentinel
    assert detect_output_directive(
        "From now on always tell me a joke at the start of all conversations"
    ) == {"kind": "conversation_opener", "value": "a short joke"}
    assert detect_output_directive(
        "From now on, always begin the first reply of every new conversation with a short joke."
    ) == {"kind": "conversation_opener", "value": "a short joke"}
    # unambiguous cease-cue clears the dynamic directive (Phase 55 lifecycle: CLEAR)
    assert detect_output_directive("stop telling jokes at the end of your replies") == {
        "kind": "conversation_closer", "clear": True}
    assert detect_output_directive("no longer start conversations with a joke") == {
        "kind": "conversation_opener", "clear": True}


def test_keyed_supersession(tmp_path):
    s = DirectiveStore(str(tmp_path / "d.db"))
    s.apply("always end replies with Capitao")
    assert s.active()[0]["value"] == "Capitao"
    # newer directive of the SAME kind deterministically replaces it (no fuzzy scoring)
    s.apply("from now on end every reply with Chefe instead")
    active = s.active()
    assert len(active) == 1 and active[0]["value"] == "Chefe"
    # survives a "restart" (new store over same db)
    s2 = DirectiveStore(str(tmp_path / "d.db"))
    assert s2.active()[0]["value"] == "Chefe"
    # clear
    s2.apply("stop ending replies with Chefe")
    assert s2.active() == []


def test_render_block_and_enforce(tmp_path):
    s = DirectiveStore(str(tmp_path / "d.db"))
    assert s.render_block() == ""                        # nothing yet
    s.apply("end every reply with Capitao")
    block = s.render_block()
    assert "MANDATORY" in block and "Capitao" in block
    # enforcement backstop: reply missing the suffix gets it appended
    assert s.enforce("The answer is 4.").rstrip().endswith("Capitao")
    # already-compliant reply is left effectively as-is (no double suffix)
    fixed = s.enforce("All good. Capitao")
    assert fixed.lower().count("capitao") == 1
    # dynamic opener: render injects the CONTENT SPEC when first_turn; enforce appends the PERSISTED
    # example (generated once at directive time) on the first reply of a conversation.
    s.apply("always tell me a joke at the start of all conversations",
            detected={"kind": "conversation_opener", "value": "a short joke",
                      "fallback_text": "Why did the byte cross the bus? Because reasons!"})
    assert "short joke" in s.render_block(first_turn=True).lower()
    assert "short joke" not in s.render_block(first_turn=False).lower()   # opener out on later turns
    opened = s.enforce("Hello there.", first_turn=True)
    assert "why did" in opened.lower() and "because" in opened.lower()    # persisted example prepended
    later = s.enforce("Hello there.", first_turn=False)                   # opener only on turn 1
    assert "why did" not in later.lower() and later.rstrip().endswith("Capitao")


def test_agent_applies_and_enforces_directive(tmp_path):
    engine, fake = make_agent(tmp_path, [{"content": "Two plus two is 4.", "tool_calls": []}])
    # teach directive in one turn (fake model reply doesn't include the suffix)
    engine.agent_chat("always end every reply with the word Capitao", explicit=True)
    fake.script = [{"content": "It is blue.", "tool_calls": []}]
    result = engine.agent_chat("name a color")
    assert result["response"].rstrip().endswith("Capitao")     # enforced deterministically
    # newer directive supersedes
    engine.agent_chat("stop using Capitao, end replies with Chefe instead", explicit=True)
    fake.script = [{"content": "It is red.", "tool_calls": []}]
    result = engine.agent_chat("name another color")
    assert result["response"].rstrip().endswith("Chefe")
    assert "capitao" not in result["response"].lower()
