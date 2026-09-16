"""72.6d — one connection policy for every store: WAL + busy timeout, so a long write on one connection does not make
another connection fail with 'database is locked'."""
import sqlite3
import threading
import time

from hmgfu.db import connect, journal_mode
from hmgfu.facts import FactStore
from hmgfu.receipts import ReceiptStore


def test_connect_sets_wal_and_busy_timeout(tmp_path):
    db = str(tmp_path / "x.db")
    a = connect(db)
    assert journal_mode(a) == "wal"
    assert a.execute("PRAGMA busy_timeout").fetchone()[0] >= 30000


def test_two_writers_overlapping_transactions_do_not_fail(tmp_path):
    db = str(tmp_path / "y.db")
    a, b = connect(db), connect(db)
    a.execute("CREATE TABLE t (k TEXT)"); a.commit()
    a.execute("BEGIN IMMEDIATE"); a.execute("INSERT INTO t VALUES ('a')")

    def release():
        time.sleep(6.5)                       # longer than sqlite's 5 s default timeout
        a.commit()
    threading.Thread(target=release, daemon=True).start()
    t0 = time.time()
    b.execute("INSERT INTO t VALUES ('b')"); b.commit()        # waits, never raises
    assert time.time() - t0 >= 6 and b.execute("SELECT count(*) FROM t").fetchone()[0] == 2


def test_stores_share_the_policy(tmp_path):
    db = str(tmp_path / "z.db")
    f, r = FactStore(db), ReceiptStore(db)
    assert journal_mode(f._db) == "wal" and journal_mode(r._db) == "wal"
    assert journal_mode(f.assertions._db) == "wal"



def test_directive_restatement_leaves_no_open_transaction(tmp_path):
    """73.4 root cause of 'database is locked': the echo-guard path lifted the tombstone (a write) and returned without
    committing; the next writer on another connection in the same thread then deadlocked."""
    from hmgfu.directives import DirectiveStore
    from hmgfu.facts import FactStore
    db = str(tmp_path / "d.db")
    ds, fs = DirectiveStore(db), FactStore(db)
    det = {"kind": "conversation_closer", "value": "a short joke", "instruction": "end with a joke", "fallback_text": ""}
    assert ds.apply("end every reply with a joke", "user_explicit", detected=det) is not None
    assert ds.apply("end every reply with a joke", "user_explicit", detected=det) is None      # restatement
    assert ds._db.in_transaction is False
    t0 = time.time()
    fs.apply_all("my name is Ana", "user_explicit")                # another connection, same thread: must not wait
    assert time.time() - t0 < 5


def test_turn_boundary_guard_commits_and_reports(tmp_path):
    from types import SimpleNamespace
    from hmgfu.db import commit_open_transactions
    from hmgfu.facts import FactStore
    fs = FactStore(str(tmp_path / "g.db"))
    fs._db.execute("CREATE TABLE IF NOT EXISTS t (k TEXT)"); fs._db.commit()
    fs._db.execute("INSERT INTO t VALUES ('x')")                   # deliberately left open
    assert fs._db.in_transaction
    eng = SimpleNamespace(facts=fs)
    assert commit_open_transactions(eng, "test") == ["facts"]
    assert fs._db.in_transaction is False
    assert commit_open_transactions(eng, "test") == []
