"""Phase 77.3 — one read path over assertions: clears retire the assertion; render_lines comes from supported active
assertions; legacy canonical rows are backfilled once; the justification gate removes an unsupported conclusion."""
from __future__ import annotations

from hmgfu.facts import FactStore


def test_clear_and_negation_retire_the_assertion(tmp_path):
    st = FactStore(str(tmp_path / "f.db"))
    st.apply_all("My dog is Rex.", "user_explicit")
    assert [a["value"] for a in st.assertions.active()] == ["Rex"] and "Rex" in " ".join(st.render_lines())
    st.apply_all("I don't have a dog called Rex.", "user_explicit")
    assert st.assertions.active() == [] and st.render_lines() == []                      # no divergence left
    st.apply_all("My favourite color is teal.", "user_explicit")
    st.apply_all("My favourite color is amber, not teal.", "user_explicit")
    vals = [a["value"] for a in st.assertions.active()]
    assert vals == ["amber"] and "teal" not in " ".join(st.render_lines())


def test_render_from_assertions_matches_the_canonical_projection(tmp_path):
    st = FactStore(str(tmp_path / "f.db"))
    for m in ("My name is Nadia Costa.", "I live in Lisbon.", "I live in Chimoio now.", "My cat is Luna and my cat is Sol. They are two different cats.",
              "A minha linguagem favorita é Java."):
        st.apply_all(m, "user_explicit")
    rendered = st.render_lines()
    canon = {f["value"] for f in st.active() if f["slot"]}
    assert canon <= {ln.split(" is ", 1)[1] for ln in rendered}                           # every canonical current value renders
    assert "Lisbon" not in " ".join(rendered) and "Chimoio" in " ".join(rendered)
    assert sum("cat" in ln for ln in rendered) == 2                                       # two entities, two lines


def test_legacy_canonical_rows_are_backfilled_once(tmp_path):
    db = str(tmp_path / "f.db")
    st = FactStore(db)
    st._db.execute("INSERT OR REPLACE INTO canonical_facts VALUES (?, ?, ?, ?, ?, ?, ?)",
                   ("identity.name", "Teodoro", None, "user_explicit", "2026-04-20T00:00:00+00:00", "so, my name is teodoro", None))
    st._db.commit()
    assert st.render_lines() == []                          # the row pre-dates the assertion store: nothing renders yet
    st2 = FactStore(db)                                     # a fresh store backfills at construction
    assert st2.render_lines() == ["Your name is Teodoro"]
    assert len([a for a in st2.assertions.active() if a["relation"] == "identity.name"]) == 1
    FactStore(db)                                           # idempotent: no second assertion
    assert len([a for a in st2.assertions.active() if a["relation"] == "identity.name"]) == 1


def test_unsupported_conclusion_leaves_the_rendered_context(tmp_path):
    st = FactStore(str(tmp_path / "f.db"))
    st.apply_all("My name is Nadia Costa.", "user_explicit")
    st.apply_all("I live in Valencia.", "user_explicit")
    name = next(a for a in st.assertions.active() if a["relation"] == "identity.name")
    loc = next(a for a in st.assertions.active() if a["relation"] == "identity.location")
    st.assertions.justify(loc["id"], [name["id"]])          # the location holds only while the name does (a test dependency)
    assert "Valencia" in " ".join(st.render_lines())
    st.assertions.retract("user", "identity.name", "Nadia Costa")
    assert "Valencia" not in " ".join(st.render_lines())      # premise gone → the conclusion is unsupported → not rendered



def test_correction_without_plurality_supersedes_the_old_entity_assertion(tmp_path):
    st = FactStore(str(tmp_path / "f.db"))
    st.apply_all("My cat is Luna.", "user_explicit")
    st.apply_all("My cat is Sol.", "user_explicit")
    assert [a["value"] for a in st.assertions.active()] == ["Sol"] and st.render_lines() == ["Your cat's name is Sol"]
    hist = st.assertions.history()
    assert [h["status"] for h in hist if h["value"] == "Luna"] == ["superseded"]
    st.apply_all("My cat is Luna and my cat is Sol. They are two different cats.", "user_explicit")   # plurality: both stay
    assert sum("cat" in ln for ln in st.render_lines()) == 2
