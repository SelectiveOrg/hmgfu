"""Authoritative runtime facts captured once for each turn.

This is deliberately data, not a phrase detector: every consumer sees the same clock snapshot,
and the values change naturally with the host clock/timezone on every turn.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass(frozen=True)
class RuntimeContext:
    now_local: str
    now_utc: str
    local_date: str
    local_time: str
    timezone_name: str
    utc_offset: str
    unix_seconds: int

    @classmethod
    def at(cls, instant: str) -> "RuntimeContext":
        """A context for one FIXED instant, every field consistent with it.

        93.RR2: an experiment that moves the clock has to move ALL of it. Rewriting one match of a
        regex left `now_local` in one minute and `local_time`, `now_utc` and `unix_seconds` in
        another, so the arm was measuring an incoherent context rather than the passage of time."""
        return cls.capture(datetime.fromisoformat(instant))

    @classmethod
    def capture(cls, now: Optional[datetime] = None) -> "RuntimeContext":
        local = now.astimezone() if now is not None else datetime.now().astimezone()
        utc = local.astimezone(timezone.utc)
        offset = local.strftime("%z")
        offset = f"{offset[:3]}:{offset[3:]}" if len(offset) == 5 else offset
        return cls(
            now_local=local.isoformat(timespec="seconds"),
            now_utc=utc.isoformat(timespec="seconds"),
            local_date=local.date().isoformat(),
            local_time=local.strftime("%H:%M:%S"),
            timezone_name=local.tzname() or "local",
            utc_offset=offset or "+00:00",
            unix_seconds=int(local.timestamp()),
        )

    def public(self) -> dict:
        return {
            "now_local": self.now_local,
            "now_utc": self.now_utc,
            "local_date": self.local_date,
            "local_time": self.local_time,
            "timezone_name": self.timezone_name,
            "utc_offset": self.utc_offset,
            "unix_seconds": self.unix_seconds,
        }

    def prompt_block(self) -> str:
        return (
            "=== AUTHORITATIVE RUNTIME CONTEXT (captured for this turn) ===\n"
            + json.dumps(self.public(), ensure_ascii=False, separators=(",", ":"))
            + "\nUse these values for current date/time and relative-time reasoning. "
              "Do not substitute training-time dates. External live facts still require a tool."
        )


def runtime_prompt(runtime_context=None) -> str:
    """Compatibility/public prompt formatter used by nano and dream workers."""
    return (runtime_context or RuntimeContext.capture()).prompt_block()


def _to_the_minute(value: str) -> str:
    """An ISO timestamp with the seconds dropped, keeping everything else it carries."""
    head, sep, tail = str(value).partition("T")
    if not sep:
        return str(value)
    parts = tail.split(":")
    if len(parts) < 3:
        return str(value)
    rest = parts[2]
    offset = rest[2:] if len(rest) > 2 else ""          # "+02:00" / "Z" survives, the seconds do not
    return f"{head}T{parts[0]}:{parts[1]}{offset}"


def router_prompt(runtime_context=None) -> str:
    """The same block with the seconds removed, for the CLASSIFIER only.

    93.R3, measured rather than assumed: replaying the router's captured request byte for byte gives
    an envelope 8 times in 8 -- the call is deterministic -- while whole fresh turns of the same
    sentence give 2 in 8, and a diff of those turns shows the ONLY difference is this clock, down to
    the second. Seconds cannot bear on "is this turn teaching me something", so they are dropped here
    and two turns in the same minute send identical bytes.

    `prompt_block` is untouched: when the user asks the time, the value spoken still comes from the
    full-precision block, and `unix_seconds` stays there for relative-time reasoning."""
    now = runtime_context or RuntimeContext.capture()
    public = dict(now.public())
    public["now_local"] = _to_the_minute(public.get("now_local", ""))
    public["now_utc"] = _to_the_minute(public.get("now_utc", ""))
    public["local_time"] = str(public.get("local_time", ""))[:5]
    # 93.RR1: `unix_seconds` ticks every second, so removing HH:MM:SS from the rendered text left the
    # context changing anyway -- two FIXED instants in the same minute still produced different bytes.
    # Floored to the minute it stays usable for relative-time reasoning and stops being a clock hand.
    if isinstance(public.get("unix_seconds"), int):
        public["unix_seconds"] = public["unix_seconds"] - (public["unix_seconds"] % 60)
    return (
        "=== AUTHORITATIVE RUNTIME CONTEXT (captured for this turn, to the minute) ===\n"
        + json.dumps(public, ensure_ascii=False, separators=(",", ":"))
        + "\nUse these values for current date/time and relative-time reasoning. "
          "Do not substitute training-time dates. External live facts still require a tool."
    )


def _grounding_missing(reply: str, keys, runtime) -> bool:
    """True if the router selected clock keys for this turn but the answer contains NONE of the
    authoritative values. Tolerant of formatting (ISO datetime → also accept its HH:MM and date
    parts; HH:MM:SS → accept HH:MM). Language-agnostic — it checks the VALUE, not phrasing."""
    if not keys:
        return False
    data = runtime.public() if hasattr(runtime, "public") else dict(runtime)
    low = reply.lower()
    forms = []
    for k in keys:
        v = str(data.get(k, "")).lower()
        if not v:
            continue
        forms.append(v)
        if "t" in v and ":" in v:            # ISO datetime → HH:MM and the date substring
            forms.append(v.split("t", 1)[1][:5])
            forms.append(v.split("t", 1)[0])
        elif ":" in v:                        # HH:MM:SS → HH:MM
            forms.append(v[:5])
    forms = [f for f in forms if len(f) >= 4]
    return bool(forms) and not any(f in low for f in forms)


def _clock_requested(query) -> bool:
    """True when the turn actually ASKED for a current date/time, so the clock may ground the answer.

    91.X1: `runtime_context_sufficient` says the clock CAN answer, not that the turn asked. The live
    router raises it for turns that merely mention, deny or complain about the time (observed acts
    `feedback` and `statement`), and grounding those overwrites the conversation with a timestamp.
    Asking arrives as a QUESTION — the router's own semantic classification, so this holds in any
    language and needs no phrase list. Measured on 19 labelled PT/EN turns (diag_clock_router.py):
    all 11 requests are classified `question`, four of them imperative ("give me the current time",
    "me diga a hora agora"); the two prohibitions are classified `instruction`. An instruction about
    the clock is a rule for future replies, not a request for the value, and the model obeys it with
    the runtime block already in its prompt — so `instruction` is not accepted here.

    `action_requested` is deliberately NOT accepted as evidence of a request: it means an action is
    wanted, not that the CLOCK is wanted, and tool_points re-raises it after the router runs. In the
    live capture it was True for a complaint about the time, which is precisely the turn this gate
    must leave alone. The cost is that a genuine request the router files as `statement` loses the
    backstop; the runtime block is still in the prompt, so the answer is degraded, not falsified.

    91.Y5: the act says the turn ASKS, not WHAT it asks -- a non-clock question the router wrongly
    called clock-sufficient would still pass. `freshness` is produced by the router as a SEPARATE
    field and means the turn wants a CURRENT value; requiring both is a conjunction of two
    independent classifications rather than trust in one. Measured on the 19-turn battery: every one
    of the 11 requests came back "current" and every one of the 8 non-requests came back "none" -- a
    clean separation on that battery, which is 19 turns on one model and not a rate."""
    return (getattr(query, "conversation_act", "") == "question"
            and getattr(query, "freshness", "none") == "current")


def ground_reply(engine, reply: str, user_message: str, query, runtime, system: str) -> str:
    """Deterministic clock-grounding backstop (Phase 57 P4). When the router flagged the runtime
    clock as SUFFICIENT for this turn, verify the answer actually carries an authoritative value;
    on a detected miss, re-ask ONCE providing the literal values. The re-ask fires only for a
    turn that ASKED for the time (`_clock_requested`); a complaint or a mention is answered normally. This is an external-signal
    correction (CRITIC pattern), NOT a static prompt rule — the values are live data and the
    re-ask fires only on a verified failure, so it self-corrects rather than hard-coding phrasing."""
    from . import config
    if not config.CLOCK_REASK_ENABLED:      # 91.Z11: experimental OFF arm; the runtime block stays in
        return reply                        # the prompt, so only the REWRITE is withdrawn
    keys = list(getattr(query, "runtime_context_keys", []) or [])
    if not getattr(query, "runtime_context_sufficient", False):
        return reply
    if not _clock_requested(query):        # 91.X1: sufficient is not the same as requested
        return reply
    if not _grounding_missing(reply, keys, runtime):
        return reply
    data = runtime.public()
    vals = {k: data[k] for k in keys if k in data} or data
    try:
        provider, model = engine.registry.resolve("chat")
        out = provider.chat(model, [
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": reply},
            {"role": "user", "content":
             "Your previous answer did not use the authoritative current date/time. Answer the "
             "ORIGINAL question again, keeping every other part of what you said, and take the "
             "date/time verbatim from these exact values (do not compute or convert to another "
             "timezone): " + json.dumps(vals, ensure_ascii=False)},
        ], temperature=0.0, think=False)
        new = (out.get("content") or "").strip()
        return new or reply
    except Exception:
        return reply
