"""95.73 — a receipt the store cannot read back is worse than no receipt.

Reproduction (live, 16/09, session 1fc923cd): the user asked for a countdown timer widget. The turn
planned, called create_widget('timer') (refused: unknown type), wrote a 4 KB HTML file, created the app
widget — and then died. `ReceiptStore.open` stored `json.dumps(args)[:4000]`, chopping the write_file
argument document mid-string, so every later read of that session raised JSONDecodeError. It surfaced
first as a failed update_plan, then as an unhandled error in end_turn: the work was done, the reply was
lost, nothing was persisted, and the session stayed poisoned for every future turn.

Invariant: whatever the receipt store writes, the receipt store can read — the size cap truncates the
VALUES, never the JSON document; and a row already chopped on disk is recovered, never raised.
"""

from __future__ import annotations

import json
import sqlite3

from hmgfu.receipts import ReceiptStore, verify_step


def test_oversized_args_stay_readable(tmp_path):
    st = ReceiptStore(str(tmp_path / "r.db"))
    html = "<!DOCTYPE html>\n<html>" + ("<div>countdown timer</div>\n" * 500)   # ~13 KB, like the real file
    assert len(json.dumps({"filename": "countdown_timer.html", "content": html})) > 4000
    rid = st.open("s", 1, "write_file", {"filename": "countdown_timer.html", "content": html}, "write", "user_request", 0)
    st.close(rid, "ok", "written", {"files": [{"path": "countdown_timer.html", "sha256": "x", "bytes": len(html)}]})

    rows = st.for_session("s")          # this is what end_turn does; it must not raise
    assert len(rows) == 1
    args = rows[0]["args"]
    assert args["filename"] == "countdown_timer.html", "the identifying argument survives the cap"
    assert rows[0]["effects"]["files"][0]["path"] == "countdown_timer.html", "effects keep their shape"
    stored = sqlite3.connect(str(tmp_path / "r.db")).execute("SELECT args FROM receipts").fetchone()[0]
    assert len(stored) <= 4000, "the cap still holds"
    assert json.loads(stored), "what was stored is a JSON document"


def test_oversized_effects_stay_readable(tmp_path):
    st = ReceiptStore(str(tmp_path / "r.db"))
    rid = st.open("s", 1, "bash", {"command": "ls"}, "write", "user_request", 0)
    st.close(rid, "ok", "listed", {"stdout": "x" * 9000, "files": [{"path": "a.txt"}]})
    rows = st.for_session("s")
    assert rows[0]["effects"]["files"][0]["path"] == "a.txt"


def test_a_row_already_chopped_on_disk_is_recovered(tmp_path):
    """The live database has one such row. Reading it must not kill the turn."""
    path = str(tmp_path / "r.db")
    st = ReceiptStore(path)
    rid = st.open("s", 1, "write_file", {"filename": "countdown_timer.html", "content": "ok"}, "write", "user_request", 0)
    chopped = json.dumps({"filename": "countdown_timer.html", "content": "<html>" + "y" * 5000})[:4000]
    db = sqlite3.connect(path)
    db.execute("UPDATE receipts SET args=? WHERE id=?", (chopped, rid))
    db.commit()
    db.close()

    rows = ReceiptStore(path).for_session("s")        # must recover, not raise
    assert len(rows) == 1
    assert "countdown_timer.html" in json.dumps(rows[0]["args"]), "the recovered text still names the file"


def test_the_step_that_wrote_the_file_still_verifies(tmp_path):
    """End to end: the post-condition of 'write the HTML file' holds even when the args were capped."""
    st = ReceiptStore(str(tmp_path / "r.db"))
    target = tmp_path / "countdown_timer.html"
    html = "<!DOCTYPE html>" + ("<div>countdown</div>" * 500)
    target.write_text(html, encoding="utf-8")
    rid = st.open("s", 1, "write_file", {"filename": "countdown_timer.html", "content": html}, "write", "user_request", 0)
    import hashlib
    digest = hashlib.sha256(target.read_bytes()).hexdigest()   # the real file, as observe_effects records it
    st.close(rid, "ok", "written", {"files": [{"path": str(target), "sha256": digest, "bytes": len(html)}]})
    ok, evidence, _missing = verify_step("Create the HTML/CSS structure for countdown_timer.html",
                                         st.for_session("s"), str(tmp_path), ["write_file"], None)
    assert ok and evidence == [rid]
