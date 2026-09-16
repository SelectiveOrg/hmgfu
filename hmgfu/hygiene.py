"""Retroactive memory hygiene (Phase 28): clean EXISTING graph data.

Phase-27 correctness fixes (dedup, assistant-never-fact, fact supersession) protect NEW
ingests only — a live graph built before them still carries the pollution the user saw
("Your name is Sebastian" ×4, assistant-authored weather 'facts'). This pass applies the
same rules retroactively. It runs inside the dream loop, is exposed at
POST /api/memory/hygiene, and every action is a demotion/reclassification — nothing is
deleted (Rule 14 / THEORY: dormant-not-deleted).
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List

from . import config, fu_math

log = logging.getLogger("hmgfu.hygiene")

# ephemeral observation classes: true "now" statements that must not act as durable facts
_EPHEMERAL_RE = re.compile(
    r"(current(ly)?\s+weather|weather\s+(in|is|now)|°c\b|°f\b|km/h|wind speed|humidity|"
    r"forecast|right now it is|current time|current price|stock price|exchange rate)",
    re.IGNORECASE)

_JUNK_RE = re.compile(
    r"(current location|currently living in your current|will share their name|"
    r"is here to assist)", re.IGNORECASE)


def is_ephemeral(content: str) -> bool:
    return bool(_EPHEMERAL_RE.search(content or ""))


def apply_ephemeral_meta(point) -> None:
    """The ONE gate every node-creation path funnels through (Phase 48): a node whose CONTENT
    is an ephemeral observation (weather-now, prices, time) gets the decay keyword + a utility
    cap, so retrieval's hours-scale decay (fu_math.memory_score) applies no matter which path
    (ingest / macro / playbook) built it. Idempotent."""
    if is_ephemeral(point.content) and "_ephemeral" not in point.keywords:
        point.keywords = list(point.keywords) + ["_ephemeral"]
        point.utility = min(point.utility, 0.3)


# PA3-imported procedures were stored as declarative FACT nodes bodied "Procedure for: <task> |
# Tools: <chain>" (import_pa3 mtype defaulted to 'fact'). They are PROCEDURAL knowledge, not
# facts — retype to 'pattern' so node_class()→'skill' and they leave the memory-recall pool
# (Phase 48 Fix 3), joining the fresh grader playbooks. Format-keyed = a one-time legacy
# migration (Rule 11), not a hot-path string rule.
_LEGACY_PROC_RE = re.compile(r"^\s*procedure for:", re.IGNORECASE)


def retype_legacy_procedures(graph) -> int:
    """Reclassify legacy PA3 'Procedure for:' fact nodes → pattern (procedural, not canon)."""
    changed = 0
    for p in graph.all_points():   # H-04: locked snapshot
        if p.status == "active" and p.type == "fact" and _LEGACY_PROC_RE.search(p.content or ""):
            p.type = "pattern"
            graph.save_point(p)
            changed += 1
    return changed


def reclassify_legacy_derived(graph) -> int:
    """PA3 hmg_nodes were generated/curated records, not literal user authorship.

    The original importer assigned all of them source=user, giving assistant summaries the
    same authority as direct statements. Gold PA3 fact rows have separate pa3:facts keys.
    """
    changed = 0
    for p in graph.all_points():
        if p.source != "user" or not any(k.startswith("pa3:nodes:") for k in p.keywords):
            continue
        p.source = "assistant"
        if p.type in ("fact", "person", "concept", "event"):
            p.type = "message"
            p.importance = min(p.importance, 0.4)
        if "_legacy_derived" not in p.keywords:
            p.keywords = list(p.keywords) + ["_legacy_derived"]
        graph.save_point(p)
        changed += 1
    return changed


def supersede_canonical_conflicts(engine) -> int:
    """Retire active episodic identity assertions that conflict with canonical facts."""
    current = {f["key"]: f["value"] for f in engine.facts.active()}
    current_name = (current.get("identity.name") or current.get("name") or "").strip().lower()
    if not current_name:
        return 0
    changed = 0
    claim_re = re.compile(r"\b(?:your|my) name is\s+([^\n.!?,;]{2,80})|\buser:name:\s*([^\n,;]{2,80})",
                          re.IGNORECASE)
    for p in engine.graph.all_points():
        if p.status != "active" or p.type in ("skill", "macro", "directive", "session"):
            continue
        text = f"{p.title}\n{p.summary}\n{p.content}"
        placeholder = "[your name]" in text.lower()
        matches = [next((g for g in m.groups() if g), "").strip().lower()
                   for m in claim_re.finditer(text)]
        incompatible = [claim for claim in matches
                        if current_name not in claim and claim not in current_name]
        if placeholder or (matches and len(incompatible) == len(matches)):
            p.status = "superseded"
            engine.graph.save_point(p)
            changed += 1
    return changed


_HIGH_LAYERS = ("L3_identity", "L4_world_model", "L5_deep_pattern")


def repair_layer_stratification(graph) -> int:
    """Phase 56 gap 4: demote episodic/procedural content OUT of the identity layers back to its
    ontological home (taxonomy.episodic_repair_layer — the one predicate). Demotion-only, all
    canonical user/system facts and control-plane nodes untouched; organic promotion can re-earn
    up to taxonomy.layer_cap(). Idempotent."""
    from .taxonomy import episodic_repair_layer
    changed = 0
    for p in graph.all_points():   # H-04: locked snapshot
        if p.layer not in _HIGH_LAYERS:
            continue
        target = episodic_repair_layer(p)
        if target and target != p.layer:
            p.layer = target
            graph.save_point(p)
            changed += 1
    return changed


def retype_stored_questions(graph) -> int:
    """Phase 62 write-gate applied retroactively: a stored user/system QUESTION typed as a fact/
    person/... becomes an episodic message tagged `_question` (never identity, never canon)."""
    from .speech_act import is_interrogative
    changed = 0
    for p in graph.all_points():
        if p.status != "active" or p.source not in ("user", "user_explicit", "system"):
            continue
        if p.type in ("skill", "directive", "macro", "pattern") or not is_interrogative(p.content):
            continue
        if ("_question" not in p.keywords or p.layer != "L1_session"
                or p.type in ("fact", "person", "place", "concept", "event", "decision")):   # idempotent
            if p.type in ("fact", "person", "place", "concept", "event", "decision"):
                p.type = "message"
            if "_question" not in p.keywords:
                p.keywords = list(p.keywords) + ["_question"]
            p.utility = min(p.utility, 0.3)
            p.layer = "L1_session"
            graph.save_point(p)
            changed += 1
    return changed


def migrate_legacy_joke_closer(db, joke_re, now: str) -> None:
    """Phase 53 one-off (moved here from directives.__init__ in 69.5 for the 400-line ceiling): a joke-at-the-end
    request older code mis-stored as an output_suffix becomes the proper conversation_closer. Idempotent."""
    row = db.execute("SELECT value, instruction FROM directives WHERE kind='output_suffix'").fetchone()
    sentinel = (row[0] or "").strip().lower() in ("short_joke", "joke", "a joke", "a short joke", "short joke") if row else False
    if row and (joke_re.search(row[0] or "") or joke_re.search(row[1] or "") or sentinel):
        db.execute("DELETE FROM directives WHERE kind='output_suffix'")
        db.execute("INSERT OR REPLACE INTO directives (kind, value, source, updated_at, instruction, fallback_text) "
                   "VALUES ('conversation_closer', 'a short joke', 'migration', ?, ?, '')",
                   (now, "End every reply with a short joke."))
        db.commit()


def migrate_tool_rules(engine) -> int:
    """66.5: standing tool rules that were stored as MEMORIES ("from now on always use brave search
    for weather") become `tool_rule:` directives (idempotent: same value = no-op) and keep a tag."""
    from .directives import detect_tool_rule
    changed = 0
    present = {d["kind"] for d in engine.directives.active()}
    for p in engine.graph.all_points():
        if p.status != "active" or p.source not in ("user", "user_explicit"):
            continue
        det = detect_tool_rule(p.content)
        if not det or det.get("clear"):
            continue
        if det["kind"] in present or engine.directives.is_cleared(det["kind"]):
            continue        # 69.5: a live directive is never overwritten by an old episode; a retired one never returns
        if engine.directives.apply(p.content, "migration", detected=det) is not None:
            changed += 1
            present.add(det["kind"])
        if "_tool_rule" not in p.keywords:
            p.keywords = list(p.keywords) + ["_tool_rule"]
            engine.graph.save_point(p)
    return changed


def repair_memory_provenance(engine) -> Dict[str, int]:
    """Fast idempotent startup migration for authoritative provenance/canonical identity."""
    return {
        "legacy_derived_reclassified": reclassify_legacy_derived(engine.graph),
        "canonical_conflicts_superseded": supersede_canonical_conflicts(engine),
        "layers_restratified": repair_layer_stratification(engine.graph),
        "questions_retyped": retype_stored_questions(engine.graph),
        "tool_rules_migrated": migrate_tool_rules(engine),
    }


def _is_junk_fact(p) -> bool:
    """Vacuous 'facts': tautological, no entities, no concrete values."""
    if _JUNK_RE.search(p.content):
        return True
    if p.type == "fact" and not p.entities and not re.search(r"\d", p.content) \
            and len(p.content) < 60 and p.source == "assistant":
        return True
    return False


def dedup_existing(graph) -> int:
    """Merge near-identical same-type actives into the newest one (others → superseded)."""
    from .ingest import _negation_polarity
    actives = [p for p in graph.active_points()
               if p.type not in ("skill", "macro") and p.embedding]
    actives.sort(key=lambda p: p.timestamp, reverse=True)   # newest first = keeper
    superseded = 0
    kept: List = []
    for p in actives:
        dup_of = None
        for k in kept:
            if k.type != p.type or _negation_polarity(k.content) != _negation_polarity(p.content):
                continue
            if fu_math.cosine(p.embedding, k.embedding) >= config.DEDUP_MIN_COSINE:
                dup_of = k
                break
        if dup_of is None:
            kept.append(p)
        else:
            p.status = "superseded"
            dup_of.access_count += p.access_count
            graph.save_point(p)
            graph.save_point(dup_of)
            superseded += 1
    return superseded


def demote_assistant_facts(graph) -> int:
    """Assistants don't author facts — reclassify existing assistant fact/person nodes to
    message (they stay recallable as episodes, but stop acting as canon)."""
    changed = 0
    for p in graph.all_points():   # H-04: locked snapshot
        if p.source == "assistant" and p.type in ("fact", "person") and p.status == "active":
            p.type = "message"
            p.importance = min(p.importance, 0.4)
            graph.save_point(p)
            changed += 1
    return changed


def is_content_free_chatter(p) -> bool:
    """Phase 65: an assistant-authored message with no entities, no numbers and under 100 chars
    carries no user knowledge ("I'm ready to help", a closer joke). Predicate only; wiring is
    gated on the precision bench (Rule 12)."""
    return (p.source == "assistant" and p.type == "message" and not p.entities
            and not re.search(r"\d", p.content or "") and len(p.content or "") < 100)


def sleep_content_free_chatter(graph) -> int:
    """Put content-free assistant chatter to sleep (dormant, reawakenable — never deleted)."""
    changed = 0
    for p in graph.all_points():
        if p.status == "active" and is_content_free_chatter(p):
            p.status = "dormant"
            graph.save_point(p)
            changed += 1
    return changed


def demote_junk(graph) -> int:
    changed = 0
    for p in graph.all_points():   # H-04: locked snapshot
        if p.status == "active" and p.type not in ("skill", "macro") and _is_junk_fact(p):
            p.status = "superseded"
            graph.save_point(p)
            changed += 1
    return changed


def tag_ephemeral(graph) -> int:
    """Mark existing ephemeral observations so the score decay applies to them too."""
    changed = 0
    for p in graph.all_points():   # H-04: locked snapshot
        if p.status == "active" and p.type not in ("skill",) and is_ephemeral(p.content) \
                and "_ephemeral" not in p.keywords:
            p.keywords = list(p.keywords) + ["_ephemeral"]
            p.stability = min(p.stability, 0.1)
            graph.save_point(p)
            changed += 1
    return changed


def redact_macro_stale_values(engine) -> int:
    """Macros are L2 digests that may have baked in a value later corrected (old 'Sebastian'
    in a summary after name→Teodoro). Redact the old value → current in macro summaries so the
    digest stops re-teaching stale canon (PA3 superseded_value_map pattern)."""
    pairs = engine.facts.superseded_values()   # [(key, old_value)]
    if not pairs:
        return 0
    active = engine.facts.active()
    redacted = 0
    for p in engine.graph.all_points():   # H-04: locked snapshot
        if p.type != "macro" or p.status != "active":
            continue
        original = p.summary or p.content
        new = original
        for key, old in pairs:
            current = next((f["value"] for f in active if f["key"] == key), None)
            if old and current and old.lower() in new.lower():
                new = re.sub(re.escape(old), current, new, flags=re.IGNORECASE)
        if new != original:
            p.summary = new
            p.content = new
            engine.graph.save_point(p)
            redacted += 1
    return redacted


def hygiene_pass(engine) -> Dict[str, int]:
    """Full retroactive pass. Order matters: junk first (cheapest), then assistant facts,
    then dedup, then ephemeral tagging, then canonical-fact supersession."""
    from .facts import supersede_stale_nodes
    report = {
        "junk_demoted": demote_junk(engine.graph),
        "assistant_facts_reclassified": demote_assistant_facts(engine.graph),
        "legacy_procedures_retyped": retype_legacy_procedures(engine.graph),
        **repair_memory_provenance(engine),
        "duplicates_superseded": dedup_existing(engine.graph),
        "ephemeral_tagged": tag_ephemeral(engine.graph),
        "stale_fact_nodes_superseded": supersede_stale_nodes(engine.facts, engine.graph),
        "macro_values_redacted": redact_macro_stale_values(engine),
    }
    log.info("hygiene: %s", report)
    return report
