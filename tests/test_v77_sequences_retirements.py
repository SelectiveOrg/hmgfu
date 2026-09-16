"""Phase 83.4 sequences + 83.5 retirements — the reserved set v5 families iv and v, failing first."""
from __future__ import annotations

import pytest

from hmgfu.facts import FactStore


def _run(tmp_path, text, prior=()):
    tmp_path.mkdir(parents=True, exist_ok=True)
    st = FactStore(str(tmp_path / "f.db"))
    for m in prior:
        st.apply_all(m, "user_explicit")
    before = {f["key"]: f["value"] for f in st.active()}
    st.apply_all(text, "user_explicit")
    after = {f["key"]: f["value"] for f in st.active()}
    return {k: v for k, v in after.items() if before.get(k) != v}, {k for k in before if k not in after}


# ---------------------------------------------------------------- 83.4 sequences: the LAST value is the current one -----
@pytest.mark.parametrize("text,key,value", [
    ("I moved to Pemba. Then to Tete. Now I'm in Quelimane.", "identity.location", "Quelimane"),
    ("Mudei-me para Pemba. Depois para Tete. Agora estou em Quelimane.", "identity.location", "Quelimane"),
    ("My favourite colour was teal, then amber, and today it's indigo.", "pref.color", "indigo"),
    ("A minha cor favorita foi o verde-azulado, depois o âmbar, e hoje é o índigo.", "pref.color", "índigo"),
    ("My favourite colour used to be teal, now it's amber.", "pref.color", "amber"),
])
def test_sequences_write_only_the_last_value(tmp_path, text, key, value):
    written, _ = _run(tmp_path / "s", text)
    assert written == {key: value}, written


def test_sequence_history_keeps_the_earlier_values(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    st = FactStore(str(tmp_path / "f.db"))
    st.apply_all("I moved to Pemba. Then to Tete. Now I'm in Quelimane.", "user_explicit")
    assert {r["key"]: r["value"] for r in st.active()} == {"identity.location": "Quelimane"}
    assert [a["value"] for a in st.assertions.active() if a["relation"] == "identity.location"] == ["Quelimane"]


# ---------------------------------------------------------------- 83.5 retirements ---------------------------------
@pytest.mark.parametrize("text,prior,cleared", [
    ("We don't have a cat anymore.", ["My cat is Luna."], "pet.cat.name"),
    ("Já não temos gato.", ["O meu gato chama-se Luna."], "pet.cat.name"),
    ("I no longer work at Vodacom.", ["My employer is Vodacom."], "identity.company"),
    ("Já não trabalho na Vodacom.", ["A minha entidade patronal é a Vodacom."], "identity.company"),
    ("Don't call me Dudu, I hate that nickname.", ["Call me Dudu."], "identity.alias"),
    ("Não me chames Dudu, detesto essa alcunha.", ["Chama-me Dudu."], "identity.alias"),
    ("That's wrong, my favourite colour isn't teal.", ["My favourite colour is teal."], "pref.color"),
    ("Isso está errado, a minha cor favorita não é o verde-azulado.", ["A minha cor favorita é o verde-azulado."], "pref.color"),
    ("I'm not Bernardo, that's my brother.", ["My name is Bernardo."], "identity.name"),
])
def test_retirements_clear_the_slot_and_write_nothing(tmp_path, text, prior, cleared):
    written, gone = _run(tmp_path / "r", text, prior=prior)
    assert written == {} and cleared in gone, (written, gone)


def test_retirement_of_another_value_changes_nothing(tmp_path):
    written, gone = _run(tmp_path / "n", "I no longer work at Vodacom.", prior=["My employer is Millennium bim."])
    assert written == {} and not gone                                           # a named retirement retires only ITS value
    written, gone = _run(tmp_path / "o", "Don't call me Dudu.", prior=["Call me Zé."])
    assert written == {} and not gone
