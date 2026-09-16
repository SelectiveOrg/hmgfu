"""FASE B — the hex viz shows the REAL system: /api/graph/viz's _reg_fields emits the true Regulator
state/c/ledger ONLY when the Regulator is live (else {} → the viz falls back, byte-identical off)."""

from hmgfu import config
from hmgfu.routes.memory import _reg_fields
from tests.test_v2_agent import make_agent


def test_reg_fields_empty_when_off(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "REGULATOR_ENABLED", False)
    engine, _ = make_agent(tmp_path, [])
    p = engine.ingest("facto qualquer", source="user")
    assert _reg_fields(engine, p.id) == {}          # off → nothing added → viz unchanged


def test_reg_fields_real_states_when_on(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "REGULATOR_ENABLED", True)
    engine, _ = make_agent(tmp_path, [])
    temp = engine.ingest("a", source="user")        # empty ledger → c 0.40 → TEMP
    cand = engine.ingest("b", source="user")
    fact = engine.ingest("c", source="user")
    engine.regulator.transition(cand.id, "explicit")            # c 0.70 → CANDIDATE
    engine.regulator.transition(fact.id, "explicit")
    engine.regulator.transition(fact.id, "explicit")           # c 1.00 + explicit → FACT

    assert _reg_fields(engine, temp.id)["state"] == "temp"
    assert _reg_fields(engine, cand.id)["state"] == "candidate"
    f = _reg_fields(engine, fact.id)
    assert f["state"] == "fact" and f["c"] >= 0.80
    assert f["ledger"]["explicit"] == 2             # the internal-hex source is the REAL ledger


def test_reg_fields_successor_link_when_superseded(tmp_path, monkeypatch):
    """B2: a SUPERSEDED node exposes `superseded_by` derived from the REAL contradiction edge
    (dream.mark_tension), so the viz can draw a link to the successor — no faked field."""
    from hmgfu.dream import mark_tension
    monkeypatch.setattr(config, "REGULATOR_ENABLED", True)
    engine, _ = make_agent(tmp_path, [])
    wrong = engine.ingest("o meu carro e um Toyota", source="user")
    right = engine.ingest("o meu carro e um Honda", source="user_explicit")
    mark_tension({"a": wrong.id, "b": right.id, "score": 0.9,
                  "resolution": {"winner": right.id, "loser": wrong.id}}, engine.graph)
    engine.regulator.transition(wrong.id, "correction")
    f = _reg_fields(engine, wrong.id)
    assert f["state"] == "superseded"
    assert f.get("superseded_by", {}).get("id") == right.id
    assert _reg_fields(engine, right.id).get("superseded_by") is None   # the survivor has no successor
