"""Phase 84.3 — the span-extractor contract: the model lists {attribute, value}; everything that protects precision stays
deterministic (grounding, predicates, third parties, closed slots, name gate, regex-first merge, cardinality, modality)."""
from __future__ import annotations

from hmgfu.fact_spans import apply_spans, extract_spans
from hmgfu.facts import FactStore


def _fake(facts):
    """A chat_json stand-in returning the given facts whatever the prompt."""
    return lambda prompt, schema: {"facts": facts}


def test_grounding_predicates_third_parties_and_closed_slots():
    text = "You'll always find me in lilac; my neighbour's dog is Rex; my guess is Manica; I drive a Nissan Navara."
    dets = extract_spans(text, _fake([
        {"attribute": "favourite colour", "value": "lilac"},          # grounded, closed slot
        {"attribute": "favourite colour", "value": "purple"},         # NOT in the text → dropped
        {"attribute": "neighbour's dog", "value": "Rex"},             # third party → dropped
        {"attribute": "guess", "value": "Manica"},                    # open key → dropped (closed slots only)
        {"attribute": "car", "value": "Nissan Navara"},               # closed slot
        {"attribute": "internet", "value": "slow"},                   # predicate value → dropped (and open)
    ]))
    assert [(d["key"], d["value"], d["path"]) for d in dets] == [("pref.color", "lilac", "spans"), ("asset.car", "Nissan Navara", "spans")]


def test_value_class_decides_when_the_attribute_is_vague():
    dets = extract_spans("These days it's all Rust for me.", _fake([{"attribute": "language I use", "value": "Rust"}]))
    assert dets and dets[0]["key"] == "pref.language"
    dets = extract_spans("Nothing beats mustard yellow.", _fake([{"attribute": "what I like", "value": "mustard yellow"}]))
    assert dets and dets[0]["key"] == "pref.color"


def test_apply_spans_adds_only_what_the_regex_missed_and_respects_modality(tmp_path):
    st = FactStore(str(tmp_path / "f.db"))
    text = "My favourite colour is amber and I answer to Kiki."
    regex_changes = st.apply_all(text, "user_explicit")
    assert {c["key"] for c in regex_changes} == {"pref.color"}
    extractor = lambda t: [{"key": "pref.color", "value": "amber", "supersedes": None, "path": "spans"},
                           {"key": "identity.alias", "value": "Kiki", "supersedes": None, "path": "spans"}]
    ch = apply_spans(st, text, "user_explicit", extractor, skip_keys=[c["key"] for c in regex_changes])
    assert [(c["key"], c["value"], c["path"]) for c in ch] == [("identity.alias", "Kiki", "spans")]
    # a hypothetical sentence never reaches the extractor (the store's modality rules apply first)
    calls = []
    def spy(t):
        calls.append(t); return []
    assert apply_spans(st, "If I lived in Nacala I'd fish every weekend.", "user_explicit", spy) == [] and calls == []
    assert apply_spans(st, "Imagine my dog were called Rex.", "user_explicit", spy) == [] and calls == []


def test_apply_spans_cardinality_and_name_gate(tmp_path):
    st = FactStore(str(tmp_path / "g.db"))
    text = "Two dogs at home: Luna and Mel."
    extractor = lambda t: [{"key": "pet.dog.name", "value": "Luna", "supersedes": None, "path": "spans"},
                           {"key": "pet.dog.name", "value": "Mel", "supersedes": None, "path": "spans"}]
    ch = apply_spans(st, text, "user_explicit", extractor)
    assert {c["key"]: c["value"] for c in ch} == {"pet.dog.name": "Luna", "pet.dog.name.2": "Mel"}
    st2 = FactStore(str(tmp_path / "h.db"))
    bad = lambda t: [{"key": "identity.name", "value": "easy to spell", "supersedes": None, "path": "spans"}]
    assert apply_spans(st2, "My name is easy to spell.", "user_explicit", bad) == []           # name-shape gate holds


def test_extractor_failure_is_advisory():
    def boom(prompt, schema):
        raise RuntimeError("model down")
    assert extract_spans("My name is Ana.", boom) == []


def test_third_party_sentences_never_reach_the_extractor(tmp_path):
    from hmgfu.value_gate import third_party_sentence
    for s in ["Our neighbour Rui drives a Hilux.", "My cousin's favourite drink is Laurentina.", "Aunt Rosa lives in Gurué.",
              "A bebida favorita do meu primo é Laurentina.", "My boss lives in Dondo.", "A nossa chefe mora no Dondo."]:
        assert third_party_sentence(s), s
    for s in ["I drive a Nissan Navara.", "My favourite drink is Laurentina.", "My sister is Carla.", "Moro no Dondo."]:
        assert not third_party_sentence(s), s
    st = FactStore(str(tmp_path / "t.db"))
    calls = []
    def spy(t):
        calls.append(t); return []
    apply_spans(st, "Our neighbour Rui drives a Hilux. I drive a Nissan Navara.", "user_explicit", spy)
    assert calls == ["I drive a Nissan Navara."]


def test_dev_findings_fixed_at_the_deterministic_side(tmp_path):
    assert [(d["key"], d["value"]) for d in extract_spans("The car is a Mazda BT-50.", _fake([{"attribute": "car", "value": "a Mazda BT-50"}]))] == [("asset.car", "Mazda BT-50")]
    assert extract_spans("Car tracker: https://gps.example.test/car/77", _fake([{"attribute": "car", "value": "https://gps.example.test/car/77"}])) == []
    assert extract_spans("I'm from Spain originally.", _fake([{"attribute": "where I'm from", "value": "Spain"}])) == []
    assert [(d["key"], d["value"]) for d in extract_spans("Corrijo: trabalho na EDM.", _fake([{"attribute": "trabalho", "value": "EDM"}]))] == [("identity.company", "EDM")]
    assert [(d["key"], d["value"]) for d in extract_spans("I work as a welder.", _fake([{"attribute": "work as", "value": "welder"}]))] == [("identity.job", "welder")]
    from hmgfu.utterance import declarative_text
    assert declarative_text("Dantes a minha cor era o coral.") == "" and declarative_text("Outrora vivia em Tete.") == ""


def test_name_of_a_relation_and_family_skip(tmp_path):
    assert [(d["key"], d["value"]) for d in extract_spans("O nome do meu gato é Tigre.", _fake([{"attribute": "nome", "value": "Tigre"}]))] == [("pet.cat.name", "Tigre")]
    st = FactStore(str(tmp_path / "n.db"))
    st.apply_all("My dog is Simba.", "user_explicit")
    text = "I got a second dog; her name is Nala."
    regex_changes = st.apply_all(text, "user_explicit")
    assert [c["key"] for c in regex_changes] == ["pet.dog.name.2"]
    ext = lambda t: [{"key": "pet.dog.name", "value": "Nala", "supersedes": None, "path": "spans"}]
    assert apply_spans(st, text, "user_explicit", ext, skip_keys=[c["key"] for c in regex_changes]) == []
    assert {r["key"]: r["value"] for r in st.active()} == {"pet.dog.name": "Simba", "pet.dog.name.2": "Nala"}
