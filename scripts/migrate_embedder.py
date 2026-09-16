"""Phase 59 — embedder migration: nomic-embed-text (768-dim) → bge-m3 (1024-dim).

PROVEN worth it before writing this (Rule 12): scripts/probe_crosslingual.py measured cross-lingual
retention 37% (nomic) → 100% (bge-m3) — a PT sentence and its EN translation go from 0.578 (noise
floor) to 0.936 (same-language ceiling). This migrates the stored graph to the new space.

Re-embeds every non-macro point from its content, then REBUILDS the embedding-derived relational
structure by REUSING the canonical ingest functions (find_relation_candidates / build_fu_edges /
compute_density) — NOT a reimplementation. Macro centroids are recomputed as the mean of their
members' new embeddings. Hex layout is KEPT (it is visualization; recall uses embeddings + edges,
and base_separation via stale hex distance is negligible — a full re-layout is a separate cosmetic
follow-up).

SAFETY: runs on a CLONE only (SQLite online-backup, read-only source) — production hmgfu.db is NEVER
opened for writing. Verify-heavy: asserts a single post-migration embedding dimension and preserved
counts, and prints a cross-lingual recall sanity check on the migrated graph.

Run:  .venv/Scripts/python scripts/migrate_embedder.py           (target defaults to bge-m3)
      HMGFU_MIGRATE_TARGET=multilingual-e5-large .venv/Scripts/python scripts/migrate_embedder.py
The clone is written to scratch/migrate_<target>.db and left in place for inspection / promotion.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# HMGFuEngine.embed() → client.embed() reads config.EMBED_MODEL (NOT the settings registry), and
# config reads HMGFU_EMBED_MODEL at IMPORT — so the target embedder must be set BEFORE importing config.
TARGET = os.environ.get("HMGFU_MIGRATE_TARGET", "bge-m3")
os.environ["HMGFU_EMBED_MODEL"] = TARGET

from hmgfu import config, fu_math                         # noqa: E402
from hmgfu.chat import HMGFuEngine                         # noqa: E402
from hmgfu.ingest import (assign_hex, build_fu_edges,      # noqa: E402,F401
                          find_relation_candidates)

SCRATCH = ROOT / "scratch"


def clone_production() -> str:
    SCRATCH.mkdir(exist_ok=True)
    clone = str(SCRATCH / f"migrate_{TARGET.replace(':', '_').replace('/', '_')}.db")
    if os.path.exists(clone):
        os.remove(clone)
    src = sqlite3.connect(f"file:{config.DB_PATH}?mode=ro", uri=True)   # READ-ONLY source
    dst = sqlite3.connect(clone)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return clone


def _mean(vectors):
    n = len(vectors)
    dim = len(vectors[0])
    acc = [0.0] * dim
    for v in vectors:
        for i in range(dim):
            acc[i] += v[i]
    return [x / n for x in acc]


def main() -> int:
    t0 = time.perf_counter()
    print(f"=== EMBEDDER MIGRATION → {TARGET} (clone-only; production is never written) ===")
    clone = clone_production()
    print(f"cloned production → {clone}")

    engine = HMGFuEngine(db_path=clone)
    if not engine.client.available():
        print("FAIL: Ollama unreachable")
        return 1
    dim = len(engine.embed("dimension probe"))   # HMGFuEngine.embed uses config.EMBED_MODEL (=TARGET)
    print(f"target embedder live: {TARGET}  dim={dim}")
    if dim <= 0:
        print("FAIL: embedder returned an empty vector")
        return 1

    g = engine.graph
    all_pts = g.all_points()
    print(f"corpus: {len(all_pts)} points, {len(g.all_edges())} edges, {len(g.macro_sources)} macros")

    # 1) RE-EMBED EVERY point (macros included — an orphaned macro not in macro_sources still needs a
    # 1024-dim vector, else a stale 768 silently returns cosine 0). Member-having macros are refined
    # to their member-mean in step 4; this guarantees no point is ever left in the old space.
    print("\n[1/4] re-embedding points...")
    reembedded, skipped = 0, []
    for i, p in enumerate(all_pts):
        text = (p.content or p.summary or p.title
                or " ".join(p.keywords) or " ".join(p.entities) or p.type or p.id).strip()
        if text:
            p.embedding = engine.embed(text)
            g.save_point(p)
            reembedded += 1
        else:
            skipped.append(p.id)
        if (i + 1) % 200 == 0:
            print(f"    {i + 1}/{len(all_pts)}")
    print(f"    re-embedded {reembedded} points (skipped {len(skipped)} truly-empty: {skipped[:5]})")

    # 2) REBUILD edges from the new space (clear all, then canonical build — dedups via edge_between)
    print("[2/4] rebuilding fu_edges from the new embeddings...")
    g._db.execute("DELETE FROM fu_edges")
    g._db.commit()
    g.edges.clear()
    g._adjacency.clear()
    new_edges = 0
    active = g.active_points()
    for i, p in enumerate(active):
        for e in build_fu_edges(p, find_relation_candidates(p, g), g):
            g.save_edge(e)
            new_edges += 1
        if (i + 1) % 200 == 0:
            print(f"    {i + 1}/{len(active)}  (edges so far: {new_edges})")
    print(f"    rebuilt {new_edges} edges")

    # 3) recompute density (centrality changed) + stability
    print("[3/4] recomputing density + stability...")
    for p in g.active_points():
        p.density = fu_math.compute_density(p, g.centrality(p.id))
        p.stability = fu_math.compute_stability(p)
        g.save_point(p)

    # 4) recompute macro centroids = mean of members' new embeddings
    print("[4/4] recomputing macro centroids...")
    macros_done = 0
    for macro_id, member_ids in g.macro_sources.items():
        mp = g.points.get(macro_id)
        embs = [g.points[m].embedding for m in member_ids
                if m in g.points and g.points[m].embedding]
        if mp is not None and embs:
            mp.embedding = _mean(embs)
            g.save_point(mp)
            macros_done += 1
    print(f"    recomputed {macros_done} macro centroids")

    # ---- VERIFY (Rule 12) ----
    print("\n=== VERIFY ===")
    dims = sorted({len(p.embedding) for p in g.all_points() if p.embedding})
    print(f"embedding dims present: {dims}  (must be a single value == {dim})")
    ok_dim = dims == [dim]
    count_ok = len(g.all_points()) == len(all_pts)   # NO test data added — the clone is promotable
    print(f"points: {len(g.all_points())} (was {len(all_pts)}, unchanged={count_ok})   "
          f"edges: {len(g.all_edges())}")

    # NON-MUTATING cross-lingual sanity — prove the live embedder aligns PT↔EN on raw vectors, WITHOUT
    # ingesting a test fact (that would pollute a promotable graph). Graph is left exactly as migrated.
    pt_v = engine.embed("O meu carro está estacionado na garagem B nível 3.")
    en_v = engine.embed("My car is parked in garage B level 3.")
    un_v = engine.embed("I enjoy hiking in the mountains on weekends.")
    xl, floor = fu_math.cosine(pt_v, en_v), fu_math.cosine(pt_v, un_v)
    print(f"cross-lingual embed sanity (no graph mutation): PT↔EN cos={xl:.3f} vs unrelated {floor:.3f}")

    # make the clone SELF-CONTAINED + promotable: persist the embedder as a setting so any engine
    # opened on it (or a promoted production) uses TARGET, not the inherited nomic default.
    from hmgfu.settings import Settings
    Settings(clone).update({"embed_model": TARGET, "embed_provider": "ollama"})
    print(f"clone embed_model setting => {Settings(clone).get('embed_model')}")

    ok = ok_dim and count_ok
    print(f"\nRESULT: dim_ok={ok_dim}  count_ok={count_ok}  clone={clone}  "
          f"elapsed={time.perf_counter() - t0:.0f}s")
    print("Next: regression bench vs this clone (HMGFU_DB_PATH=clone), gemma must hold 34/34, "
          "THEN promote (back up production first).")
    engine.graph.close()
    engine.client.close()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
