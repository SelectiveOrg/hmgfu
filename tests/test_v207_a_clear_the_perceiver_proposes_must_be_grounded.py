"""95.26 (S3) — a clear the perceiver proposes must be grounded in the message.

"Do not store anything from this session. What is my cat called?" — the nano proposed
{kind: response_style, clear: true}; `directive_candidate_supported` accepted it unconditionally and the
pre-existing style directive was deleted (an undue write, replies went terse). Positive: that message
clears nothing. Variant: a message that states the stop ("Stop the long paragraphs.") or names the
value's words ("no more background in your answers") clears. Preserve: a regex-derived stop clause
("stop starting your replies with a joke") clears as before; a set stays a set.
"""
from __future__ import annotations

from hmgfu.directives import DirectiveStore

S3 = "Do not store anything from this session. What is my cat called?"


def _store(tmp_path):
    st = DirectiveStore(str(tmp_path / "d.db"))
    st.apply("Answer in long paragraphs with full background.", "user_explicit",
             detected={"kind": "response_style", "value": "long paragraphs with full background"})
    assert [d["kind"] for d in st.active()] == ["response_style"]
    return st


def test_a_memory_instruction_clears_no_style(tmp_path):
    """THE CONTRACT — fails before: the perceiver's clear deletes the style row."""
    st = _store(tmp_path)
    out = st.apply(S3, "user_explicit", detected={"kind": "response_style", "clear": True})
    assert out is None, out
    assert [d["kind"] for d in st.active()] == ["response_style"]


def test_a_stated_stop_clears(tmp_path):
    st = _store(tmp_path)
    out = st.apply("Stop the long paragraphs, please.", "user_explicit", detected={"kind": "response_style", "clear": True})
    assert out and out.get("cleared") and st.active() == []


def test_naming_the_value_clears(tmp_path):
    st = _store(tmp_path)
    out = st.apply("No more background in your answers from now on.", "user_explicit", detected={"kind": "response_style", "clear": True})
    assert out and out.get("cleared")


def test_a_regex_derived_stop_is_unchanged(tmp_path):
    st = DirectiveStore(str(tmp_path / "e.db"))
    st.apply("Start every reply with a joke.", "user_explicit")
    assert st.active()
    out = st.apply("Stop starting your replies with a joke.", "user_explicit")
    assert out and out.get("cleared"), out
