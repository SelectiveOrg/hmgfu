"""Phase 90.2 — a receipt proves a plan step only if it matches the REQUESTED action in the CURRENT turn. Live defect
(2026-09-07, turn 10): the step "check my broader memory … links" was marked done with the receipt of an earlier, unrelated
`list_files`; the promised memory_search never ran. No new executor, no automatic retry: without a matching receipt the step
stays open and the reply says so."""
from __future__ import annotations

from hmgfu.receipts import verify_step

NAMES = ["write_file", "create_widget", "update_widget", "bash", "read_file", "list_files", "memory_search", "brave_web_search"]
STEP = "However, I can check my broader memory to see if there are other links you've shared that aren't part of my main summary"


def _receipt(rid, tool, args, turn_seq, status="ok"):
    return {"id": rid, "tool": tool, "args": args, "status": status, "consumed_by": None, "effects": {}, "turn_seq": turn_seq}


def test_an_earlier_unrelated_read_receipt_does_not_complete_a_generic_step(tmp_path):
    old = _receipt("762e610b8540", "list_files", {}, turn_seq=2)
    ok, evidence, missing = verify_step(STEP, [old], str(tmp_path), NAMES, turn_seq=10)
    assert not ok and evidence == [] and missing


def test_a_same_turn_receipt_for_the_requested_action_completes_it(tmp_path):
    hit = _receipt("m1", "memory_search", {"query": "links shared"}, turn_seq=10)
    assert verify_step(STEP, [hit], str(tmp_path), NAMES, turn_seq=10) == (True, ["m1"], [])


def test_a_same_turn_receipt_for_another_action_does_not(tmp_path):
    other = _receipt("b1", "bash", {"command": "ls"}, turn_seq=10)
    ok, evidence, _missing = verify_step(STEP, [other], str(tmp_path), NAMES, turn_seq=10)
    assert not ok and evidence == []


def test_a_matching_receipt_from_a_previous_turn_does_not(tmp_path):
    stale = _receipt("m0", "memory_search", {"query": "links"}, turn_seq=9)
    ok, evidence, _missing = verify_step(STEP, [stale], str(tmp_path), NAMES, turn_seq=10)
    assert not ok and evidence == []


def test_a_step_with_no_salient_words_is_proven_by_any_same_turn_action(tmp_path):
    """v38's shape: steps "a", "b" — nothing to match on, so the turn constraint alone decides (never an earlier turn)."""
    same = _receipt("b1", "bash", {"command": "echo b"}, turn_seq=3)
    assert verify_step("b", [same], str(tmp_path), NAMES, turn_seq=3)[0]
    assert not verify_step("b", [_receipt("b0", "bash", {"command": "echo b"}, turn_seq=1)], str(tmp_path), NAMES, turn_seq=3)[0]


def test_without_a_turn_the_old_generic_rule_still_needs_the_action_to_match(tmp_path):
    old = _receipt("r1", "list_files", {}, turn_seq=2)
    ok, _e, _m = verify_step(STEP, [old], str(tmp_path), NAMES)
    assert not ok


def test_a_promise_that_stays_a_promise_is_marked_in_the_reply():
    """The live shape: approval → "I'll start by searching…" → no tool ran even after the single existing re-ask. The step stays
    open and the reply carries the existing correction; nothing is retried automatically."""
    from hmgfu.saydo import enforce, transactions_of, PLAN_CORRECTION
    from tests.test_v41_saydo_claims import _Stub
    plan = {"title": "check links", "steps": [{"text": STEP, "status": "active"}]}
    eng = _Stub(plan, ["memory_search"])
    tx = transactions_of([], [], None, 0, episode=True)
    calls = []
    def rerun(instr, required=None):
        calls.append(instr); return ("I'll start by searching your broader memories for any additional links.", [])
    reply, trace, rep = enforce(eng, "I'll start by searching your broader memories for any additional links you've shared.", [], tx, "s1", "yes", rerun, 10)
    assert rep["action"] == "unfulfilled_plan_step" and trace == []
    assert PLAN_CORRECTION.format(step=STEP[:80]) in reply
    assert len(calls) == 1                                    # the one existing re-ask, no further retries
    assert plan["steps"][0]["status"] == "active"             # the step is not marked done
