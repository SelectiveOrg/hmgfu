"""Tools as HMG points — the core simplification (docs/PA3_LESSONS.md).

Every tool/skill lives in the hex grid as a MemoryPoint(type='skill'), so tool
selection IS memory retrieval and grading/reinforcement tune tools like memories.
Growth path: nothing to do here for new tools — sync_tool_points picks up whatever
the registry knows (built-ins, dropped-in skills, agent-created skills).
"""

from __future__ import annotations

import re

import logging
from typing import List

log = logging.getLogger("hmgfu.tool_points")


# --- learned usage phrases (Phase 56, bench L22) --------------------------------------------
# Registry descriptions are English, and the embedder is English-centric — a Portuguese
# instruction can't reach the semantic-fallback floor when the router degrades. Tool points
# therefore LEARN the user's own successful phrasings: capped, deduped by meaning, persisted as
# keywords (so sync_tool_points never resets them), folded into the embedded content.
MAX_USAGE_PHRASES = 5
PHRASE_NOVELTY_MAX_COSINE = 0.60    # only store a phrasing the current embedding does NOT cover
_PHRASE_PREFIX = "phrase:"


def tool_phrases(point) -> List[str]:
    return [k[len(_PHRASE_PREFIX):] for k in point.keywords if k.startswith(_PHRASE_PREFIX)]


def compose_tool_content(name: str, desc: str, phrases: List[str]) -> str:
    text = f"Tool {name}: {desc}"
    if phrases:
        text += " Used for: " + " | ".join(phrases)
    return text


def learn_usage_phrase(engine, point, phrase: str) -> bool:
    """After a SUCCESSFUL tool use, absorb a semantically-novel user phrasing into the tool
    point (multilingual self-growth: the first successful PT use makes future PT turns reach
    the semantic rescue even if the router degrades). Returns True when learned."""
    from . import fu_math
    phrase = " ".join((phrase or "").split())[:120]
    if len(phrase) < 8:
        return False
    existing = tool_phrases(point)
    if any(p.lower() == phrase.lower() for p in existing):
        return False
    if fu_math.cosine(engine.embed(phrase), point.embedding) >= PHRASE_NOVELTY_MAX_COSINE:
        return False                 # this phrasing is already semantically covered
    phrases = (existing + [phrase])[-MAX_USAGE_PHRASES:]     # capped FIFO
    name = next((kw[5:] for kw in point.keywords if kw.startswith("tool:")), "")
    point.keywords = ([k for k in point.keywords if not k.startswith(_PHRASE_PREFIX)]
                      + [_PHRASE_PREFIX + p for p in phrases])
    point.content = compose_tool_content(name, point.summary or "", phrases)
    point.embedding = engine.embed(point.content)
    engine.graph.save_point(point)
    log.info("tool %s learned usage phrase: %r", name, phrase[:60])
    return True


def sync_tool_points(registry, engine) -> int:
    """Every tool/skill becomes a MemoryPoint(type='skill') so tool selection IS retrieval.

    Idempotent: existing tool points (keyword 'tool:<name>') are updated, not duplicated.
    Learned usage phrases (keyword-persisted) are preserved and folded into refreshed content.
    """
    from . import fu_math
    from .ingest import assign_hex
    from .models import MemoryPoint
    existing = {}
    for p in engine.graph.points.values():
        if p.type == "skill":
            for kw in p.keywords:
                if kw.startswith("tool:"):
                    existing[kw[5:]] = p
    created = 0
    for name, schema in registry.schemas.items():
        desc = schema.get("description", "")
        text = f"Tool {name}: {desc}"
        # tool vs skill is a derived facet (taxonomy.node_class reads 'skill_created'): a
        # created/dropped-in skill has a handler; a built-in tool does not. Storage type stays
        # 'skill' for both so the ~14 existing type filters are untouched (Rule 3/11).
        kws = [f"tool:{name}"] + (["skill_created"] if name in registry.skill_handlers else [])
        if name in existing:
            point = existing[name]
            composed = compose_tool_content(name, desc, tool_phrases(point))
            if point.content != composed:  # description changed → refresh, KEEPING learned phrases
                point.content = composed
                point.summary = desc[:200]
                point.embedding = engine.embed(composed)
            if "skill_created" in kws and "skill_created" not in point.keywords:
                point.keywords = list(point.keywords) + ["skill_created"]
            engine.graph.save_point(point)
            continue
        point = MemoryPoint(
            type="skill",
            title=f"tool:{name}",
            content=text,
            summary=desc[:200],
            source="system",
            embedding=engine.embed(text),
            keywords=kws,
            topics=["tools"],
            importance=0.55, confidence=0.9, novelty=0.3, utility=0.55,
            energy=0.3, layer="L2_project",
        )
        point.density = fu_math.compute_density(point, 0.0)
        point.hex = assign_hex(point, engine.graph)
        engine.graph.save_point(point)
        created += 1
    if created:
        log.info("tool points synced: %d new (of %d tools)", created, len(registry.schemas))
    return created


# 94.5: the one tool that is pinned, and the reason it is the only one. Tool selection is similarity
# to the question, capped at `question_max_tools` (5) for a question. A shell is relevant to almost
# everything and SIMILAR to almost nothing, so `bash` never surfaced for "whats the weather" -- and the
# assistant told the user "I cannot execute curl commands directly", which was true of the five tools
# it held and false of the twenty-two that were registered.
#
# The fix is NOT to offer everything: that would put every side-effecting tool in front of the model on
# every turn. It is to keep available the one tool whose relevance is never topical -- `tool_search`,
# whose whole purpose is to find the others. What it finds is still subject to `authority.decide`, so
# discovery grants visibility, never permission.
ALWAYS_OFFERED = ("tool_search",)


_FILE_NAME = re.compile(r"\b[\w-]+\.(?:py|js|ts|json|md|txt|yml|yaml|toml|csv|html|css|sh|env)\b", re.IGNORECASE)   # 95.47


def retrieve_tools_for_turn(registry, engine, query_point, max_tools: int = 8) -> List[dict]:
    """Tool selection = HMG retrieval over skill-type points, ranked by activation score.

    The multilingual nano maps intent against the live registry and pins exact tool names.
    If nano is unavailable, the same HMG semantic score provides a language/model-neutral
    fallback; no hand-maintained action phrase list is involved.
    """
    from . import fu_math
    weights = engine.weight_learner.weights()   # learned overlay — tool selection IS retrieval
    tool_points = [p for p in engine.graph.points.values()
                   if p.type == "skill" and p.status == "active"]
    scored = []
    for p in tool_points:
        name = next((kw[5:] for kw in p.keywords if kw.startswith("tool:")), None)
        if name is None or name not in registry.schemas:
            continue
        scored.append((fu_math.memory_score(query_point, p, weights=weights), name))
    scored.sort(key=lambda t: -t[0])
    folded = query_point.text.casefold()
    explicit = [name for name in registry.schemas if name.casefold() in folded]
    # 95.19: a message that names a FILE of the workspace (its stem) requires the native read of it, as a
    # message that names a tool requires the tool -- E7: the block named inventory.txt (95.16), the model
    # went to it with a blind `grep -c` (1 matching line) because read_file was never offered.
    from .speech_act import refers_to_workspace       # the same gate that shows the block (67.6)
    from .tool_builtins import workspace_names
    stems = [n.rsplit(".", 1)[0].casefold() for n in workspace_names() if not n.endswith("/")] if refers_to_workspace(query_point.text) else []
    if "read_file" in registry.schemas and any(len(st) >= 4 and st in folded for st in stems):
        explicit.append("read_file")
    # 95.47: the mirror -- an action request that names a workspace file which does not exist yet requires the
    # native write ("Cria um script Python chamado ola_tamarin.py ..."; the pack had offered only bash)
    from .speech_act import is_action_request
    named = {m.casefold() for m in _FILE_NAME.findall(query_point.text or "")}
    existing = {n.casefold() for n in (workspace_names() if named else [])}
    if "write_file" in registry.schemas and is_action_request(query_point.text) and (named - existing):
        explicit.append("write_file")
    from .plans import enumerated_items                       # 95.54: an enumerated multi-request is the plan tool's own
    if "plan_task" in registry.schemas and len(enumerated_items(query_point.text or "")) >= 2:   # trigger (95.4's reader)
        explicit.append("plan_task")
    required = []
    for name in list(query_point.requested_tools) + explicit:
        if name in registry.schemas and name not in required:
            required.append(name)
    if required:
        query_point.requested_tools = list(required)
        query_point.action_requested = True
    query_point.explicit_tools = [n for n in explicit if n in registry.schemas]   # 95.47d: the user's own words require these
    action_requested = bool(query_point.action_requested or required)
    # Fail-soft path when nano extraction is disabled/unavailable: strong semantic alignment
    # with a registered capability is itself evidence. The catalog grows with installed skills.
    # The nano/main router is non-deterministic: ~1 in 4 times it mislabels a clear imperative
    # ("Run the shell command …") as a declarative 'statement' with action_requested=False, which
    # then offers zero tools and loses the action. A misrouted command lands as 'statement', never
    # 'question' — so include 'statement' here to let the semantic recovery below rescue it, while
    # questions / greetings / feedback stay tool-free (they only ever match a capability weakly).
    semantic_instruction = (query_point.intent == "task"
                            or query_point.conversation_act in ("instruction", "statement"))
    margin = scored[0][0] - scored[1][0] if len(scored) > 1 else (scored[0][0] if scored else 0.0)
    fallback_match = scored and scored[0][0] >= 0.28 and (margin >= 0.015 or scored[0][0] >= 0.44)
    # A misrouted command usually lands as 'statement' (handled above), but occasionally as
    # 'question'. Recover a 'question' ONLY on a STRONG capability match (>=0.40). RECALIBRATED
    # (Phase 58) after enriching the read_file/bash descriptions to be workspace-inspection anchors:
    # measured live (scripts/probe_action_turns.py), a GENUINE "inspect the project folder" question
    # now scores read_file 0.42-0.43 / bash 0.39, while a SPURIOUS greeting/identity question tops
    # out at 0.326 (read_file/bash not even top-6, <0.28). 0.40 sits in that ~0.10 gap → offers the
    # file/shell tools on real inspection questions (L8/L9) yet keeps identity/greeting tool-free
    # (L2/L3 preserved — their autobiographical context is injected, never searched).
    strong_question_action = (query_point.conversation_act == "question"
                              and bool(scored) and scored[0][0] >= 0.40)
    if not action_requested and (semantic_instruction or strong_question_action) and fallback_match:
        action_requested = True
        required.append(scored[0][1])
        query_point.action_requested = True
        query_point.requested_tools = list(required)
        # Phase 56: mark the rescue — if this tool then SUCCEEDS, the agent persists the corrected
        # classification as a routing exemplar, so the router LEARNS from its own misroutes.
        query_point.recovered_action = scored[0][1]
    if not action_requested:
        return []
    selected = list(required)
    if not selected and scored and scored[0][0] >= 0.30:
        selected.append(scored[0][1])
    for score, name in scored:
        if score < 0.44:
            continue
        if name not in selected:
            selected.append(name)
        if len(selected) >= max_tools:
            break
    offered = selected[:max_tools]
    # 94.5b: pin AFTER the cap and outside `required`. Putting it in `required` also set
    # `action_requested = True`, so every greeting became an action turn -- 11 tests failed and each
    # was right. This adds visibility only: no claim that the user asked for it, and no authority.
    #
    # 94.5c: and NOT when the turn already names its tools. v2 states the precision contract -- "an
    # explicit memory-search request receives its applicable tool, without unrelated planning /
    # tool-discovery noise" -- and it is right: discovery exists for the turn that does not know what
    # it needs, which is the turn that said "I cannot execute curl" while holding a shell it was never
    # shown. When the user named the tool, there is nothing to discover.
    if not required:
        for name in ALWAYS_OFFERED:
            if name in registry.schemas and name not in offered:
                offered.append(name)
    return [registry.schemas[n] for n in offered]
