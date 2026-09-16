"""J1c (X4 on b9bedb4 rep2, instrument) — a causal subordinate is not the claim.

"Since I don't have a dedicated line-counting tool, I processed the text of ledger.txt and identified 4
distinct lines within it." — the oracle read the subordinate's "don't" as negating the count (94.1's
scope reaches from the clause start to the later of the two words). Positive: the causal subordinate is
dropped and the main clause asserts the count, EN and PT. Preserve: a denial in the MAIN clause still
denies; a value in the causal subordinate is asserted by the subordinate itself (J1d: split, not dropped);
the concessive and wh cases unchanged.
"""
from __future__ import annotations

from scripts.answer_oracle import answered

X4 = ("Since I don't have a dedicated \"line-counting\" tool, I processed the text of `ledger.txt` and identified 4 "
      "distinct lines within it.")


def test_a_causal_subordinate_is_dropped_and_the_main_clause_asserts():
    """THE CONTRACT — fails before: 'the relation is negated'."""
    assert answered(X4, subject="lines", value="four")["ok"]
    assert answered("Como nao tenho uma ferramenta de contagem, li o ficheiro e contei 4 linhas.", subject="linhas", value="quatro")["ok"]


def test_the_main_clause_denial_and_the_other_openers_are_unchanged():
    got = answered("Because the file is empty, ledger.txt does not have four lines.", subject="lines", value="four")
    assert not got["ok"] and got["why"] == "the relation is negated"
    assert answered("Because it has four lines, the file is short.", subject="lines", value="four")["ok"]   # J1d: the subordinate asserts its own content
    assert answered("Although it is old, my main project is Nimbus.", subject="project", value="Nimbus")["ok"]
    assert not answered("Como me disseste que nao era Atlas, o teu projeto e Nimbus.", subject="projeto", value="Atlas")["ok"]
