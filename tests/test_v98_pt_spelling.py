"""Phase 90.M4 — European/Brazilian Portuguese spelling is a NORMALISATION, not a synonym list. The 1990 orthographic agreement
dropped a silent c/p before t/ç (projecto→projeto, acto→ato, directo→direto…). `_MORPH` is the existing spelling map, already
carrying favourite→favorite and colour→color; the European spellings of the slot vocabulary belong there. Property, not a phrase
list: for every EU/BR pair whose BR form is a slot alias, the EU form must resolve to the same slot. Today exactly one word of the
136-token alias vocabulary has a European variant — `projecto` — and the test enumerates the pair list so a new alias is covered."""
from __future__ import annotations

import os
import tempfile

from hmgfu.facts import FactStore
from hmgfu.slots import SLOTS, _tokens, is_slot, normalise_key

EU_BR = {"acção": "ação", "acto": "ato", "activo": "ativo", "actual": "atual", "adopção": "adoção",
         "arquitecto": "arquiteto", "colecção": "coleção", "correcto": "correto", "direcção": "direção",
         "directo": "direto", "exacto": "exato", "objecto": "objeto", "projecto": "projeto",
         "secção": "seção", "selecção": "seleção", "actividade": "atividade"}


def test_every_european_spelling_of_a_slot_alias_resolves_to_the_same_slot():
    vocabulary = {t for spec in SLOTS.values() for a in spec["aliases"] for t in _tokens(a)}
    checked = 0
    for eu, br in EU_BR.items():
        if br not in vocabulary:
            continue                                   # not part of the slot vocabulary — nothing to normalise
        checked += 1
        assert normalise_key(eu) == normalise_key(br) == [s for s in SLOTS if normalise_key(br) == s][0], (eu, br)
    assert checked >= 1, "the pair list no longer touches the slot vocabulary — re-check"


def test_the_european_spelling_writes_the_fact():
    for text, value in [("O meu projecto principal é o Mapiko.", "Mapiko"),
                        ("A partir de agora o meu projecto é o HMG.", "HMG"),
                        ("O meu projeto principal é o Mapiko.", "Mapiko")]:
        store = FactStore(os.path.join(tempfile.mkdtemp(), "f.db"))
        store.apply_all(text, "user_explicit")
        assert {r["key"]: r["value"] for r in store.active()}.get("project.main") == value, text


def test_it_is_a_normalisation_not_a_new_slot():
    assert is_slot(normalise_key("projecto")) and normalise_key("projecto") == "project.main"
    assert not is_slot(normalise_key("projector"))        # a different word is untouched
    assert normalise_key("projecto principal") == "project.main"
