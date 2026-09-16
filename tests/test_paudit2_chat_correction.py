"""P-AUDIT-2/3 — the chat-model correction signal (THEORY_V3 B.5) + FRONT 0/1/2, as enforced tests.
No Ollama: the registry's chat_for_role is mocked so the constrained correction call is deterministic.

Guards: flag OFF ⇒ nano path (production byte-identical); flag ON ⇒ nano LEAVES the hot path (FRONT 0),
correction is DEFERRED to the GPU-free queue (FRONT 2) and disabled on action turns; the message is split
into clauses so a buried correction can't hide (FRONT 1).
"""

import json

from hmgfu import config
from hmgfu.grader import _detect_correction_via_chat, _split_clauses, facts_summary, grade_turn
from hmgfu.models import RetrievedMemory
from tests.test_v2_agent import make_agent


class _Q:
    def __init__(self, action=False, tools=None):
        self.action_requested = action
        self.requested_tools = tools or []


def _mock_registry(engine, correction_payload):
    """chat_for_role: a call carrying the correction schema → correction_payload; anything else → benign."""
    def fake(role, messages, json_mode=False, temperature=0.4, tools=None, format_schema=None, think=None):
        if format_schema is not None and "is_correction" in (format_schema.get("properties") or {}):
            return {"content": correction_payload, "tool_calls": [], "thinking": ""}
        return {"content": json.dumps({"memory_grades": [], "user_correction": None, "turn_score": 0.5}),
                "tool_calls": [], "thinking": ""}
    engine.registry.chat_for_role = fake


def test_action_turn_no_longer_skips_detection():
    """P0.1 (Plan.txt): _is_action_turn is GONE — the B.5 action-skip predated FRONT-2 deferral;
    detection is a separate post-reply call, so every turn enqueues (see the grade_turn test)."""
    import hmgfu.grader as g
    assert not hasattr(g, "_is_action_turn")           # dead code removed (Rule 15)


# --- FRONT 1: mechanical clause partition (buried fix) --------------------------------------------
def test_split_clauses_buried():
    msg = ("epah choveu bue hoje e perdi o jogo do ferroviario. a proposito ja nao moro em quelimane, "
           "mudei pra nicoadala. enfim depois falamos")
    clauses = _split_clauses(msg)
    assert any("nicoadala" in c.lower() for c in clauses)   # the buried correction is isolated as a clause
    assert any("choveu" in c.lower() for c in clauses)       # the surrounding topic is separated out
    assert len(clauses) >= 3
    assert _split_clauses("") == [""]                        # degenerate input never crashes


def test_facts_summary(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    p = engine.ingest("o meu nome e Zeca", source="user")
    s = facts_summary([RetrievedMemory(point=engine.graph.points[p.id], score=0.9, reason="")])
    assert isinstance(s, str) and len(s) > 0
    assert facts_summary([]) == ""


def test_detect_correction_via_chat(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    _mock_registry(engine, json.dumps({"is_correction": True, "right": "Nelito", "wrong": "Nelson"}))
    assert _detect_correction_via_chat(engine, "nao, e Nelito", "ok", "") == {"right": "Nelito", "wrong": "Nelson"}
    _mock_registry(engine, json.dumps({"is_correction": False, "right": "", "wrong": ""}))
    assert _detect_correction_via_chat(engine, "ah ok", "sure", "") is None
    _mock_registry(engine, json.dumps({"is_correction": True, "right": "", "wrong": "Nelson"}))
    assert _detect_correction_via_chat(engine, "hmm", "ok", "") is None   # a correction must name the new value


# --- FRONT 0 + FRONT 2: flag ON ⇒ nano out, correction deferred to the queue -----------------------
def test_grade_turn_deferred_when_flag_on(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CHAT_CORRECTION_SIGNAL", True)
    engine, _ = make_agent(tmp_path, [])
    engine.ingest("o meu nome e Nelson", source="user")
    _mock_registry(engine, json.dumps({"is_correction": True, "right": "Nelito", "wrong": "Nelson"}))
    grade = grade_turn(engine, "nao pa, o meu nome e Nelito nao Nelson", "Peco desculpa, Nelito", [], [],
                       query=_Q(action=False))
    assert grade["correction_source"] == "deferred"
    assert grade["correction"] is None                 # deferred — NOT applied inline
    assert grade["producer"] == "chat-front0"          # FRONT 0: the grader nano is out of the hot path
    assert len(engine._correction_queue) == 1
    results = engine.drain_corrections()               # FRONT 2: drain when GPU-free
    assert results[0]["correction"] is not None        # detected + applied on drain (grounded: values in-message)
    assert engine._correction_queue == []


def test_grade_turn_action_turn_enqueues_when_flag_on(tmp_path, monkeypatch):
    """P0.1: flag ON + an ACTION turn ⇒ the correction is ENQUEUED like any turn (the router
    intermittently ACTION-classifies real corrections; the old skip lost them). Latency guard:
    grade_turn itself makes NO detector call — detection happens only at the post-reply drain."""
    monkeypatch.setattr(config, "CHAT_CORRECTION_SIGNAL", True)
    engine, _ = make_agent(tmp_path, [])
    engine.ingest("moro em Valencia", source="user")
    _mock_registry(engine, json.dumps({"is_correction": True, "right": "Aveiro", "wrong": "Valencia"}))
    grade = grade_turn(engine, "corrige ai: eu moro na Aveiro, nao em Valencia", "ok, corrigido",
                       [], [{"name": "memory_search", "failed": False}],
                       query=_Q(action=True, tools=["memory_search"]))
    assert grade["correction_source"] == "deferred"    # no more action-skip
    assert grade["correction"] is None                 # NOT detected inline (no call in grade_turn)
    assert len(engine._correction_queue) == 1          # enqueued for the GPU-free drain
    results = engine.drain_corrections()               # detection fires only here (post-reply)
    assert results[0]["correction"] is not None


def test_grade_turn_nano_when_flag_off(tmp_path, monkeypatch):
    """Flag OFF ⇒ the nano grader runs, nothing deferred (production byte-identical)."""
    monkeypatch.setattr(config, "CHAT_CORRECTION_SIGNAL", False)
    engine, _ = make_agent(tmp_path, [])
    _mock_registry(engine, json.dumps({"is_correction": True, "right": "X", "wrong": "Y"}))  # must be ignored
    grade = grade_turn(engine, "ah ok fixe", "sure", [], [], query=_Q())
    assert grade["correction_source"] == "nano"
    assert grade["correction"] is None
    assert engine._correction_queue == []


def test_drain_corrections_direct(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    engine.ingest("moro em quelimane", source="user")
    _mock_registry(engine, json.dumps({"is_correction": True, "right": "Nicoadala", "wrong": "Quelimane"}))
    engine.enqueue_correction("mudei pra nicoadala, ja nao quelimane", "ok", "moro em quelimane")
    results = engine.drain_corrections()
    assert len(results) == 1 and results[0]["source"] == "chat"
    assert results[0]["correction"] is not None


def test_emit_correction_fires_live_viz_event(tmp_path, monkeypatch):
    """B5: an applied chat-correction, drained while the turn emitter is live, fires exactly ONE
    `correction` WS event (REUSING engine._emit — Rule 5) so the hex viz reacts; the frontend
    events.jsx `case "correction"` refetches the real lifecycle + records the feed."""
    monkeypatch.setattr(config, "REGULATOR_ENABLED", True)
    engine, _ = make_agent(tmp_path, [])
    engine.ingest("moro em quelimane", source="user")
    events = []
    engine._emit = lambda ev: events.append(ev)      # the same WS channel agent.py wires per turn
    engine._turn_emit = True                          # emitter live (inside a turn)
    _mock_registry(engine, json.dumps({"is_correction": True, "right": "Nicoadala", "wrong": "Quelimane"}))
    engine.enqueue_correction("mudei pra nicoadala, ja nao quelimane", "ok", "moro em quelimane")
    engine.drain_corrections(apply=True)
    corr = [e for e in events if e.get("type") == "correction"]
    assert len(corr) == 1
    assert corr[0]["pid"] and corr[0]["right"] == "Nicoadala" and corr[0]["wrong"] == "Quelimane"
    assert "state" in corr[0] and "c" in corr[0]


def test_emit_correction_silent_when_no_turn_emitter(tmp_path, monkeypatch):
    """Fail-soft: outside a live turn (no _turn_emit) the drain still applies but emits nothing."""
    monkeypatch.setattr(config, "REGULATOR_ENABLED", True)
    engine, _ = make_agent(tmp_path, [])
    engine.ingest("moro em quelimane", source="user")
    events = []
    engine._emit = lambda ev: events.append(ev)
    engine._turn_emit = False                          # no live turn → no viz event
    _mock_registry(engine, json.dumps({"is_correction": True, "right": "Nicoadala", "wrong": "Quelimane"}))
    engine.enqueue_correction("mudei pra nicoadala", "ok", "moro em quelimane")
    engine.drain_corrections(apply=True)
    assert [e for e in events if e.get("type") == "correction"] == []


def test_observation_window(tmp_path, monkeypatch):
    """P-AUDIT-3b: with OBSERVE_FIRST_N>0, an applied correction logs source+ledger for spot-audit."""
    import json as _json
    from pathlib import Path
    monkeypatch.setattr(config, "OBSERVE_FIRST_N", 5)
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "agent.db"))
    engine, _ = make_agent(tmp_path, [])
    engine.ingest("moro em quelimane", source="user")
    _mock_registry(engine, json.dumps({"is_correction": True, "right": "Nicoadala", "wrong": "Quelimane"}))
    engine.enqueue_correction("mudei pra nicoadala", "ok", "moro em quelimane")
    engine.drain_corrections(apply=True)
    obs = Path(config.DB_PATH).with_name("observation_log.jsonl")
    assert obs.exists()
    entry = _json.loads(obs.read_text(encoding="utf-8").splitlines()[0])
    assert entry["source"] == "chat" and entry["n"] == 1 and "ledger" in entry
