"""Receipts — every executed action leaves a durable record; every plan step is verified against the WORLD
(Phase 71 / Codex M2). `tool succeeded` is not `step completed`.

A receipt is opened BEFORE dispatch (status `pending` = the intended action is persisted first) and closed after
(status, summary, observed effects: files with sha256, widget ids, exit codes). A step's post-condition is derived
deterministically from its text — the files it names must exist and be backed by a receipt, a "widget" step needs a
widget receipt, a step naming a tool needs a successful receipt of that tool, any other step needs some successful
receipt — and a receipt can be consumed by exactly one step. Receipts left `pending` by a crash are UNKNOWN OUTCOME
and are shown to the model on resume so it verifies the world before repeating the action.
"""
from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
import re
import sqlite3
import threading
import uuid
from typing import List, Optional, Tuple

from . import config
from .db import connect as db_connect
from .models import now_iso

log = logging.getLogger(__name__)

# a FILE is a token with a known extension — never an abbreviation such as "e.g." or "i.e." (71.7 live finding)
_EXT = r"(?:txt|md|html?|css|js|jsx|ts|tsx|json|ya?ml|toml|ini|cfg|csv|tsv|xml|pdf|png|jpe?g|gif|svg|py|sh|bat|ps1|sql|log|env|lock|zip)"
# 82.4 (Codex A3): the requested path keeps its DIRECTORY — `new/report.md` is not `old/report.md`
_FILE = re.compile(r"(?<![\w/\\])((?:[\w.-]+[/\\])*[\w][\w-]*(?:\.[\w-]+)*\." + _EXT + r")\b", re.IGNORECASE)
_WIDGET_NAME = re.compile(r"(?:create|update)_widget\s*:\s*([\w-]+)|\bwidget\s+(?:called|named|chamad[oa])\s+([\w-]+)|"
                          r"\b(?:the|a|o|um|uma)\s+([\w-]+)\s+widget\b", re.IGNORECASE)
# a THINKING step (identify/decide/analyse…) changes nothing in the world: it needs no receipt and consumes none
_THINK = re.compile(r"^\s*(?:identify|decide|determine|analy[sz]e|assess|review|consider|choose|select|plan|clarify|"
                    r"understand|confirm|gather|identificar|decidir|determinar|analisar|avaliar|rever|escolher|planear|"
                    r"esclarecer|perceber|recolher)\b", re.IGNORECASE)
_WIDGET = re.compile(r"\bwidgets?\b|\b(?:create|update)_widget\b", re.IGNORECASE)
_READ_TOOLS = {"read_file", "list_files", "memory_search", "memory_timeline", "memory_zoom", "tool_search"}
SUCCESS = ("ok", "already_present")


ARG_CAP = 4000          # per receipt column; documented in README (receipts)


def _string_slots(node, out) -> None:
    """Every string leaf in a JSON-shaped value, as (container, key) pairs that can be written back."""
    if isinstance(node, dict):
        for k, v in node.items():
            out.append((node, k)) if isinstance(v, str) else _string_slots(v, out)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            out.append((node, i)) if isinstance(v, str) else _string_slots(v, out)


def capped_json(obj, cap: int = ARG_CAP) -> str:
    """A JSON document that fits `cap` and still PARSES. 95.73: `json.dumps(obj)[:cap]` chopped a 4 KB
    write_file argument mid-string, and every later read of that session raised JSONDecodeError — which
    killed the turn in end_turn after the work was already done. Clip the longest string value instead,
    keeping the keys (they are what step verification matches on) and the structure (effects are read
    by shape: files[].path, widget_id)."""
    doc = copy.deepcopy(obj if isinstance(obj, (dict, list)) else (obj or {}))
    raw = json.dumps(doc)
    if len(raw) <= cap:
        return raw
    for _ in range(200):
        slots = []
        _string_slots(doc, slots)
        slots = [(c, k) for c, k in slots if len(c[k]) > 24]
        if not slots:
            break
        c, k = max(slots, key=lambda s: len(s[0][s[1]]))
        keep = max(24, len(c[k]) - (len(raw) - cap) - 16)
        c[k] = c[k][:keep] + "…[clipped]"
        if isinstance(doc, dict):
            doc["_clipped"] = True
        raw = json.dumps(doc)
        if len(raw) <= cap:
            return raw
    return json.dumps({"_clipped": True})          # last resort: still a document the store can read


def loads_json(raw: str, what: str = "") -> dict:
    """Read a receipt column. A row chopped by the old cap is recovered as text — its words still name
    the file or widget the step is verified against — and never raised into the turn."""
    try:
        return json.loads(raw or "{}")
    except (ValueError, TypeError):
        log.warning("receipt %s: column is not valid JSON (%d chars) — recovered as text", what, len(raw or ""))
        return {"_unreadable": True, "text": (raw or "")[:ARG_CAP]}


class ReceiptStore:
    def __init__(self, db_path: Optional[str] = None):
        self._lock = threading.RLock()
        self._db = db_connect(db_path or config.DB_PATH)
        self._db.execute("CREATE TABLE IF NOT EXISTS receipts (id TEXT PRIMARY KEY, session_id TEXT, turn_seq INTEGER, "
                         "step_index INTEGER, tool TEXT, args TEXT, effect TEXT, authorization TEXT, status TEXT, "
                         "started_at TEXT, finished_at TEXT, summary TEXT, effects TEXT, consumed_by INTEGER)")
        self._db.execute("CREATE INDEX IF NOT EXISTS receipts_session ON receipts(session_id)")
        self._db.commit()

    def open(self, session_id: str, turn_seq: int, tool: str, args: dict, effect: str, authorization: str,
             step_index: Optional[int], status: str = "pending") -> str:
        rid = uuid.uuid4().hex[:12]
        with self._lock:
            self._db.execute("INSERT INTO receipts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                             (rid, session_id or "", int(turn_seq or 0), step_index, tool, capped_json(args or {}),
                              effect, authorization or "", status, now_iso(), None, "", "{}", None))
            self._db.commit()
        return rid

    def close(self, rid: str, status: str, summary: str, effects: dict) -> None:
        with self._lock:
            self._db.execute("UPDATE receipts SET status=?, finished_at=?, summary=?, effects=? WHERE id=?",
                             (status, now_iso(), (summary or "")[:300], capped_json(effects or {}), rid))
            self._db.commit()

    def _rows(self, where: str, params: tuple) -> List[dict]:
        with self._lock:
            rows = self._db.execute("SELECT id, session_id, turn_seq, step_index, tool, args, effect, authorization, status, "
                                    "started_at, finished_at, summary, effects, consumed_by FROM receipts " + where, params).fetchall()
        out = []
        for r in rows:
            out.append({"id": r[0], "session_id": r[1], "turn_seq": r[2], "step_index": r[3], "tool": r[4],
                        "args": loads_json(r[5], r[0]), "effect": r[6], "authorization": r[7], "status": r[8],
                        "started_at": r[9], "finished_at": r[10], "summary": r[11], "effects": loads_json(r[12], r[0]),
                        "consumed_by": r[13]})
        return out

    def for_session(self, session_id: str) -> List[dict]:
        return self._rows("WHERE session_id=? ORDER BY started_at", (session_id,))

    def by_ids(self, ids: List[str]) -> List[dict]:
        """95.4b-ii: the receipts a settled plan's steps cite as evidence."""
        ids = [i for i in (ids or []) if i]
        return self._rows("WHERE id IN (" + ",".join("?" * len(ids)) + ")", tuple(ids)) if ids else []

    def pending(self, session_id: str) -> List[dict]:
        return self._rows("WHERE session_id=? AND status='pending' ORDER BY started_at", (session_id,))

    def cancel_pending(self, session_id: str) -> int:
        with self._lock:
            n = self._db.execute("UPDATE receipts SET status='cancelled', finished_at=? WHERE session_id=? AND status='pending'",
                                 (now_iso(), session_id)).rowcount
            self._db.commit()
        return n

    def consume(self, ids: List[str], step_index: int) -> None:
        with self._lock:
            for rid in ids:
                self._db.execute("UPDATE receipts SET consumed_by=? WHERE id=? AND consumed_by IS NULL", (int(step_index), rid))
            self._db.commit()


def file_sha(path: str) -> str:
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
    except OSError:
        return ""
    return h.hexdigest()


def observe_effects(tool: str, args: dict, outcome: str, workspace: str) -> dict:
    """What the world shows after the action (not what the model said)."""
    try:
        data = json.loads(outcome or "{}")
    except (json.JSONDecodeError, ValueError, TypeError):
        data = {}
    if not isinstance(data, dict):
        return {}
    if tool == "write_file" and data.get("path"):
        full = str(data["path"])
        ws = os.path.realpath(workspace) if workspace else ""
        rel = os.path.relpath(os.path.realpath(full), ws) if ws and os.path.realpath(full).startswith(ws) else os.path.basename(full)
        entry = {"path": rel.replace("\\", "/"), "sha256": file_sha(full), "bytes": data.get("bytes")}
        # 95.78 (D5): what the artefact still admits about itself, read from the CONTENT that was
        # written rather than from the stored args, which the size cap may have clipped.
        from .artefacts import placeholders_in
        marks = placeholders_in(str((args or {}).get("content") or ""))
        if marks:
            entry["placeholders"] = marks
        return {"files": [entry], "already_present": bool(data.get("already_present"))}
    if tool in ("create_widget", "update_widget") and data.get("widget_id"):
        return {"widgets": [data["widget_id"]]}
    if tool == "bash":
        return {"exit_code": data.get("exit_code")}
    return {}


def norm_path(p: str) -> str:
    """82.4: one spelling for a workspace-relative path — forward slashes, lower case, no leading ./"""
    s = (p or "").replace("\\", "/").strip().lower()
    while s.startswith("./"):
        s = s[2:]
    return s.lstrip("/")


def _same_file(requested: str, written: str) -> bool:
    """The receipt's path is the requested one: equal after normalisation, or the request named no directory and the
    basenames agree (a bare `report.md` accepts the file wherever it was written — the pre-82.4 behaviour, kept)."""
    rq, wr = norm_path(requested), norm_path(written)
    return rq == wr or ("/" not in rq and os.path.basename(wr) == rq)


def requested_widget(step_text: str) -> Optional[str]:
    """82.4: the widget a step names (`create_widget: Links`, `the links widget`, `widget called Budget`) or None."""
    m = _WIDGET_NAME.search(step_text or "")
    if not m:
        return None
    name = next((g for g in m.groups() if g), None)
    return None if not name or name.lower() in ("new", "this", "that", "novo", "nova", "este", "esta", "same") else name


def postcondition(step_text: str, tool_names) -> dict:
    """The deterministic post-condition a step text implies."""
    from .session_plans import tools_for_step
    text = step_text or ""
    files = [norm_path(f) for f in _FILE.findall(text)]
    tools = [t for t in tools_for_step(text, tool_names) if t != "write_file" or not files]
    widget = bool(_WIDGET.search(text)) and not files
    thinking = bool(_THINK.match(text)) and not files and not widget and not tools
    return {"files": files, "widget": widget, "thinking": thinking,
            "tools": [t for t in tools if t not in ("create_widget", "update_widget")] if widget else tools}


def _matches_action(step_text: str, receipt: dict) -> bool:
    """90.2: a receipt for a step that names no tool must still be the REQUESTED action — the step's salient words meet the
    receipt's tool name or arguments ("check my broader memory … links" ↔ memory_search(query="links …"); an unrelated
    list_files never proves it)."""
    from .textnorm import salient
    words = set(salient(step_text or "", min_len=4))
    if not words:                      # a step with no salient words ("b") cannot name an action: the turn constraint alone applies
        return True
    tool_words = set((receipt.get("tool") or "").lower().split("_"))
    arg_words = set(salient(json.dumps(receipt.get("args") or {}, ensure_ascii=False), min_len=4))
    return bool(words & (tool_words | arg_words))


def _built_as_file(want: str, usable: List[dict], workspace: str) -> Optional[dict]:
    """95.75 (P2): the receipt that produced the named artefact as a FILE. "Widget" is the user's word
    for the thing being built as often as it is the canvas object, and the live session wrote
    weather_widget.html and was then refused its own step for having touched no canvas widget. Same
    standard as the file route: a write receipt, the file on disk, the hash unchanged."""
    w = norm_path(want)
    if not w:
        return None
    for rec in usable:
        if rec.get("tool") in _READ_TOOLS:
            continue
        for entry in (rec.get("effects") or {}).get("files", []):
            base = os.path.basename(norm_path(entry.get("path", "")))
            if w not in base or not entry.get("sha256"):
                continue
            full = os.path.join(workspace or "", entry.get("path") or "")
            if os.path.isfile(full) and file_sha(full) == entry["sha256"]:
                return rec
    return None


def verify_step(step_text: str, receipts: List[dict], workspace: str, tool_names, turn_seq: Optional[int] = None) -> Tuple[bool, List[str], List[str]]:
    """(ok, evidence receipt ids, what is missing). Uses only successful, unconsumed receipts and the world. 90.2: with
    `turn_seq`, a step that names no file, widget or tool is proven only by a receipt of THIS turn for the requested action."""
    pc = postcondition(step_text, tool_names)
    if pc.get("thinking"):
        return (True, [], [])                       # nothing in the world to verify; consume no receipt
    usable = [r for r in receipts if r.get("status") in SUCCESS and r.get("consumed_by") is None]
    if pc["files"]:
        evidence, missing = [], []
        for f in pc["files"]:
            # 82.4 (A3): only a WRITE receipt for the requested path (directory included) can prove a file step
            hit, entry = None, None
            for cand in usable:
                if cand.get("tool") in _READ_TOOLS:
                    continue
                entry = next((x for x in (cand.get("effects") or {}).get("files", []) if _same_file(f, x.get("path", ""))), None)
                if entry is not None:
                    hit = cand; break
            if hit is None:
                missing.append(f"{f}: no receipt wrote it"); continue
            full = os.path.join(workspace or "", entry.get("path") or f)
            if not os.path.isfile(full):
                missing.append(f"{f}: missing on disk"); continue
            if not entry.get("sha256"):
                missing.append(f"{f}: the receipt carries no hash — unknown outcome, not done"); continue
            if file_sha(full) != entry["sha256"]:
                missing.append(f"{f}: content changed since the receipt"); continue
            evidence.append(hit["id"])
        return (not missing, evidence, missing)
    if pc["widget"]:
        want = requested_widget(step_text)
        def _touches(rec):
            eff = (rec.get("effects") or {}).get("widgets") or []
            if not eff:
                return False
            if not want:
                return True
            w = want.lower()
            return any(w in str(x).lower() for x in eff) or w in json.dumps(rec.get("args") or {}, ensure_ascii=False).lower()
        hit = next((r for r in usable if r["tool"] in ("create_widget", "update_widget") and _touches(r)), None)
        if hit is None:
            hit = _built_as_file(want, usable, workspace)      # 95.75 (P2): the artefact, wherever it landed
        why = "no widget was created or updated" if not want else f"no receipt touched the widget {want}"
        return (hit is not None, [hit["id"]] if hit else [], [] if hit else [why])
    if pc["tools"]:
        hit = next((r for r in usable if r["tool"] in pc["tools"]), None)
        return (hit is not None, [hit["id"]] if hit else [], [] if hit else [f"no successful run of {'/'.join(pc['tools'])}"])
    # 90.2: a generic step is proven by a receipt of THIS turn (when known) for the REQUESTED action — never by an earlier,
    # unrelated action (a turn-2 list_files once completed "check my broader memory for links" while nothing ran)
    same_turn = [r for r in usable if r["tool"] not in ("plan_task", "update_plan")
                 and (turn_seq is None or r.get("turn_seq") == turn_seq)]
    # 95.78 (D3): a step that asks for a CHANGE is never settled by a receipt that only read. The
    # effect is declared by the tool's schema and recorded on the receipt, so this reads what was
    # registered rather than guessing from the result text.
    from .speech_act import changes_the_world
    wants_change = changes_the_world(step_text)
    candidates = [r for r in same_turn if not (wants_change and r.get("effect") == "read")]
    hit = next((r for r in candidates if _matches_action(step_text, r)), None)
    why = ("no action ran for this step" if not usable else
           "this step asks for a change and only a read receipt matches it" if wants_change and same_turn and not candidates else
           "no receipt of this turn matches the requested action" if turn_seq is not None else "no receipt matches the requested action")
    return (hit is not None, [hit["id"]] if hit else [], [] if hit else [why])


# ---------------------------------------------------------------- engine helpers ------------------------------------
def _store(engine):
    return getattr(engine, "receipts", None)


def open_for(engine, tool: str, args: dict, turn_seq: int, status: str = "pending") -> Optional[str]:
    store = _store(engine)
    if store is None:
        return None
    from .authority import authorization, effect_of
    schemas = getattr(getattr(engine, "tools", None), "schemas", {}) or {}
    auth = authorization(engine) or {}
    plan = getattr(engine, "_turn_plan", None) or {}
    step = next((i for i, s in enumerate(plan.get("steps", [])) if s.get("status") == "active"), None)
    return store.open(getattr(engine, "_turn_session", None) or "", turn_seq, tool, args or {},
                      effect_of(tool, args, schemas.get(tool)), auth.get("origin") or "", step, status)


def close_for(engine, rid: Optional[str], tool: str, args: dict, outcome: str, failed: bool) -> None:
    store = _store(engine)
    if store is None or rid is None:
        return
    from .tool_builtins import get_workspace
    effects = observe_effects(tool, args or {}, outcome, get_workspace())
    status = "failed" if failed else ("already_present" if effects.get("already_present") else "ok")
    store.close(rid, status, (outcome or "")[:300], effects)


def verify_for(engine, step_text: str) -> Tuple[bool, List[str], List[str]]:
    store = _store(engine)
    if store is None:
        return (False, [], ["no receipt store"])
    from .tool_builtins import get_workspace
    names = list(getattr(getattr(engine, "tools", None), "schemas", {}) or [])
    return verify_step(step_text, store.for_session(getattr(engine, "_turn_session", None) or ""), get_workspace(), names,
                       turn_seq=getattr(engine, "_turn_seq", None) or None)            # 90.2: this turn's receipts only (0 = no turn running → unconstrained)
