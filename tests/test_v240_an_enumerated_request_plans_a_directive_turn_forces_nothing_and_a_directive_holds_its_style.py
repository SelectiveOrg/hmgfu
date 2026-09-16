"""95.54 + 95.55 + J6 (X5, T6 on v5) — an enumerated multi-request requires the plan tool; a turn that
sets a standing directive forces no tool; a directive holds the requested style in the user's words.

X5: "Dois pedidos. 1. Cria memorando.md com o texto MEMORANDO-IBIS. 2. 5566778899." — the model never
called plan_task (it wrote the file with the garbage number folded in), so no step could be rejected.
T6: "From now on, one short sentence per answer, nothing more." — the directive was written verbatim
and applied, the step-0 reply was "Please specify the topic ... using the web tool" (a forced tool on
a directive-setting turn), and the judge's exact `writes` did not see "one short sentence" inside
"one short sentence per answer, nothing more.". Positive: the plan tool is offered first for the
enumeration; nothing is forced on the directive turn; the judge reads the directive by containment.
Preserve: a single request offers no plan tool; an instruction without a directive still forces; facts
still match exactly.
"""
from __future__ import annotations

from types import SimpleNamespace as NS

import pytest

from hmgfu import tool_builtins
from hmgfu.models import QueryPoint
from hmgfu.tool_points import retrieve_tools_for_turn
from hmgfu.turn_events import plan_turn_actions
from scripts.judge_validation import _wrote
from tests.test_v2_agent import fake_embed, make_agent

X5 = "Dois pedidos. 1. Cria memorando.md com o texto MEMORANDO-IBIS. 2. 5566778899."


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setattr(tool_builtins, "get_workspace", lambda: str(tmp_path))
    return tmp_path


def _q(text, **kw):
    base = dict(text=text, embedding=fake_embed(text), intent="task", conversation_act="instruction", action_requested=False)
    base.update(kw)
    return QueryPoint(**base)


def test_an_enumerated_multi_request_offers_the_plan_tool_first(ws, tmp_path):
    """THE CONTRACT (95.54) — fails before: plan_task is not offered for X5's message."""
    engine, _ = make_agent(tmp_path, [])
    names = [s["name"] for s in retrieve_tools_for_turn(engine.tools, engine, _q(X5), max_tools=4)]
    assert names and names[0] == "plan_task", names
    names = [s["name"] for s in retrieve_tools_for_turn(engine.tools, engine, _q("Cria memorando.md com o texto MEMORANDO-IBIS."), max_tools=4)]
    assert "plan_task" not in names[:1], names


def test_a_directive_setting_turn_forces_no_tool(tmp_path):
    """THE CONTRACT (95.55) — fails before: the router's web search is forced on the style directive."""
    engine, _ = make_agent(tmp_path, [])
    engine._turn_step_tools = []
    q = NS(requested_tools=["brave_web_search"], action_requested=True, extractor="nano", needs_memory=False,
           conversation_act="instruction", directive={"kind": "response_style", "value": "one short sentence"})
    _r, forced, _ = plan_turn_actions(engine, q, "From now on, one short sentence per answer, nothing more.", ["brave_web_search"], [])
    assert forced == []
    q2 = NS(requested_tools=["write_file"], action_requested=True, extractor="nano", needs_memory=False,
            conversation_act="instruction", directive=None)
    _r, forced2, _ = plan_turn_actions(engine, q2, "Write a file notes.md containing NOTES-OK now.", ["write_file"], [])
    assert forced2 == ["write_file"]


def test_the_judge_reads_a_directive_by_containment_and_a_fact_exactly():
    """THE CONTRACT (J6) — fails before: the directive's longer value is 'not written'."""
    changes = [("directives", "response_style", "long, detailed answers", "one short sentence per answer, nothing more.")]
    assert _wrote(changes, {}, "directives", "response_style", "one short sentence")
    assert not _wrote(changes, {}, "directives", "response_style", "two sentences")
    facts = [("facts", "project.main", "Sable", "Ibis Two")]
    assert not _wrote(facts, {}, "", "project.main", "Ibis")
    assert _wrote(facts, {}, "", "project.main", "Ibis Two")
