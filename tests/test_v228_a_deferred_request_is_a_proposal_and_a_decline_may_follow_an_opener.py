"""X7 on v4 (0/3 both arms) — a request deferred to the user's confirmation is a proposal by
construction, and a decline may follow a discourse opener.

"Prepara um ficheiro resumo.md com o texto RESUMO-TAMARIN, mas so depois de eu confirmar." produced no
proposal when the model merely said it was waiting (no intent cue, no tool call); "Afinal nao, deixa
estar." then had nothing to abandon, and where a plan existed it stayed "proposed" because the decline
sat behind "Afinal". Positive: the deferred request reads as a suggestion (permission-first, Phase 67)
in PT and EN; the opener-led decline is a decline. Negative: a plain order is not a suggestion; a
message opening with "afinal" but not declining is not a decline; v3's wording still reads as deferred.
"""
from __future__ import annotations

from hmgfu.session_plans import _NO
from hmgfu.speech_act import is_deferred_to_confirmation, is_suggestion

V4 = "Prepara um ficheiro resumo.md com o texto RESUMO-TAMARIN, mas so depois de eu confirmar."
V3 = "Prepara um ficheiro relatorio.md com o texto RELATORIO-LYRA, mas espera pela minha confirmacao."
EN = "Write a file summary.md containing SUMMARY-OK, but only after I confirm."


def test_a_request_deferred_to_confirmation_is_a_proposal():
    """THE CONTRACT — fails before: none of these is read as a suggestion."""
    for t in (V4, V3, EN):
        assert is_deferred_to_confirmation(t) and is_suggestion(t), t


def test_a_plain_order_is_still_an_order():
    assert not is_suggestion("Prepara um ficheiro resumo.md com o texto RESUMO-TAMARIN.")
    assert not is_deferred_to_confirmation("Write summary.md now.")


def test_a_decline_behind_a_discourse_opener_is_a_decline():
    for t in ("Afinal nao, deixa estar.", "Actually, no.", "Bem, nao.", "Nao, deixa estar."):
        assert _NO.match(t), t
    assert not _NO.match("Afinal o projeto chama-se Vega.")
