"""J8 (X4 on v4, d95w19v4 rep1, instrument) — a plain-word subject matches its singular or plural as a whole word.

"I simply processed the text within ledger.txt and identified 4 distinct line breaks/entries." — the subject
"lines" was matched as a substring, so "line breaks" was not seen and the count was "not asserted of that
subject". Positive: "lines" matches "line"/"lines" as a whole word. Preserve: a file name or a code matches as
before; "linear" is not "line"; the one-part rule stands (a count in another sentence is still not asserted).
"""
from __future__ import annotations

from scripts.answer_oracle import _subject_in, answered

REP1 = ("I counted the lines by reading the content of the file directly. Since I don't have a dedicated "
        "\"line-counting\" tool, I simply processed the text within `ledger.txt` and identified 4 distinct line breaks/entries.")


def test_the_singular_of_a_plain_word_subject_is_seen():
    """THE CONTRACT — fails before: 'lines' is not found in 'line breaks'."""
    assert answered(REP1, subject="lines", value="four")["ok"]
    assert answered("ledger.txt has 4 lines.", subject="lines", value="four")["ok"]
    assert answered("The file holds a single line: 1.", subject="lines", value="one")["ok"]
    assert _subject_in("lines", "identified 4 distinct line breaks") and _subject_in("line", "it has 4 lines")


def test_the_other_subjects_and_the_negatives_hold():
    assert _subject_in("trabalho.txt", "trabalho.txt says tamarin") and not _subject_in("trabalho.txt", "trabalho says tamarin")
    assert not _subject_in("lines", "a linear scan found 4 items")
    assert not answered("I counted the lines. I found 4 errors.", subject="lines", value="four")["ok"] or \
        answered("I counted the lines. I found 4 errors.", subject="lines", value="four")["clause"] == "I counted the lines."
    assert not answered("I read the file. It has 4 columns.", subject="lines", value="four")["ok"]
