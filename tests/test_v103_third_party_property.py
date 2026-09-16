"""Phase 91.S1 — a relative's PROPERTY is not the user's, even though the relation itself is.

Reproduced from the independent audit (`reports/codex_execution_audit_20260909/ANALISE_E_PLANO.md` §3, P1) and seen
again in the reserved run of 90.O: after "My lucky number is 14", the sentence "My wife's lucky number is 88"
overwrites the user's value with 88, and the reply then states it. The same construction about a drink writes nothing,
so the protection is inconsistent rather than absent.

The cause is a legitimate rule taken one step too far. `wife`, `sister`, `brother` are in the RELATIONS set precisely
because `family.sister_name` is a fact about the USER's family — so the possessor is not treated as a stranger. But
that licence covers the relation's IDENTITY, not everything the relative owns: normalising "my wife's lucky number"
to `misc.lucky_number` silently changes the subject.

The contract this test fixes: a relation possessor keeps the claim for the user only when the attribute names that
person (their name); any other property belongs to them. Negatives are the other half — the family slots must keep
working, in both languages.
"""

from __future__ import annotations

import pytest

from hmgfu.facts import FactStore
from hmgfu.value_gate import third_party_attr


def _active(tmp_path, *messages):
    st = FactStore(str(tmp_path / "f.db"))
    for m in messages:
        st.apply_all(m, "user_explicit")
    return {f["key"]: f["value"] for f in st.active()}


THIRD_PARTY_PROPERTY = [
    ("My wife's lucky number is 88.", "misc.lucky_number", "14", ["My lucky number is 14."]),
    ("My wife's favourite drink is mazurca.", "pref.drink", "tea", ["My favourite drink is tea."]),
    ("My brother's favourite colour is amber.", "pref.color", "teal", ["My favourite colour is teal."]),
    ("My sister's car is a Hilux.", "asset.car", "Kia", ["My car is a Kia."]),
    ("O carro do meu irmão é um Hilux.", "asset.car", "Kia", ["O meu carro é um Kia."]),
    ("A bebida preferida da minha mãe é chá verde.", "pref.drink", "matapa", ["A minha bebida preferida é matapa."]),
]


@pytest.mark.parametrize("sentence,key,keep,before", THIRD_PARTY_PROPERTY)
def test_a_relatives_property_never_overwrites_the_users(tmp_path, sentence, key, keep, before):
    got = _active(tmp_path, *before, sentence)
    assert got.get(key) == keep, f"{sentence!r} changed {key}: {got}"


@pytest.mark.parametrize("sentence,key,keep,before", THIRD_PARTY_PROPERTY)
def test_the_relatives_property_does_not_write_on_an_empty_store(tmp_path, sentence, key, keep, before):
    """Not merely 'the old value wins': the third party's property must not be the user's fact at all."""
    got = _active(tmp_path, sentence)
    assert key not in got, f"{sentence!r} wrote {key}: {got}"


FAMILY_IDENTITY = [
    ("My sister's name is Ana.", "family.sister_name", "Ana"),
    ("My brother's name is Amaro.", "family.brother_name", "Amaro"),
    ("My mother's name is Rosa.", "family.mother_name", "Rosa"),
    ("O meu irmão chama-se Bartolomeu.", "family.brother_name", "Bartolomeu"),
]


@pytest.mark.parametrize("sentence,key,value", FAMILY_IDENTITY)
def test_the_relation_itself_is_still_the_users_fact(tmp_path, sentence, key, value):
    assert _active(tmp_path, sentence).get(key) == value


USER_OWN = [
    ("My lucky number is 14.", "misc.lucky_number", "14"),
    ("My favourite drink is tea.", "pref.drink", "tea"),
    ("A minha bebida preferida é matapa.", "pref.drink", "matapa"),
]


@pytest.mark.parametrize("sentence,key,value", USER_OWN)
def test_the_users_own_property_still_writes(tmp_path, sentence, key, value):
    assert _active(tmp_path, sentence).get(key) == value


def test_the_predicate_reads_the_attribute_not_a_name_list():
    """The rule is about the SHAPE of the attribute, so an unseen relative and an unseen property both work."""
    assert third_party_attr("wife's lucky number")
    assert third_party_attr("nephew's favourite album")
    assert not third_party_attr("sister's name")
    assert not third_party_attr("favourite colour")
