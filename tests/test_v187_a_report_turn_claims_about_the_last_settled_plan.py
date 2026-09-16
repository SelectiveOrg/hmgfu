"""95.4b-ii — a turn that did nothing and reports claims about the session's LAST settled plan.

E5 in c95b (0/3): on "did you finish everything I asked?" no plan is live (a partial plan is not
resumable), so 95.4b saw no rejected step, and the say-do gate judged "I created plan_e5.md" against
THIS turn's empty transactions — appending "(Correction: nothing was actually written …)" to a TRUE
report — while the rejected step '1234567890' went unnamed. One missing link: the referent of a claim
on a report turn. Structural: no live plan + nothing executed this turn + a settled plan in the store
=> that plan's rejected steps bind the reply, and the receipts its done steps cite support what it did.

Positive: the E5 shape gets the rejected-step correction and NOT the false "nothing was written".
Negative: a fully done plan reported truthfully gets no correction. Variant: a claim the settled plan's
receipts do not support ("I deleted your files") is still corrected. Preserve: no settled plan, no
change — a claim with no work behind it is still corrected as before (93.A); a live plan is untouched.
"""
from __future__ import annotations

from hmgfu.receipts import ReceiptStore
from hmgfu.saydo import CORRECTION, enforce, transactions_of
from hmgfu.session_plans import SessionPlanStore


class _Settings:
    def get(self, key, default=None):
        return True if key == "saydo_gate_enabled" else default


class _E:
    def __init__(self, tmp_path):
        self.settings = _Settings()
        db = str(tmp_path / "e.db")
        self.session_plans = SessionPlanStore(db)
        self.receipts = ReceiptStore(db)
        self._turn_user_message = "did you finish everything I asked?"
        self._turn_plan = None
        self._turn_step_tools = []
        self._turn_effects_allowed = False
        self._turn_unconfirmed_effects = []
        self.events = []

    def _emit(self, e):
        self.events.append(e)


TX = transactions_of([], [], None, 0)          # the report turn: nothing happened


def _rerun(instruction, required=None):
    return "", []


def _settle(e, rejected=True):
    """The E5 plan as the store holds it after turn 1: step 1 done with a real receipt, step 2 rejected."""
    rid = e.receipts.open("s1", 1, "write_file", {"path": "plan_e5.md", "content": "E5-PLAN"}, "write", "user_request", 0)
    e.receipts.close(rid, "ok", "written", {"files": [{"path": "plan_e5.md"}]})
    steps = [{"text": "Write plan_e5.md containing E5-PLAN", "status": "done", "evidence": [rid]}]
    if rejected:
        steps.append({"text": "1234567890", "status": "rejected", "note": "describes no work, so no receipt can ever prove it"})
    e.session_plans.save("s1", {"title": "E5", "status": "partial" if rejected else "done", "steps": steps,
                                "authorization": {"origin": "user_request"}})
    return rid


REPORT = 'Yes, I have finished both steps: I created `plan_e5.md` with the content "E5-PLAN" and noted your sequence 1234567890.'


def test_the_e5_report_names_the_rejected_step_and_is_not_told_nothing_was_written(tmp_path):
    """THE CONTRACT — fails before: no referent, so no rejected step and a false 'nothing was written'."""
    e = _E(tmp_path)
    _settle(e, rejected=True)
    reply, _t, report = enforce(e, REPORT, [], TX, "s1", e._turn_user_message, _rerun, 2)
    assert "NOT executed" in reply and reply.count("1234567890") == 2, reply
    assert CORRECTION not in reply, reply
    assert report.get("rejected_step_claimed") and report.get("action") != "corrected_claim", report


def test_a_true_report_of_a_done_plan_gets_no_correction(tmp_path):
    e = _E(tmp_path)
    _settle(e, rejected=False)
    reply, _t, _r = enforce(e, 'Yes, I created `plan_e5.md` with the content "E5-PLAN".', [], TX, "s1",
                            e._turn_user_message, _rerun, 2)
    assert "Correction" not in reply, reply


def test_a_claim_the_settled_plan_never_did_is_still_corrected(tmp_path):
    e = _E(tmp_path)
    _settle(e, rejected=False)
    reply, _t, _r = enforce(e, "Yes, I've deleted your old notes as asked.", [], TX, "s1", e._turn_user_message, _rerun, 2)
    assert "(Correction:" in reply and "did not remove" in reply, reply   # 95.63: the correction names what the referent did


def test_with_no_settled_plan_an_unbacked_claim_is_corrected_as_before(tmp_path):
    e = _E(tmp_path)
    reply, _t, _r = enforce(e, "I've created plan_e5.md for you.", [], TX, "s1", "done?", _rerun, 2)
    assert CORRECTION in reply, reply


def test_a_live_plan_is_the_referent_when_there_is_one(tmp_path):
    """The settled plan never displaces a live one (95.4b's own path, v180)."""
    e = _E(tmp_path)
    _settle(e, rejected=True)
    e._turn_plan = {"title": "T2", "status": "active", "steps": [{"text": "list the folder", "status": "active"}]}
    reply, _t, _r = enforce(e, "Here is what I found in the folder.", [], TX, "s1", "what is there?", _rerun, 3)
    assert "1234567890" not in reply
