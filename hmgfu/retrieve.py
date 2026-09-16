"""Retrieval Ψ (THEORY §15, §16, §23, §30): six channels → score → Fu expansion → injection.

Retrieval is pure local math over the in-memory graph — no LLM call — which is what makes it
deterministic and milliseconds-scale (Vision doc requirement).
"""

from __future__ import annotations

import logging
import re
from typing import Callable, List, Optional

from . import config, fu_math
from .context_render import _SECTION_ORDER, excerpt_for_query, is_echo, render_injection  # noqa: F401 (re-exports; 78.2)
from .models import MemoryPoint, QueryPoint, RetrievedMemory
from .retrieve_channels import (dense_candidates as _dense_candidates, entity_candidates as _entity_candidates,
                                goal_candidates as _goal_candidates, recent_candidates as _recent_candidates,
                                semantic_candidates as _semantic_candidates, wormhole_candidates as _wormhole_candidates)
from .sensitizer import Sensitizer
from .store import HMGGraph

log = logging.getLogger("hmgfu.retrieve")

# P2 history-cue guard (regression fix 2026-07-20): the router's `freshness` field over-fires
# `historical` on plain present-tense queries (it was decorative until P2 made it load-bearing),
# so the timeline SUPPLEMENT fires only when the router AND the text agree there's a real
# past-reference — belt-and-suspenders, so a router false-positive never blinds normal recall.
_HISTORY_CUE = re.compile(
    r"\b(before|previously|used to|back then|earlier|no longer|antes|anteriormente|"
    r"what was|qual era|como era|when did i|quando (?:e que )?(?:mudei|disse|falei|era)|"
    r"how long have|h[aá] quanto tempo|desde quando|first time|primeira vez|"
    r"history of|hist[oó]rico|used to be|costumava)\b", re.IGNORECASE)

def is_low_information_query(query: QueryPoint) -> bool:
    """Language-neutral gate populated by the nano conversation-act classifier."""
    return query.conversation_act == "greeting" and not query.action_requested


def make_query_point(text: str, embed: Callable[[str], List[float]],
                     sensitizer: Sensitizer, runtime_context=None, nano: bool = True) -> QueryPoint:
    import contextvars
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="embed") as ex:     # 73.2(a″): embed || extract+route
        emb_future = ex.submit(contextvars.copy_context().run, embed, text)
        extracted = (sensitizer.extract(text, runtime_context=runtime_context, route=True, nano=False) if not nano
                     else sensitizer.extract(text, runtime_context=runtime_context, route=True))   # 80.2; default call unchanged (Rule 11: stubs)
        embedding = emb_future.result()
    return QueryPoint(
        text=text,
        embedding=embedding,
        entities=extracted["entities"],
        topics=extracted["topics"],
        intent=extracted["intent"],
        conversation_act=extracted.get("conversation_act", "statement"),
        feedback_polarity=extracted.get("feedback_polarity", ""),
        action_requested=bool(extracted.get("action_requested", False)),
        requested_tools=list(extracted.get("requested_tools", [])),
        freshness=extracted.get("freshness", "none"),
        needs_memory=bool(extracted.get("needs_memory", True)),
        runtime_context_keys=list(extracted.get("runtime_context_keys", [])),
        runtime_context_sufficient=bool(extracted.get("runtime_context_sufficient", False)),
        directive=extracted.get("directive"),
        extractor=extracted.get("extractor", "fallback"),
        extraction=dict(extracted),                     # 73.2: ingest reuses it — one extraction per message
    )


COSINE_POOL_EXCLUDED = ("skill", "session", "directive", "pattern", "runbook")   # 77.1: the B2 control's pool


def retrieve_cosine(query: QueryPoint, graph: HMGGraph, limit: int, min_score: float) -> List[RetrievedMemory]:
    """77.1: `retrieval_mode = cosine` — the strong control of Phase 74 (B2) as product: vector top-k by similarity over
    the episodic pool, the relevance floor on similarity, no channels / composite score / expansion. The context policy
    downstream (ledger, history on past cues, provenance exclusion, echo-free) is the same for both modes."""
    from . import vecindex
    if is_low_information_query(query) or not query.embedding:
        return []
    pool = [p for p in graph.active_points() if p.type not in COSINE_POOL_EXCLUDED and "_question" not in p.keywords]
    top = vecindex.top_k(query.embedding, pool, limit, graph=graph)
    sims = vecindex.scores(query.embedding, top, graph=graph)
    return [RetrievedMemory(point=p, edge=None, score=s, reason=f"cosine, score={s:.2f}")
            for p, s in zip(top, sims) if s >= min_score]


def retrieve_memory(query: QueryPoint, graph: HMGGraph,
                    limit: int = config.RETRIEVAL_LIMIT,
                    min_score: float = config.RETRIEVAL_MIN_SCORE,
                    expansion_depth: int = config.EXPANSION_DEPTH,
                    weights: Optional[dict] = None, mode: str = "fu") -> List[RetrievedMemory]:
    """`mode` (77.1): `fu` = channels + composite score + Fu expansion (the experimental package); `cosine` = the B2
    control as product. Same pool, same floor semantics, same context policy downstream."""
    from .taxonomy import node_class
    if mode == "cosine":
        return retrieve_cosine(query, graph, limit, min_score)
    if is_low_information_query(query):
        return []
    # Recall is EPISODIC/SEMANTIC memory only (Phase 48). Procedural + control nodes — tools,
    # learned skills/playbooks (type pattern), directives, session-breath — are surfaced by
    # their OWN mechanisms (retrieve_tools_for_turn, directives.render_block, session linkage)
    # and must not compete in the memory panel. Uses the canonical ontology facet, not a
    # type/string blocklist; keeps fact/message/macro/micro/self (reflections) recallable.
    points = [p for p in graph.active_points()
              if node_class(p) not in ("skill", "tool", "directive", "session")
              and "_question" not in p.keywords]          # 65.3: a user's question is never an answer
    if not points:
        return []
    # P2 timeline reader ("a linha") — route to the dated chain ONLY on a deterministic past-reference
    # CUE in the text, NOT the router's `freshness` field: that field over-fires `historical` on plain
    # present-tense queries (decorative until P2 made it load-bearing), which was HIJACKING normal
    # recall for ~80% of queries (regression 2026-07-20, Rule 13 — the unreliable layer is the router,
    # so don't route on it). A genuine "what was X before" gets the full chain; everything else recalls.
    if query.freshness == "historical" and _HISTORY_CUE.search(query.text or ""):
        return _history_memories(query, graph, limit)
    ch = config.RETRIEVAL_CHANNELS
    semantic = _semantic_candidates(query, points, ch["semantic"], graph=graph)   # 76.2: vector scan
    channels = [
        ("semantic", semantic),
        ("entity", _entity_candidates(query, points, ch["entity"])),
        ("goal", _goal_candidates(points, ch["goal"])),
        ("recent", _recent_candidates(points, ch["recent"])),
        ("dense_identity", _dense_candidates(points, ch["dense"])),
        ("wormhole", _wormhole_candidates(query, graph, semantic, ch["wormhole"])),
    ]
    origin: dict = {}
    for name, members in channels:
        for p in members:
            origin.setdefault(p.id, (name, p))

    scored: List[RetrievedMemory] = []
    for channel, p in origin.values():
        # echo filter: the user's own (near-)identical utterance is not an answer (PA3 r41)
        # Echo suppression applies only to a user's stored utterance/question. Exact-value
        # facts (codewords, IDs, names) are often near-identical to the query and are answers.
        is_user_echo = p.source in ("user", "user_explicit") and p.type in ("message", "task")
        if is_user_echo and fu_math.cosine(query.embedding, p.embedding) >= config.ECHO_FILTER_MIN_COSINE:
            continue
        edge, path_rel = _best_edge_toward(p, origin, graph, query)
        score = fu_math.memory_score(query, p, edge, weights=weights, path_relevance=path_rel)
        scored.append(RetrievedMemory(
            point=p, edge=edge, score=score, path_relevance=path_rel,
            reason=f"channel={channel}, score={score:.2f}"
                   + (f", via {edge.relation_type}" if edge else ""),
        ))
    # 74.5: `min_score` is a RELEVANCE floor, not a floor on the composite Fu score. Two production findings said so:
    # re-balanced weights (73.3) and the relational bench (gold items with cosine 0.47–0.69 scored 0.20–0.36 composite
    # and were cut while plain cosine kept them). Semantic candidates pass when their similarity clears the floor;
    # candidates that arrived through a relational channel (entity, wormhole, goal, dense, recent) are what Fu is for
    # and are kept on their channel's own criterion. Ranking stays the composite memory_score.
    def _relevant(r: RetrievedMemory) -> bool:
        if not r.reason.startswith("channel=semantic"):
            return r.score >= min_score * 0.5             # relational finds keep a low floor against pure noise
        return fu_math.cosine(query.embedding, r.point.embedding) >= min_score or r.score >= min_score
    top = sorted([r for r in scored if _relevant(r)], key=lambda r: -r.score)[:limit]
    return expand_through_fu(top, graph, expansion_depth, query, limit=limit)


def _history_memories(query: QueryPoint, graph: HMGGraph, limit: int) -> List[RetrievedMemory]:
    """P2 timeline reader ("a linha", Plan.txt): a freshness=historical query walks the subject's
    whole line — ACTIVE and SUPERSEDED points alike (E.2-A: supersession is annotation, never
    deletion of history) — chronologically, each entry dated. No new storage: the chain IS the
    points + status + dates. No echo filter — the user's own past statements ARE the answer here."""
    from .taxonomy import node_class
    # 72.6g: the line is the USER's own statements — an assistant echo ("you lived in Chimoio") is not history and,
    # left in, re-teaches itself on the next history question (live replay echo loop).
    pool = [p for p in graph.all_points() if p.status in ("active", "superseded")
            and p.source in ("user", "user_explicit") and "_question" not in p.keywords
            and node_class(p) not in ("skill", "tool", "directive", "session")]
    ranked = sorted(pool, key=lambda p: -fu_math.cosine(query.embedding, p.embedding))[:limit]
    ranked.sort(key=lambda p: p.timestamp)                      # oldest → newest: the line, never cut
    return [RetrievedMemory(point=p, edge=None, score=1.0, reason=f"history[{p.status}]")
            for p in ranked]


def _best_edge_toward(p: MemoryPoint, origin: dict, graph: HMGGraph, query: Optional[QueryPoint] = None):
    """Strongest active edge linking p to another candidate — the 'path' explanation — measured as κ ALONG THE PATH
    query → other → p (74.7): edge.κ × the other endpoint's relevance to the query. Returns (edge, path_relevance);
    (None, 1.0) when no candidate edge exists. Without a query the legacy rule (raw κ) applies."""
    best, best_rel, best_path = None, 1.0, -1.0
    for e in graph.get_edges(p.id):
        if e.status != "active":
            continue
        other_id = e.to_id if e.from_id == p.id else e.from_id
        hit = origin.get(other_id)
        if hit is None:
            continue
        rel = fu_math.relevance_gate(query, hit[1]) if query is not None else 1.0
        if e.kappa * rel > best_path:
            best, best_rel, best_path = e, rel, e.kappa * rel
    return best, best_rel


def expand_through_fu(retrieved: List[RetrievedMemory], graph: HMGGraph,
                      depth: int, query: QueryPoint, limit: Optional[int] = None) -> List[RetrievedMemory]:
    """THEORY §16 — pull in strong neighbours of the winners."""
    from .taxonomy import node_class
    result = {r.point.id: r for r in retrieved}
    for item in list(retrieved):
        neighbours = graph.strong_neighbours(
            item.point.id,
            min_kappa=config.EXPANSION_MIN_KAPPA,
            min_trust=config.EXPANSION_MIN_TRUST,
            max_distance=config.EXPANSION_MAX_DISTANCE,
            depth=depth,
        )
        for point, edge in neighbours:
            # Expansion is ordinary episodic/semantic recall, so enforce the same
            # ontology boundary as the seed channels. A strong edge must not silently
            # reintroduce tools, skills, directives, or rolling session nodes.
            if node_class(point) in ("skill", "tool", "directive", "session"):
                continue
            expansion_score = item.score * edge.kappa * edge.trust
            if expansion_score < config.EXPANSION_MIN_SCORE or point.id in result:
                continue
            result[point.id] = RetrievedMemory(
                point=point, edge=edge, score=expansion_score,
                reason=f"expanded from '{item.point.title[:30]}' via {edge.relation_type} "
                       f"(κ={edge.kappa:.2f})",
            )
    ranked = sorted(result.values(), key=lambda r: -r.score)
    return ranked[:limit] if limit is not None else ranked


# --- injection (§23 + issue 12) ------------------------------------------------------



def user_fact_question(query: QueryPoint, facts) -> bool:
    """73.3 (M6): is this a QUESTION about a canonical attribute the ledger holds for the user ("what is my name?",
    "qual é a minha cor favorita?")? Decided by the closed slot vocabulary (`slots.mentions_attribute`), no phrase list."""
    if getattr(query, "conversation_act", "") != "question" or facts is None:
        return False
    from .slots import mentions_attribute
    try:
        keys = {f["key"] for f in facts.active() if f.get("slot")}
    except Exception:
        return False
    return any(mentions_attribute(k, query.text or "") for k in keys)


def organise_for_injection(retrieved: List[RetrievedMemory], graph: HMGGraph,
                           canonical: Optional[List[str]] = None,
                           superseded: Optional[List[tuple]] = None,
                           regulator=None, reverted: Optional[List[tuple]] = None,
                           echo_free: bool = False, query: Optional[QueryPoint] = None,
                           excerpt_chars: Optional[int] = None, echo_scope: str = "all",
                           echo_pairs: Optional[List[tuple]] = None) -> dict:
    """78.2/78.3: `query` + `excerpt_chars` → each memory renders its query-matched sentence window (None → today's head cut);
    `echo_scope` 'echoes' → on a user-fact question only assistant memories that RESTATE a ledger value of the asked attribute
    (`echo_pairs` = (key, value) of the active ledger) are dropped; 'all' → every assistant/dream memory (today)."""
    # A recalled memory that still carries a SUPERSEDED canonical value (an old name in a
    # correction narration) must not seed the ANSWER — the model parrots it (bench L4). It stays
    # in the graph; it's just excluded from answer context, exactly like an ephemeral. Guard on
    # length so a short old value can't nuke unrelated memories.
    # 74.3: exclusion is ATTRIBUTE-GATED (as supersede_stale_nodes has been since 69.4): a memory is dropped for a stale
    # value only when it also talks about that attribute — "Echo" the project is not a superseded mother's name.
    stale_pairs = [(k, s.lower()) for k, s in (superseded or []) if s and len(s) >= 4]
    reverted_pairs = [(k, s.lower()) for k, s in (reverted or []) if s and len(s) >= 4]   # 72.6g: never true, not history
    from .slots import mentions_attribute, value_in_text

    def _carries(pairs, blob: str) -> bool:
        return any(value_in_text(v, blob) and mentions_attribute(k, blob) for k, v in pairs)
    injection = {key: [] for key, _ in _SECTION_ORDER}
    # canonical facts (literal value, keyed, supersede-aware) go FIRST — verbatim, never the
    # lossy nano summary that dropped the actual value (the "Teodoro/Sebastian" failure)
    for line in (canonical or []):
        injection["userIdentity"].append(f"{line}  (confirmed)")
    # newest memories first WITHIN each section so conflicting facts read new→old and the
    # model trusts the most recent (the "Sebastian → Teo" case)
    ordered = sorted(retrieved, key=lambda r: r.point.timestamp, reverse=True)
    if echo_free:      # 73.3 (M6): a question about the user's own attributes is answered from the user's own words
        if echo_scope == "echoes":                                             # 78.3: drop the RESTATEMENTS, keep new information
            ordered = [r for r in ordered if r.point.source not in ("assistant", "dream") or r.reason.startswith("history")
                       or not is_echo(r.point, query.text if query is not None else "", echo_pairs or [])]
        else:
            ordered = [r for r in ordered if r.point.source not in ("assistant", "dream") or r.reason.startswith("history")]
    injection["_kept_ids"] = [r.point.id for r in ordered]                  # 78.4: what the echo guard left (for the truth bench's precision)
    ephemeral_present = False
    for item in ordered:
        p = item.point
        # P2: timeline entries render dated + chronological in their OWN section, and BYPASS the
        # stale-value filter — a superseded value is exactly what a history question asks about.
        if item.reason.startswith("history"):
            if reverted_pairs and _carries(reverted_pairs, f"{p.summary} {p.title} {p.content}"):
                continue                 # 72.6g: a value UNDONE by a rollback was never true — not even as history
            if excerpt_chars and query is not None and p.content:                # 85.2: the window the question is about —
                entry = excerpt_for_query(p.content, query.text or "", excerpt_chars)   # the 160-char head lost 4 golds (85.1)
            else:
                entry = p.summary or p.title or p.content[:160]
            injection["subjectTimeline"].append(
                f"[{(p.timestamp or '')[:10]}]{' [superseded]' if p.status == 'superseded' else ''} {entry}")
            continue
        # Phase 49: time-sensitive observations (weather/prices/status) are NEVER injected as
        # answerable context — even a fresh one is unreliable as "the current value", and the
        # model would parrot it instead of fetching live. They still appear in the recall panel.
        if "_ephemeral" in p.keywords:
            ephemeral_present = True
            continue
        if stale_pairs or reverted_pairs:
            blob = f"{p.summary} {p.title} {p.content}"
            if _carries(stale_pairs, blob) or _carries(reverted_pairs, blob):
                continue                 # carries a superseded/reverted value OF THIS ATTRIBUTE → excluded from the answer
        # 65.4 provenance at render: the user's own words are the evidence — never the nano's rewrite
        # ("A new era of innovation is about to begin" for "start calling me Trailblazer")
        if excerpt_chars and query is not None and p.content:                # 78.2: the span the question is about, not the head
            text = excerpt_for_query(p.content, query.text or "", excerpt_chars)
        else:
            text = (p.content.strip()[:200] if p.source in ("user", "user_explicit") and p.content
                    else (p.summary or p.title or p.content[:160]))
        line = f"{text}  ({fu_math.age_label(p.timestamp)})"   # temporal tag on every hex
        # Phase 61a state-pill (DISPLAY-ONLY, Invariant A1): show the Regulator's derived lifecycle
        # state. Appended to the rendered TEXT only, AFTER ranking is closed — it re-enters NO
        # scoring path (the 19 scoring sites read MemoryPoint fields/embeddings, never this string).
        # Passed non-None only on the live agent path when config.REGULATOR_ENABLED (else absent).
        if regulator is not None:
            line += f"  [{regulator.evaluate(p.id)[1].upper()}]"
        derived = p.source in ("assistant", "dream") or p.type == "macro"    # 92.E2: a macro is a
        if derived:               # CONSOLIDATION: it may say WHERE to look, it may not stand in as proof
            injection["assistantSaid"].append(f"[pattern] {line}" if p.type == "macro" else line)
        elif "_intent" in p.keywords:      # 90.N: a proposal/wish/plan is DELIVERED, under a heading that says so
            injection["proposals"].append(line)
        elif p.layer in ("L3_identity", "L4_world_model", "L5_deep_pattern")                 and "_question" not in p.keywords:
            injection["userIdentity"].append(line)
        elif p.type in ("goal", "project", "task"):
            injection["activeProjects"].append(line)
        elif p.type == "macro":
            injection["relevantFacts"].append(f"[pattern] {line}")
        elif fu_math.recency_score(p.timestamp) > 0.8:
            injection["recentContext"].append(line)
        else:
            injection["relevantFacts"].append(line)
        if item.edge is not None and item.edge.tension > 0.4:
            other_id = item.edge.to_id if item.edge.from_id == p.id else item.edge.from_id
            other = graph.points.get(other_id)
            if other is not None:
                injection["contradictions"].append(
                    f"'{text}' may conflict with '{other.summary or other.title}'"
                )
    injection["subjectTimeline"].sort()      # lines start [YYYY-MM-DD] → lexicographic = chronological
    injection["_ephemeral"] = ephemeral_present
    return injection


def build_llm_context(query: QueryPoint, graph: HMGGraph,
                      token_budget: int = config.TOKEN_BUDGET,
                      retrieved: Optional[List[RetrievedMemory]] = None,
                      canonical: Optional[List[str]] = None,
                      superseded: Optional[List[tuple]] = None,
                      regulator=None, reverted: Optional[List[tuple]] = None,
                      echo_free: bool = False, excerpt_chars: Optional[int] = None,
                      echo_scope: str = "all", echo_pairs: Optional[List[tuple]] = None) -> tuple:
    """Returns (context_text, retrieved) — retrieved carries the explainability trace.
    `echo_free` (73.3) = drop assistant/dream-authored memories from the ANSWER context (user-fact questions).
    `canonical` = verbatim first-class fact lines (facts.FactStore.render_lines);
    `superseded` = (key, old_value) pairs whose old value is excluded from the answer context;
    `reverted` = (key, value) pairs undone by a rollback — excluded even from the history timeline (72.6g).
    `regulator` = Phase 61a; when non-None each memory line gets a DISPLAY-ONLY lifecycle pill (A1)."""
    if retrieved is None:
        retrieved = retrieve_memory(query, graph)
    injection = organise_for_injection(retrieved, graph, canonical=canonical, superseded=superseded,
                                       regulator=regulator, reverted=reverted, echo_free=echo_free, query=query,
                                       excerpt_chars=excerpt_chars, echo_scope=echo_scope, echo_pairs=echo_pairs)   # 78.2/78.3
    return render_injection(injection, token_budget), retrieved
