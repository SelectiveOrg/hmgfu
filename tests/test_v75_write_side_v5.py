"""Phase 83 — the write side on unseen messages: the reserved-set (v5) failure families as failing tests, one test per
family, fixed at the cause (83.1 predicates are not values; 83.2 value boundary; 83.3 unseen moulds; 83.4 sequences;
83.5 retirements). v5 itself is a regression set from Phase 83 on; the phase is measured on the reserved v6."""
from __future__ import annotations

import pytest

from hmgfu.facts import FactStore


def _run(tmp_path, *messages, prior=()):
    tmp_path.mkdir(parents=True, exist_ok=True)
    st = FactStore(str(tmp_path / "f.db"))
    for m in prior:
        st.apply_all(m, "user_explicit")
    before = {f["key"]: f["value"] for f in st.active()}
    for m in messages:
        st.apply_all(m, "user_explicit")
    after = {f["key"]: f["value"] for f in st.active()}
    return {k: v for k, v in after.items() if before.get(k) != v}, {k for k in before if k not in after}


# ---------------------------------------------------------------- 83.1 predicates are not values ----------------
@pytest.mark.parametrize("text", [
    "My battery is at 5 percent.", "A minha bateria está a 5 por cento.", "My internet is slow today.", "My flight is at 6.",
    "O meu voo é às 6.", "My name day is in July.", "O meu dia de santo é em Julho.", "My favourite is the one on the left.",
    "O meu favorito é o da esquerda.", "My choice would be the second option.", "O meu plano é acabar até sexta.",
    "My favourite colour is hard to describe.", "A minha cor favorita é difícil de descrever.", "People say my name is unusual.",
    "Maybe my favourite colour is teal, or maybe amber.", "My neighbour's dog is called Rex.",
])
def test_predicates_and_third_parties_write_nothing(tmp_path, text):
    written, _ = _run(tmp_path / "p", text)
    assert written == {}, written


# ---------------------------------------------------------------- 83.2 value boundary ---------------------------
@pytest.mark.parametrize("text,key,value", [
    ("Afinal a minha cor favorita agora é o índigo, não o verde-oliva.", "pref.color", "índigo"),
    ("A minha cor favorita é o índigo; a minha bebida favorita é chá de rooibos.", "pref.color", "índigo"),
    ("O meu carro é um Toyota Hilux.", "asset.car", "Toyota Hilux"),
    ("O meu número da sorte é o 27.", "misc.lucky_number", "27"),
    ("I develop in Swift mostly.", "pref.language", "Swift"),
    ("Sou adepto do Black Bulls de corpo e alma.", "pref.team", "Black Bulls"),
    ("Trabalho como camionista numa transportadora.", "identity.job", "camionista"),
    ("Sou contabilista numa empresa pequena.", "identity.job", "contabilista"),
    ("Just call me T.", "identity.alias", "T"),
    ("O meu aniversário é a 8 de Novembro.", "identity.birthday", "8 de Novembro"),
])
def test_values_end_where_the_attribute_ends(tmp_path, text, key, value):
    written, _ = _run(tmp_path / "b", text)
    assert written.get(key) == value, written
