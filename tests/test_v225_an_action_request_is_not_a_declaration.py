"""95.44 (X1 on v4, 0/3 both arms) — an action request is not a declaration about the user.

"Save the name of my main project into a workspace file called trabalho.txt." was read as a declaration:
the live nano mapper returned project.main = 'trabalho.txt' 3/3 and apply_all wrote it. Positive: an
imperative that asks for an action on a workspace artefact is not a declarative clause, so no producer
sees it (regex, mapper, spans all read declarative clauses only); the mapper's result is refused end to
end. Negative: a memory request without an artefact ("Remember that my main project is Orca") stays
declarative; a plain statement is unchanged; a question is still not declarative.
"""
from __future__ import annotations

from hmgfu.facts import FactStore
from hmgfu.fact_spans import apply_spans, extract_spans
from hmgfu.slots import map_to_slot
from hmgfu.speech_act import is_action_request
from hmgfu.utterance import declarative_clauses

X1 = "Save the name of my main project into a workspace file called trabalho.txt."
X1PT = "Escreve um ficheiro trabalho.txt com o nome do meu projeto principal."


def test_an_action_request_on_an_artefact_is_not_declarative():
    """THE CONTRACT — fails before: the imperative is an assert clause."""
    assert is_action_request(X1) and is_action_request(X1PT)
    assert declarative_clauses(X1) == [] and declarative_clauses(X1PT) == []


def test_the_mapper_result_for_the_imperative_is_refused_end_to_end(tmp_path):
    store = FactStore(str(tmp_path / "f.db"))
    store.apply_all("My main project is called Tamarin.", "user_explicit", session="s1")
    store.bind_mapper(lambda text: map_to_slot(text, lambda p, s: {"slot": "project.main", "value": "trabalho.txt", "op": "set"}))
    store.use_mapper = True
    assert store.apply_all(X1, "user_explicit", session="s1") == []
    fake = lambda p, s: {"facts": [{"attribute": "main project", "value": "trabalho.txt"}]}
    assert apply_spans(store, X1, "user_explicit", lambda t: extract_spans(t, fake)) == []
    assert [(f["key"], f["value"]) for f in store.active()] == [("project.main", "Tamarin")]


def test_memory_requests_statements_and_questions_are_unchanged():
    assert not is_action_request("Remember that my main project is Orca.")
    assert [c["text"] for c in declarative_clauses("Remember that my main project is Orca.")]
    assert [c["text"] for c in declarative_clauses("Kestrel is no longer the name of my main project.")]
    assert declarative_clauses("what is in project.txt?") == []
