"""Phase 82.4 — receipts prove the REQUESTED outcome (Codex review 2, A3): the normalised target path (directory included),
the observed hash still on disk, the requested widget, and the requested effect (a read never completes a write)."""
from __future__ import annotations

import hashlib

from hmgfu.receipts import postcondition, verify_step

NAMES = ["write_file", "create_widget", "update_widget", "bash", "read_file", "list_files"]


def _sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _write_receipt(rid, rel, sha, tool="write_file"):
    return {"id": rid, "tool": tool, "status": "ok", "consumed_by": None, "args": {"path": rel},
            "effects": {"files": [{"path": rel, "sha256": sha}]}}


def test_postcondition_keeps_the_directory_of_the_requested_path():
    assert postcondition("write_file: new/report.md", NAMES)["files"] == ["new/report.md"]
    assert postcondition("save the summary to Docs\\Notes.TXT", NAMES)["files"] == ["docs/notes.txt"]
    assert postcondition("write_file: report.md", NAMES)["files"] == ["report.md"]


def test_wrong_directory_is_not_the_requested_file(tmp_path):
    (tmp_path / "old").mkdir(); (tmp_path / "new").mkdir()
    old = tmp_path / "old" / "report.md"; old.write_text("x")
    r_old = _write_receipt("r1", "old/report.md", _sha(old))
    ok, ev, missing = verify_step("write_file: new/report.md", [r_old], str(tmp_path), NAMES)
    assert not ok and ev == [] and "new/report.md" in missing[0]
    new = tmp_path / "new" / "report.md"; new.write_text("y")
    assert verify_step("write_file: new/report.md", [_write_receipt("r2", "new/report.md", _sha(new))], str(tmp_path), NAMES) == (True, ["r2"], [])
    # a request without a directory still accepts the file wherever the receipt wrote it (unchanged behaviour)
    assert verify_step("write_file: report.md", [_write_receipt("r3", "new/report.md", _sha(new))], str(tmp_path), NAMES)[0]


def test_content_changed_after_the_receipt_is_not_proven(tmp_path):
    f = tmp_path / "a.txt"; f.write_text("first")
    r = _write_receipt("r1", "a.txt", _sha(f))
    assert verify_step("write_file: a.txt", [r], str(tmp_path), NAMES)[0]
    f.write_text("changed later")
    ok, _ev, missing = verify_step("write_file: a.txt", [r], str(tmp_path), NAMES)
    assert not ok and "changed since the receipt" in missing[0]


def test_receipt_without_a_hash_is_unknown_not_done(tmp_path):
    f = tmp_path / "a.txt"; f.write_text("x")
    r = {"id": "r1", "tool": "write_file", "status": "ok", "consumed_by": None, "effects": {"files": [{"path": "a.txt"}]}}
    ok, _ev, missing = verify_step("write_file: a.txt", [r], str(tmp_path), NAMES)
    assert not ok and "no hash" in missing[0]


def test_requested_widget_must_be_the_one_touched(tmp_path):
    links = {"id": "w1", "tool": "create_widget", "status": "ok", "consumed_by": None, "args": {"title": "Links", "kind": "table"},
             "effects": {"widgets": ["widget-links"]}}
    assert verify_step("create_widget: Links", [links], str(tmp_path), NAMES) == (True, ["w1"], [])
    ok, _ev, missing = verify_step("create_widget: Budget", [links], str(tmp_path), NAMES)
    assert not ok and "Budget" in missing[0]
    assert verify_step("create the links widget", [links], str(tmp_path), NAMES)[0]        # named in prose: matched too
    assert verify_step("update the widget", [links], str(tmp_path), NAMES)[0]              # unnamed: any widget receipt


def test_a_read_never_completes_a_write(tmp_path):
    f = tmp_path / "a.txt"; f.write_text("x")
    read = {"id": "r1", "tool": "read_file", "status": "ok", "consumed_by": None, "args": {"path": "a.txt"},
            "effects": {"files": [{"path": "a.txt", "sha256": _sha(f)}]}}      # even a read that reports the file's hash
    assert not verify_step("write_file: a.txt", [read], str(tmp_path), NAMES)[0]
    assert not verify_step("save the notes to a.txt", [read], str(tmp_path), NAMES)[0]


def test_step_evidence_uses_the_same_directory_aware_matcher():
    from hmgfu.session_plans import step_evidence
    trace_old = [{"name": "write_file", "arguments": {"path": "old/report.md"}, "failed": False}]
    trace_new = [{"name": "write_file", "arguments": {"path": "new/report.md"}, "failed": False}]
    assert not step_evidence({"text": "write_file: new/report.md"}, trace_old, NAMES)
    assert step_evidence({"text": "write_file: new/report.md"}, trace_new, NAMES)
    assert step_evidence({"text": "write_file: report.md"}, trace_new, NAMES)          # bare name: any directory (kept)
