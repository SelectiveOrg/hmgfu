"""Phase 56 gap-3 evidence: wormhole calibration against REAL production data (cloned).

Clones the live DB via SQLite online backup (read-only on production — Phase 31 discipline),
then runs successive calibrated wormhole passes: each pass tallies near-misses, the calibrator
relaxes the most-binding gate (bounded), and we stop when wormholes actually fire. Proves the
analogical self-organisation layer works on the real corpus and reports WHICH gate had kept it
dark for 59 dreams. The nano veto stays live when Ollama is up (the real quality gate).

Run:  .venv/Scripts/python scripts/probe_wormhole_calibration.py
"""

from __future__ import annotations

import os
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hmgfu import config  # noqa: E402
from hmgfu.chat import HMGFuEngine  # noqa: E402
from hmgfu.dream import create_wormhole, find_distant_analogical_pairs  # noqa: E402

from _bench_paths import throwaway_db  # noqa: E402

CLONE = throwaway_db("wormhole_calibration_clone.db")
MAX_PASSES = 10


def clone_live_db() -> None:
    if os.path.exists(CLONE):
        os.remove(CLONE)
    source = sqlite3.connect(config.DB_PATH)
    target = sqlite3.connect(CLONE)
    try:
        source.backup(target)          # SQLite online backup: production stays read-only
    finally:
        target.close()
        source.close()


def main() -> int:
    clone_live_db()
    engine = HMGFuEngine(db_path=CLONE)
    cal = engine.wormhole_calibrator
    print(f"clone: {engine.graph.stats()['points']} points | "
          f"nano veto: {'LIVE' if engine.sensitizer.enabled else 'off'}")
    print(f"baseline gates: { {k: v for k, v in config.WORMHOLE.items() if k.startswith('min') or k.startswith('max')} }")

    created_total = 0
    for i in range(1, MAX_PASSES + 1):
        near = {"minAnalogy": 0, "minSemantic": 0, "minDensity": 0}
        eff = cal.effective()
        pairs = find_distant_analogical_pairs(engine.graph, engine.sensitizer,
                                              thresholds=eff, near_misses=near)
        for a, b in pairs:
            engine.graph.save_edge(create_wormhole(a, b))
            print(f"  WORMHOLE: {a.title[:40]!r} <-> {b.title[:40]!r}")
        insight = cal.observe(near, len(pairs))
        gates = {k: round(eff[k], 2) for k in ("minAnalogy", "minSemantic", "minDensity")}
        print(f"pass {i}: created={len(pairs)} near_misses={near} gates={gates}"
              + (f"\n         -> {insight}" if insight else ""))
        created_total += len(pairs)
        if created_total:
            break

    final = {k: round(v, 2) for k, v in cal.effective().items()
             if k in ("minAnalogy", "minSemantic", "minDensity")}
    print(f"\nfinal calibrated gates: {final}")
    print(f"wormholes on real corpus: {created_total}")
    engine.graph.close()
    engine.client.close()
    print("PROBE:", "PASS" if created_total > 0 else "FAIL (no wormholes within bounds)")
    return 0 if created_total > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
