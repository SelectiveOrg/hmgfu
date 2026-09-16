"""93.R5 — one turn, one answer per internal search.

Priority 7 of the plan asks for limits against repeated searches. `execute_tool` counted calls but
never noticed that the same query had already been answered this turn, so a model that decides it
must "check memory" could ask three times, pay three times and read the same rows three times.

The limit answers rather than refuses. A refusal would tell the model the memory is unavailable —
false, and an invitation to retry — so a repeat receives the SAME rows, marked as a repeat. The turn
continues; the cost is paid once.

Per TURN, not per session: between turns the world may have changed, and a search is how the model
finds that out. A failed search is not remembered as an answer either, so retrying after an error is
a retry and not a loop.
"""
from __future__ import annotations

import json
from typing import Optional

WATCHED = ("memory_search", "memory_timeline")      # internal recall; external tools are not capped here


def _key(name: str, args: dict) -> str:
    """Same tool, same question — spacing and case do not make a new search."""
    payload = {k: (" ".join(str(v).split()).casefold() if isinstance(v, str) else v)
               for k, v in sorted((args or {}).items()) if k != "limit"}
    return f"{name}::{json.dumps(payload, ensure_ascii=False, sort_keys=True)}"


def _limit_of(args: dict):
    try:
        return int((args or {}).get("limit"))
    except (TypeError, ValueError):
        return None


def _is_an_answer(result: str) -> bool:
    """93.RR3: use the shared classification rather than looking for an `error` key.

    A blocked call is not a failure -- the safety layer worked -- but it is not an ANSWER either, so
    neither is remembered: retrying after one is a retry, not a loop."""
    from .toolsys import classify_tool_result
    failed, _ = classify_tool_result(result or "")
    if failed:
        return False
    try:
        data = json.loads(result or "")
    except Exception:
        return True
    return not (isinstance(data, dict) and data.get("blocked"))


class RecallBudget:
    """The searches this turn already answered, and what they answered."""

    def __init__(self):
        self._answers = {}
        self._order = []
        self.repeats = 0

    def begin_turn(self) -> None:
        self._answers, self._order, self.repeats = {}, [], 0

    def seen(self, name: str, args: dict) -> Optional[str]:
        """The earlier answer to this exact search, marked as a repeat — or None if it is new."""
        if name not in WATCHED:
            return None
        entry = self._answers.get(_key(name, args))
        if entry is None:
            return None
        # 93.RR3: asking for MORE rows is a legitimate widening, and the stored answer cannot satisfy
        # it. Only a request the stored answer already covers is served from it.
        wanted, held = _limit_of(args), entry.get("limit")
        if wanted is not None and held is not None and wanted > held:
            return None
        prior = entry["result"]
        self.repeats += 1
        return json.dumps({"repeat_of_this_turn": True,
                           "note": "you already ran this exact search this turn; these are the same "
                                   "rows, not new ones. Answer from them or ask the user.",
                           "result": prior}, ensure_ascii=False)

    def record(self, name: str, args: dict, result: str, owner=None) -> str:
        """Remember this answer and hand it straight back, so a caller can `return budget.record(...)`."""
        if owner is not None:                    # 93.Q3: the same two tools, recognised once
            from .recall_state import mark_search
            mark_search(owner, name, result, not _is_an_answer(result))
        if name in WATCHED and _is_an_answer(result):
            key = _key(name, args)
            if key not in self._answers:
                self._order.append(str((args or {}).get("query", "")).strip())
            held = self._answers.get(key, {}).get("limit")
            wanted = _limit_of(args)
            keep = wanted if held is None or wanted is None else max(held, wanted)
            self._answers[key] = {"result": result, "limit": keep}
        return result

    def queries(self) -> list:
        """What was actually searched this turn — so a receipt can say a search HAPPENED."""
        return list(self._order)


def budget_for(owner) -> RecallBudget:
    """The ledger belonging to this tool system, created on first use.

    Lives here rather than in `toolsys`, which is at its module ceiling, and keeps the whole limit --
    its rule, its state and its lifecycle -- in one file."""
    budget = getattr(owner, "_recall_budget", None)
    if budget is None:
        budget = owner._recall_budget = RecallBudget()
    return budget
