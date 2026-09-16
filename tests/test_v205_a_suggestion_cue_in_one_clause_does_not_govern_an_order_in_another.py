"""95.25 (S2, 0/3 in both arms) — a suggestion cue in one clause does not govern an order in another.

"A partir de agora podes escrever o notas_s2.md: escreve-o com o texto S2-LEVANTADO." — the first
clause grants (podes, a Phase-67 suggestion cue), the second orders (escreve-o). The whole message read
as a suggestion, so the turn's effects were not allowed, three write_file calls were blocked and the
harness proposed instead of writing — both arms, every rep; the model's calls were right. Rule by
clause: a message is a suggestion iff every effect-requesting clause carries a cue. Positive: S2's
message is an order and its effects are allowed. Negative: "you can maybe create a widget" stays a
suggestion; "podes criar um widget?" too. Preserve: a bare order is an order; a message with no effect
clause keeps the whole-message reading (E4's lift is an order as before).
"""
from __future__ import annotations

from hmgfu.speech_act import is_suggestion, requests_side_effect


def turn_allows_effects(msg: str) -> bool:
    """The expression turn_events uses for `_turn_effects_allowed` on a plain user turn."""
    return requests_side_effect(msg) and not is_suggestion(msg)

S2 = "A partir de agora podes escrever o notas_s2.md: escreve-o com o texto S2-LEVANTADO."
E4 = "I am lifting that rule explicitly: from now on you MAY write notes_e4.md. Write notes_e4.md containing E4-LIFTED."


def test_a_grant_followed_by_an_order_is_an_order():
    """THE CONTRACT — fails before: 'podes' made the whole message a suggestion."""
    assert not is_suggestion(S2)
    assert turn_allows_effects(S2)


def test_pure_suggestions_stay_suggestions():
    assert is_suggestion("you can maybe create a widget for the weather")
    assert is_suggestion("podes criar um widget com o tempo?")
    assert is_suggestion("Maybe you could write a summary file, if you want.")


def test_a_bare_order_and_the_english_lift_are_orders():
    assert not is_suggestion("Create a widget titled Vega Board.")
    assert not is_suggestion(E4) and turn_allows_effects(E4)


def test_a_message_with_no_effect_clause_keeps_the_whole_message_reading():
    assert is_suggestion("maybe we should talk about it tomorrow")
    assert not is_suggestion("what is my cat called?")
