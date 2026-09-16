"""First-class directives (PA3 OutputFormatDirectiveSection analog) — the biggest parity gap.

A directive is a standing instruction on HOW to respond. Unlike a fuzzy memory, it is stored
in a dedicated table keyed by KIND, so a new directive of the same kind DETERMINISTICALLY
supersedes the old one (no reliance on the contradiction scorer) and a "stop" clears it.
Active directives are injected as a high-salience mandatory block (PA3 lesson: soft prompt
placement matters; a local model obeys the LAST, clearest instruction).
"""

from __future__ import annotations

from .value_gate import directive_candidate_supported   # 92.E2: evidence, not precedence
import re

from .speech_act import has_standing_cue   # 73.4: a new standing rule must read as one
import sqlite3
import threading
from typing import List, Optional

from . import config
from .db import connect as db_connect
from .models import now_iso

# trigger for each kind (end\w* also matches "ending"/"ends"); value scanned after the "with"
_SUFFIX_RE = re.compile(r"\b(?:end|finish|terminate|conclude|sign|append|suffix)\w*[^.]{0,40}?\bwith\b",
                        re.IGNORECASE)
_PREFIX_RE = re.compile(r"\b(?:begin|start|open|prefix|preced)\w*[^.]{0,40}?\bwith\b", re.IGNORECASE)
_STOP_CUES = ("stop", "no longer", "don't", "dont", "do not", "never", "cease")
# UNAMBIGUOUS cease-cues for clearing a dynamic opener/closer — excludes "never"/"don't", which
# double as qualifiers ("always a joke, never a boring one"). The router handles subtler stops.
_STOP_STRONG = ("stop", "no longer", "cease")
_RETRACT_CUES = ("forget that", "forget it", "never mind", "nevermind", "cancel that", "scrap that", "esquece", "cancela isso", "desfaz")   # 95.26: an anaphoric retraction is a stated stop
_WORD_RE = re.compile(r"['\"]?([A-Za-z][\w-]{1,29})['\"]?")
# replacement inside a stop clause: "use/switch to <value>" or "<value> instead".
# NOT "with" — that's the ORIGINAL directive's preposition (would echo the retired value).
_REPLACE_RE = re.compile(r"(?:\b(?:use|to)\b\s+['\"]?([A-Za-z][\w-]{1,29})['\"]?"
                         r"|['\"]?([A-Za-z][\w-]{1,29})['\"]?\s+instead)", re.IGNORECASE)

_FILLER = {"the", "word", "phrase", "a", "an", "exact", "literal", "text", "string", "term",
           "your", "my", "each", "every", "all", "reply", "replies", "response", "responses",
           "answer", "answers", "message", "messages", "of", "is", "it"}

# H-06: an "end/begin ... with X" clause is an OUTPUT DIRECTIVE only when it talks about the reply itself (an
# output-object noun or standing framing near the trigger); "finish the project with Python" is task language.
_OUTPUT_OBJECT = re.compile(r"\b(?:repl(?:y|ies)|answers?|responses?|messages?|output|"
                            r"sentences?|lines?)\b", re.IGNORECASE)
_STANDING = re.compile(r"\b(?:from now on|going forward|always|every time|each time|"
                       r"whenever|henceforth)\b", re.IGNORECASE)
# "end with the word/phrase X" explicitly formats the OUTPUT — a directive even without a
# reply-object noun. Ordinary task language ("finish the project with Python") lacks it.
_LITERAL_MARKER = re.compile(r"\bthe\s+(?:word|phrase|letter|string|text|token)\b", re.IGNORECASE)
_JOKE_OPENER = re.compile(
    r"\b(?:from now on|always|every)\b.{0,70}\b(?:tell|start|begin)\b.{0,90}\bjoke\b"
    r"|\bjoke\b.{0,45}\b(?:start|begin|opening)\b.{0,35}\bconversations?\b",
    re.IGNORECASE,
)
# a recurring joke/humour at the END of replies is a conversation_closer — dynamic content,
# NOT an output_suffix (which would append the literal instruction text to every reply).
_JOKE_CLOSER = re.compile(
    r"\bjoke\b.{0,55}\b(?:end|ending|ends|close|closing|finish|conclude|conclusion|last)\b"
    r"|\b(?:end|ending|close|closing|finish|conclude|last)\b.{0,55}\bjoke\b",
    re.IGNORECASE,
)

def _is_directive_context(text: str, start: int, end: int) -> bool:
    window = text[max(0, start - 60):min(len(text), end + 30)]
    return bool(_OUTPUT_OBJECT.search(window) or _STANDING.search(window)
                or _LITERAL_MARKER.search(window))


def _first_value(after: str) -> Optional[str]:
    for m in _WORD_RE.finditer(after):
        if m.group(1).lower() not in _FILLER:
            return m.group(1)
    return None


def _replacement(text: str) -> Optional[str]:
    for m in _REPLACE_RE.finditer(text):
        tok = m.group(1) or m.group(2)
        if tok and tok.lower() not in _FILLER:
            return tok
    return None


# Phase 66.5 — STANDING TOOL RULES ("from now on always use brave search for weather"). Kind is
# `tool_rule:<tool-slug>` so several rules coexist (one row per tool, PRIMARY KEY kind); value = topic.
_TOOL_RULE_RE = re.compile(
    r"\b(?:always|sempre|from now on|for now on|de agora em diante|going forward|a partir de agora)\b"
    r"[^.!?\n]{0,50}?\b(?:use|usa|usar|utiliza|utilizar|prefer|prefira)\b\s+(?:the\s+|o\s+|a\s+)?"
    r"([A-Za-z][\w\- ]{2,30}?)\s+(?:for|to|when|para|quando|em)\b\s+([^.!?\n]{3,80})", re.IGNORECASE)
_TOOL_RULE_STOP = re.compile(r"\b(?:stop|no longer|never|para de|deixa de|n[aã]o uses?)\b[^.!?\n]{0,30}?"
                             r"\b(?:using|use|usar|utilizar)\s+(?:the\s+|o\s+|a\s+)?([A-Za-z][\w\- ]{2,30})", re.IGNORECASE)


def _tool_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def detect_tool_rule(text: str) -> Optional[dict]:
    """{kind:'tool_rule:<slug>', value:<topic>} | {kind, clear} | None."""
    text = re.sub(r"\s+", " ", text or "")          # "from now  on" (double space) must still match
    m = _TOOL_RULE_STOP.search(text)
    if m:
        return {"kind": f"tool_rule:{_tool_slug(m.group(1))}", "clear": True}
    m = _TOOL_RULE_RE.search(text)
    if not m:
        return None
    return {"kind": f"tool_rule:{_tool_slug(m.group(1))}", "value": m.group(2).strip().rstrip(",;"),
            "instruction": (text or "").strip()[:500], "fallback_text": ""}


def resolve_tool_name(slug: str, tool_names) -> Optional[str]:
    """'brave_search' → 'brave_web_search': substring either way, else all slug tokens ⊂ tool tokens."""
    names = list(tool_names or [])
    for n in names:
        if slug in n.lower() or n.lower() in slug:
            return n
    toks = set(slug.split("_")) - {"the", "tool", "search"} or set(slug.split("_"))
    hits = [n for n in names if toks <= set(n.lower().split("_"))]
    return hits[0] if len(hits) == 1 else None


def _topic_tokens(s: str) -> set:
    return {t for t in re.findall(r"[a-z\u00C0-\u00FF]{4,}", (s or "").lower())
            if t not in ("search", "request", "requests", "getting", "para", "todays", "today", "when", "always")}


def detect_output_directive(text: str) -> Optional[dict]:
    """{kind, value} | {kind, clear} | None. Handles multi-clause corrections generally:
    the LAST positively-stated 'end/begin with X' wins; a negated-only clause clears (or
    switches to an explicit 'use Y / Y instead')."""
    low = text.lower()
    # STOP an existing dynamic-content opener/closer (regex backup; the router clears semantically).
    # Only unambiguous cease-cues fire, so "always a joke, never a boring one" is not misread.
    if any(cue in low for cue in _STOP_STRONG) and ("joke" in low or "opener" in low or "closer" in low):
        opener_ctx = re.search(r"\b(?:open|begin|start|first)\w*", low)
        closer_ctx = re.search(r"\b(?:clos|end|ending|last|conclud|finish)\w*", low)
        return {"kind": "conversation_opener" if (opener_ctx and not closer_ctx)
                else "conversation_closer", "clear": True}
    # SET/CHANGE: opener/closer `value` is the CONTENT SPEC (regex only knows the joke case; the
    # router extracts arbitrary specs — a curious fact, a quote — in any language).
    if _JOKE_OPENER.search(text):
        return {"kind": "conversation_opener", "value": "a short joke"}
    if _JOKE_CLOSER.search(text):
        return {"kind": "conversation_closer", "value": "a short joke"}
    for kind, rx in (("output_suffix", _SUFFIX_RE), ("output_prefix", _PREFIX_RE)):
        positive, had_negated = None, False
        for m in rx.finditer(text):
            value = _first_value(text[m.end():])
            if not value:
                continue
            if not _is_directive_context(text, m.start(), m.end()):
                continue                  # ordinary task language, not an output directive (H-06)
            window = text[max(0, m.start() - 22):m.start()].lower()
            if any(cue in window for cue in _STOP_CUES):
                had_negated = True
            else:
                positive = value          # keep the last positive statement
        if positive:
            return {"kind": kind, "value": positive}
        if had_negated:
            repl = _replacement(text)
            return {"kind": kind, "value": repl} if repl else {"kind": kind, "clear": True}
    return None


def is_blocked_directive_change(detected, active: List[dict], tool_action: bool,
                                conversation_act: str = "instruction", text: str = "") -> bool:
    """Bench L24 rounds 2+3 (multilingual echo): with the active directives visible as routing
    context, the router may re-emit one TRANSLATED into the turn's language ('a short joke' →
    'uma piada curta') on an UNRELATED turn — a genuine tool call (round 2) or a plain question
    (round 3) — which the exact-value echo guard cannot catch lexically. Language-agnostic
    invariant: CHANGING an already-active directive kind is itself a standing instruction, so it
    applies ONLY on a non-tool turn the router classified as instruction/statement. A NEW kind
    still applies anywhere, and CLEAR always passes through (stop must never be blocked).
    `tool_action` = the turn GENUINELY invokes a tool (router's real pin ∩ offered) — NOT the raw
    action_requested flag, which the router sets True even for a directive-set ('start with a
    joke' reads imperative) that pins no tool. Using the genuine signal is the L24 fix."""
    if not isinstance(detected, dict) or detected.get("clear"):
        return False
    if not any(d.get("kind") == detected.get("kind") for d in active):
        # brand-new directive kind — no echo risk, but (73.4) a NEW standing rule must be STATED as standing in the
        # user's own words; a router-invented suffix on "share the link…" is not one. Callers that pass no text keep
        # the old behaviour (Rule 11).
        return bool(text) and not has_standing_cue(text) and str(detected.get("kind", "")).startswith(
            ("output_", "conversation_"))
    # A genuine set/change is the PRIMARY intent of the turn, so it lands on a directive-bearing
    # act (instruction/statement — different models label it differently, e.g. ornith says
    # 'statement'). Block the echo only where a directive change is implausible: a genuine tool
    # call, or a question/greeting/feedback turn (where round-2/3 translate-echoes appeared).
    return tool_action or conversation_act in ("question", "greeting", "feedback")


def sanitize_router_directive(directive) -> Optional[dict]:
    """Normalise a router/nano `directive` dict into the stored form (or None). Content-general:
    opener/closer `value` is the CONTENT SPEC (a joke, a curious fact, a quote…). A bare 'short_joke'
    sentinel mis-filed as a literal prefix/suffix is reclassified to a closer so it never leaks; a
    `clear` flag is passed through. Lives here (directive domain) so the sensitizer stays lean."""
    if not isinstance(directive, dict):
        return None
    from .turn_router import normalise_enum
    kind = normalise_enum(directive.get("kind"),
                          {"output_prefix", "output_suffix", "conversation_opener",
                           "conversation_closer", "response_style"}, "")   # 93.C
    if not kind:
        return None
    value = str(directive.get("value", ""))[:120].strip()
    if kind in ("output_prefix", "output_suffix") and value.lower() in (
            "short_joke", "joke", "a joke", "a short joke", "short joke"):
        kind, value = "conversation_closer", "a short joke"
    if kind in ("conversation_opener", "conversation_closer") and value.lower() in (
            "short_joke", "joke", ""):
        value = "a short joke"                       # readable default for a bare/empty sentinel
    if directive.get("clear") is True:
        return {"kind": kind, "clear": True}
    if not value and kind == "response_style":
        # 93.C: for a style rule the user's own sentence IS the rule, so a model that put it under
        # `instruction` has still said something usable. Other kinds keep needing a separate value:
        # a prefix or an opener is not the sentence that asked for it.
        value = str(directive.get("instruction", ""))[:120].strip()
    if not value:
        return None
    return {"kind": kind, "value": value,
            "condition": str(directive.get("condition", ""))[:240].strip(),   # 93.C: stated, not invented
            "instruction": str(directive.get("instruction", ""))[:500].strip(),
            "fallback_text": str(directive.get("fallback_text", ""))[:500].strip()}




class DirectiveStore:
    def __init__(self, db_path: Optional[str] = None):
        self._lock = threading.RLock()
        self._db = db_connect(db_path or config.DB_PATH)
        self._db.execute("CREATE TABLE IF NOT EXISTS directives ("
                         "kind TEXT PRIMARY KEY, value TEXT, source TEXT, updated_at TEXT)")
        # 69.5: a CLEARED directive leaves a tombstone so startup migrations never resurrect it from old episodes
        self._db.execute("CREATE TABLE IF NOT EXISTS directive_tombstones (kind TEXT PRIMARY KEY, cleared_at TEXT)")
        columns = {row[1] for row in self._db.execute("PRAGMA table_info(directives)")}
        if "instruction" not in columns:
            self._db.execute("ALTER TABLE directives ADD COLUMN instruction TEXT DEFAULT ''")
        if "fallback_text" not in columns:
            self._db.execute("ALTER TABLE directives ADD COLUMN fallback_text TEXT DEFAULT ''")
        if "condition" not in columns:          # 93.C: the exception a policy holds under
            self._db.execute("ALTER TABLE directives ADD COLUMN condition TEXT DEFAULT ''")
        from .hygiene import migrate_legacy_joke_closer
        migrate_legacy_joke_closer(self._db, _JOKE_CLOSER, now_iso())   # Phase 53 one-off (lives in hygiene)

    def apply(self, text: str, source: str = "user_explicit",
              detected: Optional[dict] = None) -> Optional[dict]:
        """Detect + upsert/clear a directive from a message. Returns the action or None."""
        from .prohibitions import detect_lift, detect_prohibition, rows_forbidding   # 95.65a/c/d: a standing prohibition,
        lift = detect_lift(text, self.active())                       # and its LIFT, are the store's own to read -- the lift first
        if lift:
            with self._lock:                                          # 95.65c/d: every row naming the file goes, whatever its kind
                for r in rows_forbidding(self.active(), set(lift["files"])):
                    self._db.execute("DELETE FROM directives WHERE kind=?", (r["kind"],))
                self._db.commit()
        det = (detected if directive_candidate_supported(detected, text) else None) or detect_prohibition(text) \
            or detect_output_directive(text) or detect_tool_rule(text)   # then the turn's own directive, if any (v173: a permission)
        if det is None:
            return {"kind": lift["kind"], "cleared": True} if lift else None
        with self._lock:
            kept = self._prohibition_kept(det, text)      # 95.3: a prohibition is lifted only by the user's own STATED lift
            if kept:
                return kept
            if det.get("clear") and det is detected and not self._clear_grounded(det, text):
                return None                            # 95.26: a perceiver's clear the message does not state
            if det.get("clear"):
                self._db.execute("DELETE FROM directives WHERE kind=?", (det["kind"],))
                self._db.execute("INSERT OR REPLACE INTO directive_tombstones (kind, cleared_at) VALUES (?, ?)",
                                 (det["kind"], now_iso()))
                self._db.commit()
                return {"kind": det["kind"], "cleared": True}
            if source != "migration":
                # the user states the rule again → the tombstone is lifted (a migration may NOT lift it)
                self._db.execute("DELETE FROM directive_tombstones WHERE kind=?", (det["kind"],))
                self._db.commit()          # 73.4: a write left open here held the WAL lock into the facts INSERT (deadlock)
            # ECHO GUARD (56, L25): the router may re-emit an active directive on an unrelated turn; same kind + same
            # value = a RESTATEMENT -- the row stays, no change is reported. Only a genuinely new value supersedes.
            row = self._db.execute("SELECT value, fallback_text FROM directives WHERE kind=?",
                                   (det["kind"],)).fetchone()
            if row is not None and (row[0] or "").strip().lower() == \
                    str(det.get("value", "")).strip().lower():
                fresh = str(det.get("fallback_text", ""))[:500]
                if not (row[1] or "").strip() and fresh:   # backfill an empty example only
                    self._db.execute("UPDATE directives SET fallback_text=? WHERE kind=?",
                                     (fresh, det["kind"]))
                    self._db.commit()
                return None
            # newer directive of the same kind DETERMINISTICALLY replaces the old (PRIMARY KEY)
            instruction = str(det.get("instruction", ""))[:500]
            fallback_text = str(det.get("fallback_text", ""))[:500]
            self._db.execute(
                "INSERT OR REPLACE INTO directives "
                "(kind, value, source, updated_at, instruction, fallback_text, condition) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (det["kind"], det["value"], source, now_iso(), instruction, fallback_text,
                 str(det.get("condition", ""))[:240]),                       # 93.C
            )
            self._db.commit()
            return {"kind": det["kind"], "value": det["value"],
                    "instruction": instruction, "fallback_text": fallback_text}

    def _clear_grounded(self, det: dict, text: str) -> bool:
        """95.26: the message states the stop (a cease cue) or names what it clears -- the kind's words or the active
        value's own words. "Do not store anything from this session" names neither: it clears nothing (S3)."""
        low = " ".join((text or "").split()).lower()
        if any(cue in low for cue in _STOP_STRONG + _RETRACT_CUES) or has_standing_cue(text or ""):
            return True                                   # a stated stop, a retraction ("forget that", v135), or the standing ground _prohibition_kept accepts (95.3b)
        kind = str(det.get("kind") or "")
        kind_words = {w for w in re.split(r"[_:\s]+", kind.replace("response", "").replace("conversation", "").replace("output", "")) if len(w) > 2}
        row = self._db.execute("SELECT value FROM directives WHERE kind=?", (kind,)).fetchone()
        value_words = {w for w in re.findall(r"[a-z][\w-]{3,}", (row[0] if row else "").lower())} - _FILLER
        toks = set(re.findall(r"[a-z][\w-]{2,}", low))
        return bool(toks & kind_words) or bool(toks & value_words)

    def _prohibition_kept(self, det: dict, text: str) -> Optional[dict]:
        """95.3: the stored rule for this kind (95.65a: or the one naming the FILE this message names, whatever its
        kind) is a prohibition and `text` does not state a lift -> the clear / overwrite is refused, with the reason."""
        from .speech_act import prohibits_effect
        row = self._db.execute("SELECT value, instruction FROM directives WHERE kind=?",
                               (det.get("kind"),)).fetchone()
        if row is None or not prohibits_effect(row[1] or row[0] or ""):
            from .prohibitions import named_files, rows_forbidding
            hit = rows_forbidding(self.active(), named_files(text or "") | named_files(str(det.get("value") or "")))
            if not hit:
                return None
            row, det = (hit[0]["value"], hit[0]["instruction"]), {**det, "kind": hit[0]["kind"]}
        lifting = det.get("clear") or not prohibits_effect(str(det.get("value") or ""))
        if not lifting:
            return None                                   # a prohibition restated or tightened: proceed
        low = (text or "").lower()
        from .speech_act import has_standing_cue          # 95.3b: a lift of a STANDING rule is itself stated as standing
        if any(cue in low for cue in _STOP_STRONG) or has_standing_cue(text or ""):
            return None                                   # the user stated the lift: proceed
        return {"kind": det.get("kind"), "kept": "prohibition",
                "reason": "a standing prohibition is lifted only by a stated lift (stop / no longer / cease)"}

    def tool_rules_for(self, text: str, tool_names) -> List[str]:
        """66.5: resolved tool names whose standing rule's topic overlaps this message (≥1 content
        token) — the user's own rule, so it is treated like a tool the user NAMED (forced)."""
        words = _topic_tokens(text)
        out = []
        for d in self.active():
            if not d["kind"].startswith("tool_rule:"):
                continue
            if _topic_tokens(d["value"]) & words:
                name = resolve_tool_name(d["kind"][10:], tool_names)
                if name and name not in out:
                    out.append(name)
        return out

    def is_cleared(self, kind: str) -> bool:
        """True when the user retired this directive kind and has not re-stated it since (69.5)."""
        with self._lock:
            return self._db.execute("SELECT 1 FROM directive_tombstones WHERE kind=?", (kind,)).fetchone() is not None

    def active(self) -> List[dict]:
        with self._lock:
            rows = self._db.execute(
                "SELECT kind, value, updated_at, instruction, fallback_text, condition FROM directives"
            ).fetchall()
        return [{"kind": k, "value": v, "updated_at": u, "instruction": i or "",
                 "fallback_text": f or "", "condition": c or ""} for k, v, u, i, f, c in rows]

    def render_block(self, first_turn: bool = True, suppress_generated: bool = False,
                     tool_names=None) -> str:
        """The mandatory prompt block; the rendering itself lives in directive_render (93.C)."""
        from .directive_render import render_block
        return render_block(self.active(), first_turn, suppress_generated, tool_names)

    def enforce(self, reply: str, first_turn: bool = True, force_generated: bool = False) -> str:
        """Deterministic backstop (PA3 lesson: soft prompt alone doesn't bind a local model).
        Literal prefix/suffix are ALWAYS guaranteed. Dynamic opener/closer content is content-general
        (a joke, a fact, a quote…) and cannot be verified deterministically, so enforce appends the
        PERSISTED example (generated once at directive time) rather than inspecting the reply. The
        opener is applied ONLY here (an opener in the prompt dominates the turn — Phase 52); the
        closer HAS a prompt path, so it is only force-appended on ACTION turns where render_block
        suppressed it (`force_generated`), never on ordinary turns (that would staple a duplicate)."""
        for d in self.active():
            val = d["value"]
            if d["kind"].startswith("tool_rule:"):
                continue                               # 66.5: no text effect; enforced at the tool layer
            if d["kind"] == "output_suffix":
                if not reply.rstrip().rstrip(".!?").lower().endswith(val.lower()):
                    reply = reply.rstrip() + "\n\n" + val
            elif d["kind"] == "output_prefix":
                if not reply.lstrip().lower().startswith(val.lower()):
                    reply = val + " " + reply.lstrip()
            elif d["kind"] == "conversation_opener" and first_turn:
                example = (d.get("fallback_text") or "").strip()
                if example and not reply.lstrip().lower().startswith(example.lower()):
                    reply = example + "\n\n" + reply.lstrip()
            elif d["kind"] == "conversation_closer" and force_generated:
                example = (d.get("fallback_text") or "").strip()
                if example and example.lower() not in reply[-(len(example) + 40):].lower():
                    reply = reply.rstrip() + "\n\n" + example
        return reply
