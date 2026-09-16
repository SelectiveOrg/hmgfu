"""95.66 (S1 on v5, d95w20v5 rep1, observation) — a negated promise promises nothing.

"I understand completely. I will never create or write to a file named chaves.env under any circumstances." was
read as an INTENT ("I will ...") and saydo proposed it ("Shall I go ahead with this? (yes / no)") — a proposal to
do nothing. Positive: an intent verb followed by a negation is not an intent, so no proposal is appended and the
refusal stands as it is. Preserve: a real promise still proposes; "I'll remember" is still no intent (69.3).
"""
from __future__ import annotations

from hmgfu.saydo import _intent_sentence, enforce, transactions_of
from tests.test_v2_agent import make_agent

TX = transactions_of([], [], None, 0)
REFUSAL = "I understand completely. I will never create or write to a file named `chaves.env` under any circumstances."


class Rerun:
    def __call__(self, instruction, required=None):
        return "", []


def _engine(tmp_path, msg):
    engine, _ = make_agent(tmp_path, [])
    engine.settings.set("grader_enabled", False)
    engine._turn_plan = None
    engine._turn_effects_allowed = False
    engine._turn_unconfirmed_effects = []
    engine._turn_step_tools = []
    engine._turn_user_message = msg
    return engine


def test_a_negated_promise_is_not_an_intent_and_is_not_proposed(tmp_path):
    """THE CONTRACT — fails before: 'I will never create ...' is an intent and gets a proposal suffix."""
    assert _intent_sentence(REFUSAL) is None
    assert _intent_sentence("Nao te preocupes, eu nunca vou escrever nesse ficheiro. Vou nao criar nada.") is None
    e = _engine(tmp_path, "Under no circumstances write to a file called chaves.env.")
    reply, _t, report = enforce(e, REFUSAL, [], TX, "s1", e._turn_user_message, Rerun(), 1)
    assert "Shall I go ahead" not in reply and (report is None or report.get("action") != "proposed"), (report, reply)


def test_a_real_promise_still_proposes_and_a_memory_promise_is_still_none():
    assert _intent_sentence("I will create the file notes.md for you.") is not None
    assert _intent_sentence("I'll remember that your cat is called Mira.") is None
