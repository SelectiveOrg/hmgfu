"""Energy propagation Φ (THEORY §14 + issue 3: per-hop factor clamped, no amplification)."""

from __future__ import annotations

from collections import deque

from . import config, fu_math
from .models import MemoryPoint, now_iso
from .store import HMGGraph


def propagate_energy(origin: MemoryPoint, graph: HMGGraph,
                     max_depth: int = config.PROPAGATION_MAX_DEPTH) -> int:
    """BFS energy spread from an activated point. Returns number of points touched."""
    queue = deque([(origin.id, origin.energy, 0)])
    visited = set()
    touched = 0
    while queue:
        point_id, energy, depth = queue.popleft()
        if point_id in visited or depth > max_depth:
            continue
        visited.add(point_id)
        point = graph.points.get(point_id)
        if point is None or point.status != "active":
            continue
        if point_id != origin.id:
            point.energy = fu_math.clamp(point.energy + energy)
            point.last_accessed_at = now_iso()
            graph.save_point(point)
            touched += 1
        for other, edge in graph.neighbours_of(point_id):
            next_energy = energy * fu_math.propagation_factor(edge)
            if next_energy < config.PROPAGATION_FLOOR:
                continue
            queue.append((other.id, next_energy, depth + 1))
    return touched
