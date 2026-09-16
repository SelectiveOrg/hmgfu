"""X4 instrument — a number is the same number written in words or in digits.

X4 (candidate 0/3): the product discovered `bash`, ran `wc -l stock.txt`, answered "There are 4 lines"
and read the file to confirm — the oracle wanted "four". Positive: "4 lines" asserts "four"; "quatro"
too. Negative: a different number does not. Preserve: non-numeric values unchanged; a denial still
denies.
"""
from __future__ import annotations

from scripts.answer_oracle import answered


def test_digits_assert_the_number_word():
    """THE CONTRACT — fails before: '4' is not 'four'."""
    assert answered("There are 4 lines in stock.txt.", subject="lines", value="four")["ok"]
    assert answered("stock.txt has four lines.", subject="lines", value="4")["ok"]
    assert answered("O ficheiro tem 4 linhas.", subject="linhas", value="quatro")["ok"]


def test_a_different_number_does_not():
    assert not answered("There are 5 lines in stock.txt.", subject="lines", value="four")["ok"]


def test_non_numeric_values_and_denials_are_unchanged():
    assert answered("Your cat is called Sol.", subject="cat", value="Sol")["ok"]
    assert not answered("There are not four lines in stock.txt.", subject="lines", value="four")["ok"]
