"""All Fu-theory formulas (THEORY Part A §5–§10, §20, §21 + Part B issue 5 definitions).

Pure functions — no I/O, no Ollama. Everything here is unit-tested in tests/test_fu_math.py.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import List, Optional

from . import config
from .models import FuEdge, MemoryPoint, QueryPoint


# --- primitives ---------------------------------------------------------------

def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return clamp(dot / (na * nb), -1.0, 1.0)


_LEXICAL_STOP = {"a", "an", "the", "is", "are", "was", "were", "do", "did", "does",
                 "what", "which", "who", "where", "when", "how", "my", "your", "me",
                 "i", "you", "it", "to", "of", "for", "in", "on", "with", "about"}


def lexical_relevance(query_text: str, content: str) -> float:
    """Literal query-token coverage, guarding embedding collisions on exact facts/IDs."""
    tokens = lambda s: {t for t in re.findall(r"[a-z0-9-]+", (s or "").lower())
                        if len(t) > 1 and t not in _LEXICAL_STOP}
    query, memory = tokens(query_text), tokens(content)
    return len(query & memory) / len(query) if query else 0.0


def jaccard(a: List[str], b: List[str]) -> float:
    sa, sb = {x.lower() for x in a}, {x.lower() for x in b}
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def normalise_log(x: float, ref: float = config.RECURRENCE_REF) -> float:
    """log-saturating normalisation: 0 → 0, ref → 1 (THEORY issue 5)."""
    if x <= 0:
        return 0.0
    return clamp(math.log(1 + x) / math.log(1 + ref))


def _parse_ts(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def hours_between(t1: str, t2: str) -> float:
    return abs((_parse_ts(t1) - _parse_ts(t2)).total_seconds()) / 3600.0


def compare_ts(t1: str, t2: str) -> int:
    """Chronological comparison of two ISO timestamps → 1 if t1 newer, -1 if older, 0 equal.
    Parses offsets to real UTC instants (M-06): '10:00+05:00' (05:00Z) is OLDER than
    '08:00+00:00' — a naive string compare gets this backwards. Falls back to string order
    only if a timestamp is unparseable."""
    try:
        a, b = _parse_ts(t1), _parse_ts(t2)
    except (ValueError, TypeError):
        return (t1 > t2) - (t1 < t2)
    return (a > b) - (a < b)


def age_days(ts: str, now: Optional[str] = None) -> float:
    ref = _parse_ts(now) if now else datetime.now(timezone.utc)
    return max(0.0, (ref - _parse_ts(ts)).total_seconds() / 86400.0)


def age_label(ts: str, now: Optional[str] = None) -> str:
    """Human relative age so the LLM perceives which memories are old vs new."""
    try:
        secs = age_days(ts, now) * 86400.0
    except (ValueError, TypeError):
        return "unknown time"
    if secs < 90:
        return "just now"
    if secs < 3600:
        return f"{int(secs // 60)}m ago"
    if secs < 86400:
        return f"{int(secs // 3600)}h ago"
    days = secs / 86400.0
    if days < 14:
        return f"{int(days)}d ago"
    if days < 60:
        return f"{int(days // 7)}w ago"
    if days < 730:
        return f"{int(days // 30)}mo ago"
    return f"{int(days // 365)}y ago"


def temporal_proximity(t1: str, t2: str) -> float:
    """exp(-|Δt|/τ), τ = 72h (THEORY issue 5)."""
    return math.exp(-hours_between(t1, t2) / config.TEMPORAL_TAU_HOURS)


def recency_score(ts: str, now: Optional[str] = None) -> float:
    """exp(-age/τ), τ = 14 days (THEORY issue 5)."""
    return math.exp(-age_days(ts, now) / config.RECENCY_TAU_DAYS)


def distance_decay(fu_distance: float) -> float:
    """Attenuation by Fu magnitude: F=1 → 1.0, larger intervals attenuate (THEORY issue 5)."""
    return 1.0 / (1.0 + max(0.0, fu_distance - 1.0))


# --- ρ: ontological density (§6) -------------------------------------------------

def compute_centrality(point_id: str, edges: List[FuEdge], n_points: int) -> float:
    """Local relational centrality: κ-weighted degree, log-normalised (THEORY §6 'L')."""
    weighted_degree = sum(
        e.kappa for e in edges
        if e.status == "active" and (e.from_id == point_id or e.to_id == point_id)
    )
    return normalise_log(weighted_degree, ref=8.0)


def compute_density(p: MemoryPoint, centrality: float) -> float:
    w = config.DENSITY_WEIGHTS
    recurrence = normalise_log(p.access_count + 1)
    raw = (
        w["importance"] * p.importance
        + w["recurrence"] * recurrence
        + w["emotionalIntensity"] * p.emotional_intensity
        + w["utility"] * p.utility
        + w["confidence"] * p.confidence
        + w["novelty"] * p.novelty
        + w["centrality"] * centrality
    )
    return clamp(raw)


def compute_stability(p: MemoryPoint) -> float:
    """stability = 0.5·ρ + 0.3·recurrence + 0.2·confidence (THEORY issue 5)."""
    return clamp(0.5 * p.density + 0.3 * normalise_log(p.access_count + 1) + 0.2 * p.confidence)


# --- κ: coupling (§7) --------------------------------------------------------------

def detect_explicit_reference(a: MemoryPoint, b: MemoryPoint) -> float:
    """X term: literal mention of the other point's title/entities (THEORY issue 9)."""
    def mentions(text: str, other: MemoryPoint) -> bool:
        low = text.lower()
        if other.title and len(other.title) > 3 and other.title.lower() in low:
            return True
        return any(len(e) > 2 and e.lower() in low for e in other.entities)
    return 1.0 if (mentions(a.content, b) or mentions(b.content, a)) else 0.0


_CAUSAL_CUES = ("because", "therefore", "so that", "caused", "leads to", "resulted",
                "porque", "portanto", "por isso", "causou", "resultou", "devido")


def detect_causal_signal(a: MemoryPoint, b: MemoryPoint) -> float:
    """Heuristic C term; the sensitizer may override with a nano judgement."""
    text = (a.content + " " + b.content).lower()
    hit = any(cue in text for cue in _CAUSAL_CUES)
    return (0.6 if hit else 0.0) * (1.0 if jaccard(a.topics, b.topics) > 0 else 0.5)


def compute_kappa(a: MemoryPoint, b: MemoryPoint,
                  causal: Optional[float] = None,
                  explicit: Optional[float] = None) -> float:
    w = config.KAPPA_WEIGHTS
    raw = (
        w["semantic"] * cosine(a.embedding, b.embedding)
        + w["temporal"] * temporal_proximity(a.timestamp, b.timestamp)
        + w["entityOverlap"] * jaccard(a.entities, b.entities)
        + w["goalOverlap"] * jaccard(a.topics, b.topics)
        + w["causal"] * (causal if causal is not None else detect_causal_signal(a, b))
        + w["explicit"] * (explicit if explicit is not None else detect_explicit_reference(a, b))
    )
    return clamp(raw)


def query_kappa(q: QueryPoint, p: MemoryPoint) -> float:
    """κ estimate between a query and a stored point: T=0, X from literal mention (issue 9)."""
    w = config.KAPPA_WEIGHTS
    low = q.text.lower()
    explicit = 1.0 if (
        (p.title and len(p.title) > 3 and p.title.lower() in low)
        or any(len(e) > 2 and e.lower() in low for e in p.entities)
    ) else 0.0
    raw = (
        w["semantic"] * cosine(q.embedding, p.embedding)
        + w["entityOverlap"] * jaccard(q.entities, p.entities)
        + w["goalOverlap"] * jaccard(q.topics, p.topics)
        + w["explicit"] * explicit
    )
    return clamp(raw)


# --- Ω and F (§8, §9) -----------------------------------------------------------------

def compute_omega(relation_type: str) -> float:
    return config.OMEGA.get(relation_type, config.OMEGA_DEFAULT)


def fu_distance(kappa: float, omega: float, rho_a: float, rho_b: float,
                base_separation: float) -> float:
    """F(A,B) = N · [1 + κ·ρA·ρB·Ω] — relational magnitude, NOT a ranking metric (issue 1)."""
    return base_separation * (1.0 + kappa * rho_a * rho_b * omega)


def base_separation(hex_dist: int) -> float:
    """N(A,B) = 1 + hexDistance/3 (THEORY issue 5)."""
    return 1.0 + hex_dist / 3.0


# --- resonance / tension / trust (issue 5) ----------------------------------------------

def compute_resonance(a: MemoryPoint, b: MemoryPoint) -> float:
    sem = cosine(a.embedding, b.embedding)
    emo = 1.0 - abs(a.emotional_valence - b.emotional_valence) / 2.0
    return clamp(0.6 * sem + 0.4 * emo)


_NEGATION_CUES = ("not ", "no longer", "instead", "never", "stopped", "won't", "don't",
                  "não ", "nunca", "deixou de", "em vez", "já não")


def contradiction_heuristic(a: MemoryPoint, b: MemoryPoint) -> float:
    """Fallback contradiction signal: shared topic/entity + negation cue + opposite valence."""
    overlap = max(jaccard(a.topics, b.topics), jaccard(a.entities, b.entities))
    if overlap == 0:
        return 0.0
    text = (a.content + " " + b.content).lower()
    negation = any(cue in text for cue in _NEGATION_CUES)
    valence_flip = (a.emotional_valence * b.emotional_valence) < -0.05
    # explicit negation over strongly-shared entities is a high-confidence contradiction
    # even with neutral valence (bench B2: "stop ending with X, use Y instead")
    signal = (0.6 if negation else 0.0) + (0.35 if valence_flip else 0.0)
    return clamp(signal * (0.6 + overlap))


def compute_tension(a: MemoryPoint, b: MemoryPoint,
                    contradiction_signal: Optional[float] = None) -> float:
    sig = contradiction_signal if contradiction_signal is not None else contradiction_heuristic(a, b)
    return clamp(sig * max(jaccard(a.topics, b.topics), 0.3))


def compute_trust(a: MemoryPoint, b: MemoryPoint) -> float:
    st = config.SOURCE_TRUST
    source_part = (st.get(a.source, 0.6) + st.get(b.source, 0.6)) / 2.0
    conf_part = (a.confidence + b.confidence) / 2.0
    return clamp(0.5 * source_part + 0.5 * conf_part)


# --- retrieval score (§30 — canonical) ------------------------------------------------------

def mode_match(q: QueryPoint, p: MemoryPoint) -> float:
    """M term: topical alignment with the query's mode/intent (THEORY issue 5)."""
    topical = jaccard(q.topics, p.topics)
    intent_bonus = 0.0
    if q.intent == "task" and p.type in ("task", "goal", "project", "skill", "decision"):
        intent_bonus = 0.5
    elif q.intent == "emotional" and (p.type == "emotion" or p.emotional_intensity > 0.5):
        intent_bonus = 0.5
    elif q.intent == "question" and p.type in ("fact", "concept", "macro", "person", "place", "event"):
        intent_bonus = 0.3
    elif q.intent == "reflection" and p.type == "reflection":
        intent_bonus = 0.5      # self-aware nodes surface when the LLM is THINKING (Phase 43)
    return clamp(0.5 * topical + intent_bonus + 0.25)


def normalise_separation(n: float) -> float:
    """D_Fu penalty input: base separation N mapped to 0..1 (issue 1)."""
    return clamp((n - 1.0) / 4.0)


def relevance_gate(q: QueryPoint, p: MemoryPoint, semantic: Optional[float] = None) -> float:
    """Phase 47 relevance gate in [0, 1]: how much a memory is ABOUT the query (semantic or κ), scaled between
    config.IMPORTANCE_RELEVANCE_GATE floor and ref. Used for the ρ/U importance terms and (74.7) for the κ a
    neighbouring candidate can lend along a path."""
    if semantic is None:
        semantic = 0.75 * cosine(q.embedding, p.embedding) + 0.25 * lexical_relevance(q.text, p.content)
    g = config.IMPORTANCE_RELEVANCE_GATE
    return clamp((max(semantic, query_kappa(q, p)) - g["floor"]) / max(1e-6, g["ref"] - g["floor"]))


def memory_score_components(q: QueryPoint, p: MemoryPoint,
                            edge: Optional[FuEdge] = None, path_relevance: float = 1.0) -> dict:
    """Per-component values of MemoryScore, keyed like config.MEMORY_SCORE_WEIGHTS, plus the
    multiplicative factors. ONE implementation shared by scoring and by the weight LEARNER
    (Phase 56): the learner assigns credit/blame to exactly what the score computed.
    `path_relevance` (74.7): relevance gate of the edge's OTHER endpoint to the query — the κ the edge lends is
    κ along the path query → other → p, so a cluster of self-similar memories no longer inflates every member
    whatever the question (§30 βκ is query-relative). The score takes the STRONGEST path, direct or via the edge;
    an edge that lends nothing brings no distance penalty either."""
    semantic = 0.75 * cosine(q.embedding, p.embedding) + 0.25 * lexical_relevance(q.text, p.content)
    # Phase 47 relevance gate: the ρ/U "general importance" terms only AMPLIFY an already
    # on-topic memory — they must not let a globally-dense hub outrank on-topic memories on
    # an unrelated query. Gate on query-relative relevance only (never edge.kappa, which a
    # hub maxes out regardless of the query). See config.IMPORTANCE_RELEVANCE_GATE.
    imp_gate = relevance_gate(q, p, semantic)
    direct_kappa = query_kappa(q, p)
    via_kappa = edge.kappa * clamp(path_relevance) if edge is not None else 0.0
    via_path = edge is not None and via_kappa >= direct_kappa
    # issue 15 source-trust + issue 16 ephemeral decay — multiplicative, not learned
    factor = config.SOURCE_SCORE_FACTOR.get(p.source, 1.0)
    if "_ephemeral" in p.keywords:
        factor *= math.exp(-age_days(p.timestamp) * 24.0 / config.EPHEMERAL_TAU_HOURS)
    return {
        "semantic": semantic,
        "kappa": via_kappa if via_path else direct_kappa,
        "density": p.density * imp_gate,
        "utility": p.utility * imp_gate,
        "recency": recency_score(p.timestamp),
        "modeMatch": mode_match(q, p),
        "wormholeBoost": 1.0 if (edge is not None and edge.relation_type == "wormhole") else 0.0,
        "fuDistancePenalty": normalise_separation(edge.base_separation) if via_path else 0.2,
        "tensionPenalty": edge.tension if edge is not None else 0.0,
        "_factor": factor,
    }


def memory_score(q: QueryPoint, p: MemoryPoint, edge: Optional[FuEdge] = None,
                 weights: Optional[dict] = None, path_relevance: float = 1.0) -> float:
    """MemoryScore(p|q) = αS + βκ + γρ + δU + εR + ζM + ηW − λD_Fu − τT (§30).
    `weights` = effective (possibly LEARNED) weights; None → the config baseline.
    `path_relevance` (74.7): see memory_score_components."""
    w = weights or config.MEMORY_SCORE_WEIGHTS
    c = memory_score_components(q, p, edge, path_relevance)
    raw = sum(w[k] * c[k] * (-1.0 if k.endswith("Penalty") else 1.0)
              for k in config.MEMORY_SCORE_WEIGHTS)
    return clamp(raw * c["_factor"])


# --- decay & promotion (§20, §21) --------------------------------------------------------------

def compute_decay(p: MemoryPoint, now: Optional[str] = None) -> float:
    age_factor = math.log(age_days(p.timestamp, now) + 1.0) / 10.0
    recurrence = normalise_log(p.access_count + 1)
    decay = (
        config.BASE_DECAY
        * (1.0 - p.density)
        * (1.0 - p.utility)
        * (1.0 - recurrence)
        * age_factor
    )
    return clamp(decay, 0.0, config.DECAY_CAP)


def should_go_dormant(p: MemoryPoint, centrality: float) -> bool:
    """Dormancy gate incl. centrality guard (THEORY issue 4: hubs never sleep)."""
    return (
        p.energy < config.DORMANT_ENERGY
        and p.density < config.DORMANT_DENSITY
        and p.access_count < config.DORMANT_MAX_ACCESS
        and centrality < config.DORMANT_MAX_CENTRALITY
    )


def should_promote(p: MemoryPoint) -> bool:
    t = config.PROMOTE
    return (
        p.density > t["density"]
        and p.utility > t["utility"]
        and p.confidence > t["confidence"]
        and p.access_count >= t["accessCount"]
        and p.stability > t["stability"]
        and p.layer != config.MEMORY_LAYERS[-1]
    )


def next_layer(layer: str) -> str:
    layers = config.MEMORY_LAYERS
    i = layers.index(layer) if layer in layers else 0
    return layers[min(i + 1, len(layers) - 1)]


# --- propagation attenuation (§14 + issue 3) -----------------------------------------------------

def propagation_factor(edge: FuEdge) -> float:
    """Per-hop attenuation, clamped so no configuration amplifies energy."""
    factor = edge.kappa * edge.omega * edge.trust * distance_decay(edge.distance) * (1.0 - edge.tension)
    return clamp(factor, 0.0, config.PROPAGATION_MAX_FACTOR)
