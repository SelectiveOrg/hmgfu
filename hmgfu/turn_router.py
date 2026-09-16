"""Multilingual, runtime-catalog turn routing performed by the configured main model."""

from __future__ import annotations

import re
import json
import logging

log = logging.getLogger("hmgfu.turn_router")

# 92.E5R: faults that can only mean THIS codebase is broken. Nothing on the routing path compiles or
# evaluates model output, so a model can never provoke one -- while a reset socket, a timeout or an
# unparseable payload can, and those must still degrade. Stated here because this module owns both
# the router call and the worker boundary; the sensitizer imports it rather than keeping a copy.
OWN_DEFECT = (SyntaxError, ImportError, NameError)


def reraise_if_ours(exc: BaseException) -> None:
    """Let a broken module fail loudly instead of quietly turning every turn into the fallback."""
    if isinstance(exc, OWN_DEFECT):
        raise exc



EXTRACT_PROMPT = """Analyse the message and return one JSON object with: title, summary, type,
keywords, entities, topics, emotional_valence, emotional_intensity, importance, confidence,
novelty, utility, intent, conversation_act, feedback_polarity, action_requested, requested_tools,
freshness, needs_memory, runtime_context_keys, runtime_context_sufficient, and directive.
Allowed intent: question,task,reflection,emotional,statement.
Allowed conversation_act: greeting,question,instruction,feedback,statement.
feedback_polarity: "positive" | "negative" | null — ONLY when the message reacts to the
assistant's previous work (praise/satisfaction vs complaint/it-failed), judged by MEANING in the
user's language; null otherwise.
Allowed freshness: none,historical,current.
directive is null or {kind, value, instruction, fallback_text, condition, clear}; allowed kinds are
output_prefix,output_suffix,conversation_opener,conversation_closer,response_style. A standing rule
about HOW replies should be written (length, tone, level of detail) is response_style: `value` is the
rule ALONE, never the whole sentence that states it, and `condition` is the exception the user stated,
if any -- put the exception only in `condition`, never in both. Recurring content at the START
or END of replies is conversation_opener/closer and its `value` is the CONTENT DESCRIPTION (a joke,
a curious fact, a quote, …), NEVER an output_suffix holding the literal instruction. Set clear=true
when the user asks to STOP it. Preserve the user's language. requested_tools must contain only
exact names from the runtime catalog. A current-clock question uses runtime context, not a tool; only a REQUEST for the current
date/time sets runtime_context_sufficient — mentioning, denying or forbidding it does not.
Detect standing instructions semantically in any language. JSON only; no prose or markdown."""


ROUTE_PROMPT = """Classify this single user turn by meaning, independent of its language.
Return JSON only:
{
 "conversation_act": "greeting|question|instruction|feedback|statement",
 "feedback_polarity": null or "positive" or "negative" (only when the message reacts to the assistant's previous work — praise vs complaint — judged by meaning in ANY language),
 "action_requested": true or false,
 "requested_tools": ["exact names chosen only from the runtime catalog"],
 "freshness": "none|historical|current",
 "needs_memory": true or false,
 "runtime_context_keys": ["now_local|now_utc|local_date|local_time|timezone_name|utc_offset"],
 "runtime_context_sufficient": true or false,
 "directive": null or {
   "kind": "output_prefix|output_suffix|conversation_opener|conversation_closer|response_style",
   "value": "for response_style: the rule itself, short (e.g. 'short snippets'). For prefix/suffix: the exact literal text. For opener/closer: a SHORT description of the CONTENT to produce every time, in the user's language (e.g. 'a short joke', 'a curious scientific fact', 'uma citacao inspiradora') — NOT a literal, the system generates fresh matching content.",
   "instruction": "the persistent instruction verbatim in the user's language",
   "condition": "for response_style only: the exception the user stated, verbatim; '' when none",
   "fallback_text": "",
   "clear": true ONLY when the user asks to STOP/remove an existing standing directive of this kind
 }
}
[[LEARNING]]An action means the assistant must execute an available capability, not merely answer from runtime
context or knowledge. If the supplied runtime clock fully answers the request, set
runtime_context_sufficient=true, list the exact keys, action_requested=false, and request no tool.
Sufficiency describes a REQUEST for the current date or time. A turn that only mentions the time,
denies having asked for it, complains about being given it, forbids it in future, or uses the word
in another sense is NOT asking: set runtime_context_sufficient=false with runtime_context_keys=[],
whatever its conversation_act. For mixed requests that also need external changing facts,
runtime_context_sufficient is false.
A standing directive governs future replies or future conversations. Before
returning directive=null, decide whether the instruction applies beyond this turn; if it does,
directive MUST be an object. A recurring FIRST-reply requirement is conversation_opener; a
recurring LAST-line requirement is conversation_closer. Their `value` is the CONTENT DESCRIPTION
(a joke, a curious fact, a quote, …) — the system generates fresh matching content each turn. To
CHANGE the content (e.g. jokes -> facts) return the SAME kind with the new value; to STOP it return
that kind with clear=true.
If the message MODIFIES or STOPS one of the ACTIVE STANDING DIRECTIVES listed after the catalog,
return `directive` with that SAME kind and either the new value (change) or clear=true (stop) —
decide by MEANING in ANY language ("stop doing that", "no more X at the end", "chega de piadas",
"pare com isso" all clear an active conversation_closer; "actually make it Y instead" changes it).
The catalog is runtime data: use exact current names and never invent a tool."""


MAX_REQUESTED_TOOLS = 3      # 73.2: structural cap on the router's tool list (schema + sanitiser)


# 92.E5R: the envelope paragraph, added ONLY when the schema carries the field. It used to live
# inside ROUTE_PROMPT, where it told the model that memory_update was OPTIONAL and to "omit the field
# entirely" while the grammar REQUIRED it -- an instruction the grammar forbids is not an instruction.
# Tying it to the schema also keeps arm S on the pre-92 contract: a control that moved is not a
# control.
LEARNING_PROMPT = """memory_update describes what the user is TEACHING, ANSWERING or WITHDRAWING this turn. WITHDRAWING
is feedback "retract": the user says a record should no longer stand -- they are done with it, it is
not theirs, stop treating it as current -- and the one proposal names the thing to drop in
subject_ref with NO value. Example shape: {"feedback": "retract", "proposals": [{"kind":
"domain_definition", "subject_ref": "<the thing to drop>"}]}. Never restate the old value as if it
were new, and never report a removal you did not propose. Otherwise it is what the user is teaching,
never what
you infer or believe. feedback says what the user did about a question you asked; proposals carry at
most four targets, each with the kind, the subject, the project context and the VALUE IN THE USER'S
OWN WORDS, copied verbatim from the message so it can be located there. Never invent a value, never
propose one for a subject the user did not mention, and set ambiguity when the target, the value or
the context is genuinely unclear instead of guessing. Set the field to null when the turn teaches
nothing: a null envelope is treated as "no update", never as agreement.
Choose the kind by what the user's sentence IS: personal_fact for something true about the user or
their world; domain_definition when they say what a term MEANS, with subject_ref the term and value
the MEANING ALONE, never the whole sentence that states it; behavior_policy only for a rule about how
YOU should answer. When a policy holds only in some cases, put the exception in condition and the
rule in value; leave condition empty when the user stated none, and never invent one.
"""


LEARNING_SLOT = "[[LEARNING]]"     # where the paragraph goes, exactly where it lived before 92.E5R


def learning_enabled(format_schema) -> bool:
    """Whether THIS call carries the envelope, read from the schema so prompt and grammar agree."""
    return bool(((format_schema or {}).get("properties") or {}).get("memory_update"))


def router_schema(catalog_names, learning: bool = False) -> dict:
    """JSON Schema that grammar-CONSTRAINS the router output (Phase 57). Every enum is built from
    the LIVE tool catalog / fixed key sets each turn, so it is fully dynamic — no phrase lists.
    Passed to Ollama `format`, it makes a dropped field, a non-enum conversation_act, or an
    off-catalog tool name literally unrepresentable at decode time (llama.cpp masks them)."""
    tool_enum = sorted({str(n) for n in (catalog_names or [])})
    tool_items = {"type": "string", "enum": tool_enum} if tool_enum else {"type": "string"}
    schema = {
        "type": "object",
        "properties": {
            "conversation_act": {"type": "string",
                                 "enum": ["greeting", "question", "instruction", "feedback", "statement"]},
            "feedback_polarity": {"type": ["string", "null"], "enum": ["positive", "negative", None]},
            "action_requested": {"type": "boolean"},
            # 73.2: a turn asks for a FEW tools; without a cap the 12B router once enumerated the whole
            # 21-tool catalog (27 s of decoding) on "remember that my favorite drink is ginger tea"
            "requested_tools": {"type": "array", "items": tool_items, "maxItems": MAX_REQUESTED_TOOLS},
            "freshness": {"type": "string", "enum": ["none", "historical", "current"]},
            "needs_memory": {"type": "boolean"},
            "runtime_context_keys": {"type": "array", "items": {"type": "string",
                                     "enum": ["now_local", "now_utc", "local_date", "local_time",
                                              "timezone_name", "utc_offset"]}},
            "runtime_context_sufficient": {"type": "boolean"},
            # 92.E4: the teaching/feedback envelope. The model proposes a target and a value; it does
            # NOT supply evidence references, because a model that can cite can cite falsely -- the
            # span is located by the system against the real message. Present only when `learning`.
            "memory_update": {"anyOf": [{"type": "null"}, {"type": "object", "properties": {
                "feedback": {"type": "string", "enum": ["none", "confirm", "reject", "uncertain",
                                                        "correct", "retract", "approve_behavior",
                                                        "complain", "resume_case"]},
                "scope": {"type": "string", "enum": ["memory", "behavior", "plan", "unclear"]},
                "ambiguity": {"type": "string", "enum": ["none", "target", "relation", "value",
                                                         "time", "contradictory", "unsupported"]},
                "proposals": {"type": "array", "maxItems": 4, "items": {"type": "object", "properties": {
                    "kind": {"type": "string", "enum": ["personal_fact", "domain_definition",
                                                        "behavior_policy"]},
                    "subject_ref": {"type": "string"}, "context_ref": {"type": "string"},
                    "relation": {"type": "string"}, "value": {"type": "string"},
                    # 93.C: the exception a policy carries. A policy stored without "unless I ask for
                    # the full context" is not the policy the user stated.
                    "condition": {"type": "string"}},
                    "required": ["kind", "value"]}}},
                # 93.R4: `ambiguity` REQUIRED, for the third time the same lesson (92.E4 memory_update,
                # 93.R1 condition): an optional field is an omitted field, and this one is the ONLY
                # thing that can raise a grounded question. "none" is the valid answer when the turn is
                # clear -- the model is not being asked to doubt everything, only to say which it is.
                "required": ["ambiguity"]}]},
            "directive": {"anyOf": [
                {"type": "null"},
                {"type": "object", "properties": {
                    # 93.C: `response_style` is a standing rule about HOW to answer, with the exception
                    # the user stated. Without it the model classified such a turn as an instruction and
                    # had nowhere to put it -- neither field could hold the rule, so nothing was learned.
                    "kind": {"type": "string", "enum": ["output_prefix", "output_suffix",
                             "conversation_opener", "conversation_closer", "response_style"]},
                    "value": {"type": "string"}, "condition": {"type": "string"},
                    "instruction": {"type": "string"},
                    "fallback_text": {"type": "string"},
                    "clear": {"type": "boolean"},
                # 93.R1: `condition` is REQUIRED for the same reason `memory_update` had to be (92.E4):
                # an optional field was simply omitted every time. "" is the valid answer for a kind
                # that carries no exception, and for one stated without any.
                }, "required": ["kind", "condition"]},
            ]},
        },
        # 92.E4: when present, memory_update is REQUIRED so the model must decide about it
        # explicitly. It may be null -- "this turn teaches nothing" is an answer -- but an OPTIONAL
        # field was simply omitted every time, which left the protocol wired and inert.
        "required": ["conversation_act", "action_requested", "requested_tools", "freshness",
                     "needs_memory", "runtime_context_keys", "runtime_context_sufficient"],
    }
    if not learning:                       # 92.E5R: with the mode off the router sees the B0 contract
        schema["properties"].pop("memory_update", None)
    else:
        schema["required"].append("memory_update")
    return schema


def normalise_enum(value, allowed, default):
    normal = re.sub(r"_+", "_", re.sub(r"[^a-z0-9_]+", "_", str(value).lower())).strip("_")
    return normal if normal in allowed else default


def catalog_json(catalog: dict) -> str:
    return json.dumps([{"name": n, "description": s.get("description", "")[:240]}
                       for n, s in catalog.items()], ensure_ascii=False)


def start_route(chat, parse_json, text: str, runtime_prompt: str, catalog_text: str, directives_text: str = "",
                exemplars_text: str = "", format_schema: dict = None, learning_text: str = "",
                pending_question: str = "", pending_needs: str = ""):
    """73.2(a″): run classify_turn on a worker NOW (it needs nothing from the nano extraction) — returns a future.
    The worker inherits the caller's context so the call ledger attributes the router to the turn."""
    import contextvars
    from concurrent.futures import ThreadPoolExecutor
    ex = ThreadPoolExecutor(max_workers=1, thread_name_prefix="router")
    fut = ex.submit(contextvars.copy_context().run, classify_turn, chat, parse_json, text, runtime_prompt,
                    catalog_text, directives_text, exemplars_text, format_schema, learning_text,
                    pending_question, pending_needs)
    ex.shutdown(wait=False)
    return fut


def merge_route(raw: dict, future, on_fused=None) -> dict:
    """Fold the router's classification into the nano extraction (same semantics as enrich_route).
    95.10: `on_fused(nano_snapshot, router_result_or_None, fused)` lets the caller record BOTH stages
    for the trace -- _sanitise rebuilds the dict from a fixed key set, so nothing else survives."""
    snapshot = dict(raw) if on_fused is not None else None
    router = None
    try:
        router = future.result()
        raw.update(router)
    except Exception as exc:
        reraise_if_ours(exc)   # 92.E5R: a NameError in the worker is not a model with nothing to say
        log.warning("main turn routing failed (%s); keeping nano signals", exc)
    if on_fused is not None:
        try:
            on_fused(snapshot, router, raw)
        except Exception as exc:                       # a trace hook must never change the turn
            log.warning("route trace hook failed: %s", exc)
    return raw


def enrich_route(chat, parse_json, raw: dict, text: str, runtime_prompt: str,
                 catalog_text: str, directives_text: str = "",
                 exemplars_text: str = "", format_schema: dict = None,
                 learning_text: str = "") -> dict:
    """The synchronous twin of merge_route. It carries `learning_text` for the same reason it carries
    the exemplars: the two paths must not disagree about what the router was shown."""
    try:
        raw.update(classify_turn(chat, parse_json, text, runtime_prompt, catalog_text,
                                 directives_text, exemplars_text, format_schema, learning_text))
    except Exception as exc:
        reraise_if_ours(exc)
        log.warning("main turn routing failed (%s); keeping nano signals", exc)
    return raw


def _filling_line(needs: str) -> str:
    """What the router is told when the outstanding question asks for a missing piece.

    Its own function so the wording could be MEASURED against the real router rather than guessed at.
    Four candidates were run through `classify_turn` with the real model on three fillers and two
    unrelated turns. The first wording -- a description of what a filler is -- landed 0/3; naming the
    shape of the proposal and where the value comes from landed 2/3, with no proposal at all on the
    unrelated turns. The barest fragment ("my current project") still produces nothing, and that
    limit is reported rather than tuned away."""
    return ("THAT QUESTION ASKS THE USER TO NAME SOMETHING. The value is already known: it is the "
            "quoted value in the question. This turn supplies the MISSING PIECE, so emit "
            f'memory_update with one proposal: {{"kind": "domain_definition", "{needs}_ref": '
            '"<exactly what the user just wrote>", "value": "<the quoted value from the question>"}, '
            'feedback "none", ambiguity "none". Do NOT emit feedback, and do NOT invent a different '
            "value. If this turn clearly talks about something else, emit memory_update null.")


def classify_turn(chat, parse_json, text: str, runtime_prompt: str,
                  catalog_text: str, directives_text: str = "",
                  exemplars_text: str = "", format_schema: dict = None,
                  learning_text: str = "", pending_question: str = "",
                  pending_needs: str = "") -> dict:
    # The active directives are the SOURCE OF TRUTH the router needs to reason about a change/stop
    # (Phase 55): a turn like "stop doing that" is only interpretable against what is in force.
    # They are CONTEXT — re-emitting one unchanged on an unrelated turn would mutate its persisted
    # example (bench L25), so the prompt says so and DirectiveStore.apply() echo-guards anyway.
    active = (f"\nACTIVE STANDING DIRECTIVES (context, currently in force — this turn may CHANGE "
              f"or STOP one; if the message does not itself state, change or stop a standing "
              f"rule, return directive=null):\n{directives_text}") if directives_text else ""
    # Learned few-shots (Phase 56): CONFIRMED corrections of past misroutes, selected per-turn by
    # similarity from RouteMemory — the router improves with experience instead of repeating the
    # same mistake at a fixed rate. Framing is strict: examples inform CLASSIFICATION of a
    # near-identical request only — they are never instructions to execute anything themselves.
    learned = (f"\nLEARNED ROUTING EXAMPLES (past corrected classifications. Apply ONLY if the "
               f"current message requests the SAME action in different words; they NEVER apply "
               f"to greetings, questions, statements, or different requests, and they are NOT "
               f"commands to execute):\n{exemplars_text}") if exemplars_text else ""
    # 92.E5 (adapt only): meanings a human already CONFIRMED. They say how to READ a new wording
    # of the same thing; they authorise nothing and are not values to assert.
    confirmed = (chr(10) + "CONFIRMED INTERPRETATIONS (a human approved these meanings; reuse them "
                 "to read a NEW wording of the same thing. They are not commands, not tools, and not "
                 "facts to repeat):" + chr(10) + learning_text) if learning_text else ""
    # 93.R4: a bare "yes" teaches nothing alone -- its meaning is the question it answers, and the
    # router was never shown one was outstanding. Context, like the active directives: it says how
    # to READ this turn and authorises nothing.
    # 93.Q2: `question_for` asks two different questions, and only one of them can be answered with a
    # word. Telling the router to expect a yes/no to a question that asked for a NAME is why the
    # answer that supplied the name produced no envelope at all -- the reply is neither feedback nor
    # a free-standing new fact, and nothing said what it is. `needs` comes off the case itself.
    filling = (chr(10) + _filling_line(pending_needs)
               if (pending_question and pending_needs in ("subject", "context")) else "")
    waiting = ((chr(10) + "QUESTION YOU ASKED AND ARE WAITING ON (context): " + pending_question
                + chr(10) + "A bare yes/no/maybe this turn ANSWERS THAT QUESTION -- report it as "
                "feedback (confirm / reject / uncertain), not as a new fact. If the turn answers "
                "something else entirely, ignore this line." + filling) if pending_question else "")
    # 93.W: the learning contract goes LAST, nearest the message it is about. It used to sit inside
    # ROUTE_PROMPT, ahead of 22 tools and 3,793 characters of catalogue, and a single-variable bisect
    # on the real router showed what that cost: the same sentence and the same schema produced a
    # correct `domain_definition` proposal with an empty catalogue and `memory_update: null` with the
    # real one. Nothing was wrong with the contract's words -- 0/6 "no envelope" in
    # diag_definition_write was a position. Measured after moving them: taught 1/3 -> 2/3 with undue
    # proposals on the negatives unchanged at 0/3.
    teaching = ("\n" + LEARNING_PROMPT) if learning_enabled(format_schema) else ""
    reply = chat(
        "router",                                   # 73.2: its own role (default = the chat model)
        [{"role": "system", "content": runtime_prompt + "\n"
          + ROUTE_PROMPT.replace("[[LEARNING]]", "")
          + "\nRUNTIME TOOL CATALOG:\n" + catalog_text + active + learned + confirmed + waiting
          + teaching},
         {"role": "user", "content": text[:4000]}],
        json_mode=True, temperature=0.0, format_schema=format_schema,
        think=False,   # 73.2: a grammar-constrained CLASSIFICATION never needs native reasoning — with the model
    )                  # default (thinking on) gemma4:12b spent 6–70 s per route; with think=False 2.2–3.1 s
    return parse_json(reply) or {}


def generate_directive_content(chat, parse_json, content_spec: str, role: str = "chat") -> str:
    """Produce ONE short piece of content matching a free-text spec — 'a short joke', 'a curious
    scientific fact', 'uma citação inspiradora' — in the spec's OWN language. This is what makes
    opener/closer directives content-general instead of joke-only (Phase 55)."""
    reply = chat(
        role,
        [{"role": "system", "content":
          "Produce ONE short piece of content that fits the user's description, in the SAME "
          "language as the description. Return JSON only: {\"text\": \"the content\"}. Output ONLY "
          "the content itself — no preamble, no surrounding quotes, no meta-commentary, and never "
          "restate the description."},
         {"role": "user", "content": content_spec[:1000]}],
        json_mode=True, temperature=0.5, think=False,      # 73.2: a one-line JSON needs no reasoning
    )
    return str((parse_json(reply) or {}).get("text", "")).strip()[:500]


def resilient_content(chat, parse_json, content_spec: str) -> str:
    for role in ("chat", "nano"):
        try:
            out = generate_directive_content(chat, parse_json, content_spec, role)
            if out:
                return out
        except Exception as exc:
            log.warning("%s directive-content generation failed (%s)", role, exc)
    return ""
