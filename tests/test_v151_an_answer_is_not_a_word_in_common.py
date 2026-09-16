"""93.Q2 (F2) — the clarification judge's own negatives: mentioning the topic is not answering.

The independent review of 93.P gives the counter-example verbatim. `diag_clarification.py` scored
"the teaching was applied in a new session" as `"project" in reply.lower()`, and therefore scored

    Nimbus is not a project. I don't know what it is.

as a success. That reply says the opposite of what was taught, and the run it belonged to was
reported as a closed cycle.

So these are the cases the old gate passed and the new one must fail — negation, wrong entity, wrong
context — each paired with the legitimate positive it must keep accepting, because a judge that
refuses everything proves as little as one that accepts everything. The positives are the
discriminating half: a correct answer phrased differently, an answer with a contrast after it, and an
answer that names the context asked about.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from answer_oracle import answered  # noqa: E402

SUBJECT = "Nimbus"
VALUE = "the name of my current project"


def _ok(reply, **kw):
    return answered(reply, subject=SUBJECT, value=VALUE, **kw)


# --- the positives, first: the judge has to be able to say yes -------------------------------------

def test_the_taught_answer_is_an_answer():
    assert _ok("Nimbus is the name of my current project.")["ok"]


def test_a_different_wording_that_still_asserts_it_is_an_answer():
    assert _ok("From what you told me, Nimbus is the name of my current project.")["ok"]


def test_a_contrast_after_the_answer_does_not_undo_it():
    """The negation has to be scoped, or every careful answer would be scored as a denial."""
    assert _ok("Nimbus is the name of my current project, not a client.")["ok"]


# --- the review's own counter-example ---------------------------------------------------------------

def test_the_reply_the_old_gate_accepted_is_refused():
    got = _ok("Nimbus is not a project. I don't know what it is.")
    assert not got["ok"]


def test_negating_the_relation_itself_is_refused():
    got = _ok("Nimbus is not the name of my current project.")
    assert not got["ok"] and got["why"] == "the relation is negated"


def test_sharing_the_topic_word_is_not_an_answer():
    assert not _ok("You have mentioned a project before.")["ok"]


# --- wrong entity, wrong context --------------------------------------------------------------------

def test_the_same_value_asserted_of_another_entity_is_not_this_answer():
    got = _ok("Atlas is the name of my current project.")
    assert not got["ok"] and got["why"] == "the subject is not asserted about at all"


def test_the_value_asserted_in_another_context_is_refused_when_a_context_is_asked_for():
    got = _ok("In Project Omega, Nimbus is the name of my current project.",
              context="Project Alpha")
    assert not got["ok"] and got["why"] == "asserted outside the context asked about"


def test_the_value_asserted_in_the_right_context_is_accepted():
    assert _ok("In Project Alpha, Nimbus is the name of my current project.",
               context="Project Alpha")["ok"]


# --- modality: a mention is not an assertion --------------------------------------------------------

def test_asking_about_it_is_not_answering_it():
    assert not _ok("Is Nimbus the name of my current project?")["ok"]


def test_a_hypothetical_is_not_an_answer():
    assert not _ok("If Nimbus were the name of my current project, I would say so.")["ok"]


def test_an_empty_reply_is_not_an_answer():
    assert not _ok("")["ok"]


# --- the qualifier: asking for the MEANING without accepting a word in common ------------------------
#
# The first version of this judge required every content word of the taught sentence and scored
# "it is listed in my records as your primary project" as not an answer -- a correct application of
# the memory, rejected for being phrased differently. That is the same class of instrument error as
# the gate it replaced, in the other direction. It was corrected after seeing results, which is said
# plainly here; what keeps the correction from being a loosening is that the clause discipline stays:
# the subject must be asserted about, and nothing between it and the value may negate it.

from answer_oracle import POSSESSIVE  # noqa: E402


def _meaning(reply):
    return answered(reply, subject=SUBJECT, value="project", qualifier=POSSESSIVE)


def test_a_correct_answer_in_other_words_is_an_answer():
    assert _meaning("While Project Nimbus often refers to a cloud initiative, it is listed in my "
                    "records as your primary project.")["ok"]


def test_another_correct_wording_is_too():
    assert _meaning("Based on our shared history, Nimbus is the specific project you are currently "
                    "working on.")["ok"]


def test_the_generic_meaning_of_the_word_is_not_the_taught_one():
    """The negative the qualifier exists for: a cloud product is not the user's project."""
    got = _meaning("Project Nimbus most commonly refers to a cloud computing initiative by Google.")
    assert not got["ok"] and got["why"] == "asserted, but not as the user's own"


def test_the_negation_guard_survives_the_looser_value():
    assert not _meaning("Nimbus is not your project.")["ok"]


def test_a_question_is_still_not_an_answer_under_the_qualifier():
    assert not _meaning("Is Nimbus your project?")["ok"]


# --- 94.1c: negation judged independently, in both languages -----------------------------------------
#
# Preserving the frozen 93.V score was a COMPATIBILITY check, not proof the judge is right. This asks
# the question directly, and it includes the two shapes the earlier scope heuristics were never tested
# on: a sentence with NO comma, and a negation inside a quotation.
#
# The history is the point. Attempt 1 looked only BETWEEN subject and value, so "I have never sent an
# email" read as an assertion that one was sent. Attempt 2 widened to the whole clause, which made the
# Portuguese contraction "no" ("in the") a denial and dropped every arm of the frozen set. Attempt 3
# stopped guessing at distance and disambiguated the WORD: `DENIAL` drops bare English "no", which is
# the only member that collides, and keeps "no longer".

NEGATION_CASES = [
    ("en assert", "Nimbus is your current project.", "Nimbus", "project", True),
    ("en trailing contrast", "Nimbus is your current project, not a client.", "Nimbus", "project", True),
    ("en adjunct, no comma", "According to my records Nimbus is your current project.",
     "Nimbus", "project", True),
    ("en not", "Nimbus is not your current project.", "Nimbus", "project", False),
    ("en never, no comma", "I have never sent an email on your behalf.", "email", "sent", False),
    ("en contraction", "Nimbus isn't your project.", "Nimbus", "project", False),
    ("en no longer", "Nimbus is no longer your project.", "Nimbus", "project", False),
    ("pt contraction, comma", "Com base no registo, o teu projeto atual e o HMG.", "HMG", "projeto", True),
    ("pt contraction, NO COMMA", "Com base no registo o teu projeto atual e o HMG.", "HMG", "projeto", True),
    ("pt contraction na", "Na minha memoria o teu projeto atual e o HMG.", "HMG", "projeto", True),
    ("pt plain assert", "O teu projeto atual e o HMG.", "HMG", "projeto", True),
    ("pt nao, no comma", "O ACME-7 nao e o teu projeto atual.", "ACME-7", "projeto", False),
    ("pt nao accented", "O ACME-7 não é o teu projeto atual.", "ACME-7", "projeto", False),
    ("pt nunca", "Nunca disseste que o ACME-7 e o teu projeto.", "ACME-7", "projeto", False),
    ("quoted denial, assert after",
     'You said "I never use ACME-7" and Nimbus is your current project.', "Nimbus", "project", True),
    ("quoted assert, real denial",
     'You said "Nimbus is my project" but Nimbus is not your project.', "Nimbus", "project", False),
]


@pytest.mark.parametrize("label,reply,subject,value,is_an_answer", NEGATION_CASES,
                         ids=[c[0] for c in NEGATION_CASES])
def test_negation_is_judged_the_same_in_both_languages(label, reply, subject, value, is_an_answer):
    assert answered(reply, subject=subject, value=value)["ok"] is is_an_answer
