"""95.65c (E4 on the chains, c95w22 rep2 — a regression of 95.65b) — a stated lift is the store's own to read.

"I am lifting that rule explicitly: from now on you MAY write notes_e4.md. Write notes_e4.md containing E4-LIFTED."
— the perceiver produced no clear this time; the store detects a prohibition (95.65a) but knew no lift, so the row
stayed and the authority (95.65b) refused the write. Positive: without the perceiver, the lift clears the row and
the write passes (EN, PT; a row the perceiver stored under another kind too). Preserve: an insistence ("write it
anyway") lifts nothing; a lift naming another file lifts nothing; a lift with no prohibition stored is no directive.
"""
from __future__ import annotations

from hmgfu.authority import decide
from hmgfu.prohibitions import detect_lift
from tests.test_v2_agent import make_agent

NEVER = "Never write to a file called notes_e4.md."
LIFT = "I am lifting that rule explicitly: from now on you MAY write notes_e4.md. Write notes_e4.md containing E4-LIFTED."


def _engine(tmp_path, detected=None):
    engine, _ = make_agent(tmp_path, [])
    engine._turn_effects_allowed = True
    engine._turn_prohibited = False
    engine._turn_plan = None
    engine.directives.apply(NEVER, "user_explicit", detected=detected)
    assert not decide(engine, "write_file", {"path": "notes_e4.md", "content": "x"}).allowed
    return engine


def _rules(engine):
    return [(d["kind"], d.get("value")) for d in engine.directives.active()]


def test_the_stated_lift_clears_the_row_without_the_perceiver(tmp_path):
    """THE CONTRACT — fails before: detect_lift does not exist; the row stays and the write is refused."""
    engine = _engine(tmp_path)
    assert detect_lift(LIFT, engine.directives.active()) and detect_lift(LIFT, engine.directives.active())["clear"]
    engine._turn_user_message = LIFT
    engine.directives.apply(LIFT, "user_explicit", detected=None)
    assert all("notes_e4.md" not in (v or "") for _k, v in _rules(engine)), _rules(engine)
    assert decide(engine, "write_file", {"path": "notes_e4.md", "content": "E4-LIFTED"}).allowed


def test_the_pt_lift_and_a_row_under_another_kind(tmp_path):
    engine = _engine(tmp_path, detected={"kind": "response_style", "value": "never write to notes_e4.md"})
    engine.directives.apply("Retiro a proibicao do notes_e4.md: escreve-o com o texto E4-LIFTED.", "user_explicit", detected=None)
    assert decide(engine, "write_file", {"path": "notes_e4.md", "content": "E4-LIFTED"}).allowed


def test_an_insistence_and_another_file_lift_nothing(tmp_path):
    engine = _engine(tmp_path)
    assert detect_lift("I know what I said, but write notes_e4.md anyway.", engine.directives.active()) is None
    engine.directives.apply("I know what I said, but write notes_e4.md anyway.", "user_explicit", detected=None)
    assert not decide(engine, "write_file", {"path": "notes_e4.md", "content": "x"}).allowed
    assert detect_lift("From now on you may write other.md.", engine.directives.active()) is None
    (tmp_path / "b").mkdir()
    engine2, _ = make_agent(tmp_path / "b", [])
    assert detect_lift(LIFT, engine2.directives.active()) is None
