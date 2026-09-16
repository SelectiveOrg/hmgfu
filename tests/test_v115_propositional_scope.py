"""Phase 91.Z — the modality contract classifies PROPOSITIONS, not just sentences.

`sentence_modalities` used to assign one modality per sentence, so "I deny that my dog is called
Green." was `assert` and reached the ledger as a claim. A denial, a doubt or a report is a GOVERNING
CLAUSE, and the proposition it governs carries the status the governor licenses.

Three of these cases were found by instruments rather than by design, and each is kept here so it
cannot come back:

  * the IMPERATIVE ("Remember that ...") has a null subject, and reading it as somebody else's report
    silently stopped four sealed write-set items from being written;
  * a sentence-initial capital is not a proper name, so "Please"/"Could" were mistaken for a speaker;
  * a governed status must NOT use the fiction/hypothesis carry-over, or a denial silences the NEXT
    sentence -- "I deny that blue is my favorite color. My dog is called Green." wrote nothing at all.
"""

from __future__ import annotations

import pytest

from hmgfu.utterance import governed_proposition, sentence_modalities


def _one(text: str):
    got = sentence_modalities(text)
    assert len(got) == 1, got
    return got[0]["text"], got[0]["modality"]


# the user's own voice asserts the complement -- including the three assertions 91.Y silently dropped
@pytest.mark.parametrize("text", [
    "I know that Green is my dog.",
    "I can confirm that Green is my dog.",
    "I am telling you that Green is my dog.",
    "I want to tell you that Green is my dog.",
    "you should know that Green is my dog.",
    "Remember that Green is my dog.",
    "Please remember that Green is my dog.",
    "Could you remember that Green is my dog?",
    "Since 2019 I have told you that Green is my dog.",
])
def test_the_user_asserts_the_complement(text):
    assert _one(text)[1] == "assert"


# denied, doubted, hedged: never a fact
@pytest.mark.parametrize("text", [
    "I deny that Green is my dog.",
    "I deny that my dog is called Green.",
    "I doubt that my dog is called Green.",
    "I never said that Green is my dog.",
    "I did not say that my dog is called Green.",
    "Not that Green is my dog.",
    "I confirm that I deny that blue is my favorite color.",
    "I say that maybe blue is my favorite color.",
    "Eu nunca disse que o meu cao chama-se Green.",
    "Nego que o meu cao chama-se Green.",
    "Duvido que o meu cao chama-se Green.",
])
def test_a_denied_or_doubted_proposition_is_not_a_fact(text):
    assert _one(text)[1] == "hypothesis"


# somebody else's voice: an assertion inside a citation is not the user's own
@pytest.mark.parametrize("text", [
    "My neighbour mentioned that Green is my dog.",
    "I say she claimed that blue is my favorite color.",
    "I was told that Green is my dog.",
    "The vet mentioned that Green is my dog.",
])
def test_an_assertion_inside_a_citation_is_not_the_users(text):
    assert _one(text)[1] == "cite"


def test_a_relative_clause_is_not_a_complement_clause():
    """Without the complement-taking verb class this sentence would be torn in half."""
    text, modality = _one("the car that I bought is blue")
    assert (text, modality) == ("the car that I bought is blue", "assert")


def test_a_denial_does_not_silence_the_next_sentence():
    """The carry-over is for a frame that persists; a denial is about ONE proposition."""
    got = sentence_modalities("I deny that blue is my favorite color. My dog is called Green.")
    assert [c["modality"] for c in got] == ["hypothesis", "assert"]
    assert got[1]["text"] == "My dog is called Green."


def test_the_fiction_carry_over_still_works():
    """The mechanism the previous test must not break."""
    got = sentence_modalities("For a character in my novel. My name is Oscar.")
    assert [c["modality"] for c in got] == ["fiction", "fiction"]


def test_a_mixed_sentence_keeps_its_legitimate_half():
    got = sentence_modalities("I doubt that my dog is called Green, but my cat is called Momo.")
    assert [c["modality"] for c in got] == ["hypothesis", "assert"]


def test_the_strictest_status_in_a_chain_wins():
    assert governed_proposition("I confirm that I deny that blue is my favorite color.") == (
        "blue is my favorite color.", "hypothesis")


def test_time_survives_the_unwrapping():
    """A date qualifying the proposition is still read after the governor is peeled off."""
    got = sentence_modalities("I want to tell you that since 2019 my base is Tete.")
    assert got[0]["modality"] == "assert" and got[0]["valid_from"] == "2019-01-01"
