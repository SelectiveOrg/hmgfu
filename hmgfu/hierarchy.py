"""Memory hierarchy — the Nanite-style LOD tree over macros (ANALYSIS Parts 2–3, G1–G4).

Everything here is DERIVED from the persisted `macro_sources` containment map + embeddings —
no schema change, no new columns (Rule 11). Levels: micro = 0; a macro = 1 + max(child level).

- build_super_macros: recursive consolidation (macros of macros) up to HIERARCHY_MAX_LEVEL —
  Nanite's "group → simplify → re-split, recursively".
- coverage_error: how much gist is lost by showing the macro instead of its children
  (1 − mean cosine(child, macro)) — Nanite's per-cluster error metric.
- root_frontier / select_cut: the coarse top of the tree, and the view-budgeted frontier
  (expand the worst-covered macro until the budget is spent) — Nanite's cut selection.
"""

from __future__ import annotations

import logging
from typing import Callable, Dict, List

from . import config, fu_math
from .models import FuEdge, MemoryPoint
from .store import HMGGraph

log = logging.getLogger("hmgfu.hierarchy")


def children_of(graph: HMGGraph, macro_id: str) -> List[MemoryPoint]:
    """A macro's direct children (active only), from the persisted containment map."""
    return [graph.points[pid] for pid in graph.macro_sources.get(macro_id, [])
            if pid in graph.points and graph.points[pid].status == "active"]


def parent_index(graph: HMGGraph) -> Dict[str, str]:
    """child id → containing ACTIVE macro id (first wins if a node is in several clusters).

    94.6b: status matters. A superseded macro covers nothing -- `root_frontier` hides any point that
    has a parent, so counting a retired digest as a parent would hide the detail it summarised the
    moment a correction demoted it, removing the summary AND the evidence under it. `children_of`
    already filters the other direction for the same reason.
    """
    parents: Dict[str, str] = {}
    for macro_id, sources in graph.macro_sources.items():
        macro = graph.points.get(macro_id)
        if macro is None or macro.status != "active":
            continue
        for pid in sources:
            parents.setdefault(pid, macro_id)
    return parents


def macro_levels(graph: HMGGraph) -> Dict[str, int]:
    """Level of every macro: 1 + max(child level); micros are 0. Cycle-safe memo."""
    levels: Dict[str, int] = {}

    def level(pid: str, seen: frozenset) -> int:
        p = graph.points.get(pid)
        if p is None or p.type != "macro":
            return 0
        if pid in levels:
            return levels[pid]
        if pid in seen:            # containment cycle guard — treat as leaf macro
            return 1
        kids = graph.macro_sources.get(pid, [])
        lv = 1 + max((level(k, seen | {pid}) for k in kids), default=0)
        levels[pid] = lv
        return lv

    for p in graph.points.values():
        if p.type == "macro" and p.status == "active":
            level(p.id, frozenset())
    return levels


def coverage_error(graph: HMGGraph, macro: MemoryPoint) -> float:
    """1 − mean cosine(child, macro): how much detail is LOST by showing the macro alone.
    High error → the cut should descend into this macro's children."""
    kids = [k for k in children_of(graph, macro.id) if k.embedding]
    if not kids or not macro.embedding:
        return 0.0
    sims = [fu_math.cosine(k.embedding, macro.embedding) for k in kids]
    return fu_math.clamp(1.0 - sum(sims) / len(sims))


def root_frontier(graph: HMGGraph) -> List[MemoryPoint]:
    """The coarse top of the tree: parentless active macros + active points covered by no macro."""
    parents = parent_index(graph)
    out = []
    for p in graph.active_points():
        if p.type == "skill":
            continue
        if p.type == "macro":
            if p.id not in parents:
                out.append(p)
        elif p.id not in parents:
            out.append(p)
    return out


def select_cut(graph: HMGGraph, max_items: int = 24) -> List[MemoryPoint]:
    """View-budgeted frontier (the Nanite cut): start coarse, repeatedly expand the macro whose
    coverage_error is highest, until the budget is reached or nothing expandable remains."""
    cut = sorted(root_frontier(graph), key=lambda p: -p.density)[:max_items]
    while len(cut) < max_items:
        expandable = [(coverage_error(graph, p), p) for p in cut
                      if p.type == "macro" and graph.macro_sources.get(p.id)]
        expandable = [(e, p) for e, p in expandable if e > 0]
        if not expandable:
            break
        _, worst = max(expandable, key=lambda t: t[0])
        kids = children_of(graph, worst.id)
        if not kids or len(cut) - 1 + len(kids) > max_items:
            break
        cut.remove(worst)
        cut.extend(kids)
    return cut


def _greedy_clusters(macros: List[MemoryPoint], min_cos: float, min_size: int) -> List[List[MemoryPoint]]:
    """Greedy embedding clustering: each macro joins the first cluster whose seed it matches."""
    clusters: List[List[MemoryPoint]] = []
    for m in sorted(macros, key=lambda p: -p.density):
        if not m.embedding:
            continue
        placed = False
        for cluster in clusters:
            if fu_math.cosine(m.embedding, cluster[0].embedding) >= min_cos:
                cluster.append(m)
                placed = True
                break
        if not placed:
            clusters.append([m])
    return [c for c in clusters if len(c) >= min_size]


def build_super_macros(graph: HMGGraph, sensitizer, embed: Callable) -> List[str]:
    """Recursive consolidation (G1): cluster same-level PARENTLESS macros into a super-macro,
    level by level, up to HIERARCHY_MAX_LEVEL. Returns created macro ids."""
    from .ingest import assign_hex
    created: List[str] = []
    for _lvl in range(1, config.HIERARCHY_MAX_LEVEL):
        levels = macro_levels(graph)
        parents = parent_index(graph)
        layer = [p for p in graph.active_points()
                 if p.type == "macro" and levels.get(p.id) == _lvl and p.id not in parents]
        clusters = _greedy_clusters(layer, config.SUPER_MACRO_MIN_COSINE,
                                    config.SUPER_MACRO_MIN_CLUSTER)
        if not clusters:
            break
        for members in clusters:
            summary = sensitizer.summarise_cluster(members)
            if not summary:
                continue
            super_macro = MemoryPoint(
                type="macro",
                title=f"Macro L{_lvl + 1}: {members[0].title.replace('Macro:', '').strip()[:40]}",
                content=summary, summary=summary, source="dream",
                embedding=embed(summary) if summary else list(members[0].embedding),
                entities=sorted({e for m in members for e in m.entities})[:10],
                topics=sorted({t for m in members for t in m.topics})[:6],
                importance=max(m.importance for m in members),
                utility=max(m.utility for m in members),
                confidence=sum(m.confidence for m in members) / len(members),
                density=fu_math.clamp(sum(m.density for m in members) / len(members) + 0.1),
                energy=0.5, layer=fu_math.next_layer(members[0].layer),
                timestamp=max(m.timestamp for m in members),   # 74.8: content's recency, not the dream's
            )
            super_macro.hex = assign_hex(super_macro, graph)
            super_macro.stability = fu_math.compute_stability(super_macro)
            graph.save_point(super_macro)
            graph.save_macro_sources(super_macro.id, sorted(m.id for m in members))
            for m in members:
                graph.save_edge(FuEdge(
                    from_id=m.id, to_id=super_macro.id, relation_type="part_of",
                    direction="two_way", kappa=0.6, omega=fu_math.compute_omega("part_of"),
                    distance=1.0, base_separation=1.0, resonance=0.6, tension=0.0, trust=0.7,
                ))
            created.append(super_macro.id)
            log.info("super-macro L%d %s over %d macros", _lvl + 1, super_macro.id, len(members))
    return created
