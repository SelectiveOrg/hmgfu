"""Phase 79.3 finding — a Portuguese NEGATED copula ("o meu nome não é esse") must never write a fact; it retires the value
it negates when that value is stored, exactly as the English "my name is not X" does."""
from __future__ import annotations

from hmgfu.facts import FactStore
from hmgfu.fact_detect import detect_facts


def test_negated_copula_is_a_negation_not_a_value(tmp_path):
    assert detect_facts("Isso está errado, o meu nome não é esse.") == []                        # demonstrative: no value at all
    dets = detect_facts("O meu nome não é Sebastian.")
    assert dets == [{"key": "nome", "clear_value": "Sebastian"}]
    st = FactStore(str(tmp_path / "f.db"))
    st.apply_all("O meu nome é Teodoro.", "user_explicit")
    assert st.apply_all("Isso está errado, o meu nome não é esse.", "user_explicit") == []
    assert {f["key"]: f["value"] for f in st.active()} == {"identity.name": "Teodoro"}            # the real name survives
    st.apply_all("O meu nome não é Teodoro.", "user_explicit")
    assert st.active() == []                                                                     # a named negation retires it
    st2 = FactStore(str(tmp_path / "g.db"))
    st2.apply_all("My name is Teodoro.", "user_explicit")
    st2.apply_all("That's wrong, my name is not that.", "user_explicit")
    assert {f["key"]: f["value"] for f in st2.active()} == {"identity.name": "Teodoro"}
