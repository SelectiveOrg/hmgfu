"""95.9b (E7 c95c rep1) — the command under another argument name is still the command.

95.9 refused the echoed request twice — correctly — and the retry guard then blocked `bash` for the
turn. But the calls carried the REAL command under `code` ({"code": "grep -r widget-B . | wc -l",
"command": "<the user's sentence>"}): the model drifted on the argument name, the drift 71.7 already
folds for the file tools. When `command` echoes the request and another string argument holds a
different text, that text is the command. Positive: the `code` command runs. Negative: `code` echoing
the request too is still refused. Preserve: the bare echo is still refused; a real `command` runs.
"""
from __future__ import annotations

import json
import shutil

import pytest

from tests.test_v2_agent import make_agent

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="needs a bash on PATH")

SENTENCE = "Show me a metric widget with the number of widget-B in the workspace inventory."


def _engine(tmp_path):
    eng = make_agent(tmp_path, [])[0]
    eng._turn_user_message = SENTENCE
    return eng


def test_the_command_under_code_runs(tmp_path):
    """THE CONTRACT — fails before: refused as the echoed request, the real command never runs."""
    out = json.loads(_engine(tmp_path).tools.execute_tool("bash", {"command": SENTENCE, "code": "printf v192-ok"}))
    assert out.get("stdout") == "v192-ok", out


def test_code_that_also_echoes_the_request_is_refused(tmp_path):
    out = json.loads(_engine(tmp_path).tools.execute_tool("bash", {"command": SENTENCE, "code": SENTENCE}))
    assert "error" in out and "request" in out["error"], out


def test_the_bare_echo_is_still_refused(tmp_path):
    out = json.loads(_engine(tmp_path).tools.execute_tool("bash", {"command": SENTENCE}))
    assert "error" in out and "request" in out["error"], out


def test_a_real_command_still_runs(tmp_path):
    out = json.loads(_engine(tmp_path).tools.execute_tool("bash", {"command": "printf v192-real"}))
    assert out.get("stdout") == "v192-real", out
