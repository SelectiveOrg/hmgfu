"""Hex grid math on cube coordinates (THEORY Part A: H; §13 placement; issue 13 spiral search).

Cube coordinates satisfy q + r + s == 0. One memory point per cell (a cell is the point's
address; semantic zones emerge from neighbourhood).
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Tuple

from .models import Hex

# The six cube-coordinate direction vectors, in ring-walk order.
DIRECTIONS = [(1, 0, -1), (1, -1, 0), (0, -1, 1), (-1, 0, 1), (-1, 1, 0), (0, 1, -1)]


def hex_distance(a: Hex, b: Hex) -> int:
    return max(abs(a.q - b.q), abs(a.r - b.r), abs(a.s - b.s))


def neighbours(h: Hex) -> List[Hex]:
    return [Hex(h.q + dq, h.r + dr, h.s + ds) for dq, dr, ds in DIRECTIONS]


def ring(center: Hex, radius: int) -> List[Hex]:
    """All cells at exactly `radius` from center (radius >= 1)."""
    if radius <= 0:
        return [Hex(center.q, center.r, center.s)]
    results = []
    # start at direction 4 scaled by radius (conventional ring walk)
    dq, dr, ds = DIRECTIONS[4]
    h = Hex(center.q + dq * radius, center.r + dr * radius, center.s + ds * radius)
    for side in range(6):
        for _ in range(radius):
            results.append(Hex(h.q, h.r, h.s))
            dq, dr, ds = DIRECTIONS[side]
            h = Hex(h.q + dq, h.r + dr, h.s + ds)
    return results


def spiral(center: Hex, max_radius: int) -> Iterable[Hex]:
    """Center, then rings of increasing radius — deterministic free-cell search order."""
    yield Hex(center.q, center.r, center.s)
    for radius in range(1, max_radius + 1):
        for h in ring(center, radius):
            yield h


def round_cube(qf: float, rf: float, sf: float) -> Hex:
    """Round fractional cube coords to the nearest valid cell."""
    q, r, s = round(qf), round(rf), round(sf)
    dq, dr, ds = abs(q - qf), abs(r - rf), abs(s - sf)
    if dq > dr and dq > ds:
        q = -r - s
    elif dr > ds:
        r = -q - s
    else:
        s = -q - r
    return Hex(int(q), int(r), int(s))


def weighted_centroid(items: List[Tuple[Hex, float]]) -> Hex:
    """Weighted average of hex positions (THEORY §13: weight = cos_sim * density)."""
    total = sum(w for _, w in items)
    if total <= 0:
        return Hex(0, 0, 0)
    qf = sum(h.q * w for h, w in items) / total
    rf = sum(h.r * w for h, w in items) / total
    sf = sum(h.s * w for h, w in items) / total
    return round_cube(qf, rf, sf)


def nearest_free_hex(target: Hex, occupied: Dict[str, str], max_radius: int = 64) -> Hex:
    """First free cell in spiral order around target (THEORY issue 13)."""
    for h in spiral(target, max_radius):
        if h.key() not in occupied:
            return h
    raise RuntimeError(f"no free hex within radius {max_radius} of {target.key()}")
