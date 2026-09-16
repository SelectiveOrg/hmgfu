"""Phase 73.2(a) — the post-reply TAIL of an agent turn: ingest + reinforce + ontology nodes + grader + mini-dream +
persistence. Moved out of agent.py (module ceiling) and made schedulable.

Why: after the reply is shown, a turn still spends 3–6.5 s ingesting (nano extractions, embeddings) and up to 5 s in a
mini-dream — time the HTTP caller and the NEXT turn's engine lock both wait for. With `tail_async` (a documented
setting, default OFF) the transcript is persisted immediately, the reply returns, and the tail runs on a worker thread;
the next turn JOINS the previous tail before it touches the graph (`wait_for_tail`), so the graph a turn reads is always
complete — the overlap is the user's own reading/typing time. The stored metadata is patched with the grade and the
full timings when the tail finishes; `grade` / `mini_dream` are None in the async response and arrive as events.
The tail reads only session-keyed state (never `engine._turn_*`), which is what makes this safe.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

log = logging.getLogger("hmgfu.turn_tail")


@dataclass
class TailContext:
    """Snapshot of everything the tail needs — taken while the turn state is still this turn's."""
    sid: str
    turn_seq: int
    user_message: str
    source: str
    fact_changes: list
    raw_reply: str
    reply: str
    retrieved: list
    tool_trace: list
    query: Any
    mem_items: list
    grounding: Any
    saydo: Any
    thoughts: List[str]
    plan: Any
    timer: Any
    emit: Optional[Callable[[dict], None]] = None
    extraction: dict = field(default_factory=dict)
    embedding: list = field(default_factory=list)
    held: list = field(default_factory=list)       # 95.46: slots the protocol asked about this turn

    def send(self, event: dict) -> None:
        if self.emit is None:
            return
        try:
            self.emit(event)
        except Exception as exc:                       # a closed socket must never break the tail
            log.debug("tail emit dropped: %s", exc)


ROUTE_FIELDS = ("conversation_act", "feedback_polarity", "action_requested", "requested_tools", "freshness", "needs_memory",
                "runtime_context_keys", "runtime_context_sufficient", "directive", "route_source")


def enrich_for_ingest(engine, extraction: dict, text: str) -> dict:
    """80.2: when `nano_in_tail` is on and the pre-reply extraction was heuristic, run the nano ONCE now (route off) and
    keep the turn's ROUTE fields from the pre-reply extraction; the stored point gets the nano's title / summary / type /
    keywords / entities / topics / emotion. Any failure → the heuristic extraction stands (never a crash)."""
    settings = getattr(engine, "settings", None)
    if settings is None or not settings.get("nano_in_tail") or not extraction \
            or not str(extraction.get("extractor", "")).startswith("heuristic"):
        return extraction
    try:
        full = engine.sensitizer.extract(text, route=False)
    except Exception as exc:
        log.warning("tail nano extraction failed (%s); heuristic fields stand", exc)
        return extraction
    if not full or str(full.get("extractor", "")) != "nano":
        return extraction
    merged = dict(full)
    for key in ROUTE_FIELDS:
        if key in extraction:
            merged[key] = extraction[key]
    merged["extractor"] = "nano"
    return merged


def _ingest_and_learn(engine, c: TailContext) -> None:
    from .learning_hooks import confirm_recovered_route
    from .taxonomy import mirror_directive_nodes, remember_turn_tools, store_reflection, upsert_session_node
    extraction = enrich_for_ingest(engine, c.extraction or {}, c.user_message)     # 80.2: the nano runs here when configured
    user_point = engine.ingest(c.user_message, source=c.source, extracted=extraction or None,
                               embedding=c.embedding or None)       # 73.2: the routing extraction IS the message's
    fact_changes = list(c.fact_changes)
    if engine.settings.get("fact_mapper_mode") == "spans":          # 84.3/84.4: the span extractor, AFTER the reply
        from .fact_spans import apply_spans, registry_span_extractor
        extractor = registry_span_extractor(engine.registry, engine.settings.get("fact_mapper_role") or "nano")
        try:
            fact_changes += apply_spans(engine.facts, c.user_message, c.source, extractor,
                                        skip_keys=[ch["key"] for ch in c.fact_changes if ch.get("key")] + list(c.held or []),   # 95.46
                                        skip_values=[ch.get("value") for ch in c.fact_changes if ch.get("value")])   # 90.G2
        except Exception as exc:                                    # advisory: never breaks the tail
            log.warning("span extractor in the tail failed (%s)", exc)
    for ch in fact_changes:
        if ch.get("key"):
            engine.facts.link_source(ch["key"], user_point.id)     # P1 provenance, every fact
    engine._store_assistant_reply(c.raw_reply, c.retrieved)         # 65.4: trivia/jokes never enter memory
    if getattr(engine, "_turn_superseded", False):                   # 95.22: the turn's OWN points were born after
        from .facts import supersede_stale_nodes                     # the pre-reply demotion (L4: a step narration
        supersede_stale_nodes(engine.facts, engine.graph)            # "from Nimbus" stayed active) -- same rule, once more
    engine.reinforce(c.retrieved)
    engine._reinforce_used_tools(c.tool_trace, user_point)
    upsert_session_node(engine, c.sid, user_point)                  # ontology nodes (Phase 43)
    if c.thoughts:
        store_reflection(engine, c.thoughts, user_point)
    mirror_directive_nodes(engine)
    remember_turn_tools(engine, c.sid, c.tool_trace)
    confirm_recovered_route(engine, c.query, c.user_message, c.tool_trace)   # Phase 56 router learning


def _grade(engine, c: TailContext):
    if not engine.settings.get("grader_enabled"):
        return None
    try:
        from .grader import grade_turn
        return grade_turn(engine, c.user_message, c.reply, c.retrieved, c.tool_trace, query=c.query)
    except Exception as exc:
        log.warning("grader failed (non-fatal): %s", exc)
        return None


def _dream(engine):
    from .learning_hooks import maybe_schedule_full_dream
    mini_report = None
    if engine._should_run_mini_dream():
        from .dream import mini_dream_loop, unresolved_tension_count
        mini_report = mini_dream_loop(engine.graph, engine.sensitizer)
        engine.learned_params.set_bounded("state:tension_seen", unresolved_tension_count(engine.graph), 0, 10**6)
    maybe_schedule_full_dream(engine)                               # full self-organisation, background (Phase 56)
    return mini_report


def metadata_for(c: TailContext, grade, timings) -> dict:
    """The PA3 metadata contract for the stored assistant message."""
    return {
        "tool_calls": [{"name": t["name"], "arguments": t["arguments"], "result": t["result"][:800],
                        "failed": t["failed"], "blocked": t.get("blocked", False)} for t in c.tool_trace],
        "memory_count": len(c.retrieved), "memory_items": c.mem_items, "grade": grade,
        "grounding": c.grounding, "plan": c.plan, "saydo": c.saydo,
        "thinking": "\n\n".join(c.thoughts)[:4000] or None, "timings": timings,
    }


def run_tail(engine, c: TailContext) -> tuple:
    """The tail itself, synchronous. Returns (grade, mini_report, timings)."""
    _ingest_and_learn(engine, c)
    c.timer.mark("ingest")
    grade = _grade(engine, c)
    c.timer.mark("grade")
    mini_report = _dream(engine)
    c.timer.mark("dream")
    timings = c.timer.finish()
    c.send({"type": "turn_timings", "turn_seq": c.turn_seq, **{k: v for k, v in timings.items() if k != "detail"}})
    if grade is not None:
        c.send({"type": "grade", "turn_seq": c.turn_seq, **grade})
    engine._maybe_drain_corrections()                               # FRONT 2: deferred corrections, GPU free
    from .db import commit_open_transactions
    commit_open_transactions(engine, "end of tail")                 # 73.4: nor into the next turn
    return grade, mini_report, timings


def finish_turn(engine, c: TailContext) -> tuple:
    """Default: run the tail, then persist. `tail_async`: persist now, run the tail on a worker, patch metadata after."""
    from .db import commit_open_transactions
    commit_open_transactions(engine, "end of reply")            # 73.4: no store may carry a write lock into the tail
    if not engine.settings.get("tail_async"):
        grade, mini_report, timings = run_tail(engine, c)
        engine.sessions.save_message(c.sid, "user", c.user_message, c.turn_seq)
        engine.sessions.save_message(c.sid, "assistant", c.reply, c.turn_seq, metadata=metadata_for(c, grade, timings))
        return grade, mini_report, timings
    timings = {**c.timer.finish(), "tail": "pending"}
    engine.sessions.save_message(c.sid, "user", c.user_message, c.turn_seq)
    engine.sessions.save_message(c.sid, "assistant", c.reply, c.turn_seq, metadata=metadata_for(c, None, timings))

    def worker():
        try:
            c.timer.adopt_thread()                                   # the tail's model calls count for this turn
            grade, _mini, full = run_tail(engine, c)
            engine.sessions.update_metadata(c.sid, c.turn_seq, {"grade": grade, "timings": {**full, "tail": "done"}})
        except Exception as exc:
            log.warning("turn tail failed (non-fatal, turn %s): %s", c.turn_seq, exc)

    thread = threading.Thread(target=worker, name=f"tail-{c.sid[:6]}-{c.turn_seq}", daemon=True)
    engine._tail_thread = thread
    thread.start()
    return None, None, timings


def wait_for_tail(engine, timeout: Optional[float] = None) -> bool:
    """Join the previous turn's tail (if any) so the graph a new turn reads is complete. True if one was waited for."""
    thread = getattr(engine, "_tail_thread", None)
    if thread is not None and thread.is_alive():
        thread.join(timeout)
        return True
    return False
