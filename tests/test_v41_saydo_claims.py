"""Phase 69.3 — execution claims bound by type; failed attempts; paraphrases; memory promises; unit binding."""

from __future__ import annotations

from hmgfu.grounding import ungrounded_claims
from hmgfu.saydo import classify, exec_claims, transactions_of
from tests.test_v2_agent import make_agent

NONE = {"facts": 0, "retractions": 0, "directive": False, "effects": 0, "effects_remove": 0, "episode": False}


def test_claim_classes_and_type_binding():
    assert exec_claims("I've deleted your files and updated the car link.") == {"remove", "update"}
    assert exec_claims("Your link has been updated.") == {"update"} and exec_claims("The files were successfully deleted.") == {"remove"}
    assert exec_claims("Já memorizei o teu nome.") == {"memory"} and exec_claims("Criei o widget.") == {"create"}
    c = classify("I've deleted your files and updated the car link.", [], {**NONE, "facts": 1})
    assert c["false_exec_claim"] and c["unsupported_claims"] == ["remove"]        # a colour write is not a deletion
    assert not classify("I've updated your link.", [], {**NONE, "facts": 1})["false_exec_claim"]
    assert classify("I've created the widget.", [], {**NONE, "facts": 1})["false_exec_claim"]
    assert not classify("I've created the widget.", [], {**NONE, "effects": 1})["false_exec_claim"]
    assert not classify("I've removed your dog.", [], {**NONE, "retractions": 1})["false_exec_claim"]
    assert not classify("I've noted your preference.", [], {**NONE, "episode": True})["false_exec_claim"]   # episodic memory is real
    assert classify("Já memorizei o teu nome.", [], {})["false_exec_claim"]


def test_failed_attempt_is_not_action_and_memory_promise_is_not_an_intent():
    c = classify("I'll inspect the file.", [{"name": "read_file", "failed": True}], NONE)
    assert c["intent_no_action"] and c["read_only"]
    c = classify("I've noted that. I'll make sure to remember those details for you.", [], {**NONE, "facts": 3})
    assert c["intent"] is None and not c["intent_no_action"] and not c["false_exec_claim"]
    c = classify("Vou guardar essas informações sobre suas preferências.", [], {**NONE, "episode": True})
    assert c["intent"] is None


def test_transactions_of_counts_retractions_and_remove_effects():
    tx = transactions_of([{"name": "remove_widget", "arguments": {}, "failed": False}, {"name": "write_file", "failed": True}],
                         [{"key": "pet.name", "cleared": "Bento"}, {"key": "pref.color", "value": "blue"}], None, episode=True)
    # 93.A: `operations` is additive — the old keys keep their exact meaning, and each change now also
    # names the operation and its target, so a removal can no longer be mistaken for a write.
    assert tx == {"facts": 1, "retractions": 1, "directive": False, "effects": 1, "effects_remove": 1,
                  "plan_ops": 0, "episode": True,
                  "operations": [{"op": "remove", "target": "fact:pet.name"},
                                 {"op": "update", "target": "fact:pref.color"},
                                 {"op": "remove", "target": "tool:remove_widget"}]}


def test_memory_acknowledgement_turn_makes_no_proposal(tmp_path):
    engine, _ = make_agent(tmp_path, [{"content": "It's a pleasure, Nadia! I've noted your name and your dog Bento — "
                                                  "I'll make sure to remember those details for you.", "tool_calls": []}])
    engine.settings.set("grader_enabled", False)
    s = engine.sessions.create_session("m")["id"]
    r = engine.agent_chat("By the way, my name is Nadia Costa and my dog is Bento.", session_id=s)
    assert "Shall I go ahead" not in r["response"] and engine.session_plans.get(s) is None
    assert "Correction" not in r["response"]


def test_unit_travels_with_the_number():
    assert ungrounded_claims("It is 26°C", ["Humidity is 26%. Temperature unavailable."]) == ["26°C"]
    assert ungrounded_claims("It is 26°C", ["Temperature is 26 °C"]) == []
    assert ungrounded_claims("Humidity 26%", ["humidity: 26%"]) == [] and ungrounded_claims("Humidity 26%", ["26°C"]) == ["26%"]


def test_keeping_a_distinction_in_mind_is_not_an_action():
    c = classify("Understood. I'll keep that distinction clear: Oscar is the character's name, not yours.", [], {**NONE, "episode": True})
    assert c["intent"] is None and not c["intent_no_action"]
    c = classify("I'll keep the two names straight from now on.", [], {**NONE, "episode": True})
    assert c["intent"] is None
    assert classify("I'll check the file now.", [], NONE)["intent_no_action"]      # a real read intent still counts



class _Stub:
    """Minimal engine surface for saydo.enforce (settings, session plans, turn state)."""
    def __init__(self, plan, step_tools):
        from types import SimpleNamespace
        self.settings = SimpleNamespace(get=lambda k, d=None: True)
        self.session_plans = SimpleNamespace(pending=lambda sid: None)
        self._turn_plan, self._turn_step_tools = plan, step_tools
        self._turn_unconfirmed_effects, self._turn_proposed, self.emitted = [], False, []
    def _emit(self, ev):
        self.emitted.append(ev)


def _plan():
    return {"title": "three notes", "steps": [{"text": "write note3.txt", "status": "active"}]}


def test_reask_is_fulfilled_only_by_the_required_step_tool():
    from hmgfu.saydo import enforce, transactions_of, PLAN_CORRECTION
    tx = transactions_of([], [], None, 0, episode=True)
    # the re-ask ran a read-only bash and claimed completion → NOT fulfilled, claim corrected, plan stays open
    eng = _Stub(_plan(), ["write_file"])
    rerun = lambda instr, required=None: ("I have updated the tracking: all steps are now complete.",
                                          [{"name": "bash", "arguments": {"command": "ls"}, "result": "note1.txt"}])
    reply, trace, rep = enforce(eng, "Continuing the plan now.", [], tx, "s1", "continue", rerun, 2)
    assert rep["action"] == "unfulfilled_plan_step" and rep["false_exec_claim"] is True
    assert PLAN_CORRECTION.format(step="write note3.txt") in reply
    assert eng.emitted[-1]["ok"] is False
    # the re-ask ran the required write → fulfilled
    eng = _Stub(_plan(), ["write_file"])
    rerun_ok = lambda instr, required=None: ("Done: note3.txt written.",
                                             [{"name": "write_file", "arguments": {"path": "note3.txt"}, "result": "ok"}])
    reply, trace, rep = enforce(eng, "Continuing the plan now.", [], tx, "s1", "continue", rerun_ok, 2)
    assert rep["action"] == "executed_intent" and "Correction" not in reply
