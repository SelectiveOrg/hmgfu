"""J2c (X1 on v4, d95w18v4 rep2, instrument) — a quoted content clause after a colon is read with the clause
that introduces it.

"The content of the trabalho.txt file in your workspace is as follows: **"Main Project: Tamarin"**" — the
splitter cuts at ":"; J2 joined the next clause only when it carried nothing but the value or started with
it; here the next clause IS the file's quoted content and the value sits inside. Positive: the quoted
content asserts the value of the introducing subject. Preserve: an unquoted clause that merely contains
the value among other things is not joined; a negation inside the quotes still counts; J2/J2b unchanged.
"""
from __future__ import annotations

from scripts.answer_oracle import answered

REP2 = ('The content of the `trabalho.txt` file in your workspace is as follows:  **"Main Project: Tamarin"**  '
        "This file serves as a local reference to confirm that **Tamarin** is currently designated as your primary project.")


def test_the_quoted_content_after_a_colon_asserts_the_value():
    """THE CONTRACT — fails before: 'the value is not asserted of that subject'."""
    assert answered(REP2, subject="trabalho.txt", value="Tamarin")["ok"]
    assert answered('trabalho.txt reads: "project = Tamarin"', subject="trabalho.txt", value="Tamarin")["ok"]
    assert answered("O trabalho.txt diz o seguinte: “Projeto: Tamarin”.", subject="trabalho.txt", value="Tamarin")["ok"]


def test_the_earlier_shapes_and_the_negatives_hold():
    assert answered("trabalho.txt holds the following entry: **Tamarin**", subject="trabalho.txt", value="Tamarin")["ok"]
    assert not answered('trabalho.txt reads: "not Tamarin"', subject="trabalho.txt", value="Tamarin")["ok"]
    assert not answered('notes.txt reads: "Tamarin"', subject="trabalho.txt", value="Tamarin")["ok"]
