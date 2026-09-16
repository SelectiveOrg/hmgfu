"""Master cycle HMG_FU_MEMORY_CYCLE (THEORY §24, §25) — one engine object owns the whole stack."""

from __future__ import annotations

import logging
import time
from typing import List, Optional

from . import config, fu_math
from .dream import dream_loop, mini_dream_loop, unresolved_tension_count
from .ingest import ingest_memory
from .models import DreamReport, QueryPoint, RetrievedMemory, now_iso
from .ollama_client import OllamaClient
from .retrieve import build_llm_context, make_query_point, retrieve_memory
from .sensitizer import Sensitizer
from .store import HMGGraph

log = logging.getLogger("hmgfu.chat")

_SYSTEM_PROMPT = """You are an AI companion with a persistent relational memory (HMG-Fu).
The 'Relevant memory context' block contains what you genuinely remember about this user from
past interactions — treat it as your own memory, not as a document. Use it naturally.
If memories contradict, prefer the newer one and, when it matters, mention the change.
Be concise and warm."""


class HMGFuEngine:
    """Owns graph + sensitizer + Ollama client; every public method is one theory operation."""

    def __init__(self, db_path: Optional[str] = None, client: Optional[OllamaClient] = None):
        self.client = client or OllamaClient()
        self.graph = HMGGraph(db_path)
        nano_ok = self.client.available()
        self.sensitizer = Sensitizer(self.client, enabled=nano_ok)
        self.turn_count = 0
        # learned parameter overlay (Phase 56): retrieval reads EFFECTIVE weights (config baseline
        # × learned multiplier, stock until the grader teaches). Updates happen at the agent layer.
        from .learning import LearnedParams, WeightLearner, WormholeCalibrator
        self.learned_params = LearnedParams(db_path)
        self.weight_learner = WeightLearner(self.learned_params)
        self.wormhole_calibrator = WormholeCalibrator(self.learned_params)
        # Phase 61a: the Regulator reuses learned_params (no parallel table, Rule 5). Instantiating is
        # harmless — every signal write and the state-pill are gated on config.REGULATOR_ENABLED, so
        # with the flag OFF this object is observed by nothing (byte-identical, guard 2).
        from .regulator import Regulator
        self.regulator = Regulator(self.learned_params)
        # FRONT 2 (P-AUDIT-3): deferred correction queue. The chat correction is post-turn + advisory,
        # so it fires only when the GPU is free (embedder + reply done) — never cohabiting with the
        # embedder → no VRAM thrash. Only used when CHAT_CORRECTION_SIGNAL is on (i.e. at/after the flip).
        self._correction_queue: list = []
        self._auto_drain_corrections = True
        self._observed = 0   # P-AUDIT-3b post-flip observation window counter
        if not nano_ok:
            log.warning("Ollama unavailable — sensitizer running on heuristic fallback")

    def embed(self, text: str) -> List[float]:
        return self.client.embed(text)

    # --- theory operations -------------------------------------------------------

    def ingest(self, content: str, source: str = "user", mtype: Optional[str] = None,
               extracted=None, embedding=None, timestamp: Optional[str] = None):
        point = ingest_memory(content, source, self.graph, self.sensitizer, self.embed, mtype,
                              extracted=extracted, embedding=embedding,        # 73.2: reuse, never recompute
                              timestamp=timestamp)                            # 74.8: observation time
        # 95.22: a point born from evidence the ledger has already superseded is born superseded -- the
        # correction turn's own narration, a reflection minutes later, or the same text ingested again
        # (a duplicate comes back through here too). Skills excepted, as in supersede_stale_nodes.
        from .fact_nodes import born_stale
        if point.type != "skill" and point.status == "active" and born_stale(self.facts, point.content + " " + (point.summary or "")):
            point.status = "superseded"
            self.graph.save_point(point)
        # Phase 61a signal: a user-explicit statement is the ONLY promoter to FACT (I1). This one
        # choke point also covers the correction's right-fact (grader._apply_correction ingests it
        # as user_explicit). Gated → no-op when the flag is OFF.
        if config.REGULATOR_ENABLED and source == "user_explicit":
            self.regulator.transition(point.id, "explicit")
        return point

    def enqueue_correction(self, message: str, reply: str, facts: str) -> None:
        """FRONT 2: defer a chat-correction detection to the GPU-free drain (grade_turn calls this)."""
        self._correction_queue.append({"message": message, "reply": reply, "facts": facts})

    def _maybe_drain_corrections(self) -> None:
        """FRONT 2: production auto-drain at end of turn (GPU free); the audit disables it to batch."""
        if self._auto_drain_corrections and self._correction_queue:
            try:
                self.drain_corrections()
            except Exception as exc:
                log.warning("correction drain failed (non-fatal): %s", exc)

    def drain_corrections(self, apply: bool = True) -> list:
        """FRONT 2: run the deferred correction detections when the GPU is free (embedder + reply done)
        → gemma4-only, no embedder cohabitation, no thrash. With apply=True (production) each is applied
        via _apply_correction (ingest+supersede — an embed). With apply=False (audit) it is only DETECTED
        + grounded — gemma4-only, no embed → maximal stability. Returns {message, correction, source, error}."""
        from .grader import _detect_correction_via_chat, _apply_correction, _correction_grounded
        queue, self._correction_queue = self._correction_queue, []
        results = []
        for item in queue:
            rec = {"message": item["message"], "correction": None, "source": "chat", "error": None}
            try:
                corr = _detect_correction_via_chat(self, item["message"], item["reply"], item["facts"])
                if apply:
                    rec["correction"] = _apply_correction(self, corr, item["message"]) if corr else None
                    self._observe_correction(rec, corr)   # post-flip observation window (gated)
                    if corr and rec["correction"]:
                        self._emit_correction(rec["correction"], corr)   # live viz event (reuse _emit)
                else:
                    rec["correction"] = corr if (corr and _correction_grounded(corr, item["message"])) else None
            except Exception as exc:
                rec["source"], rec["error"] = "error", f"{type(exc).__name__}: {exc}"
            results.append(rec)
        return results

    def _observe_correction(self, rec: dict, corr) -> None:
        """P-AUDIT-3b post-flip observation window: log the first OBSERVE_FIRST_N drained corrections'
        source + detection + lifecycle-ledger to `observation_log.jsonl` (next to the DB) for spot-audit.
        Gated on config.OBSERVE_FIRST_N (0 = off); fail-soft — monitoring must never break a turn."""
        if not config.OBSERVE_FIRST_N or self._observed >= config.OBSERVE_FIRST_N:
            return
        try:
            import json
            from pathlib import Path
            self._observed += 1
            pid = rec["correction"].get("ingested") if isinstance(rec["correction"], dict) else None
            ledger = self.regulator.ledger(pid) if pid else {}
            entry = {"n": self._observed, "at": now_iso(), "source": rec["source"],
                     "message": (rec["message"] or "")[:120], "detected": corr, "ingested": pid, "ledger": ledger}
            path = Path(config.DB_PATH).with_name("observation_log.jsonl")
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as exc:
            log.debug("observation-window log failed (non-fatal): %s", exc)

    def _emit_correction(self, applied: dict, corr: dict) -> None:
        """Live viz event: a correction was detected+applied in the (post-turn) drain. Reuses the WS
        `_emit` channel (agent.py) — fail-soft; only fires while the turn emitter is still live."""
        emit = getattr(self, "_emit", None)
        if not emit or not getattr(self, "_turn_emit", None):
            return
        try:
            pid = applied.get("ingested")
            c, st = self.regulator.evaluate(pid) if pid else (None, None)
            emit({"type": "correction", "pid": pid, "state": st,
                  "c": round(c, 3) if c is not None else None,
                  "right": corr.get("right"), "wrong": corr.get("wrong")})
        except Exception as exc:
            log.debug("correction event emit failed (non-fatal): %s", exc)

    def retrieve(self, text: str, **overrides) -> tuple:
        """overrides: limit / min_score / expansion_depth (AgentEngine passes live settings)."""
        runtime_context = overrides.pop("runtime_context", None)
        nano_pre = not (hasattr(self, "settings") and self.settings.get("nano_in_tail"))         # 80.2
        query = make_query_point(text, self.embed, self.sensitizer, runtime_context=runtime_context, nano=nano_pre)
        started = time.perf_counter()
        overrides.setdefault("weights", self.weight_learner.weights())   # learned overlay (Phase 56)
        if hasattr(self, "settings"):
            overrides.setdefault("mode", self.settings.get("retrieval_mode") or "fu")   # 77.1: fu | cosine
        retrieved = retrieve_memory(query, self.graph, **overrides)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return query, retrieved, elapsed_ms

    def dream(self) -> DreamReport:
        # wormhole gates self-calibrate from near-miss evidence unless learning is switched off
        # (settings live on the agent layer; the base prototype engine defaults to learning on)
        adapt = self.settings.get("learning_enabled") if hasattr(self, "settings") else True
        from .dream import DreamBudget
        budget = DreamBudget(seconds=self.settings.get("dream_budget_s") or 0.0,
                             region_only=bool(self.settings.get("dream_region_only"))) if hasattr(self, "settings") else None
        last = self.graph.dream_reports(limit=1)
        return dream_loop(self.graph, self.sensitizer, self.embed,
                          calibrator=self.wormhole_calibrator if adapt else None,
                          budget=budget, since=last[0].created_at if (last and budget and budget.region_only) else None)

    def reinforce(self, retrieved: List[RetrievedMemory]) -> None:
        """THEORY §25 — used memories and their edges get stronger."""
        for item in retrieved:
            point = item.point
            point.access_count += 1
            point.last_accessed_at = now_iso()
            point.energy = fu_math.clamp(point.energy + item.score * config.REINFORCE_ENERGY_GAIN)
            point.density = fu_math.compute_density(point, self.graph.centrality(point.id))
            self.graph.save_point(point)
            if item.edge is not None:
                edge = item.edge
                edge.activation_count += 1
                edge.last_activated_at = now_iso()
                edge.kappa = fu_math.clamp(edge.kappa + item.score * config.REINFORCE_KAPPA_GAIN)
                edge.trust = fu_math.clamp(edge.trust + config.REINFORCE_TRUST_GAIN)
                self.graph.save_edge(edge)

    def _should_run_mini_dream(self) -> bool:
        if self.turn_count > 0 and self.turn_count % config.MINI_DREAM_EVERY_N_TURNS == 0:
            return True
        return unresolved_tension_count(self.graph) > config.MINI_DREAM_TENSION_TRIGGER

    def _should_store_assistant(self, reply: str) -> bool:
        """THEORY issue 14: store replies that carry decisions/commitments/novel synthesis."""
        extracted = self.sensitizer.extract(reply)
        # NOT "fact" (Phase 48): the assistant recalls facts, it never authors them — storing a
        # reply merely because the nano typed it 'fact' is the build-chatter pollution source.
        return (extracted["importance"] >= config.STORE_ASSISTANT_MIN_IMPORTANCE
                or extracted["type"] in ("decision", "task", "goal"))

    def _store_assistant_reply(self, reply, retrieved) -> bool:
        """Store a worthwhile assistant reply — but NEVER as a fact/identity (the assistant
        recalls facts, it does not author them: prevents the 'I've remembered your name is
        Sebastian' → new fact feedback loop) and NEVER when it merely echoes a recalled memory."""
        if not self._should_store_assistant(reply):
            return False
        emb = self.embed(reply)
        for r in (retrieved or []):
            if r.point.embedding and fu_math.cosine(emb, r.point.embedding) >= 0.9:
                return False   # echo of something already remembered — don't re-store
        self.ingest(reply, source="assistant", mtype="message", embedding=emb)   # 73.2: embedded once
        return True

    # --- the master cycle (§24) -----------------------------------------------------

    def chat(self, user_message: str, explicit: bool = False) -> dict:
        self.turn_count += 1
        from .runtime_context import RuntimeContext
        runtime = RuntimeContext.capture()
        # 1-2. query point + retrieval
        query, retrieved, retrieval_ms = self.retrieve(user_message, runtime_context=runtime)
        # 3. injectable context
        context, _ = build_llm_context(query, self.graph, retrieved=retrieved,
                                       excerpt_chars=self.settings.get("excerpt_max_chars"))   # 78.2
        # 4. answer with memory
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT + "\n\n" + runtime.prompt_block()
             + "\n\n" + context},
            {"role": "user", "content": user_message},
        ]
        # 95.77: the same root cause as the health display — this path called the compiled-in
        # default and ignored the chat model the user had chosen. With a registry the PROVIDER is
        # chosen too, so a non-Ollama choice is honoured rather than sent to the Ollama client.
        registry = getattr(self, "registry", None)
        if registry is not None:
            reply = registry.chat_for_role("chat", messages, temperature=0.6)["content"]
        else:
            from .providers import model_for_role
            reply = self.client.chat(model_for_role(self, "chat"), messages, temperature=0.6)
        # 5. ingest the user message
        source = "user_explicit" if explicit else "user"
        if hasattr(self, "facts"):               # 69.5: ONE ledger contract for every chat path (F07)
            self.facts.apply_all(user_message, source)
        user_point = self.ingest(user_message, source=source)
        # 6. maybe ingest the reply (never as a fact; never an echo)
        stored_reply = self._store_assistant_reply(reply, retrieved)
        # 7. reinforcement
        self.reinforce(retrieved)
        # 8. mini dream loop when due
        mini_report = None
        if self._should_run_mini_dream():
            mini_report = mini_dream_loop(self.graph, self.sensitizer)
        return {
            "response": reply,
            "injected_context": context,
            "retrieved": [r.public() for r in retrieved],
            "retrieval_ms": round(retrieval_ms, 1),
            "user_point_id": user_point.id,
            "stored_assistant_reply": stored_reply,
            "mini_dream": mini_report.public() if mini_report else None,
            "stats": self.graph.stats(),
        }
