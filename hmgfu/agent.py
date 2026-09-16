"""AgentEngine — the agentic master cycle: HMG-Fu memory + tool calling + PA3-proven guards.

Extends HMGFuEngine (v1 chat stays intact for plain /api/chat). One turn:
  retrieve memories + retrieve tools (both = HMG retrieval) → provider chat with tools →
  tool loop (guards: 2-strike block, stuck-loop, max iterations, forced finalization) →
  ingest + reinforce → grade (post-turn, fail-soft) → optional mini-dream.
"""

from __future__ import annotations

import json
import logging
import threading
from collections import deque
from typing import List, Optional

from . import config, fu_math
from .chat import HMGFuEngine, _SYSTEM_PROMPT
from .taxonomy import apply_user_feedback, category_of, node_class
from .models import now_iso
from .plans import iteration_budget
from .prompts import _AGENT_PROMPT_EXTRA, workspace_block
from .turn_events import emit_context_pack, memory_items, plan_enumerated_request, plan_turn_actions, turn_response
from .turn_timing import TurnTimer, instrument_engine
from .turn_tail import TailContext, finish_turn, wait_for_tail
from .thinking import (extract_thinking, narrate_tool_calls,  # noqa: F401 (re-export)
                       thinking_directive)
from .tool_protocol import parse_protocol_tool_call, render_tool_protocol  # noqa: F401
from .providers import ProviderError, ProviderRegistry
from .retrieve import build_llm_context, user_fact_question
from .sessions import SessionStore
from .settings import Settings
from .toolsys import (ToolRegistry, classify_tool_result, retrieve_tools_for_turn,
                      sync_tool_points, tool_signature)

log = logging.getLogger("hmgfu.agent")

class AgentEngine(HMGFuEngine):
    """HMGFuEngine + providers + tools + grader. The v2 front door."""

    def __init__(self, db_path: Optional[str] = None, client=None):
        super().__init__(db_path=db_path, client=client)
        self.settings = Settings(db_path or config.DB_PATH)
        self.registry = ProviderRegistry(self.settings, self.client)
        self.sensitizer.bind_role_chat(self.registry.chat_for_role)
        self.tools = ToolRegistry(engine=self)
        self.sensitizer.bind_action_catalog(self.tools)
        self.sessions = SessionStore(db_path or config.DB_PATH)
        from .directives import DirectiveStore
        self.directives = DirectiveStore(db_path or config.DB_PATH)
        # give the router the active directives so it can reason about a CHANGE/STOP of one (Phase 55)
        self.sensitizer.bind_directives(self.directives.active)
        self.sensitizer.bind_learning_examples(self)   # 92.E5: confirmed meanings, adapt only
            # routing-exemplar memory (Phase 56): confirmed misroute corrections become per-turn few-shots
        from .learning_hooks import init_route_learning
        init_route_learning(self, db_path)
        from .facts import FactStore
        self.facts = FactStore(db_path or config.DB_PATH)
        from .session_plans import SessionPlanStore
        self.session_plans = SessionPlanStore(db_path or config.DB_PATH)   # 67.3 plans outlive the turn
        from .receipts import ReceiptStore
        self.receipts = ReceiptStore(db_path or config.DB_PATH)            # 71: every action leaves a receipt
        from .prospective import ProspectiveStore
        self.prospective = ProspectiveStore(db_path or config.DB_PATH)      # 75.2: reminders by time / condition
        from .bandit import Bandit
        self.bandit = Bandit(self.learned_params)                           # 75.5: outcome-driven choice, bounded (base ctor made learned_params)
        from .slots import registry_mapper
        self.facts.bind_mapper(registry_mapper(self.registry))   # Phase 62: closed-slot model mapper
        from .pre_router import pre_route
        from .knn_router import make_knn_pre_router
        _knn = make_knn_pre_router(self)                         # 89.1: setting-gated, OFF by default; advisory
        def _pre(text):                                          # 79.3: deterministic pre-router, setting-gated, OFF by default
            route = _knn(text)                                   # 89.1: the nearest-exemplar router first, when enabled
            if route is not None:
                return route
            if not self.settings.get("router_bypass_enabled"):
                return None
            route = pre_route(text, list(self.sensitizer._action_catalog()), self.facts)
            if route is not None and self.settings.get("bypass_skips_nano"):
                route = dict(route, skip_nano=True)                # 79.6: heuristic extraction, no nano call either
            return route
        self.sensitizer.bind_pre_router(_pre)
        instrument_engine(self)                                  # 73.0: every model call is ledgered
            # Phase 62 dream clock: the turn counter survives restarts (it reset to 0 on every process start,
            # so the full dream effectively never ran)
        self._restore_turn_count()
        from .hygiene import repair_memory_provenance
        repair = repair_memory_provenance(self)
        if any(repair.values()):
            log.info("startup memory provenance repair: %s", repair)
            # H-01: turn context (_turn_session/_turn_emit/_turn_plan/…) is ENGINE-GLOBAL, so two
            # concurrent turns would stomp each other. One local model runs one turn at a time; the
            # lock makes that explicit (Rule 13: the real constraint).
        self._turn_lock = threading.Lock()
        self._turn_session: Optional[str] = None; self._turn_emit = None
        self._turn_plan: Optional[dict] = None
        self._apply_nano_gates()   # reconcile persisted flags -> config AT INIT: a restart must not leave the Regulator/observation window disarmed until the first retrieve (P0.2 finding)
        self._turn_files: list = []; self._turn_evidence: list = []   # 94.2: outcomes, for published values
        self._turn_url: Optional[str] = None
        self._turn_thoughts: list = []
        if self.settings.get("tool_points_enabled") and self.client.available():
            try:
                sync_tool_points(self.tools, self)
            except Exception as exc:   # fail-soft: tools still callable without points
                log.warning("tool point sync failed: %s", exc)

    # --- live settings application (Rule 10: every knob visible in /api/settings) -----

    def _apply_nano_gates(self) -> None:
        self.sensitizer.extract_enabled = self.settings.get("nano_sensitizer_enabled")
        self.sensitizer.dream_enabled = self.settings.get("nano_dream_enabled")
        config.reconcile_flags(self.settings)   # settings -> live config feature flags (env wins, Rule 10)
        from .tool_builtins import set_workspace; set_workspace(self.settings.get("workspace_dir"))

    def _tool_cap(self, query, user_message: str) -> int:
        """66.6: a plain question sees the smaller tool set unless the user named a tool."""
        named = any(n.lower() in user_message.lower() for n in self.tools.schemas)
        if query.conversation_act == "question" and not named:
            return self.settings.get("question_max_tools")
        return self.settings.get("max_tools_per_turn")

    def _restore_turn_count(self) -> None:
        self.turn_count = int(self.learned_params.get("state:turn_count", 0))

    def embed(self, text: str) -> List[float]:
        """Embedding model/provider is a live setting, just like the four chat roles. 89.1/89.2: a one-entry memo so the
        turn's text is embedded ONCE when the kNN router and retrieval both ask for it — even while the first call is in flight."""
        memo = getattr(self, "_embed_memo", None)
        if memo is None:
            from .embed_memo import EmbedMemo
            memo = self._embed_memo = EmbedMemo()   # 89.2: shares an in-flight embedding across threads (retrieval || router)
        return memo(text, self.registry.embed_for_role)

    def retrieve(self, text: str, **overrides) -> tuple:
        self._apply_nano_gates()
        overrides.setdefault("limit", self.settings.get("retrieval_limit"))
        overrides.setdefault("min_score", self.settings.get("retrieval_min_score"))
        overrides.setdefault("expansion_depth", self.settings.get("expansion_depth"))
        return super().retrieve(text, **overrides)

    def dream(self):
        self._apply_nano_gates()
        report = super().dream()
        from .hygiene import hygiene_pass
        hygiene = hygiene_pass(self)          # retroactive cleanup every full dream
        report.summary += " · hygiene: " + ", ".join(f"{k}={v}" for k, v in hygiene.items() if v)
        self.graph.save_dream_report(report)
        return report

    def _should_run_mini_dream(self) -> bool:
        every = self.settings.get("mini_dream_every_n_turns")
        if every > 0 and self.turn_count > 0 and self.turn_count % every == 0:
            return True
            # tension trigger fires only when unresolved tension GREW since the last mini-dream: production
            # had 133 stale tension edges, so the old ">trigger" check fired EVERY turn
        from .dream import unresolved_tension_count
        n = unresolved_tension_count(self.graph)
        return n > config.MINI_DREAM_TENSION_TRIGGER and n > self.learned_params.get("state:tension_seen", 0)

    # --- events + widgets --------------------------------------------------------

    def _emit(self, event: dict) -> None:
        if self._turn_emit is not None:
            try:
                self._turn_emit(event)
            except Exception as exc:
                log.warning("event emit failed: %s", exc)

    def widget_action(self, action: str, args: dict) -> dict:
        from .widgets import widget_action
        return widget_action(self, action, args)

    def _supersede_stale_fact_nodes(self, user_message: str = "", learning=None):
        from .fact_nodes import demote_after_supersession          # 95.18: canonical AND definition revisions
        demote_after_supersession(self, user_message, learning)

    def _record_artifacts(self, name: str, outcome: str) -> None:
        from .widgets import record_turn_artifact
        record_turn_artifact(self, name, outcome)

    def agent_chat(self, user_message: str, explicit: bool = False,
                   session_id: Optional[str] = None, emit=None) -> dict:
        sid = self.sessions.ensure_session(session_id)
            # one turn at a time across the engine (H-01): shared turn-state is not concurrency-safe
        if not self._turn_lock.acquire(blocking=False):
            return {"response": "(a turn is already running — wait for it to finish)",
                    "session_id": sid, "error": "busy", "retrieved": [], "tool_trace": []}
        try:
            return self._agent_chat_locked(user_message, explicit, sid, emit)
        finally:
            self._turn_lock.release()

    def _agent_chat_locked(self, user_message: str, explicit: bool,
                           sid: str, emit) -> dict:
        wait_for_tail(self)                            # 73.2(a): the previous turn's tail completes first
        self.turn_count += 1
        self.learned_params.set_bounded("state:turn_count", self.turn_count, 0, 10**9)
        turn_seq = self.sessions.next_turn_seq(sid)
        self._turn_session, self._turn_emit, self._turn_plan = sid, emit, None
        self._turn_files, self._turn_url, self._turn_evidence = [], None, []   # widget arg coverage
        self._turn_user_message = user_message         # 62.14: back-fills a missing single required arg
        self._turn_runtime = None                      # 66.3: deixis completion reads the turn clock
        self._turn_seq = turn_seq
        timer = TurnTimer(self)                        # 73.0: stage marks + model-call ledger for this turn
        from .utterance import past_cue
        from .session_plans import begin_turn
        pinned = begin_turn(self, sid, user_message)   # 67.3: approval / resume / pending proposal
        self._turn_thoughts = []                       # reasoning blocks (persisted for restore)
        self._emit({"type": "status", "text": "Recalling memories", "turn_seq": turn_seq})
        from .runtime_context import RuntimeContext
        runtime = RuntimeContext.capture()
        self._turn_runtime = runtime
        from .prospective import begin_turn as prospective_begin_turn
        prospective_block = prospective_begin_turn(self, sid, user_message, runtime, turn_seq)   # 75.2: due + new
        memory_actions = {"memory_search", "memory_timeline", "memory_zoom"}
        from .query_depth import depth_for
        query, retrieved, retrieval_ms = self.retrieve(
            user_message, limit=depth_for(user_message, self.settings), runtime_context=runtime      # 86.1: deeper on aggregation questions
        )
        # Snapshot the ROUTER's own tool pins BEFORE retrieve_tools_for_turn's semantic recovery can
        # spuriously add one — the echo-guard needs the router's genuine signal (bench L24). See ROADMAP.
        timer.mark("retrieve")
        router_pinned_tools = list(query.requested_tools or [])
        tool_schemas = retrieve_tools_for_turn(
            self.tools, self, query,
            max_tools=self._tool_cap(query, user_message),               # 66.6 intent-conditioned
        ) if self.settings.get("tool_points_enabled") else []
        from .session_plans import ensure_step_tools; tool_schemas = ensure_step_tools(self, self._turn_plan, tool_schemas)   # 67.12 step tool offered+required
        from .runbooks import runbooks_for_turn
        runbook_block = runbooks_for_turn(self, query) if self._turn_plan is None else ""   # 75.1: proven sequences
        offered_names = [t["name"] for t in tool_schemas]
        requested_actions, forced_actions, retrieved = plan_turn_actions(
            self, query, user_message, offered_names, retrieved)          # 65.2 / 66.5 / 66.6
        pinned, tool_schemas, forced_actions = plan_enumerated_request(self, user_message, tool_schemas, forced_actions, pinned)   # 95.54b
        mem_items = memory_items(retrieved)
        self._emit({"type": "memory_used", "turn_seq": turn_seq, "count": len(retrieved),
                    "items": mem_items, "retrieval_ms": round(retrieval_ms, 1)})
        # first-class facts + directives take effect THIS turn: literal keyed value, new
        # supersedes old, stale-value nodes demoted, injected verbatim at the front.
        source = "user_explicit" if explicit else "user"
        from .directives import is_blocked_directive_change
        # Echo-guard uses a GENUINE tool request (router's raw pins ∩ offered), NOT the fallback-
        # forced action flag: a directive-set pins no tool, so the flag wrongly blocked it (L24).
        genuine_tool_turn = bool([n for n in router_pinned_tools if n in offered_names])
        directive_change = None if is_blocked_directive_change(
            query.directive, self.directives.active(), genuine_tool_turn,
            query.conversation_act, text=user_message,                  # 73.4: a new standing rule must read as one
        ) else self.directives.apply(user_message, source, detected=query.directive)
        self.facts.open_slot_regex_writes = bool(self.settings.get("open_slot_regex_writes"))   # 84.2
        self.facts.use_mapper = self.settings.get("fact_mapper_mode") == "fallback"              # 84.3: spans run in the tail
        # 92.E4: BEFORE the reply context, so a confirmation is consumed against its own snapshot;
        # None when the mode is off (arm S): no table, no change.
        from .learning_hooks import DEFINITION_RELATION, ask_pending_question, run_learning_turn
        learning = run_learning_turn(self, sid, user_message, query, source=source,
                                     turn_id=str(turn_seq), plan_pending=bool(self._turn_plan))
        if learning:
            self._emit({"type": "learning", "turn_seq": turn_seq, "receipt": learning["receipt"], "action": learning["decision"]["action"], "case_id": learning.get("case_id"),
                        "reason": learning["decision"].get("reason"), "envelope": (query.extraction or {}).get("memory_update")})   # 95.49: attribution needs the perceiver's envelope
        dec = (learning or {}).get("decision") or {}; held = [r for r in (dec.get("blocked_proposals") or []) if r] if dec.get("action") == "ask" else []   # 95.46
        fact_changes = self.facts.apply_all(user_message, source, session=sid, hold_keys=held)   # 62.10; 91.W2; 95.46
        fact_change = fact_changes[0] if fact_changes else None
        from .fact_nodes import has_supersession; self._turn_superseded = has_supersession(fact_changes, learning)   # 95.22: the tail demotes once more
        if self._turn_superseded: self._supersede_stale_fact_nodes(user_message, learning)
        # learning loop: THIS message may be feedback on the PREVIOUS turn's tools (user grades, never self — Phase 43). Router-semantic polarity decides (Phase 56); efficiency-weighted.
        tool_feedback = apply_user_feedback(self, sid, user_message, query=query)
        if tool_feedback:
            self._emit({"type": "tool_feedback", "turn_seq": turn_seq, **tool_feedback})
        context, _ = build_llm_context(query, self.graph, retrieved=retrieved,
                                       token_budget=self.settings.get("token_budget"),
                                       canonical=self.facts.render_lines()   # 92.E5R: + what was DEFINED
                                       + self.facts.assertions.render_definition_lines(DEFINITION_RELATION)
                                       + (self.facts.render_history_lines()
                                          if past_cue(user_message) else []),   # 72.3
                                       superseded=self.facts.superseded_values(),
                                       reverted=self.facts.reverted_values(),          # 72.6g: rolled-back probe values
                                       echo_free=user_fact_question(query, self.facts),   # 73.3: the user's own words answer
                                       regulator=self.regulator if config.REGULATOR_ENABLED else None,
                                       excerpt_chars=self.settings.get("excerpt_max_chars"),          # 78.2
                                       echo_scope=self.settings.get("echo_guard_scope"),              # 78.3
                                       echo_pairs=self.facts.active_pairs())
        provider, chat_model = self.registry.resolve("chat")
        native = provider.supports_native_tools
            # Phase 58 — unified thinking: native reasoning via the Ollama `think` param for any
            # thinking-capable model, disabled on action turns so it never buries the tool call.
        from .thinking import turn_thinking
        turn_think, directive = turn_thinking(self.settings.get("thinking_mode"),
                                              bool(requested_actions), provider, chat_model, self.client)
        from .speech_act import refers_to_workspace
        from .tool_builtins import get_workspace
        from .turn_events import recent_window
        from .operational_state import record_operations, state_block   # 93.D: verified state
        system = _SYSTEM_PROMPT + _AGENT_PROMPT_EXTRA + directive \
            + ("\n\n" + state_block(self, sid)) \
            + ("\n\n" + pinned if pinned else "") \
            + ("\n\n" + runbook_block if runbook_block else "") \
            + ("\n\n" + prospective_block if prospective_block else "") \
            + "\n\n" + runtime.prompt_block() + "\n\n" + context \
            + recent_window(self, sid, self.settings.get("recent_turns_window"))
        if refers_to_workspace(user_message) or self._turn_plan is not None:   # 67.6 scoped
            system += workspace_block(get_workspace(), user_message)   # 95.33: a named small file is shown
        if tool_schemas and not native:
            system += "\n" + render_tool_protocol(tool_schemas)
            # The conversation_opener is applied ONLY by the deterministic enforce() below, NEVER
            # injected into the prompt: an opener instruction forces text-generation mode, where the
            # model tells a joke and then skips the requested action (L6) or answers a substantive
            # turn with ONLY the joke (L17). render_block still emits output_prefix/suffix.
        system += self.directives.render_block(first_turn=False,
                                               suppress_generated=bool(requested_actions),
                                               tool_names=list(self.tools.schemas))
        emit_context_pack(self, query, tool_schemas, turn_seq)   # Phase 47 visibility (turn_events)
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ]
        timer.mark("prepare")
        reply, tool_trace, finalized = self._tool_loop(
            messages, tool_schemas, native, turn_seq=turn_seq,
            required_actions=forced_actions, think=turn_think,
        )
        reply, _ = extract_thinking(reply)       # reasoning already emitted per-iteration
        timer.mark("chat")
        from .widgets import auto_serve_built_apps, materialize_reply_artifacts   # 69.1 boundary
        tool_trace = tool_trace + materialize_reply_artifacts(self, user_message, reply)   # 70.7: a receipt
        from .saydo import enforce as saydo_enforce, keep_guarantee, transactions_of   # 67.2: claims are contracts
        def _rerun(instruction, required=None):
            r2, t2, _ = self._tool_loop(messages + [{"role": "assistant", "content": reply},
                                                    {"role": "user", "content": instruction}],
                                        tool_schemas, native, turn_seq=turn_seq, think=turn_think,
                                        required_actions=required)
            return extract_thinking(r2)[0], tool_trace + t2
        tx = transactions_of(tool_trace, fact_changes, directive_change, 0, episode=True,
                             learning_effects=(learning or {}).get("effects"))        # 93.A
        record_operations(self, tx, sid, turn_seq)   # 93.R2: whose turn, in which conversation
        reply, tool_trace, _saydo = saydo_enforce(  # episode=True: the user message is ingested below
            self, reply, tool_trace, tx, sid, user_message, _rerun, turn_seq)
        reply = ask_pending_question(self, learning, reply, turn_seq)
        from .grounding import verify_grounding    # 66.2 → 69.3: grounding checks the FINAL reply (after any rerun)
        reply, _grounding = verify_grounding(
            self, reply, tool_trace, [t["result"] for t in tool_trace] + [context, user_message, runtime.prompt_block()],
            messages, provider, chat_model, turn_seq)
        # P4: deterministic clock-grounding — if the router said the runtime clock answers this
        # turn but the reply missed the value, re-ask once with the literal values (data-derived).
        from .runtime_context import ground_reply
        reply = ground_reply(self, reply, user_message, query, runtime, system)
        if not tool_trace:                                                    # 77.4: claim-level gate on tool-free turns
            from .grounding import verify_claims
            reply, _claims = verify_claims(self, reply, user_message, [context, runtime.prompt_block()], messages,
                                           provider, chat_model, turn_seq)
            if _claims and _grounding is None:
                _grounding = _claims
        timer.mark("gates")
        first_or_new_opener = turn_seq == 1 or bool(
            directive_change and directive_change.get("kind") == "conversation_opener"
        )
        raw_reply = reply                       # 65.4: what the MODEL said, before opener/closer
        reply = self.directives.enforce(
            reply, first_turn=first_or_new_opener,
            force_generated=bool(requested_actions),
        ); reply = keep_guarantee(reply, _saydo)   # backstop opener/closer on action turns; 95.36: saydo's suffix stands
        auto_serve_built_apps(self)   # 95.75 (P3): BEFORE the plan settles — it must be able to prove the step
        from .session_plans import end_turn
        end_turn(self, sid, tool_trace, finalized)   # 67.3: honest status, persisted, re-pinned next turn
        self._emit({"type": "text", "text": reply, "turn_seq": turn_seq})
        timer.mark_reply()

        # 73.2(a): the post-reply tail (ingest, reinforce, ontology, grader, mini-dream, persistence) lives in
        # turn_tail.py — synchronous by default; `tail_async` runs it on a worker the next turn joins first
        grade, mini_report, timings = finish_turn(self, TailContext(
            sid=sid, turn_seq=turn_seq, user_message=user_message, source=source, fact_changes=fact_changes, held=held,
            raw_reply=raw_reply, reply=reply, retrieved=retrieved, tool_trace=tool_trace, query=query,
            mem_items=mem_items, grounding=_grounding, saydo=_saydo, thoughts=list(self._turn_thoughts),
            plan=self._turn_plan, timer=timer, emit=self._turn_emit,
            extraction=query.extraction, embedding=query.embedding))
        self._emit({"type": "done", "turn_seq": turn_seq, "final_text": reply,
                    "stats": self.graph.stats()})
        self._turn_session, self._turn_emit = None, None

        return turn_response(self, reply, sid, turn_seq, context, retrieved, retrieval_ms, tool_schemas, tool_trace,
                             finalized, runtime, grade, mini_report, timings)

    # --- tool loop with guards (PA3_LESSONS #1-3) --------------------------------------

    def _tool_loop(self, messages: List[dict], tool_schemas: List[dict],
                   native: bool = True, turn_seq: int = 0,
                   required_actions: Optional[List[str]] = None, think=None) -> tuple:
        from .tool_loop import run_tool_loop
        return run_tool_loop(self, messages, tool_schemas, native, turn_seq,
                             required_actions=required_actions, think=think)

    # --- learning: used tools strengthen (Fu edges tool↔user topics) ----------------------

    def _reinforce_used_tools(self, tool_trace: List[dict], user_point) -> None:
        from .learning_hooks import reinforce_used_tools
        reinforce_used_tools(self, tool_trace, user_point)   # + usage-phrase learning (Phase 56)

    def _tool_point(self, name: str):
        for p in self.graph.points.values():
            if p.type == "skill" and f"tool:{name}" in p.keywords:
                return p
        return None
