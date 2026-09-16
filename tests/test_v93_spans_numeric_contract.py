"""Phase 90.H1 — the errata question answered by the contract: the write sets mark 'My lucky number is 9' / 'O meu número da sorte é 8'
as NO-WRITE while '17' and '42' are writes, and the regex path behaves exactly so (single-digit values are not attribute values —
the counting-number ambiguity). The spans path must apply the same rule: the oracles are right, the two "undue writes" were real.
Originals preserved; no errata."""
from __future__ import annotations

from hmgfu.fact_spans import extract_spans


def _fake(facts):
    return lambda prompt, schema: {"facts": facts}


def test_single_digit_numbers_are_not_values_on_the_spans_path_either():
    for text, val in [("My lucky number is 9.", "9"), ("O meu número da sorte é 8.", "8")]:
        dets = extract_spans(text, _fake([{"attribute": "lucky number", "value": val}]))
        assert dets == [], text


def test_multi_digit_lucky_numbers_still_pass():
    for text, val in [("My lucky number is 17.", "17"), ("My lucky number is 42.", "42")]:
        dets = extract_spans(text, _fake([{"attribute": "lucky number", "value": val}]))
        assert [(d["key"], d["value"]) for d in dets] == [("misc.lucky_number", val)], text
