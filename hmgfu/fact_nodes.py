"""Graph-side supersession (split out of facts.py at the 400-line ceiling, Phase 77.3): demote the EPISODIC nodes that
carry a value the ledger has superseded or a user correction has named as wrong. The ledger (facts.py) decides what is
true; this module makes recall stop surfacing what no longer is. Imported by facts.py for compatibility."""
from __future__ import annotations

import re
from typing import List

from .slots import value_in_text


def stale_pairs(store: "FactStore") -> List[tuple]:
    """(attribute-or-term, old value, current value) for every supersession the ledger holds: canonical
    facts (`superseded_values`, with 72.6g's reverted values whose current is "" -- demote even beside the
    current value) and definitions (assertion history: a superseded row with an active successor)."""
    active = store.active()
    reverted = {(k, v.lower()) for k, v in store.reverted_values()}
    out = []
    for key, old in store.superseded_values():
        current = "" if (key, old.lower()) in reverted else next((f["value"] for f in active if f["key"] == key), "")
        out.append((key, old, current))
    assertions = getattr(store, "assertions", None)
    if assertions is not None:
        names = {e["id"]: (e.get("name") or "").partition("::")[2] for e in assertions.entities(kind="definition")}
        rows = assertions.history()
        for h in rows:
            if h["status"] != "superseded" or h["entity_id"] not in names:
                continue
            cur = next((r["value"] for r in rows if r["entity_id"] == h["entity_id"] and r["relation"] == h["relation"]
                        and r["status"] == "active"), "")
            if cur and cur.strip().lower() != h["value"].strip().lower():
                out.append(("term:" + names[h["entity_id"]], h["value"], cur))
    return out


def born_stale(store: "FactStore", text: str, pairs=None) -> bool:
    """95.22: does this text assert a superseded value of an attribute (or term) it talks about, without
    the current one? Conservative on purpose (94.6): same attribute, old value present, current value
    absent -- a history that carries both survives, and so does the correction itself."""
    from .slots import mentions_attribute
    text = text or ""
    for key, old, current in (pairs if pairs is not None else stale_pairs(store)):
        if key.startswith("term:"):
            if not value_in_text(key[5:], text):
                continue                                   # a definition is about ITS term
        elif not mentions_attribute(key, text):
            continue                                       # 69.4: the node must talk about THIS attribute
        if value_in_text(old, text) and (not current or not value_in_text(current, text)):
            return True
    return False


def supersede_stale_nodes(store: "FactStore", graph) -> int:
    """Demote episodic nodes carrying a now-superseded value out of recall (the stale 'My name is
    Sebastian' nodes after the correction to Teodoro). 94.6: macros are IN (the digest injected into the
    next session went on asserting the old value); skills stay out (a tool description mentioning a
    value is not asserting it). 95.22: the same rule as `born_stale`, applied to every active point."""
    pairs = stale_pairs(store)
    demoted = 0
    for p in graph.all_points():   # H-04: locked snapshot
        if p.status != "active" or p.type == "skill":
            continue
        if born_stale(store, p.content + " " + p.summary, pairs):
            p.status = "superseded"
            graph.save_point(p)
            demoted += 1
    return demoted


def has_supersession(fact_changes, learning) -> bool:
    """95.2b: did THIS turn supersede or clear a canonical value -- by the regex path (`fact_changes`)
    OR by the protocol (`learning["effects"][*]["effects"]`, 95.2)? The demotion trigger reads both, so
    a correction the protocol wrote demotes the stale nodes exactly as a regex-written one does."""
    changes = list(fact_changes or [])
    for eff in (learning or {}).get("effects") or []:
        inner = eff.get("effects") if isinstance(eff, dict) else None
        if isinstance(inner, list):
            changes.extend(c for c in inner if isinstance(c, dict))
    return any(c.get("prev") or c.get("cleared") for c in changes)


def demote_after_supersession(engine, message: str = "", learning=None) -> list:
    """95.18: everything a supersession of THIS turn must demote, whichever writer made it. The canonical
    path (`supersede_stale_nodes`, 94.6/95.2b) as before; and every DEFINITION revision the protocol
    wrote is curated here -- the corrected definition ingested as a user_explicit fact (the winner) and
    the bearers of the prior value superseded (`supersede_named_stale`) -- instead of waiting for the
    grader's nano to perceive a correction (L1 c95g rep3: `correction: null`, nothing demoted, the
    stale echo reinforced, the new session answered the old value). Pairs are remembered on
    `engine._turn_curated` so the grader's path never curates the same pair twice."""
    from .facts import supersede_stale_nodes
    supersede_stale_nodes(engine.facts, engine.graph)
    curated = getattr(engine, "_turn_curated", None)
    if curated is None:
        curated = engine._turn_curated = {}
    out = []
    for eff in (learning or {}).get("effects") or []:
        for c in (eff.get("effects") if isinstance(eff, dict) and isinstance(eff.get("effects"), list) else []):
            prev, value = str(c.get("prev") or ""), str(c.get("value") or "")
            if not prev or not value or (prev, value) in curated or not str(c.get("key", "")).startswith("definition:"):
                continue
            subject = str(c.get("subject") or "").strip()
            winner = engine.ingest(f"{subject} means {value}" if subject else value, source="user_explicit", mtype="fact")
            named = supersede_named_stale(engine.graph, winner, prev, value, context=message)
            curated[(prev, value)] = winner.id
            out.append({"prev": prev, "value": value, "winner": winner.id, "superseded": named["superseded"],
                        "ambiguous": named["ambiguous"]})
    return out


def supersessions_from_message(assertions, message: str) -> List[tuple]:
    """95.1b: the (old, new) value pairs the assertions store superseded BECAUSE OF this message.

    The successor carries the message as its `source_span` (learning_apply writes it so) and each
    predecessor's `valid_to` equals the successor's `recorded_at` (assert_ stamps both with one `now`).
    This is what grounds a correction on subject + attribute + revision instead of on the nano's free
    phrase, which only ever matched points that repeated the user's wording."""
    text = (message or "").strip()
    if not text or assertions is None:
        return []
    rows = assertions.history()
    fresh = [r for r in rows if r["status"] == "active" and (r.get("source_span") or "").strip()
             and text.startswith((r.get("source_span") or "").strip())]
    out = []
    for r in fresh:
        for h in rows:
            if (h["entity_id"] == r["entity_id"] and h["relation"] == r["relation"]
                    and h["status"] == "superseded" and h["valid_to"] == r["recorded_at"]
                    and (h["value"], r["value"]) not in out):
                out.append((h["value"], r["value"]))
    return out


def _words(s: str) -> set:
    # 95.1b-ii: a QUOTED subject ('ACME-7') tokenised as "'acme" and never overlapped the subject set,
    # so every point that quotes the subject -- system summaries do -- was invisible. Edge apostrophes
    # are stripped; an inner one (i've, user's) is kept. Same tokens for both sides of the overlap.
    return {w for w in (t.strip("'") for t in re.findall(r"[\w']+", (s or "").lower())) if len(w) > 3}


def supersede_named_stale(graph, winner, wrong: str, right: str, context: str = "") -> dict:
    """A user correction NAMES the stale value (`wrong`) → supersede the active fact(s) that assert it
    directly, TARGETED by the perceiver's own signal instead of re-derived by a downstream heuristic
    (Rule 13). The FREE-FORM sibling of supersede_stale_nodes (no canonical key): catches same-attribute
    value swaps (blue↔green, Valencia↔Aveiro) that dream.contradiction_heuristic (use_nano=False) misses.
    I1-safe — `winner` is the user_explicit corrected fact, so mark_tension flips only the loser.

    A correction is ABSORBING, so it fires ONLY on an UNAMBIGUOUS resolution to an EXISTING fact
    (na dúvida, não disparar). The stale node must CONTAIN the old value, NOT the new one, AND share
    the correction's SUBJECT — the significant words of `context` (the user's message) ∪ the `winner`
    tokens, minus the swapped values (the perceiver often returns `right` as a bare value, so the
    message carries the subject). Returns {"superseded": [ids], "ambiguous": None | reason}: no wrong
    value / no subject to disambiguate / no matching active fact → fire NOTHING and return the reason
    (the caller logs it + records the Regulator signal, keeping facts.py regulator-free)."""
    from .dream import mark_tension                       # lazy: facts→dream is one-way (no cycle)
    wl, rl = (wrong or "").strip().lower(), (right or "").strip().lower()
    if len(wl) < 2:
        return {"superseded": [], "ambiguous": "no_wrong_value"}
    # RAW bearers of the OLD value that don't already carry the new one (an active fact asserting `wrong`).
    def _txt(p):
        return (p.content + " " + (p.summary or "")).lower()
    raw = [p for p in graph.active_points()                      # 94.6: macros included, same reason
           if p.id != winner.id and p.type != "skill"              # as supersede_stale_nodes above
           and wl in _txt(p) and not (rl and rl in _txt(p))]
    if not raw:                                          # the old value is not a stored fact → nothing to do
        return {"superseded": [], "ambiguous": "no_target"}
    # Disambiguate to an UNAMBIGUOUS target. Subject = the correction's concept words (message ∪ winner)
    # minus the OLD value. Prefer bearers that share the subject; but a SINGLE bearer of the old value is
    # itself unambiguous (the correction may rephrase the subject — "sou de Aveiro" vs stored "moro em
    # Valencia" — sharing only the value). Many bearers + no subject match → ambiguous, don't fire.
    subject = (_words(context) | _words(" ".join(winner.keywords + winner.entities + winner.topics))) - _words(wl)
    keyed = [p for p in raw if subject & _words(_txt(p))] if subject else []
    if keyed:
        targets = keyed
    elif len(raw) == 1:
        targets = raw                                    # unique bearer → unambiguous even without subject
    else:
        return {"superseded": [], "ambiguous": "ambiguous_subject"}   # can't pick the target → don't fire
    superseded: List[str] = []
    for p in targets:
        mark_tension({"a": p.id, "b": winner.id, "score": 0.9,
                      "resolution": {"winner": winner.id, "loser": p.id}}, graph)
        if graph.points[p.id].status == "superseded":
            superseded.append(p.id)
    return {"superseded": superseded, "ambiguous": None}
