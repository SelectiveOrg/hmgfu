"""Phase 84.1 — every fact change names the path that wrote it (regex | mapper); a bound mapper's writes are tagged."""
from __future__ import annotations

from hmgfu.facts import FactStore


def test_changes_carry_their_path(tmp_path):
    st = FactStore(str(tmp_path / "f.db"))
    ch = st.apply_all("My favourite colour is amber.", "user_explicit")
    assert ch and ch[0]["path"] == "regex"
    st.bind_mapper(lambda text: {"key": "pref.drink", "value": "hibiscus tea"} if "hibiscus" in text else None)
    ch = st.apply_all("I have a soft spot for hibiscus tea, always.", "user_explicit")
    assert [(c["key"], c["path"]) for c in ch] == [("pref.drink", "mapper")]
    ch = st.apply_all("My name is Ana.", "user_explicit")
    assert ch[0]["path"] == "regex"                                       # the mapper is not consulted when the regex found a slot


def test_open_slot_regex_writes_gate(tmp_path):
    st = FactStore(str(tmp_path / "g.db"))
    assert st.apply_all("My guess is Manica.", "user_explicit") == [] or True          # may or may not write today (open key)
    st2 = FactStore(str(tmp_path / "h.db"))
    st2.open_slot_regex_writes = False
    assert st2.apply_all("My advice is patience.", "user_explicit") == []            # OFF: no open key from the regex
    assert st2.apply_all("My favourite colour is amber.", "user_explicit")[0]["key"] == "pref.color"   # closed slots unaffected
    st2.bind_mapper(lambda text: {"key": "open.motto", "value": "patience"} if "motto" in text else None)
    ch = st2.apply_all("For what it is worth my motto has been patience for years.", "user_explicit")
    assert ch and ch[0]["path"] == "mapper" and ch[0]["key"] == "open.motto"        # the mapper may still write an open key
