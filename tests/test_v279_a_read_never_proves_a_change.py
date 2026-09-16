"""95.78 D3 — a `bash cat` of an unrelated file closed a step that said "write the code".

Live session 523b0720: the active step was a sentence of prose, "Since this requires fetching live data
and designing the interface, I'll need to write the HTML/JavaScript code and then". It names no file,
no widget and no tool, so verification fell to the generic branch, where a receipt of the turn counts
if its salient words meet the step's. The turn's only receipt was `bash cat maputo_weather_widget.html`
— a READ of a file from twelve days earlier — and the word "html" appeared on both sides. The step was
marked done and the plan closed, with nothing written that turn.

Invariant: a receipt whose declared effect is `read` never settles a step that asks for a change. The
effect is declared by the tool's own schema and already sits on every receipt, so this reads what is
recorded rather than guessing from the wording of the result.
"""

from __future__ import annotations

import hashlib

from hmgfu.receipts import ReceiptStore, verify_step
from hmgfu.speech_act import changes_the_world

NAMES = ["write_file", "read_file", "list_files", "memory_search", "create_widget", "bash"]
THE_REAL_STEP = ("Since this requires fetching live data and designing the interface, I'll need to "
                 "write the HTML/JavaScript code and then")


def _read_receipt(st, command="cat maputo_weather_widget.html"):
    rid = st.open("s", 6, "bash", {"command": command}, "read", "user_request", 0)
    st.close(rid, "ok", '{"stdout": "<!DOCTYPE html>..."}', {})
    return rid


def test_the_step_that_asks_for_a_change_is_recognised():
    assert changes_the_world(THE_REAL_STEP)
    assert changes_the_world("Save the game as a new HTML file in the workspace")
    assert changes_the_world("Rewrite weather_widget.html with better error handling")
    assert not changes_the_world("check my broader memory for links")
    assert not changes_the_world("list the files in the workspace")
    assert not changes_the_world("Verify the file exists and present it to the user")


def test_a_read_receipt_does_not_close_a_writing_step(tmp_path):
    st = ReceiptStore(str(tmp_path / "r.db"))
    _read_receipt(st)
    ok, evidence, missing = verify_step(THE_REAL_STEP, st.for_session("s"), str(tmp_path), NAMES, turn_seq=6)
    assert not ok and not evidence, missing
    assert missing and "read" in missing[0].lower(), missing


def test_the_write_that_did_the_work_still_closes_it(tmp_path):
    st = ReceiptStore(str(tmp_path / "r.db"))
    _read_receipt(st)
    target = tmp_path / "weather.html"
    target.write_text("<!DOCTYPE html><html>built</html>", encoding="utf-8")
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    rid = st.open("s", 6, "write_file", {"path": "weather.html", "content": "…"}, "write", "user_request", 0)
    st.close(rid, "ok", "written", {"files": [{"path": "weather.html", "sha256": digest, "bytes": 33}]})
    ok, evidence, missing = verify_step(THE_REAL_STEP, st.for_session("s"), str(tmp_path), NAMES, turn_seq=6)
    assert ok and evidence == [rid], missing


def test_a_reading_step_is_still_proven_by_a_read(tmp_path):
    """90.2 stands: the requested action proves the step, and some steps request a read."""
    st = ReceiptStore(str(tmp_path / "r.db"))
    rid = st.open("s", 2, "memory_search", {"query": "links to the project"}, "read", "user_request", 0)
    st.close(rid, "ok", '{"results": []}', {})
    ok, evidence, _missing = verify_step("check my broader memory for links", st.for_session("s"),
                                         str(tmp_path), NAMES, turn_seq=2)
    assert ok and evidence == [rid]


def test_an_explicit_read_tool_step_is_unaffected(tmp_path):
    st = ReceiptStore(str(tmp_path / "r.db"))
    rid = st.open("s", 2, "list_files", {"path": "."}, "read", "user_request", 0)
    st.close(rid, "ok", '{"files": []}', {})
    ok, evidence, _missing = verify_step("list the files in the workspace", st.for_session("s"),
                                         str(tmp_path), NAMES, turn_seq=2)
    assert ok and evidence == [rid]
