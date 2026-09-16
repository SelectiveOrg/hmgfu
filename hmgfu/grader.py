"""Turn grader + learning loop (PA3 concepts, HMG-Fu-native).

Producer selectable at runtime (settings.grader_producer): "nano" uses the grader role model,
"main" uses the chat model. Output is ADVISORY (PA3 lesson 7): it tunes utility EMAs and may
extract a playbook pattern-memory; nothing on the next turn's critical path depends on it.

Grades: each recalled memory as cited / implied / unused (EMA on point.utility, which feeds ρ),
each used tool as helpful / harmful, plus an overall turn score. On detected user correction,
the contradiction machinery marks tension / supersedes (never a file edit — PA3 memory lesson).
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import List, Optional

from . import config, fu_math
from .models import MemoryPoint, now_iso
from .sensitizer import parse_nano_json

log = logging.getLogger("hmgfu.grader")

EMA_ALPHA = 0.3
GRADE_VALUE = {"cited": 1.0, "implied": 0.6, "unused": 0.0}

_GRADE_PROMPT = """You grade one assistant turn for a memory system. Return ONLY JSON:
{
 "turn_score": 0.0 to 1.0,
 "memory_grades": [{"index": <int>, "grade": "cited"|"implied"|"unused"}],
 "tool_grades": [{"name": "<tool>", "helpful": true|false}],
 "user_correction": null or {"wrong": "<what the user said is wrong>", "right": "<the corrected fact>"},
 "task_pattern": null or "<one-sentence reusable procedure IF the turn completed a multi-step task>"
}
"memory_grades.index" refers to the numbered memory list. Grade "cited" only if the reply
actually used that memory's content. JSON only."""


def _heuristic_grades(reply: str, retrieved, user_message: str = "") -> List[dict]:
    """Deterministic fallback: a memory is 'cited' only when the reply shares at least TWO distinctive
    tokens with it that the USER's own message did not already contain (65.5 — one shared word like
    "person" was grading junk as cited and pumping its utility). Questions/session breath are never
    cited: they are not knowledge."""
    import re
    reply_toks = set(re.findall(r"[a-z0-9]{4,}", reply.lower()))
    user_toks = set(re.findall(r"[a-z0-9]{4,}", (user_message or "").lower()))
    grades = []
    for i, item in enumerate(retrieved):
        p = item.point
        if "_question" in p.keywords or p.type == "session":
            grades.append({"index": i, "grade": "unused"}); continue
        toks = set()
        for t in list(p.entities) + list(p.keywords):
            toks |= set(re.findall(r"[a-z0-9]{4,}", str(t).lower()))
        distinctive = (toks & reply_toks) - user_toks
        grades.append({"index": i, "grade": "cited" if len(distinctive) >= 2 else "unused"})
    return grades


def grade_turn(engine, user_message: str, reply: str, retrieved, tool_trace,
               query=None) -> dict:
    """Run the grader, apply EMAs, corrections and playbook extraction. Returns the grade card.
    `query` (the turn's QueryPoint) enables the Phase 56 weight learner — grades teach the
    retrieval scoring math which components earn recall."""
    if config.CHAT_CORRECTION_SIGNAL:
        # FLAG ON (P-AUDIT-3): the grader nano LEAVES the hot path (FRONT 0). memory_grades → the
        # existing model-free heuristic (utility/weight-learning stay alive); tool_grades were already
        # dead (Phase 43); turn_score is display-only. The correction — the only critical, nano-lossy
        # output — comes from the STRONG chat model, DEFERRED to the GPU-free queue (FRONT 2), disabled
        # on action turns (B.5). This branch is reached only when the flag is on, i.e. at/after the flip.
        producer, payload = "chat-front0", None
        memory_grades, tool_grades, turn_score, task_pattern, correction = \
            _heuristic_grades(reply, retrieved, user_message), [], None, None, None
        # P0.1 (Plan.txt): enqueue on EVERY turn — action turns included. The B.5 action-skip
        # predated FRONT-2: detection is now a SEPARATE deferred post-reply call (no shared
        # prompt, no quality coupling with the primary task), and the router intermittently
        # ACTION-classifies real corrections, so skipping was LOSING them (B6 live finding).
        engine.enqueue_correction(user_message, reply, facts_summary(retrieved))
        correction_source = "deferred"
    else:
        # FLAG OFF: production UNCHANGED (nano grader) — produção intocada até o flip ser ganho.
        producer = engine.settings.get("grader_producer")
        role = "chat" if producer == "main" else "grader"
        memory_list = "\n".join(
            f"{i}. [{r.point.type}] {r.point.summary or r.point.content[:120]}"
            for i, r in enumerate(retrieved)
        ) or "(none)"
        tool_list = ", ".join(sorted({t["name"] for t in tool_trace})) or "(none)"
        payload = None
        try:
            raw = engine.registry.chat_for_role(role, [
                {"role": "system", "content": _GRADE_PROMPT},
                {"role": "user", "content":
                    f"USER: {user_message[:1500]}\n\nASSISTANT: {reply[:2500]}\n\n"
                    f"MEMORIES RECALLED:\n{memory_list[:2500]}\n\nTOOLS USED: {tool_list}"},
            ], json_mode=True, temperature=0.0, think=False)
            payload = parse_nano_json(raw["content"])
        except Exception as exc:
            log.warning("grader model call failed (%s producer): %s", producer, exc)
        # nano output is untrusted: enforce shapes (lists of dicts / dict / str) before applying
        def _dict_list(value):
            return [x for x in value if isinstance(x, dict)] if isinstance(value, list) else []
        memory_grades = _dict_list((payload or {}).get("memory_grades")) or _heuristic_grades(reply, retrieved, user_message)
        tool_grades = _dict_list((payload or {}).get("tool_grades"))
        turn_score = (payload or {}).get("turn_score")
        correction = (payload or {}).get("user_correction")
        if not isinstance(correction, dict):
            correction = None
        correction_source = "nano"
        task_pattern = (payload or {}).get("task_pattern")
        if not isinstance(task_pattern, str):
            task_pattern = None
        elif task_pattern.strip().lower() in {"n/a", "none", "null", "not applicable"}:
            task_pattern = None

    memory_details = _apply_memory_grades(engine, retrieved, memory_grades)
    tool_details = _apply_tool_grades(engine, tool_grades)
    # Phase 56 learning loop: the same grades adapt the retrieval WEIGHTS (bounded, persisted)
    # so the scoring math itself improves with experience — not only per-point utility.
    weights_learned = 0
    if query is not None and engine.settings.get("learning_enabled"):
        try:
            weights_learned = engine.weight_learner.learn_from_grades(query, retrieved, memory_grades)
        except Exception as exc:
            log.warning("weight learning failed (non-fatal): %s", exc)
    correction_result = _apply_correction(engine, correction, user_message) if correction else None
    playbook_id = None
    if task_pattern and engine.settings.get("playbook_extraction") and len(tool_trace) >= 2:
        playbook_id = _extract_playbook(engine, task_pattern, tool_trace)

    return {
        "producer": producer,
        "turn_score": turn_score if isinstance(turn_score, (int, float)) else None,
        "memories_graded": len(memory_details),            # counts kept for compat (Rule 11)
        "tools_graded": len(tool_details),
        # P3 (ANALYSIS Part 5): the per-item learning detail the card used to discard
        "memory_details": memory_details,
        "tool_details": tool_details,
        "weights_learned_from": weights_learned,   # Phase 56: grades that taught the score weights
        "correction": correction_result,
        "correction_source": correction_source,   # P-AUDIT-2: chat | nano (which perceiver decided)
        "playbook_id": playbook_id,
        "source": "model" if payload else "heuristic",
    }


def _apply_memory_grades(engine, retrieved, grades: List[dict]) -> List[dict]:
    """Usefulness EMA on utility (feeds ρ); returns per-item records so the card shows WHAT (P3)."""
    details = []
    for grade in grades:
        try:
            index = int(grade.get("index"))
        except (TypeError, ValueError):
            continue
        if not 0 <= index < len(retrieved):   # M-17: a negative index must NOT grade the last memory
            continue
        value = GRADE_VALUE.get(str(grade.get("grade")))
        if value is None:
            continue
        item = retrieved[index]
        point = item.point
        before = point.utility
        # 94.6: use is not verification — a SUPERSEDED point cannot GAIN from use, only LOSE (v166).
        target = fu_math.clamp((1 - EMA_ALPHA) * before + EMA_ALPHA * value)
        withheld = point.status == "superseded" and target > before
        point.utility = before if withheld else target
        point.density = fu_math.compute_density(point, engine.graph.centrality(point.id))
        engine.graph.save_point(point)
        # Phase 61a: a memory the reply actually used (cited/implied) is a silent_use signal — the
        # weakest, CAPPED tier (use is ambiguous, not user verification). Gated → no-op when OFF.
        if config.REGULATOR_ENABLED and value > 0:
            engine.regulator.transition(point.id, "silent_use")
        details.append({"id": point.id, "title": (point.title or point.summary or "")[:60],
                        "type": point.type, "grade": str(grade.get("grade")),
                        "before": round(before, 3), "after": round(point.utility, 3),
                        "reward_withheld": withheld})   # 94.6: visible, not silent (Rule 10)
    return details


def _apply_tool_grades(engine, grades: List[dict]) -> List[dict]:
    """Phase 43: the nano no longer grades tools; only user feedback changes utility (read-only here)."""
    observed = []
    for grade in grades:
        helpful = grade.get("helpful")
        if not isinstance(helpful, bool):
            continue
        name = str(grade.get("name", ""))
        point = engine._tool_point(name)
        if point is None:
            continue
        observed.append({"name": name, "helpful": helpful,
                         "before": round(point.utility, 3), "after": round(point.utility, 3)})
    return observed


_CORRECTION_CUES = ("not ", "n't", "no longer", "actually", "correction", "wrong", "isn't",
                    "aren't", "instead", "i meant", "rather", "mistake", "wasn't", "isnt")


# --- P-AUDIT-2 (THEORY_V3 B.5): correction signal from the STRONG chat model ----------------------
# FLAT schema (Ollama constrained decoding masks off-schema tokens; keep it flat — no nesting).
_CHAT_CORRECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "is_correction": {"type": "boolean"},
        "right": {"type": "string"},
        "wrong": {"type": "string"},
    },
    "required": ["is_correction", "right", "wrong"],
}
_CHAT_CORRECTION_SYS = (
    "You detect CORRECTIONS for a personal-memory assistant. Decide if, in the USER's LAST message, "
    "the user is CORRECTING a previously-stated fact about themselves or the world — changing a value "
    "already recorded (name, spelling, city, job/role, date/year, preference, surname, marital/other "
    "status). Corrections appear in Portuguese, English, Valencian/Valencia slang, with typos, as very "
    "short messages, or BURIED mid-way inside a longer message about another topic — catch all of "
    "them. It is NOT a correction when the user merely acknowledges ('ah ok', 'certo', 'se tu o dizes', "
    "'hmm', 'ta bem'), praises, asks a question, or states a brand-NEW fact that does not replace an "
    "earlier one. Output the schema: is_correction; when true, right = the corrected/new value and "
    "wrong = the old value being replaced (empty string if unknown); when false, right and wrong are "
    "empty strings. The USER MESSAGE is given as NUMBERED CLAUSES — examine EACH clause on its own: a "
    "correction can sit in a SINGLE clause while every other clause is about a different topic (weather, "
    "football, family, a trip, the market). If ANY one clause changes a recorded fact, is_correction=true "
    "and take right/wrong from THAT clause, ignoring the surrounding topic. "
    "DECISION RULE — compare each clause against KNOWN FACTS: a clause is a CORRECTION if it CHANGES, "
    "NARROWS, SPLITS, or CONTRADICTS a value present in KNOWN FACTS. This INCLUDES clarifications ('só pra "
    "esclarecer, X e Y são coisas diferentes'), refinements/qualifiers ('não é SÓ X, também/afinal Z', "
    "'sou sócio, não só dono'), and a stated shift ('agora sou mais X', 'já não é X, mudou') when a prior "
    "value was recorded. But a clause stating a value that is NOT in KNOWN FACTS and contradicts nothing "
    "there is a brand-NEW first-time fact — is_correction=FALSE (do not flag a first mention)."
)


def facts_summary(retrieved) -> str:
    """The recalled-facts context for the correction detector. Captured at turn time so the deferred
    queue (FRONT 2) can run the detection later with the REAL context."""
    return "; ".join((r.point.summary or r.point.title or "")[:80]
                     for r in (retrieved or [])[:6] if (r.point.summary or r.point.title))


# FRONT 1 (P-AUDIT-3, buried fix): mechanical CPU partition — no model, no VRAM. Splits on sentence
# enders + ellipsis + PT discourse markers that introduce a buried aside ("a propósito", "já agora"…).
_CLAUSE_SPLIT = re.compile(
    r"[.!?;\n]+|\.{2,}|…+"
    r"|\b(?:a prop[oó]sito|j[aá] agora|ah e|por sinal|enfim|de resto|s[oó] que|entretanto|ali[aá]s"
    r"|s[oó] pra (?:constar|esclarecer)|n[aã]o te disse mas)\b",
    re.IGNORECASE)


def _split_clauses(message: str, max_clauses: int = 16) -> List[str]:
    """Partition the message into clauses. Burial defeats the model's attention over a long context;
    numbered clauses reduce the task to the per-sentence case where the detector already scores 1.00."""
    parts = [p.strip(" ,-–—") for p in _CLAUSE_SPLIT.split(message or "")]
    clauses = [p for p in parts if len(p) >= 4]
    return clauses[:max_clauses] or [(message or "").strip()]


def _detect_correction_via_chat(engine, user_message: str, reply: str, facts: str) -> Optional[dict]:
    """Constrained-decoding correction detection on the CHAT model (gemma4:12b). Returns {right,wrong}
    or None. `facts` = pre-built recalled-facts summary (facts_summary). FRONT 1: the message is ALSO
    presented as NUMBERED CLAUSES so a BURIED correction cannot hide behind the surrounding topic."""
    clauses = _split_clauses(user_message)
    numbered = "\n".join(f"  [{i + 1}] {c}" for i, c in enumerate(clauses))
    messages = [
        {"role": "system", "content": _CHAT_CORRECTION_SYS},
        {"role": "user", "content": f"KNOWN FACTS (recorded earlier): {facts or '(none)'}\n\n"
                                    f"ASSISTANT JUST SAID: {reply[:1200]}\n\n"
                                    f"USER'S LAST MESSAGE, split into numbered clauses — examine EACH:\n{numbered}"},
    ]
    # A transient Ollama/VRAM blip must NOT silently demote the strong perceiver to the weak nano —
    # retry with backoff, and only raise (→ nano fallback) if the STRONG model is genuinely offline.
    raw, last_exc = None, None
    for attempt in range(4):
        try:
            raw = engine.registry.chat_for_role("chat", messages, json_mode=True, temperature=0.0,
                                                format_schema=_CHAT_CORRECTION_SCHEMA, think=False)   # 73.2
            if raw and raw.get("content"):
                break
            last_exc = "empty content"
        except Exception as exc:
            last_exc = exc
        if attempt < 3:
            time.sleep(1.5 * (attempt + 1))   # 1.5/3/4.5s — long enough to outwait a gemma4 VRAM reload
    if not (raw and raw.get("content")):
        raise RuntimeError(f"chat correction call empty/failed after retries: {last_exc}")
    parsed = parse_nano_json(raw["content"])
    if isinstance(parsed, dict) and parsed.get("is_correction"):
        right = str(parsed.get("right") or "").strip()
        if right:                                  # a correction must name the new value
            return {"right": right, "wrong": str(parsed.get("wrong") or "").strip()}
    return None


def _correction_grounded(correction: dict, user_message: str) -> bool:
    """M-17: only trust a grader-reported correction that the USER actually expressed — the
    message carries a correction cue, or the corrected/wrong value appears in it. Blocks a
    hallucinated correction from being persisted at the highest source-trust tier."""
    low = (user_message or "").lower()
    if any(cue in low for cue in _CORRECTION_CUES):
        return True
    for field in ("right", "wrong"):
        toks = [t for t in re.findall(r"[\w']+", str(correction.get(field) or "").lower()) if len(t) > 3]
        if toks and any(t in low for t in toks):
            return True
    return False


def _apply_correction(engine, correction: dict, user_message: str = "") -> Optional[dict]:
    """A correction is a curation event: ingest the right fact as user-explicit; the
    contradiction machinery (ingest → tension; explicit source wins) supersedes the wrong one."""
    right = str(correction.get("right") or "").strip()
    if not right or len(right) < 4:
        return None
    if not _correction_grounded(correction, user_message):   # M-17: don't persist a hallucinated correction
        log.info("grader correction rejected — not grounded in user message: %r", right[:60])
        return None
    from .fact_nodes import supersessions_from_message
    grounded = supersessions_from_message(getattr(engine.facts, "assertions", None), user_message)   # 95.1b: the ledger's own pairs
    curated = getattr(engine, "_turn_curated", None) or {}
    if grounded and all(pair in curated for pair in grounded):          # 95.18: the protocol curated this pair already
        return {"ingested": curated[grounded[0]], "conflicts_marked": 0, "ambiguous": None, "grounded": grounded}
    point = engine.ingest(right, source="user_explicit", mtype="fact")
    from .dream import detect_contradictions, mark_tension
    found = 0
    for contradiction in detect_contradictions(engine.graph, engine.sensitizer,
                                               use_nano=False, max_checks=20):
        if contradiction["a"] == point.id or contradiction["b"] == point.id:
            mark_tension(contradiction, engine.graph, agrees_with=right)   # 95.1: B is not the error
            found += 1
            if config.REGULATOR_ENABLED:                       # Phase 61a absorbing-correction signal
                _record_correction_signals(engine, contradiction)
    # B6: the perceiver NAMED the stale value -> supersede its bearers directly; absorbing: only an unambiguous target (Rule 13/12)
    from .facts import supersede_named_stale, supersede_stale_nodes
    named = {"superseded": [], "ambiguous": None}
    if grounded: found += supersede_stale_nodes(engine.facts, engine.graph)   # 95.22c: the ledger holds the pair -> its ONE rule (born_stale over every active point)
    for wrong, new_value in ([] if grounded else [(str(correction.get("wrong") or ""), right)]):
        named = supersede_named_stale(engine.graph, point, wrong, new_value, context=user_message)
        for cid in named["superseded"]:
            found += 1
            if config.REGULATOR_ENABLED:
                engine.regulator.transition(cid, "correction")
    if named["ambiguous"] and not found:
        log.info("correction not superseded (%s): wrong=%r right=%r", named["ambiguous"], str(correction.get("wrong"))[:40], right[:40])
    return {"ingested": point.id, "conflicts_marked": found, "ambiguous": named["ambiguous"],
            "grounded": grounded}


def _record_correction_signals(engine, contradiction) -> None:
    """Phase 61a: a user correction is ABSORBING (→ SUPERSEDED). Mark 'correction' ONLY on the point
    mark_tension ACTUALLY superseded — verify status. infer_resolution may reach NO clear winner and
    supersede nothing, and the superseded member may be EITHER a or b; assuming "the other id lost"
    would poison a SURVIVING fact (verify-refuter finding). No-op unless a member is truly superseded."""
    for cid in (contradiction.get("a"), contradiction.get("b")):
        pt = engine.graph.points.get(cid) if cid else None
        if pt is not None and pt.status == "superseded":
            engine.regulator.transition(cid, "correction")


def _extract_playbook(engine, pattern: str, tool_trace) -> Optional[str]:
    """Successful multi-tool turn → reusable 'pattern' memory (PA3 playbooks, simplified).
    Phase 43 efficiency: a learned loop's utility is INVERSELY proportional to how many tools it
    needed — a result reached with fewer tools outranks the same result reached with more, and
    when a similar playbook already exists the SHORTER path replaces the longer one."""
    ok_steps = [t["name"] for t in tool_trace if not t["failed"] and not t.get("blocked")]
    if not ok_steps:
        return None
    n_steps = len(ok_steps)
    efficiency_utility = fu_math.clamp(0.85 - 0.06 * n_steps)   # fewer tools → higher utility
    content = f"Procedure: {pattern.strip()} (steps: {' → '.join(ok_steps)})"
    embedding = engine.embed(content)
    for p in engine.graph.points.values():
        if p.type == "pattern" and fu_math.cosine(embedding, p.embedding) > 0.92:
            prev_steps = len([k for k in p.keywords if not k.startswith("_")])
            if n_steps < max(1, prev_steps):        # a SHORTER path to the same result → replace
                p.content, p.summary = content, pattern[:200]
                p.keywords = ok_steps[:6]
                p.utility = fu_math.clamp(max(p.utility, efficiency_utility) + 0.05)
            else:
                p.utility = fu_math.clamp(p.utility + 0.05)
            p.access_count += 1
            p.last_accessed_at = now_iso()
            engine.graph.save_point(p)
            return p.id
    point = MemoryPoint(
        type="pattern", title=pattern[:70], content=content, summary=pattern[:200],
        source="dream", embedding=embedding, topics=["procedures"],
        keywords=ok_steps[:6],
        importance=0.6, utility=efficiency_utility, confidence=0.7, novelty=0.5,
        energy=0.4, layer="L2_project",
    )
    point.density = fu_math.compute_density(point, 0.0)
    from .ingest import assign_hex
    point.hex = assign_hex(point, engine.graph)
    from .hygiene import apply_ephemeral_meta   # a playbook over ephemeral content decays too
    apply_ephemeral_meta(point)
    engine.graph.save_point(point)
    log.info("playbook extracted: %s", pattern[:60])
    return point.id
