"""Calibrated abstention (Phase 75.3) — metamemory: the system says, in the injected context, when its memory has
NOTHING about the question, instead of offering weak neighbours the reader will stitch into an answer.

Evidence strength e(q) ∈ [0, 1] = the best similarity between the question and any recalled memory, or 1.0 when the
canonical ledger holds a value for a user-fact question. When e(q) < `abstention_floor` (a setting, 0 = off) ONE
explicit line is prepended to the context: the memory has no record of this; say so, do not guess. The floor is
CALIBRATED offline on a pre-registered dev split (scripts/bench_abstention.py) and reported on the test split — it is
never tuned on the numbers it is judged by. Pure functions, no store, no model call."""
from __future__ import annotations

from typing import List, Optional

from . import fu_math
from .models import QueryPoint, RetrievedMemory


def evidence_strength(query: QueryPoint, retrieved: List[RetrievedMemory], ledger_hit: bool = False) -> float:
    """max cosine(question, recalled memory); 1.0 when the ledger answers a user-fact question; 0.0 with nothing."""
    if ledger_hit:
        return 1.0
    if not query.embedding or not retrieved:
        return 0.0
    return max((fu_math.cosine(query.embedding, r.point.embedding) for r in retrieved if r.point.embedding), default=0.0)


def ledger_answers(query: QueryPoint, facts, canonical: Optional[List[str]]) -> bool:
    """A user-fact question whose attribute the ledger holds counts as full evidence (the M6 rule reused)."""
    if not canonical:
        return False
    from .retrieve import user_fact_question
    return user_fact_question(query, facts)


def coverage_strength(question: str, retrieved: List[RetrievedMemory], canonical: Optional[List[str]] = None) -> float:
    """75.3b: share of the question's salient words that appear in the recalled context (memories + ledger lines).
    'Which did I do first, fixing the fence or buying cows from Peter?' with no 'cows'/'peter' anywhere → low."""
    from .textnorm import norm, salient
    words = salient(question, min_len=4)
    if not words:
        return 1.0                                       # nothing to cover — never abstain on an empty question
    blob = norm(" ".join([f"{r.point.summary} {r.point.title} {r.point.content}" for r in retrieved] + list(canonical or [])))
    return sum(1 for w in words if w in blob) / len(words)


def abstention_line(evidence: float, floor: float) -> str:
    """The one context line the gate adds ('' when the floor is off or the evidence clears it)."""
    if floor <= 0.0 or evidence >= floor:
        return ""
    return (f"MEMORY CHECK: nothing in memory is about this question (best match {evidence:.2f} < {floor:.2f}). "
            "If the question asks about the user's past or their facts, say plainly that there is no record of it — "
            "do not guess, do not stitch an answer from unrelated memories.")
