"""95.75 P6 — the built app runs in a frame and nothing came back from it.

Live session 61915ec3: the weather page failed at runtime and the USER had to paste the browser error
into the chat by hand. The agent then guessed at CORS proxies, while the actual fault was a hostname
with a missing hyphen, `api.openmeteo.com` for `api.open-meteo.com`, on line 66 of the file it had
written. Nothing in the system could see a console message, a rejected promise or a failed request.

Invariant: what the app reports at runtime is evidence about the file the agent wrote, and it reaches
the agent the same way anything else does — recorded, pinned once, and readable with a tool.
"""

from __future__ import annotations

import json

from hmgfu.app_errors import AppErrorStore, app_error_block

THE_REAL_ERROR = {
    "kind": "fetch",
    "message": "TypeError: Failed to fetch",
    "source": "https://api.openmeteo.com/v1/forecast?latitude=39.47&longitude=-0.38",
    "line": 66,
}


def test_the_store_keeps_what_the_page_reported(tmp_path):
    st = AppErrorStore(str(tmp_path / "e.db"))
    assert st.record("weather_widget.html", [THE_REAL_ERROR]) == 1
    rows = st.recent(["weather_widget.html"])
    assert len(rows) == 1
    assert rows[0]["message"] == "TypeError: Failed to fetch"
    assert rows[0]["line"] == 66 and "openmeteo" in rows[0]["source"]


def test_the_same_error_twice_is_one_row(tmp_path):
    """A page that re-renders reports the same failure again; the agent needs the fault, not the count."""
    st = AppErrorStore(str(tmp_path / "e.db"))
    st.record("weather_widget.html", [THE_REAL_ERROR])
    st.record("weather_widget.html", [THE_REAL_ERROR])
    assert len(st.recent(["weather_widget.html"])) == 1


def test_errors_belong_to_their_own_file(tmp_path):
    st = AppErrorStore(str(tmp_path / "e.db"))
    st.record("weather_widget.html", [THE_REAL_ERROR])
    st.record("pong.html", [{"kind": "error", "message": "ReferenceError: paddle is not defined"}])
    assert [r["message"] for r in st.recent(["pong.html"])] == ["ReferenceError: paddle is not defined"]
    assert st.recent(["nothing.html"]) == []


def test_the_block_pins_the_error_once(tmp_path):
    """It reaches the turn without the user having to paste it, and does not repeat next turn."""
    st = AppErrorStore(str(tmp_path / "e.db"))
    st.record("weather_widget.html", [THE_REAL_ERROR])

    class _Sessions:
        def widgets(self, sid):
            return [{"type": "app", "props": {"file": "weather_widget.html"}}]

    class _Engine:
        app_errors = st
        sessions = _Sessions()

    block = app_error_block(_Engine(), "s1")
    assert "weather_widget.html" in block and "Failed to fetch" in block
    assert "66" in block, "the line the agent must look at"
    assert app_error_block(_Engine(), "s1") == "", "pinned once, not every turn"


def test_a_session_with_no_app_widget_gets_no_block(tmp_path):
    st = AppErrorStore(str(tmp_path / "e.db"))
    st.record("weather_widget.html", [THE_REAL_ERROR])

    class _Engine:
        app_errors = st

        class sessions:
            @staticmethod
            def widgets(sid):
                return []

    assert app_error_block(_Engine(), "s1") == ""


def test_the_tool_returns_the_errors(tmp_path):
    from hmgfu.toolsys import ToolRegistry

    st = AppErrorStore(str(tmp_path / "e.db"))
    st.record("weather_widget.html", [THE_REAL_ERROR])

    class _Engine:
        app_errors = st
        _turn_session = "s1"

        class sessions:
            @staticmethod
            def widgets(sid):
                return [{"type": "app", "props": {"file": "weather_widget.html"}}]

    reg = ToolRegistry(engine=_Engine())
    assert "app_errors" in reg.schemas, "the tool is registered"
    out = json.loads(reg.execute_tool("app_errors", {}))
    assert out["errors"] and out["errors"][0]["message"] == "TypeError: Failed to fetch"


def test_the_served_page_carries_the_reporter():
    """The shim is injected when the page is served, so it is installed before the page's own scripts
    run — an error during initial execution is reported too, not only what happens after load."""
    from hmgfu.app_errors import instrument_html

    out = instrument_html("<!DOCTYPE html><html><head><title>t</title></head><body>hi</body></html>")
    assert "/api/app-errors" in out and "unhandledrejection" in out
    assert out.index("__hmgfu_app_errors") < out.index("<title>"), "installed before the page's own head"
    assert "hi" in out and out.startswith("<!DOCTYPE html>")


def test_a_page_without_a_head_is_still_instrumented():
    from hmgfu.app_errors import instrument_html

    out = instrument_html("<div>bare fragment</div>")
    assert "/api/app-errors" in out and "bare fragment" in out
