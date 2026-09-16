"""95.35 (S4, d95w9 rep2) — a value the ledger holds for another attribute is not put forward for the
unknown one.

"e a minha empresa, como se chama?" with no company on record and project.main = Marlin: the reply
offered Marlin as a possible company name ('Caso "Marlin" seja o nome da sua empresa ...') beside the
95.27 question. Positive: the offer is detected and the single re-ask replaces the reply with one that
offers nothing, then asks. Fallback (95.35b): if the re-ask still carries one, the offending clause is dropped and the suffix asks.
Negative: a clause that names the value's OWN attribute ("o seu projeto principal é o Marlin") is not
an offer and nothing is re-asked. Preserve: no held values, nothing to offer.
"""
from __future__ import annotations

from hmgfu.saydo import UNKNOWN_SUFFIX, enforce, offered_for_unknown, transactions_of, without_offers
from tests.test_v2_agent import make_agent

TX = transactions_of([], [], None, 0)
MSG = "e a minha empresa, como se chama?"
GUESS = 'Caso "Marlin" seja o nome da sua empresa ou se tiver outra estrutura, informe o nome exato agora.'
CLEAN = "Nao tenho o nome da sua empresa registado nos meus dados."
HONEST = "O seu projeto principal e o Marlin. O nome da sua empresa nao consta nos meus registos."


def _engine(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    engine.settings.set("grader_enabled", False)
    engine._turn_plan = None
    engine._turn_effects_allowed = False
    engine._turn_unconfirmed_effects = []
    engine._turn_step_tools = []
    engine._turn_user_message = MSG
    engine.facts.apply_all("My main project is Marlin.", "user", session="s1")
    assert [f["value"] for f in engine.facts.active() if f["key"] == "project.main"] == ["Marlin"]
    return engine


class Rerun:
    def __init__(self, reply):
        self.reply, self.calls = reply, []

    def __call__(self, instruction, required=None):
        self.calls.append(instruction)
        return self.reply, []


def test_the_offer_is_detected_and_the_re_ask_replaces_it(tmp_path):
    """THE CONTRACT — fails before: the guess is published beside the question."""
    e = _engine(tmp_path)
    assert offered_for_unknown(e, GUESS, "company") == "Marlin"
    assert offered_for_unknown(e, HONEST, "company") is None
    rerun = Rerun(CLEAN)
    reply, _t, report = enforce(e, GUESS, [], TX, "s1", MSG, rerun, 2)
    assert len(rerun.calls) == 1 and "company" in rerun.calls[0]
    assert "Marlin" not in reply and reply.endswith(UNKNOWN_SUFFIX.format(label="company")), reply
    assert report.get("action") == "asked_unknown"


def test_a_re_ask_that_offers_again_drops_the_offer_and_the_suffix_asks(tmp_path):
    """95.35b: the offending clause is not published; the guess is a single clause, so only the suffix remains."""
    e = _engine(tmp_path)
    rerun = Rerun(GUESS)
    reply, _t, _r = enforce(e, GUESS, [], TX, "s1", MSG, rerun, 2)
    assert len(rerun.calls) == 1 and "Marlin" not in reply and reply.endswith(UNKNOWN_SUFFIX.format(label="company").strip()), reply


def test_naming_the_values_own_attribute_is_not_an_offer(tmp_path):
    e = _engine(tmp_path)
    rerun = Rerun(CLEAN)
    reply, _t, _r = enforce(e, HONEST, [], TX, "s1", MSG, rerun, 2)
    assert rerun.calls == [] and reply.startswith(HONEST) and reply.endswith(UNKNOWN_SUFFIX.format(label="company"))


def test_nothing_held_means_nothing_offered(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    assert offered_for_unknown(engine, GUESS, "company") is None
    assert offered_for_unknown(engine, GUESS, "KLM-3") is None           # a term, not a slot


DRAGGED = ("Atualmente, nao tenho o nome da sua empresa registado. Para garantir um suporte contextualizado, "
           "especialmente quando discutirmos os detalhes do projeto Marlin, seria util se me informasse o nome da sua empresa. "
           "Assim que me fornecer essa informacao, poderei guarda-la.")


def test_a_value_dragged_in_beside_its_own_attribute_is_still_not_published(tmp_path):
    """95.35b — fails before: "projeto Marlin" in the clause about the company was exempt (d95w10 rep2)."""
    e = _engine(tmp_path)
    assert offered_for_unknown(e, DRAGGED, "company") == "Marlin"
    rerun = Rerun(DRAGGED)                                    # the re-ask drags it in again
    reply, _t, _r = enforce(e, DRAGGED, [], TX, "s1", MSG, rerun, 2)
    assert len(rerun.calls) == 1
    assert "Marlin" not in reply and "nao tenho o nome da sua empresa registado" in reply, reply
    assert reply.endswith(UNKNOWN_SUFFIX.format(label="company"))
    assert without_offers(e, DRAGGED, "company").startswith("Atualmente") and "guarda-la." in without_offers(e, DRAGGED, "company")
