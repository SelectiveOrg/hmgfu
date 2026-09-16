"""Memory surface for the frontend: search, timeline, and the viz-shaped graph."""

from __future__ import annotations

import anyio
from fastapi import APIRouter, HTTPException

from ..runtime import get_engine

router = APIRouter()


@router.get("/api/memory/search")
async def memory_search(q: str, limit: int = 12):
    engine = get_engine()
    if not q.strip():
        raise HTTPException(400, "empty query")
    def run():
        query, retrieved, elapsed_ms = engine.retrieve(q)
        return {
            "results": [r.public() for r in retrieved[:limit]],
            "retrieval_ms": round(elapsed_ms, 1),
        }
    return await anyio.to_thread.run_sync(run)


@router.get("/api/memory/timeline")
async def memory_timeline(limit: int = 50, type: str | None = None,
                          before: str | None = None, include_skills: bool = False):
    engine = get_engine()
    points = [p for p in engine.graph.points.values()
              if include_skills or p.type != "skill"]
    if type:
        points = [p for p in points if p.type == type]
    if before:
        points = [p for p in points if p.timestamp < before]
    points.sort(key=lambda p: p.timestamp, reverse=True)
    from ..taxonomy import category_of, node_class
    return {"timeline": [{**p.public(), "nodeClass": node_class(p), "category": category_of(p)}
                         for p in points[:min(limit, 200)]],
            "total": len(points)}


def _biome(valence: float) -> str:
    return "A" if valence > 0.15 else ("B" if valence < -0.15 else "C")


# --- THEORY v3 (The Governed Hexagon): typed-port schema for the hex UI (viz-only; additive) ------
# Maps the 8 stored FuEdge.relation types onto v3's six side-ports + one center wormhole-port
# (THEORY_V3 B.2). Ports NEVER affect ranking (v3 A1/A2) — this is routing/state geometry only.
_V3_PORT = {   # buckets the 16 config.OMEGA relation types (verified) → v3's 6 sides + center
    "same_entity": (1, "factual"), "part_of": (1, "factual"),
    "temporal": (2, "temporal"),
    "contradiction": (3, "contradictory"),
    "evidence_for": (4, "positive"), "goal_related": (4, "positive"), "project_related": (4, "positive"),
    "evidence_against": (5, "negative"),
    "semantic_similarity": (6, "context"), "memory_of": (6, "context"), "analogy": (6, "context"),
    "emotional": (6, "context"), "causal": (6, "context"), "depends_on": (6, "context"),
    "skill_required": (6, "context"),
    "wormhole": ("center", "wormhole"),
}
# Provisional lifecycle mapping from the CURRENT status field. Real TEMP/CANDIDATE states arrive
# with the Regulator (Phase 61a, gated on E.3); until then we surface the closest existing meaning.
_V3_LIFECYCLE = {"active": "FACT", "superseded": "SUPERSEDED", "dormant": "EVAPORATED"}


def _v3_port(relation_type: str):
    return _V3_PORT.get(relation_type, (6, "context"))


def _successor(graph, pid: str):
    """The surviving fact that replaced a superseded one — REUSE the existing contradiction edge
    (Rule 5, no new store): mark_tension records a `contradiction` FuEdge between loser (superseded)
    and the active user_explicit winner. Return {id,label} of that winner, or None (a direct
    correction signal with no ingested successor is a real case too — the link is simply absent)."""
    for e in graph.edges.values():
        if e.relation_type != "contradiction" or e.status != "active":
            continue
        other = e.to_id if e.from_id == pid else (e.from_id if e.to_id == pid else None)
        w = graph.points.get(other) if other else None
        if w is not None and w.status == "active":
            return {"id": w.id, "label": (w.title or w.summary or w.content or "")[:26]}
    return None


def _reg_fields(engine, pid: str) -> dict:
    """REAL lifecycle from the Regulator ledger (no new storage — the lc:<pid>:* LearnedParams keys),
    ONLY when the Regulator is live; else {} so the viz falls back to the provisional status-derived
    `lifecycle`. The viz draws what the system DOES: `state` = the true TEMP/CANDIDATE/FACT/SUPERSEDED,
    `c` = confidence, `ledger` = the recorded signal counts the internal-hexes render (each = an event),
    `superseded_by` = the successor fact (B2, only for SUPERSEDED, from the real contradiction edge)."""
    from .. import config
    if not config.REGULATOR_ENABLED:
        return {}
    from ..regulator import confidence, state
    led = engine.regulator.ledger(pid)
    out = {"c": round(confidence(led), 3), "state": state(led), "ledger": led}
    if out["state"] == "superseded":
        succ = _successor(engine.graph, pid)
        if succ:
            out["superseded_by"] = succ
    return out


@router.post("/api/memory/hygiene")
async def memory_hygiene():
    """Retroactive hygiene pass (dedup, assistant-fact reclassification, junk/stale demotion,
    ephemeral tagging) — also runs inside every full dream loop."""
    from ..hygiene import hygiene_pass
    engine = get_engine()
    report = await anyio.to_thread.run_sync(lambda: hygiene_pass(engine))
    return {"report": report, "stats": engine.graph.stats()}


@router.get("/api/graph/viz")
async def graph_viz(cap: int = 220, root: str | None = None, frontier: int = 0,
                    roots: int = 0):
    """Graph mapped to the design system's HmgGraph / HmgHexGrid props.
    P5 zoom modes: `root=<macro_id>` → ONLY that macro's children on a FRESH local spiral
    (one clean honeycomb per level — drill-down); `frontier=1` → the coarse Nanite cut."""
    from .. import hexgrid
    from ..hierarchy import children_of, macro_levels, parent_index, root_frontier, select_cut
    from ..taxonomy import category_of, node_class
    from ..models import Hex
    engine = get_engine()
    g = engine.graph
    cap = max(1, min(cap, 500))
    coord_override, crumb = {}, []
    parents = parent_index(g)
    if root:
        if root not in g.points or g.points[root].type != "macro":
            raise HTTPException(404, "macro not found")
        points = sorted(children_of(g, root), key=lambda p: -p.density)[:cap]
        # fresh local honeycomb per level (G6 without a schema change)
        for p, cell in zip(points, hexgrid.spiral(Hex(0, 0, 0), 64)):
            coord_override[p.id] = (cell.q, cell.r)
        node = root
        while node:                                   # breadcrumb root→…→here
            mp = g.points.get(node)
            crumb.insert(0, {"id": node, "label": (mp.title if mp else node)[:32]})
            node = parents.get(node)
        ranked = points
    elif roots:
        coarse = [p for p in root_frontier(g) if p.type == "macro"]
        if not coarse:
            coarse = [p for p in root_frontier(g) if p.type != "skill"]
        points = sorted(coarse, key=lambda p: -(p.density + p.energy))[:cap]
        ranked = points
    elif frontier:
        points = sorted(select_cut(g, max_items=cap), key=lambda p: -p.density)
        ranked = points
    else:
        ranked = sorted((p for p in g.points.values() if p.status == "active"),
                        key=lambda p: -(p.density + p.energy))
        points = ranked[:cap]
    included_macros = [p for p in points if p.type == "macro"]
    macro_ids = {p.id for p in included_macros}
    source_ids = ({pid for mid in macro_ids for pid in g.macro_sources.get(mid, [])}
                  if not (root or frontier or roots) else set())
    if source_ids:  # preserve complete Λ-compression clusters inside the existing cap
        pinned = macro_ids | source_ids
        points = (included_macros
                  + [p for p in ranked if p.id in source_ids]
                  + [p for p in ranked if p.id not in pinned])[:cap]
    ids = {p.id for p in points}
    # B2 — surface a SUPERSEDED fact when a VISIBLE fact replaced it (REUSE the contradiction edge,
    # Rule 5): the active-only cut hides losers, so the viz would otherwise pretend the old fact
    # vanished. Bounded — only losers whose winner is already in view; drawn faded (HZ_STATE_FADE)
    # with the successor link (_reg_fields.superseded_by), so the real replace history is honest.
    for e in list(g.edges.values()):
        if e.relation_type != "contradiction" or e.status != "active":
            continue
        for win_id, lose_id in ((e.from_id, e.to_id), (e.to_id, e.from_id)):
            lose = g.points.get(lose_id)
            if win_id in ids and lose_id not in ids and lose is not None and lose.status == "superseded":
                points.append(lose)
                ids.add(lose_id)
    macro_cluster = {}   # point_id -> (cluster_index, macro_title)
    for idx, (macro_id, sources) in enumerate(g.macro_sources.items()):
        macro = g.points.get(macro_id)
        for pid in sources:
            macro_cluster[pid] = (idx + 1, macro.title[:24] if macro else "macro")
    levels = macro_levels(g)
    hex_nodes, graph_nodes = [], []
    for p in points:
        cluster, macro_label = macro_cluster.get(p.id, (None, None))
        is_macro = p.type == "macro"
        hex_nodes.append({
            "id": p.id, "q": p.hex.q, "r": p.hex.r,
            "type": "macro" if is_macro else "micro",
            "label": (p.title or p.summary or "")[:26],
            "cluster": (list(g.macro_sources).index(p.id) + 1) if is_macro and p.id in g.macro_sources else cluster,
            "macroLabel": (p.title[:24] if is_macro else macro_label),
            "energy": round(max(p.energy, p.density * 0.7), 3),
            "biome": _biome(p.emotional_valence),
            # debug-view fields (Phase 31: live hex field widget = the v1 debug view, in-canvas)
            "layer": p.layer, "kind": p.type, "status": p.status, "source": p.source,
            "lifecycle": _V3_LIFECYCLE.get(p.status, "FACT"),   # v3 lifecycle (provisional; see _V3_LIFECYCLE)
            **_reg_fields(engine, p.id),   # REAL lifecycle state + c + ledger from the Regulator (when live)
            "density": round(p.density, 3), "stability": round(p.stability, 3),
            "summary": (p.summary or p.content)[:180],
            "entities": p.entities[:6], "topics": p.topics[:4], "access": p.access_count,
            "parent": parents.get(p.id), "level": levels.get(p.id, 0),
            "children": len(children_of(g, p.id)) if is_macro else 0,
            # ontology facets (Phase 43, additive — the viz can color by class/category)
            "nodeClass": node_class(p), "category": category_of(p),
        })
        if p.id in coord_override:
            hex_nodes[-1]["q"], hex_nodes[-1]["r"] = coord_override[p.id]
        graph_nodes.append({
            "id": p.id, "type": "macro" if is_macro else "micro",
            "biome": _biome(p.emotional_valence),
            "label": (p.title or "")[:26],
            "energy": round(max(0.15, p.density), 3),
            "valence": round(p.emotional_valence, 2),
            "nodeClass": node_class(p), "category": category_of(p),
        })
    edges = []
    for e in g.edges.values():
        if e.status == "active" and e.from_id in ids and e.to_id in ids and e.kappa >= 0.3:
            _port, _ptype = _v3_port(e.relation_type)
            edges.append({"src": e.from_id, "dst": e.to_id,
                          "type": "Wormhole" if e.relation_type == "wormhole" else "Turn_Response",
                          "kappa": round(e.kappa, 3), "tension": round(e.tension, 3),
                          "relation": e.relation_type,
                          "port": _port, "portType": _ptype})   # v3 typed-port (viz-only, additive)
        if len(edges) >= 600:
            break
    classes = {}
    for p in g.active_points():
        c = node_class(p); classes[c] = classes.get(c, 0) + 1
    return {"hex_nodes": hex_nodes, "graph_nodes": graph_nodes, "edges": edges,
            "classes": classes,
            "root": root, "path": crumb, "stats": g.stats()}
