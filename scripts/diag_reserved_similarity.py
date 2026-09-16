"""Phase 89.4 (Codex proposal §E, adopted) — a reserved set must be new by FAMILY, not only by literal text: for every reserved turn,
the nearest exemplar in the router's base by embedding cosine; report the distribution and every turn at or above the flag threshold.
Read-only (clone; the production DB is not touched). Usable for any future reserved set against any exemplar base."""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _bench_paths import SCRATCH  # noqa: E402
from bench_recall_truth import clone_live  # noqa: E402
from hmgfu import fu_math  # noqa: E402
from hmgfu.agent import AgentEngine  # noqa: E402
from hmgfu.knn_router import DEFAULT_SOURCES, ExemplarBase  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reserved", required=True, help="the reserved set (turns with text)")
    ap.add_argument("--flag", type=float, default=0.90, help="nearest-exemplar cosine at/above which a turn is flagged as a near-duplicate")
    ap.add_argument("--db", default=None)
    ap.add_argument("--base-texts", default=None, help="90.I2: build the base from another oracle's texts (conversation turns + questions) instead of the router's exemplar base")
    args = ap.parse_args()
    clone = os.path.join(SCRATCH, f"reserved_sim_{os.getpid()}.db"); clone_live(clone, args.db)
    e = AgentEngine(db_path=clone)
    def _texts(path):
        d = json.load(open(path, encoding="utf-8"))
        if "turns" in d:
            return [{"id": t["id"], "text": t["text"]} for t in d["turns"]]
        out = []
        for c in d["conversations"]:                      # a conversation set: every turn and the final question are texts
            out += [{"id": f"{c['id']}#t{i}", "text": t} for i, t in enumerate(c["turns"])]
            out.append({"id": f"{c['id']}#q", "text": c["question"]})
        return out
    if args.base_texts:
        class _B:                                          # the same shape ExemplarBase exposes: items with text + embedding
            pass
        base = _B(); base.items = [{"text": t["text"], "embedding": e.embed(t["text"])} for t in _texts(args.base_texts)]
    else:
        base = ExemplarBase(e.embed, str(e.settings.get("embed_model") or ""))
    turns = _texts(args.reserved)
    sims = []
    for t in turns:
        v = e.embed(t["text"])
        s, near = max(((fu_math.cosine(v, i["embedding"]), i["text"]) for i in base.items), key=lambda x: x[0])
        sims.append((s, t["id"], t["text"], near))
    ss = sorted(x[0] for x in sims)
    q = lambda p: ss[min(len(ss) - 1, int(p * len(ss)))]
    print(f"reserved {os.path.basename(args.reserved)} n={len(turns)} vs base {len(base.items)} texts ({os.path.basename(args.base_texts) if args.base_texts else ', '.join(os.path.basename(p) for p in DEFAULT_SOURCES)})")
    print(f"nearest-exemplar cosine: p10 {q(0.1):.3f} · p50 {q(0.5):.3f} · p90 {q(0.9):.3f} · max {ss[-1]:.3f} · literal duplicates {sum(1 for x in sims if x[0] >= 0.999)}")
    flagged = sorted((x for x in sims if x[0] >= args.flag), key=lambda x: -x[0])
    print(f"flagged at ≥ {args.flag:.2f}: {len(flagged)}/{len(turns)}")
    for s, tid, text, near in flagged:
        print(f"  {s:.3f} {tid} {text[:50]!r} ~ {near[:50]!r}")
    e.graph.close()
    try:
        os.remove(clone)
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
