"""Phase 53 — conversation_closer directive (joke at the END), fixing the instruction-leak bug.

Before: only output_prefix/suffix/conversation_opener existed, so "tell a joke at the end of every
response" was stored as output_suffix with value=the literal instruction, and enforce() appended
"Tell me a joke at the end of every response." to every reply. Now it is a first-class kind that
appends a generated JOKE, never the instruction. No Ollama needed.
"""

from __future__ import annotations

import sqlite3

from hmgfu.directives import DirectiveStore, detect_output_directive


def test_detect_joke_at_end_is_closer():
    assert detect_output_directive("tell me a joke at the end of every response") == {
        "kind": "conversation_closer", "value": "a short joke"}
    # opener + literal prefix/suffix still route correctly (no regression)
    assert detect_output_directive("always start every conversation with a joke")["kind"] == "conversation_opener"
    assert detect_output_directive("begin every reply with the word hi")["kind"] == "output_prefix"


def test_enforce_appends_joke_not_instruction(tmp_path):
    ds = DirectiveStore(str(tmp_path / "d.db"))
    ds.apply("tell me a joke at the end of every response",
             detected={"kind": "conversation_closer", "value": "a short joke",
                       "fallback_text": "Why did the node retire? It lost its edge!"})
    # ACTION turn: render_block suppressed the closer, so enforce force-appends the persisted example
    out = ds.enforce("The weather in Aveiro is sunny.", force_generated=True)
    assert "Tell me a joke at the end" not in out          # the leaked instruction is gone
    assert out != "The weather in Aveiro is sunny."          # a joke WAS appended
    assert "?" in out                                       # the persisted joke's setup
    # ORDINARY turn: the in-prompt directive is trusted; enforce must NOT staple a duplicate
    assert ds.enforce("The weather in Aveiro is sunny.") == "The weather in Aveiro is sunny."


def test_enforce_does_not_double_when_example_already_present(tmp_path):
    ds = DirectiveStore(str(tmp_path / "d.db"))
    ex = "Why did the node cross the grid? To connect!"
    ds.apply("joke at the end", detected={"kind": "conversation_closer", "value": "a short joke",
                                          "fallback_text": ex})
    reply = "It is sunny.\n\n" + ex
    out = ds.enforce(reply, force_generated=True)
    assert out == reply                                     # example already at the end → no double-append


def test_migration_converts_malformed_output_suffix(tmp_path):
    db = str(tmp_path / "legacy.db")
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE directives (kind TEXT PRIMARY KEY, value TEXT, source TEXT, "
                "updated_at TEXT, instruction TEXT DEFAULT '', fallback_text TEXT DEFAULT '')")
    con.execute("INSERT INTO directives VALUES ('output_suffix', "
                "'Tell me a joke at the end of every response.', 'user', 't', 'just tell the joke', '')")
    con.commit(); con.close()
    ds = DirectiveStore(db)                                 # __init__ migrates
    kinds = [d["kind"] for d in ds.active()]
    assert kinds == ["conversation_closer"]                # not output_suffix anymore
    assert "Tell me a joke at the end" not in ds.enforce("Answer.")
