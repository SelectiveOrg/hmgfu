"""J1b (T4 d95w11e rep3, instrument) — a concessive subordinate is not the claim.

The reply said 'Embora o termo "Kernel Lock Manager" descreva uma função real ..., a sigla KLM-3 não é
um padrão da indústria para isso' and the oracle read the subordinate with the main clause (J1 covers
wh-openers only; the denial stands after both words, 94.1's scope). Positive: the concessive
subordinate is dropped and the main clause is judged on its own words — a correct non-assertion.
Preserve: a value asserted in the MAIN clause after a concessive still asserts; a concessive opener
is not a question; the wh-subordinate case (J1) is unchanged; a plain assertion is unchanged.
"""
from __future__ import annotations

from hmgfu.speech_act import is_interrogative
from scripts.answer_oracle import answered

T4 = ('Embora o termo "Kernel Lock Manager" descreva uma função real dentro de sistemas operacionais (gerenciar como '
      'processos acessam recursos compartilhados para evitar conflitos), a sigla **KLM-3** não é um padrão da indústria para isso.')


def test_the_concessive_subordinate_is_not_the_claim():
    """THE CONTRACT — fails before: the subordinate's value is read with the main clause's subject."""
    got = answered(T4, subject="KLM-3", value="Kernel Lock Manager")
    assert not got["ok"], got
    assert not answered("Although he calls it Kernel Lock Manager, KLM-3 is not that.", subject="KLM-3", value="Kernel Lock Manager")["ok"]


def test_the_main_clause_after_a_concessive_still_asserts():
    assert answered("Embora ele diga outra coisa, KLM-3 significa Kernel Load Monitor.", subject="KLM-3", value="Kernel Load Monitor")["ok"]
    assert answered("Although it is old, my main project is Nimbus.", subject="project", value="Nimbus")["ok"]


def test_openers_and_the_wh_case_are_unchanged():
    assert not is_interrogative("Embora eu tenha duvidas, o meu projeto principal e o Vega.")
    assert not answered("Como me disseste que nao era Atlas, o teu projeto e Nimbus.", subject="projeto", value="Atlas")["ok"]
    assert answered("KLM-3 means Kernel Lock Manager.", subject="KLM-3", value="Kernel Lock Manager")["ok"]


def test_a_main_clause_opening_with_a_pronoun_keeps_its_antecedent():
    """v151 caught the first cut: the pronoun refers back to the subordinate's subject."""
    got = answered("While Project Nimbus often refers to a cloud initiative, it is listed in my records as your primary project.",
                   subject="project", value="Nimbus", qualifier=("your", "yours"))
    assert got["ok"], got
    assert answered("Embora o nome seja comum, ele e o teu projeto principal: Nimbus.", subject="projeto", value="Nimbus")["ok"]
