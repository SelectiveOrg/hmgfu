"""Phase 91.X2 — the subject of "<value> is my <attr>" is the subject, not the connector before it.

`pet.dog.name = 'but'` entered the user's real ledger at 20:36:38 from

    "but you should know that green is my dog also"

Reproduced at the detector and attributed to the baseline 0c65488 -- pre-existing, not a regression
of 91.V/W. The investigation of subject -> relation -> value found three separate defects, and the
reported sentence is only the one that got through:

  * the VALUE is any run of up to six tokens ending before "is my", so a leading discourse connector
    is swallowed into it -- "but green", "and blue". For a NAME slot the name-shape gate rejects the
    two-token result, but for an open slot nothing does: `pref.color = 'and blue'` is written.
  * the ATTRIBUTE absorbs a trailing adverb -- "dog also" normalises to `pet.dog.name` silently.
  * a single lowercase token passes the name-shape gate (`_looks_like_name` returns True for any
    non-numeric single token), which is why 'but' -- and nothing longer -- reached the ledger.

The contract asserted here is grammatical, not a list of sentences: a discourse connector opening a
clause is not part of the subject; an adverb closing a clause is not part of the attribute; and a
function word is never a name.
"""

from __future__ import annotations

import pytest

from hmgfu.fact_detect import detect_facts
from hmgfu.slots import normalise_key

# (sentence, expected {normalised key: value}) -- {} means the utterance must write nothing
CASES = [
    # the subject survives a leading connector, EN and PT
    ("green is my dog", {"pet.dog.name": "green"}),
    ("but green is my dog", {"pet.dog.name": "green"}),
    ("and blue is my cat", {"pet.cat.name": "blue"}),
    ("so rex is my dog", {"pet.dog.name": "rex"}),
    ("but teal is my favorite color", {"pref.color": "teal"}),
    ("and blue is my favourite colour", {"pref.color": "blue"}),
    # a trailing adverb belongs to the clause, not to the attribute
    ("green is my dog also", {"pet.dog.name": "green"}),
    ("rex is my dog too", {"pet.dog.name": "rex"}),
    # the reported sentence, whole
    ("but you should know that green is my dog also", {"pet.dog.name": "green"}),
    ("you should know that green is my dog", {"pet.dog.name": "green"}),
    # negatives: nothing may be written
    ("but is my dog's name", {}),
    ("and that is my dog", {}),
    ("green is not my dog", {}),
    ("but", {}),
    ("and", {}),
    ("so", {}),
]

# A connector must never end up as a NAME, whatever route produced it. Kept separate because it is
# the defence in depth: even a mould this file does not know about must not write one.
CONNECTORS = ["but", "and", "so", "or", "then", "also", "though", "however",
              "mas", "e", "ou", "porem", "contudo", "entao", "tambem"]


def _written(text: str) -> dict:
    return {normalise_key(d["key"]): d.get("value") for d in detect_facts(text) if d.get("value")}


@pytest.mark.parametrize("text,expected", CASES)
def test_subject_relation_value_attribution(text, expected):
    assert _written(text) == expected


@pytest.mark.parametrize("word", CONNECTORS)
def test_a_connector_is_never_a_name(word):
    from hmgfu.fact_detect import name_value_ok
    assert not name_value_ok("pet.dog.name", word), f"{word!r} was accepted as a pet name"
    assert not name_value_ok("identity.name", word), f"{word!r} was accepted as a person's name"
