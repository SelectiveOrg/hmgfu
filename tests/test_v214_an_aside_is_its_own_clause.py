"""S4 instrument (d95w9 rep1) — an aside is its own clause.

The reply "— como o fato de que o seu projeto principal é o Marlin, ... —, o nome da sua empresa não
consta ..." was judged as asserting Marlin of the company: one sentence held both words, its modality
was assert, and the negation stood after both. A dash- or bracket-delimited aside is a structural unit
(like J1's subordinate and J2's colon clause): the sentence is judged with the aside removed, the aside
on its own. Positive: the S4 shape is not an assertion about the company. Preserve: an aside carrying
nothing but the value still answers (J2's rule); a plain assertion still asserts; a denial with an
aside in it still denies.
"""
from __future__ import annotations

from scripts.answer_oracle import answered

S4 = ("Embora eu tenha informações bem detalhadas sobre os seus projetos atuais e preferências pessoais — como o "
      "fato de que o seu projeto principal é o **Marlin**, a sua localização em Aveiro, o nome do seu gato Sol e a "
      "definição técnica para KLM-3 (Kernel Load Monitor) —, o nome da sua empresa não consta explicitamente nos "
      "dados que foram consolidados na minha memória de longo prazo até este momento.")


def test_the_aside_does_not_assert_its_value_of_the_sentences_subject():
    """THE CONTRACT — fails before: one sentence, both words, read as asserted."""
    got = answered(S4, subject="empresa", value="Marlin")
    assert not got["ok"], got
    assert answered(S4, subject="projeto", value="Marlin")["ok"]          # the aside asserts it of the project


def test_an_aside_that_is_only_the_value_still_answers():
    assert answered("O teu projeto — Marlin — é o principal.", subject="projeto", value="Marlin")["ok"]
    assert answered("Your main project (Marlin) is going well.", subject="project", value="Marlin")["ok"]


def test_plain_assertions_and_denials_are_unchanged():
    assert answered("A tua empresa chama-se Marlin.", subject="empresa", value="Marlin")["ok"]
    got = answered("The company — I checked the records — is not Marlin.", subject="company", value="Marlin")
    assert not got["ok"] and got["why"] == "the relation is negated", got
