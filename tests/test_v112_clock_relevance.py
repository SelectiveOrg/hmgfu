"""Phase 91.X1 — the clock may ground an answer only when the turn ASKED for it.

Observed on a throwaway base with the LIVE router (outputs/evidence_91_X1_attribution.txt): the
router marks `runtime_context_sufficient=true` with the full clock key set for turns that merely
MENTION or COMPLAIN about the time. `ground_reply` then re-asked the model to answer "using ONLY
these exact values", and the user's own complaint -- "why are you saying the time? you could just
ask me what do i mean" -- was answered with the clock and nothing else.

The gate verified that the clock was SUFFICIENT and that the reply did not carry it. It never
verified that the clock was RELEVANT: that the turn requested a current date/time at all.
Mentioning, denying or complaining about the time is not asking for it.

The contract asserted here is general and act-based, so it holds in any language and for sentences
that appear nowhere in this file: the override fires for a turn that asks (question/instruction, or
an explicit action request) and stays out of the way otherwise.
"""

from __future__ import annotations

from hmgfu.models import QueryPoint
from hmgfu.runtime_context import RuntimeContext, ground_reply
from tests.test_v2_agent import make_agent

RT = RuntimeContext(now_local="2026-07-05T18:30:00+02:00", now_utc="2026-07-05T16:30:00+00:00",
                    local_date="2026-07-05", local_time="18:30:00",
                    timezone_name="SAST", utc_offset="+02:00", unix_seconds=1783269000)
KEYS = ["now_local", "now_utc", "local_date", "local_time", "timezone_name", "utc_offset"]

# Every case carries the classification the LIVE router produced for that shape of turn, measured on
# a 19-case labelled battery (scripts/diag_clock_router.py, outputs/evidence_91_X1_router.txt).
# Two entries here were written from assumption first and CORRECTED by that measurement: an
# imperative request ("diz-me a hora local") is filed as `question`, not `instruction`, and
# "preciso de saber a hora exata agora" as `question`, not `statement`+action. The contract narrowed
# accordingly -- it is the measurement that chose it, not the other way round.
NOT_A_REQUEST = [
    # (act, action_requested, message) -- complaint, mention, negation, prohibition, other sense; PT and EN
    ("feedback", False, "why are you saying the time? you could just ask me what do i mean"),
    ("feedback", False, "porque estas sempre a dizer as horas? nao te perguntei isso"),
    ("statement", False, "I hate it when apps show me the time I did not ask for"),
    ("feedback", False, "eu nao perguntei as horas"),
    ("statement", False, "but babys is also babys"),
    ("statement", False, "the time we spent together was great"),
    # a prohibition is an instruction ABOUT the clock, not a request FOR it. The router keeps calling
    # it sufficient (it flipped between runs), so the gate must refuse it on its own.
    ("instruction", False, "never show me the time again"),
    ("instruction", False, "nao me digas mais as horas"),
    # action_requested is not evidence of a clock request: it means an action is wanted, and
    # tool_points raises it after the router runs -- observed True for a complaint in the live capture.
    ("statement", True, "I hate it when apps show me the time I did not ask for"),
    ("feedback", True, "why are you saying the time?"),
]

A_REQUEST = [
    ("question", False, "que horas sao?"),
    ("question", False, "what time is it?"),
    ("question", False, "diz-me a hora local, por favor"),      # imperative, filed as a question
    ("question", False, "give me the current time"),
    ("question", False, "me diga a hora agora"),
    ("question", False, "preciso de saber a hora exata agora"),
    ("question", True, "what time is it, and what is my dog called?"),   # mixed: still asks
]

UNGROUNDED = "Fair point, I will just ask you what you mean instead of guessing."


def _q(act: str, action: bool, freshness: str = "") -> QueryPoint:
    # 91.Y5: `freshness` is the router's own second signal and carries the MEASURED value for each
    # shape -- "current" for a request, "none" for a mention, complaint or prohibition.
    return QueryPoint(conversation_act=act, action_requested=action,
                      freshness=freshness or ("current" if act == "question" else "none"),
                      runtime_context_sufficient=True, runtime_context_keys=list(KEYS))


def test_clock_does_not_override_a_turn_that_did_not_ask_for_it(tmp_path):
    """Mentioning, denying or complaining about the time must never trigger the re-ask."""
    engine, fake = make_agent(tmp_path, [])
    for act, action, msg in NOT_A_REQUEST:
        out = ground_reply(engine, UNGROUNDED, msg, _q(act, action), RT, "sys")
        assert out == UNGROUNDED, f"the clock overwrote the answer to {msg!r}"
    assert fake.calls == [], "the gate re-asked the model for a turn that never requested the time"


def test_a_question_that_does_not_want_a_current_value_is_left_alone(tmp_path):
    """91.Y5: the act says the turn asks; `freshness` says WHAT it asks for. A question the router
    wrongly marked clock-sufficient, but which wants no current value, must not be overwritten."""
    engine, fake = make_agent(tmp_path, [])
    out = ground_reply(engine, UNGROUNDED, "why did you mention the time earlier?",
                       _q("question", False, freshness="none"), RT, "sys")
    assert out == UNGROUNDED and fake.calls == []


def test_clock_still_grounds_a_real_request(tmp_path):
    """The Phase 57 backstop is preserved: a genuine request whose answer misses the value is fixed."""
    engine, fake = make_agent(tmp_path, [{"content": "It is 18:30:00 (+02:00).", "tool_calls": []}
                                         for _ in A_REQUEST])
    for act, action, msg in A_REQUEST:
        out = ground_reply(engine, UNGROUNDED, msg, _q(act, action), RT, "sys")
        assert out == "It is 18:30:00 (+02:00).", f"the backstop stopped grounding {msg!r}"
    assert len(fake.calls) == len(A_REQUEST)
