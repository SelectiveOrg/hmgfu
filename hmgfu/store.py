"""SQLite persistence + in-memory HMGGraph (THEORY §27 MVP tables + issue 6 macro unification).

The graph is the working set: all points/edges loaded at startup, mutations write through to
SQLite in the same call. Prototype scale (thousands of points) — no pagination needed.
"""

from __future__ import annotations

import sqlite3
import threading
from typing import Dict, List, Optional

from . import config
from .db import connect as db_connect
from .models import DreamReport, FuEdge, Hex, MemoryPoint

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memory_points (
    id TEXT PRIMARY KEY, type TEXT, title TEXT, content TEXT, summary TEXT, source TEXT,
    timestamp TEXT, last_accessed_at TEXT, access_count INTEGER,
    embedding TEXT, keywords TEXT, entities TEXT, topics TEXT,
    emotional_valence REAL, emotional_intensity REAL, importance REAL,
    confidence REAL, novelty REAL, utility REAL, density REAL, energy REAL,
    stability REAL, hex_q INTEGER, hex_r INTEGER, hex_s INTEGER, layer TEXT,
    status TEXT, extractor TEXT
);
CREATE TABLE IF NOT EXISTS fu_edges (
    id TEXT PRIMARY KEY, from_point_id TEXT, to_point_id TEXT, relation_type TEXT,
    direction TEXT, kappa REAL, omega REAL, distance REAL, base_separation REAL,
    resonance REAL, tension REAL, trust REAL, created_at TEXT, last_activated_at TEXT,
    activation_count INTEGER, status TEXT
);
CREATE TABLE IF NOT EXISTS macro_sources (
    macro_id TEXT, point_id TEXT, PRIMARY KEY (macro_id, point_id)
);
CREATE TABLE IF NOT EXISTS dream_reports (
    id TEXT PRIMARY KEY, summary TEXT, macros_created TEXT, wormholes_created TEXT,
    contradictions_found TEXT, memories_decayed TEXT, memories_promoted TEXT,
    insights TEXT, created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_edges_from ON fu_edges(from_point_id);
CREATE INDEX IF NOT EXISTS idx_edges_to ON fu_edges(to_point_id);
"""


class HMGGraph:
    """In-memory relational field with write-through SQLite persistence."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or config.DB_PATH
        self._lock = threading.RLock()
        self._db = db_connect(self.db_path)
        self._db.executescript(_SCHEMA)
        self._db.commit()
        self.points: Dict[str, MemoryPoint] = {}
        self.edges: Dict[str, FuEdge] = {}
        self._adjacency: Dict[str, List[str]] = {}   # point_id -> [edge_id]
        self.occupied: Dict[str, str] = {}           # hex key -> point_id
        self._hex_of: Dict[str, str] = {}            # point_id -> last-persisted hex key (M-03)
        self.macro_sources: Dict[str, List[str]] = {}
        self.version = 0                              # 76.2: bumped on every point write/delete — the vector index's key
        self.dirty: set = set()                       # 76.2: ids written/deleted since the vector index last synced
        self._load()

    # --- loading ---------------------------------------------------------------

    def _load(self) -> None:
        with self._lock:
            for row in self._db.execute("SELECT * FROM memory_points"):
                p = MemoryPoint.from_row(row)
                self.points[p.id] = p
                self.occupied[p.hex.key()] = p.id
                self._hex_of[p.id] = p.hex.key()
            for row in self._db.execute("SELECT * FROM fu_edges"):
                e = FuEdge.from_row(row)
                self.edges[e.id] = e
                self._index_edge(e)
            for macro_id, point_id in self._db.execute("SELECT macro_id, point_id FROM macro_sources"):
                self.macro_sources.setdefault(macro_id, []).append(point_id)

    def _index_edge(self, e: FuEdge) -> None:
        self._adjacency.setdefault(e.from_id, []).append(e.id)
        self._adjacency.setdefault(e.to_id, []).append(e.id)

    # --- persistence -----------------------------------------------------------

    def save_point(self, p: MemoryPoint) -> None:
        with self._lock:
            # M-03: callers mutate the SAME object we hold, so comparing existing.hex to p.hex
            # is always equal and never freed the old cell. Track the last-PERSISTED key instead.
            old_key = self._hex_of.get(p.id)
            new_key = p.hex.key()
            if old_key is not None and old_key != new_key and self.occupied.get(old_key) == p.id:
                self.occupied.pop(old_key, None)
            self.points[p.id] = p
            self.occupied[new_key] = p.id
            self._hex_of[p.id] = new_key
            self.version += 1
            self.dirty.add(p.id)
            self._db.execute(
                "INSERT OR REPLACE INTO memory_points VALUES (" + ",".join("?" * 28) + ")",
                p.to_row(),
            )
            self._db.commit()

    def save_edge(self, e: FuEdge) -> None:
        with self._lock:
            if e.id not in self.edges:
                self._index_edge(e)
            self.edges[e.id] = e
            self._db.execute(
                "INSERT OR REPLACE INTO fu_edges VALUES (" + ",".join("?" * 16) + ")",
                e.to_row(),
            )
            self._db.commit()

    def delete_point(self, point_id: str) -> bool:
        """Hard-remove a point and everything that references it: its edges (table, in-memory map,
        and BOTH endpoints' adjacency), its hex cell, and any macro-source rows. Returns True if the
        point existed. Prototype scale (O(edges of the point)); used to prune projections such as a
        cleared directive node (decay only dormant-flags, so a hard delete is the only clean removal)."""
        with self._lock:
            self.version += 1
            self.dirty.add(point_id)
            p = self.points.pop(point_id, None)
            if p is None:
                return False
            for eid in list(self._adjacency.get(point_id, [])):
                e = self.edges.pop(eid, None)
                if e is not None:
                    other = e.to_id if e.from_id == point_id else e.from_id
                    if other in self._adjacency:
                        self._adjacency[other] = [x for x in self._adjacency[other] if x != eid]
                self._db.execute("DELETE FROM fu_edges WHERE id=?", (eid,))
            self._adjacency.pop(point_id, None)
            key = self._hex_of.pop(point_id, None) or p.hex.key()
            if self.occupied.get(key) == point_id:
                self.occupied.pop(key, None)
            self.macro_sources.pop(point_id, None)
            for mid in list(self.macro_sources):
                if point_id in self.macro_sources[mid]:
                    self.macro_sources[mid] = [x for x in self.macro_sources[mid] if x != point_id]
            self._db.execute("DELETE FROM macro_sources WHERE macro_id=? OR point_id=?",
                             (point_id, point_id))
            self._db.execute("DELETE FROM memory_points WHERE id=?", (point_id,))
            self._db.commit()
            return True

    def save_macro_sources(self, macro_id: str, point_ids: List[str]) -> None:
        with self._lock:
            self.macro_sources[macro_id] = list(point_ids)
            self._db.executemany(
                "INSERT OR REPLACE INTO macro_sources VALUES (?, ?)",
                [(macro_id, pid) for pid in point_ids],
            )
            self._db.commit()

    def save_dream_report(self, r: DreamReport) -> None:
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO dream_reports VALUES (" + ",".join("?" * 9) + ")",
                r.to_row(),
            )
            self._db.commit()

    def dream_reports(self, limit: int = 20) -> List[DreamReport]:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM dream_reports ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [DreamReport.from_row(r) for r in rows]

    # --- graph queries -----------------------------------------------------------

    def get_edges(self, point_id: str) -> List[FuEdge]:
        return [self.edges[eid] for eid in self._adjacency.get(point_id, []) if eid in self.edges]

    def edge_between(self, a_id: str, b_id: str) -> Optional[FuEdge]:
        for e in self.get_edges(a_id):
            if (e.from_id == a_id and e.to_id == b_id) or (e.from_id == b_id and e.to_id == a_id):
                return e
        return None

    def neighbours_of(self, point_id: str) -> List[tuple]:
        """[(point, edge)] over active edges; respects one_way direction."""
        out = []
        for e in self.get_edges(point_id):
            if e.status != "active":
                continue
            if e.from_id == point_id:
                other = self.points.get(e.to_id)
            elif e.direction == "two_way":
                other = self.points.get(e.from_id)
            else:
                continue
            if other is not None:
                out.append((other, e))
        return out

    def strong_neighbours(self, point_id: str, min_kappa: float, min_trust: float = 0.0,
                          max_distance: float = 1e9, depth: int = 1) -> List[tuple]:
        """Transitive strong neighbourhood [(point, edge)] (THEORY §16)."""
        seen = {point_id}
        frontier = [point_id]
        result = []
        for _ in range(depth):
            nxt = []
            for pid in frontier:
                for other, e in self.neighbours_of(pid):
                    if other.id in seen or other.status != "active":
                        continue
                    if e.kappa < min_kappa or e.trust < min_trust or e.base_separation > max_distance:
                        continue
                    seen.add(other.id)
                    result.append((other, e))
                    nxt.append(other.id)
            frontier = nxt
        return result

    def active_points(self) -> List[MemoryPoint]:
        # H-04: materialize UNDER the lock — a concurrent save_point() mutating the dict during
        # iteration otherwise raises "dictionary changed size during iteration".
        with self._lock:
            return [p for p in self.points.values() if p.status == "active"]

    def all_points(self) -> List[MemoryPoint]:
        """Locked snapshot for any reader that would otherwise iterate self.points live (H-04)."""
        with self._lock:
            return list(self.points.values())

    def all_edges(self) -> List[FuEdge]:
        with self._lock:
            return list(self.edges.values())

    def centrality(self, point_id: str) -> float:
        from . import fu_math
        return fu_math.compute_centrality(point_id, self.get_edges(point_id), len(self.points))

    def stats(self) -> dict:
        with self._lock:   # H-04: consistent snapshot under concurrent mutation
            points = list(self.points.values())
            edges = list(self.edges.values())
        return {
            "points": len(points),
            "active": sum(1 for p in points if p.status == "active"),
            "dormant": sum(1 for p in points if p.status == "dormant"),
            "edges": len(edges),
            "wormholes": sum(1 for e in edges if e.relation_type == "wormhole"),
            "macros": sum(1 for p in points if p.type == "macro"),
            "layers": {
                layer: sum(1 for p in points if p.layer == layer)
                for layer in config.MEMORY_LAYERS
            },
        }

    def close(self) -> None:
        with self._lock:
            self._db.close()
