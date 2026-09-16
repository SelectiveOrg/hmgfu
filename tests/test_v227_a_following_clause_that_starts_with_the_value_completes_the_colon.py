"""J2b (X1 on v4, instrument) — a following clause that STARTS with the value completes the colon.

The live answer "The content of the file `trabalho.txt` is: **Tamarin** As we discussed recently, this
file serves ..." glued the value to the next sentence in one clause; J2 read a following clause with
the colon clause only when it carried nothing but the value, so a correct grounded answer was judged
not asserted. Positive: the value first in the following clause completes the colon. Preserve: J2's
only-the-value case; a following clause where the value is not first does not complete it; a denial in
the following clause still denies.
"""
from __future__ import annotations

from scripts.answer_oracle import answered

GLUED = ("The content of the file `trabalho.txt` is: **Tamarin** As we discussed recently, this file serves as your primary "
         "reference for the name of your main project.")


def test_a_following_clause_starting_with_the_value_completes_the_colon():
    """THE CONTRACT — fails before: the following clause carries more than the value."""
    assert answered(GLUED, subject="trabalho.txt", value="Tamarin")["ok"]


def test_the_only_value_case_and_the_negatives_are_unchanged():
    assert answered("The content of trabalho.txt is:\n\n**Tamarin**\n\nAnything else?", subject="trabalho.txt", value="Tamarin")["ok"]
    assert not answered("The content of trabalho.txt is: as we discussed, Tamarin is your project.", subject="trabalho.txt", value="Tamarin")["ok"]
    got = answered("The content of trabalho.txt is: not Tamarin, something else.", subject="trabalho.txt", value="Tamarin")
    assert not got["ok"]
