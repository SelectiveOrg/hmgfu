"""95.59 (T4 on v4, d95w16v4 rep3) — what the answer STATES is judged before what it promises.

"o que quer dizer PXD-4?" with "Packet Drop Daemon" pending (a doubted citation the protocol is asking
about): the reply "PXD-4 significa **Packet Drop Daemon**. (Vou manter esse termo em mente ...)" carried an
intent, so saydo's intent branch returned "proposed" and the pending value was published — the
unknown-offer rule (95.27/95.35/95.48) fires on that reply in isolation but ran last. Positive: the
offer is dropped and the unknown is asked, intent or not. Preserve: an intent with no unknown asked
still proposes; a clean answer to the unknown is untouched.
"""
from __future__ import annotations

from hmgfu.learning_state import run_learning_turn
from hmgfu.saydo import enforce, transactions_of
from tests.test_v2_agent import make_agent

TX = transactions_of([], [], None, 0)
T4 = "Segundo o Rui, PXD-4 quer dizer Packet Drop Daemon, mas ele costuma enganar-se nestas siglas."
ENV = {"ambiguity": "unsupported", "feedback": "none", "scope": "unclear",
       "proposals": [{"kind": "domain_definition", "value": "Packet Drop Daemon", "subject_ref": "PXD-4",
                      "evidence_refs": ["turn:1#32-50"]}]}
ASK = "o que quer dizer PXD-4?"
LEAK = "PXD-4 significa **Packet Drop Daemon**.   (Vou manter esse termo em mente para quando o Rui falar disso.)"
CLEAN = "Nao tenho o significado de PXD-4 registado. O que quer dizer?"


class Q:
    def __init__(self, env):
        self.extraction = {"memory_update": env}


class Rerun:
    def __init__(self, reply):
        self.reply, self.calls = reply, []

    def __call__(self, instruction, required=None):
        self.calls.append(instruction)
        return self.reply, []


def _engine(tmp_path, msg):
    engine, _ = make_agent(tmp_path, [])
    engine.settings.set("grader_enabled", False)
    engine.settings.set("interactive_learning_mode", "confirm")
    engine._turn_plan = None
    engine._turn_effects_allowed = False
    engine._turn_unconfirmed_effects = []
    engine._turn_step_tools = []
    engine._turn_user_message = msg
    return engine


def test_the_pending_value_is_dropped_even_when_the_reply_also_promises(tmp_path):
    """THE CONTRACT — fails before: the intent branch returns 'proposed' with the value published."""
    e = _engine(tmp_path, ASK)
    assert run_learning_turn(e, "s1", T4, Q(ENV), turn_id="1")["decision"]["action"] == "ask"
    reply, _t, report = enforce(e, LEAK, [], TX, "s1", ASK, Rerun(LEAK), 2)
    assert "Packet Drop Daemon" not in reply, reply
    assert (report or {}).get("action") == "asked_unknown" and "?" in reply[-160:], (report, reply)


def test_a_promise_with_no_unknown_still_proposes_and_a_clean_answer_is_untouched(tmp_path):
    e = _engine(tmp_path, "Podes tratar disso?")
    reply, _t, report = enforce(e, "Vou tratar disso agora.", [], TX, "s1", "Podes tratar disso?", Rerun("Vou tratar disso agora."), 2)
    assert (report or {}).get("action") == "proposed", report
    e2 = _engine(tmp_path, ASK)
    assert run_learning_turn(e2, "s1", T4, Q(ENV), turn_id="1")["decision"]["action"] == "ask"
    reply, _t, report = enforce(e2, CLEAN, [], TX, "s1", ASK, Rerun(CLEAN), 2)
    assert reply == CLEAN and (report is None or report.get("action") != "asked_unknown"), (report, reply)
