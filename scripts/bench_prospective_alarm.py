"""Phase 77.6 — prospective alarm bench: (1) a FROZEN-CLOCK walk over N synthetic time triggers with random due instants —
each must fire at the FIRST tick >= its due instant and never before (false fires = 0, late fires = 0, misses = 0);
(2) a LIVE ticker on a throwaway store for --live-seconds with nothing due → zero notifications (no false fires under a
real thread and a real clock). Versioned output; the production database is never touched (throwaway DB under scratch)."""
from __future__ import annotations

import argparse
import os
import random
import sys
import time
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from _bench_paths import throwaway_db, write_versioned  # noqa: E402
from hmgfu.prospective import ProspectiveStore  # noqa: E402
from hmgfu.prospective_alarm import AlarmTicker, fire_due  # noqa: E402


class _Settings:
    def __init__(self, tick): self.d = {"prospective_enabled": True, "prospective_tick_s": tick}
    def get(self, k): return self.d.get(k)


class _Engine:
    def __init__(self, path, tick=30):
        self.prospective = ProspectiveStore(path); self.settings = _Settings(tick)
    def _emit(self, ev): pass


def frozen_walk(n: int, seed: int, tick_s: int) -> dict:
    rng = random.Random(seed)
    e = _Engine(throwaway_db("prospective_alarm_frozen"))
    t0 = datetime(2026, 9, 6, 8, 0, tzinfo=timezone(timedelta(hours=2)))
    due_of = {}
    for i in range(n):
        due = t0 + timedelta(seconds=rng.randint(1, 6 * 3600))
        row = e.prospective.add("bench", {"kind": "time", "due": due.isoformat(timespec="seconds"), "text": f"item {i}", "keywords": []}, 0, "bench")
        due_of[row["id"]] = due
    # a few condition triggers: the ticker must never fire them
    for i in range(5):
        e.prospective.add("bench", {"kind": "condition", "due": None, "condition": "nelson replies", "keywords": ["nelson"], "text": f"cond {i}"}, 0, "bench")
    false_fires = late_fires = 0
    fired_at = {}
    now = t0
    end = t0 + timedelta(hours=6, minutes=1)
    while now <= end:
        for row in fire_due(e, now.isoformat(timespec="seconds")):
            if row["kind"] != "time" or row["id"] not in due_of:
                false_fires += 1; continue
            fired_at[row["id"]] = now
            if now < due_of[row["id"]]:
                false_fires += 1
            elif (now - due_of[row["id"]]).total_seconds() >= tick_s:
                late_fires += 1                                   # fired later than the first tick >= due
        now += timedelta(seconds=tick_s)
    misses = len(due_of) - len(fired_at)
    conds_left = sum(1 for t in e.prospective.pending() if t["kind"] == "condition")
    return {"n": n, "tick_s": tick_s, "fired": len(fired_at), "false_fires": false_fires, "late_fires": late_fires, "misses": misses,
            "condition_triggers_untouched": conds_left == 5, "notifications": len(e.prospective.notifications(10000))}


def live_idle(seconds: float) -> dict:
    e = _Engine(throwaway_db("prospective_alarm_live"), tick=1)
    far = (datetime.now().astimezone() + timedelta(days=1)).isoformat(timespec="seconds")
    e.prospective.add("bench", {"kind": "time", "due": far, "text": "tomorrow", "keywords": []}, 0, "bench")
    t = AlarmTicker(e).start()
    time.sleep(seconds)
    t.stop()
    return {"seconds": seconds, "ticks": t.ticks, "fired": t.fired, "notifications": len(e.prospective.notifications()), "pending": len(e.prospective.pending())}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=20260906)
    ap.add_argument("--tick", type=int, default=30)
    ap.add_argument("--live-seconds", type=float, default=20.0)
    args = ap.parse_args()
    frozen = frozen_walk(args.n, args.seed, args.tick)
    live = live_idle(args.live_seconds)
    ok = frozen["false_fires"] == 0 and frozen["late_fires"] == 0 and frozen["misses"] == 0 and frozen["condition_triggers_untouched"] \
        and live["fired"] == 0 and live["notifications"] == 0 and live["ticks"] >= max(1, int(args.live_seconds) - 2)
    print(f"FROZEN WALK n={frozen['n']} tick={frozen['tick_s']}s · fired {frozen['fired']} · false fires {frozen['false_fires']} · "
          f"late fires {frozen['late_fires']} · misses {frozen['misses']} · condition triggers untouched {frozen['condition_triggers_untouched']}")
    print(f"LIVE IDLE {live['seconds']}s · ticks {live['ticks']} · fired {live['fired']} · notifications {live['notifications']} · pending {live['pending']}")
    print("PASS" if ok else "FAIL")
    print("versioned:", write_versioned("bench_prospective_alarm", {"frozen": frozen, "live": live, "ok": ok}))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
