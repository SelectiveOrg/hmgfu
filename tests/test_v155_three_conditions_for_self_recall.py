"""93.Q4 — the self-recall judge, and why one definition of "correct" will not do for three conditions.

The review asks for three comparable conditions and four measurements. The trap is scoring them all
the same way: a search is the warranted act when the context does not answer, and a pure cost when it
does, so a single gate would either punish the right behaviour in one arm or reward the wrong one in
another.

The other trap is the one 93.Q3 fixed in the product: crediting a run for saying *"I don't have a
specific location recorded"*. That is a claim about the MEMORY, and it is wrong in `related_only`
(the venue is stored, merely unretrieved) and still unsupported in `truly_absent`, where what the turn
actually knows is that a search did not find it.

The two conditions that are compared must differ in exactly one thing, so the settings they run under
are asserted equal here — a campaign that changed retrievability AND existence at once is what the
review refused to accept as a control.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from self_recall_arms import ARMS, judge, seeds_the_value, settings_for

STORED = "Kestrel Pier"


def test_only_the_absent_arm_withholds_the_value():
    assert [a for a in ARMS if not seeds_the_value(a)] == ["truly_absent"]


def test_the_two_compared_arms_run_under_identical_settings():
    """The whole point of the pair: one variable, not two."""
    assert settings_for("related_only") == settings_for("truly_absent")


def test_the_in_context_arm_is_declared_different_rather_than_hidden():
    assert settings_for("in_context") != settings_for("related_only")


# --- in_context: answering is the job; searching anyway is a cost -----------------------------------

def test_answering_from_the_context_is_correct_without_any_search():
    got = judge("in_context", searched=False, value_in_context=True, answered_ok=True,
                reply=f"It is at {STORED}.")
    assert got["correct"] and not got["search_was_needed"] and not got["unnecessary_search"]


def test_searching_when_the_context_already_answered_is_counted_as_waste():
    got = judge("in_context", searched=True, value_in_context=True, answered_ok=True,
                reply=f"It is at {STORED}.")
    assert got["unnecessary_search"], "a search on every turn is a cost, not a virtue"


# --- related_only: the condition the live run got wrong ---------------------------------------------

def test_finding_it_after_a_focused_search_is_correct():
    got = judge("related_only", searched=True, value_in_context=False, answered_ok=True,
                reply=f"You agreed on {STORED}.")
    assert got["correct"] and got["search_was_needed"]


def test_saying_it_is_not_recorded_when_it_is_stored_is_not_correct():
    """The live reply, verbatim in spirit: the venue WAS stored and merely outside the context."""
    got = judge("related_only", searched=True, value_in_context=False, answered_ok=False,
                reply="I don't have a specific location recorded in our conversation yet.")
    assert got["claimed_absence"] and not got["correct"]


def test_an_answer_that_is_simply_wrong_is_not_rescued_by_saying_nothing_about_memory():
    got = judge("related_only", searched=True, value_in_context=False, answered_ok=False,
                reply="It is at the Town Hall.")
    assert not got["correct"]


# --- truly_absent: not finding it is allowed; inventing and overclaiming are not ----------------------

def test_not_finding_it_and_saying_so_is_correct():
    got = judge("truly_absent", searched=True, value_in_context=False, answered_ok=False,
                reply="I could not find a venue in what I searched for about the launch party.")
    assert got["correct"] and not got["claimed_absence"]


def test_inventing_a_venue_is_not_correct():
    got = judge("truly_absent", searched=True, value_in_context=False, answered_ok=False,
                reply="It is at the Town Hall.", invented=True)
    assert not got["correct"]


def test_a_flat_claim_about_the_memory_is_still_not_correct_here():
    """A search that found nothing licenses "I did not find it", not "you never told me"."""
    got = judge("truly_absent", searched=True, value_in_context=False, answered_ok=False,
                reply="You never told me where the party is.")
    assert got["claimed_absence"] and not got["correct"]


@pytest.mark.parametrize("reply", ["I have no record of that.",
                                   "Nothing recorded about the venue.",
                                   "I don't have that stored."])
def test_the_absence_cues_catch_the_shapes_the_live_runs_used(reply):
    assert judge("truly_absent", searched=True, value_in_context=False, answered_ok=False,
                 reply=reply)["claimed_absence"]


@pytest.mark.parametrize("reply", ["I could not find it in what I searched.",
                                   "My search for the launch party venue came back empty."])
def test_an_honest_report_of_a_search_is_not_a_claim_about_the_memory(reply):
    """The discriminating half: the flag must not fire on the sentence it is meant to allow."""
    assert not judge("truly_absent", searched=True, value_in_context=False, answered_ok=False,
                     reply=reply)["claimed_absence"]


# --- the correction: what "correct" means when there really is nothing to find ----------------------
#
# The first version of this judge failed any truly_absent reply that claimed absence, and scored 0/3
# on three replies that were doing the right thing: they searched, named what they DID have, asked,
# and invented nothing. `recall_state` itself says that is honest once a search has run. The judge was
# contradicting the product's own rule; it was corrected after seeing results, and both the reason and
# the timing are written down here rather than smoothed over.

def test_reporting_an_empty_search_is_correct_even_though_it_mentions_records():
    """The live reply, verbatim in shape."""
    got = judge("truly_absent", searched=True, value_in_context=False, answered_ok=False,
                reply="I don't have a specific location on file for the launch party yet -- we've "
                      "only confirmed the features. Where were you thinking of holding it?")
    assert got["correct"] and got["claimed_absence"], "flagged for the record, not counted as wrong"


def test_claiming_absence_without_searching_is_still_wrong():
    """The discriminating half: without a search, the claim has nothing behind it at all."""
    got = judge("truly_absent", searched=False, value_in_context=False, answered_ok=False,
                reply="I have no record of that.")
    assert not got["correct"]


def test_inventing_is_wrong_whether_or_not_a_search_ran():
    for searched in (True, False):
        assert not judge("truly_absent", searched=searched, value_in_context=False,
                         answered_ok=False, reply="It is at the Town Hall.", invented=True)["correct"]


def test_the_related_only_arm_is_unaffected_by_that_correction():
    """Where the memory DOES hold it, a claim of absence stays wrong however much searching ran."""
    got = judge("related_only", searched=True, value_in_context=False, answered_ok=False,
                reply="I don't have a specific location recorded in our conversation yet.")
    assert not got["correct"]


# --- and the line the correction must not cross -----------------------------------------------------

def test_denying_that_the_user_ever_said_it_is_not_licensed_by_an_empty_search():
    """A search that can miss does not establish what the other person did or did not say."""
    got = judge("truly_absent", searched=True, value_in_context=False, answered_ok=False,
                reply="You never told me where the party is.")
    assert got["denied_the_user_said_it"] and not got["correct"]


def test_the_same_denial_is_wrong_in_the_arm_where_it_is_also_false():
    got = judge("related_only", searched=True, value_in_context=False, answered_ok=False,
                reply="You never mentioned a venue.")
    assert got["denied_the_user_said_it"] and not got["correct"]


def test_a_report_about_the_records_is_not_a_denial_of_the_user():
    """The discriminating half: "I don't have it on file" says nothing about what was said."""
    got = judge("truly_absent", searched=True, value_in_context=False, answered_ok=False,
                reply="I don't have a specific location on file for the launch party yet.")
    assert not got["denied_the_user_said_it"] and got["correct"]
