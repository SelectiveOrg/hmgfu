"""Import curated memories from PriorAgent's agent.db into this HMG-Fu graph.

READ-ONLY on the source (sqlite mode=ro URI — the PA3 db is a protected asset).
Everything is re-embedded with our embedder (PA3 vectors are mxbai-1024/hash — incompatible).
Idempotent: every imported point carries a `pa3:<table>:<id>` keyword; re-runs skip those.

What is imported (docs/PA3_LESSONS.md import decision):
  1. LIVE hmg_fact_statements            → type=fact,   layer L3_identity   (the gold)
  2. hmg_nodes active, kind in fact/preference/identity/directive → mapped types
  3. --include-declarative: active declarative nodes with importance >= 0.7

Usage:
  .venv/Scripts/python scripts/import_pa3.py [--dry-run] [--include-declarative] [--limit N]
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hmgfu import fu_math  # noqa: E402
from hmgfu.chat import HMGFuEngine  # noqa: E402
from hmgfu.ingest import assign_hex, build_fu_edges, find_relation_candidates  # noqa: E402
from hmgfu.models import MemoryPoint  # noqa: E402

PA3_DB = r"C:\Users\you\PriorAgent\data\agent.db"

SOURCE_MAP = {  # PA3 fact source → our source (trust mapping)
    "set_user_fact": "user_explicit", "user_correction": "user_explicit",
    "llm_curator": "assistant", "resolver": "system", "regex": "system",
    "system": "system", "unknown": "system",
}
KIND_MAP = {  # PA3 memory_kind → our type
    "fact": "fact", "preference": "fact", "identity": "fact",
    "directive": "decision", "declarative": "fact",
}
# Phase 56 root-cause fix: derived hmg_nodes import with source="assistant" — model-curated
# records, NOT user authorship — so they must NEVER land in the identity layers (that mapping
# put 1100+ episodic nodes in L3_identity and polluted the identity channel/injection). Only the
# GOLD hmg_fact_statements path below earns L3. Organic promotion can still lift a node to its
# taxonomy.layer_cap through real use.
LAYER_MAP = {"fact": "L1_session", "preference": "L1_session", "identity": "L1_session",
             "directive": "L1_session", "declarative": "L1_session"}


def existing_pa3_keys(engine) -> set:
    keys = set()
    for p in engine.graph.points.values():
        keys.update(kw for kw in p.keywords if kw.startswith("pa3:"))
    return keys


def import_point(engine, *, content, title, summary, source, pa3_key, mtype, layer,
                 confidence, importance, utility, novelty, emotional_intensity,
                 created_at, entities, topics, keywords, dry_run) -> bool:
    if dry_run:
        return True
    point = MemoryPoint(
        type=mtype, title=title[:80], content=content, summary=summary[:300],
        source=source, timestamp=created_at,
        embedding=engine.embed(content),
        keywords=(keywords or [])[:5] + [pa3_key],
        entities=entities or [], topics=topics or [],
        emotional_intensity=emotional_intensity, importance=importance,
        confidence=confidence, novelty=novelty, utility=utility,
        energy=0.25, layer=layer,
    )
    point.density = fu_math.compute_density(point, 0.0)
    point.hex = assign_hex(point, engine.graph)
    point.stability = fu_math.compute_stability(point)
    engine.graph.save_point(point)
    # wire Fu edges natively (no PA3 edges imported)
    for edge in build_fu_edges(point, find_relation_candidates(point, engine.graph, limit=15),
                               engine.graph)[:6]:
        engine.graph.save_edge(edge)
    return True


def norm_ts(value) -> str:
    """PA3 timestamps are REAL epoch or ISO text — normalise to ISO."""
    try:
        return time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(float(value)))
    except (TypeError, ValueError):
        s = str(value or "")
        return s if s else "2026-01-01T00:00:00+00:00"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--include-declarative", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="cap per table (0 = all)")
    args = ap.parse_args()

    src = sqlite3.connect(f"file:{PA3_DB.replace(os.sep, '/')}?mode=ro", uri=True)
    engine = HMGFuEngine()
    if not engine.client.available():
        print("FAIL: Ollama must be running (re-embedding needs the embedder)")
        return 1
    seen = existing_pa3_keys(engine)
    stats = {"facts": 0, "nodes": 0, "skipped": 0}

    # --- 1. LIVE fact statements -----------------------------------------------------
    rows = src.execute(
        "SELECT id, entity_key, value, confidence, source, statement_text, created_at "
        "FROM hmg_fact_statements "
        "WHERE superseded_by IS NULL AND (rejected IS NULL OR rejected=0) ORDER BY id"
    ).fetchall()
    if args.limit:
        rows = rows[:args.limit]
    for fid, key, value, confidence, source, statement, created in rows:
        pa3_key = f"pa3:facts:{fid}"
        if pa3_key in seen:
            stats["skipped"] += 1
            continue
        content = statement or f"{key.replace('_', ' ').replace(':', ': ')}: {value}"
        import_point(
            engine, content=content, title=key.replace("_", " ")[:70],
            summary=f"{key}: {value}"[:250],
            source=SOURCE_MAP.get(source, "system"), pa3_key=pa3_key,
            mtype="fact", layer="L3_identity",
            confidence=float(confidence or 0.7), importance=0.75, utility=0.7,
            novelty=0.3, emotional_intensity=0.0, created_at=norm_ts(created),
            entities=[], topics=[key.split(":")[0].split("_")[0]],
            keywords=[key], dry_run=args.dry_run,
        )
        stats["facts"] += 1
        if stats["facts"] % 25 == 0:
            print(f"  facts: {stats['facts']}/{len(rows)}")

    # --- 2. curated node kinds ---------------------------------------------------------
    kinds = ["fact", "preference", "identity", "directive"]
    query = (
        "SELECT node_id, content, memory_kind, confidence, importance, utility, novelty, "
        "emotional_intensity, title, summary, created_at, entities_json, topics_json, keywords_json "
        "FROM hmg_nodes WHERE status='active' AND memory_kind IN (%s)" % ",".join("?" * len(kinds))
    )
    params = list(kinds)
    if args.include_declarative:
        query += " UNION ALL SELECT node_id, content, memory_kind, confidence, importance, " \
                 "utility, novelty, emotional_intensity, title, summary, created_at, " \
                 "entities_json, topics_json, keywords_json FROM hmg_nodes " \
                 "WHERE status='active' AND memory_kind='declarative' AND importance >= 0.7"
    rows = src.execute(query, params).fetchall()
    if args.limit:
        rows = rows[:args.limit]
    import json as _json
    for (nid, content, kind, confidence, importance, utility, novelty, emo,
         title, summary, created, entities_j, topics_j, keywords_j) in rows:
        pa3_key = f"pa3:nodes:{nid}"
        if pa3_key in seen or not (content or "").strip():
            stats["skipped"] += 1
            continue
        def _load(j):
            try:
                out = _json.loads(j) if j else []
                return [str(x) for x in out][:8] if isinstance(out, list) else []
            except (ValueError, TypeError):
                return []
        import_point(
            engine, content=content[:4000], title=(title or content[:70]),
            summary=(summary or content[:200]),
            # hmg_nodes are model-curated/derived records, not literal user authorship.
            # Gold direct statements come from hmg_fact_statements above.
            source="assistant", pa3_key=pa3_key,
            mtype=KIND_MAP.get(kind, "fact"), layer=LAYER_MAP.get(kind, "L1_session"),
            confidence=float(confidence or 0.6), importance=float(importance or 0.5),
            utility=float(utility or 0.5), novelty=float(novelty or 0.4),
            emotional_intensity=float(emo or 0.0), created_at=norm_ts(created),
            entities=_load(entities_j), topics=_load(topics_j), keywords=_load(keywords_j),
            dry_run=args.dry_run,
        )
        stats["nodes"] += 1
        if stats["nodes"] % 50 == 0:
            print(f"  nodes: {stats['nodes']}/{len(rows)}")

    src.close()
    mode = "DRY-RUN " if args.dry_run else ""
    print(f"\n{mode}import done: {stats['facts']} facts, {stats['nodes']} nodes, "
          f"{stats['skipped']} skipped (already imported)")
    if not args.dry_run:
        print("graph now:", engine.graph.stats())
    engine.graph.close()
    engine.client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
