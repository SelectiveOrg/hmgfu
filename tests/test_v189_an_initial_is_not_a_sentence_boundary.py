"""95.14 (L5 c95c rep1) — an initial is not a sentence boundary.

The ledger wrote `identity.name = teodoro h. ferreira` and the reply said "Your name is teodoro h.
ferreira." — and the judge scored it "the value is not asserted of that subject", because
`sentence_modalities` (the ledger's own splitter, reused by the answer oracle) cuts after every period:
"Your name is teodoro h." + "ferreira.". One structural guard on both splitters: a period that closes a
single-letter word is an initial. Positive: the name stays one clause and the oracle reads it; negative:
two real sentences still split; variant: the teaching sentence keeps its full name in the first clause;
preserve: the contrastive split ("but") is untouched.
"""
from __future__ import annotations

from hmgfu.utterance import declarative_clauses, sentence_modalities
from scripts.answer_oracle import answered


def test_the_reply_with_an_initial_is_one_clause_and_the_oracle_reads_it():
    """THE CONTRACT — fails before: 'ferreira.' lands in a clause with no subject."""
    clauses = [c["text"] for c in sentence_modalities("Your name is teodoro h. ferreira.")]
    assert clauses == ["Your name is teodoro h. ferreira."], clauses
    assert answered("Your name is teodoro h. ferreira.", subject="name", value="ferreira")["ok"]


def test_two_real_sentences_still_split():
    assert [c["text"] for c in sentence_modalities("I am here. You are there.")] == ["I am here.", "You are there."]


def test_the_teaching_sentence_keeps_the_whole_name_in_its_clause():
    first = declarative_clauses("my real name is actually teodoro h. ferreira. and i want you to start calling me with that name for now on")[0]["text"]
    assert "teodoro h. ferreira" in first, first


def test_a_capitalised_initial_is_the_same_case():
    clauses = [c["text"] for c in sentence_modalities("My name is Teodoro H. Ferreira. I live in Valencia.")]
    assert clauses == ["My name is Teodoro H. Ferreira.", "I live in Valencia."], clauses


def test_a_digit_before_the_period_is_not_an_initial():
    """T3's worked example (v167): "BETA-9." closes a sentence."""
    texts = [c["text"] for c in sentence_modalities("I have nothing on BETA-9. ACME-7 means Atlas Control Mesh.")]
    assert texts == ["I have nothing on BETA-9.", "ACME-7 means Atlas Control Mesh."], texts


def test_the_contrastive_split_is_untouched():
    texts = [c["text"] for c in sentence_modalities("I liked tea but now I prefer coffee.")]
    assert len(texts) == 2 and texts[1].startswith("but"), texts
