"""Phase 90.G2 — the three real undue writes the it.1 prompt produced on the sealed sets (D3) must be stopped at the deterministic side,
without touching correct writes: (1) an employer must be a proper name — "district hospital" / "logistics firm" are descriptions, not
companies; (2) a value the regex already wrote this message under another slot is not a second fact ("Hi there, Bernardo here." →
regex identity.name=Bernardo; the model's nickname=Bernardo is a duplicate, not an alias). No model call."""
from __future__ import annotations

from hmgfu.fact_spans import apply_spans, extract_spans


def _fake(facts):
    return lambda prompt, schema: {"facts": facts}


def test_generic_employer_descriptions_are_not_companies():
    dets = extract_spans("I work as a nurse at the district hospital.",
                         _fake([{"attribute": "job", "value": "nurse"}, {"attribute": "employer", "value": "district hospital"}]))
    assert [(d["key"], d["value"]) for d in dets] == [("identity.job", "nurse")]
    dets = extract_spans("I work as a truck driver for a logistics firm.",
                         _fake([{"attribute": "job", "value": "truck driver"}, {"attribute": "employer", "value": "a logistics firm"}]))
    assert [(d["key"], d["value"]) for d in dets] == [("identity.job", "truck driver")]


def test_proper_name_employers_still_pass():
    for text, val in [("I'm employed at Millennium bim as a teller.", "Millennium bim"),
                      ("I've started working at Standard Bank.", "Standard Bank"),
                      ("Trabalho na Hidroeléctrica de Cahora Bassa.", "Hidroeléctrica de Cahora Bassa")]:
        dets = extract_spans(text, _fake([{"attribute": "employer", "value": val}]))
        assert ("identity.company", val) in [(d["key"], d["value"]) for d in dets], text


def test_a_value_the_regex_already_wrote_is_not_a_second_fact(tmp_path):
    from hmgfu.facts import FactStore
    store = FactStore(str(tmp_path / "f.db"))
    text = "Hi there, Bernardo here."
    changes = store.apply_all(text, "user_explicit")
    assert any(c.get("key") == "identity.name" and c.get("value") == "Bernardo" for c in changes)
    extractor = lambda t: extract_spans(t, _fake([{"attribute": "nickname", "value": "Bernardo"}]))
    added = apply_spans(store, text, "user_explicit", extractor,
                        skip_keys=[c["key"] for c in changes if c.get("key")], skip_values=[c.get("value") for c in changes if c.get("value")])
    assert added == []
    assert not any(r["key"] == "identity.alias" for r in store.active())
