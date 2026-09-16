"""95.13 (X6 rep1): shell output is bytes; the bash tool renders it as text and never fails on a byte.

Reproduced on the run's own command (`curl -s "http://wttr.in/Valencia?1"`): subprocess.run(text=True)
decoded with the console codepage (cp1252), the reader thread raised UnicodeDecodeError, proc.stdout
was None and run_bash died on the slice -- "TypeError: 'NoneType' object is not subscriptable" on both
approved turns of X6 rep1. Positive: a byte outside the codepage; negative: plain ASCII unchanged;
variant: real UTF-8 decoded; preserve: exit code and stderr still reported.
"""
import shutil

import pytest

from hmgfu.tool_builtins import run_bash

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="needs a bash on PATH")


def test_a_byte_outside_the_console_codepage_does_not_kill_the_tool():
    out = run_bash(r"printf 'a\x90b'")
    assert "error" not in out, out
    assert out["exit_code"] == 0
    assert out["stdout"].startswith("a") and out["stdout"].endswith("b")


def test_plain_ascii_output_is_unchanged():
    out = run_bash("printf 'hello'")
    assert out["stdout"] == "hello" and out["exit_code"] == 0


def test_real_utf8_output_is_decoded_as_text():
    out = run_bash("printf 'Valencia \\xe2\\x98\\x80'")
    assert out["stdout"] == "Valencia ☀", out


def test_exit_code_and_stderr_are_still_reported():
    out = run_bash("printf 'x\\x90' >&2; exit 3")
    assert out["exit_code"] == 3 and out["stderr"].startswith("x")
