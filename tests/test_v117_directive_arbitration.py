"""Phase 92.E2 — a router candidate does not outrank the evidence in the instruction.

Observed in five real conversations (docs/LEARNING_AUDIT_SYNTHESIS.md): the user asked for a SEARCH
POLICY -- "use memory search when you are not sure of the answer" -- and the system stored an
`output_prefix` whose literal value was the word `none`, then prepended "none " to later replies,
including an apology. The instruction text itself was still in the prompt, so this was never a case
of the instruction going missing: the representation, the execution and the verbal confirmation were
simply not the same thing.

`DirectiveStore.apply` read `detected or detect_output_directive(text) or detect_tool_rule(text)`, so
a supplied candidate SHORT-CIRCUITED both local detectors and no arbitration happened at all.

The contract here is evidence, not precedence, and it has to survive three ways at once:

  * a LITERAL format (output_prefix/output_suffix) must have its value present in the instruction --
    which is why the wrong `none` is refused while an explicitly requested `none` is kept. Banning the
    word globally would be a patch, not a fix;
  * a CONTENT SPEC (conversation_opener/closer) is a description by design ("a short joke") and is
    NOT expected to appear literally, so it keeps working;
  * the router legitimately reads formats the local regex cannot ("prefix your answers with the word
    Bom dia" -> fmt=None), so candidates are not rejected wholesale.
"""

from __future__ import annotations

import pytest

from hmgfu.directives import DirectiveStore

POLICY = "for now on always use memory search when you are not sure of the unswer"


def _store(tmp_path, name="d.db"):
    return DirectiveStore(str(tmp_path / name))


def test_a_search_policy_is_not_stored_as_a_format(tmp_path):
    """The reported defect: a format candidate wins over the policy actually stated."""
    st = _store(tmp_path)
    st.apply(POLICY, "user_explicit", detected={"kind": "output_prefix", "value": "none",
                                                "instruction": POLICY, "fallback_text": ""})
    kinds = {d["kind"]: d.get("value") for d in st.active()}
    assert "output_prefix" not in kinds, f"the policy became a format: {kinds}"
    assert kinds.get("tool_rule:memory_search") == "you are not sure of the unswer", kinds


def test_the_reply_is_not_prefixed_after_the_policy(tmp_path):
    """The visible symptom: 'none ' prepended to every reply, apologies included."""
    st = _store(tmp_path)
    st.apply(POLICY, "user_explicit", detected={"kind": "output_prefix", "value": "none",
                                                "instruction": POLICY, "fallback_text": ""})
    assert st.enforce("Understood.") == "Understood."
    assert st.enforce("I apologize; that should not appear.") == "I apologize; that should not appear."


@pytest.mark.parametrize("text,value", [
    ("always start your replies with the word none", "none"),
    ("begin every reply with none", "none"),
    ("always prefix your answers with the word Bom dia", "Bom dia"),
])
def test_a_literal_format_the_user_really_asked_for_is_kept(tmp_path, text, value):
    """Including `none`. The value is evidenced in the instruction, so it is a real format."""
    st = _store(tmp_path)
    st.apply(text, "user_explicit", detected={"kind": "output_prefix", "value": value,
                                              "instruction": text, "fallback_text": ""})
    assert {d["kind"]: d.get("value") for d in st.active()}.get("output_prefix") == value


def test_a_content_spec_does_not_need_to_appear_literally(tmp_path):
    """opener/closer values are DESCRIPTIONS by design; the literal test must not apply to them."""
    text = "always finish your replies with something funny"
    st = _store(tmp_path)
    st.apply(text, "user_explicit", detected={"kind": "conversation_closer", "value": "a short joke",
                                              "instruction": text, "fallback_text": ""})
    assert {d["kind"]: d.get("value") for d in st.active()}.get("conversation_closer") == "a short joke"


@pytest.mark.parametrize("value", ["", None, "   "])
def test_a_candidate_without_a_value_never_creates_a_format(tmp_path, value):
    st = _store(tmp_path)
    st.apply("please remember how I like answers", "user_explicit",
             detected={"kind": "output_prefix", "value": value, "instruction": "x", "fallback_text": ""})
    assert not [d for d in st.active() if d["kind"] == "output_prefix"]


def test_an_unsupported_format_candidate_writes_nothing_when_there_is_no_policy(tmp_path):
    """A wrong candidate must not invent a format out of an unrelated message."""
    st = _store(tmp_path)
    st.apply("my dog is called Green", "user_explicit",
             detected={"kind": "output_prefix", "value": "none", "instruction": "x", "fallback_text": ""})
    assert st.active() == []


def test_the_policy_is_reachable_as_a_tool_rule(tmp_path):
    """Persisting the right KIND is what makes the behaviour executable at all."""
    st = _store(tmp_path)
    st.apply(POLICY, "user_explicit", detected={"kind": "output_prefix", "value": "none",
                                                "instruction": POLICY, "fallback_text": ""})
    assert st.tool_rules_for("I am not sure of the answer", ["memory_search"]) == ["memory_search"]
