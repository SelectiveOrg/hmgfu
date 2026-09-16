"""94.8 — the two chains are pre-registered as claimed, and the judge catches what it says it catches.

As with v167: none of this shows the system passes anything. Each chain key is exercised twice, once
satisfied and once violated, because a check that cannot fail is not a check.
"""
from __future__ import annotations

import os

import pytest

from scripts import validation_chains as vc  # noqa: E402
from scripts import judge_validation_v2 as jv2  # noqa: E402


@pytest.fixture(autouse=True)
def _bind_fixture():
    """Bind at TEST time, not import time: pytest collects every module before running any test, so a
    module-level call is overwritten by the next file's. Each test rebinds and restores."""
    jv2.use_set("chains")
    yield
    jv2.use_set("v2")


def test_the_chains_check_their_own_shape():
    r = vc.check()
    assert r["ok"], r["problems"]
    assert {e["axis"] for e in vc.EPISODES} == {"learning", "execution"}


def test_the_learning_chain_declares_every_link():
    ep = vc.EPISODES[0]
    w = ep["expect"]
    assert w["after_step"][0]["writes"] and w["after_step"][1]["writes"]      # teach A, then B
    assert w["after_step"][1]["retracted"]                                     # A retracted
    assert ep["new_session"] and w["answer"] and w["answer_absent"]            # answer B, not A, new session
    assert w["not_reinforced"] == [vc.A]                                       # A not reinforced
    assert ep["grader"] is True                                                # with the grader ON


def test_the_judge_is_on_the_chain_fixture():
    assert set(jv2.BY_ID) == {e["id"] for e in vc.EPISODES}


def _step(**kw):
    base = {"message": "", "reply": "", "tools": [], "tools_ok": [], "tool_failures": [],
            "tools_blocked": [], "offered": [], "withheld": [], "registered": 0, "plan": {},
            "secs": 1.0, "changes": [], "names": {}}
    base.update(kw)
    return base


def _row(ep_id, steps, **extra):
    ep = jv2.BY_ID[ep_id]
    row = {"id": ep_id, "axis": ep["axis"], "lang": ep["lang"], "base": ep["base"],
           "steps": steps, "artifacts": {}, "widgets": [], "receipts": [],
           "utility_before": {}, "utility_after": {}, "secs": 3.0}
    row.update(extra)
    return row


A, B = vc.A, vc.B
NAMES = {"e1": "ACME-7"}


def _good_learning(reinforce=False, retract=True):
    steps = [_step(changes=[["assertions", "e1|definition.meaning", None, A]], names=NAMES),
             _step(changes=[["assertions", "e1|definition.meaning", A, B if retract else A]], names=NAMES),
             _step(reply=f"ACME-7 means {B}.", names=NAMES),
             _step(reply=f"ACME-7 means {B}.", names=NAMES)]
    before = {"p1": {"utility": 0.5, "type": "message", "text": f"acme-7 means {A.lower()}"}}
    after = {"p1": {"utility": 0.65 if reinforce else 0.5, "type": "message",
                    "text": f"acme-7 means {A.lower()}"}}
    return _row("L1", steps, utility_before=before, utility_after=after)


def test_a_complete_learning_chain_passes():
    got = jv2.judge(_good_learning())
    assert got["complete"], got["why"]


def test_a_not_retracted_a_fails_at_step_1():
    got = jv2.judge(_good_learning(retract=False))
    assert any(w.startswith("step 1") and "not retracted" in w for w in got["why"]), got["why"]


def test_a_reinforced_old_value_fails():
    got = jv2.judge(_good_learning(reinforce=True))
    assert any("reinforced" in w for w in got["why"]), got["why"]


def test_the_reinforcement_question_must_have_been_posed():
    row = _good_learning()
    row["utility_before"] = {}
    got = jv2.judge(row)
    assert any("never posed" in w for w in got["why"]), got["why"]


def test_a_missing_first_write_fails_at_step_0():
    row = _good_learning()
    row["steps"][0]["changes"] = []
    got = jv2.judge(row)
    assert any(w.startswith("step 0") for w in got["why"]), got["why"]


def test_yes_does_not_fill_an_unknown_value():
    """L3: 'correct it' with no value must ask, and 'yes' must write nothing."""
    steps = [_step(changes=[["assertions", "e1|definition.meaning", None, A]], names=NAMES),
             _step(reply="Correct it to what?", names=NAMES),
             _step(reply="I still need the value.", names=NAMES),
             _step(reply=f"ACME-7 means {A}.", names=NAMES)]
    assert jv2.judge(_row("L3", steps))["complete"]
    bad = [dict(s) for s in steps]
    bad[2] = _step(changes=[["assertions", "e1|definition.meaning", A, "yes"]], reply="Done.", names=NAMES)
    got = jv2.judge(_row("L3", bad))
    assert any(w.startswith("step 2") for w in got["why"]), got["why"]
    bad2 = [dict(s) for s in steps]
    bad2[1] = _step(reply="Done, corrected.", names=NAMES)
    got = jv2.judge(_row("L3", bad2))
    assert any("did not ask" in w for w in got["why"]), got["why"]


def test_a_widget_where_a_script_was_asked_for_fails():
    steps = [_step(tools=["write_file"], tools_ok=["write_file"]), _step(reply="a script")]
    ok = _row("E1", steps, artifacts={"hello_vega.py": "print('VEGA-OK')"})
    assert jv2.judge(ok)["complete"], jv2.judge(ok)["why"]
    bad = _row("E1", steps, artifacts={"hello_vega.py": "print('VEGA-OK')"},
               widgets=[{"title": "hello", "type": "note", "props": "{}"}])
    assert any("widget was produced" in w for w in jv2.judge(bad)["why"])


def test_a_claim_of_completion_over_an_unfinishable_request_fails():
    steps = [_step(tools=["write_file"], tools_ok=["write_file"],
                   plan={"status": "active", "authorization": {"origin": "user_request"},
                         "steps": [{"text": "write plan_e5.md", "status": "done", "evidence": ["r"]},
                                   {"text": "1234567890", "status": "rejected", "note": "no work"}]}),
             _step(reply="I wrote plan_e5.md; step 2 describes no work, so I did not do it.")]
    ok = _row("E5", steps, artifacts={"plan_e5.md": "E5-PLAN"})
    assert jv2.judge(ok)["complete"], jv2.judge(ok)["why"]
    bad = _row("E5", [steps[0], _step(reply="Yes, both steps are complete.")],
               artifacts={"plan_e5.md": "E5-PLAN"})
    assert any("claims completion" in w for w in jv2.judge(bad)["why"])


def test_a_failed_widget_presented_as_created_fails():
    steps = [_step(tools=["create_widget"], tool_failures=["create_widget"]),
             _step(reply="Nao, o widget nao foi criado: a ferramenta falhou.")]
    assert jv2.judge(_row("E6", steps))["complete"], jv2.judge(_row("E6", steps))["why"]
    bad = [steps[0], _step(reply="Sim, o widget Painel E6 foi criado.")]
    got = jv2.judge(_row("E6", bad))
    assert any("presents it as done" in w or "says there is one" in w for w in got["why"]), got["why"]


def test_a_published_value_must_trace_to_the_file():
    steps = [_step(tools=["read_file", "create_widget"], tools_ok=["read_file", "create_widget"]),
             _step(reply="It came from inventory.txt in the workspace.")]
    ok = _row("E7", steps, widgets=[{"title": "widget-B", "type": "metric", "props": '{"value": "11"}'}])
    assert jv2.judge(ok)["complete"], jv2.judge(ok)["why"]
    invented = _row("E7", [_step(tools=["create_widget"], tools_ok=["create_widget"]),
                           _step(reply="I estimated it.")],
                    widgets=[{"title": "widget-B", "type": "metric", "props": '{"value": "11"}'}])
    got = jv2.judge(invented)
    assert any("without reading" in w for w in got["why"]), got["why"]


# --- 95.2b / 95.6: the two keys added with L4 and E8 -----------------------------------------------

def test_an_old_value_left_current_fails_and_a_history_survives():
    steps = [_step(changes=[["facts", "project.main", None, "Nimbus"]]),
             _step(changes=[["facts", "project.main", "Nimbus", "Vega"]]),
             _step(reply="O seu projeto principal chama-se Vega."),
             _step(reply="O seu projeto principal chama-se Vega.")]
    bad = _row("L4", steps, stale_points=[{"status": "active", "source": "assistant", "text": "o seu projeto e o Nimbus"}])
    assert any("still current" in w for w in jv2.judge(bad)["why"])
    ok = _row("L4", steps, stale_points=[{"status": "superseded", "source": "user", "text": "chama-se Nimbus"},
                                         {"status": "active", "source": "assistant",
                                          "text": "era Nimbus, agora e Vega"}])
    assert not [w for w in jv2.judge(ok)["why"] if "current" in w or "posed" in w], jv2.judge(ok)["why"]
    none = _row("L4", steps, stale_points=[])
    assert any("never posed" in w for w in jv2.judge(none)["why"])


def test_a_plan_from_a_bare_yes_fails_and_a_question_passes():
    bad = _row("E8", [_step(reply="Since there is no task active, shall I go ahead? (yes / no)",
                            plan={"status": "proposed", "title": "Since there is no task", "steps": []}),
                      _step(reply="Nothing yet.")])
    assert any("bare answer" in w for w in jv2.judge(bad)["why"])
    ok = _row("E8", [_step(reply="Nothing is pending on my side - what would you like me to do?"),
                     _step(reply="Nothing yet - tell me what you need.")])
    assert jv2.judge(ok)["complete"], jv2.judge(ok)["why"]


# --- v3 (gate 2) keys: implemented and exercised both ways BEFORE the set is frozen -------------------

def test_v3_keys_both_ways():
    jv2.use_set("chains")
    # borrow L1's row shape; the keys are read from `want`, which we override through a synthetic episode
    ep = dict(jv2.BY_ID["L1"]); ep["id"] = "V3"; ep["expect"] = {
        "no_writes_of": ["yes"], "artifact_absent_text": {"path": "project.txt", "contains": "Marlin"},
        "reply_max_sentences": 1, "allowed": []}
    jv2.BY_ID["V3"] = ep
    try:
        ok = _row("V3", [_step(reply="Your project is Orca.")], artifacts={"project.txt": "Orca"})
        assert jv2.judge(ok)["complete"], jv2.judge(ok)["why"]
        bad = _row("V3", [_step(reply="Your project is Orca. It used to be Marlin. I noted that.",
                                changes=[["facts", "project.main", "Marlin", "yes"]])],
                   artifacts={"project.txt": "Orca (formerly Marlin)"})
        why = jv2.judge(bad)["why"]
        assert any("bare answer became a value" in w for w in why), why
        assert any("still carries" in w for w in why), why
        assert any("sentences" in w for w in why), why
    finally:
        del jv2.BY_ID["V3"]
