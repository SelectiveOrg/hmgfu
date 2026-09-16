"""Phase 82.2 — one durable revision (Codex review 2, A2): the canonical row and its assertion are written on ONE connection
in ONE transaction (a crash between them leaves no half revision); construction reconciles and reports divergence;
`active(at=, known_at=)` separates valid time from known time; the replaced value is kept, not overwritten."""
from __future__ import annotations

import sqlite3

import pytest

from hmgfu.assertions import AssertionStore
from hmgfu.facts import FactStore


def _store(tmp_path, *messages):
    tmp_path.mkdir(parents=True, exist_ok=True)
    st = FactStore(str(tmp_path / "f.db"))
    for m in messages:
        st.apply_all(m, "user_explicit")
    return st


def test_canonical_and_assertion_share_one_connection(tmp_path):
    st = _store(tmp_path / "a")
    assert st.assertions._db is st._db                                         # one connection → one transaction


def test_crash_between_the_two_writes_leaves_no_half_revision(tmp_path):
    st = _store(tmp_path / "b", "My name is Ana.")
    real = st.assertions.assert_

    def boom(*a, **k):
        raise RuntimeError("injected crash between canonical and assertion writes")
    st.assertions.assert_ = boom
    with pytest.raises(RuntimeError):
        st.apply_all("My favourite colour is amber.", "user_explicit")
    st.assertions.assert_ = real
    canon = {r["key"]: r["value"] for r in st.active()}
    assert "pref.color" not in canon and canon["identity.name"] == "Ana"        # the canonical write rolled back
    assert not [h for h in st.history() if h["key"] == "pref.color"]           # and so did its history row
    assert not [a for a in st.assertions.active() if a["relation"] == "pref.color"]
    st.apply_all("My favourite colour is amber.", "user_explicit")             # the store is still usable afterwards
    assert {r["key"]: r["value"] for r in st.active()}["pref.color"] == "amber"
    assert [a["value"] for a in st.assertions.active() if a["relation"] == "pref.color"] == ["amber"]


def test_construction_reconciles_and_reports_divergence(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = str(tmp_path / "f.db")
    st = FactStore(path)
    st.apply_all("My name is Ana.", "user_explicit")
    st.apply_all("My dog is Rex.", "user_explicit")
    # simulate an old two-connection divergence: a canonical row without its assertion, and an assertion nothing supports
    raw = sqlite3.connect(path)
    raw.execute("DELETE FROM assertions WHERE relation='identity.name'")
    raw.execute("INSERT INTO assertions (id, entity_id, relation, value, polarity, modality, valid_from, valid_to, recorded_at, source_episode, source_span, status) VALUES ('orphan1','user','pref.color','amber','pos','assert',NULL,NULL,'2026-01-01T00:00:00+00:00',NULL,'','active')")
    raw.commit(); raw.close()
    st2 = FactStore(path)
    rep = st2.reconcile_report
    assert rep["backfilled"] == 1 and rep["orphaned"] == 1                    # reported, not silent
    active = {(a["relation"], a["value"]) for a in st2.assertions.active()}
    assert ("identity.name", "Ana") in active and ("pref.color", "amber") not in active
    assert ("pet.dog.name", "Rex") in active                                    # untouched rows stay
    assert FactStore(path).reconcile_report == {"backfilled": 0, "orphaned": 0, "relinked": 0}  # idempotent


def test_valid_time_and_known_time_answer_differently(tmp_path):
    a = AssertionStore(str(tmp_path / "a.db"))
    a.assert_("user", "identity.location", "Lisbon", valid_from="2020-01-01T00:00:00+00:00", source_span="I lived in Lisbon from 2020")
    recorded = a.active()[0]["recorded_at"]
    # valid time: it HELD in 2021 (when did it happen)
    assert [x["value"] for x in a.active(at="2021-06-01T00:00:00+00:00")] == ["Lisbon"]
    # known time: we did not KNOW it in 2021 (when did we learn it) — recorded today
    assert a.active(at="2021-06-01T00:00:00+00:00", known_at="2021-06-01T00:00:00+00:00") == []
    assert [x["value"] for x in a.active(known_at=recorded)] == ["Lisbon"]


def test_replaced_value_is_kept_not_overwritten(tmp_path):
    a = AssertionStore(str(tmp_path / "b.db"))
    a.assert_("user", "pref.color", "amber", source_span="amber")
    a.assert_("user", "pref.color", "teal", source_span="teal")
    hist = a.history("user", "pref.color")
    assert [h["value"] for h in hist] == ["amber", "teal"] and hist[0]["status"] == "superseded" and hist[0]["valid_to"]
    assert [x["value"] for x in a.active()] == ["teal"]


def test_supersession_closes_the_old_value_at_the_new_valid_from(tmp_path):
    a = AssertionStore(str(tmp_path / "c.db"))
    a.assert_("user", "identity.location", "Lisbon", valid_from="2015-01-01T00:00:00+00:00", source_span="I have lived in Lisbon since 2015")
    a.assert_("user", "identity.location", "Chimoio", valid_from="2020-01-01T00:00:00+00:00", source_span="since 2020 I live in Chimoio")
    hist = {h["value"]: h for h in a.history("user", "identity.location")}
    assert hist["Lisbon"]["valid_to"] == "2020-01-01T00:00:00+00:00"          # 87.3: valid time, not the recording time
    assert [x["value"] for x in a.active(at="2019-06-01T00:00:00+00:00")] == ["Lisbon"]
    assert [x["value"] for x in a.active(at="2021-06-01T00:00:00+00:00")] == ["Chimoio"]
    assert a.active(at="2019-06-01T00:00:00+00:00", known_at="2019-06-01T00:00:00+00:00") == []   # known time untouched
    b = AssertionStore(str(tmp_path / "d.db"))
    b.assert_("user", "pref.color", "amber", source_span="amber"); b.assert_("user", "pref.color", "teal", source_span="teal")
    assert {h["value"]: h for h in b.history("user", "pref.color")}["amber"]["valid_to"] is not None   # no valid_from: closes at recording time
