"""First-class canonical facts (PA3 hmg_fact_statements analog; sibling of directives.py).

The nano summary is LOSSY — it turned "My name is Teodoro Ferreira" into "corrects an
identity", dropping the value the model needs. So identity/value facts are captured with their
LITERAL value, keyed by concept, and a NEW value DETERMINISTICALLY supersedes the old (no fuzzy
scoring). They are injected VERBATIM at the front of memory context, and the old value's episodic
nodes are marked superseded so they drop out of recall.
"""

from __future__ import annotations

import re
import sqlite3
import threading
from typing import List, Optional

from . import config
from .db import connect as db_connect
from .models import now_iso
from .fact_detect import (_DECLARATIVE_CUE, _VALUE_STOP, _looks_like_name,  # noqa: F401 (re-exports)
                          _plausible_open_fact, detect_fact, detect_facts, name_value_ok)
from .slots import base_slot, infer_slot_from_value, is_reference_to_attribute, is_slot, label_for, normalise_key, value_in_text
from .speech_act import is_interrogative
from .value_gate import correction_antecedent, utterance_subject   # 91.V1/V2

class FactStore:
    def __init__(self, db_path: Optional[str] = None):
        self._lock = threading.RLock()
        self._subject_by_session: dict = {}   # 91.W2: the previous utterance's subject, PER SESSION
        self._db = db_connect(db_path or config.DB_PATH)
        from .assertions import AssertionStore
        self.assertions = AssertionStore(db_path or config.DB_PATH, conn=self._db)   # 72.2 C/R objects; 82.2: ONE connection, one revision
        self._db.execute("CREATE TABLE IF NOT EXISTS canonical_facts ("
                         "key TEXT PRIMARY KEY, value TEXT, prev_value TEXT, source TEXT, "
                         "updated_at TEXT, verbatim TEXT, source_turn_id TEXT)")
        for col in ("verbatim TEXT", "source_turn_id TEXT"):   # P1 additive migration for existing DBs
            try:
                self._db.execute(f"ALTER TABLE canonical_facts ADD COLUMN {col}")
            except sqlite3.OperationalError:
                pass                                           # column already there
        # Phase 62: append-only history (every set/clear), keyed by the closed slot vocabulary
        self._db.execute("CREATE TABLE IF NOT EXISTS fact_history (id INTEGER PRIMARY KEY, key TEXT, "
                         "value TEXT, prev_value TEXT, source TEXT, op TEXT, updated_at TEXT, verbatim TEXT)")
        self._db.commit()
        self._mapper = None
        self.open_slot_regex_writes = True      # 84.2: set per turn from settings by the engine; the bench sets it directly
        self.use_mapper = True                  # 84.3: False when fact_mapper_mode is spans/off (the legacy mapper stays bound)
        self._rekey_legacy()
        from .fact_reconcile import reconcile
        self.reconcile_report = reconcile(self)                         # 77.3 backfill + 82.2 orphan sweep, reported

    def bind_mapper(self, mapper) -> None:
        """Model-backed slot mapper (slots.map_to_slot bound to a provider) — used ONLY for
        declarative statements the regex did not resolve to a closed slot. Advisory."""
        self._mapper = mapper

    def _rekey_legacy(self) -> None:
        """Idempotent migration: rows written before the closed schema are re-keyed through
        `normalise_key`; when two spellings collapse to one slot the NEWEST value wins and the
        older becomes its prev (the fragmentation the autopsy found, healed in place)."""
        with self._lock:
            rows = self._db.execute("SELECT key, value, prev_value, source, updated_at, verbatim, "
                                    "source_turn_id FROM canonical_facts").fetchall()
            by_slot: dict = {}
            for row in rows:
                by_slot.setdefault(normalise_key(row[0]), []).append(row)
            for new_key, group in by_slot.items():
                if len(group) == 1 and group[0][0] == new_key:
                    continue
                group.sort(key=lambda r: r[4] or "")
                newest = group[-1]
                prev = group[-2][1] if len(group) > 1 else newest[2]
                for r in group:
                    self._db.execute("DELETE FROM canonical_facts WHERE key=?", (r[0],))
                self._db.execute("INSERT OR REPLACE INTO canonical_facts VALUES (?, ?, ?, ?, ?, ?, ?)",
                                 (new_key, newest[1], prev, newest[3], newest[4], newest[5], newest[6]))
            self._db.commit()

    def _resolve(self, text: str, session: Optional[str] = None) -> List[dict]:
        """Regex first (deterministic), keys normalised to the closed schema; the model mapper
        only for declarative statements the regex left open/unresolved. Never a question.
        Returns EVERY grounded fact in the utterance (audit H: multi-fact speech)."""
        from .utterance import declarative_clauses
        clauses = declarative_clauses(text)   # 91.AA3: modality-licensed PROPOSITIONS
        if not clauses:
            return []
        texts = [c["text"] if c["text"][-1:] in ".!?;:" else c["text"] + "." for c in clauses]   # keep the boundary
        dated = {(d["key"], d.get("value")): c["valid_from"] for c, t in zip(clauses, texts) if c.get("valid_from") for d in detect_facts(t)}
        text = joined = " ".join(texts)      # 91.AA3: detection AND the mapper see only LICENSED text
        dets = detect_facts(joined) or correction_antecedent(joined, self._subject_by_session.get(session), dict(self.active_pairs()))  # 91.V1/V2/W2
        found = []
        for det in dets:
            det["valid_from"] = dated.get((det["key"], det.get("value")), det.get("valid_from"))   # ITS clause date
            det["key"] = normalise_key(det["key"])
            if det["key"] in ("open.favorite", "open.preferred", "open.favorite_one") and det.get("value"):
                det["key"] = infer_slot_from_value(det["value"]) or det["key"]
            if det.get("value") and ((not det.get("trusted") and not name_value_ok(det["key"], det["value"]))   # 83.3: "that's my actual name"
                                     or is_reference_to_attribute(det["key"], det["value"])):     # 95.30: "my main project" is the attribute, not its value
                continue                         # 77.5 (A): a predicate is not a name ("my dog Rex is 4 years old")
            if det.get("weak") and not is_slot(det["key"]):
                continue                         # 77.5: a colon form ("my X: Y") counts only for a closed slot
            if det.get("clear"):
                if is_slot(det["key"]):
                    found.append(det)
                continue
            if not is_slot(det["key"]) and det.get("update"):
                cand = self._slot_by_value_type(det.get("value", ""))                        # 67.5
                if cand and _update_subject_fits(det["key"], cand):
                    det["key"] = cand         # 69.4: "new recipe: URL" is NOT the car link — subject must fit
            if not is_slot(det["key"]) and not _plausible_open_fact(det):
                continue                         # the regex may not mint junk open keys
            if not is_slot(det["key"]) and not self.open_slot_regex_writes and det.get("path", "regex") == "regex":
                continue                         # 84.2: open keys from the regex are OFF — the mapper may still write one
            found.append(det)
        found = _cardinality(found, text)             # 72.3: two dogs in ONE message = two entities (pet.dog.name, pet.dog.name.2)
        seen: set = set()          # two surface forms of the same slot in one utterance = one write —
        found = [d for d in reversed(found) if not (d["key"] in seen or seen.add(d["key"]))][::-1]   # the LAST wins (69.4)
        if not any(is_slot(d["key"]) for d in found) and self._mapper is not None and self.use_mapper \
                and _DECLARATIVE_CUE.search(text):
            mapped = self._mapper(text)          # grounded by slots.map_to_slot (value must be in text)
            if mapped and mapped.get("value") and not name_value_ok(mapped["key"], mapped["value"]):
                mapped = None                    # 77.5 (A): the mapper's name values pass the same gate
            if mapped:
                mapped["path"] = "mapper"                                  # 84.1: which path wrote it (the ruler needs to know)
                found = [mapped] + [d for d in found if d["key"] != mapped["key"]]
        for d in found:
            d.setdefault("path", "regex")
        return found

    def _slot_by_value_type(self, value: str) -> Optional[str]:
        """67.5: an update that names no owner ("here's the updated link: URL") targets the ONE existing
        slot whose current value has the same type (URL / number); ambiguity → no guess."""
        v = (value or "").strip()
        kind = "url" if re.match(r"https?://", v, re.IGNORECASE) else ("number" if re.fullmatch(r"[\d.,]+", v) else None)
        if kind is None:
            return None
        matches = [f["key"] for f in self.active() if f["slot"] and (
            (kind == "url" and re.match(r"https?://", f["value"] or "", re.IGNORECASE))
            or (kind == "number" and re.fullmatch(r"[\d.,]+", (f["value"] or "").strip())))]
        return matches[0] if len(matches) == 1 else None

    def apply(self, text: str, source: str = "user") -> Optional[dict]:
        """Compatibility wrapper: applies EVERY fact in the utterance, returns the first change."""
        changes = self.apply_all(text, source)
        return changes[0] if changes else None

    def apply_all(self, text: str, source: str = "user", session: Optional[str] = None, hold_keys=()) -> List[dict]:
        held = {base_slot(k) for k in (hold_keys or ())}      # 95.46: slots the protocol is asking about this turn
        out = [c for c in (self._apply_one(d, text, source) for d in self._resolve(text, session) if base_slot(d["key"]) not in held) if c]
        self._subject_by_session[session] = utterance_subject(text)   # what THIS utterance was about, for a later correction
        return out

    def _apply_one(self, det: dict, text: str, source: str) -> Optional[dict]:
        """82.2 (Codex A2): the canonical row, its history row and its assertion are ONE transaction on ONE connection —
        an exception anywhere rolls all of them back; nothing is committed until the whole revision is written."""
        with self._lock:
            try:
                out = self._apply_locked(det, text, source)
                self._db.commit()
                return out
            except Exception:
                self._db.rollback()
                raise

    def _apply_locked(self, det: dict, text: str, source: str) -> Optional[dict]:
        with self._lock:
            if det.get("clear"):
                # retraction by selector: whatever the slot holds is retired (tombstone in history)
                row = self._db.execute("SELECT value FROM canonical_facts WHERE key=?", (det["key"],)).fetchone()
                if not row:
                    return None
                self._db.execute("DELETE FROM canonical_facts WHERE key=?", (det["key"],))
                self._db.execute("INSERT INTO fact_history (key, value, prev_value, source, op, updated_at, "
                                 "verbatim) VALUES (?, ?, ?, ?, 'clear', ?, ?)",
                                 (det["key"], "", row[0], source, now_iso(), text.strip()))
                self._retract_assertion(det["key"], row[0])                      # 77.3: the assertion retires with the slot
                return {"key": det["key"], "cleared": row[0]}
            if det.get("clear_value"):
                # negation only ("I'm not X") — if X was the stored value, retire it
                row = self._db.execute("SELECT value FROM canonical_facts WHERE key=?",
                                       (det["key"],)).fetchone()
                if row and row[0].lower() == det["clear_value"].lower():
                    self._db.execute("DELETE FROM canonical_facts WHERE key=?", (det["key"],))
                    self._db.execute("INSERT INTO fact_history (key, value, prev_value, source, op, "
                                     "updated_at, verbatim) VALUES (?, ?, ?, ?, 'clear', ?, ?)",
                                     (det["key"], "", row[0], source, now_iso(), text.strip()))
                    self._retract_assertion(det["key"], row[0])                  # 77.3
                    return {"key": det["key"], "cleared": det["clear_value"]}
                return None
            prev = self._db.execute("SELECT value FROM canonical_facts WHERE key=?",
                                    (det["key"],)).fetchone()
            if prev and prev[0].strip().lower() == det["value"].strip().lower():
                return None                         # restated, unchanged: no write, no history row
            prev_val = prev[0] if prev else det.get("supersedes")
            # P1 provenance spine ("a gravação"): the EXACT user words are stored with the derived
            # value at WRITE time — never reconstructed later (Plan.txt G1 falsifier).
            ts = now_iso()
            self._db.execute("INSERT OR REPLACE INTO canonical_facts VALUES (?, ?, ?, ?, ?, ?, ?)",
                             (det["key"], det["value"], prev_val, source, ts, text.strip(), None))
            self._db.execute("INSERT INTO fact_history (key, value, prev_value, source, op, updated_at, "
                             "verbatim) VALUES (?, ?, ?, ?, 'set', ?, ?)",
                             (det["key"], det["value"], prev_val, source, ts, text.strip()))
            self._record_assertion(det, text)                            # 72.2: C object with entity + validity
            if prev_val and prev_val.strip().lower() != det["value"].strip().lower():
                from .slots import base_slot
                self.assertions.supersede_value(base_slot(det["key"]), prev_val)   # 77.3: the replaced value's assertion retires too
            if det.get("supersedes"):
                self._retract_named(det["key"], det["supersedes"], source, text)   # 72.3: "Teca, not Bento"
            return {"key": det["key"], "value": det["value"], "prev": prev_val, "path": det.get("path", "regex")}

    def _retract_assertion(self, key: str, value: str) -> int:
        """77.3: a canonical clear retires the assertion it came from (relation = base slot, same value) — for the user
        entity and for a named pet entity alike. Before this, only named negations reached the assertion store."""
        from .slots import base_slot
        return self.assertions.retract(None, base_slot(key), value)

    def _backfill_assertions(self) -> int:
        """77.3 (Rule 11): legacy canonical rows without an assertion get one — body in `fact_reconcile` (82.2)."""
        from .fact_reconcile import backfill
        return backfill(self)

    def _record_assertion(self, det: dict, text: str) -> None:
        base = base_slot(det["key"])
        if base.startswith("pet."):
            entity = self.assertions.upsert_entity("pet", det["key"])   # 95.32: the animal (its slot), not its current name
            relation = base
        else:
            entity, relation = "user", base
        from .assertions import locate_value
        start, end = locate_value(text, det["value"])                     # 82.3: exact offsets into the ORIGINAL message
        self.assertions.assert_(entity, relation, det["value"], valid_from=det.get("valid_from"), source_span=text,
                                span_start=start, span_end=end)

    def _retract_named(self, key: str, wrong: str, source: str, text: str) -> None:
        """A named negation ("my dog is Teca, not Bento") retires `wrong` wherever the SAME family holds it — a legacy
        pet.name=Bento must not survive as a second current pet (Codex 69 finding E). 82.1 (Codex review 2, A1): the
        assertion side is scoped like the canonical side — before, it retracted by bare value across every entity and
        relation, so a user named Bento lost their name when the dog Bento was retired. 82.5: the scope is the SAME base
        slot plus the legacy species-less `pet.name` — a cat named Bento survives the dog's correction."""
        from .slots import base_slot
        base = base_slot(key)
        scope = {base} | ({"pet.name"} if base.startswith("pet.") else set())    # 82.5: same slot (+ legacy species-less pet.name), never another species
        with self._lock:
            rows = self._db.execute("SELECT key, value FROM canonical_facts WHERE key<>?", (key,)).fetchall()
            for k, v in rows:
                if base_slot(k) in scope and (v or "").strip().lower() == wrong.strip().lower():
                    self._db.execute("DELETE FROM canonical_facts WHERE key=?", (k,))
                    self._db.execute("INSERT INTO fact_history (key, value, prev_value, source, op, updated_at, verbatim) "
                                     "VALUES (?, '', ?, ?, 'clear', ?, ?)", (k, v, source, now_iso(), text.strip()))
        for rel in scope:
            self.assertions.retract(None, rel, wrong)                          # committed by _apply_one (82.2)

    def history(self, key: Optional[str] = None, limit: int = 50) -> List[dict]:
        """Append-only slot history (oldest -> newest)."""
        with self._lock:
            if key:
                rows = self._db.execute("SELECT key, value, prev_value, source, op, updated_at, verbatim "
                                        "FROM fact_history WHERE key=? ORDER BY id DESC LIMIT ?",
                                        (key, limit)).fetchall()
            else:
                rows = self._db.execute("SELECT key, value, prev_value, source, op, updated_at, verbatim "
                                        "FROM fact_history ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [{"key": k, "value": v, "prev": p, "source": s, "op": o, "updated_at": u, "verbatim": vb}
                for k, v, p, s, o, u, vb in reversed(rows)]

    def link_source(self, key: str, turn_id: str) -> None:
        """P1: attach the source-turn point id to a canon row written THIS turn — the caller passes
        the id of the very message `apply` derived the value from (a real link, never a backfill)."""
        from .slots import base_slot
        with self._lock:
            self._db.execute("UPDATE canonical_facts SET source_turn_id=? WHERE key=?", (turn_id, key))
            row = self._db.execute("SELECT value FROM canonical_facts WHERE key=?", (key,)).fetchone()
            if row and row[0]:
                self.assertions.link_episode(base_slot(key), row[0], turn_id)   # 82.3 (A4): the assertion links too
            self._db.commit()

    def active(self) -> List[dict]:
        with self._lock:
            rows = self._db.execute("SELECT key, value, prev_value, updated_at, verbatim, "
                                    "source_turn_id, source FROM canonical_facts").fetchall()
        return [{"key": k, "value": v, "prev": p, "updated_at": u, "verbatim": vb, "source_turn_id": s,
                 "source": src, "label": label_for(k), "slot": is_slot(k)}
                for k, v, p, u, vb, s, src in rows]

    def active_pairs(self) -> List[tuple]:
        """78.3: (key, value) of the active canonical slots — the echo test's ledger."""
        return [(row["key"], row["value"]) for row in self.active() if row["slot"] and row["value"]]

    def render_lines(self) -> List[str]:
        """Verbatim CURRENT canonical-fact lines for the FRONT of the memory context. The
        superseded value is DELIBERATELY excluded: naming it leaked the old value into every
        identity answer (bench L4 — both gemma AND ornith parroted "(corrected from Sebastian)").
        Supersession is already enforced by the keyed store + supersede_stale_nodes + the
        trust-most-recent injection header; the front-of-context line states only what IS."""
        # 77.3: ONE read path — the rendered line comes from the ASSERTION store (query-time validity, one row per entity,
        # `supported()` = the justification gate; no product path writes justifications yet, so it passes everything
        # directly asserted — wired, and said so). canonical_facts remains the projection the provenance helpers read.
        lines, seen = [], set()
        for a in self.assertions.active():
            rel = a["relation"]
            if not is_slot(rel) or not a["value"] or not self.assertions.supported(a["id"]):
                continue
            key = (rel, a["value"].strip().lower())
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"Your {label_for(rel)} is {a['value']}")
        return lines

    def render_history_lines(self, limit: int = 8) -> List[str]:
        """72.3: what WAS true — for past-cue questions ("where did I live before?"), instead of relying on a globally
        demoted memory. Distinct (slot, old value) pairs that differ from the current value, newest first."""
        current = {f["key"]: (f["value"] or "").lower() for f in self.active()}
        lines, seen = [], set()
        with self._lock:
            rows = self._db.execute("SELECT key, value, prev_value, op, updated_at, source FROM fact_history ORDER BY id DESC").fetchall()
        # 72.6g: a value UNDONE by a rollback/migration row was never true for the user (the Phase 69 probe "Chimoio")
        reverted = {(k, (p or "").lower()) for k, _v, p, _op, _ts, src in rows if src in _REVERT_SOURCES and p}
        for key, val, prev, op, ts, src in rows:
            if not is_slot(key) or src in _REVERT_SOURCES:
                continue
            for old in ((prev,) if op == "set" else (prev, val)):
                if old and old.lower() != current.get(key, "") and (key, old.lower()) not in seen \
                        and (key, old.lower()) not in reverted:
                    seen.add((key, old.lower()))
                    lines.append(f"Before {ts[:10]}, your {label_for(key)} was {old}")
            if len(lines) >= limit:
                break
        return lines

    def reverted_values(self) -> List[tuple]:
        """72.6g: (key, value) pairs UNDONE by a rollback/migration row — values that were never true for the user
        (the Phase 69 probe). Stronger than superseded: nodes carrying them are demoted even beside the current value."""
        with self._lock:
            rows = self._db.execute("SELECT key, prev_value FROM fact_history WHERE source IN (%s) AND prev_value IS NOT NULL"
                                    % ",".join("?" * len(_REVERT_SOURCES)), tuple(sorted(_REVERT_SOURCES))).fetchall()
        return [(k, p) for k, p in rows if p]

    def superseded_values(self) -> List[tuple]:
        """(key, old_value) pairs whose episodic memory nodes should be demoted from recall:
        the previous value AND every earlier distinct value in the slot's history (Phase 62 —
        after Python→Rust→Java, both Python and Rust are stale, not just Rust)."""
        out, seen = [], set()
        current = {f["key"]: f["value"].lower() for f in self.active()}
        for f in self.active():
            if f["prev"] and f["prev"].lower() != f["value"].lower():
                out.append((f["key"], f["prev"])); seen.add((f["key"], f["prev"].lower()))
        with self._lock:
            rows = self._db.execute("SELECT key, value, prev_value, op FROM fact_history").fetchall()
        for key, val, prev, op in rows:
            if key not in current:
                if op == "clear" and prev and (key, prev.lower()) not in seen:   # 69.4: a retired value is stale too
                    out.append((key, prev)); seen.add((key, prev.lower()))
                continue
            for v in (val, prev):
                if v and v.lower() != current[key] and (key, v.lower()) not in seen:
                    out.append((key, v)); seen.add((key, v.lower()))
        return out


_REVERT_SOURCES = {"migration", "rollback", "audit"}          # history rows that UNDO a write, never user history
_GENERIC_SUBJECT = {"link", "url", "number", "numero", "value", "valor", "address", "endereco", "one", "info", "data", "code", "codigo", "id"}


def _update_subject_fits(open_key: str, slot: str) -> bool:
    """69.4 → 72.3: an update form binds to the same-type slot only when its subject is ONLY generic words
    ("updated link") or names that slot ("updated car location link") — never "new recipe link" onto the car link."""
    from .slots import _tokens, normalise_key
    subject = open_key.split(".", 1)[-1]
    toks = {t for t in _tokens(subject)}
    return (bool(toks) and toks <= _GENERIC_SUBJECT) or normalise_key(subject) == slot


_PLURAL = re.compile(r"\b(two|three|both|different|another|other|second|dois|duas|tr[eê]s|ambos|ambas|diferentes|outro|outra|"
                     r"segundo|segunda|tamb[eé]m)\b", re.IGNORECASE)


def _cardinality(found: List[dict], text: str) -> List[dict]:
    """72.3: when ONE message asserts two distinct values for the same pet slot and signals plurality ("two dogs",
    "another"), the second value becomes an ordinal entity (pet.dog.name.2) instead of overwriting the first."""
    if not _PLURAL.search(text or ""):
        return found
    out, count = [], {}
    for d in found:
        k = d["key"]
        if k.startswith("pet.") and d.get("value") and not d.get("clear") and not d.get("clear_value"):
            same = [x for x in out if x["key"].startswith(k) and (x.get("value") or "").lower() == d["value"].lower()]
            if same:
                continue                                          # the same entity reached through two surface forms
            prior = [x for x in out if x["key"].startswith(k) and x.get("value") and x["value"].lower() != d["value"].lower()]
            if prior:
                count[k] = count.get(k, 1) + 1
                d = dict(d, key=f"{k}.{count[k]}")
        out.append(d)
    return out


# 77.3 (module ceiling): the graph-side supersession helpers live in fact_nodes.py; re-exported here so every
# `from .facts import supersede_stale_nodes / supersede_named_stale` keeps working (Rule 11).
from .fact_nodes import supersede_named_stale, supersede_stale_nodes  # noqa: E402,F401
