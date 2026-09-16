"""Phase 61a — the inert-wiring guards, AS ENFORCED TESTS (not doctrine).

GUARD 3 (Invariant A1): the lifecycle state-pill is DISPLAY-ONLY. It is appended to the rendered
prompt text after ranking is closed and must re-enter NO scoring path. Enforced two ways: (a) rendering
the pill invokes ZERO calls to fu_math.memory_score / memory_score_components; (b) turning the pill on
changes ONLY the text (each line gains a suffix), never the retrieved scores.

GUARD 2 (inertness): with config.REGULATOR_ENABLED False the wiring is byte-identical — no pill in the
context and no `lc:` ledger key is ever written. The flip only becomes observable when the flag is on.

These run without Ollama (fake embedder via make_agent), like the rest of the suite.
"""

from hmgfu import config, fu_math
from hmgfu.models import RetrievedMemory
from hmgfu.retrieve import organise_for_injection, render_injection
from tests.test_v2_agent import make_agent


class _FakeReg:
    """A regulator stand-in returning a fixed (confidence, state) — decouples the A1/display tests
    from ledger arithmetic (that is proven in test_regulator_i1.py)."""

    def __init__(self, state):
        self._state = state

    def evaluate(self, pid):
        return (0.9, self._state)


def _two_facts(engine):
    a = engine.ingest("Project uses Google Maps", source="user")
    b = engine.ingest("Project uses OpenStreetMap now", source="user")
    pa, pb = engine.graph.points[a.id], engine.graph.points[b.id]
    for p in (pa, pb):
        p.type = "fact"
        p.timestamp = "2026-01-01T00:00:00+00:00"
        engine.graph.save_point(p)
    return [RetrievedMemory(point=pa, score=0.5, reason=""),
            RetrievedMemory(point=pb, score=0.6, reason="")]


# --- GUARD 3 (A1) ---------------------------------------------------------------------------------
def test_a1_pill_rendering_invokes_zero_scoring(tmp_path, monkeypatch):
    """A1, enforced: building + rendering the pill must call NO ranking function. If a future edit
    routes the pill through scoring, `calls` becomes non-empty and this fails."""
    engine, _ = make_agent(tmp_path, [])
    retrieved = _two_facts(engine)
    calls = []
    monkeypatch.setattr(fu_math, "memory_score", lambda *a, **k: calls.append("score") or 0.0)
    monkeypatch.setattr(fu_math, "memory_score_components",
                        lambda *a, **k: calls.append("components") or {})
    inj = organise_for_injection(retrieved, engine.graph, regulator=_FakeReg("fact"))
    render_injection(inj)
    assert calls == [], f"A1 VIOLATED: pill path invoked scoring {calls}"


def test_a1_pill_changes_only_text_not_scores(tmp_path):
    """Turning the pill on changes ONLY the rendered text (each line gains the suffix); the retrieved
    scores are untouched — the pill cannot influence rank."""
    engine, _ = make_agent(tmp_path, [])
    retrieved = _two_facts(engine)
    scores_before = [r.score for r in retrieved]
    inj_off = organise_for_injection(retrieved, engine.graph, regulator=None)
    inj_on = organise_for_injection(retrieved, engine.graph, regulator=_FakeReg("candidate"))
    assert [r.score for r in retrieved] == scores_before          # scores frozen
    off = inj_off["relevantFacts"]
    on = inj_on["relevantFacts"]
    assert len(off) == len(on)
    for lo, ln in zip(off, on):
        assert ln == f"{lo}  [CANDIDATE]"                          # only difference is the pill


# --- GUARD 2 (inertness) --------------------------------------------------------------------------
def test_guard2_regulator_none_has_no_pill(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    inj = organise_for_injection(_two_facts(engine), engine.graph, regulator=None)
    blob = "\n".join(inj["relevantFacts"])
    for tag in ("[FACT]", "[CANDIDATE]", "[TEMP]", "[SUPERSEDED]"):
        assert tag not in blob


def test_guard2_flag_off_writes_no_ledger(tmp_path, monkeypatch):
    """With the flag OFF, a user_explicit ingest (the strongest signal) writes ZERO `lc:` keys."""
    monkeypatch.setattr(config, "REGULATOR_ENABLED", False)
    engine, _ = make_agent(tmp_path, [])
    engine.ingest("My name is Alex", source="user_explicit")
    lc = [k for k in engine.learned_params._cache if k.startswith("lc:")]
    assert lc == [], f"inertness VIOLATED: ledger keys written while OFF: {lc}"


def test_flag_on_explicit_signal_records(tmp_path, monkeypatch):
    """The other side of the gate: with the flag ON, user_explicit ingest records exactly one
    explicit signal (evidence the wiring is live when flipped — the 'allowed to flip' proof)."""
    monkeypatch.setattr(config, "REGULATOR_ENABLED", True)
    engine, _ = make_agent(tmp_path, [])
    p = engine.ingest("My name is Alex", source="user_explicit")
    led = engine.regulator.ledger(p.id)
    assert led["explicit"] == 1
    assert led["correction"] is False


# --- correction-hook correctness (verify-refuter regression) --------------------------------------
def test_correction_marks_only_the_superseded_point(tmp_path):
    """REGRESSION (verify-refuter, CONFIRMED bug): the absorbing 'correction' signal must fire ONLY
    on the point the graph ACTUALLY superseded — never a surviving fact, even when it is the other
    member of the contradiction pair. The old code assumed 'the other id lost' and poisoned survivors."""
    from hmgfu.grader import _record_correction_signals
    engine, _ = make_agent(tmp_path, [])
    a = engine.ingest("I'm called Alice", source="user_explicit")     # survives
    b = engine.ingest("I'm Alison", source="user")
    pb = engine.graph.points[b.id]
    pb.status = "superseded"                                            # only b actually superseded
    engine.graph.save_point(pb)
    _record_correction_signals(engine, {"a": a.id, "b": b.id})
    assert engine.regulator.ledger(b.id)["correction"] is True         # the superseded one → absorbed
    assert engine.regulator.ledger(a.id)["correction"] is False        # surviving fact NOT poisoned


def test_correction_no_supersession_records_nothing(tmp_path):
    """When mark_tension supersedes NOTHING (unclear resolution → no clear user_explicit winner),
    ZERO correction signals are recorded — the exact case the old unconditional hook mishandled."""
    from hmgfu.grader import _record_correction_signals
    engine, _ = make_agent(tmp_path, [])
    a = engine.ingest("claim one", source="user")
    b = engine.ingest("claim two", source="user")                      # both remain active
    _record_correction_signals(engine, {"a": a.id, "b": b.id})
    assert engine.regulator.ledger(a.id)["correction"] is False
    assert engine.regulator.ledger(b.id)["correction"] is False
