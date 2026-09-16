"""Single source of truth for every tunable in HMG-Fu.

All values trace back to docs/THEORY.md (section references in comments).
Every setting can be overridden with an environment variable named HMGFU_<NAME>;
overrides are documented in README.md — there are no hidden flags.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(name: str, default):
    raw = os.environ.get(f"HMGFU_{name}")
    if raw is None:
        return default
    if isinstance(default, bool):
        return raw.lower() in ("1", "true", "yes", "on")
    if isinstance(default, int):
        return int(raw)
    if isinstance(default, float):
        return float(raw)
    return raw


def _env_is_set(name: str) -> bool:
    """Whether HMGFU_<NAME> is present in the environment (vs absent). Powers the documented
    FEATURE-FLAG PRECEDENCE (regulator_enabled / chat_correction_signal / observe_first_n):

        env var SET  ->  the env value wins; the persisted UI setting is IGNORED.
        env var UNSET -> the persisted UI setting is used (default OFF if never toggled).

    This is DELIBERATELY the INVERSE of the embed_model resolution (where the persisted setting
    silently overrode env — the bge-m3 clone footgun). For an operator, a deployment env flag must
    be authoritative and never be clobbered by a stale DB toggle. reconcile_flags() applies
    settings -> config.<NAME> once per turn only when the env is UNSET, so the live config.<NAME>
    read sites stay byte-identical when neither env nor setting is on."""
    return f"HMGFU_{name}" in os.environ


_FLAG_KEYS = (("REGULATOR_ENABLED", "regulator_enabled"),
              ("CHAT_CORRECTION_SIGNAL", "chat_correction_signal"),
              ("OBSERVE_FIRST_N", "observe_first_n"))


def reconcile_flags(settings) -> None:
    """Push the persisted UI settings into the live config.<NAME> feature flags, honouring the
    precedence in _env_is_set (env-set wins, never clobbered; else the setting; else the OFF default)."""
    for env_name, key in _FLAG_KEYS:
        if not _env_is_set(env_name):
            globals()[env_name] = settings.get(key)


# --- Models (PROJECT_ID.md) -------------------------------------------------
CHAT_MODEL = _env("CHAT_MODEL", "gemma4:12b")            # main mind
ROUTER_MODEL = _env("ROUTER_MODEL", CHAT_MODEL)          # 73.2: turn router (classification); defaults to the main mind
NANO_MODEL = _env("NANO_MODEL", "qwen2.5:1.5b-instruct")  # high-frequency sensitizer
GRADER_MODEL = _env("GRADER_MODEL", "gemma-cpu:latest")  # advisory nano-produced grader
DREAM_MODEL = _env("DREAM_MODEL", "qwen2.5:1.5b-instruct")  # dream-loop worker
EMBED_MODEL = _env("EMBED_MODEL", "nomic-embed-text")     # embeddings
OLLAMA_URL = _env("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_TIMEOUT_S = _env("OLLAMA_TIMEOUT_S", 300.0)  # build turns generate large files locally
NANO_TIMEOUT_S = _env("NANO_TIMEOUT_S", 45.0)

# --- Storage -----------------------------------------------------------------
DB_PATH = _env("DB_PATH", os.path.join(os.path.dirname(os.path.dirname(__file__)), "hmgfu.db"))

# --- Density ρ weights (THEORY §6; sum = 1.00) --------------------------------
DENSITY_WEIGHTS = {
    "importance": 0.22,
    "recurrence": 0.16,
    "emotionalIntensity": 0.13,
    "utility": 0.18,
    "confidence": 0.12,
    "novelty": 0.07,
    "centrality": 0.12,
}

# --- Coupling κ weights (THEORY §7; sum = 1.00) --------------------------------
KAPPA_WEIGHTS = {
    "semantic": 0.25,
    "temporal": 0.10,
    "entityOverlap": 0.18,
    "goalOverlap": 0.18,
    "causal": 0.14,
    "explicit": 0.15,
}

# --- Relation type Ω (THEORY §8; wormhole deliberately > 1) --------------------
OMEGA = {
    "same_entity": 1.00,
    "causal": 0.95,
    "project_related": 0.90,
    "goal_related": 0.88,
    "evidence_for": 0.85,
    "evidence_against": 0.80,
    "skill_required": 0.78,
    "temporal": 0.75,
    "semantic_similarity": 0.70,
    "analogy": 0.65,
    "emotional": 0.60,
    "contradiction": 0.55,
    "part_of": 0.90,
    "depends_on": 0.85,
    "memory_of": 0.70,
    "wormhole": 1.20,
}
OMEGA_DEFAULT = 0.5

# --- Final retrieval score weights (THEORY §30 — canonical, replaces §10) -------
MEMORY_SCORE_WEIGHTS = {
    # Query fit is deliberately stronger than accumulated popularity. Even after the
    # importance gate saturates, a dense/repeated partial match must not outrank a much
    # closer answer solely because it has been accessed more often (Phase 50).
    "semantic": 0.42,
    "kappa": 0.20,
    "density": 0.06,
    "utility": 0.05,
    "recency": 0.07,
    "modeMatch": 0.08,
    "wormholeBoost": 0.07,
    "fuDistancePenalty": 0.03,
    "tensionPenalty": 0.02,
}

# --- Helper-function constants (THEORY Part B, issue 5) ------------------------
RECURRENCE_REF = 20            # accesses at which recurrence saturates
TEMPORAL_TAU_HOURS = 72.0      # κ temporal proximity time-constant
RECENCY_TAU_DAYS = 14.0        # retrieval recency time-constant

# --- THEORY v3 lifecycle / Regulator (Phase 61a; gated on E.3, OFF in production until it passes) --
# Every point carries a bounded confidence c and a lifecycle state. INVARIANT I1 (anti-poisoning,
# STRUCTURAL not tuned): no accumulation of silent use + praise can reach FACT — the ceiling without
# an explicit user signal is TEMP_C + SILENT_CAP + PRAISE_CAP = 0.40+0.10+0.10 = 0.60 < FACT_T (0.80).
# A correction is an ABSORBING transition to SUPERSEDED that no counter reverses. Proven in
# tests/test_regulator_i1.py. Every value HMGFU_LIFECYCLE_* overridable (no hidden flags, Rule 10).
LIFECYCLE = {
    "TEMP_C": _env("LIFECYCLE_TEMP_C", 0.40),          # birth confidence
    "CANDIDATE_T": _env("LIFECYCLE_CANDIDATE_T", 0.50),
    "FACT_T": _env("LIFECYCLE_FACT_T", 0.80),          # AND requires >=1 explicit user signal
    "EXPLICIT_D": _env("LIFECYCLE_EXPLICIT_D", 0.30),  # user statement/confirmation
    "PRAISE_D": _env("LIFECYCLE_PRAISE_D", 0.05),
    "PRAISE_CAP": _env("LIFECYCLE_PRAISE_CAP", 0.10),  # praise is NOISY (approval != verification)
    "SILENT_D": _env("LIFECYCLE_SILENT_D", 0.01),
    "SILENT_CAP": _env("LIFECYCLE_SILENT_CAP", 0.10),  # silence is the weakest signal
    "EVAPORATE_TTL_DAYS": _env("LIFECYCLE_EVAPORATE_TTL_DAYS", 30),
}
# 91.Z11 EXPERIMENT (user-approved, candidate only, NOT a production activation). The clock re-ask
# rewrites an answer when the router marked the clock sufficient and the reply carries no clock
# value. The 91.Y review showed the eligibility test cannot establish that the information REQUESTED
# is the clock, so the experiment measures the gate OFF against ON in the SAME code. Default ON, so
# nothing changes unless the flag is set: HMGFU_CLOCK_REASK_ENABLED=0 turns it off.
CLOCK_REASK_ENABLED = _env("CLOCK_REASK_ENABLED", True)
# 92.E4 INTERACTIVE LEARNING. off = today exactly (arm S): the protocol never runs and a legacy base
# never gains its table. confirm = the teaching/feedback protocol (arm C). adapt = C plus reuse of
# interpretations a human already confirmed (arm L). Default off; nothing is activated by installing
# this. Set with HMGFU_INTERACTIVE_LEARNING_MODE or the settings row of the same name.
INTERACTIVE_LEARNING_MODE = _env("INTERACTIVE_LEARNING_MODE", "off")
REGULATOR_ENABLED = _env("REGULATOR_ENABLED", False)   # production flag — ON only after E.3 passes
# P-AUDIT-2 (THEORY_V3 B.5): source the CORRECTION signal from the STRONG chat model (gemma4:12b) via
# schema-constrained decoding instead of the weak nano grader (which detected 4/15 in P-AUDIT run 1);
# nano is demoted to fallback for this field. Field disabled on action turns. Default OFF (nano path).
CHAT_CORRECTION_SIGNAL = _env("CHAT_CORRECTION_SIGNAL", False)
# P-AUDIT-3b: the perception WON (recall 15/15, ghost 0, 0 fallbacks) → the flip is AUTHORIZED. Enable
# in production via env (HMGFU_CHAT_CORRECTION_SIGNAL=1 HMGFU_REGULATOR_ENABLED=1); the config DEFAULTS
# stay OFF so the test suite keeps guarding the flag-off (production-byte-identical) path. Post-flip
# observation window: with OBSERVE_FIRST_N>0, the first N drained corrections log source + lifecycle
# ledger to `observation_log.jsonl` (next to the DB) for Trailblazer's spot-audit.
OBSERVE_FIRST_N = _env("OBSERVE_FIRST_N", 0)
SOURCE_TRUST = {"user_explicit": 0.95, "user": 0.80, "assistant": 0.65, "dream": 0.60, "system": 0.70}
# THEORY Part B issue 15 (PA3-proven recall hygiene): retrieval-score source factor.
# Canonical user statements outrank the assistant's own stored chatter, which otherwise
# poisons recall with its past wrong/empty answers (recency makes them win).
SOURCE_SCORE_FACTOR = {"user_explicit": 1.25, "user": 1.00, "system": 1.00, "dream": 0.95, "assistant": 0.85}
# Phase 47 — importance-relevance gate. The ρ (density) + U (utility) "general importance"
# terms scale 0→1 as query relevance rises floor→ref, so a globally-dense identity hub
# (e.g. "Trailblazing") can't hijack an unrelated query on its ρ/U alone. Relevance is
# QUERY-RELATIVE ONLY (semantic cosine + query_kappa); never edge.kappa, which is high for
# any hub regardless of the query. Identity is unaffected: it rides the verbatim canonical-
# fact channel + scores high on identity queries anyway (proven: no regression on "my name?").
IMPORTANCE_RELEVANCE_GATE = {"floor": 0.25, "ref": 0.50}

# --- Edges / ingestion (THEORY §12, §13) ---------------------------------------
KAPPA_MIN_EDGE = 0.18          # drop weaker candidate edges (unless wormhole)
CANDIDATE_NEIGHBOURS = 12      # semantic neighbours considered for hex placement
MAX_EDGES_PER_INGEST = 12

# --- Energy propagation Φ (THEORY §14 + issue 3) --------------------------------
PROPAGATION_MAX_DEPTH = 3
PROPAGATION_FLOOR = 0.05
PROPAGATION_MAX_FACTOR = 0.95  # per-hop attenuation clamp: no amplification, ever

# --- Retrieval Ψ (THEORY §15, §16) ----------------------------------------------
RETRIEVAL_CHANNELS = {
    "semantic": 60, "entity": 30, "goal": 30, "recent": 20, "dense": 20, "wormhole": 20,
}
RETRIEVAL_MIN_SCORE = 0.35
RETRIEVAL_LIMIT = 12
EXPANSION_DEPTH = 2
EXPANSION_MIN_KAPPA = 0.45
EXPANSION_MIN_TRUST = 0.55
EXPANSION_MAX_DISTANCE = 2.5
EXPANSION_MIN_SCORE = 0.25
DENSE_IDENTITY_MIN = 0.60      # ρ threshold for the dense-identity channel
TOKEN_BUDGET = _env("TOKEN_BUDGET", 1800)
# Question-echo self-match filter (PA3 r41 lesson, generalised): a candidate whose embedding
# is nearly identical to the query IS the query — it carries no answer and drowns canon.
ECHO_FILTER_MIN_COSINE = 0.93
# Ingest dedup: a near-identical same-kind memory reinforces one node instead of duplicating
# it (stops confident-wrong-fact pollution accumulating copies).
DEDUP_MIN_COSINE = _env("DEDUP_MIN_COSINE", 0.94)
# Ephemeral observations (weather/price/time "now" statements) decay in retrieval with this
# time constant — hours, not the 14-day recency tau (issue 16).
EPHEMERAL_TAU_HOURS = _env("EPHEMERAL_TAU_HOURS", 6.0)

# --- Wormholes (THEORY §17) ------------------------------------------------------
# A wormhole links two DISTANT, ESTABLISHED memories that are structurally analogous but
# lexically dissimilar (THEORY issue 10). It gates on shared DENSITY (both load-bearing), NOT
# novelty — established analogies are by definition not novel, so the old minNovelty/minUtility
# gates made the mechanism unfireable on a mature graph (Phase 33 diagnosis). The hard
# topicOverlap gate was also dropped: the analogy heuristic already rewards topic overlap, and
# hard-gating it double-penalizes genuine CROSS-domain analogies (which have disjoint topic tags).
WORMHOLE = {
    "minHexDistance": 3, "minAnalogy": 0.7, "minSemantic": 0.42,
    "maxEntityOverlap": 0.5, "minDensity": 0.4,
    "kappa": 0.85, "omega": 1.20, "distance": 0.5, "trust": 0.65,
}

# --- Macros (THEORY §18 + issue 6) ------------------------------------------------
MACRO_MIN_CLUSTER = 5
MACRO_MIN_KAPPA = 0.40
MACRO_MIN_DENSITY = 0.35
MACRO_MAX_NODES = 25

# --- Memory hierarchy / zoom (ANALYSIS: Nanite-style LOD; hierarchy.py) --------------
HIERARCHY_MAX_LEVEL = _env("HIERARCHY_MAX_LEVEL", 3)     # macro levels above micro (micro=0)
SUPER_MACRO_MIN_CLUSTER = 3    # parentless same-level macros needed to form a super-macro
SUPER_MACRO_MIN_COSINE = 0.55  # embedding similarity for macros to cluster upward

# --- Decay Δ (THEORY §20 + issue 4) ------------------------------------------------
BASE_DECAY = 0.04
DECAY_CAP = 0.20
DORMANT_ENERGY = 0.05
DORMANT_DENSITY = 0.20
DORMANT_MAX_ACCESS = 2
DORMANT_MAX_CENTRALITY = 0.30  # issue 4: hubs never go dormant

# --- Promotion (THEORY §21) ---------------------------------------------------------
PROMOTE = {"density": 0.68, "utility": 0.55, "confidence": 0.65, "accessCount": 3, "stability": 0.60}

# --- Contradictions (THEORY §22 + issue 7) -------------------------------------------
CONTRADICTION_MIN_SCORE = 0.72
CONTRADICTION_CONFIDENCE_GAP = 0.20

# --- Master cycle (THEORY §24, §25 + issues 11, 14) -----------------------------------
REINFORCE_ENERGY_GAIN = 0.20
REINFORCE_KAPPA_GAIN = 0.03
REINFORCE_TRUST_GAIN = 0.01
MINI_DREAM_EVERY_N_TURNS = _env("MINI_DREAM_EVERY_N_TURNS", 8)
MINI_DREAM_TENSION_TRIGGER = 5
STORE_ASSISTANT_MIN_IMPORTANCE = 0.45

# --- Server ---------------------------------------------------------------------------
API_HOST = _env("API_HOST", "127.0.0.1")
API_PORT = _env("API_PORT", 8777)

MEMORY_LAYERS = ["L0_raw", "L1_session", "L2_project", "L3_identity", "L4_world_model", "L5_deep_pattern"]

MEMORY_TYPES = [
    "message", "fact", "project", "goal", "task", "person", "place", "event",
    "emotion", "decision", "pattern", "skill", "concept", "macro", "micro",
    # ontology node classes (Phase 43): session breath, LLM self-memory, canon directives.
    # `skill` stays the whole action surface (tool vs skill is a derived facet, taxonomy.node_class).
    "session", "reflection", "directive",
]

RELATION_TYPES = list(OMEGA.keys())


def weight_sums() -> dict:
    """Sanity helper used by tests: every weight table must sum to ~1.0 (positive mass)."""
    return {
        "density": sum(DENSITY_WEIGHTS.values()),
        "kappa": sum(KAPPA_WEIGHTS.values()),
        "memory_score_positive": sum(
            v for k, v in MEMORY_SCORE_WEIGHTS.items() if not k.endswith("Penalty")
        ),
        "memory_score_penalties": sum(
            v for k, v in MEMORY_SCORE_WEIGHTS.items() if k.endswith("Penalty")
        ),
    }
