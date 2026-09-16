"""95.53 (X7 on v5, 0/3 both arms) — the deferral construction with its preposition variants; a decline
behind a reconsideration opener.

"Prepara um ficheiro sumario.md com o texto SUMARIO-IBIS, mas fica a espera da minha ordem." was not
read as deferred ("espera (pela|a) minha" only; here "a espera DA minha ordem"), so the file was written
at once; "Pensando melhor, nao vale a pena." was not read as a decline (the opener class lacked the
reconsideration openers), so a plan would not have been abandoned. Positive: the v5 wording and its
kin defer (PT and EN); the reconsideration-led declines decline. Preserve: v3's and v4's deferral
wordings; a plain order; a non-declining "Pensando melhor, ..." sentence.
"""
from __future__ import annotations

from hmgfu.session_plans import _NO
from hmgfu.speech_act import is_deferred_to_confirmation, is_suggestion

V5 = "Prepara um ficheiro sumario.md com o texto SUMARIO-IBIS, mas fica a espera da minha ordem."


def test_the_v5_deferral_and_its_kin_are_read():
    """THE CONTRACT — fails before: 'a espera da minha ordem' is not a deferral."""
    for t in (V5,
              "Prepara o ficheiro, mas fico a espera da tua luz verde.".replace("tua", "minha"),
              "Escreve o resumo.md, mas so quando eu mandar.",
              "Draft summary.md, but hold off until I give the word.",
              "Write summary.md, but wait for my word."):
        assert is_deferred_to_confirmation(t) and is_suggestion(t), t


def test_the_earlier_deferral_wordings_and_a_plain_order_are_unchanged():
    assert is_deferred_to_confirmation("Prepara um ficheiro resumo.md com o texto RESUMO-TAMARIN, mas so depois de eu confirmar.")
    assert is_deferred_to_confirmation("Prepara um ficheiro relatorio.md com o texto RELATORIO-LYRA, mas espera pela minha confirmacao.")
    assert not is_deferred_to_confirmation("Prepara um ficheiro sumario.md com o texto SUMARIO-IBIS.")
    assert not is_suggestion("Prepara um ficheiro sumario.md com o texto SUMARIO-IBIS.")


def test_a_decline_behind_a_reconsideration_opener_is_a_decline():
    for t in ("Pensando melhor, nao vale a pena.", "On second thought, no.", "Thinking about it, don't.", "Afinal de contas, deixa estar."):
        assert _NO.match(t), t
    assert not _NO.match("Pensando melhor, o projeto chama-se Ibis.")
