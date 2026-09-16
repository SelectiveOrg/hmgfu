"""95.57 (X4 on v5, d95w16v5 rep1) — an input redirection to a path is a read.

"Count the lines in contagem.txt; there is no counting tool, so find another way." — the model called
`wc -l < contagem.txt`; `<` was forbidden outright, so a read was blocked as a side effect and the
turn proposed instead of counting. Positive: `< path` after a read program is the path as an
argument. Preserve: `>` and `>>` write; `<<` (a heredoc) and `<(` (a process substitution) stay out;
a write program with an input redirection is still not a read.
"""
from __future__ import annotations

from hmgfu.authority import effect_of, shell_is_read_only


def test_an_input_redirection_to_a_path_is_a_read():
    """THE CONTRACT — fails before: `wc -l < contagem.txt` is not read-only."""
    for c in ("wc -l < contagem.txt", "cat < contagem.txt", "grep -c '' < contagem.txt", "wc -l <contagem.txt"):
        assert shell_is_read_only(c), c
    assert effect_of("bash", {"command": "wc -l < contagem.txt"}) == "read"


def test_the_writing_forms_stay_out():
    for c in ("sort < a.txt > b.txt", "wc -l << EOF", "cat <(ls)", "tee < a.txt b.txt", "wc -l < a.txt; rm a.txt"):
        assert not shell_is_read_only(c), c
    assert effect_of("bash", {"command": "echo x > f.txt"}) == "write"
