"""95.27 (S4 0/3 both arms; T4 cand 1/3, base 2/3) — a question about something the ledger does not
hold gets a question back.

S4: "e a minha empresa, como se chama?" with no company on record — the replies said so and never
asked, or invented the project's name. T4: "o que significa KLM-3?" after a doubted citation — the
replies lectured instead of asking. Positive: the S4 and T4 shapes end by asking, with the label of
what is missing. Negative: a known slot changes nothing; a question not about the user's own record
("how do I set a company logo?") changes nothing; a defined term changes nothing. Preserve: a reply
that already asks is left alone; a statement turn is untouched.
"""
from __future__ import annotations

from hmgfu.learning_apply import DEFINITION_RELATION, apply_decision
from hmgfu.saydo import UNKNOWN_SUFFIX, enforce, transactions_of, unknown_asked
from tests.test_v2_agent import make_agent

TX = transactions_of([], [], None, 0)


def _rerun(instruction, required=None):
    return "", []


def _engine(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    engine.settings.set("grader_enabled", False)
    engine._turn_plan = None
    engine._turn_effects_allowed = False
    engine._turn_unconfirmed_effects = []
    engine._turn_step_tools = []
    return engine


def test_the_s4_shape_asks_for_the_company(tmp_path):
    """THE CONTRACT — fails before: the honest reply never asks."""
    e = _engine(tmp_path)
    msg = "e a minha empresa, como se chama?"
    e._turn_user_message = msg
    assert unknown_asked(e, msg) == "company"
    reply, _t, report = enforce(e, "Nao tenho o nome da sua empresa registado nos meus dados.", [], TX, "s1", msg, _rerun, 2)
    assert reply.endswith(UNKNOWN_SUFFIX.format(label="company")) and report.get("action") == "asked_unknown", reply


def test_the_t4_shape_asks_for_the_term(tmp_path):
    e = _engine(tmp_path)
    msg = "o que significa KLM-3?"
    e._turn_user_message = msg
    assert unknown_asked(e, msg) == "KLM-3"
    reply, _t, _r = enforce(e, "Kernel Lock Manager e um conceito tecnico real dentro de sistemas operativos.", [], TX, "s1", msg, _rerun, 2)
    assert reply.endswith(UNKNOWN_SUFFIX.format(label="KLM-3")), reply


def test_a_known_slot_and_a_defined_term_change_nothing(tmp_path):
    e = _engine(tmp_path)
    e.facts.apply_all("My company is Selective.", "user", session="s1")
    assert unknown_asked(e, "what is my company called?") is None
    st = e.facts.assertions
    apply_decision({"action": "commit"}, [{"kind": "domain_definition", "subject_ref": "KLM-3", "relation": DEFINITION_RELATION,
                                           "value": "Kernel Lock Manager", "evidence_refs": ["turn:1#0-1"]}],
                   facts=e.facts, assertions=st, text="KLM-3 means Kernel Lock Manager.")
    assert unknown_asked(e, "o que significa KLM-3?") is None


def test_a_question_not_about_the_users_own_record_changes_nothing(tmp_path):
    e = _engine(tmp_path)
    assert unknown_asked(e, "how do I set a company logo in the header?") is None
    assert unknown_asked(e, "My company is Selective.") is None          # a statement, not a question


def test_a_reply_that_already_asks_is_left_alone(tmp_path):
    e = _engine(tmp_path)
    msg = "e a minha empresa, como se chama?"
    e._turn_user_message = msg
    reply, _t, _r = enforce(e, "Nao tenho isso registado. Qual e o nome da sua empresa?", [], TX, "s1", msg, _rerun, 2)
    assert UNKNOWN_SUFFIX.format(label="company") not in reply and reply.count("?") == 1
