"""Phase 82.1 — scoped retraction (Codex review 2, A1): a named negation retires the wrong value ONLY inside the family it
names. Written FAILING first: a user called Bento with a dog called Bento must keep their own name when
"my dog is Teca, not Bento" retires the dog; the canonical and assertion read paths must agree."""
from __future__ import annotations

from hmgfu.facts import FactStore


def _store(tmp_path, *messages):
    tmp_path.mkdir(parents=True, exist_ok=True)
    st = FactStore(str(tmp_path / "f.db"))
    for m in messages:
        st.apply_all(m, "user_explicit")
    return st


def _canon(st):
    return {r["key"]: r["value"] for r in st.active()}


def _asserted(st):
    return {(a["entity_id"], a["relation"], a["value"]) for a in st.assertions.active()}


def test_named_negation_stays_inside_its_family(tmp_path):
    st = _store(tmp_path / "a", "My name is Bento.", "My dog is Bento.", "My dog is Teca, not Bento.")
    canon = _canon(st)
    assert canon["identity.name"] == "Bento" and canon["pet.dog.name"] == "Teca"        # canonical: user keeps the name
    asserted = _asserted(st)
    assert ("user", "identity.name", "Bento") in asserted                                  # A1: the assertion must survive too
    assert not any(rel.startswith("pet.") and val == "Bento" for _e, rel, val in asserted)
    assert "Bento" in " ".join(st.render_lines()) and "Teca" in " ".join(st.render_lines())  # the ONE read path shows both


def test_named_negation_pt_same_scope(tmp_path):
    st = _store(tmp_path / "b", "Chamo-me Bento.", "O meu cão chama-se Bento.", "O meu cão é o Teca, não o Bento.")
    canon = _canon(st)
    assert canon["identity.name"] == "Bento" and canon["pet.dog.name"] == "Teca"
    assert ("user", "identity.name", "Bento") in _asserted(st)


def test_named_negation_still_retires_a_legacy_pet_row(tmp_path):
    # the Codex-69 case that motivated the family sweep must keep working: a legacy pet.name row holding the wrong value
    st = _store(tmp_path / "c", "My pet is Bento.", "My dog is Teca, not Bento.")
    lines = " ".join(st.render_lines())
    assert "Bento" not in lines and "Teca" in lines
    assert not any(val == "Bento" for _e, _r, val in _asserted(st))


def test_canonical_and_assertions_agree_after_retraction(tmp_path):
    st = _store(tmp_path / "d", "My name is Bento.", "My sister is Bento.", "My dog is Bento.", "My dog is Teca, not Bento.")
    canon = _canon(st)
    assert canon["identity.name"] == "Bento" and canon["family.sister_name"] == "Bento" and canon["pet.dog.name"] == "Teca"
    values_asserted = {(rel, val) for _e, rel, val in _asserted(st)}
    for key, val in canon.items():
        assert (key, val) in values_asserted, (key, val)                                   # every canonical row has its assertion


def test_named_negation_never_crosses_species(tmp_path):
    st = _store(tmp_path / "e", "My dog is Bento.", "My cat is Bento.", "My dog is Teca, not Bento.")
    canon = _canon(st)
    assert canon["pet.dog.name"] == "Teca" and canon["pet.cat.name"] == "Bento"          # 82.5 suite finding A
    assert ("pet.cat.name", "Bento") in {(r, v) for _e, r, v in _asserted(st)}
