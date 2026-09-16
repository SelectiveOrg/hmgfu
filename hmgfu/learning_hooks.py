"""Agent-side wiring of the Phase 56 learning mechanisms (kept out of agent.py — 400-line rule).

Three hooks, all gated by the visible `learning_enabled` setting:
- init: construct RouteMemory + bind the sensitizer's learned-few-shot provider;
- confirm_recovered_route: persist a semantic-recovery rescue as a routing exemplar ONLY when
  the rescued tool actually executed successfully that turn;
- maybe_schedule_full_dream: THEORY §19 'nightly reorganisation' actually scheduled (Phase 56
  root cause: 56/59 production dreams were minis — the macro/wormhole self-organisation stage
  never ran on the matured corpus because the full dream was manual-only).
"""

from __future__ import annotations

import logging
import threading

from . import config

log = logging.getLogger("hmgfu.learning_hooks")


def init_route_learning(engine, db_path=None) -> None:
    """RouteMemory + sensitizer few-shot provider (learned, per-turn, similarity-selected)."""
    from .route_memory import RouteMemory
    engine.route_memory = RouteMemory(db_path or config.DB_PATH, engine.embed)
    engine.sensitizer.bind_route_exemplars(
        lambda text: engine.route_memory.exemplars_for(text)
        if engine.settings.get("learning_enabled") else "")


def confirm_recovered_route(engine, query, user_message: str, tool_trace) -> None:
    """A rescue CONFIRMED by execution becomes a routing exemplar — the router learns the
    corrected classification instead of re-misrouting similar turns."""
    recovered = getattr(query, "recovered_action", "")
    if recovered and engine.settings.get("learning_enabled") and any(
            t.get("name") == recovered and not t.get("failed") and not t.get("blocked")
            for t in tool_trace):
        engine.route_memory.record_confirmed_recovery(user_message, "instruction", [recovered])


def reinforce_used_tools(engine, tool_trace, user_point) -> None:
    """Used tools strengthen: access/energy/utility nudge + Fu edge to the user's topic point.
    Phase 43: NO self-penalty — a technical failure is not user dissatisfaction; tool utility is
    graded ONLY by user feedback. Phase 56: a successful use also lets the tool point LEARN the
    user's phrasing (multilingual semantic coverage — see tool_points.learn_usage_phrase)."""
    if not tool_trace:
        return
    from . import fu_math
    from .ingest import build_fu_edges
    from .models import now_iso
    from .tool_points import learn_usage_phrase
    by_tool: dict = {}
    for entry in tool_trace:
        by_tool.setdefault(entry["name"], []).append(entry)
    for name, entries in by_tool.items():
        point = engine._tool_point(name)
        if point is None:
            continue
        succeeded = any(not e["failed"] and not e.get("blocked") for e in entries)
        point.access_count += 1
        point.last_accessed_at = now_iso()
        point.utility = fu_math.clamp(point.utility + (0.03 if succeeded else 0.0))
        point.energy = fu_math.clamp(point.energy + (0.15 if succeeded else 0.0))
        point.density = fu_math.compute_density(point, engine.graph.centrality(point.id))
        engine.graph.save_point(point)
        if succeeded and engine.settings.get("learning_enabled"):
            learn_usage_phrase(engine, point, user_point.content)
        if succeeded and engine.graph.edge_between(point.id, user_point.id) is None:
            for edge in build_fu_edges(point, [user_point], engine.graph):
                edge.relation_type = "skill_required"
                edge.omega = fu_math.compute_omega("skill_required")
                engine.graph.save_edge(edge)


def maybe_schedule_full_dream(engine) -> None:
    """Run the FULL dream (macros, wormholes, calibration, hygiene) in a background daemon
    thread every `full_dream_every_n_turns` turns; single-flight; 0 disables."""
    every = engine.settings.get("full_dream_every_n_turns")
    if every <= 0 or engine.turn_count == 0 or engine.turn_count % every != 0:
        return
    thread = getattr(engine, "_dream_thread", None)
    if thread is not None and thread.is_alive():
        return

    def _run():
        try:
            engine.dream()
        except Exception as exc:
            log.warning("scheduled full dream failed (non-fatal): %s", exc)

    engine._dream_thread = threading.Thread(target=_run, daemon=True, name="hmgfu-full-dream")
    engine._dream_thread.start()
    log.info("full dream scheduled in background (turn %d, every %d)", engine.turn_count, every)


def ask_pending_question(engine, learning, reply: str, turn_seq) -> str:
    """93.R4: when the protocol decided to ASK, make sure the reply carries the question, then record
    that this turn asked it.

    Both halves or neither. A case marked as having asked something the user never saw would accept a
    "yes" to a question nobody heard; a question asked and never recorded leaves the case unable to
    accept any answer at all, which is what kept the chain from closing. The question is appended only
    when the model did not ask it itself, so a natural reply is left alone."""
    if not learning or (learning.get("decision") or {}).get("action") != "ask":
        return reply
    question = str(learning.get("question") or "").strip()
    case_id = learning.get("case_id")
    if not question or not case_id:
        return reply
    out = reply if question in reply else (reply.rstrip() + "\n\n" + question)
    try:
        from .learning_state import LearningState, deliver_question
        state = LearningState(learning.get("db_path"), create=False)
        try:
            deliver_question(state, case_id, turn_id=str(turn_seq), reply=out)
        finally:
            state.close()
    except Exception as exc:                     # recording must never cost the user their answer
        log.warning("could not record the delivered question (%s)", exc)
    return out


# 93.R4: re-exported here so the turn imports its learning wiring from one place (agent.py ceiling).
from .learning_state import DEFINITION_RELATION, run_learning_turn   # noqa: E402,F401
