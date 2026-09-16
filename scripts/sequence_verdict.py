"""93.R1 — the strict half of the sequence verdict: what the stores hold, what the call did.

Separated from the probe so the judge can be tested on its own (v138) and reused. The two rules it
exists to enforce, both from the independent review of 93.F:

  * **an envelope is not learning.** The previous gate accepted any delta, or the mere presence of an
    envelope, so a refused proposal — or one committed with the wrong value, or filed under the wrong
    target, or stripped of the exception the user stated — counted as a success;
  * **a tool call is not execution.** `bench_say_do` fills `_tools` from the whole trace, failed and
    blocked calls included, so a call that raised counted as a widget.

The mere emission of an envelope stays worth recording — it separates "perception said nothing" from
"perception spoke and the write was refused" — but it is reported as its own metric, never folded
into the success gate.
"""
from __future__ import annotations

import re
from typing import Iterable, Optional


def _norm(value: Optional[str]) -> str:
    return " ".join((value or "").split()).strip(" .").casefold()


def _same_exception(stored: str, expected: str) -> bool:
    """93.RR4: EQUIVALENCE, not occurrence.

    Containment let a stored exception ADD to what the user said — "unless the user asks for the full
    context **or whenever convenient**" passed, and that extra disjunct is a case the user never
    granted. So the expected text must be there AND nothing else may be: after removing it, no word
    characters may remain. Punctuation and spacing are ignored; a negated, widened, narrowed or
    removed exception all leave or lack content and are refused, without depending on any list of
    phrases."""
    a, b = _norm(stored), _norm(expected)
    if not b:
        return not a                      # none stated: an invented one is still an invention
    if b not in a:
        return False                      # negated, widened or reworded away from what was said
    residue = a.replace(b, " ", 1)
    return not re.search(r"[^\W_]", residue, flags=re.UNICODE)


def taught_policy(directive_rows: Iterable[dict], *, expect_value: str,
                  expect_condition: str = "", kind: str = "response_style") -> bool:
    """True only when the policy is IN the store, under the right kind and value, and its exception is
    EQUIVALENT to the one the user stated — neither widened, narrowed, negated, invented nor dropped."""
    for row in directive_rows or []:
        if row.get("kind") != kind:
            continue
        if _norm(row.get("value")) != _norm(expect_value):
            continue
        wanted = ([expect_condition] if isinstance(expect_condition, str)
                  else list(expect_condition or [""]))
        # a probe may declare several spellings of the SAME statement ("unless I ask" / "unless the
        # user asks"); each is still matched by equivalence, so no extra case can slip in. The set is
        # declared up front by the probe, never widened after seeing a result.
        if not any(_same_exception(row.get("condition") or "", w) for w in wanted):
            continue
        return True
    return False


def tool_succeeded(tool_trace: Iterable[dict], name: str) -> bool:
    """Did this tool actually run to a result — not merely appear in the trace?"""
    return any(t.get("name") == name and not t.get("failed") and not t.get("blocked")
               for t in tool_trace or [])


def failures_of(tool_trace: Iterable[dict], name: str) -> list:
    """The failed or blocked attempts, so a run can say WHY it did not count."""
    return [{"name": t.get("name"), "blocked": bool(t.get("blocked")),
             "result": str(t.get("result"))[:120]}
            for t in tool_trace or []
            if t.get("name") == name and (t.get("failed") or t.get("blocked"))]
