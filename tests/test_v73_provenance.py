"""Phase 82.3 — exact provenance (Codex review 2, A4): every assertion written from a turn points at its episode (the
ingested point id) and carries the exact offsets of its value inside the message; `link_source` links the assertion, not
only the canonical projection; a provenance report counts linked vs unlinked."""
from __future__ import annotations

from hmgfu.assertions import locate_value
from hmgfu.fact_reconcile import provenance
from hmgfu.facts import FactStore


def _store(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    return FactStore(str(tmp_path / "f.db"))


def test_locate_value_is_exact_and_case_insensitive():
    assert locate_value("My favourite colour is Amber, always.", "amber") == (23, 28)
    assert locate_value("Chamo-me Élio Mabunda.", "Élio Mabunda") == (9, 21)
    assert locate_value("I am Happy, that's my actual name.", "Feliz") == (None, None)      # mapped value: not verbatim


def test_assertion_carries_episode_and_exact_span(tmp_path):
    st = _store(tmp_path / "a")
    text = "By the way, my dog is called Simba and I live in Tete."
    changes = st.apply_all(text, "user_explicit")
    for ch in changes:
        st.link_source(ch["key"], "pt-0001")                            # what turn_tail does after ingest
    by_rel = {a["relation"]: a for a in st.assertions.active()}
    dog, loc = by_rel["pet.dog.name"], by_rel["identity.location"]
    assert dog["source_episode"] == "pt-0001" and loc["source_episode"] == "pt-0001"
    assert text[dog["span_start"]:dog["span_end"]] == "Simba" and text[loc["span_start"]:loc["span_end"]] == "Tete"
    assert dog["source_span"] == text                                   # the whole message, not a 300-char cut
    canon = {r["key"]: r for r in st.active()}
    assert canon["pet.dog.name"]["source_turn_id"] == "pt-0001"         # the canonical projection still links (Rule 11)


def test_link_source_targets_only_this_turns_assertion(tmp_path):
    st = _store(tmp_path / "b")
    st.apply_all("My favourite colour is amber.", "user_explicit"); st.link_source("pref.color", "pt-1")
    st.apply_all("My favourite colour is teal.", "user_explicit"); st.link_source("pref.color", "pt-2")
    hist = {a["value"]: a["source_episode"] for a in st.assertions.history("user", "pref.color")}
    assert hist == {"amber": "pt-1", "teal": "pt-2"}                    # the superseded one keeps ITS episode


def test_provenance_report_counts_links(tmp_path):
    st = _store(tmp_path / "c")
    st.apply_all("My name is Ana.", "user_explicit"); st.link_source("identity.name", "pt-9")
    st.apply_all("My sister is Zara.", "user_explicit")                 # never linked (e.g. a bench path)
    rep = provenance(st)
    assert rep == {"active": 2, "with_episode": 1, "with_span": 2, "unlinked": ["family.sister_name"]}


def test_legacy_assertions_take_the_canonical_rows_real_link(tmp_path):
    st = _store(tmp_path / "d")
    st.apply_all("My name is Ana.", "user_explicit"); st.link_source("identity.name", "pt-7")
    st._db.execute("UPDATE assertions SET source_episode=NULL"); st._db.commit()      # a pre-82.3 row: canonical linked, assertion not
    st2 = FactStore(str(tmp_path / "d" / "f.db"))
    assert st2.reconcile_report["relinked"] == 1
    assert [a["source_episode"] for a in st2.assertions.active()] == ["pt-7"]


def test_accented_values_link_and_supersede(tmp_path):
    st = _store(tmp_path / "e")
    st.apply_all("Chamo-me Élio Mabunda.", "user_explicit"); st.link_source("identity.name", "pt-1")
    assert [a["source_episode"] for a in st.assertions.active() if a["relation"] == "identity.name"] == ["pt-1"]   # 82.5: SQLite lower() is ASCII-only
    st.apply_all("Chamo-me Lúcia Matola.", "user_explicit")
    assert [a["value"] for a in st.assertions.active() if a["relation"] == "identity.name"] == ["Lúcia Matola"]
    st.apply_all("O meu cão chama-se Íris.", "user_explicit"); st.apply_all("O meu cão é o Teca, não o Íris.", "user_explicit")
    assert not [a for a in st.assertions.active() if a["value"] == "Íris"]
