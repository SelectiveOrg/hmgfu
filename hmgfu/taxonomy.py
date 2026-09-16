"""Canonical node ontology + user-feedback learning loop (Phase 43).

No parallel store (Rule 5): every node is a MemoryPoint in the one graph, keyed by idempotent
keywords. Storage `type` stays the existing set (skill = the whole action surface); the ONTOLOGY
facets (node_class, category) are DERIVED here and exposed to the viz — nothing is duplicated.

Hierarchy (low→high): message/fact → session → micro(L1 macro) → macro(L2+ macro)
                       = specials at the top level (directive · skill/tool).
"""

from __future__ import annotations

import logging
from typing import List, Optional

from . import config, fu_math
from .models import FuEdge, MemoryPoint, now_iso

log = logging.getLogger("hmgfu.taxonomy")

# storage types that are "specials": high importance, survive compression, never decay away
SPECIAL_TYPES = ("directive", "skill", "session", "runbook")   # 75.1: a runbook is procedural, never an episode


def node_class(p: MemoryPoint) -> str:
    """Ontology CLASS of a node (for viz + recall), derived from its storage type + keywords."""
    t = p.type
    if t == "session":
        return "session"
    if t == "reflection":
        return "self"          # self-aware node (the LLM's own reasoning)
    if t == "directive":
        return "directive"
    if t == "macro":
        return "macro" if p.layer in ("L3_identity", "L4_world_model", "L5_deep_pattern") else "micro"
    if t == "skill":
        # built-in tools carry no skill handler; created skills do → the tool/skill split,
        # WITHOUT a risky storage-type change (Rule 3)
        return "skill" if any(k == "skill_created" for k in p.keywords) else "tool"
    if t == "pattern":
        return "skill"         # a learned playbook is a self-made skill
    if t == "runbook":
        return "skill"         # 75.1: a proven step sequence from an executed plan — procedural, surfaced like tools
    if t in ("fact", "concept", "person", "place", "event"):
        return "fact"
    return "message"


def is_user_grounded(p: MemoryPoint) -> bool:
    """Phase 65 precision facet: a recalled item that can legitimately answer a question ABOUT the
    user. Excludes the user's own stored questions, session breath, and content-free assistant
    chatter (no entities, no digits, short). Used by the precision bench and the grader."""
    if "_question" in p.keywords or p.type in ("session", "skill", "directive", "pattern", "runbook"):
        return False
    if p.source in ("user", "user_explicit"):
        return True
    if p.type in ("macro", "fact", "person", "place", "concept", "project", "goal"):
        return True
    if p.source in ("assistant", "system", "dream"):
        # 70.3 (M0.6): an assistant/system/dream line is NEVER user-grounded for the precision metric —
        # entities and length are not grounding; only the user's own words (and typed knowledge) are.
        return False
    return True


def category_of(p: MemoryPoint) -> str:
    """CATEGORY facet: positive / negative / neutral / factual / contradictory."""
    if p.status == "superseded":
        return "contradictory"
    if node_class(p) == "fact":
        return "factual"
    if p.emotional_valence > 0.15:
        return "positive"
    if p.emotional_valence < -0.15:
        return "negative"
    return "neutral"


def _keyed_node(engine, key: str) -> Optional[MemoryPoint]:
    for p in engine.graph.all_points():
        if key in p.keywords:
            return p
    return None


def upsert_session_node(engine, sid: str, user_point) -> MemoryPoint:
    """ONE session node per session (type=session, L1_session): the rolling breath of the
    conversation. Linked part_of to each turn's user point. A special → survives compression."""
    key = f"session:{sid}"
    line = (user_point.summary or user_point.content[:90]).strip()
    node = _keyed_node(engine, key)
    if node is None:
        node = MemoryPoint(type="session", title=f"Session {sid[:8]}", content=line, summary=line,
                           source="system", keywords=[key], layer="L1_session",
                           importance=0.7, confidence=0.8, utility=0.6, stability=0.85,
                           embedding=(list(user_point.embedding) if line == user_point.content.strip()
                                      and user_point.embedding else engine.embed(line)))   # 73.2: same text → same vector
        from .ingest import assign_hex
        node.hex = assign_hex(node, engine.graph)
    else:
        node.content = (node.content + "\n" + line)[-1200:]
        node.summary = node.content.split("\n")[-1][:200]
        node.embedding = engine.embed(node.content[-400:])
        node.last_accessed_at = now_iso()
    node.density = fu_math.compute_density(node, engine.graph.centrality(node.id))
    engine.graph.save_point(node)
    if engine.graph.edge_between(node.id, user_point.id) is None:
        engine.graph.save_edge(FuEdge(from_id=user_point.id, to_id=node.id, relation_type="part_of",
                                      direction="two_way", kappa=0.55,
                                      omega=fu_math.compute_omega("part_of"), distance=1.0,
                                      base_separation=1.0, resonance=0.5, tension=0.0, trust=0.8))
    return node


def store_reflection(engine, thoughts: List[str], user_point) -> Optional[MemoryPoint]:
    """Self-aware node (type=reflection): the LLM's own reasoning, recalled when THINKING.
    Anti-poisoning (Phase 27): source=assistant (0.85 score factor) + never a fact, so it cannot
    outrank user facts on ordinary questions."""
    text = "\n".join(t for t in thoughts if t).strip()
    if len(text) < 80:
        return None
    point = engine.ingest(text[:1500], source="assistant", mtype="reflection")
    if engine.graph.edge_between(point.id, user_point.id) is None:
        engine.graph.save_edge(FuEdge(from_id=point.id, to_id=user_point.id, relation_type="memory_of",
                                      direction="two_way", kappa=0.5,
                                      omega=fu_math.compute_omega("memory_of"), distance=1.0,
                                      base_separation=1.0, resonance=0.5, tension=0.0, trust=0.6))
    return point


def mirror_directive_nodes(engine) -> int:
    """Project DirectiveStore rows into DIRECTIVE graph nodes (compression/decay-immune, top
    importance). The store stays the enforcement source of truth (Rule 11); the node is the
    recall/viz/edge projection — same pattern as sync_tool_points. Facts are NOT mirrored: they
    already exist as fact-type nodes (no triple)."""
    changed = 0
    active_kinds = set()
    for d in engine.directives.active():
        active_kinds.add(d["kind"])
        ckey = f"directive:{d['kind']}"
        text = f"{d['kind'].replace('_', ' ')}: {d['value']}"
        node = _keyed_node(engine, ckey)
        if node is not None and d["value"].lower() in node.content.lower():
            continue
        if node is None:
            node = MemoryPoint(type="directive", title=text[:60], keywords=[ckey],
                               layer="L5_deep_pattern", source="user_explicit")
            from .ingest import assign_hex
            node.hex = assign_hex(node, engine.graph)
        node.content = node.summary = text
        node.embedding = engine.embed(text)
        node.importance, node.confidence, node.stability, node.utility = 0.95, 0.95, 1.0, 0.9
        node.density = fu_math.compute_density(node, engine.graph.centrality(node.id))
        engine.graph.save_point(node)
        changed += 1
    # prune projections whose directive was CLEARED — the store DELETEs a cleared directive, but the
    # node is decay-immune, so without this it lingers in the viz/recall as a directive not in force
    # (Phase 55 lifecycle: CLEAR must remove it everywhere, not only from enforcement).
    for p in engine.graph.all_points():
        if p.type != "directive":
            continue
        key = next((k for k in p.keywords if k.startswith("directive:")), "")
        kind = key.split("directive:", 1)[1] if key else ""
        if kind and kind not in active_kinds:
            engine.graph.delete_point(p.id)
            changed += 1
    return changed


# --- layer stratification ontology (Phase 56 gap 4) ---------------------------------------
# THE single source of truth for "which layer does this content belong in". The audit found
# 1152/1539 points in L3_identity (PA3 importer mapped whole kinds to identity; Phase 48
# re-TYPED assistant facts without re-LAYERING), so the injector's "User identity" section and
# the dense-identity retrieval channel fired on episodic chatter.

def episodic_repair_layer(p) -> Optional[str]:
    """Home layer for content that does NOT belong in the identity layers (None = belongs).
    Used by hygiene (demote existing pollution) and as the basis of layer_cap (stop new
    pollution at the promotion gate) — one predicate, two enforcement points."""
    if p.type in ("directive", "session", "skill", "macro"):
        return None                     # control-plane / hierarchy-owned, layered by their owners
    if p.type == "pattern":
        return "L2_project"             # procedural home (grader playbooks, retyped procedures)
    if p.type == "message" or "_question" in p.keywords:
        return "L1_session"             # an utterance/question is an episode, never identity itself
    if p.type in ("decision", "event", "reflection") and p.source != "user_explicit":
        return "L1_session"
    if p.type in ("fact", "person", "place", "concept") and p.source in ("assistant", "dream"):
        return "L1_session"             # assistants don't author identity (Phase 48 doctrine)
    return None


def layer_cap(p) -> str:
    """Ontological ceiling for ORGANIC promotion: episodic/procedural content may earn up to
    the project layer through use, but never presents as identity/world-model."""
    if episodic_repair_layer(p) is None:
        return config.MEMORY_LAYERS[-1]
    return "L2_project"


# --- user-feedback learning loop: the ONE place tool utility is graded (Rule 5) -----------
# Penalties come from the USER, never self (user mandate). _reinforce_used_tools only wires
# edges + access; the nano grader no longer touches tool utility.
# Phase 56: the PRIMARY signal is the router's SEMANTIC feedback_polarity (any language). The
# lexical cue lists below are the OFFLINE fallback only (models off / tests) — never the main
# path, per the no-static-lexical doctrine.
_POS = ("thanks", "thank you", "perfect", "great", "works", "worked", "awesome", "nice", "good job",
        "obrigado", "boa", "funcionou", "perfeito", "excelente")
_NEG = ("not work", "doesn't work", "didn't work", "does not work", "still wrong", "still broken",
        "wrong", "failed", "broken", "useless", "not what", "não funcion", "errado", "falhou")


def classify_feedback(text: str, query=None) -> Optional[bool]:
    """True/False/None. Router polarity (semantic, multilingual) decides when present; the
    lexical scan only backstops turns routed WITHOUT a model (offline fallback extractor)."""
    if query is not None and getattr(query, "feedback_polarity", ""):
        return query.feedback_polarity == "positive"
    if query is not None and getattr(query, "extractor", "fallback") != "fallback":
        # a model DID route this turn and saw no feedback reaction — trust it; a lexical
        # override here would resurrect exactly the static-keyword behaviour we removed
        return None
    low = text.lower()
    if any(c in low for c in _NEG):
        return False
    if any(c in low for c in _POS):
        return True
    return None


def apply_user_feedback(engine, sid: str, user_message: str, query=None) -> Optional[dict]:
    """Grade the PREVIOUS turn's tools by what the user just said. Positive → reward; negative →
    penalize. Efficiency (user mandate): the reward per tool is DIVIDED by how many tools that
    turn used, so a result reached with fewer tools reinforces each tool more — shorter learned
    loops win."""
    last = getattr(engine, "_last_turn_tools", {}).get(sid)
    verdict = classify_feedback(user_message, query=query)
    if not last or verdict is None:
        return None
    target = 0.95 if verdict else 0.1
    # fewer tools → stronger per-tool reinforcement (efficiency-weighted)
    gain = 0.35 / max(1, len(last)) if verdict else 0.35
    graded = []
    for name in set(last):
        point = engine._tool_point(name)
        if point is None:
            continue
        before = point.utility
        point.utility = fu_math.clamp((1 - gain) * point.utility + gain * target)
        engine.graph.save_point(point)
        graded.append({"tool": name, "before": round(before, 3), "after": round(point.utility, 3)})
    if graded:
        log.info("user-feedback grading (%s, %d tools): %s",
                 "positive" if verdict else "negative", len(last), graded)
    return {"verdict": verdict, "tool_count": len(last), "tools": graded} if graded else None


def remember_turn_tools(engine, sid: str, tool_trace: List[dict]) -> None:
    """Record this turn's successful tools so the NEXT user message can grade them."""
    if not hasattr(engine, "_last_turn_tools"):
        engine._last_turn_tools = {}
    used = [t["name"] for t in tool_trace if not t.get("failed") and not t.get("blocked")]
    if used:
        engine._last_turn_tools[sid] = used
    else:
        engine._last_turn_tools.pop(sid, None)
