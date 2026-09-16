"""Vector scan (Phase 76.2) — the one hot loop at scale. Profile at 100k points (bench_scale, dim 1024): the pure-Python
cosine over all active points was 11.2 of 12.7 s per query; edges and channels were noise beside it. This module gives
`scores` / `top_k` / `best` with the SAME ranking as `fu_math.cosine` applied point by point — ties broken by input
order exactly as Python's stable `sorted` does (the sealed corpus has identical filler lines, hence exact ties at the
top-k boundary; an unstable partition flipped two questions in the first equivalence run) — computed as one float32
matrix product when numpy is present. numpy is OPTIONAL (README: install it for graphs past ~2k points); without it the
pure-Python path runs unchanged. Float32 rounding (~1e-7) can still reorder two DISTINCT embeddings that are closer than
that; documented, measured, not hidden.

Maintenance is INCREMENTAL: `HMGGraph` records every written/deleted point id in `graph.dirty` and bumps `graph.version`;
the index consumes the dirty set (append / overwrite rows) instead of rebuilding — a full rebuild only when the index does
not exist or more than a quarter of the rows changed. `HMGFU_VECTOR_INDEX=0` forces the pure path — a documented A/B switch."""
from __future__ import annotations

import os
import weakref
from typing import Dict, List, Optional, Sequence, Tuple

from . import fu_math

try:                                  # optional dependency
    import numpy as _np
except Exception:                     # pragma: no cover — the fallback test monkeypatches this
    _np = None

ENABLED = os.environ.get("HMGFU_VECTOR_INDEX", "1").strip() not in ("0", "false", "no")
REBUILD_FRACTION = 0.25


def available() -> bool:
    return ENABLED and _np is not None


def _unit_rows(points: Sequence, dim: int):
    mat = _np.zeros((len(points), dim), dtype=_np.float32)
    for i, p in enumerate(points):
        e = p.embedding
        if e and len(e) == dim:
            mat[i] = e
    norms = _np.linalg.norm(mat, axis=1)
    norms[norms == 0.0] = 1.0
    return mat / norms[:, None]


class _Index:
    """Unit-normalised rows for the active points of one graph, kept in step with the graph incrementally."""
    __slots__ = ("version", "row_of", "mat", "n", "dim")

    def __init__(self, graph) -> None:
        pts = graph.active_points()
        self.dim = next((len(p.embedding) for p in pts if p.embedding), 1)
        self.n = len(pts)
        cap = max(64, int(self.n * 1.5))
        self.mat = _np.zeros((cap, self.dim), dtype=_np.float32)
        if pts:
            self.mat[:self.n] = _unit_rows(pts, self.dim)
        self.row_of: Dict[str, int] = {p.id: i for i, p in enumerate(pts)}
        self.version = graph.version
        graph.dirty.clear()

    def apply_dirty(self, graph) -> None:
        """Bring the index to the graph's version using only the ids the graph marked dirty."""
        dirty = set(graph.dirty)
        for pid in dirty:
            p = graph.points.get(pid)
            active = p is not None and p.status == "active" and p.embedding and len(p.embedding) == self.dim
            row = self.row_of.get(pid)
            if active:
                if row is None:
                    if self.n >= self.mat.shape[0]:
                        grown = _np.zeros((self.mat.shape[0] * 2, self.dim), dtype=_np.float32)
                        grown[:self.n] = self.mat[:self.n]
                        self.mat = grown
                    row = self.n
                    self.row_of[pid] = row
                    self.n += 1
                self.mat[row] = _unit_rows([p], self.dim)[0]
            elif row is not None:
                self.mat[row] = 0.0                      # a deleted / non-active point scores 0 and leaves the map
                del self.row_of[pid]
        self.version = graph.version
        graph.dirty.clear()


# 91.AA: keyed by id() for speed, but an id is REUSED after its object is collected, so the entry
# carries a weak reference back to the graph it was built for. A dead or mismatched referent is a
# miss, never a stale index served to a different graph.
_CACHE: Dict[int, tuple] = {}


def _index(graph) -> Optional[_Index]:
    if graph is None or not hasattr(graph, "version") or not hasattr(graph, "dirty") or not hasattr(graph, "active_points"):
        return None
    ref, idx = _CACHE.get(id(graph), (None, None))
    if ref is not None and ref() is not graph:       # 91.AA: an id reused by a different graph
        idx = None
    if idx is None or (idx.version != graph.version and len(graph.dirty) > REBUILD_FRACTION * max(1, idx.n)):
        idx = _Index(graph)
        try:
            _CACHE[id(graph)] = (weakref.ref(graph), idx)
        except TypeError:                            # a graph that cannot be weak-referenced is not cached
            return idx
    elif idx.version != graph.version:
        idx.apply_dirty(graph)
    return idx


def _unit_query(query_embedding: List[float]):
    q = _np.asarray(query_embedding, dtype=_np.float32)
    n = float(_np.linalg.norm(q)) or 1.0
    return q / n


def scores(query_embedding: List[float], points: Sequence, graph=None) -> List[float]:
    """cosine(query, p) for every p in `points`, in `points` order — the values fu_math.cosine gives (float32 arithmetic)."""
    if not available() or not points or not query_embedding:
        return [fu_math.cosine(query_embedding, p.embedding) for p in points]
    q = _unit_query(query_embedding)
    idx = _index(graph)
    if idx is not None and idx.dim == len(query_embedding) and all(p.id in idx.row_of for p in points):
        allscores = (idx.mat[:idx.n] @ q).tolist()        # one product over every row (no 400 MB fancy-index copy at 100k),
        row_of = idx.row_of
        return [allscores[row_of[p.id]] for p in points]  # then gathered in the caller's order — never the matrix order
    return (_unit_rows(points, len(query_embedding)) @ q).tolist()       # points outside the graph (or no graph): one-off


def top_k(query_embedding: List[float], points: Sequence, k: int, graph=None) -> List:
    """The k points with the highest cosine to the query, best first; ties keep input order (as `sorted` does)."""
    if not points or k <= 0:
        return []
    if not available() or not query_embedding:
        return sorted(points, key=lambda p: -fu_math.cosine(query_embedding, p.embedding))[:k]
    s = _np.asarray(scores(query_embedding, points, graph))
    order = _np.argsort(-s, kind="stable")[:k]          # stable: exact ties resolve by input order, like Python's sorted
    return [points[i] for i in order.tolist()]


def best(query_embedding: List[float], points: Sequence, graph=None) -> Tuple[Optional[object], float]:
    """(point, cosine) of the single nearest point — what the ingest duplicate check needs (first of a tie, like a scan)."""
    if not points:
        return None, 0.0
    s = scores(query_embedding, points, graph)
    i = max(range(len(points)), key=lambda j: (s[j], -j))
    return points[i], s[i]


def clear_cache() -> None:
    _CACHE.clear()
