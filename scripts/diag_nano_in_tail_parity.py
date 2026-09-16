"""Phase 80.3 G3 — stored-point parity with `nano_in_tail` ON: for the 12 turns of the latency script, the pre-reply extraction
is heuristic+router (no nano call), the tail's enrich step runs the nano once, and the INGESTED point must carry the nano's
fields (extractor 'nano', its summary/type) while keeping the turn's route fields. Reported per message; on a clone of the
live DB; the nano's output is itself nondeterministic (temperature 0.1), so parity is on WHICH extractor's fields land, not
on byte equality between two nano calls."""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from _bench_paths import SCRATCH, write_versioned  # noqa: E402
from bench_latency import SCRIPT  # noqa: E402
from bench_recall_truth import clone_live  # noqa: E402
from hmgfu.agent import AgentEngine  # noqa: E402
from hmgfu.runtime_context import RuntimeContext  # noqa: E402
from hmgfu.turn_tail import ROUTE_FIELDS, enrich_for_ingest  # noqa: E402


def main() -> int:
    clone = os.path.join(SCRATCH, f"nano_in_tail_parity_{os.getpid()}.db")
    clone_live(clone)
    e = AgentEngine(db_path=clone)
    for key, val in {"grader_enabled": False, "tail_async": False, "full_dream_every_n_turns": 0, "mini_dream_every_n_turns": 0,
                     "nano_in_tail": True}.items():
        e.settings.set(key, val)
    if not e.client.available():
        print("FAIL: Ollama unreachable"); return 1
    rows, ok = [], 0
    for cls, text in SCRIPT:
        pre = e.sensitizer.extract(text, runtime_context=RuntimeContext.capture(), route=True, nano=False)
        full = enrich_for_ingest(e, pre, text)
        point = e.ingest(text, source="user", extracted=full, embedding=e.embed(text))
        routes_kept = all(full.get(k) == pre.get(k) for k in ROUTE_FIELDS if k in pre)
        good = pre.get("extractor") == "heuristic+router" and full.get("extractor") == "nano" and routes_kept and bool(point.summary)
        ok += bool(good)
        rows.append({"class": cls, "text": text, "pre_extractor": pre.get("extractor"), "stored_extractor": full.get("extractor"),
                     "routes_kept": routes_kept, "stored_type": point.type, "stored_summary": (point.summary or "")[:80], "ok": good})
        print(f"  [{'OK ' if good else 'BAD'}] {cls:8s} pre={pre.get('extractor')} stored={full.get('extractor')} routes_kept={routes_kept} "
              f"type={point.type} summary={point.summary[:60]!r}")
    print(f"PARITY {ok}/{len(rows)} · pre-reply extractor heuristic+router on all, stored extractor nano on all, route fields kept")
    print("versioned:", write_versioned("nano_in_tail_parity", {"ok": ok, "n": len(rows), "rows": rows}))
    e.graph.close(); e.client.close()
    return 0 if ok == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
