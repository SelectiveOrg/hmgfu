"""95.63 (X2 on v4, d95w18v4 rep1; the X5 report-turn observation on w17) — a report turn with no settled plan
refers to the session's last turn with receipts.

"o que foi que criaste?" — the turn executed nothing; the reply reported the previous turn's real write
("salvei o arquivo na raiz do workspace") and saydo corrected it with "nothing was actually written", true of
this turn and false of the report. 95.4b-ii read a settled PLAN's receipts; with no plan the referent is
the session's last turn with receipts. Positive: the honest report stands. Preserve: with no receipts in
the session the correction stands; a claim the last receipts do not support is still corrected.
"""
from __future__ import annotations

from hmgfu.saydo import enforce, transactions_of
from tests.test_v2_agent import make_agent

TX = transactions_of([], [], None, 0)
ASK = "o que foi que criaste?"
REPORT = "Criei o ficheiro ola_tamarin.py na raiz do workspace com o texto TAMARIN-OK."
DELETED = "Apaguei o ficheiro ola_tamarin.py."


class Rerun:
    def __call__(self, instruction, required=None):
        return "", []


def _engine(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    engine.settings.set("grader_enabled", False)
    engine._turn_plan = None
    engine._turn_effects_allowed = False
    engine._turn_unconfirmed_effects = []
    engine._turn_step_tools = []
    engine._turn_user_message = ASK
    return engine


def _write_receipt(engine, sid):
    rid = engine.receipts.open(sid, 1, "write_file", {"path": "ola_tamarin.py", "content": "print('TAMARIN-OK')"}, "write", "user_request", None)
    engine.receipts.close(rid, "ok", "wrote ola_tamarin.py", {"files": ["ola_tamarin.py"]})


def test_the_honest_report_of_the_last_turns_write_stands(tmp_path):
    """THE CONTRACT — fails before: the report is corrected with 'nothing was actually written'."""
    e = _engine(tmp_path)
    _write_receipt(e, "s1")
    reply, _t, report = enforce(e, REPORT, [], TX, "s1", ASK, Rerun(), 2)
    assert "nothing was actually written" not in reply and (report or {}).get("action") != "corrected_claim", (report, reply)


def test_no_receipts_and_an_unsupported_claim_are_still_corrected(tmp_path):
    e = _engine(tmp_path)
    reply, _t, report = enforce(e, REPORT, [], TX, "s1", ASK, Rerun(), 2)
    assert (report or {}).get("action") == "corrected_claim", report
    (tmp_path / "b").mkdir()
    e2 = _engine(tmp_path / "b")
    _write_receipt(e2, "s1")
    reply, _t, report = enforce(e2, DELETED, [], TX, "s1", ASK, Rerun(), 2)
    assert (report or {}).get("action") == "corrected_claim" and "did not remove" in reply, (report, reply)
