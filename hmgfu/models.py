"""Data model: MemoryPoint, FuEdge, QueryPoint, DreamReport (THEORY Part A §3, §4)."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_id() -> str:
    return uuid.uuid4().hex[:16]


@dataclass
class Hex:
    """Cube coordinate on the hex grid (q + r + s == 0)."""
    q: int = 0
    r: int = 0
    s: int = 0

    def key(self) -> str:
        return f"{self.q},{self.r},{self.s}"


@dataclass
class MemoryPoint:
    id: str = field(default_factory=create_id)
    type: str = "message"                 # config.MEMORY_TYPES
    title: str = ""
    content: str = ""
    summary: str = ""
    source: str = "user"                  # user | user_explicit | assistant | dream | system
    timestamp: str = field(default_factory=now_iso)
    last_accessed_at: str = field(default_factory=now_iso)
    access_count: int = 0
    embedding: list = field(default_factory=list)
    keywords: list = field(default_factory=list)
    entities: list = field(default_factory=list)
    topics: list = field(default_factory=list)
    emotional_valence: float = 0.0        # -1..1
    emotional_intensity: float = 0.0      # 0..1
    importance: float = 0.5
    confidence: float = 0.6
    novelty: float = 0.5
    utility: float = 0.5
    density: float = 0.0                  # ρ
    energy: float = 0.0                   # current field energy
    stability: float = 0.0                # resistance to forgetting
    hex: Hex = field(default_factory=Hex)
    layer: str = "L0_raw"
    status: str = "active"                # active | dormant | superseded
    extractor: str = "fallback"           # nano | fallback (THEORY issue 8 observability)

    def to_row(self) -> tuple:
        return (
            self.id, self.type, self.title, self.content, self.summary, self.source,
            self.timestamp, self.last_accessed_at, self.access_count,
            json.dumps(self.embedding), json.dumps(self.keywords),
            json.dumps(self.entities), json.dumps(self.topics),
            self.emotional_valence, self.emotional_intensity, self.importance,
            self.confidence, self.novelty, self.utility, self.density, self.energy,
            self.stability, self.hex.q, self.hex.r, self.hex.s, self.layer,
            self.status, self.extractor,
        )

    @staticmethod
    def from_row(row) -> "MemoryPoint":
        return MemoryPoint(
            id=row[0], type=row[1], title=row[2], content=row[3], summary=row[4],
            source=row[5], timestamp=row[6], last_accessed_at=row[7], access_count=row[8],
            embedding=json.loads(row[9]), keywords=json.loads(row[10]),
            entities=json.loads(row[11]), topics=json.loads(row[12]),
            emotional_valence=row[13], emotional_intensity=row[14], importance=row[15],
            confidence=row[16], novelty=row[17], utility=row[18], density=row[19],
            energy=row[20], stability=row[21], hex=Hex(row[22], row[23], row[24]),
            layer=row[25], status=row[26], extractor=row[27],
        )

    def public(self) -> dict:
        d = asdict(self)
        d.pop("embedding", None)  # too heavy for the UI payload
        return d


@dataclass
class FuEdge:
    id: str = field(default_factory=create_id)
    from_id: str = ""
    to_id: str = ""
    relation_type: str = "semantic_similarity"   # config.RELATION_TYPES
    direction: str = "two_way"                   # one_way | two_way
    kappa: float = 0.0        # κ coupling
    omega: float = 0.7        # Ω relation geometry
    distance: float = 1.0     # Fu magnitude F (THEORY issue 1: stored, not a ranking metric)
    base_separation: float = 1.0  # N — used for the D_Fu penalty
    resonance: float = 0.0
    tension: float = 0.0
    trust: float = 0.5
    created_at: str = field(default_factory=now_iso)
    last_activated_at: str = field(default_factory=now_iso)
    activation_count: int = 0
    status: str = "active"    # active | weak | dormant | broken

    def to_row(self) -> tuple:
        return (
            self.id, self.from_id, self.to_id, self.relation_type, self.direction,
            self.kappa, self.omega, self.distance, self.base_separation, self.resonance,
            self.tension, self.trust, self.created_at, self.last_activated_at,
            self.activation_count, self.status,
        )

    @staticmethod
    def from_row(row) -> "FuEdge":
        return FuEdge(
            id=row[0], from_id=row[1], to_id=row[2], relation_type=row[3], direction=row[4],
            kappa=row[5], omega=row[6], distance=row[7], base_separation=row[8],
            resonance=row[9], tension=row[10], trust=row[11], created_at=row[12],
            last_activated_at=row[13], activation_count=row[14], status=row[15],
        )

    def public(self) -> dict:
        return asdict(self)


@dataclass
class QueryPoint:
    """Temporary point created for each user query (THEORY §10)."""
    text: str = ""
    embedding: list = field(default_factory=list)
    entities: list = field(default_factory=list)
    topics: list = field(default_factory=list)
    intent: str = "question"   # question | task | reflection | emotional | statement
    conversation_act: str = "statement"
    feedback_polarity: str = ""    # positive | negative | "" — router-judged, any language
    action_requested: bool = False
    recovered_action: str = ""     # tool rescued by semantic recovery this turn (Phase 56)
    requested_tools: list = field(default_factory=list)
    explicit_tools: list = field(default_factory=list)   # 95.47d: the tools the user's own words require (a named file / tool / enumeration)
    extraction: dict = field(default_factory=dict)      # 73.2: the full sensitizer extraction (reused at ingest)
    freshness: str = "none"
    needs_memory: bool = True
    runtime_context_keys: list = field(default_factory=list)
    runtime_context_sufficient: bool = False
    directive: Optional[dict] = None
    extractor: str = "fallback"
    timestamp: str = field(default_factory=now_iso)


@dataclass
class RetrievedMemory:
    point: MemoryPoint = None
    edge: Optional[FuEdge] = None
    score: float = 0.0
    reason: str = ""
    path_relevance: float = 1.0          # 74.7: relevance gate of the edge's other endpoint (1.0 = no edge / legacy)

    def public(self) -> dict:
        return {
            "point": self.point.public() if self.point else None,
            "edge": self.edge.public() if self.edge else None,
            "score": round(self.score, 4),
            "reason": self.reason,
        }


@dataclass
class DreamReport:
    id: str = field(default_factory=create_id)
    summary: str = ""
    macros_created: list = field(default_factory=list)
    wormholes_created: list = field(default_factory=list)
    contradictions_found: list = field(default_factory=list)
    memories_decayed: list = field(default_factory=list)
    memories_promoted: list = field(default_factory=list)
    insights: list = field(default_factory=list)
    created_at: str = field(default_factory=now_iso)

    def to_row(self) -> tuple:
        return (
            self.id, self.summary, json.dumps(self.macros_created),
            json.dumps(self.wormholes_created), json.dumps(self.contradictions_found),
            json.dumps(self.memories_decayed), json.dumps(self.memories_promoted),
            json.dumps(self.insights), self.created_at,
        )

    @staticmethod
    def from_row(row) -> "DreamReport":
        return DreamReport(
            id=row[0], summary=row[1], macros_created=json.loads(row[2]),
            wormholes_created=json.loads(row[3]), contradictions_found=json.loads(row[4]),
            memories_decayed=json.loads(row[5]), memories_promoted=json.loads(row[6]),
            insights=json.loads(row[7]), created_at=row[8],
        )

    def public(self) -> dict:
        return asdict(self)
