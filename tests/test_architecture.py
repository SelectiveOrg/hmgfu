"""Self-enforcing architecture rules (ROADMAP Phase 18, PA3_LESSONS refusal #2).

These tests keep the codebase modular AS IT GROWS: they fail the moment a module
balloons past the ceiling or the compat façade breaks — so the ceiling can't erode
silently the way PA3's ws_handler did (4,800 lines).
"""

import os

import pytest

HMGFU_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "hmgfu")
APP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "app")

MODULE_LINE_CEILING = 400          # PA3_LESSONS: no module grows past ~400 lines
FRONTEND_LINE_CEILING = 300        # our jsx modules are far smaller; keep them that way


def _py_files(root):
    for dirpath, _, files in os.walk(root):
        if "__pycache__" in dirpath:
            continue
        for f in files:
            if f.endswith(".py"):
                yield os.path.join(dirpath, f)


def _count_lines(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return sum(1 for _ in fh)


def test_no_python_module_exceeds_ceiling():
    offenders = {
        os.path.relpath(p, HMGFU_DIR): _count_lines(p)
        for p in _py_files(HMGFU_DIR)
        if _count_lines(p) > MODULE_LINE_CEILING
    }
    assert not offenders, (
        f"modules over {MODULE_LINE_CEILING} lines: {offenders} — split them "
        f"(see ROADMAP Phase 18 / docs/PA3_LESSONS.md refusal #2)"
    )


def test_no_frontend_module_exceeds_ceiling():
    offenders = {}
    if os.path.isdir(APP_DIR):
        for f in os.listdir(APP_DIR):
            path = os.path.join(APP_DIR, f)
            if os.path.isfile(path) and _count_lines(path) > FRONTEND_LINE_CEILING:
                offenders[f] = _count_lines(path)
    assert not offenders, f"frontend modules over {FRONTEND_LINE_CEILING} lines: {offenders}"


def test_toolsys_facade_reexports():
    """Existing import contracts must keep working after the Phase 18 split (Rule 11)."""
    from hmgfu.toolsys import (BUILTIN_TOOLS, ToolRegistry, classify_tool_result,  # noqa: F401
                               read_file, retrieve_tools_for_turn, run_bash,
                               sync_tool_points, tool_signature, write_file)


def test_routes_registered_and_app_importable():
    """Every router module is wired; the app assembles without a running engine."""
    from hmgfu.api import app
    from hmgfu.routes import ALL_ROUTERS
    assert len(ALL_ROUTERS) == 4
    paths = set(app.openapi()["paths"].keys())   # forces lazy router resolution
    for expected in ("/", "/debug", "/api/health", "/api/chat", "/api/agent/chat",
                     "/api/memory/search", "/api/memory/timeline", "/api/graph/viz",
                     "/api/tools", "/api/settings", "/api/sessions", "/api/system/status"):
        assert expected in paths, f"route {expected} missing after split"
    # websocket routes don't appear in OpenAPI — assert on the owning router
    from hmgfu.routes import agent_ws
    assert any(getattr(r, "path", None) == "/ws" for r in agent_ws.router.routes)


def test_runtime_guard():
    """get_engine before lifespan must fail loudly, not return None."""
    import hmgfu.runtime as runtime
    saved = runtime._engine
    runtime._engine = None
    try:
        with pytest.raises(RuntimeError):
            runtime.get_engine()
    finally:
        runtime._engine = saved
