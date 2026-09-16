"""Prospective ALARM (Phase 77.6) — due TIME triggers fire without a turn.

Before this, a reminder set for 09:00 fired only when the user's next message arrived (75.2 fired at turn start). Now a
daemon ticker evaluates the pending time triggers against the host clock every `prospective_tick_s` seconds
(single-flight, like the scheduled full dream; 0 disables without a restart) and FIRES what is due: the trigger is
marked fired (no turn → `fired_turn` NULL) and a NOTIFICATION row is written. Delivery is whichever comes first — the
next turn renders the undelivered notifications as a PROSPECTIVE block and marks them delivered, or the UI polls
`GET /api/prospective/notifications` and acknowledges them. Condition triggers need a message; the ticker never fires them.
`fire_due` is a pure function of the clock (testable frozen); the thread only supplies the clock and the cadence."""
from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Callable, List, Optional

log = logging.getLogger("hmgfu.prospective_alarm")


def fire_due(engine, now_local_iso: str, by: str = "ticker") -> List[dict]:
    """Fire every pending TIME trigger whose due instant is <= now. Returns the fired rows (possibly empty)."""
    if not engine.settings.get("prospective_enabled"):
        return []
    now = datetime.fromisoformat(now_local_iso)
    fired = []
    for t in engine.prospective.pending():
        if t["kind"] != "time" or not t["due"]:
            continue
        if datetime.fromisoformat(t["due"]) <= now:
            row = engine.prospective.fire(t["id"], None, by=by)
            if row is not None:
                fired.append(row)
    if fired:
        log.info("prospective alarm fired %d trigger(s) without a turn", len(fired))
    return fired


class AlarmTicker:
    """Daemon thread: every `prospective_tick_s` seconds (read live; 0 = idle) call fire_due with the current local clock."""

    def __init__(self, engine, clock: Optional[Callable[[], str]] = None):
        self.engine = engine
        self._clock = clock or _local_now_iso
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.ticks = 0
        self.fired = 0

    def _interval(self) -> float:
        try:
            return float(self.engine.settings.get("prospective_tick_s") or 0)
        except Exception:
            return 0.0

    def run_once(self) -> List[dict]:
        self.ticks += 1
        fired = fire_due(self.engine, self._clock())
        self.fired += len(fired)
        return fired

    def _loop(self) -> None:
        while not self._stop.is_set():
            interval = self._interval()
            if interval > 0:
                try:
                    self.run_once()
                except Exception as exc:                                   # never let the alarm kill the process
                    log.warning("prospective alarm tick failed (non-fatal): %s", exc)
            self._stop.wait(interval if interval > 0 else 5.0)          # 0 = idle poll of the setting every 5 s

    def start(self) -> "AlarmTicker":
        if self._thread is not None and self._thread.is_alive():
            return self                                                  # single-flight
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="hmgfu-prospective-alarm")
        self._thread.start()
        return self

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout)

    @property
    def alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()


def _local_now_iso() -> str:
    from .runtime_context import RuntimeContext
    return RuntimeContext.capture().now_local


def start_ticker(engine) -> AlarmTicker:
    ticker = getattr(engine, "_alarm_ticker", None)
    if ticker is None:
        ticker = engine._alarm_ticker = AlarmTicker(engine)
    ticker.start()
    log.info("prospective alarm ticker up (every %ss; 0 = idle)", engine.settings.get("prospective_tick_s"))
    return ticker


def stop_ticker(engine) -> None:
    ticker = getattr(engine, "_alarm_ticker", None)
    if ticker is not None:
        ticker.stop()
