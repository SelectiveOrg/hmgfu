"""92.E5R — what a learning turn actually wrote, judged against what it was allowed to write.

The previous oracle asked `bool(new_definition) == should_commit`. That accepts a definition of the
wrong term, or with the meaning inverted, as a PASS, and it cannot see an undue write at all: a
negative that quietly wrote a personal fact scored the same as a negative that wrote nothing. The
review was right that zero definitions on the negatives therefore demonstrated nothing about zero
undue writes.

So a turn is judged on three things, in this order:

  1. the definition, by TERM, MEANING and CONTEXT -- an inverted definition (`Cluster Routing Daemon`
     defined as `CRD-3`) is a wrong answer, not a smaller right one;
  2. every other write, across the ledger, the assertions and the directives, not only the store the
     probe happens to care about;
  3. what was ALLOWED. A message can legitimately state a preference while not being a definition, so
     each probe declares its permitted writes up front and anything outside them is undue. Labelling
     the allowance first is what stops "no delta" from being confused with "correct behaviour".

Used by the C/L probe and by the preparation check, so teaching and measurement judge by one rule.
"""
from __future__ import annotations

from typing import Iterable, Optional

DEFINITION_RELATION = "definition.meaning"


def snapshot(engine) -> dict:
    """Every write-visible store, keyed so a diff is meaningful rather than positional."""
    return {
        "facts": {r["key"]: r.get("value") for r in engine.facts.active()},
        "assertions": {(r.get("entity_id"), r.get("relation")): r.get("value")
                       for r in engine.facts.assertions.active()},
        "directives": {r["kind"]: r.get("value") for r in engine.directives.active()},
        # NOT a write set: the readable <context>::<term> key behind each opaque entity id, because
        # upsert_entity mints `definition:<hash8>` and the identity lives in the entities table.
        "entities": {e["id"]: e.get("name") or "" for e in engine.facts.assertions.entities()},
    }


def delta(before: dict, after: dict) -> list:
    """Added or changed entries, as (store, key, old, new). Removals count too: a write that
    supersedes is still a write."""
    out = []
    for store in ("facts", "assertions", "directives"):
        b, a = before.get(store, {}), after.get(store, {})
        for key in set(a) | set(b):
            if b.get(key) != a.get(key):
                out.append((store, key, b.get(key), a.get(key)))
    return sorted(out, key=lambda x: (x[0], str(x[1])))


def _norm(value: Optional[str]) -> str:
    return " ".join((value or "").split()).strip(" .").casefold()


def definition_change(changes: Iterable, term: str, meaning: str, context: Optional[str] = None,
                      names: Optional[dict] = None):
    """The change that defines `term` as `meaning` (in `context` when required), or None.

    Identity is resolved the way the WRITE resolved it: `upsert_entity` keeps the readable
    `<context>::<term>` key (learning_state.definition_entity_key) in the entities table and returns
    an opaque `definition:<hash8>`, so the term and the context come from `names`, never from the id.
    Inverting term and meaning fails here, which is the point."""
    names = names or {}
    for change in changes:
        store, key, _old, new = change
        if store != "assertions" or not isinstance(key, tuple) or key[1] != DEFINITION_RELATION:
            continue
        entity = str(names.get(key[0]) or key[0] or "")
        ctx, _, subject = entity.partition("::")
        if _norm(subject or entity) != _norm(term):
            continue
        if context is not None and _norm(ctx) and _norm(context) not in _norm(ctx):
            continue
        if _norm(new) == _norm(meaning):
            return change
    return None


def definition_written(changes: Iterable, term: str, meaning: str, context: Optional[str] = None,
                       names: Optional[dict] = None) -> bool:
    return definition_change(changes, term, meaning, context, names) is not None


def undue_writes(changes: Iterable, allowed: Iterable = ()) -> list:
    """Every change no allowance covers. An allowance is a dict of substring conditions:
    `{"store": "facts", "key": "pref.", "value": "kizomba"}` -- absent conditions do not constrain."""
    rules = list(allowed or ())
    out = []
    for change in changes:
        store, key, old, new = change
        text_key = "::".join(str(x) for x in key) if isinstance(key, tuple) else str(key)
        content = new if new is not None else old      # a clear is a change OF the old content
        if any(("store" not in r or r["store"] == store)
               and ("key" not in r or _norm(r["key"]) in _norm(text_key))
               and ("value" not in r or _norm(r["value"]) in _norm(content))
               for r in rules):
            continue
        out.append(change)
    return out


def judge_turn(changes: Iterable, *, expect_definition=None, allowed=(), names=None) -> dict:
    """One verdict for one turn: was the required definition written, and what else was written.

    `expect_definition` is (term, meaning[, context]) or None for a turn that must define nothing.
    `names` maps entity ids to their readable keys, without which term and context cannot be read."""
    changes = list(changes)
    if expect_definition:
        term, meaning = expect_definition[0], expect_definition[1]
        context = expect_definition[2] if len(expect_definition) > 2 else None
        match = definition_change(changes, term, meaning, context, names)
        ok = match is not None
        rest = [c for c in changes if c != match]      # the required write is not an undue one
    else:
        ok = not any(store == "assertions" and isinstance(key, tuple)
                     and key[1] == DEFINITION_RELATION for store, key, _o, _n in changes)
        rest = changes
    undue = undue_writes(rest, allowed)
    return {"definition_ok": ok, "undue": undue, "correct": ok and not undue,
            "changes": [(st, str(k), o, n) for st, k, o, n in changes]}
