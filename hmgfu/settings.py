"""Runtime settings — persisted key/value over SQLite, defaults from config.py.

The UI changes these live (PUT /api/settings): per-role provider+model, grader producer
(nano | main), feature toggles. Everything visible via GET /api/settings (Rule 10).
"""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from . import config

DEFAULTS = {
    # per-role provider + model (multi-provider selector)
    "chat_provider": "ollama",   "chat_model": config.CHAT_MODEL,
    "router_provider": "ollama", "router_model": config.ROUTER_MODEL,   # 73.2: the turn classifier
    "nano_provider": "ollama",   "nano_model": config.NANO_MODEL,
    "dream_provider": "ollama",  "dream_model": config.DREAM_MODEL,
    "grader_provider": "ollama", "grader_model": config.GRADER_MODEL,
    "embed_provider": "ollama",  "embed_model": config.EMBED_MODEL,
    # grader producer: "nano" = dedicated grader role model; "main" = the chat model grades
    "grader_producer": "nano",
    # thinking mode (PA3: dynamic | always | off) — how often the model shows its reasoning
    "thinking_mode": "dynamic",
    # nano-worker toggles (off → deterministic heuristic fallbacks, never a crash)
    "nano_sensitizer_enabled": True,   # extraction nano (entities/topics/emotion/importance)
    "nano_dream_enabled": True,        # dream worker (macro summaries, analogy/contradiction, insights)
    "grader_enabled": True,
    "tail_async": True,                # 73.4: ingest/grader/mini-dream run after the reply on a worker; the next turn joins it
    "playbook_extraction": True,
    "tool_points_enabled": True,
    # Phase 56 self-tuning master switch: grader→score-weight learning, wormhole gate
    # calibration, and routing-exemplar memory. Off → config-baseline behaviour everywhere;
    # learned state is inspectable at GET /api/learning either way (Rule 10).
    "learning_enabled": True,
    # memory-recall tuning (live-adjustable; defaults = THEORY §15/§16/§23)
    # Phase 77.1: the experimental Fu package (channels + composite score + expansion) vs the strong control as product
    # (vector top-k + the same context policy). Default decided by the pre-registered rule in ROADMAP 77.1.
    "retrieval_mode": "fu",            # fu | cosine
    "retrieval_limit": 12,             # recalled memories per turn (top-k)
    # Phase 86.1: a deeper recall for AGGREGATION questions only ("how many … in total"); 0 = off = every turn uses retrieval_limit
    "retrieval_limit_aggregate": 0,
    "retrieval_min_score": 0.35,       # activation-score floor
    "expansion_depth": 2,              # Fu-expansion hops
    "token_budget": 1800,              # injected-context token budget
    # Phase 78: long-form excerpt policy. 0 = today's head cut (byte-identical); the promotion candidate is chosen on the
    # deterministic attribution, promoted only if the pre-registered gates pass. echo_guard_scope: all = every assistant/dream
    # memory leaves a user-fact answer (73.3); echoes = only the ones that RESTATE a ledger value of the asked attribute.
    # Phase 79.3: deterministic pre-router for the two uniform turn classes (recall of a ledger attribute; plain fact
    # statement) — no model router call on those turns. OFF until the 79 gates pass.
    # Phase 80.2: the nano extraction runs in the post-reply tail instead of before the reply (heuristic + router before;
    # the stored point still gets the nano's fields). OFF = today. Promoted only by the Phase 80 gates.
    "nano_in_tail": False,
    "router_bypass_enabled": False,
    # Phase 89.1: nearest-exemplar router — the turn's embedding decides the route when the k nearest labelled exemplars agree
    # and are at least min_sim close; otherwise the model router runs (fallback). OFF = today.
    "knn_router_enabled": False,
    "knn_router_k": 3,
    "knn_router_min_sim": 0.80,
    # Phase 84.2: the generic "my X is Y" regex may mint OPEN keys (open.guess, open.advice…) — the systematic precision leak
    # the reserved sets showed. False = only closed slots from the regex; open keys come from the model mapper or not at all.
    "open_slot_regex_writes": True,
    # 92.E4: off = today exactly (arm S, no protocol and no table on a legacy base); confirm = the
    # teaching/feedback protocol (arm C); adapt = C plus reuse of interpretations a human confirmed
    # (arm L). Default off: installing this activates nothing.
    "interactive_learning_mode": "off",
    # Phase 84.3/84.4: the model-backed write path. fallback = today (single-slot mapper, pre-reply, only when the regex found
    # no slot); spans = the span-extractor contract in the turn TAIL on every declarative message (adds slots the regex missed);
    # off = regex only. fact_mapper_role picks the model role for either contract.
    "fact_mapper_mode": "fallback",
    "fact_mapper_role": "nano",
    # Phase 79.6: on a pre-routed turn, extract with the deterministic heuristic instead of the nano (2 calls: embed + chat).
    "bypass_skips_nano": False,
    "excerpt_max_chars": 0,            # 0 = OFF: today's head cut (byte-identical). >0 = the query-matched span, that many chars
    "echo_guard_scope": "all",
    "mini_dream_every_n_turns": 8,
    # Phase 56: the FULL dream (macros, wormholes, hygiene) is now actually scheduled — production
    # evidence showed 56/59 dreams were minis, so the self-organisation stage never ran live.
    # Runs in a background thread every N turns; 0 disables (manual /api/dream still works).
    "full_dream_every_n_turns": 0,     # 76.3 ablation: a full dream cost relational recall (0.717 → 0.683, macro crowding) and
                                       # saved no tokens (+0.3% / −0.5%) → off the default path; manual / API dreams still run
    # Phase 76.3: dreams as budgeted maintenance — 0 = unbudgeted (today's behaviour); region_only scopes the proposing
    # stages to the points touched since the last dream. Promoted only by the 76.3 ablation.
    "dream_budget_s": 0,
    "dream_region_only": False,
    "max_tools_per_turn": 8,
    # Phase 66.6 minimal action: a plain QUESTION (no tool named by the user) sees fewer tools and a
    # shorter tool leash — small models over-call when offered the whole surface.
    "question_max_tools": 5,
    "question_max_iterations": 3,
    # Phase 66.2: numbers/URLs in a reply that followed a tool round must trace to a tool result or memory
    "grounding_gate_enabled": True,
    # Phase 77.4: claim-level abstention on tool-free turns — the reply's novel words must be in the evidence; the floor
    # is chosen on the pre-registered dev split (bench_abstention --signal claim). OFF until that gate passes.
    "claim_gate_enabled": False,
    "claim_gate_floor": 0.5,
    # Phase 67: say-do gate (intent/execution claims checked from telemetry), the recall-only memory's
    # guaranteed anaphora window (last N session turns, verbatim), and self-instructed recall on plan steps
    "saydo_gate_enabled": True,
    "recent_turns_window": 3,
    "plan_step_recall": True,
    "agent_max_iterations": 16,
    # Phase 75.1: procedural memory — a finalized plan leaves a runbook; a similar later request sees it beside the tools
    "runbooks_enabled": False,          # promoted to True by the 75.1 gate (bench_runbooks)
    "runbook_match_floor": 0.62,        # cosine(request, runbook task) needed to surface one
    # Phase 75.2: prospective memory — reminders by time / condition from the user's own words (deterministic)
    "prospective_enabled": True,
    # Phase 77.6: the alarm ticker — due time-triggers fire without a turn every N seconds (0 = idle, no restart needed)
    "prospective_tick_s": 30,
    # Phase 75.5: outcome-driven bandit (Thompson sampling, bounded, in learned_params) at the runbook-offer site
    "bandit_enabled": False,            # promoted by the 75.5 gate (offline convergence + tool/say-do held with it ON)        # 75.2 gate met (heldout_m4 28/28, firing tests, zero false sets, no regression) → ON
    # working folder for bash/read/write tools ("" = <repo>/workspace default)
    "workspace_dir": "",
    # Phase 61a Regulator + P-AUDIT correction perceiver (defaults OFF → flag-off byte-identical, the
    # suite keeps guarding it). PRECEDENCE (config._env_is_set): if the matching HMGFU_<NAME> env var
    # is set it WINS and these settings are ignored; else these persisted values apply. The Regulator
    # toggle is an absorbing signal in production — the UI gates it behind an explicit confirmation.
    "regulator_enabled": False,          # lifecycle state machine live (records signals + display pill)
    "chat_correction_signal": False,     # correction from the strong chat model (deferred, GPU-free)
    "observe_first_n": 0,                # post-flip observation window: log the first N corrections (0 = off)
}

# M-04: numeric bounds — reject negative limits/depths/budgets that would produce
# negative-slice or zero-iteration behavior downstream. (min, max) inclusive.
_RANGES = {
    "retrieval_limit": (1, 50),
    "retrieval_limit_aggregate": (0, 50),    # 86.1: 0 = off
    "knn_router_k": (1, 7),                  # 89.1
    "knn_router_min_sim": (0.5, 0.99),       # 89.1
    "retrieval_min_score": (0.0, 1.0),
    "runbook_match_floor": (0.0, 1.0),
    "claim_gate_floor": (0.0, 1.0),
    "expansion_depth": (0, 5),
    "token_budget": (256, 8000),
    "excerpt_max_chars": (0, 2000),          # 0 = head cut (valid sentinel)
    "mini_dream_every_n_turns": (0, 1000),   # 0 = disable mini-dream (valid sentinel)
    "full_dream_every_n_turns": (0, 5000),   # 0 = disable scheduled full dream
    "dream_budget_s": (0, 3600),
    "prospective_tick_s": (0, 3600),
    "max_tools_per_turn": (1, 30),
    "question_max_tools": (1, 30),
    "question_max_iterations": (1, 60),
    "recent_turns_window": (0, 12),
    "agent_max_iterations": (1, 60),
    "observe_first_n": (0, 1000),            # 0 = observation window off
}
# fixed-choice string settings
_ENUMS = {
    "echo_guard_scope": {"all", "echoes"},       # 78.3
    "retrieval_mode": {"fu", "cosine"},          # 77.1
    "thinking_mode": {"dynamic", "always", "off"},
    "grader_producer": {"nano", "main"},
    "fact_mapper_mode": {"fallback", "spans", "off"},   # 84.3
    "fact_mapper_role": {"nano", "chat"},               # 84.3
}


class Settings:
    def __init__(self, db_path: Optional[str] = None):
        self._lock = threading.RLock()
        self._db = sqlite3.connect(db_path or config.DB_PATH, check_same_thread=False)
        self._db.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        self._db.commit()
        self._cache = dict(DEFAULTS)
        for key, raw in self._db.execute("SELECT key, value FROM settings"):
            if key in DEFAULTS:
                try:
                    self._cache[key] = json.loads(raw)
                except (json.JSONDecodeError, ValueError):
                    pass

    def get(self, key: str):
        with self._lock:
            if key not in DEFAULTS:
                raise KeyError(f"unknown setting '{key}'")
            return self._cache[key]

    @staticmethod
    def _coerce(key: str, value):
        """Type-check, range-check and enum-check ONE key without touching state.
        Returns the coerced value or raises KeyError/ValueError."""
        if key not in DEFAULTS:
            raise KeyError(f"unknown setting '{key}'")
        expected = type(DEFAULTS[key])
        if expected is bool and not isinstance(value, bool):
            raise ValueError(f"'{key}' expects bool")
        if expected is int and (isinstance(value, bool) or not isinstance(value, int)):
            raise ValueError(f"'{key}' expects int")
        if expected is float:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"'{key}' expects number")
            value = float(value)
        if expected is str and not isinstance(value, str):
            raise ValueError(f"'{key}' expects str")
        if key in _RANGES:
            lo, hi = _RANGES[key]
            if not lo <= value <= hi:
                raise ValueError(f"'{key}' must be in [{lo}, {hi}]")
        if key in _ENUMS and value not in _ENUMS[key]:
            raise ValueError(f"'{key}' must be one of {sorted(_ENUMS[key])}")
        return value

    def set(self, key: str, value) -> None:
        value = self._coerce(key, value)
        with self._lock:
            self._cache[key] = value
            self._db.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)",
                             (key, json.dumps(value)))
            self._db.commit()

    def all(self) -> dict:
        with self._lock:
            return dict(self._cache)

    def update(self, patch: dict) -> dict:
        # M-04: validate the WHOLE patch first, then commit atomically — a bad key no longer
        # leaves earlier keys half-applied.
        coerced = {key: self._coerce(key, value) for key, value in patch.items()}
        with self._lock:
            for key, value in coerced.items():
                self._cache[key] = value
                self._db.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)",
                                 (key, json.dumps(value)))
            self._db.commit()
        return coerced
