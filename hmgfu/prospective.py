"""Prospective memory — TRIGGERS by time or condition (Phase 75.2). The user asks, in their own words, to be reminded
("lembra-me amanhã às 9 de ligar ao João", "remind me to send the invoice when Nelson replies"); a DETERMINISTIC
detector (PT/EN, no model call) writes a trigger row: kind `time` (a due instant resolved against the turn's local
clock) or `condition` (salient words of the condition clause). At turn start, due time triggers and condition triggers
whose words the current message carries FIRE: injected as a PROSPECTIVE block, emitted as an event with a transcript
pill, marked fired with the turn as receipt. The model never invents a trigger; "remind me what I said" is recall, not
a trigger; a cancel cue cancels the most recent pending one. Bounded and visible: setting `prospective_enabled`,
`GET /api/prospective`, `POST /api/prospective/{id}/cancel`; deleting the table restores stock behaviour."""
from __future__ import annotations

import json
import logging
import math
import re
import threading
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from . import config
from .db import connect as db_connect
from .models import now_iso
from .textnorm import norm as _norm, salient

log = logging.getLogger("hmgfu.prospective")

STATUSES = ("pending", "fired", "cancelled")
DEFAULT_HOUR = 9                    # "tomorrow" / "on monday" without a clock → 09:00 local
EVENING_HOUR = 20                   # "tonight" / "esta noite"

_LEAD = r"^\s*(?:(?:please|por favor|hey|ok|ah|podes|pode|poderias|can you|could you|will you|you could)[,\s]+)*"
_CUE = (r"(?:remind me|remind us|lembra[- ]me|lembre[- ]me|lembrem[- ]me|avisa[- ]me|avise[- ]me|recorda[- ]me|alert me|ping me|"
        r"nudge me|don'?t let me forget|n[aã]o me deixes esquecer|n[aã]o me deixe esquecer)")
_TRIGGER = re.compile(_LEAD + _CUE + r"\b(?P<rest>.*)$", re.IGNORECASE | re.DOTALL)
# after the cue, a WH word / "of what" = a recall question about the past, never a trigger
_RECALL = re.compile(r"^\s*(?:what|whats|what's|who|where|when|why|how|which|whether|if i|about what|of what|o que|do que|"
                     r"quem|onde|quando|porque|como|qual|quais|se eu)\b", re.IGNORECASE)
_CANCEL = re.compile(r"\b(?:cancel|cancela|cancelar|esquece|esquecer|forget|remove|apaga|apagar|delete)\b.{0,40}?"
                     r"\b(?:reminder|reminders|lembrete|lembretes|alerta|aviso|trigger)\b|"
                     r"\b(?:reminder|lembrete)\b.{0,20}?\b(?:cancel|cancela|off|n[aã]o (?:é|e) preciso)\b", re.IGNORECASE)

_REL = re.compile(r"\b(?:in|em|daqui a|dentro de|within)\s+(\d{1,3})\s*(minutes?|mins?|minutos?|hours?|hrs?|h|horas?|days?|dias?|weeks?|semanas?)\b",
                  re.IGNORECASE)
_DAY = re.compile(r"\b(tomorrow|amanh[aã]|today|hoje|tonight|esta noite|hoje [aà] noite|next week|na pr[oó]xima semana|"
                  r"semana que vem|next month|no pr[oó]ximo m[eê]s|monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
                  r"segunda(?:-feira)?|ter[cç]a(?:-feira)?|quarta(?:-feira)?|quinta(?:-feira)?|sexta(?:-feira)?|s[aá]bado|domingo)\b",
                  re.IGNORECASE)
_CLOCK = re.compile(r"\b(?:at|às|as|by|até|para as|pelas)\s*(\d{1,2})(?:[:h](\d{2}))?\s*(am|pm|h|horas)?\b", re.IGNORECASE)
_COND = re.compile(r"\b(when|whenever|as soon as|once|after|if|quando|sempre que|assim que|logo que|depois de|depois que|se|caso)\s+(?P<clause>.+)$",
                   re.IGNORECASE | re.DOTALL)
_WEEKDAYS = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
             "segunda": 0, "terca": 1, "quarta": 2, "quinta": 3, "sexta": 4, "sabado": 5, "domingo": 6}
def _resolve_due(rest: str, now: datetime) -> Optional[datetime]:
    """Due instant from a relative span, a day word and/or a clock; None when the text carries no time."""
    low = _norm(rest)
    m = _REL.search(low)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        if unit.startswith(("min",)):
            return now + timedelta(minutes=n)
        if unit.startswith(("h",)):
            return now + timedelta(hours=n)
        if unit.startswith(("d",)):
            return (now + timedelta(days=n)).replace(hour=DEFAULT_HOUR, minute=0, second=0, microsecond=0)
        return (now + timedelta(weeks=n)).replace(hour=DEFAULT_HOUR, minute=0, second=0, microsecond=0)
    day = _DAY.search(low)
    clock = _CLOCK.search(low)
    base = None
    if day:
        w = day.group(1)
        if w in ("tomorrow", "amanha"):
            base = now + timedelta(days=1)
        elif w in ("today", "hoje"):
            base = now
        elif w in ("tonight", "esta noite", "hoje a noite"):
            return now.replace(hour=EVENING_HOUR, minute=0, second=0, microsecond=0)
        elif w in ("next week", "na proxima semana", "semana que vem"):
            base = now + timedelta(days=7)
        elif w in ("next month", "no proximo mes"):
            base = now + timedelta(days=30)
        else:
            key = w.split("-")[0]
            target = _WEEKDAYS.get(key)
            if target is not None:
                ahead = (target - now.weekday()) % 7 or 7
                base = now + timedelta(days=ahead)
    if clock:
        hour, minute, suffix = int(clock.group(1)), int(clock.group(2) or 0), (clock.group(3) or "").lower()
        if suffix == "pm" and hour < 12:
            hour += 12
        if suffix == "am" and hour == 12:
            hour = 0
        if not 0 <= hour <= 23 or not 0 <= minute <= 59:
            return None
        anchor = base or now
        due = anchor.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if base is None and due <= now:
            due += timedelta(days=1)                    # "at 9" after 9 o'clock means tomorrow 9
        return due
    if base is not None:
        return base.replace(hour=DEFAULT_HOUR, minute=0, second=0, microsecond=0)
    return None


def _payload(rest: str) -> str:
    text = _REL.sub(" ", rest)
    text = _CLOCK.sub(" ", text)
    text = _DAY.sub(" ", text)
    text = re.sub(r"^\s*(?:to|de|que|para|of|about)\s+", "", text.strip(), flags=re.IGNORECASE)
    return " ".join(text.split()).strip(" ,.;:!") [:200]


def detect(text: str, now_local_iso: str) -> Optional[dict]:
    """The trigger a user utterance sets, or None. {'kind': 'time'|'condition'|'cancel', 'due', 'condition', 'keywords', 'text'}."""
    text = (text or "").strip()
    if not text:
        return None
    if _CANCEL.search(text):
        return {"kind": "cancel"}
    m = _TRIGGER.match(text)
    if not m:
        return None
    rest = m.group("rest").strip()
    if not rest or _RECALL.match(rest):
        return None                                     # "remind me what I said about X" is recall, not a trigger
    now = datetime.fromisoformat(now_local_iso)
    cond = _COND.search(rest)
    due = _resolve_due(rest, now)
    if due is not None and (cond is None or cond.start() > (_REL.search(_norm(rest)) or _DAY.search(_norm(rest)) or _CLOCK.search(_norm(rest))).start()):
        payload = _payload(rest if cond is None else rest[:cond.start()])
        return {"kind": "time", "due": due.isoformat(timespec="seconds"), "condition": "", "keywords": [],
                "text": payload or _payload(rest)}
    if cond is not None:
        clause = cond.group("clause").strip(" ,.;:!")
        words = salient(clause)
        if not words:
            return None
        return {"kind": "condition", "due": None, "condition": clause[:200], "keywords": words,
                "text": _payload(rest[:cond.start()]) or clause[:200]}
    return None                                         # a bare "remind me to X" carries no trigger — ask, do not guess


def condition_fires(keywords: List[str], message: str) -> bool:
    if not keywords:
        return False
    toks = set(salient(message))
    need = max(1, math.ceil(len(keywords) / 2))
    return len(toks & set(keywords)) >= need


class ProspectiveStore:
    def __init__(self, db_path: Optional[str] = None):
        self._lock = threading.RLock()
        self._db = db_connect(db_path or config.DB_PATH)
        self._db.execute("CREATE TABLE IF NOT EXISTS prospective_triggers (id TEXT PRIMARY KEY, session_id TEXT, kind TEXT, "
                         "due TEXT, condition TEXT, keywords TEXT, text TEXT, status TEXT, created_turn INTEGER, created_at TEXT, "
                         "fired_turn INTEGER, fired_at TEXT, source TEXT)")
        # 77.6: a fire that happened while NO turn was open leaves a notification; delivered by the next turn or by the UI
        self._db.execute("CREATE TABLE IF NOT EXISTS prospective_notifications (id TEXT PRIMARY KEY, trigger_id TEXT, session_id TEXT, "
                         "kind TEXT, due TEXT, text TEXT, fired_at TEXT, fired_by TEXT, delivered_at TEXT, delivered_by TEXT)")
        self._db.commit()

    def add(self, session_id: str, trig: dict, turn_seq: int, source: str) -> dict:
        tid = uuid.uuid4().hex[:12]
        with self._lock:
            self._db.execute("INSERT INTO prospective_triggers VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                             (tid, session_id or "", trig["kind"], trig.get("due"), trig.get("condition") or "",
                              json.dumps(trig.get("keywords") or []), trig["text"], "pending", int(turn_seq or 0), now_iso(),
                              None, None, (source or "")[:300]))
            self._db.commit()
        return self.get(tid)

    def _rows(self, where: str, params: tuple = ()) -> List[dict]:
        with self._lock:
            rows = self._db.execute("SELECT id, session_id, kind, due, condition, keywords, text, status, created_turn, created_at, "
                                    "fired_turn, fired_at, source FROM prospective_triggers " + where, params).fetchall()
        return [{"id": r[0], "session_id": r[1], "kind": r[2], "due": r[3], "condition": r[4], "keywords": json.loads(r[5] or "[]"),
                 "text": r[6], "status": r[7], "created_turn": r[8], "created_at": r[9], "fired_turn": r[10], "fired_at": r[11],
                 "source": r[12]} for r in rows]

    def get(self, tid: str) -> Optional[dict]:
        rows = self._rows("WHERE id=?", (tid,))
        return rows[0] if rows else None

    def pending(self) -> List[dict]:
        return self._rows("WHERE status='pending' ORDER BY created_at")

    def all(self, limit: int = 100) -> List[dict]:
        return self._rows("ORDER BY created_at DESC LIMIT ?", (int(limit),))

    def set_status(self, tid: str, status: str, turn_seq: Optional[int] = None) -> Optional[dict]:
        with self._lock:
            if status == "fired":
                self._db.execute("UPDATE prospective_triggers SET status=?, fired_turn=?, fired_at=? WHERE id=?",
                                 (status, int(turn_seq) if turn_seq is not None else None, now_iso(), tid))   # 77.6: no turn → NULL
            else:
                self._db.execute("UPDATE prospective_triggers SET status=? WHERE id=?", (status, tid))
            self._db.commit()
        return self.get(tid)

    def cancel_latest(self) -> Optional[dict]:
        pend = self.pending()
        return self.set_status(pend[-1]["id"], "cancelled") if pend else None

    # ---- 77.6: fires outside a turn leave a NOTIFICATION (one lock around status + row: a turn starting at the same
    # instant sees either "pending" or "fired + notification", never a fired trigger without its row)
    def fire(self, tid: str, turn_seq: Optional[int] = None, by: str = "turn") -> Optional[dict]:
        with self._lock:
            row = self.get(tid)
            if row is None or row["status"] != "pending":
                return None
            self.set_status(tid, "fired", turn_seq)
            if by != "turn":
                self._db.execute("INSERT INTO prospective_notifications VALUES (?,?,?,?,?,?,?,?,?,?)",
                                 (uuid.uuid4().hex[:12], tid, row["session_id"], row["kind"], row["due"], row["text"], now_iso(), by,
                                  None, None))
                self._db.commit()
            return self.get(tid)

    def _notif_rows(self, where: str, params: tuple = ()) -> List[dict]:
        with self._lock:
            rows = self._db.execute("SELECT id, trigger_id, session_id, kind, due, text, fired_at, fired_by, delivered_at, delivered_by "
                                    "FROM prospective_notifications " + where, params).fetchall()
        return [{"id": r[0], "trigger_id": r[1], "session_id": r[2], "kind": r[3], "due": r[4], "text": r[5], "fired_at": r[6],
                 "fired_by": r[7], "delivered_at": r[8], "delivered_by": r[9]} for r in rows]

    def undelivered(self) -> List[dict]:
        return self._notif_rows("WHERE delivered_at IS NULL ORDER BY fired_at")

    def notifications(self, limit: int = 100) -> List[dict]:
        return self._notif_rows("ORDER BY fired_at DESC LIMIT ?", (int(limit),))

    def mark_delivered(self, ids: List[str], by: str) -> int:
        if not ids:
            return 0
        with self._lock:
            cur = self._db.execute(f"UPDATE prospective_notifications SET delivered_at=?, delivered_by=? WHERE delivered_at IS NULL "
                                   f"AND id IN ({','.join('?' * len(ids))})", (now_iso(), by, *ids))
            self._db.commit()
            return cur.rowcount

    def close(self) -> None:
        self._db.close()


def due_now(store: ProspectiveStore, now_local_iso: str, message: str, turn_seq: int) -> List[dict]:
    """Pending triggers that fire on this turn: time triggers past due, condition triggers the message carries.
    A trigger never fires on the turn that set it."""
    now = datetime.fromisoformat(now_local_iso)
    out = []
    for t in store.pending():
        if t["created_turn"] >= int(turn_seq or 0):
            continue
        if t["kind"] == "time" and t["due"] and datetime.fromisoformat(t["due"]) <= now:
            out.append(t)
        elif t["kind"] == "condition" and condition_fires(t["keywords"], message):
            out.append(t)
    return out


def render_fired(fired: List[dict]) -> str:
    lines = ["=== PROSPECTIVE — reminders the user asked for that are DUE NOW: deliver them in this reply ==="]
    for t in fired:
        when = f"due {t['due'][:16]}" if t["kind"] == "time" else f"condition: {t['condition']}"
        lines.append(f"- {t['text']}  ({when}; asked as: \"{(t['source'] or '')[:100]}\")")
    return "\n".join(lines)


def render_late(late: List[dict]) -> str:
    """77.6: reminders that came due while no conversation was open — the turn delivers them, once."""
    lines = ["=== PROSPECTIVE — reminders that came DUE while no conversation was open: deliver them in this reply ==="]
    for n in late:
        lines.append(f"- {n['text']}  (due {(n['due'] or '')[:16]}; fired {(n['fired_at'] or '')[:16]})")
    return "\n".join(lines)


def render_set(t: dict) -> str:
    when = f"at {t['due'][:16]}" if t["kind"] == "time" else f"when: {t['condition']}"
    return f"=== REMINDER SET (deterministic, from the user's words) === \"{t['text']}\" — {when}. Confirm it briefly in your reply."


def begin_turn(engine, session_id: str, user_message: str, runtime, turn_seq: int) -> str:
    """Turn-start hook: fire what is due; capture a new trigger or a cancel from THIS message. Returns the prompt block."""
    if not engine.settings.get("prospective_enabled"):
        return ""
    store = engine.prospective
    now_iso_local = runtime.now_local
    blocks = []
    late = store.undelivered()                                   # 77.6: fired by the ticker while no conversation was open
    if late:
        store.mark_delivered([n["id"] for n in late], f"turn:{turn_seq}")
        engine._emit({"type": "prospective_fired", "turn_seq": turn_seq, "by": "ticker",
                      "items": [{"id": n["trigger_id"], "text": n["text"], "kind": n["kind"], "due": n["due"], "fired_at": n["fired_at"]}
                                for n in late]})
        blocks.append(render_late(late))
    fired = due_now(store, now_iso_local, user_message, turn_seq)
    for t in fired:
        store.fire(t["id"], turn_seq, by="turn")
    if fired:
        engine._emit({"type": "prospective_fired", "turn_seq": turn_seq,
                      "items": [{"id": t["id"], "text": t["text"], "kind": t["kind"], "due": t["due"]} for t in fired]})
        blocks.append(render_fired(fired))
    trig = detect(user_message, now_iso_local)
    if trig and trig["kind"] == "cancel":
        gone = store.cancel_latest()
        if gone is not None:
            engine._emit({"type": "prospective_cancelled", "turn_seq": turn_seq, "item": {"id": gone["id"], "text": gone["text"]}})
            blocks.append(f"=== REMINDER CANCELLED === \"{gone['text']}\" — confirm briefly.")
    elif trig:
        row = store.add(session_id, trig, turn_seq, user_message)
        engine._emit({"type": "prospective_set", "turn_seq": turn_seq,
                      "item": {"id": row["id"], "text": row["text"], "kind": row["kind"], "due": row["due"], "condition": row["condition"]}})
        blocks.append(render_set(row))
    return "\n\n".join(blocks)


def list_triggers(engine, limit: int = 100) -> List[dict]:
    return engine.prospective.all(limit)
