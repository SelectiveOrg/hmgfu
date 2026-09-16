"""J1d (X4 on e05b40a rep2, instrument) — a subordinate is split off and judged on its own, not dropped.

"Since there were 4 distinct lines of text separated by these breaks, the total count is 4." — the
causal subordinate carried the answer and J1c's cut discarded it; the main clause named no subject.
The J1 family exists to keep a subordinate's negation out of the main clause's denial scope, never to
discard what the subordinate asserts. Positive: the causal subordinate that carries the answer asserts
it. Preserve: the wh case still does not assert the denied old value; the concessive case (T4) still
does not assert the cited value of the term; the causal-noise case (J1c) still asserts the main
clause; the pronoun-opener case (v151) still asserts.
"""
from __future__ import annotations

from scripts.answer_oracle import answered


def test_a_causal_subordinate_that_carries_the_answer_asserts_it():
    """THE CONTRACT — fails before: the subordinate is cut and the main clause names no subject."""
    got = answered("Since there were 4 distinct lines of text separated by these breaks, the total count is 4.",
                   subject="lines", value="four")
    assert got["ok"], got
    assert answered("Como o ficheiro tinha 4 linhas, a contagem deu 4.", subject="linhas", value="quatro")["ok"]


def test_the_earlier_verdicts_are_unchanged():
    assert not answered("Como me disseste que nao era Atlas, o teu projeto e Nimbus.", subject="projeto", value="Atlas")["ok"]
    assert answered("Como me disseste que nao era Atlas, o teu projeto e Nimbus.", subject="projeto", value="Nimbus")["ok"]
    T4 = ('Embora o termo "Kernel Lock Manager" descreva uma função real dentro de sistemas operacionais, a sigla '
          '**KLM-3** não é um padrão da indústria para isso.')
    assert not answered(T4, subject="KLM-3", value="Kernel Lock Manager")["ok"]
    assert answered("Since I don't have a dedicated line-counting tool, I processed ledger.txt and identified 4 distinct lines within it.",
                    subject="lines", value="four")["ok"]
    assert answered("While Project Nimbus often refers to a cloud initiative, it is listed in my records as your primary project.",
                    subject="project", value="Nimbus", qualifier=("your", "yours"))["ok"]
