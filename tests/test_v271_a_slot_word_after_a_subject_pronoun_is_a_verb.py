"""95.69 (S4 on v6, 1/3) — in the unknown reader, a slot word right after a subject pronoun is a verb, not the asked
head.

"e a empresa onde eu trabalho, qual e?" resolved to the JOB slot ("trabalho" is a job token and the longer word),
so the offer rule looked for the job's tokens in the reply and never dropped the clause that named the empresa
and carried "Corvo"; the judge read Corvo asserted of the company. Positive: the question asks the company; the
clause naming the company and carrying another slot's value is an offer and is dropped. Preserve: "qual e o meu
trabalho?" still asks the job; a question naming no slot asks nothing.
"""
from __future__ import annotations

from hmgfu.unknowns import offered_for_unknown, unknown_asked, without_offers
from tests.test_v2_agent import make_agent

ASK = "e a empresa onde eu trabalho, qual e?"
REPLY = ("No momento, as informacoes que possuo sobre voce incluem o seu projeto principal (Corvo). Se voce puder me "
         "informar o nome da empresa, eu poderei registar essa informacao no desenvolvimento do projeto Corvo.")


def _engine(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    for t in ("My main project is called Corvo.", "I live in Chimoio.", "My dog is called Tufa."):
        engine.facts.apply_all(t, "user_explicit", session="s0")
    return engine


def test_the_company_is_asked_and_the_offer_is_dropped(tmp_path):
    """THE CONTRACT — fails before: the label is 'job' and no offer is seen."""
    engine = _engine(tmp_path)
    label = unknown_asked(engine, ASK)
    assert label == "company", label
    assert offered_for_unknown(engine, REPLY, label, "s1") == "Corvo"
    assert "nome da empresa" not in without_offers(engine, REPLY, label, "s1")   # the offending clause is dropped


def test_the_job_question_and_a_slotless_question_hold(tmp_path):
    engine = _engine(tmp_path)
    assert unknown_asked(engine, "qual e o meu trabalho?") == "job"
    assert unknown_asked(engine, "what is my job?") == "job"
    assert unknown_asked(engine, "what is the weather like?") is None
