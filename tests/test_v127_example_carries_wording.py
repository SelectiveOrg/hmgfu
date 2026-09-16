"""92.E5c — an example has to carry the WORDING that was confirmed, not only the value.

Why this test exists: the C/L comparison (3 repetitions, both headroom wordings, no leakage) found no
transfer, and the cause is visible in what an example actually contains. `_persist` stored
`snapshot["proposed_question"]` under `expression`, so a confirmed case remembered the question the
assistant had proposed -- or nothing at all on a teaching turn, where no question is ever asked -- and
never the sentence the user actually said. The block the router then sees is a value pair,
`ACME-7 = Atlas Control Mesh`, which says nothing about how a definition is phrased. Asking the model
to reuse an interpretation from that is asking it to generalise from evidence it was not given.

The tests discriminate rather than merely assert the new behaviour:

  * the wording that gets stored must be the USER's utterance, not the assistant's proposed question
    -- a question the assistant invented is not something a human confirmed, and letting it in through
    the same field is how a reflection would start authorising facts;
  * the block must still be empty outside `adapt`, since that is the one difference the C/L comparison
    is allowed to have;
  * an example carrying a user sentence stays advisory, because raw user text now reaches the prompt
    and it must remain data.
"""
from __future__ import annotations

from hmgfu.learning_state import LearningState, _persist, derive_example, example_is_advisory

CASE = {"id": "c1", "state": "committed", "revision": 4, "question_delivered": True,
        "teaching_was_explicit": True}
PROPOSALS = [{"kind": "domain_definition", "subject_ref": "ACME-7", "context_ref": "project terminology",
              "value": "Atlas Control Mesh", "relation": "definition.meaning",
              "evidence_refs": ["turn:1#30-48"]}]
COMMIT = {"action": "commit"}
SAID = "In this project, ACME-7 means Atlas Control Mesh."


def test_the_stored_wording_is_the_users_sentence():
    ex = derive_example(dict(CASE, expression=SAID), COMMIT, PROPOSALS)
    assert ex["expression"] == SAID, "the example must remember how the user phrased it"


def test_an_assistant_question_is_not_a_confirmed_wording():
    """The discriminating half: a proposed question must not be dressed up as the user's wording."""
    ex = derive_example(dict(CASE, expression="", question="Did you mean Atlas Control Mesh?"),
                        COMMIT, PROPOSALS)
    assert ex["expression"] != "Did you mean Atlas Control Mesh?" or ex["expression"] == "", (
        "a question the assistant proposed is not a wording a human confirmed")


def test_a_user_sentence_in_an_example_is_still_advisory():
    assert example_is_advisory(derive_example(dict(CASE, expression=SAID), COMMIT, PROPOSALS))


def test_persist_records_the_turn_text_not_the_question():
    """Straight at the defect: what the case table keeps after a teaching turn."""
    import json

    st = LearningState(":memory:")
    snapshot = {"session_id": "s1", "store_revision": 4, "pending_case": None,
                "proposed_question": "Could you confirm that?"}
    case_id = _persist(st, dict(COMMIT, handled_targets=["definition:x"]), snapshot, PROPOSALS,
                       "s1", 4, "1", text=SAID)
    row = st._db.execute("SELECT payload_json FROM learning_cases WHERE id=?", (case_id,)).fetchone()
    payload = json.loads(row[0])
    assert payload["expression"] == SAID
    assert payload["expression"] != snapshot["proposed_question"]
    st.close()


def test_the_rendered_block_shows_the_wording_and_only_in_adapt():
    """End of the chain: what the router is actually handed."""
    from hmgfu.sensitizer import Sensitizer

    class _Settings:
        def __init__(self, mode):
            self.mode = mode

        def get(self, key):
            return self.mode if key == "interactive_learning_mode" else None

    class _Facts:
        def __init__(self, db):
            self._db = db

    class _Engine:
        def __init__(self, mode, db):
            self.settings = _Settings(mode)
            self.facts = _Facts(db)

    st = LearningState(":memory:")
    _persist(st, dict(COMMIT, handled_targets=["definition:x"]),
             {"session_id": "s1", "store_revision": 4, "pending_case": None,
              "proposed_question": "Could you confirm that?"},
             PROPOSALS, "s1", 4, "1", text=SAID)

    sens = Sensitizer(client=None, enabled=False)
    sens.bind_learning_examples(_Engine("adapt", st._db))
    block = sens._learning_examples_text("DELTA-9 - Dynamic Ledger Transfer Adapter.")
    assert SAID in block, f"the confirmed wording must reach the router, got {block!r}"
    assert "Atlas Control Mesh" in block

    sens.bind_learning_examples(_Engine("confirm", st._db))
    assert sens._learning_examples_text("DELTA-9 - Dynamic Ledger Transfer Adapter.") == ""
    st.close()
