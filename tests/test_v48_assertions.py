"""Phase 72 — modalities per sentence, assertions with entities/validity, cardinality, named negation, update subject,
mapper clause binding, history view. Own reproductions of Codex's seven deferred M3 checks."""

from __future__ import annotations

import json

from hmgfu.assertions import AssertionStore
from hmgfu.facts import FactStore
from hmgfu.slots import base_slot, is_slot, label_for, map_to_slot, relation_in_clause
from hmgfu.utterance import declarative_text, past_cue, sentence_modalities, valid_from_of
from tests.test_v2_agent import make_agent


def _store(tmp_path, *messages, mapper=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    st = FactStore(str(tmp_path / "f.db"))
    if mapper:
        st.bind_mapper(mapper)
    for m in messages:
        st.apply_all(m, "user_explicit")
    return st


def _active(st):
    return {f["key"]: f["value"] for f in st.active()}


def test_sentence_modalities_and_carry_over():
    mods = {c["text"]: c["modality"] for c in sentence_modalities("For a fictional character. My name is Oscar.")}
    assert mods["My name is Oscar."] == "fiction"
    mods = sentence_modalities("My friend says 'my name is Oscar'. That is his name, not mine.")
    assert any(c["modality"] == "cite" and "Oscar" in c["text"] for c in mods) and "Oscar" not in declarative_text("My friend says 'my name is Oscar'.")
    assert declarative_text("For a story I am writing: my name is Oscar. Anyway, my real name is Nadia Costa.").strip().startswith("my real name is Nadia Costa") or "Nadia Costa" in declarative_text("For a story I am writing: my name is Oscar. Anyway, my real name is Nadia Costa.")
    assert valid_from_of("Desde 2023 eu moro em Chimoio.") == "2023-01-01" and declarative_text("Desde 2023 eu moro em Chimoio.")
    assert declarative_text("In 2010 I lived in Lisbon.") == "" and past_cue("where did I live before?") and not past_cue("where do I live?")


def test_codex_m3_cases_as_own_reproductions(tmp_path):
    assert _active(_store(tmp_path / "a", "My name is Nadia Costa.", "My friend says 'my name is Oscar'.")) == {"identity.name": "Nadia Costa"}
    assert _active(_store(tmp_path / "b", "My name is Nadia Costa.", "For a fictional character. My name is Oscar.")) == {"identity.name": "Nadia Costa"}
    assert _active(_store(tmp_path / "c", "Desde 2023 eu moro em Chimoio.")) == {"identity.location": "Chimoio"}
    st = _store(tmp_path / "d", "Here is the link for my car location: https://example.test/car", "Here is the new recipe link: https://example.test/soup")
    assert _active(st) == {"asset.car_location_link": "https://example.test/car", "open.recipe_link": "https://example.test/soup"}
    text = "My mother's name is Ana and my favorite color is amber."
    assert not relation_in_clause("family.mother_name", text, "amber") and relation_in_clause("family.mother_name", text, "Ana")
    assert map_to_slot(text, lambda *_: {"slot": "family.mother_name", "value": "amber", "op": "set"}) is None
    st = _store(tmp_path / "e", "My dog is Bento and my dog is Teca. These are two different dogs.")
    vals = json.dumps(_active(st))
    assert "Bento" in vals and "Teca" in vals and is_slot("pet.dog.name.2") and base_slot("pet.dog.name.2") == "pet.dog.name"
    assert label_for("pet.dog.name.2") == "dog's name (2)"
    st = _store(tmp_path / "f", "My pet is Bento.", "My dog is Teca, not Bento.")
    assert "Bento" not in " ".join(st.render_lines()) and "Teca" in " ".join(st.render_lines())


def test_correction_without_plurality_replaces_and_generic_link_still_binds(tmp_path):
    assert _active(_store(tmp_path / "g", "My dog is Bento.", "My dog is Teca.")) == {"pet.dog.name": "Teca"}
    st = _store(tmp_path / "h", "Here is the link for my car location: https://example.test/old", "Here's the updated link: https://example.test/new")
    assert _active(st)["asset.car_location_link"] == "https://example.test/new"


def test_assertion_store_bitemporal_and_justifications(tmp_path):
    st = AssertionStore(str(tmp_path / "a.db"))
    a1 = st.assert_("user", "identity.location", "Lisbon", valid_from="2020-01-01", source_span="I live in Lisbon")
    a2 = st.assert_("user", "identity.location", "Chimoio", source_span="I live in Chimoio now")
    assert [a["value"] for a in st.active()] == ["Chimoio"]
    assert [a["value"] for a in st.active(at="2021-06-01T00:00:00+00:00")] == ["Lisbon"]     # query-time validity
    hist = st.history("user", "identity.location")
    assert [h["status"] for h in hist] == ["superseded", "active"] and hist[0]["valid_to"]
    dog = st.upsert_entity("pet", "Bento"); dog2 = st.upsert_entity("pet", "Teca")
    assert dog != dog2 and st.upsert_entity("pet", "bento") == dog
    concl = st.assert_("user", "derived.lunch", "vegetarian near Valencia office")
    st.justify(concl, [a2, st.assert_("user", "pref.food", "vegetarian")])
    assert st.supported(concl)
    st.retract("user", "pref.food", "vegetarian")
    assert not st.supported(concl) and st.supported(a2)                                    # revision is localised


def test_facts_write_assertions_with_entities_and_history_view(tmp_path):
    st = _store(tmp_path / "i", "Since 2021 I live in Nampula.", "My cat is Luna and my cat is Sol. They are two different cats.")
    loc = [a for a in st.assertions.active() if a["relation"] == "identity.location"]
    assert loc and loc[0]["valid_from"] == "2021-01-01" and loc[0]["value"] == "Nampula"
    assert {e["name"] for e in st.assertions.entities("pet")} == {"pet.cat.name", "pet.cat.name.2"}   # 95.32: the entity is the animal (its slot), the name is its value
    pets = [a for a in st.assertions.active() if a["relation"] == "pet.cat.name"]         # the relation is the base slot; the entity tells the cats apart
    assert sorted(a["value"] for a in pets) == ["Luna", "Sol"] and len({a["entity_id"] for a in pets}) == 2
    st2 = _store(tmp_path / "j", "I live in Lisbon.", "I live in Chimoio now.")
    hist = " ".join(st2.render_history_lines())
    assert "Lisbon" in hist and "home city" in hist and "Chimoio" not in hist


def test_agent_adds_history_lines_on_past_cue_questions(tmp_path):
    engine, _ = make_agent(tmp_path, [{"content": "You lived in Lisbon before.", "tool_calls": []}])
    engine.settings.set("grader_enabled", False)
    engine.facts.apply_all("I live in Lisbon.", "user_explicit"); engine.facts.apply_all("I live in Chimoio now.", "user_explicit")
    captured = {}
    orig = engine._tool_loop
    def spy(messages, *a, **k):
        captured["system"] = messages[0]["content"]; return orig(messages, *a, **k)
    engine._tool_loop = spy
    engine.agent_chat("where did I live before?", session_id=engine.sessions.create_session("h")["id"])
    assert "Lisbon" in captured["system"] and "Before" in captured["system"]


def test_heldout_m3_first_run_findings(tmp_path):
    assert declarative_text("For a story I am writing: my name is Oscar. Anyway, my real name is Nadia Costa.") == "my real name is Nadia Costa."
    assert _active(_store(tmp_path / "k", "For a story I am writing: my name is Oscar. Anyway, my real name is Nadia Costa.")) == {"identity.name": "Nadia Costa"}
    assert _active(_store(tmp_path / "l", "Desde 2019 vivo na Aveiro.")) == {"identity.location": "Aveiro"}
    st = _store(tmp_path / "m", "My cat is Luna and my cat is Sol. They are two different cats.")
    assert _active(st) == {"pet.cat.name": "Luna", "pet.cat.name.2": "Sol"}                 # no duplicate ordinal


def test_write_set_second_run_findings(tmp_path):
    # colon-introduced speech is split by the sentence splitter → the next sentence is a citation
    mods = sentence_modalities("In the book, the hero says: my name is Kael.")
    assert [m["modality"] for m in mods] == ["cite"]
    assert _active(_store(tmp_path / "n", "In the book, the hero says: my name is Kael.")) == {}
    # reported speech with a complementiser is a citation (PT and EN), never first person
    assert sentence_modalities("O meu colega diz que a comida favorita dele é frango.")[0]["modality"] == "cite"
    assert sentence_modalities("My sister told me that her favorite color is red.")[0]["modality"] == "cite"
    assert sentence_modalities("I told you that my name is Ana.")[0]["modality"] == "assert"
    assert _active(_store(tmp_path / "o", "O meu colega diz que a comida favorita dele é frango.")) == {}
    # value canonicalisation: leading article / "called" / trailing "these days" / slash values / PT forms
    assert _active(_store(tmp_path / "p", "My cat is called Mimi.")) == {"pet.cat.name": "Mimi"}
    assert _active(_store(tmp_path / "q", "A minha gata é a Nina.")) == {"pet.cat.name": "Nina"}
    assert _active(_store(tmp_path / "r", "I'm living in Quelimane these days.")) == {"identity.location": "Quelimane"}
    assert _active(_store(tmp_path / "s", "My timezone is Africa/Valencia.")) == {"misc.timezone": "Africa/Valencia"}
    assert _active(_store(tmp_path / "t", "A minha esposa chama-se Lúcia.")) == {"family.partner_name": "Lúcia"}
    assert _active(_store(tmp_path / "u", "Podes tratar-me por Bia.")) == {"identity.alias": "Bia"}
    assert _active(_store(tmp_path / "v", "I work as a data engineer.")) == {"identity.job": "data engineer"}
    assert _active(_store(tmp_path / "w", "Eu sou o Paulo Chissano.")) == {"identity.name": "Paulo Chissano"}
    assert _active(_store(tmp_path / "x", "Imagina que a minha cor favorita é dourado.")) == {}


def test_write_set_v2_heldout_findings(tmp_path):
    assert _active(_store(tmp_path / "a2", "Para o meu romance: chamo-me Vasco e vivo no Porto.")) == {}          # fiction + possessive
    assert _active(_store(tmp_path / "b2", "For a story: my name is Vasco. In reality, my name is Helder Nhantumbo.")) == {"identity.name": "Helder Nhantumbo"}
    assert _active(_store(tmp_path / "c2", "My guess is that the meeting is at 3pm.")) == {}                        # complement clause
    assert _active(_store(tmp_path / "d2", "A minha dúvida é sobre o preço.")) == {}                                # prepositional phrase
    assert _active(_store(tmp_path / "e2", "Here is my car location link: https://example.test/car/9")) == {"asset.car_location_link": "https://example.test/car/9"}
    assert _active(_store(tmp_path / "f2", "O meu prato favorito é caril de caranguejo.")) == {"pref.food": "caril de caranguejo"}
    st = _store(tmp_path / "g2", "O meu primo chama-se Tino e o cão dele é o Rex.")
    assert all(v != "Tino e o cão dele é" for v in _active(st).values())                                          # PT clause cut


def test_write_set_v3_heldout_findings(tmp_path):
    assert _active(_store(tmp_path / "a3", "Podem chamar-me Fina.")) == {"identity.alias": "Fina"}
    assert _active(_store(tmp_path / "b3", "I'm based in Nampula these days.")) == {"identity.location": "Nampula"}
    assert _active(_store(tmp_path / "c3", "A minha mulher chama-se Ester.")) == {"family.partner_name": "Ester"}
    assert _active(_store(tmp_path / "d3", "O link da localização do meu carro é https://example.test/car/78")) == {"asset.car_location_link": "https://example.test/car/78"}
    assert _active(_store(tmp_path / "e3", "Let's pretend my favorite color is silver.")) == {}


def test_history_lines_skip_values_undone_by_a_rollback(tmp_path):
    """72.6g (live replay): a probe value rolled back by a migration row was never true → no 'Before … was Chimoio'."""
    from hmgfu.facts import FactStore
    st = FactStore(str(tmp_path / "h.db"))
    st.apply_all("I live in Lisbon", "user_explicit")
    st.apply_all("I live in Valencia", "user_explicit")
    st.apply_all("I live in Chimoio", "user")                    # the probe
    with st._lock:                                                # the rollback, as Phase 69 recorded it
        cur = st._db.execute("SELECT value FROM canonical_facts WHERE key='identity.location'").fetchone()
        assert cur[0] == "Chimoio"
        st._db.execute("UPDATE canonical_facts SET value='Valencia', prev_value='Chimoio', source='migration' WHERE key='identity.location'")
        st._db.execute("INSERT INTO fact_history (key, value, prev_value, source, op, updated_at, verbatim) VALUES "
                       "('identity.location','Valencia','Chimoio','migration','set','2026-09-05T01:30:50','rollback')")
        st._db.commit()
    lines = st.render_history_lines()
    assert any("Lisbon" in l for l in lines) and not any("Chimoio" in l for l in lines)


def test_reverted_value_is_demoted_even_beside_the_current_value(tmp_path):
    """72.6g (live replay echo loop): an assistant reply "you lived in Lisbon and Chimoio before Valencia" carries the
    rolled-back probe value beside the current one; a REVERTED value was never true, so the node is demoted, while a
    node carrying a merely SUPERSEDED value beside the current one (real history) stays."""
    from hmgfu.facts import FactStore, supersede_stale_nodes
    from hmgfu.models import MemoryPoint
    from hmgfu.store import HMGGraph
    g = HMGGraph(str(tmp_path / "g.db"))
    echo = MemoryPoint(type="message", content="Before Valencia you lived in Lisbon and Chimoio", summary="",
                       source="assistant", embedding=[0.1] * 4)
    history = MemoryPoint(type="message", content="I moved from Lisbon to Valencia in 2021", summary="",
                          source="user", embedding=[0.1] * 4)
    g.save_point(echo); g.save_point(history)
    st = FactStore(str(tmp_path / "f.db"))
    st.apply_all("I live in Lisbon", "user_explicit"); st.apply_all("I live in Valencia", "user_explicit")
    st.apply_all("I live in Chimoio", "user")
    with st._lock:
        st._db.execute("UPDATE canonical_facts SET value='Valencia', prev_value='Chimoio', source='migration' WHERE key='identity.location'")
        st._db.execute("INSERT INTO fact_history (key, value, prev_value, source, op, updated_at, verbatim) VALUES "
                       "('identity.location','Valencia','Chimoio','migration','set','2026-09-05T01:30:50','rollback')")
        st._db.commit()
    assert ("identity.location", "Chimoio") in st.reverted_values()
    supersede_stale_nodes(st, g)
    assert g.points[echo.id].status == "superseded"          # reverted value → demoted despite "Valencia" in the text
    assert g.points[history.id].status == "active"           # superseded value beside the current one = real history


def test_history_timeline_is_the_users_own_line_and_skips_reverted_values(tmp_path):
    """72.6g (live replay echo loop): the timeline reader returns only the user's statements (no assistant echoes), and
    a value undone by a rollback never appears in the timeline, even though superseded values legitimately do."""
    from hmgfu.models import MemoryPoint, QueryPoint
    from hmgfu.retrieve import _history_memories, organise_for_injection
    from hmgfu.store import HMGGraph
    g = HMGGraph(str(tmp_path / "g.db"))
    lisbon = MemoryPoint(type="message", content="I live in Lisbon", summary="", source="user", embedding=[0.1] * 4,
                         status="superseded", timestamp="2026-05-09T09:07:13")
    probe = MemoryPoint(type="message", content="I live in Chimoio. What do you know about that city?", summary="",
                        source="user", embedding=[0.1] * 4, status="superseded", timestamp="2026-09-05T01:29:00")
    echo = MemoryPoint(type="message", content="You have previously lived in Lisbon and Chimoio.", summary="",
                       source="assistant", embedding=[0.1] * 4, status="active", timestamp="2026-09-05T13:18:00")
    for p in (lisbon, probe, echo):
        g.save_point(p)
    items = _history_memories(QueryPoint(text="where did I live before?", embedding=[0.1] * 4), g, limit=10)
    assert {i.point.id for i in items} == {lisbon.id, probe.id}                 # the assistant echo is not the line
    inj = organise_for_injection(items, g, reverted=[("identity.location", "Chimoio")])
    timeline = " ".join(inj["subjectTimeline"])
    assert "Lisbon" in timeline and "Chimoio" not in timeline
