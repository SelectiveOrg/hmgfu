"""95.51 + 95.52 (N1, N4 on v5, 0/3 both arms) — one English copula class for the possessive and the
article forms; the PT pet-rename retirement clause class.

"Heads-up: the main project goes by Ibis these days; Sable was the old name." wrote nothing (the article
form had is / is called / is named; "goes by" lived only in the possessive form). "Novidade: a minha gata
deixou de se chamar Mira; agora chama-se Nina." wrote nothing (the rename mould knew "(ja) nao se chama
X, chama-se Y" only). Positive: both write, and the store supersedes. Preserve: the possessive "goes
by", the "is called" article form, the v3 rename wording, and a third party's project all as before.
"""
from __future__ import annotations

from hmgfu.facts import FactStore
from hmgfu.fact_detect import detect_facts

N1 = "Heads-up: the main project goes by Ibis these days; Sable was the old name."
N4 = "Novidade: a minha gata deixou de se chamar Mira; agora chama-se Nina."


def _pairs(dets):
    return [(d["key"], d["value"]) for d in dets]


def test_the_article_form_reads_the_shared_copula_class():
    """THE CONTRACT (95.51) — fails before: 'goes by' is not in the article form."""
    assert ("main_project", "Ibis") in _pairs(detect_facts(N1))
    assert ("main_project", "Ibis") in _pairs(detect_facts("The main project is known as Ibis now."))
    assert ("main_project", "Ibis") in _pairs(detect_facts("My main project goes by Ibis."))


def test_the_pt_rename_retirement_clause_is_read():
    """THE CONTRACT (95.52) — fails before: 'deixou de se chamar' is not a retirement clause."""
    assert _pairs(detect_facts(N4)) == [("pet.cat.name", "Nina")]
    assert _pairs(detect_facts("A minha gata ja nao e a Mira; agora e a Nina.")) == [("pet.cat.name", "Nina")]
    assert _pairs(detect_facts("Correcao: a minha gata ja nao se chama Sol, chama-se Lua.")) == [("pet.cat.name", "Lua")]


def test_the_store_supersedes_on_both(tmp_path):
    store = FactStore(str(tmp_path / "a.db"))
    store.apply_all("My main project is called Sable.", "user_explicit", session="s0")
    assert [(c.get("key"), c.get("value")) for c in store.apply_all(N1, "user_explicit", session="s1")] == [("project.main", "Ibis")]
    assert [(f["key"], f["value"]) for f in store.active() if f["key"] == "project.main"] == [("project.main", "Ibis")]
    store2 = FactStore(str(tmp_path / "b.db"))
    store2.apply_all("My cat is called Mira.", "user_explicit", session="s0")
    assert [(c.get("key"), c.get("value")) for c in store2.apply_all(N4, "user_explicit", session="s1")] == [("pet.cat.name", "Nina")]
    assert [(f["key"], f["value"]) for f in store2.active() if f["key"] == "pet.cat.name"] == [("pet.cat.name", "Nina")]


def test_third_party_and_open_heads_still_write_nothing():
    assert detect_facts("The main project of Rui goes by Atlas.") == []
    assert [d for d in detect_facts("The weather goes by fast these days.") if d["key"] == "weather" and not d.get("weak")] == []
