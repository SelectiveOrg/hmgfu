"""Procedural memory — RUNBOOKS (Phase 75.1). A finalized session plan (done / partial / failed) leaves ONE runbook
point: the task, the steps in order with the tools that fulfilled each (from the receipts the step consumed), the
files touched and the outcome. Runbooks are procedural, not episodic: they are surfaced like tools (beside the tool
schemas, when the current request resembles a runbook's task) and never enter the memory panel (taxonomy class
`skill`; `retrieve_memory` excludes that class). Re-finalizing the same plan updates its runbook (idempotent key).
A runbook shown at proposal time is recorded on the new plan (`runbook_hint`); when that plan finalizes, the runbook's
utility moves with the outcome — the signal the outcome-driven policy (75.5) reads. Bounded, inspectable: setting
`runbooks_enabled`, floor `runbook_match_floor`, list at /api/runbooks; deleting the points restores stock behaviour."""
from __future__ import annotations

import hashlib
import logging
import os
from typing import List, Optional

from . import fu_math
from .models import MemoryPoint, QueryPoint, now_iso
from .tool_points import MAX_USAGE_PHRASES, PHRASE_NOVELTY_MAX_COSINE, _PHRASE_PREFIX, tool_phrases

log = logging.getLogger("hmgfu.runbooks")

RUNBOOK_TYPE = "runbook"
MAX_SHOWN = 2
BANDIT_SITE = "runbook_offer"          # 75.5: arms "offer" (show the matched runbook) / "skip" (let the model plan alone)
OUTCOME_EMA = 0.3                      # utility moves 30% toward the outcome (1 followed-and-done, 0 failed)


def _key(session_id: str, title: str) -> str:
    return "runbook_of:" + hashlib.sha1(f"{session_id}|{title}".encode("utf-8")).hexdigest()[:12]


def _step_tools(step_index: int, receipts: List[dict]) -> tuple:
    """Tools and files the receipts consumed by this step recorded — the WORLD's account of the step."""
    mine = [r for r in receipts if r.get("consumed_by") == step_index and r.get("status") == "ok"]
    tools = sorted({r["tool"] for r in mine})
    files = sorted({os.path.basename(f.get("path", "")) for r in mine for f in (r.get("effects") or {}).get("files", []) if f.get("path")})
    return tools, files


def render_runbook_text(plan: dict, receipts: List[dict]) -> str:
    lines = []
    for i, s in enumerate(plan.get("steps", [])):
        tools, files = _step_tools(i, receipts)
        mark = {"done": "✓", "failed": "✗"}.get(s.get("status"), "·")
        extra = (" [" + ", ".join(tools) + "]" if tools else "") + (" → " + ", ".join(files) if files else "")
        lines.append(f"{i + 1}. {mark} {s.get('text', '')}{extra}")
    return "\n".join(lines)


def task_text(title: str, request: str, steps: List[str], phrases: List[str]) -> str:
    """What a runbook is ABOUT, for matching: the task title, the user's own request(s) in their language, the steps."""
    parts = [title] + ([request] if request else []) + phrases + steps
    return "\n".join(p for p in parts if p)


def learn_request_phrase(engine, rb: MemoryPoint, phrase: str, title: str, request: str, steps: List[str]) -> bool:
    """75.1b: a followed runbook absorbs the request that led to its reuse when the embedding does not cover it yet
    (multilingual self-growth — the Phase 56 tool-phrase rule, same cap and novelty threshold)."""
    phrase = " ".join((phrase or "").split())[:120]
    if len(phrase) < 8 or phrase.lower() == (request or "").lower():
        return False
    existing = tool_phrases(rb)
    if any(p.lower() == phrase.lower() for p in existing):
        return False
    if fu_math.cosine(engine.embed(phrase), rb.embedding) >= PHRASE_NOVELTY_MAX_COSINE:
        return False
    phrases = (existing + [phrase])[-MAX_USAGE_PHRASES:]
    rb.keywords = [k for k in rb.keywords if not k.startswith(_PHRASE_PREFIX)] + [_PHRASE_PREFIX + p for p in phrases]
    rb.embedding = engine.embed(task_text(title, request, steps, phrases))
    return True


def existing_runbook(engine, key: str) -> Optional[MemoryPoint]:
    return next((p for p in engine.graph.points.values() if p.type == RUNBOOK_TYPE and key in p.keywords), None)


def on_plan_finalized(engine, session_id: str, plan: dict) -> Optional[MemoryPoint]:
    """Derive (or refresh) the runbook of a finalized plan; move a hinted runbook's utility with the outcome."""
    if plan.get("status") not in ("done", "partial", "failed") or not plan.get("steps"):
        return None
    receipts = engine.receipts.for_session(session_id) if getattr(engine, "receipts", None) is not None else []
    title = (plan.get("title") or "plan")[:80]
    body = render_runbook_text(plan, receipts)
    tools_used = sorted(set(plan.get("tools_used", [])) | {r["tool"] for r in receipts if r.get("consumed_by") is not None})
    request = (plan.get("request") or "")[:300]
    content = f"Runbook: {title}\nOutcome: {plan['status']}" + (f"\nAsked as: {request}" if request else "") + f"\n{body}"
    key = _key(session_id, title)
    step_texts = [s.get("text", "") for s in plan["steps"]]
    rb = existing_runbook(engine, key)
    if rb is None:
        rb = MemoryPoint(type=RUNBOOK_TYPE, title=title, content=content, summary=f"{title} — {plan['status']}",
                         source="system", embedding=engine.embed(task_text(title, request, step_texts, [])),
                         keywords=["_runbook", key, f"plan_session:{session_id}"] + [f"tool:{t}" for t in tools_used]
                         + [f"receipt:{r['id']}" for r in receipts if r.get("consumed_by") is not None][:24],
                         entities=[], topics=["runbook"], importance=0.7, utility=0.6 if plan["status"] == "done" else 0.4,
                         confidence=1.0, density=0.3, energy=0.5, layer="L2_project")
        if request:
            rb.keywords.append("request:" + request[:120])
    else:
        rb.content, rb.summary = content, f"{title} — {plan['status']}"
        rb.timestamp = now_iso()
    rb.keywords = sorted(set(rb.keywords) | {f"outcome:{plan['status']}"} - {f"outcome:{o}" for o in ("done", "partial", "failed") if o != plan["status"]})
    engine.graph.save_point(rb)
    plan["runbook_id"] = rb.id
    site_arm = plan.get("bandit")
    if site_arm and getattr(engine, "bandit", None) is not None:      # 75.5: the outcome pays the arm that was chosen
        target = 1.0 if plan["status"] == "done" else (0.5 if plan["status"] == "partial" else 0.0)
        engine.bandit.reward(site_arm[0], site_arm[1], target)
    hint = plan.get("runbook_hint")
    if hint and hint != rb.id:
        src = engine.graph.points.get(hint)
        if src is not None:
            target = 1.0 if plan["status"] == "done" else (0.5 if plan["status"] == "partial" else 0.0)
            src.utility = fu_math.clamp(src.utility + OUTCOME_EMA * (target - src.utility))
            src.access_count += 1
            src.keywords = sorted(set(src.keywords) | {f"followed:{plan['status']}"})
            if plan["status"] == "done" and request:      # 75.1b: learn the phrasing that led to the reuse
                src_request = next((k[8:] for k in src.keywords if k.startswith("request:")), "")
                src_steps = [ln.split(" ", 2)[-1].split(" [")[0] for ln in src.content.splitlines() if ln[:1].isdigit()]
                learn_request_phrase(engine, src, request, src.title, src_request, src_steps)
            engine.graph.save_point(src)
    log.info("runbook %s for plan '%s' (%s)", rb.id, title, plan["status"])
    return rb


def match_runbooks(engine, query: QueryPoint, floor: float, limit: int = MAX_SHOWN) -> List[tuple]:
    """Runbooks whose TASK resembles the current request (cosine of title+steps vs the request)."""
    if not query.embedding:
        return []
    # 75.1b: the floor is a SIMILARITY floor (cosine, the 74.5 rule); the RANK is memory scoring's own relevance
    # definition — 0.75 cosine + 0.25 literal overlap — so a shared task word ("links") breaks ties that
    # cross-lingual cosine alone gets wrong among near-identical tasks.
    scored = []
    for p in engine.graph.points.values():
        if p.type != RUNBOOK_TYPE or p.status != "active" or not p.embedding:
            continue
        cos = fu_math.cosine(query.embedding, p.embedding)
        if cos < floor:
            continue
        scored.append((0.75 * cos + 0.25 * fu_math.lexical_relevance(query.text, p.content), p))
    scored.sort(key=lambda t: (-t[0], -t[1].utility))
    return scored[:limit]


def render_block(matches: List[tuple]) -> str:
    if not matches:
        return ""
    out = ["=== RUNBOOKS (proven sequences from earlier plans in THIS memory — reuse when the task fits) ==="]
    for score, p in matches:
        out.append(f"[{(p.timestamp or '')[:10]} · {p.summary} · match {score:.2f}]\n{p.content}")
    out.append("If one fits, propose ITS steps (adapted) as the plan instead of inventing a new sequence.")
    return "\n".join(out)


def runbooks_for_turn(engine, query: QueryPoint) -> str:
    """Turn-start hook: the block to add to the system prompt ('' when nothing fits or the feature is off)."""
    engine._turn_runbooks_shown = []
    if not engine.settings.get("runbooks_enabled"):
        return ""
    from .retrieve import user_fact_question
    if user_fact_question(query, engine.facts):            # a question about the user is never a task to re-run
        return ""
    matches = match_runbooks(engine, query, float(engine.settings.get("runbook_match_floor")))
    if not matches:
        return ""
    # 75.5: with the bandit ON, offering the runbook is a CHOICE learned from outcomes (plan followed to done or not);
    # the arm is recorded on the plan proposed this turn and rewarded when that plan finalizes.
    arm = engine.bandit.choose(BANDIT_SITE, ["offer", "skip"], default="offer",
                               enabled=bool(engine.settings.get("bandit_enabled"))) if getattr(engine, "bandit", None) else "offer"
    engine._turn_bandit = (BANDIT_SITE, arm) if engine.settings.get("bandit_enabled") else None
    if arm == "skip":
        engine._emit({"type": "runbooks", "items": [], "skipped_by_bandit": True})
        return ""
    engine._turn_runbooks_shown = [p.id for _, p in matches]
    engine._emit({"type": "runbooks", "items": [{"id": p.id, "title": p.title, "outcome": p.summary,
                                                 "match": round(s, 3)} for s, p in matches]})
    return render_block(matches)


def list_runbooks(engine) -> List[dict]:
    return [{"id": p.id, "title": p.title, "summary": p.summary, "utility": round(p.utility, 3), "timestamp": p.timestamp,
             "followed": p.access_count, "content": p.content}
            for p in sorted((p for p in engine.graph.points.values() if p.type == RUNBOOK_TYPE and p.status == "active"),
                            key=lambda p: p.timestamp, reverse=True)]
