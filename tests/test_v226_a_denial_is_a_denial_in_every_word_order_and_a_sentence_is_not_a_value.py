"""95.43 + 95.45 (N6 on v4, 0/3 both arms) — a denial is a denial in every word order; a sentence is
not a value; a denial the ledger can see is asked about whatever the perceiver proposes.

"Kestrel is no longer the name of my main project." was written as project.main (the whole sentence
as the value): the perceiver proposed the sentence, the modality reader looked for a negation only
before the fragment, and the slot write took a sentence for a name. Positive: the negated copula after
the subject negates it (EN and PT); a whole-sentence value is refused; the held value under the denial
is derived as a negated proposal so the protocol asks and writes nothing, and "Sure, go ahead" still
writes nothing. Negative: "Marlin is my main project, not Orca" keeps Marlin asserted; a real new value
still commits; a message that denies nothing derives nothing.
"""
from __future__ import annotations

from hmgfu.learning_apply import DEFINITION_RELATION, ledger_grounded_denials
from hmgfu.learning_apply import _is_the_message
from hmgfu.learning_evidence import _modality_of
from hmgfu.learning_state import run_learning_turn
from tests.test_v2_agent import make_agent

DENY = "Kestrel is no longer the name of my main project."
DENY_PT = "O Kestrel ja nao e o nome do meu projeto principal."


class Q:
    def __init__(self, envelope=None):
        self.extraction = {"memory_update": envelope} if envelope is not None else {}


def _env(text, value, subject):
    start = text.index(value) if value in text else 0
    return {"feedback": "none", "scope": "memory", "ambiguity": "none", "target_case_id": None,
            "proposals": [{"kind": "domain_definition", "subject_ref": subject, "relation": DEFINITION_RELATION,
                           "value": value, "evidence_refs": [f"turn:1#{start}-{start + len(value)}"]}]}


def _engine(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    engine.settings.set("interactive_learning_mode", "confirm")
    engine.facts.apply_all("My main project is called Kestrel.", "user_explicit", session="s0")
    return engine


def _project(engine):
    return [(f["value"]) for f in engine.facts.active() if f["key"] == "project.main"]


def test_a_negated_copula_after_the_subject_negates_it():
    """THE CONTRACT (modality) — fails before: 'no longer' after the fragment is not seen."""
    assert _modality_of("Kestrel", DENY) == "negated"
    assert _modality_of("Kestrel", DENY_PT) == "negated"
    assert _modality_of("Marlin", "Marlin is my main project, not Orca.") == "assert"
    assert _modality_of("Orca", "My main project is called Orca now.") == "assert"


def test_a_sentence_is_not_a_value_and_the_ledger_derives_the_denial(tmp_path):
    assert _is_the_message(DENY, DENY) and not _is_the_message("Kestrel", DENY)
    e = _engine(tmp_path)
    got = ledger_grounded_denials(e.facts, DENY)
    assert got and got[0]["relation"] == "project.main" and got[0]["value"] == "Kestrel" and got[0].get("denial")
    assert ledger_grounded_denials(e.facts, "My main project is called Kestrel, as I said.") == []


def test_the_denial_is_asked_about_and_nothing_is_written_even_when_the_perceiver_proposes_the_sentence(tmp_path):
    """THE CONTRACT (protocol) — fails before: the sentence is committed as project.main."""
    e = _engine(tmp_path)
    out = run_learning_turn(e, "s1", DENY, Q(_env(DENY, DENY, subject="main project")), turn_id="1")
    assert out["decision"]["action"] == "ask" and "What is it now?" in (out["decision"].get("question") or ""), out["decision"]
    assert _project(e) == ["Kestrel"]
    yes = run_learning_turn(e, "s1", "Sure, go ahead.", Q({}), turn_id="2")
    assert yes["decision"]["action"] != "commit" and _project(e) == ["Kestrel"], (yes["decision"], _project(e))


def test_a_real_new_value_still_commits(tmp_path):
    e = _engine(tmp_path)
    text = "My main project is called Tamarin now."
    out = run_learning_turn(e, "s1", text, Q(_env(text, "Tamarin", subject="main project")), turn_id="1")
    assert out["decision"]["action"] == "commit" and _project(e) == ["Tamarin"], (out["decision"], _project(e))


def test_a_rename_that_states_the_new_value_derives_no_denial_and_the_subject_is_the_word_used(tmp_path):
    """95.45b (caught offline before wave 14): a correction with a replacement is not a denial; the derived
    subject is the attribute word the message uses ("gata"), so the evidence binding holds."""
    e = _engine(tmp_path)
    e.facts.apply_all("My cat is called Sol.", "user_explicit", session="s0")
    assert ledger_grounded_denials(e.facts, "Correcao: a minha gata ja nao se chama Sol, chama-se Lua.") == []
    got = ledger_grounded_denials(e.facts, "A minha gata ja nao se chama Sol.")
    assert got and got[0]["subject_ref"] == "gata" and got[0]["value"] == "Sol"

