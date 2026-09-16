"""95.78 D4 — the agent explained a file that was not the widget.

Live session 523b0720: it built `weather_widget_final.html` at 15:28 and, one turn later, inspected
`maputo_weather_widget.html` from twelve days earlier, then told the user "the widget is currently a
static template showing 28°C" — a number from the wrong file. Nothing in the turn said which file the
app on the canvas is showing, so the agent guessed from the workspace listing by name.

Invariant: what the canvas is showing is state of the session, and it travels with the rest of it.
"""

from __future__ import annotations

from types import SimpleNamespace

from hmgfu.app_errors import session_app_files
from hmgfu.operational_state import state_block


def _engine(widgets):
    return SimpleNamespace(sessions=SimpleNamespace(widgets=lambda sid: widgets),
                           session_plans=None, _turn_plan=None)


def test_the_files_behind_the_canvas_apps_are_known():
    eng = _engine([{"type": "app", "props": {"file": "weather_widget_final.html"}},
                   {"type": "note", "props": {"text": "hello"}},
                   {"type": "app", "props": '{"file": "pong.html"}'}])
    assert session_app_files(eng, "s1") == ["weather_widget_final.html", "pong.html"]


def test_the_state_block_names_them():
    eng = _engine([{"type": "app", "props": {"file": "weather_widget_final.html"}}])
    block = state_block(eng, "s1")
    assert "weather_widget_final.html" in block
    assert "canvas" in block.lower()


def test_a_canvas_without_apps_says_nothing_about_files():
    eng = _engine([{"type": "note", "props": {"text": "hello"}}])
    assert ".html" not in state_block(eng, "s1")


def test_an_engine_without_a_session_store_still_renders():
    """The block is assembled on every turn, so a missing store must not break it."""
    block = state_block(SimpleNamespace(session_plans=None, _turn_plan=None), "s1")
    assert isinstance(block, str) and ".html" not in block
