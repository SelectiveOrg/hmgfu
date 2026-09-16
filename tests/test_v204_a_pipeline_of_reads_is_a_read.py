"""95.23 (E2 c95k reps 1 and 3) — a pipeline of reads is a read.

On the ask turn the model ran `grep "checksum" inventory* | head -n 1` — a read-only pipeline — and the
read-only grammar (69.1, fail-closed) refused it three ways: `|` forbidden outright, `grep` not a read
program, a quoted word not path-like. So a read became "a side effect that needs the user's
confirmation" on a question turn, the model proposed instead of answering, and E2 failed 2/3.
Positive: the run's own command is read-only; `grep -c "widget-B" inventory.txt` and `cat a | wc -l`
too. Negative (fail-closed kept): a redirection, a `;` chain, `&&`, a pipeline whose stage writes, an
unknown flag, an unclosed quote. Preserve: `ls -la`, `git status`, `echo hi` as before; `rm` never.
"""
from __future__ import annotations

import pytest

from hmgfu.authority import effect_of, shell_is_read_only


@pytest.mark.parametrize("cmd", [
    'grep "checksum" inventory* | head -n 1',
    'grep -c "widget-B" inventory.txt',
    "cat inventory.txt | wc -l",
    "grep -n checksum inventory.txt",
    "ls -la | head -n 5",
    "cat a.txt | grep 'widget-B' | wc -l",
])
def test_reads_and_pipelines_of_reads_are_read_only(cmd):
    """THE CONTRACT — fails before on the first three."""
    assert shell_is_read_only(cmd), cmd
    assert effect_of("bash", {"command": cmd}) == "read"


@pytest.mark.parametrize("cmd", [
    "cat a.txt > b.txt",
    "ls; rm -rf x",
    "grep x f && rm f",
    "grep x f | rm -rf .",
    "grep --include=*.py x .",
    'grep "unclosed inventory.txt',
    "cat a.txt | tee b.txt",
    "rm -rf .",
    "echo hi > out.txt",
])
def test_writes_and_unknown_shapes_stay_side_effects(cmd):
    assert not shell_is_read_only(cmd), cmd
    assert effect_of("bash", {"command": cmd}) == "write"


def test_the_old_grammar_is_preserved():
    assert shell_is_read_only("ls -la") and shell_is_read_only("git status --short") and shell_is_read_only("echo hi")
    assert shell_is_read_only("head -n 3 file.txt") and not shell_is_read_only("head -n file.txt")
