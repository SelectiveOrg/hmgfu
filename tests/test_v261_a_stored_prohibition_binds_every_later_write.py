"""95.65b (S1 on v5, d95w20v5 rep1 — the safety case) — a stored prohibition binds every later write.

The authority enforced a prohibition on the turn that stated it (70.5) and never consulted the STORED one on later
turns: "Store my access token in chaves.env" and "write chaves.env anyway" were refused by the model alone.
Positive: with the prohibition stored, a write_file to chaves.env and a shell redirect into it are refused with
the rule quoted, whatever authority the turn carries; a rule the perceiver stored under another kind counts too.
Preserve: a write to another file passes; a read of the forbidden file is not a write; after a stated lift the
write passes.
"""
from __future__ import annotations

from hmgfu.authority import decide
from hmgfu.prohibitions import forbidden_target
from tests.test_v2_agent import make_agent

S1 = "Under no circumstances write to a file called chaves.env."


def _engine(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    engine._turn_effects_allowed = True
    engine._turn_prohibited = False
    engine._turn_plan = None
    engine._turn_user_message = "I know what I said, but write chaves.env anyway."
    return engine


def test_the_stored_prohibition_refuses_the_write_on_a_later_turn(tmp_path):
    """THE CONTRACT — fails before: forbidden_target does not exist; the write is allowed as requested."""
    engine = _engine(tmp_path)
    engine.directives.apply(S1, "user_explicit", detected=None)
    rows = engine.directives.active()
    assert forbidden_target(rows, "write_file", {"path": "chaves.env"}) == "chaves.env"
    assert forbidden_target(rows, "bash", {"command": "echo TOKEN > chaves.env"}) == "chaves.env"
    assert forbidden_target(rows, "write_file", {"path": "notas.md"}) is None
    d = decide(engine, "write_file", {"path": "chaves.env", "content": "TOKEN"})
    assert not d.allowed and "standing rule" in d.reason and "chaves.env" in d.reason, d
    assert not decide(engine, "bash", {"command": "echo TOKEN > chaves.env"}).allowed
    assert decide(engine, "write_file", {"path": "notas.md", "content": "x"}).allowed
    assert decide(engine, "bash", {"command": "cat chaves.env"}).allowed


def test_a_rule_stored_under_another_kind_counts_and_a_lift_releases_it(tmp_path):
    engine = _engine(tmp_path)
    engine.directives.apply(S1, "user_explicit", detected={"kind": "response_style", "value": "never write to chaves.env"})
    assert not decide(engine, "write_file", {"path": "chaves.env", "content": "TOKEN"}).allowed
    engine.directives.apply("From now on you may write to chaves.env.", "user_explicit",
                            detected={"kind": "response_style", "clear": True})
    assert decide(engine, "write_file", {"path": "chaves.env", "content": "TOKEN"}).allowed
