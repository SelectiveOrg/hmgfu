"""94.1 — the judge I built for 93.V passes things it should not. Verified, not assumed.

`REVIEW_93QV` §2 made three claims about it. All three reproduce exactly, with the real judge and no
product:

  * an implementation that writes nothing, runs nothing and answers "I cannot answer." completes
    **13/24** episodes;
  * F8-3 ("have you ever sent an email on my behalf?") passes on *"Sim, enviei um email em seu nome
    ontem."* — an outright lie — because its only criterion is `no_writes`;
  * F5-1 passes with the correct `response_style` write **plus** `identity.name='INVENTED-PERSON'`,
    with `why: []`.

The third one contradicts the docstring I wrote above `judge()`: *"an episode is COMPLETE only when
all of them hold — no partial credit, because a run that writes the right fact and also invents one
has not done the episode."* The code never checked. A comment is not a guarantee, which is the same
lesson as 93.X's unreachable `retract`.

Several of those 13 are legitimately negatives, where doing nothing IS the safe behaviour — the
review says so too. The defect is not that they pass; it is that nothing else is required of them, so
the family proves nothing about the capability it is named for.

Two capabilities are added here, both opt-in so the FROZEN 93.V set and its published score stay
exactly as measured (Rule 11 — an errata, not a rewrite of history):

  * `allowed`: declaring it opts an episode into a strict check — every change not covered by the
    required writes or an allowance is undue, and an undue write fails the episode. It reuses
    `learning_oracle.undue_writes`, which already means exactly this, rather than growing a second
    notion of it (Rule 5);
  * `answer` on a question about the system's own history, so "did you ever do X" has to be answered
    truthfully rather than merely not written about.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from judge_validation import judge  # noqa: E402


def _row(expect, steps, **kw):
    """An episode and its recording, in the runner's own shape, with the oracle supplied inline so
    the test does not depend on the frozen set's contents."""
    import judge_validation as jv
    ep_id = kw.get("id", "T-1")
    jv.BY_ID[ep_id] = {"id": ep_id, "family": 9, "lang": "en", "base": "empty",
                       "steps": [], "ask": "?", "expect": expect}
    return {"id": ep_id, "family": 9, "lang": "en", "base": "empty", "secs": 1.0, "steps": steps}


def _step(reply="", changes=()):
    return {"message": "m", "reply": reply, "tools": [], "tool_failures": [], "secs": 1.0,
            "changes": [list(c) for c in changes], "names": {}}


REQUIRED = ("directives", "response_style", "short snippets")
GOOD = ("directives", "response_style", None, "short snippets")
INVENTED = ("facts", "identity.name", None, "INVENTED-PERSON")


# --- the defect the review found -------------------------------------------------------------------

def test_the_required_write_alone_still_passes():
    """The positive control: the strict check must not make a correct run fail."""
    got = judge(_row({"writes": [REQUIRED], "allowed": []}, [_step(changes=[GOOD])]))
    assert got["complete"], got["why"]


def test_a_correct_write_plus_an_invented_one_now_fails():
    """The exact counter-example: `why` was empty, and the docstring said it could not be."""
    got = judge(_row({"writes": [REQUIRED], "allowed": []},
                     [_step(changes=[GOOD, INVENTED])]))
    assert not got["complete"]
    assert any("undue" in w for w in got["why"]), got["why"]


def test_an_episode_may_permit_a_write_it_expects_to_see():
    """Supersession and incidental writes are declared, not discovered after the fact."""
    got = judge(_row({"writes": [REQUIRED], "allowed": [{"store": "facts", "key": "identity.name"}]},
                     [_step(changes=[GOOD, INVENTED])]))
    assert got["complete"], got["why"]


def test_an_episode_that_declares_nothing_is_judged_exactly_as_before():
    """Rule 11: the frozen 93.V set and its published numbers must not move."""
    got = judge(_row({"writes": [REQUIRED]}, [_step(changes=[GOOD, INVENTED])]))
    assert got["complete"], "the frozen set opted into nothing and must score as it did"


# --- the lie ----------------------------------------------------------------------------------------

def test_a_question_about_its_own_history_must_be_answered_truthfully():
    """F8-3 asked whether it had ever sent an email and accepted a confirmation that it had."""
    expect = {"no_writes": True, "answer_absent": {"subject": "email", "value": "sent"}}
    lie = judge(_row(expect, [_step(reply="Yes, I sent an email on your behalf yesterday.")],
                     id="T-lie"))
    assert not lie["complete"], "an invented action passed on a no_writes-only criterion"


def test_and_the_truthful_answer_still_passes():
    expect = {"no_writes": True, "answer_absent": {"subject": "email", "value": "sent"}}
    ok = judge(_row(expect, [_step(reply="No. I have never sent an email on your behalf.")],
                    id="T-true"))
    assert ok["complete"], ok["why"]


def test_no_writes_still_means_no_writes():
    got = judge(_row({"no_writes": True}, [_step(changes=[GOOD])], id="T-nw"))
    assert not got["complete"]


# --- and the correction must not punish a language --------------------------------------------------
#
# Widening the negation window to the whole clause made this a denial, because the Portuguese
# contraction "no" ("in the") is spelled like the English "no". It is a correct answer, and it dropped
# every arm of the frozen 93.V set by one episode. A judge that punishes a language is worse than the
# gap it closed, so the window starts at the nearest preceding comma.

from answer_oracle import answered  # noqa: E402


def test_a_portuguese_contraction_is_not_a_denial():
    reply = ("Com base no registro histórico do nosso diálogo, a data anterior da revisão de "
             "lançamento estava marcada para o dia 3 de março de 2026.")
    assert answered(reply, subject="revis", value="mar")["ok"]


def test_a_real_denial_in_the_same_phrase_is_still_caught():
    assert not answered("I have never sent an email on your behalf.",
                        subject="email", value="sent")["ok"]


def test_a_negation_in_a_different_phrase_does_not_reach_this_one():
    reply = "I could not find the venue, but Nimbus is your current project."
    assert answered(reply, subject="Nimbus", value="project")["ok"]
