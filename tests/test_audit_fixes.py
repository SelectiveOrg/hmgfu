"""Regression tests for the full-code-audit remediation (reports/full_code_audit_2026-07-04).

One test per behavioral finding fixed. Pure/isolated where possible; make_agent (fake model,
no Ollama) for the ones needing an engine. Concurrency (H-04), the WS terminal event (M-05),
and the frontend fixes (M-09) are verified live, not here.
"""

import pytest

from hmgfu import fu_math
from hmgfu.directives import detect_output_directive
from hmgfu.facts import detect_fact
from hmgfu.grader import _apply_memory_grades, _correction_grounded
from hmgfu.models import Hex, MemoryPoint, RetrievedMemory
from hmgfu.plans import plan_action
from hmgfu.sessions import SessionStore
from hmgfu.settings import Settings
from hmgfu.store import HMGGraph
from hmgfu.tool_builtins import set_workspace, write_file
from hmgfu.toolsys import _run_coroutine
from tests.test_v2_agent import make_agent


# --- H-05: ordinary "I am …" must NOT overwrite the canonical name ---------------------
def test_h05_copula_is_not_a_name():
    for phrase in ("I am happy to be here", "I am working on the project",
                   "I am very tired today", "I'm just looking around", "I am going home"):
        assert detect_fact(phrase) is None, phrase
    # real declarations still work
    assert detect_fact("I am Teodoro")["value"] == "Teodoro"
    det = detect_fact("my name is Sebastian")     # R2 (95.12): the explicit form is also TRUSTED at the store
    assert {k: det[k] for k in ("key", "value", "supersedes")} == {"key": "name", "value": "Sebastian", "supersedes": None}
    assert det.get("trusted") is True
    assert detect_fact("call me Teo")["value"] == "Teo"          # Phase 62: routed to identity.alias
    # negation still clears
    assert detect_fact("I'm not Sebastian") == {"key": "name", "clear_value": "Sebastian"}


# --- H-06: ordinary task language must NOT create output directives --------------------
def test_h06_task_language_is_not_a_directive():
    for phrase in ("finish the project with Python", "start my day with coffee",
                   "conclude the report with evidence", "begin the meeting with introductions"):
        assert detect_output_directive(phrase) is None, phrase
    # genuine standing directives still detected
    assert detect_output_directive("always end every reply with the word Capitao") == \
        {"kind": "output_suffix", "value": "Capitao"}
    assert detect_output_directive("begin each response with Hello") == \
        {"kind": "output_prefix", "value": "Hello"}


# --- M-06: timestamps compared as real UTC instants, not strings -----------------------
def test_m06_offset_timestamps_compared_chronologically():
    # 10:00+05:00 is 05:00Z — OLDER than 08:00+00:00; a string compare gets this backwards
    assert fu_math.compare_ts("2026-07-04T10:00:00+05:00", "2026-07-04T08:00:00+00:00") < 0
    assert fu_math.compare_ts("2026-07-04T08:00:00+00:00", "2026-07-04T10:00:00+05:00") > 0
    assert fu_math.compare_ts("2026-07-04T08:00:00+00:00", "2026-07-04T08:00:00+00:00") == 0


# --- M-03: moving a point frees the old occupied hex cell ------------------------------
def test_m03_move_frees_old_hex_cell(tmp_path):
    g = HMGGraph(db_path=str(tmp_path / "s.db"))
    p = MemoryPoint(hex=Hex(0, 0, 0))
    g.save_point(p)
    assert g.occupied.get("0,0,0") == p.id
    p.hex = Hex(1, -1, 0)          # same object mutated in place (the real call pattern)
    g.save_point(p)
    assert "0,0,0" not in g.occupied          # old cell released (was leaking before)
    assert g.occupied.get("1,-1,0") == p.id
    g.close()


# --- H-04: locked snapshot readers exist and materialize -------------------------------
def test_h04_snapshot_readers(tmp_path):
    g = HMGGraph(db_path=str(tmp_path / "s.db"))
    for i in range(5):
        g.save_point(MemoryPoint(hex=Hex(i, -i, 0)))
    assert isinstance(g.all_points(), list) and len(g.all_points()) == 5
    assert isinstance(g.all_edges(), list)
    assert len(g.active_points()) == 5
    g.close()


# --- M-02: history returns the NEWEST rows, in ascending order -------------------------
def test_m02_history_keeps_newest(tmp_path):
    s = SessionStore(db_path=str(tmp_path / "s.db"))
    sid = s.create_session()["id"]
    for i in range(205):
        s.save_message(sid, "user", f"m{i:03d}", turn_seq=i)
    h = s.history(sid, limit=200)
    assert len(h) == 200
    assert h[-1]["content"] == "m204"      # newest present (was dropped before)
    assert h[0]["content"] == "m005"       # oldest 5 dropped; ascending display order


# --- M-04: settings reject bad ranges and apply patches atomically ---------------------
def test_m04_settings_range_and_atomic(tmp_path):
    s = Settings(db_path=str(tmp_path / "s.db"))
    with pytest.raises(ValueError):
        s.set("retrieval_limit", -5)
    with pytest.raises(ValueError):
        s.set("thinking_mode", "bogus")
    before = s.get("retrieval_limit")
    with pytest.raises(KeyError):
        s.update({"retrieval_limit": 7, "nonexistent_key": 1})
    assert s.get("retrieval_limit") == before     # atomic: the valid key was NOT half-applied


# --- H-02: write_file cannot escape the workspace, even overwriting an existing file ----
def test_h02_write_stays_in_workspace(tmp_path):
    ws = tmp_path / "workspace"; ws.mkdir()
    outside = tmp_path / "outside.txt"; outside.write_text("original")
    set_workspace(str(ws))
    try:
        r = write_file(str(outside), "HACKED")
        assert r.get("blocked")                    # existing external file NOT overwritten
        assert outside.read_text() == "original"
        r2 = write_file("inside.txt", "ok")
        assert not r2.get("blocked") and (ws / "inside.txt").read_text() == "ok"
    finally:
        set_workspace(None)


# --- L-05: plan update rejects a negative step index -----------------------------------
def test_l05_update_plan_rejects_negative_index(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    engine._turn_emit = lambda ev: None
    engine._turn_plan = {"title": "t", "steps": [
        {"text": "a", "status": "active"}, {"text": "b", "status": "pending"}]}
    r = plan_action(engine, "update_plan", {"step": -1, "status": "done"})
    assert "error" in r
    assert engine._turn_plan["steps"][-1]["status"] == "pending"   # last step untouched


# --- M-07: async skill handler runs in a loopless (worker-thread-like) caller ----------
def test_m07_async_handler_runs():
    async def handler():
        return "async-ok"
    assert _run_coroutine(handler()) == "async-ok"


# --- M-17: grader ignores out-of-range indices; correction must be grounded ------------
def test_m17_memory_grade_index_bounds(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    p = engine.ingest("I love hiking in the mountains", source="user")
    item = RetrievedMemory(point=engine.graph.points[p.id], score=0.5)
    u0 = item.point.utility
    n = _apply_memory_grades(engine, [item], [{"index": -1, "grade": "cited"},
                                              {"index": 5, "grade": "cited"}])
    assert n == [] and abs(item.point.utility - u0) < 1e-9   # negative/oob ignored (P3: list return)
    n2 = _apply_memory_grades(engine, [item], [{"index": 0, "grade": "cited"}])
    assert len(n2) == 1 and item.point.utility > u0          # valid index applied


def test_m17_correction_must_be_grounded():
    assert _correction_grounded({"right": "cat is Shadow"}, "actually my cat is Shadow now")
    assert _correction_grounded({"right": "Shadow", "wrong": "Nimbus"}, "my cat is Shadow")
    assert not _correction_grounded({"right": "you love pizza"}, "what is the weather today")
