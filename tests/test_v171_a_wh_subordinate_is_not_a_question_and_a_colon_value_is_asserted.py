"""J1 / J2 — the two judge errors found in 94.7/94.8, fixed at the layer each belongs to.

J1 is NOT only a judge error. `speech_act.is_interrogative` reads any sentence-initial wh-word as a
question when there is no "?", so the Portuguese subordinate opener *"Como você acabou de me informar
que não trabalha mais no Nimbus, o seu projeto atual é o Vega."* is classified `question` — by the
system (router, fact extraction) as much as by the judge that imports it. R5 scored a correct answer
wrong in both arms because of it. The structural rule: a wh-opener that is followed by a comma and a
NEW clause opening with its own determiner/pronoun, with no "?", is a subordinate, not a question.

J2 is judge-only. `sentence_modalities` splits at ":" (it must — "the hero says: …" is reported
speech), so *"The checksum line in the inventory file is: **VEGA-INVENTORY-OK**"* becomes two clauses
and the value never shares a clause with its subject. E2 scored three correct replies wrong. The judge
reads a clause that carries nothing but the value with the assert clause before it.

Positives, negatives, variants, and the behaviour that must not change — PT and EN — as §9 requires.
"""
from __future__ import annotations

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
from answer_oracle import answered  # noqa: E402
from hmgfu.speech_act import is_interrogative  # noqa: E402
from hmgfu.utterance import sentence_modalities  # noqa: E402


# --- J1: a wh-word opening a subordinate is not a question ------------------------------------------

@pytest.mark.parametrize("text", [
    "Como você acabou de me informar que não trabalha mais no Nimbus, o seu projeto atual é o Vega.",
    "Como me disseste ontem, o teu projeto principal é o Vega.",
    "When I started, my main project was Nimbus.",
    "Quando começámos, o projeto chamava-se Halcyon.",
    "How you described it, the checksum line is VEGA-INVENTORY-OK.",
])
def test_a_wh_subordinate_opener_is_a_statement(text):
    assert not is_interrogative(text), text


@pytest.mark.parametrize("text", [
    "Como te chamas?",
    "Como estás",                              # no "?", no comma-clause: still a question
    "Quando é a revisão de lançamento?",
    "What is my main project called?",
    "How did you get that, and what did you have to find first?",
    "Where did we agree to hold the launch party",
])
def test_a_real_question_is_still_a_question(text):
    assert is_interrogative(text), text


def test_the_pt_subordinate_reply_is_read_as_an_assertion():
    """The R5 reply, both arms: correct, and now scored so."""
    reply = "Como você acabou de me informar que não trabalha mais no Nimbus, o seu projeto atual é o Vega."
    mods = [c["modality"] for c in sentence_modalities(reply)]
    assert "assert" in mods, mods
    assert answered(reply, subject="projeto", value="Vega")["ok"]


def test_the_subordinate_does_not_confirm_the_old_value():
    """Negation inside the subordinate must not read as asserting Nimbus of the project."""
    reply = "Como você acabou de me informar que não trabalha mais no Nimbus, o seu projeto atual é o Vega."
    assert not answered(reply, subject="projeto", value="Nimbus")["ok"]


# --- J2: a value after a colon is asserted of the subject before it ------------------------------------

@pytest.mark.parametrize("reply", [
    "The checksum line in the inventory file is: **VEGA-INVENTORY-OK**",
    "The checksum line found in the inventory file is: VEGA-INVENTORY-OK",
    "A linha de checksum no ficheiro de inventário é: **VEGA-INVENTORY-OK**",
])
def test_a_colon_separated_value_is_asserted_of_its_subject(reply):
    assert answered(reply, subject="checksum", value="VEGA-INVENTORY-OK")["ok"], reply


def test_a_colon_value_is_not_asserted_of_a_subject_it_does_not_follow():
    """The value after the colon belongs to the clause before it, not to any earlier subject."""
    reply = "The project is Nimbus. The checksum line is: **VEGA-INVENTORY-OK**"
    assert not answered(reply, subject="project", value="VEGA-INVENTORY-OK")["ok"]


def test_reported_speech_after_a_colon_is_still_a_citation():
    """The reason the splitter splits at ':' must survive: 'the hero says: …' is not the user's claim."""
    reply = "In the book, the hero says: my name is Kael."
    assert not answered(reply, subject="name", value="Kael")["ok"]


def test_a_denial_before_the_colon_still_negates():
    reply = "The checksum line is not: VEGA-INVENTORY-OK"
    assert not answered(reply, subject="checksum", value="VEGA-INVENTORY-OK")["ok"]
