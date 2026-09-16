"""J9 (X1 on v4, d95w19v4 rep2, instrument) — a file that "says" something asserts its content.

"The file trabalho.txt contains the name of your main project. Specifically, it says: **Tamarin**" — "X says ..."
is reported speech for the modality contract (a citation of a person, never an assertion), so the clause was
skipped and the value was "not asserted of that subject". For a FILE (the asked subject is a file name, named in
the clause or as the antecedent of its pronoun) "says / reads / diz" reports the file's own content. Positive: the
file's content is asserted (named subject; pronoun antecedent; PT). Preserve: a PERSON who says something is
still a citation; another file's content asserts nothing of this one; a file that says "not Tamarin" is negated.
"""
from __future__ import annotations

from scripts.answer_oracle import _is_file, answered

REP2 = ("The file `trabalho.txt` contains the name of your main project.  Specifically, it says: **Tamarin**  "
        "As we discussed previously, this confirms that **Tamarin** is the current name for your primary work.")


def test_a_file_that_says_the_value_asserts_it():
    """THE CONTRACT — fails before: the 'says' clause is a citation and is skipped."""
    assert answered(REP2, subject="trabalho.txt", value="Tamarin")["ok"]
    assert answered("trabalho.txt says Tamarin.", subject="trabalho.txt", value="Tamarin")["ok"]
    assert answered("O trabalho.txt diz Tamarin.", subject="trabalho.txt", value="Tamarin")["ok"]
    assert _is_file("trabalho.txt") and _is_file("ola_ibis.py") and not _is_file("Rui") and not _is_file("PXD-4")


def test_a_person_who_says_it_is_still_a_citation_and_the_negatives_hold():
    assert not answered("trabalho.txt is here. Rui says it holds Tamarin.", subject="trabalho.txt", value="Tamarin")["ok"]
    assert not answered("notes.txt says Tamarin.", subject="trabalho.txt", value="Tamarin")["ok"]
    assert not answered("trabalho.txt says it is not Tamarin.", subject="trabalho.txt", value="Tamarin")["ok"]
