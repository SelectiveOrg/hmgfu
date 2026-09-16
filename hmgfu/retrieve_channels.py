"""Candidate channels for recall (THEORY §15) — split out of retrieve.py at the 400-line ceiling (74.7).

Each channel proposes candidates on its OWN criterion; `retrieve_memory` merges them and scores the union with the
composite memory_score. Bench-only comparators live in scripts/, never here."""
from __future__ import annotations

from typing import List

from . import config, fu_math, vecindex
from .models import MemoryPoint, QueryPoint
from .store import HMGGraph


def semantic_candidates(q: QueryPoint, points: List[MemoryPoint], limit: int, graph: HMGGraph = None) -> List[MemoryPoint]:
    """Top-`limit` by cosine — one matrix product over the graph's cached rows when numpy is present (76.2), the same
    ranking point by point otherwise."""
    return vecindex.top_k(q.embedding, points, limit, graph=graph)


def entity_candidates(q: QueryPoint, points: List[MemoryPoint], limit: int) -> List[MemoryPoint]:
    hits = [(p, fu_math.jaccard(q.entities, p.entities)) for p in points]
    return [p for p, s in sorted(hits, key=lambda t: -t[1]) if s > 0][:limit]


def goal_candidates(points: List[MemoryPoint], limit: int) -> List[MemoryPoint]:
    goals = [p for p in points if p.type in ("goal", "project", "task")]
    return sorted(goals, key=lambda p: -(p.density + p.utility))[:limit]


def recent_candidates(points: List[MemoryPoint], limit: int) -> List[MemoryPoint]:
    return sorted(points, key=lambda p: p.timestamp, reverse=True)[:limit]


def dense_candidates(points: List[MemoryPoint], limit: int) -> List[MemoryPoint]:
    dense = [p for p in points if p.density >= config.DENSE_IDENTITY_MIN or p.layer in
             ("L3_identity", "L4_world_model", "L5_deep_pattern")]
    return sorted(dense, key=lambda p: -p.density)[:limit]


def wormhole_candidates(q: QueryPoint, graph: HMGGraph, seeds: List[MemoryPoint],
                         limit: int) -> List[MemoryPoint]:
    """Points reachable from semantic seeds through a wormhole edge."""
    out = []
    for seed in seeds[:20]:
        for other, edge in graph.neighbours_of(seed.id):
            if edge.relation_type == "wormhole" and other.status == "active":
                out.append(other)
                if len(out) >= limit:
                    return out
    return out
