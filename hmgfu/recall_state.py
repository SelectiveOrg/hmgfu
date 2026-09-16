"""93.Q3 — which of four states the turn is in, so the assistant stops overclaiming about its memory.

A live run answered *"I don't have a specific location recorded in our conversation yet"* while the
location was stored and merely outside the retrieved context. Not inventing a location was right;
saying it is not recorded was a claim about the MEMORY made from the CONTEXT, and the two are
different things.

The states, and why they are not one:

  * **answered** — the retrieved evidence covers the relation asked for. Nothing more is needed, and
    searching anyway would be a cost with no question behind it.
  * **related_only** — there are memories about the topic but none that answer. This is the state
    that was being reported as absence; what it warrants is a focused look, not a conclusion.
  * **searched_without_result** — a search ran and did not find it. Now "I could not find it" is
    honest, provided it says what was searched. Asking again the same way would be a loop.
  * **tool_unavailable** — the search could not run. That is a limitation of this turn, and saying
    the memory is empty would be inventing a fact about oneself.

The classification is deliberately blunt: it asks whether any retrieved line carries the relation the
question is about, using the question's own words rather than a list of phrases. A blunt rule that
refuses to conclude absence is safer here than a clever one that sometimes does.
"""
from __future__ import annotations

import re

RECALL_STATES = ("answered", "related_only", "searched_without_result", "tool_unavailable")

def recall_state(*, needs_memory: bool, searched: bool, found: bool = False,
                 tool_failed: bool = False) -> str:
    """Which of the four states this turn is in, from what the system already knows.

    93.Q3: an earlier attempt judged sufficiency by comparing the question's words with the retrieved
    lines. That is a semantic judgement dressed as a lexical one -- every memory about the party
    shares words with a question about the party -- and the review is explicit that coverage, not
    topical resemblance, is what matters. So this reuses the judgement the router already makes and
    the contract already carries: `needs_memory`, the model's own statement that the context in front
    of it does not answer the turn. The rest are facts, not judgements: whether a search ran, whether
    it found anything, whether the tool worked."""
    if tool_failed:
        return "tool_unavailable"
    if searched:
        return "answered" if found else "searched_without_result"
    return "related_only" if needs_memory else "answered"


def should_search(state: str) -> bool:
    """Only the state that has a question left to answer asks for a search.

    93.Q3: not a rule to search on every turn. `answered` needs nothing, and repeating an identical
    search after one that found nothing is the loop the recall budget already refuses."""
    return state == "related_only"


def describe(state: str) -> str:
    """How to say this honestly, without turning an empty context into an empty memory."""
    return {
        "answered": "the retrieved memories answer this",
        "related_only": ("there are memories about this topic but none of them says what was asked; "
                         "look further before saying anything about what is or is not stored"),
        "searched_without_result": ("a search ran and did not find it; say that you could not find "
                                    "it and what you searched for, not that it was never said"),
        "tool_unavailable": ("the search could not run this turn; say so as a limitation of the "
                             "turn, never as an empty memory"),
    }.get(state, "")


def mark_search(owner, name: str, result: str, failed: bool) -> None:
    """Record that an internal search ran this turn, and whether it brought anything back.

    93.Q3: these are the facts `recall_state` reads. Kept here with the states rather than in the tool
    dispatcher, which is at its module ceiling and has no business knowing what they are for."""
    if name not in ("memory_search", "memory_timeline"):
        return
    marks = getattr(getattr(owner, "engine", None), "_turn_recall", None)
    if not isinstance(marks, dict):
        return
    marks["searched"] = True
    marks["tool_failed"] = bool(failed)
    empty = '"results": []' in (result or "") or '"rows": []' in (result or "")
    marks["found"] = bool(marks.get("found") or (not failed and not empty))
