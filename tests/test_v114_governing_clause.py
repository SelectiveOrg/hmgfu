"""Phase 91.Y — a proposition under a governing clause is not automatically the user's own claim.

91.X2 taught the subject extraction to cut through a complementizer. It cut without preserving the
semantic status of the clause it discarded, so "I never said that Green is my dog" overwrote the
ledger with Green. The independent review caught it; this test is the contract that stopped it.

`clause_asserted` is an ALLOW-LIST of the assertive frame -- the user's own speech act, in the
present -- so an unfamiliar governing verb fails CLOSED. It is the write-side counterpart of the
modality contract in `utterance.py`, and the same discipline as `_INTENT`'s `_SPEECH_ACT` guard,
which already keeps "I want to tell you that my name is X" an assertion.

The cases below are the DEV shapes; the sealed counterpart lives in
`scripts/oracles/modality_reserved_v1.json` and shares no sentence with them.
"""

from __future__ import annotations

import pytest

from hmgfu.fact_detect import detect_facts
from hmgfu.value_gate import clause_asserted, clause_governor

# the user asserts it: nothing governs the proposition, or the governor is their own speech act
ASSERTED = [
    "Green is my dog",
    "Actually Green is my dog",
    "but Green is my dog",
    "but you should know that green is my dog also",
    "you should know that Green is my dog",
    "I want to tell you that Green is my dog",
    "I should mention that Green is my dog",
]

# the user does NOT assert it: the governor denies, doubts, intends, reports or questions
NOT_ASSERTED = [
    "I never said that Green is my dog",
    "I did not say that Green is my dog",
    "I deny that Green is my dog",
    "It is not true that Green is my dog",
    "Not that Green is my dog",
    "I doubt that Green is my dog",
    "I am not sure that Green is my dog",
    "I was going to say that Green is my dog",
    "I was told that Green is my dog",
    "She wrote that Green is my dog",
    "My neighbour says that Green is my dog",
    "Who said that Green is my dog",
    "I heard that Green is my dog",
    "The vet mentioned that Green is my dog",
    "Maybe Green is my dog",
]


@pytest.mark.parametrize("text", ASSERTED)
def test_the_user_asserts_it(text):
    assert clause_asserted(text) is True, f"{clause_governor(text)!r} should assert its complement"


@pytest.mark.parametrize("text", NOT_ASSERTED)
def test_the_user_does_not_assert_it(text):
    assert clause_asserted(text) is False, f"{clause_governor(text)!r} must not assert its complement"


@pytest.mark.parametrize("text", [
    "I never said that Green is my dog.",
    "I deny that Green is my dog.",
    "I doubt that Green is my dog.",
    "Not that Green is my dog.",
    "I was told that Green is my dog.",
])
def test_no_pet_name_is_detected_from_an_unasserted_complement(text):
    assert not [d for d in detect_facts(text) if (d.get("value") or "").lower() == "green"], \
        f"{text!r} produced a write for Green"


def test_the_reported_sentence_still_resolves_to_its_subject():
    """The 91.X2 gain is not traded away to fix the regression."""
    got = {d["key"]: d.get("value") for d in detect_facts("but you should know that green is my dog also")}
    assert got == {"dog": "green"}
