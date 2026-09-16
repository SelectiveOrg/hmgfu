"""Ingestion pipeline (THEORY §11–§13): sensitize → embed → density → hex → edges → propagate → macros."""

from __future__ import annotations

import logging
from typing import Callable, List, Optional

from .extraction_schema import _DEFAULTS   # J5: a point is born at the schema default utility
from . import config, fu_math, hexgrid
from .models import FuEdge, MemoryPoint, now_iso
from .propagate import propagate_energy
from .sensitizer import Sensitizer
from .store import HMGGraph

log = logging.getLogger("hmgfu.ingest")


_NEG = ("not", "n't", "no longer", "never", "isn't", "aren't", "wasn't", "stop", "instead",
        "não", "nunca", "deixou")


def _negation_polarity(text: str) -> bool:
    low = text.lower()
    return any(cue in low for cue in _NEG)


def _find_duplicate(embedding: List[float], mtype: str, content: str,
                    graph: HMGGraph) -> Optional[MemoryPoint]:
    """Nearest active same-kind point above the dedup threshold (THEORY: memory is relational,
    not a log — identical assertions reinforce one node instead of accumulating copies).
    A negation vs affirmation ('X' vs 'not X') is a CONTRADICTION, not a duplicate — never merge."""
    polarity = _negation_polarity(content)
    best, best_sim = None, config.DEDUP_MIN_COSINE
    from . import vecindex
    cands = [p for p in graph.active_points()
             if p.type == mtype and p.embedding and p.type not in ("skill", "macro")
             and _negation_polarity(p.content) == polarity]           # opposite polarity → not a duplicate
    nearest, sim = vecindex.best(embedding, cands, graph=graph)          # 76.2: one matrix product, same nearest
    if nearest is not None and sim >= best_sim:
        best, best_sim = nearest, sim
    return best


def classify_relation(a: MemoryPoint, b: MemoryPoint) -> str:
    """Pick the dominant relation type from the strongest available signal (THEORY §12)."""
    if fu_math.jaccard(a.entities, b.entities) >= 0.5:
        return "same_entity"
    if fu_math.contradiction_heuristic(a, b) > 0.5:
        return "contradiction"
    if fu_math.detect_causal_signal(a, b) > 0.4:
        return "causal"
    shared_topics = fu_math.jaccard(a.topics, b.topics)
    if shared_topics > 0 and ("goal" in (a.type, b.type) or "task" in (a.type, b.type)):
        return "goal_related"
    if shared_topics > 0 and "project" in (a.type, b.type):
        return "project_related"
    if a.emotional_intensity > 0.5 and b.emotional_intensity > 0.5:
        return "emotional"
    if fu_math.hours_between(a.timestamp, b.timestamp) < 2.0:
        return "temporal"
    return "semantic_similarity"


def assign_hex(point: MemoryPoint, graph: HMGGraph):
    """THEORY §13: weighted centroid of the 12 nearest semantic points, then nearest free cell."""
    from . import vecindex
    others = [p for p in graph.active_points() if p.id != point.id and p.embedding]
    top = vecindex.top_k(point.embedding, others, config.CANDIDATE_NEIGHBOURS, graph=graph)   # 76.2
    sims = vecindex.scores(point.embedding, top, graph=graph)
    nearby = list(zip(top, sims))
    if not nearby:
        return hexgrid.nearest_free_hex(point.hex, graph.occupied)
    centroid = hexgrid.weighted_centroid(
        [(p.hex, max(0.0, sim) * max(p.density, 0.05)) for p, sim in nearby]
    )
    return hexgrid.nearest_free_hex(centroid, graph.occupied)


def build_fu_edges(point: MemoryPoint, candidates: List[MemoryPoint],
                   graph: HMGGraph) -> List[FuEdge]:
    """THEORY §12 — one edge per candidate above the κ floor."""
    edges: List[FuEdge] = []
    for candidate in candidates:
        if candidate.id == point.id or graph.edge_between(point.id, candidate.id):
            continue
        relation_type = classify_relation(point, candidate)
        kappa = fu_math.compute_kappa(point, candidate)
        if kappa < config.KAPPA_MIN_EDGE and relation_type != "wormhole":
            continue
        omega = fu_math.compute_omega(relation_type)
        n = fu_math.base_separation(hexgrid.hex_distance(point.hex, candidate.hex))
        edges.append(FuEdge(
            from_id=point.id,
            to_id=candidate.id,
            relation_type=relation_type,
            direction="one_way" if relation_type in ("causal", "evidence_for", "evidence_against") else "two_way",
            kappa=kappa,
            omega=omega,
            distance=fu_math.fu_distance(kappa, omega, point.density, candidate.density, n),
            base_separation=n,
            resonance=fu_math.compute_resonance(point, candidate),
            tension=fu_math.compute_tension(point, candidate),
            trust=fu_math.compute_trust(point, candidate),
        ))
        if len(edges) >= config.MAX_EDGES_PER_INGEST:
            break
    return edges


def find_relation_candidates(point: MemoryPoint, graph: HMGGraph, limit: int = 30) -> List[MemoryPoint]:
    """Union of semantic-nearest and entity-sharing active points."""
    from . import vecindex
    active = [p for p in graph.active_points() if p.id != point.id]
    semantic = vecindex.top_k(point.embedding, [p for p in active if p.embedding], limit, graph=graph)   # 76.2
    entity_hits = [p for p in active if fu_math.jaccard(point.entities, p.entities) > 0][:limit]
    seen, out = set(), []
    for p in semantic + entity_hits:
        if p.id not in seen:
            seen.add(p.id)
            out.append(p)
    return out


def reawaken_dormant(point: MemoryPoint, graph: HMGGraph) -> int:
    """THEORY issue 4: a dormant memory directly referenced by entity comes back to life."""
    woken = 0
    if not point.entities:
        return 0
    for p in graph.points.values():
        if p.status == "dormant" and fu_math.jaccard(point.entities, p.entities) >= 0.5:
            p.status = "active"
            p.energy = max(p.energy, 0.3)
            p.last_accessed_at = now_iso()
            graph.save_point(p)
            woken += 1
    return woken


def ingest_memory(content: str, source: str, graph: HMGGraph, sensitizer: Sensitizer,
                  embed: Callable[[str], List[float]],
                  mtype: Optional[str] = None, extracted=None, embedding=None,
                  timestamp: Optional[str] = None) -> MemoryPoint:
    """THEORY §11 — the 12-step ingestion cycle. 73.2: `extracted` / `embedding` already computed for this
    exact text (the turn's routing extraction, the query embedding) are reused instead of a second model call.
    74.8: `timestamp` = when the content was OBSERVED (imports, replays, benches); default now. Everything derived
    at ingest — macro dates, spans — follows the observation time, never the import time."""
    extracted = extracted if extracted else sensitizer.extract(content)
    embedding = list(embedding) if embedding else embed(content)
    # dedup: a near-identical active memory of the same kind → reinforce it, don't duplicate
    # (stops the "Your name is Sebastian" ×4 pollution). Reinforcement = recency + energy bump.
    dup = _find_duplicate(embedding, mtype or extracted["type"], content, graph)
    if dup is not None:
        dup.access_count += 1
        dup.last_accessed_at = now_iso()
        dup.energy = fu_math.clamp(dup.energy + 0.1)
        dup.confidence = fu_math.clamp(max(dup.confidence, extracted["confidence"]))
        if len(content) > len(dup.content):   # keep the fuller phrasing
            dup.content, dup.summary = content, extracted["summary"] or dup.summary
        dup.density = fu_math.compute_density(dup, graph.centrality(dup.id))
        graph.save_point(dup)
        log.info("dedup: reinforced %s instead of a new %s node", dup.id, dup.type)
        return dup
    forced_type = mtype or extracted["type"]
    # Authorship guard (Phase 48, Rule 3: a type+source predicate, not a string blocklist): the
    # assistant RECALLS facts, it never AUTHORS canon; a nano mislabelling a reply/dream summary
    # as fact/person/place/concept/event is a category error — demote to episodic 'message' at
    # the one point source and type converge (stops "I built your widget" becoming a user fact).
    if source in ("assistant", "dream") and forced_type in ("fact", "person", "place", "concept", "event"):
        forced_type = "message"
    # Speech-act gate (Phase 62): a user QUESTION/REQUEST is an episode, never a fact/person —
    # both stores held "what is my name?" as identity and recalled it as evidence.
    from .speech_act import is_interrogative
    is_question = source in ("user", "user_explicit") and is_interrogative(content)
    if is_question and forced_type in ("fact", "person", "place", "concept", "event", "decision"):
        forced_type = "message"
    # Status gate (Phase 90.N, the same shape as the two gates above): a user message with NO assertive clause — a
    # proposal, a wish, a plan — is an EPISODE, never an active project. Traced defect s06: the nano types "We should
    # work on Mapiko." `task`, and organise_for_injection files goal/project/task under the section rendered as
    # "Active projects and goals", so the DELIVERED CONTEXT asserts an activity the user only proposed — the status is
    # lost two layers before the reader. Reuses the modality contract of 90.L; the words stay verbatim in the episode,
    # only the ACTIVITY CLAIM is refused. An acceptance followed by an explicit start types normally again.
    from .utterance import sentence_modalities
    _mods = [c["modality"] for c in sentence_modalities(content)] if source in ("user", "user_explicit") else []
    no_assertion = bool(_mods) and "assert" not in _mods and not is_question
    # the TAG is narrower than the type gate on purpose: a past, fiction or citation clause also has no assertion, and
    # it is NOT a proposal — routing it to the proposals section would be the same category error in a new place.
    is_intent = no_assertion and "intent" in _mods
    if no_assertion and forced_type in ("goal", "project", "task"):
        forced_type = "message"
    point = MemoryPoint(
        type=forced_type,
        title=extracted["title"],
        content=content,
        summary=extracted["summary"],
        source=source,
        embedding=embedding,
        keywords=extracted["keywords"],
        entities=extracted["entities"],
        topics=extracted["topics"],
        emotional_valence=extracted["emotional_valence"],
        emotional_intensity=extracted["emotional_intensity"],
        importance=extracted["importance"],
        confidence=extracted["confidence"],
        novelty=extracted["novelty"],
        utility=_DEFAULTS["utility"],       # J5: utility is EARNED by use (grader EMA), never rated at birth
        energy=extracted["importance"],
        extractor=extracted["extractor"],
        timestamp=timestamp or now_iso(),
    )
    # ephemeral observations (weather-now, prices, time) are true only briefly — tag them via
    # the single choke-point (Phase 48) so retrieval decays them within hours; same wrapper is
    # reused by the macro + playbook creation paths.
    from .hygiene import apply_ephemeral_meta
    apply_ephemeral_meta(point)
    if is_question and "_question" not in point.keywords:
        point.keywords = list(point.keywords) + ["_question"]
        point.utility = min(point.utility, 0.3)
    # 90.N (iteration 2): the same keyword tag the store already uses for questions and ephemeral observations. Refusing
    # the ACTIVITY CLAIM must not delete the information: the tag lets the renderer deliver the sentence under a heading
    # that states what it is, instead of dropping it into the general pool where the reader stops offering it at all.
    if is_intent and "_intent" not in point.keywords:
        point.keywords = list(point.keywords) + ["_intent"]
    if source in ("user", "user_explicit"):
        from .directives import detect_tool_rule
        det = detect_tool_rule(content)
        if det and not det.get("clear") and "_tool_rule" not in point.keywords:
            point.keywords = list(point.keywords) + ["_tool_rule"]     # 66.5: survives action turns
    point.embedding = embedding
    point.density = fu_math.compute_density(point, centrality=0.0)
    point.hex = assign_hex(point, graph)
    point.stability = fu_math.compute_stability(point)
    graph.save_point(point)

    woken = reawaken_dormant(point, graph)
    candidates = find_relation_candidates(point, graph)
    edges = build_fu_edges(point, candidates, graph)
    for edge in edges:
        graph.save_edge(edge)
    # density depends on centrality, which the new edges just changed — recompute once
    point.density = fu_math.compute_density(point, graph.centrality(point.id))
    point.stability = fu_math.compute_stability(point)
    graph.save_point(point)

    propagate_energy(point, graph)
    # user-explicit statements resolve conflicts IMMEDIATELY (a correction must not wait
    # for the next dream loop — bench B2 lesson; function-level import avoids a cycle)
    if source == "user_explicit":
        from .dream import detect_point_contradictions, mark_tension
        for contradiction in detect_point_contradictions(point, graph, sensitizer):
            mark_tension(contradiction, graph)
    update_macros(point, graph, sensitizer, embed)
    log.info("ingested %s (%s, %d edges, %d reawakened)", point.id, point.type, len(edges), woken)
    return point


def find_local_cluster(point: MemoryPoint, graph: HMGGraph) -> List[MemoryPoint]:
    """THEORY §18: strong local neighbourhood eligible for macro consolidation.
    P2 (ANALYSIS 4.3): `_ephemeral` observations are TRANSIENT — never consolidated.
    Phase 43: SPECIALS (directive/skill/session) survive compression — never clustered."""
    from .taxonomy import SPECIAL_TYPES
    eligible = (point.density >= config.MACRO_MIN_DENSITY
                and "_ephemeral" not in point.keywords and point.type not in SPECIAL_TYPES)
    members = [point] if eligible else []
    for other, edge in graph.strong_neighbours(point.id, min_kappa=config.MACRO_MIN_KAPPA, depth=2):
        if other.type in ("macro",) + SPECIAL_TYPES or other.density < config.MACRO_MIN_DENSITY \
                or "_ephemeral" in other.keywords:
            continue
        members.append(other)
        if len(members) >= config.MACRO_MAX_NODES:
            break
    return members


def update_macros(point: MemoryPoint, graph: HMGGraph, sensitizer: Sensitizer,
                  embed: Callable[[str], List[float]]) -> Optional[MemoryPoint]:
    """THEORY §18 — consolidate the local cluster into (or merge with) a macro-memory."""
    cluster = find_local_cluster(point, graph)
    if len(cluster) < config.MACRO_MIN_CLUSTER:
        return None
    cluster_ids = {p.id for p in cluster}
    existing = None
    for macro_id, sources in graph.macro_sources.items():
        if len(cluster_ids & set(sources)) >= max(2, len(sources) // 2):
            existing = graph.points.get(macro_id)
            break
    summary = sensitizer.summarise_cluster(cluster)
    # provenance: the span of member observations (content only — summary stays the nano's
    # sentence so embeddings are not polluted by date strings)
    span_lo = min(p.timestamp for p in cluster)[:10]
    span_hi = max(p.timestamp for p in cluster)[:10]
    span = f" (observed {span_lo} → {span_hi})" if span_lo != span_hi else f" (observed {span_lo})"
    density = fu_math.clamp(sum(p.density for p in cluster) / len(cluster) + 0.1)
    if existing is not None:
        existing.summary = summary or existing.summary
        existing.density = fu_math.clamp((existing.density + density) / 2)
        existing.last_accessed_at = now_iso()
        existing.timestamp = max(existing.timestamp, max(p.timestamp for p in cluster))   # 74.8: content's recency
        graph.save_point(existing)
        graph.save_macro_sources(existing.id, sorted(cluster_ids | set(graph.macro_sources.get(existing.id, []))))
        return existing
    macro = MemoryPoint(
        type="macro",
        title=f"Macro: {point.topics[0] if point.topics else point.title[:40]}",
        content=(summary + span) if summary else summary,
        summary=summary,
        source="dream",
        embedding=embed(summary) if summary else list(point.embedding),
        keywords=point.keywords,
        entities=sorted({e for p in cluster for e in p.entities})[:10],
        topics=sorted({t for p in cluster for t in p.topics})[:6],
        importance=max(p.importance for p in cluster),
        utility=max(p.utility for p in cluster),
        confidence=sum(p.confidence for p in cluster) / len(cluster),
        density=density,
        energy=0.5,
        layer="L2_project",
        timestamp=max(p.timestamp for p in cluster),   # 74.8: a summary is as recent as what it summarises, not the dream
    )
    macro.hex = assign_hex(macro, graph)
    macro.stability = fu_math.compute_stability(macro)
    from .hygiene import apply_ephemeral_meta   # a macro of ephemeral observations is ephemeral
    apply_ephemeral_meta(macro)
    graph.save_point(macro)
    graph.save_macro_sources(macro.id, sorted(cluster_ids))
    for member in cluster:
        n = fu_math.base_separation(hexgrid.hex_distance(macro.hex, member.hex))
        graph.save_edge(FuEdge(
            from_id=member.id, to_id=macro.id, relation_type="part_of", direction="two_way",
            kappa=0.6, omega=fu_math.compute_omega("part_of"),
            distance=fu_math.fu_distance(0.6, 0.9, member.density, macro.density, n),
            base_separation=n, resonance=0.6, tension=0.0, trust=0.7,
        ))
    log.info("macro %s created over %d points", macro.id, len(cluster))
    return macro
