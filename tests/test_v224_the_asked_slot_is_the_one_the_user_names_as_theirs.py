"""95.42 (S4 on v4, 0/3 both arms) — the slot the user asks about is the one they name as theirs; a held
slot answers only itself.

"e onde e que eu trabalho, qual e a minha empresa?" matched identity.location ("onde", HELD),
identity.job ("trabalho") and identity.company ("empresa"); 95.27's exemption "a held match answers
itself" was scoped to ANY matched slot, so the held location silenced the two unknown ones and the
honest reply never asked. Positive: the v4 wording asks for the company; a message with no possessive
asks for the most specific unknown match even when a weaker held match exists. Preserve: the v3
wording still asks for the company; a held company ("what is my company called?") still answers
itself; a question not about the user changes nothing.
"""
from __future__ import annotations

from hmgfu.unknowns import unknown_asked
from tests.test_v2_agent import make_agent

PRIOR = ["My main project is called Kestrel.", "I live in Quelimane.", "My dog is called Faro."]


def _engine(tmp_path, held=PRIOR):
    engine, _ = make_agent(tmp_path, [])
    for t in held:
        engine.facts.apply_all(t, "user_explicit", session="s0")
    return engine


def test_the_v4_wording_asks_for_the_company_the_user_names_as_theirs(tmp_path):
    """THE CONTRACT — fails before: the held location ("onde") silences the ask."""
    e = _engine(tmp_path)
    assert unknown_asked(e, "e onde e que eu trabalho, qual e a minha empresa?") == "company"


def test_without_a_possessive_the_most_specific_unknown_match_is_asked_for(tmp_path):
    e = _engine(tmp_path)
    assert unknown_asked(e, "onde e que eu trabalho?") == "job"


def test_the_v3_wording_and_the_held_exemption_are_unchanged(tmp_path):
    e = _engine(tmp_path)
    assert unknown_asked(e, "e a minha empresa, como se chama?") == "company"
    e.facts.apply_all("My company is Selective.", "user_explicit", session="s0")
    assert unknown_asked(e, "what is my company called?") is None
    assert unknown_asked(e, "how do I set a company logo in the header?") is None
