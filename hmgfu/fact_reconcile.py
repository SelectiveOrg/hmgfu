"""Phase 82.2 (Codex review 2, A2) — startup reconciliation of the two fact views.

The canonical view (`canonical_facts`) and the assertion view (`assertions`) are written in ONE transaction since 82.2, so
new divergence cannot happen; rows written before (two connections, two commits) may still disagree. At construction
`reconcile` REPAIRS and REPORTS: (a) `backfill` — a canonical row with no active assertion for (base slot, value) gets one
(77.3, unchanged); (b) `orphans` — an active positive assertion whose (relation, value) no canonical row supports, and
that no justification derives, is superseded (kept in history, never deleted). Idempotent; the report is on the store.
"""
from __future__ import annotations

import logging

from .assertions import now_iso
from .slots import base_slot

log = logging.getLogger("hmgfu.fact_reconcile")


def backfill(store) -> int:
    active_rel = {(a["relation"], (a["value"] or "").strip().lower()) for a in store.assertions.active()}
    n = 0
    for row in store.active():
        if not row["slot"] or not row["value"]:
            continue
        if (base_slot(row["key"]), row["value"].strip().lower()) in active_rel:
            continue
        store._record_assertion({"key": row["key"], "value": row["value"], "valid_from": None}, row.get("verbatim") or "")
        if row.get("source_turn_id"):                                   # 82.3: the canonical row's REAL link, carried over
            store.assertions.link_episode(base_slot(row["key"]), row["value"], row["source_turn_id"])
        n += 1
    return n


def relink(store) -> int:
    """82.3 (A4, Rule 11): assertions written before episode linking take the episode their canonical row recorded at
    write time (`source_turn_id`, set by the turn that derived the value) — a real link, never a backfill guess."""
    n = 0
    for row in store.active():
        if row.get("source_turn_id") and row.get("value"):
            n += store.assertions.link_episode(base_slot(row["key"]), row["value"], row["source_turn_id"])
    return n


def orphans(store) -> int:
    supported = {(base_slot(r["key"]), (r["value"] or "").strip().lower()) for r in store.active() if r["value"]}
    derived = {c for (c,) in store.assertions._db.execute("SELECT conclusion FROM justifications").fetchall()}
    n = 0
    for a in store.assertions.active():
        if a["id"] in derived or (a["relation"], (a["value"] or "").strip().lower()) in supported:
            continue
        store.assertions._db.execute("UPDATE assertions SET status='superseded', valid_to=? WHERE id=?", (now_iso(), a["id"]))
        n += 1
    return n


def provenance(store) -> dict:
    """82.3 (A4) report: active assertions with an episode link and with exact offsets; the relations still unlinked."""
    rows = store.assertions.active()
    return {"active": len(rows),
            "with_episode": sum(1 for a in rows if a.get("source_episode")),
            "with_span": sum(1 for a in rows if a.get("span_start") is not None),
            "unlinked": sorted(a["relation"] for a in rows if not a.get("source_episode"))}


def reconcile(store) -> dict:
    with store._lock:
        report = {"backfilled": backfill(store), "orphaned": orphans(store), "relinked": relink(store)}
        store._db.commit()
    if any(report.values()):
        log.warning("fact views reconciled at startup: %s", report)
    return report
