"""J7 (X1 on v4, d95w16v4 rep3, instrument) — a sentence opening with a bare pronoun is read with the
previous sentence's subject when that sentence named it.

"The file `trabalho.txt` contains the name of your main project. Specifically, it holds the following
entry: **Tamarin**" — the value is asserted of "it", whose antecedent is trabalho.txt in the sentence
before; the oracle saw the subject and the value in two different parts. Positive: the pronoun sentence
asserts the value of the antecedent (EN, PT; with and without the connective). Preserve: a pronoun whose
previous sentence names ANOTHER subject asserts nothing of the asked one; a negated pronoun sentence is
negated; the plain and the J2 shapes are unchanged.
"""
from __future__ import annotations

from scripts.answer_oracle import answered

REP3 = ("The file `trabalho.txt` contains the name of your main project. Specifically, it holds the following entry:  "
        "**Tamarin**  This file was recently updated to reflect that **Tamarin** is the current and official name of your "
        "primary project, replacing the previous designation, Kestrel.")


def test_the_pronoun_sentence_asserts_the_value_of_its_antecedent():
    """THE CONTRACT — fails before: 'the value is not asserted of that subject'."""
    assert answered(REP3, subject="trabalho.txt", value="Tamarin")["ok"]
    assert answered("trabalho.txt is in the workspace. It contains Tamarin.", subject="trabalho.txt", value="Tamarin")["ok"]
    assert answered("O trabalho.txt existe. Ele contem Tamarin.", subject="trabalho.txt", value="Tamarin")["ok"]
    assert answered("I read trabalho.txt. In short, it says Tamarin.", subject="trabalho.txt", value="Tamarin")["ok"]


def test_another_antecedent_a_negation_and_the_plain_shapes():
    assert not answered("The other file is notes.txt. It contains Tamarin.", subject="trabalho.txt", value="Tamarin")["ok"]
    assert not answered("trabalho.txt is there. It does not contain Tamarin.", subject="trabalho.txt", value="Tamarin")["ok"]
    assert answered("trabalho.txt says Tamarin.", subject="trabalho.txt", value="Tamarin")["ok"]
    assert answered("trabalho.txt holds the following entry: **Tamarin**", subject="trabalho.txt", value="Tamarin")["ok"]
    assert not answered("trabalho.txt is there. Kestrel was the old name.", subject="trabalho.txt", value="Tamarin")["ok"]
