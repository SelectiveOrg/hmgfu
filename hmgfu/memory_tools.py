"""93.Q4 - the three READ-ONLY memory tools, apart from the dispatcher that offers them.

Split out of `toolsys`, which reached its module ceiling, along a seam that was already there: these
touch nothing but the engine, while the registry around them is about naming, permissions, budgets
and loops. It also puts the REACH of a search -- how far it looks, as against how much a turn injects
unasked -- next to the code that decides it (v156). `_recall_record` comes with them because they are
its only callers; `toolsys` imports it back, so no existing name moved.
"""
from __future__ import annotations

import json


def _recall_record(r) -> dict:
    """69.5 provenance: the user's own words are the evidence — a model-written summary is DERIVED and may
    invent details, so a user-authored point exposes its raw content only; other points carry both, labelled."""
    p = r.point
    rec = {"title": p.title, "content": (p.content or "")[:400], "type": p.type, "source": p.source,
           "score": round(r.score, 3), "reason": r.reason, "timestamp": p.timestamp}
    if p.source not in ("user", "user_explicit") and p.summary:
        rec["derived_summary"] = p.summary
    return rec


def memory_search(engine, args: dict) -> str:
    if engine is None:
        return json.dumps({"error": "memory engine not attached"})
    canonical = engine.facts.render_lines() if hasattr(engine, "facts") else []
    q = str(args.get("query") or "").strip()
    if not q:                        # 62.14: an empty query must never reach the embedder
        return json.dumps({"error": "query is required", "canonical_facts": canonical,
                           "guidance": "Answer from canonical_facts; call again with a real query "
                                       "only for something not listed there."})
    # 93.Q4: ask retrieval for as much as THIS call was told to look at. Without the limit,
    # `AgentEngine.retrieve` filled it from `retrieval_limit` -- the per-turn INJECTION budget --
    # so a deliberate search saw exactly as few memories as the automatic pass that had already
    # missed the answer. The live `related_only` runs searched 3/3 and the search returned the
    # venue 0/3 for that reason. The two numbers are different quantities: one is what to put in
    # front of the model unasked on every turn, the other is how far to look once it has decided
    # something is missing.
    limit = int(args.get("limit") or 8)
    try:
        query, retrieved, elapsed_ms = engine.retrieve(q, limit=limit)
    except Exception as exc:         # 62.14: retrieval failure must not blank the answer
        return json.dumps({"error": f"retrieval failed: {exc}", "canonical_facts": canonical,
                           "guidance": "Retrieval is unavailable; canonical_facts are current and "
                                       "authoritative — answer from them."})
    payload = {
        "results": [_recall_record(r) for r in retrieved[:limit] if r.point.type != "skill"],
        "retrieval_ms": round(elapsed_ms, 1),
    }
            # Bench L4: results are memory RECORDS, so the canonical frame travels WITH them
    if canonical:                    # 69.5: a successful search with ZERO points still returns the ledger
        payload["canonical_facts"] = canonical
        payload["guidance"] = (
            "Results are memory RECORDS and may mention outdated values from past "
            "conversations. canonical_facts hold the ONLY current values — any conflicting "
            "value inside results is HISTORICAL; never present it as current.")
    return json.dumps(payload)

def memory_zoom(engine, args: dict) -> str:
    """Hierarchical recall (P5): overview = the Nanite cut; in/out = drill the macro tree."""
    if engine is None:
        return json.dumps({"error": "memory engine not attached"})
    from .hierarchy import children_of, parent_index, root_frontier
    graph = engine.graph
    scope = str(args.get("scope", "overview")).lower()
    limit = max(1, min(int(args.get("limit") or 12), 40))
    mid = str(args.get("macro_id") or "")

    def row(p):
        kids = len(graph.macro_sources.get(p.id, []))
        return {"id": p.id, "title": p.title[:60], "type": p.type,
                "summary": (p.summary or p.content)[:160],
                "children": kids, "zoomable": kids > 0}
    if scope == "overview":
        top = sorted(root_frontier(graph), key=lambda p: -p.density)[:limit]
        return json.dumps({"scope": "overview", "items": [row(p) for p in top],
                           "hint": "call memory_zoom scope='in' with a zoomable id for finer detail"})
    if scope == "in":
        if mid not in graph.points:
            return json.dumps({"error": f"unknown macro_id '{mid}' — use scope='overview' first"})
        kids = sorted(children_of(graph, mid), key=lambda p: -p.density)[:limit]
        return json.dumps({"scope": "in", "macro": row(graph.points[mid]),
                           "items": [row(p) for p in kids]})
    if scope == "out":
        parent = parent_index(graph).get(mid)
        if parent is None or parent not in graph.points:
            return json.dumps({"scope": "out", "items": [],
                               "hint": "already at the top — use scope='overview'"})
        return json.dumps({"scope": "out", "macro": row(graph.points[parent]),
                           "items": [row(p) for p in children_of(graph, parent)[:limit]]})
    return json.dumps({"error": f"unknown scope '{scope}' (overview | in | out)"})

def memory_timeline(engine, args: dict) -> str:
    if engine is None:
        return json.dumps({"error": "memory engine not attached"})
    points = [p for p in engine.graph.points.values() if p.type != "skill"]
    mtype = args.get("type")
    if mtype:
        points = [p for p in points if p.type == mtype]
    before = args.get("before")
    if before:
        points = [p for p in points if p.timestamp < before]
    points.sort(key=lambda p: p.timestamp, reverse=True)
    limit = int(args.get("limit") or 20)
    return json.dumps({"timeline": [
        {"timestamp": p.timestamp, "type": p.type, "title": p.title,
         "summary": p.summary or p.content[:120], "layer": p.layer, "status": p.status}
        for p in points[:limit]
    ]})


# --- result classification (PA3 invariant) ----------------------------------------------
