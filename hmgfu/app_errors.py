"""95.75 (P6) — what a built app reports at runtime, brought back to the agent.

An app the agent writes is served into a sandboxed frame and runs there. Until now nothing came back:
a console message, a rejected promise or a failed request stayed in the user's browser, so the only
channel was the user pasting the text by hand. The live weather page failed on a hostname with a
missing hyphen and the agent, blind, theorised about CORS proxies instead.

Three parts, one contract: the served page carries a reporter (installed before the page's own
scripts, so a fault during initial execution is reported too), the store keeps one row per distinct
fault per file, and the turn pins what is new ONCE — the `app_errors` tool reads the rest on demand.
Errors are keyed by FILE, which is what the widget points at, so no session plumbing reaches the page.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
from typing import List, Optional

from . import config
from .db import connect as db_connect
from .models import now_iso

MAX_MESSAGE = 400
PIN_LIMIT = 6              # how many distinct faults the turn pins at once


class AppErrorStore:
    """One row per distinct fault per file. `seen` marks what the agent has already been shown."""

    def __init__(self, db_path: Optional[str] = None):
        self._lock = threading.RLock()
        self._db = db_connect(db_path or config.DB_PATH)
        self._db.execute("CREATE TABLE IF NOT EXISTS app_errors (id TEXT PRIMARY KEY, file TEXT, kind TEXT, "
                         "message TEXT, source TEXT, line INTEGER, at TEXT, seen INTEGER DEFAULT 0)")
        self._db.execute("CREATE INDEX IF NOT EXISTS app_errors_file ON app_errors(file)")
        self._db.commit()

    @staticmethod
    def _fingerprint(file: str, entry: dict) -> str:
        raw = "|".join([file, str(entry.get("kind", "")), str(entry.get("message", ""))[:MAX_MESSAGE],
                        str(entry.get("source", "")), str(entry.get("line", ""))])
        return hashlib.sha256(raw.encode("utf-8", "replace")).hexdigest()[:16]

    def record(self, file: str, entries: List[dict]) -> int:
        """Store what the page reported. Returns how many rows are new — a page that re-renders reports
        the same fault again, and the agent needs the fault, not the count."""
        file = (file or "").strip()
        if not file:
            return 0
        new = 0
        with self._lock:
            for entry in entries or []:
                if not isinstance(entry, dict) or not str(entry.get("message", "")).strip():
                    continue
                rid = self._fingerprint(file, entry)
                if self._db.execute("SELECT 1 FROM app_errors WHERE id=?", (rid,)).fetchone():
                    continue
                try:
                    line = int(entry.get("line") or 0) or None
                except (TypeError, ValueError):
                    line = None
                self._db.execute("INSERT INTO app_errors VALUES (?,?,?,?,?,?,?,0)",
                                 (rid, file, str(entry.get("kind", "error"))[:40],
                                  str(entry.get("message", ""))[:MAX_MESSAGE],
                                  str(entry.get("source", ""))[:300], line, now_iso()))
                new += 1
            self._db.commit()
        return new

    def _rows(self, where: str, params: tuple, limit: int) -> List[dict]:
        with self._lock:
            rows = self._db.execute("SELECT id, file, kind, message, source, line, at, seen FROM app_errors "
                                    + where + " ORDER BY at DESC LIMIT ?", params + (limit,)).fetchall()
        return [{"id": r[0], "file": r[1], "kind": r[2], "message": r[3], "source": r[4],
                 "line": r[5], "at": r[6], "seen": bool(r[7])} for r in rows]

    def recent(self, files: List[str], limit: int = 20) -> List[dict]:
        files = [f for f in (files or []) if f]
        if not files:
            return []
        marks = ",".join("?" * len(files))
        return self._rows(f"WHERE file IN ({marks})", tuple(files), limit)

    def unseen(self, files: List[str], limit: int = PIN_LIMIT) -> List[dict]:
        files = [f for f in (files or []) if f]
        if not files:
            return []
        marks = ",".join("?" * len(files))
        return self._rows(f"WHERE seen=0 AND file IN ({marks})", tuple(files), limit)

    def mark_seen(self, ids: List[str]) -> None:
        ids = [i for i in (ids or []) if i]
        if not ids:
            return
        with self._lock:
            self._db.execute("UPDATE app_errors SET seen=1 WHERE id IN (" + ",".join("?" * len(ids)) + ")", tuple(ids))
            self._db.commit()

    def clear(self, file: str) -> int:
        """Forget a file's faults — the agent rewrote it, so the old run says nothing about the new one."""
        with self._lock:
            n = self._db.execute("DELETE FROM app_errors WHERE file=?", ((file or "").strip(),)).rowcount
            self._db.commit()
        return int(n or 0)


def store_for(engine):
    """The engine's error store, attached on first use from the engine's own database. agent.py sits at
    the module-line ceiling the architecture test enforces, so this channel costs it nothing; an engine
    that was given a store explicitly (the tests, a caller) keeps the one it has."""
    store = getattr(engine, "app_errors", None)
    if store is None:
        path = getattr(getattr(engine, "graph", None), "db_path", None) or config.DB_PATH
        store = AppErrorStore(path)
        try:
            engine.app_errors = store
        except AttributeError:            # a frozen//slotted caller still gets a working store
            pass
    return store


# ---------------------------------------------------------------- the turn's view -------------------
def session_app_files(engine, session_id: str) -> List[str]:
    """The workspace files this session's app widgets are showing."""
    sessions = getattr(engine, "sessions", None)
    if sessions is None:
        return []
    try:
        widgets = sessions.widgets(session_id) or []
    except Exception:
        return []
    out = []
    for w in widgets:
        if w.get("type") != "app":
            continue
        props = w.get("props") or {}
        if isinstance(props, str):
            try:
                props = json.loads(props)
            except (ValueError, TypeError):
                props = {}
        f = (props.get("file") or w.get("file") or "").strip()
        if f and f not in out:
            out.append(f)
    return out


def app_error_block(engine, session_id: str) -> str:
    """The pinned notice, once per fault. Empty when the session shows no app or nothing is new."""
    store = store_for(engine)
    if store is None:
        return ""
    rows = store.unseen(session_app_files(engine, session_id))
    if not rows:
        return ""
    store.mark_seen([r["id"] for r in rows])
    lines = []
    for r in rows:
        where = f" line {r['line']}" if r.get("line") else ""
        src = f" [{r['source']}]" if r.get("source") else ""
        lines.append(f"- {r['file']}{where}: {r['kind']}: {r['message']}{src}")
    return ("=== THE APP ON THE CANVAS REPORTED AN ERROR (observed while it ran, not the user's words) ===\n"
            + "\n".join(lines)
            + "\nThis is about the file YOU wrote. Read it at the line named, fix the cause, write the file "
              "again. Call app_errors for the full list. Do not ask the user to copy the console.")


# ---------------------------------------------------------------- the served page -------------------
_REPORTER = """<script id="__hmgfu_app_errors">
(function(){
  var f=new URLSearchParams(location.search).get("path")||location.pathname,q=[],t=null,seen={};
  function flush(){t=null;if(!q.length)return;var b=JSON.stringify({file:f,errors:q.splice(0,q.length)});
    try{fetch("/api/app-errors",{method:"POST",headers:{"Content-Type":"application/json"},body:b,keepalive:true});}catch(e){}}
  function push(e){var k=e.kind+"|"+e.message+"|"+(e.line||"");if(seen[k])return;seen[k]=1;q.push(e);
    if(!t)t=setTimeout(flush,400);}
  window.addEventListener("error",function(e){push({kind:"error",message:String(e.message||e.type),
    source:String(e.filename||""),line:e.lineno||0});},true);
  window.addEventListener("unhandledrejection",function(e){var r=e.reason;
    push({kind:"unhandledrejection",message:String(r&&r.message?r.message:r)});});
  var ce=console.error;console.error=function(){push({kind:"console.error",
    message:Array.prototype.map.call(arguments,String).join(" ")});return ce.apply(console,arguments);};
  var of=window.fetch;if(of)window.fetch=function(){var u=String(arguments[0]&&arguments[0].url||arguments[0]||"");
    return of.apply(window,arguments).then(function(r){if(!r.ok)push({kind:"fetch",
      message:"HTTP "+r.status+" "+r.statusText,source:u});return r;},
      function(err){push({kind:"fetch",message:String(err),source:u});throw err;});};
  window.addEventListener("pagehide",flush);
})();
</script>
"""
_HEAD = re.compile(r"<head[^>]*>", re.IGNORECASE)


def instrument_html(html: str) -> str:
    """The page with the reporter installed FIRST, so a fault while the page's own scripts run is
    reported too. Only the response is changed; the file on disk is untouched, so the receipt hash
    that proves the step still matches."""
    text = html or ""
    m = _HEAD.search(text)
    if m:
        return text[:m.end()] + _REPORTER + text[m.end():]
    m = re.search(r"<!DOCTYPE[^>]*>", text, re.IGNORECASE)
    at = m.end() if m else 0
    return text[:at] + _REPORTER + text[at:]
