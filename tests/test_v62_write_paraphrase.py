"""Phase 77.5 — novel phrasing on the write side: one test per failure CLASS of the sealed v4 set (the set itself is
the measurement; these pin the mechanism so a later change cannot silently undo it)."""
from __future__ import annotations

from hmgfu.facts import FactStore
from hmgfu.fact_detect import _looks_like_name, name_value_ok
from hmgfu.utterance import sentence_modalities


_N = [0]


def _store(tmp_path, *msgs):
    _N[0] += 1
    st = FactStore(str(tmp_path / f"f{_N[0]}.db"))                            # a fresh store per call
    for m in msgs:
        st.apply_all(m, "user_explicit")
    return st, {f["key"]: f["value"] for f in st.active()}


def test_a_name_slots_take_only_name_shaped_values(tmp_path):
    assert name_value_ok("identity.name", "Rute Machel dos Santos") and name_value_ok("pet.dog.name", "mimi")
    assert name_value_ok("pref.color", "hard to spell")                        # not a name slot: not gated here
    for bad in ("4 years old", "asleep on the sofa", "hungry again", "hard to spell for most people", "difícil de pronunciar"):
        assert not name_value_ok("pet.dog.name", bad) and not _looks_like_name(bad, strict=False)
    _, a = _store(tmp_path, "My dog is Rex.", "My dog Rex is 4 years old.", "My cat is hungry again.",
                  "My name is hard to spell for most people.", "O meu nome é difícil de pronunciar.")
    assert a == {"pet.dog.name": "Rex"}


def test_b_nominal_fiction_frame_is_not_a_fact(tmp_path):
    assert [c["modality"] for c in sentence_modalities("In the novel I'm writing, my name is Zora.")] == ["fiction"]
    _, a = _store(tmp_path, "In the novel I'm writing, my name is Zora.", "No romance que escrevo, chamo-me Zora.")
    assert a == {}


def test_c_negated_location_retires_the_value(tmp_path):
    _, a = _store(tmp_path, "I live in Pemba.", "I no longer live in Pemba.")
    assert a == {}
    _, a = _store(tmp_path, "Moro em Tete.", "Já não moro em Tete.")
    assert a == {}
    _, a = _store(tmp_path, "I live in Pemba.", "I don't live in Pemba anymore, I live in Aveiro.")
    assert a == {"identity.location": "Aveiro"}


def test_d_pet_have_frames_and_enumeration(tmp_path):
    _, a = _store(tmp_path, "We have a dog at home, his name is Bolt.", "Our cat answers to Mika.")
    assert a == {"pet.dog.name": "Bolt", "pet.cat.name": "Mika"}
    _, a = _store(tmp_path, "Temos um cão em casa, chama-se Faísca.", "A nossa gata chama-se Nina.")
    assert a == {"pet.dog.name": "Faísca", "pet.cat.name": "Nina"}
    _, a = _store(tmp_path, "I have two dogs, Bolt and Kika.")
    assert a == {"pet.dog.name": "Bolt", "pet.dog.name.2": "Kika"}
    _, a = _store(tmp_path, "Tenho dois cães, o Bolt e a Kika.")
    assert a == {"pet.dog.name": "Bolt", "pet.dog.name.2": "Kika"}


def test_e_preference_frames_resolve_through_the_schema(tmp_path):
    _, a = _store(tmp_path, "Colour-wise I always go for burgundy.", "A bebida que prefiro é sumo de maracujá.",
                  "If there's one dish I love, it's matapa.", "My go-to drink is hibiscus tea.",
                  "These days I code mostly in Rust.", "I'm a Costa do Sol supporter, always have been.",
                  "My music taste: marrabenta, mostly.", "My birthday falls on 3 March.", "My brother goes by Nuno.")
    assert a == {"pref.color": "burgundy", "pref.drink": "hibiscus tea", "pref.food": "matapa", "pref.language": "Rust",
                 "pref.team": "Costa do Sol", "pref.music": "marrabenta", "identity.birthday": "3 March",
                 "family.brother_name": "Nuno"}
    st, a = _store(tmp_path, "My favourite colour used to be teal, now it's amber.")
    assert a == {"pref.color": "amber"} and "teal" not in " ".join(st.render_lines())
    _, a = _store(tmp_path, "A minha cor favorita era o verde, agora é o roxo.")
    assert a == {"pref.color": "roxo"}
    _, a = _store(tmp_path, "My plan: go to the beach.")                     # a colon form needs a closed slot
    assert a == {}


def test_f_identity_paraphrases_and_value_trimming(tmp_path):
    _, a = _store(tmp_path, "Apresento-me: sou a Joana Tembe.", "Mudei-me para a Aveiro o mês passado.",
                  "I work as a nurse at the district hospital.")
    assert a == {"identity.name": "Joana Tembe", "identity.location": "Aveiro", "identity.job": "nurse"}
    _, a = _store(tmp_path, "Vivo em Quelimane há dois anos.")
    assert a == {"identity.location": "Quelimane"}
    _, a = _store(tmp_path, "We moved last month; home is Matola now.")
    assert a == {"identity.location": "Matola"}
    _, a = _store(tmp_path, "Note for later: my car is parked at https://maps.example.test/car-42")
    assert a == {"asset.car_location_link": "https://maps.example.test/car-42"}
    _, a = _store(tmp_path, "Sou adepto do Ferroviário da Aveiro.", "Sou engenheira.")   # bare "sou": no name written
    assert a == {"pref.team": "Ferroviário da Aveiro", "identity.job": "engenheira"}


def test_g_fuller_restatement_of_the_same_name_wins(tmp_path):
    _, a = _store(tmp_path, "I'm Petra, by the way — Petra Vidal.")
    assert a == {"identity.name": "Petra Vidal"}
    _, a = _store(tmp_path, "Sou a Joana, já agora — Joana Tembe.")
    assert a == {"identity.name": "Joana Tembe"}


def test_h_a_relatives_attribute_is_not_a_user_fact(tmp_path):
    _, a = _store(tmp_path, "My sister's favourite food is mucapata.", "O prato favorito da minha irmã é badjias.")
    assert a == {}
    _, a = _store(tmp_path, "O meu primo é o Tino.")                        # a bare relative is still the user's fact
    assert a == {"open.primo": "Tino"}
