"""95.54b (X5 on v5: g5cand 0/3, d95w16v5 rep1 0/1) — an enumerated multi-request is planned by the harness.

"Dois pedidos. 1. Cria memorando.md com o texto MEMORANDO-IBIS. 2. 5566778899." — on v4 the model
called plan_task itself (3/3) and the garbage item was rejected in place; on v5 it never did (write_file
once, bash three times), so no step could be rejected and the plan tool's validation (94.3b, 95.4) never
ran. The harness now plans the turn through the same handler before the model acts. Positive: the plan
exists with one rejected step (with its reason) and the model sees the pinned block; the file is still
written and the step is done on its receipt. Preserve: a single request plans nothing; a question list
plans nothing; a pending proposal is left alone; a prohibited turn plans nothing.
"""
from __future__ import annotations

import pytest

from hmgfu import tool_builtins
from hmgfu.session_plans import propose
from tests.test_v2_agent import make_agent

X5 = "Dois pedidos. 1. Cria memorando.md com o texto MEMORANDO-IBIS. 2. 5566778899."
WRITE = {"content": "", "tool_calls": [{"name": "write_file", "arguments": {"path": "memorando.md", "content": "MEMORANDO-IBIS"}}]}
REPORT = {"content": "Criei o memorando.md com o texto MEMORANDO-IBIS.", "tool_calls": []}


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setattr(tool_builtins, "get_workspace", lambda: str(tmp_path))
    return tmp_path


def _agent(path, script):
    engine, fake = make_agent(path, script)
    return engine, fake, engine.sessions.create_session()["id"]


def _rejected(plan):
    return [s for s in (plan or {}).get("steps") or [] if s.get("status") == "rejected"]


def test_the_enumerated_request_is_planned_and_the_garbage_item_is_rejected(ws, tmp_path):
    """THE CONTRACT — fails before: no plan exists when the model never calls plan_task."""
    engine, fake, sid = _agent(tmp_path, [WRITE, REPORT])
    engine.agent_chat(X5, explicit=False, session_id=sid)
    plan = engine.session_plans.get(sid)
    assert plan and len(plan["steps"]) == 2, plan
    assert len(_rejected(plan)) == 1 and _rejected(plan)[0]["text"] == "5566778899." and _rejected(plan)[0].get("note"), plan
    assert plan["steps"][0]["status"] == "done" and plan["status"] == "partial", plan
    assert (tmp_path / "memorando.md").read_text(encoding="utf-8").strip() == "MEMORANDO-IBIS"
    first = " ".join(str(m.get("content", "")) for m in fake.calls[0]["messages"])
    assert "PINNED PLAN" in first and "[rejected: not executed] 1. 5566778899." in first


def test_a_single_request_and_a_question_list_plan_nothing(ws, tmp_path):
    engine, _, sid = _agent(tmp_path, [WRITE, REPORT])
    engine.agent_chat("Cria memorando.md com o texto MEMORANDO-IBIS.", explicit=False, session_id=sid)
    assert engine.session_plans.get(sid) is None
    (tmp_path / "b").mkdir()
    engine2, _, sid2 = _agent(tmp_path / "b", [{"content": "Nao sei.", "tool_calls": []}])
    engine2.agent_chat("Duas perguntas. 1. Qual e o meu nome? 2. Onde e que eu moro?", explicit=False, session_id=sid2)
    assert engine2.session_plans.get(sid2) is None


def test_a_pending_proposal_and_a_prohibited_turn_are_left_alone(ws, tmp_path):
    engine, _, sid = _agent(tmp_path, [{"content": "Qual dos dois?", "tool_calls": []}])
    engine._turn_user_message = "already"
    propose(engine, sid, "already", ["write already.md"])
    engine.agent_chat(X5, explicit=False, session_id=sid)
    assert engine.session_plans.get(sid)["title"] == "already"
    (tmp_path / "c").mkdir()
    engine2, _, sid2 = _agent(tmp_path / "c", [{"content": "Entendido.", "tool_calls": []}])
    engine2.agent_chat("Nunca escrevas ficheiros. 1. Cria nota.md com o texto NOTA. 2. 1234567890.", explicit=False, session_id=sid2)
    assert engine2.session_plans.get(sid2) is None
