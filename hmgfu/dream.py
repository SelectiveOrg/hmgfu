"""Dream loop (THEORY §17, §19–§22): the periodic reorganisation of the memory field.

Full loop = macros + wormholes + contradictions + decay + promotion + rebalance + insights.
Mini loop (THEORY issue 11) = decay + promotion + contradiction marking only (fast, no LLM).
"""

from __future__ import annotations

import itertools
import logging
from typing import Callable, List, Optional, Tuple

from . import config, fu_math, hexgrid
from .ingest import update_macros
from .slots import value_in_text   # 95.1: one containment rule, shared with fact_nodes
from .models import DreamReport, FuEdge, MemoryPoint, create_id, now_iso
from .sensitizer import Sensitizer
from .store import HMGGraph

log = logging.getLogger("hmgfu.dream")


# --- wormholes (§17) --------------------------------------------------------------

def analogy_heuristic(a: MemoryPoint, b: MemoryPoint) -> float:
    """THEORY issue 10: structural similarity with lexical dissimilarity."""
    semantic = fu_math.cosine(a.embedding, b.embedding)
    entity_overlap = fu_math.jaccard(a.entities, b.entities)
    topic_overlap = fu_math.jaccard(a.topics, b.topics)
    return fu_math.clamp(semantic * (1.0 - entity_overlap) + 0.3 * topic_overlap)


def _wormhole_gates(a: MemoryPoint, b: MemoryPoint, analogy: float, w: dict):
    """(structural_ok, failed_relaxable_gates). The STRUCTURAL gates (hex distance, lexical
    dissimilarity) define what a wormhole IS and never adapt; the three threshold gates are
    the calibrator-relaxable ones (Phase 56)."""
    structural = (
        hexgrid.hex_distance(a.hex, b.hex) > w["minHexDistance"]
        and fu_math.jaccard(a.entities, b.entities) < w["maxEntityOverlap"]
    )
    failed = [key for key, ok in (
        ("minAnalogy", analogy > w["minAnalogy"]),
        ("minSemantic", fu_math.cosine(a.embedding, b.embedding) > w["minSemantic"]),
        ("minDensity", min(a.density, b.density) > w["minDensity"]),
    ) if not ok]
    return structural, failed


def should_create_wormhole(a: MemoryPoint, b: MemoryPoint, analogy: float,
                           thresholds: dict = None) -> bool:
    """Distant + strongly analogous + lexically dissimilar + both load-bearing (Phase 33).
    Gates on DENSITY, not novelty — see config.WORMHOLE for why. `thresholds` = calibrated
    gate overlay (WormholeCalibrator.effective()); None → config baseline."""
    structural, failed = _wormhole_gates(a, b, analogy, thresholds or config.WORMHOLE)
    return structural and not failed


def create_wormhole(a: MemoryPoint, b: MemoryPoint) -> FuEdge:
    w = config.WORMHOLE
    return FuEdge(
        from_id=a.id, to_id=b.id, relation_type="wormhole", direction="two_way",
        kappa=w["kappa"], omega=w["omega"], distance=w["distance"],
        base_separation=fu_math.base_separation(hexgrid.hex_distance(a.hex, b.hex)),
        resonance=fu_math.compute_resonance(a, b),
        tension=fu_math.compute_tension(a, b),
        trust=w["trust"],
    )


def find_distant_analogical_pairs(graph: HMGGraph, sensitizer: Sensitizer,
                                  max_pairs: int = 5, thresholds: dict = None,
                                  near_misses: dict = None, pool=None) -> List[Tuple[MemoryPoint, MemoryPoint]]:
    """Sample dense points from different hex regions; the nano is the QUALITY judge (it vetoes
    spurious analogies among short/conversational nodes). A content-length floor just drops
    trivially short nodes; we deliberately do NOT whitelist types — a genuine analogy can live
    in a plain statement, and over-restricting types silently hides real wormholes (Phase 33).
    `near_misses` (Phase 56): pairs that pass the structural gates but fail EXACTLY ONE
    relaxable threshold are tallied per gate — the calibrator's evidence."""
    w = thresholds or config.WORMHOLE
    pool_floor = min(0.35, w["minDensity"])   # a calibrated density gate must widen the pool too
    dense = sorted(
        (p for p in (pool if pool is not None else graph.active_points())      # 76.3: a region, or everything
         if p.type not in ("macro", "skill") and p.density > pool_floor
         and p.embedding and len(p.content) >= 40),
        key=lambda p: -p.density,
    )[:30]
    candidates = []
    for a, b in itertools.combinations(dense, 2):
        if graph.edge_between(a.id, b.id):
            continue
        analogy = analogy_heuristic(a, b)
        structural, failed = _wormhole_gates(a, b, analogy, w)
        if structural and not failed:
            candidates.append((analogy, a, b))
        elif structural and len(failed) == 1 and near_misses is not None:
            near_misses[failed[0]] = near_misses.get(failed[0], 0) + 1
    candidates.sort(key=lambda t: -t[0])
    confirmed = []
    for analogy, a, b in candidates[:max_pairs * 2]:
        nano_score = sensitizer.score_pair("analogy", a.content, b.content,
                                          a.timestamp, b.timestamp)
        if nano_score is not None and nano_score < 0.5:
            continue  # nano vetoed the heuristic
        confirmed.append((a, b))
        if len(confirmed) >= max_pairs:
            break
    return confirmed


# --- contradictions (§22 + issue 7) -----------------------------------------------------

def infer_resolution(a: MemoryPoint, b: MemoryPoint) -> dict:
    """Symmetric resolution: newer > confidence gap > explicit source > needs_clarification."""
    order = fu_math.compare_ts(a.timestamp, b.timestamp)   # M-06: real UTC instant comparison
    if order > 0:
        return {"winner": a.id, "loser": b.id, "reason": "newer_memory"}
    if order < 0:
        return {"winner": b.id, "loser": a.id, "reason": "newer_memory"}
    if a.confidence > b.confidence + config.CONTRADICTION_CONFIDENCE_GAP:
        return {"winner": a.id, "loser": b.id, "reason": "higher_confidence"}
    if b.confidence > a.confidence + config.CONTRADICTION_CONFIDENCE_GAP:
        return {"winner": b.id, "loser": a.id, "reason": "higher_confidence"}
    if a.source == "user_explicit" and b.source != "user_explicit":
        return {"winner": a.id, "loser": b.id, "reason": "explicit_user_statement"}
    if b.source == "user_explicit" and a.source != "user_explicit":
        return {"winner": b.id, "loser": a.id, "reason": "explicit_user_statement"}
    return {"winner": None, "loser": None, "reason": "needs_clarification"}


def detect_point_contradictions(point: MemoryPoint, graph: HMGGraph, sensitizer: Sensitizer,
                                use_nano: bool = True) -> List[dict]:
    """Local contradiction scan around ONE point — used at ingest time for user-explicit
    statements so a correction resolves IMMEDIATELY, not at the next dream loop."""
    contradictions = []
    for b, _edge in graph.strong_neighbours(point.id, min_kappa=0.25, depth=2):
        if b.type == "macro":
            continue
        score = fu_math.contradiction_heuristic(point, b)
        if use_nano and 0.35 < score <= config.CONTRADICTION_MIN_SCORE:
            nano = sensitizer.score_pair("contradiction", point.content, b.content,
                                         point.timestamp, b.timestamp)
            if nano is not None:
                score = nano
        if score > config.CONTRADICTION_MIN_SCORE:
            contradictions.append({
                "id": create_id(), "a": point.id, "b": b.id,
                "score": round(score, 3), "resolution": infer_resolution(point, b),
            })
    return contradictions


def detect_contradictions(graph: HMGGraph, sensitizer: Sensitizer,
                          use_nano: bool = True, max_checks: int = 40, pool=None) -> List[dict]:
    contradictions = []
    checked = set()
    for a in (pool if pool is not None else graph.active_points()):
        if len(checked) >= max_checks:   # M-11: budget bounds TRAVERSAL, not just scoring —
            break                        # otherwise strong_neighbours() ran for every point
        if a.type == "macro":
            continue
        for b, edge in graph.strong_neighbours(a.id, min_kappa=0.35, depth=2):
            if len(checked) >= max_checks:
                break
            key = tuple(sorted((a.id, b.id)))
            if key in checked or b.type == "macro":
                continue
            checked.add(key)
            score = fu_math.contradiction_heuristic(a, b)
            if use_nano and 0.35 < score <= config.CONTRADICTION_MIN_SCORE:
                nano = sensitizer.score_pair("contradiction", a.content, b.content,
                                             a.timestamp, b.timestamp)
                if nano is not None:
                    score = nano
            if score > config.CONTRADICTION_MIN_SCORE:
                resolution = infer_resolution(a, b)
                contradictions.append({
                    "id": create_id(), "a": a.id, "b": b.id,
                    "score": round(score, 3), "resolution": resolution,
                })
    return contradictions


def mark_tension(contradiction: dict, graph: HMGGraph, agrees_with: str = "") -> None:
    """Record tension on the edge; supersede the loser only for explicit-user winners (issue 7).
    95.1: a loser carrying `agrees_with` (the value the correction established) is NOT demoted -- the
    correction sentence "B, not A" and a history "was A, now B" agree with B. tests/test_v169_*."""
    a = graph.points.get(contradiction["a"])
    b = graph.points.get(contradiction["b"])
    if a is None or b is None:
        return
    edge = graph.edge_between(a.id, b.id)
    if edge is None:
        n = fu_math.base_separation(hexgrid.hex_distance(a.hex, b.hex))
        edge = FuEdge(
            from_id=a.id, to_id=b.id, relation_type="contradiction", direction="two_way",
            kappa=0.5, omega=fu_math.compute_omega("contradiction"),
            distance=fu_math.fu_distance(0.5, 0.55, a.density, b.density, n),
            base_separation=n, resonance=0.2, trust=0.5,
        )
    edge.tension = max(edge.tension, contradiction["score"])
    edge.relation_type = "contradiction"
    graph.save_edge(edge)
    res = contradiction["resolution"]
    # supersede when the winner is a user-explicit statement — covers BOTH source asymmetry
    # AND a newer explicit statement overriding an older explicit one (bench B2 failure:
    # two user_explicit directives were both injected and the stale one kept winning)
    winner = graph.points.get(res["winner"]) if res.get("winner") else None
    if winner is not None and winner.source == "user_explicit" and res.get("loser"):
        loser = graph.points.get(res["loser"])
        if loser is not None and not (agrees_with and value_in_text(agrees_with, loser.content)):
            loser.status = "superseded"
            graph.save_point(loser)


# --- decay & promotion (§20, §21) ----------------------------------------------------------

def decay_weak_memories(graph: HMGGraph) -> List[str]:
    from .taxonomy import SPECIAL_TYPES
    decayed = []
    for point in graph.all_points():   # H-04: locked snapshot (runs in the dream worker thread)
        if point.status != "active" or point.type in SPECIAL_TYPES:   # specials never decay away
            continue
        decay = fu_math.compute_decay(point)
        if decay <= 0:
            continue
        point.energy = fu_math.clamp(point.energy - decay)
        if fu_math.should_go_dormant(point, graph.centrality(point.id)):
            point.status = "dormant"
            decayed.append(point.id)
        graph.save_point(point)
    return decayed


def promote_stable_memories(graph: HMGGraph) -> List[str]:
    from .taxonomy import layer_cap
    promoted = []
    layers = config.MEMORY_LAYERS
    for point in graph.all_points():   # H-04: locked snapshot
        if point.status != "active":
            continue
        point.stability = fu_math.compute_stability(point)
        if fu_math.should_promote(point):
            # ontological ceiling (Phase 56): episodic content may earn L2 through use but never
            # presents as identity — the promotion gate enforces what the hygiene repair restores.
            nxt = fu_math.next_layer(point.layer)
            if layers.index(nxt) <= layers.index(layer_cap(point)):
                point.layer = nxt
                point.stability = fu_math.clamp(point.stability + 0.15)
                promoted.append(point.id)
        graph.save_point(point)
    return promoted


# --- rebalance -------------------------------------------------------------------------------

def rebalance_hex_grid(graph: HMGGraph, embed: Callable[[str], List[float]],
                       max_moves: int = 10) -> int:
    """Re-place the most drifted points: those far from their strongest neighbour."""
    from .ingest import assign_hex
    moves = 0
    for point in sorted(graph.active_points(), key=lambda p: -p.energy)[:50]:
        neighbours = graph.strong_neighbours(point.id, min_kappa=0.5, depth=1)
        if not neighbours:
            continue
        strongest, _ = max(neighbours, key=lambda t: t[1].kappa)
        if hexgrid.hex_distance(point.hex, strongest.hex) > 6:
            point.hex = assign_hex(point, graph)
            graph.save_point(point)
            moves += 1
            if moves >= max_moves:
                break
    return moves


# --- loops -------------------------------------------------------------------------------------

class DreamBudget:
    """76.3: what one dream may spend. seconds 0 / calls 0 = unlimited (today's behaviour); region_only restricts the
    proposing stages to points touched since the last dream (plus their strong neighbours)."""
    def __init__(self, seconds: float = 0.0, calls: int = 0, region_only: bool = False) -> None:
        self.seconds, self.calls, self.region_only = float(seconds or 0.0), int(calls or 0), bool(region_only)


def dream_region(graph: HMGGraph, since: Optional[str]) -> List[MemoryPoint]:
    """Points written or accessed since `since` (ISO), plus their strong neighbours — the maintenance frontier."""
    if not since:
        return graph.active_points()
    touched = [p for p in graph.active_points() if (p.timestamp or "") >= since or (p.last_accessed_at or "") >= since]
    ids = {p.id for p in touched}
    for p in list(touched):
        for other, _edge in graph.strong_neighbours(p.id, min_kappa=config.EXPANSION_MIN_KAPPA, depth=1):
            if other.id not in ids and other.status == "active":
                ids.add(other.id); touched.append(other)
    return touched


def dream_loop(graph: HMGGraph, sensitizer: Sensitizer,
               embed: Callable[[str], List[float]], calibrator=None,
               budget: Optional["DreamBudget"] = None, since: Optional[str] = None) -> DreamReport:
    """Full nightly reorganisation (THEORY §19). `calibrator` (Phase 56) supplies calibrated
    wormhole gates and learns from this dream's near-miss statistics; None → config baseline.
    76.3: `budget` bounds the run in seconds and model calls and `since` scopes the proposing stages to the
    region touched since the last dream; each stage stops at the budget; the cut is recorded in the summary."""
    import time as _time
    from .taxonomy import SPECIAL_TYPES
    from .turn_timing import call_index
    report = DreamReport()
    budget = budget or DreamBudget()
    t_start, calls0, cut = _time.monotonic(), call_index(), []

    def over(stage: str) -> bool:
        spent_s = _time.monotonic() - t_start
        spent_calls = call_index() - calls0
        if (budget.seconds and spent_s >= budget.seconds) or (budget.calls and spent_calls >= budget.calls):
            cut.append(stage)
            return True
        return False

    pool = dream_region(graph, since) if budget.region_only else graph.active_points()
    # 1. consolidate clusters into macros around energetic points
    seeds = sorted(
        (p for p in pool
         if p.type not in ("macro",) + SPECIAL_TYPES and "_ephemeral" not in p.keywords),
        key=lambda p: -p.energy,
    )[:10]
    seen_macros = set()
    for seed in seeds:
        if over("macros"):
            break
        macro = update_macros(seed, graph, sensitizer, embed)
        if macro is not None and macro.id not in seen_macros:
            seen_macros.add(macro.id)
            report.macros_created.append(macro.id)
    # 1b. recursive consolidation: macros of macros (hierarchy.py, ANALYSIS G1)
    if not over("super_macros"):
        from .hierarchy import build_super_macros
        report.macros_created.extend(build_super_macros(graph, sensitizer, embed))
    # 2. wormholes (gates calibrated from real near-miss evidence when a calibrator is given)
    near_misses = {"minAnalogy": 0, "minSemantic": 0, "minDensity": 0}
    thresholds = calibrator.effective() if calibrator is not None else None
    if not over("wormholes"):
        for a, b in find_distant_analogical_pairs(graph, sensitizer, thresholds=thresholds,
                                                  near_misses=near_misses, pool=pool if budget.region_only else None):
            wormhole = create_wormhole(a, b)
            graph.save_edge(wormhole)
            report.wormholes_created.append(wormhole.id)
    # 3. contradictions — verify dependencies over the region touched, not the whole graph
    if not over("contradictions"):
        for contradiction in detect_contradictions(graph, sensitizer, pool=pool if budget.region_only else None):
            mark_tension(contradiction, graph)
            report.contradictions_found.append(contradiction["id"])
    # 4. decay, 5. promotion — derived-state rebuild, cheap and always run
    report.memories_decayed = decay_weak_memories(graph)
    report.memories_promoted = promote_stable_memories(graph)
    # 6. rebalance
    moves = rebalance_hex_grid(graph, embed) if not over("rebalance") else 0
    # 7. insights (model calls)
    macro_summaries = [graph.points[mid].summary for mid in report.macros_created
                       if mid in graph.points]
    report.insights = [] if over("insights") else sensitizer.dream_insight(graph.stats(), macro_summaries)
    if calibrator is not None:   # self-tuning step + visible trace of WHAT adapted (Rule 10)
        adaptation = calibrator.observe(near_misses, len(report.wormholes_created))
        if adaptation:
            report.insights = list(report.insights) + [adaptation]
    report.summary = (
        f"{len(report.macros_created)} macros, {len(report.wormholes_created)} wormholes, "
        f"{len(report.contradictions_found)} contradictions, "
        f"{len(report.memories_decayed)} decayed, {len(report.memories_promoted)} promoted, "
        f"{moves} rebalanced"
    )
    if budget.seconds or budget.calls or budget.region_only:                   # 76.3: what this dream was allowed
        report.summary += (f" · budget {budget.seconds:.0f}s/{budget.calls} calls, region {len(pool)} pts, "
                           f"{_time.monotonic() - t_start:.1f}s, {call_index() - calls0} calls"
                           + (f", cut at: {', '.join(dict.fromkeys(cut))}" if cut else ""))
    graph.save_dream_report(report)
    log.info("dream loop: %s", report.summary)
    return report


def mini_dream_loop(graph: HMGGraph, sensitizer: Sensitizer) -> DreamReport:
    """Fast between-turns pass (THEORY issue 11): no LLM work."""
    report = DreamReport()
    for contradiction in detect_contradictions(graph, sensitizer, use_nano=False, max_checks=15):
        mark_tension(contradiction, graph)
        report.contradictions_found.append(contradiction["id"])
    report.memories_decayed = decay_weak_memories(graph)
    report.memories_promoted = promote_stable_memories(graph)
    report.summary = (
        f"mini: {len(report.contradictions_found)} contradictions, "
        f"{len(report.memories_decayed)} decayed, {len(report.memories_promoted)} promoted"
    )
    graph.save_dream_report(report)
    return report


def unresolved_tension_count(graph: HMGGraph) -> int:
    return sum(1 for e in graph.edges.values() if e.tension > 0.4 and e.status == "active")
