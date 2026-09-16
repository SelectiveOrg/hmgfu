"""Canvas widget actions + deterministic argument coverage (Phase 24 doctrine:
the SYSTEM guarantees widget quality — a sparse tool call is enriched from turn
artifacts or answered with precise feedback, never rendered blank)."""

from __future__ import annotations

import json
import os
import re
import uuid

from .sessions import WIDGET_TYPES


def record_turn_artifact(engine, name: str, outcome: str) -> None:
    """Track what the turn produced (workspace files, dev URLs) for deterministic coverage.

    94.2: also keep the raw outcome text. A widget prop that states a fact about the world has to be
    checkable against something, and what the tools actually returned this turn is that something."""
    if outcome:
        getattr(engine, "_turn_evidence", []).append(str(outcome)[:8000])
    try:
        data = json.loads(outcome)
    except (json.JSONDecodeError, ValueError, TypeError):
        return
    if not isinstance(data, dict):
        return
    if name == "write_file" and data.get("path"):
        from .tool_builtins import get_workspace
        ws = os.path.abspath(get_workspace())
        full = os.path.abspath(data["path"])
        if full.startswith(ws):
            engine._turn_files.append(os.path.relpath(full, ws).replace("\\", "/"))
    elif name == "bash":
        m = re.search(r"https?://(?:localhost|127\.0\.0\.1):\d+\S*", str(data.get("stdout", "")))
        if m:
            engine._turn_url = m.group(0)

# props a widget type needs to be meaningful; missing → precise feedback (model retries)
REQUIRED_PROPS = {
    "weather": ["temp", "place"],
    "metric": ["value"],
    "note": ["text"],
    "table": ["rows"],
    "diff": ["diff"],
    "plan": ["steps"],
}


# 94.2: props whose value ASSERTS something about the world, so it must trace to evidence before it is
# published. Deliberately narrow: `note.text` is what the user dictated and `table.rows` is data they
# supplied, so checking those would refuse ordinary use. A weather reading and a metric are claims.
OBSERVED_PROPS = {"weather": ["temp", "place"], "metric": ["value"]}


def _turn_evidence(engine) -> str:
    """Everything this turn may honestly draw a published value from, as one searchable blob.

    Three sources, which are the three the user named: what the TOOLS returned this turn, what the
    USER said this turn, and what the fact LEDGER already holds (a stored location is evidence even
    though no tool fetched it this turn)."""
    parts = [str(x) for x in (getattr(engine, "_turn_evidence", None) or [])]
    parts.append(str(getattr(engine, "_turn_user_message", "") or ""))
    try:
        parts.extend(str(line) for line in engine.facts.render_lines())
    except Exception:
        pass
    return " ".join(parts).casefold()


def _traceable(value, evidence: str) -> bool:
    """Is this published value found in what the turn actually has?

    A number is compared as a numeral so 19, "19" and 19.0 all match the same "19" in a tool result;
    a string is compared whole, casefolded."""
    text = str(value).strip()
    if not text:
        return False
    if isinstance(value, bool):
        return True
    try:
        number = float(text)
    except (TypeError, ValueError):
        return text.casefold() in evidence
    whole = int(number) if number == int(number) else number
    return str(whole) in evidence or text.casefold() in evidence


# widget-schema structural keys (never a prop); everything else at the top level of a call is a
# prop the model FLATTENED out of the nested `props` object — folded in below.
_WIDGET_STRUCT_KEYS = {"type", "title", "props", "id"}
# synonyms models reach for instead of the canonical prop name a widget type requires
_PROP_ALIASES = {"text": ("content", "body", "message"), "value": ("number", "val"),
                 "rows": ("data", "items"), "steps": ("tasks",), "temp": ("temperature",),
                 "place": ("location", "city")}


def enrich_widget_args(engine, wtype: str, args: dict) -> tuple:
    """(props, error_or_None). Deterministic coverage of sparse tool calls — INCLUDING args a model
    FLATTENED: many models emit {type:'note', text:'…'} (or {…, content:'…'}) instead of the nested
    {type:'note', props:{text:'…'}}. Every non-structural top-level key is folded into props and
    common synonyms normalized to the canonical prop, BEFORE validation — so a correct value at the
    wrong nesting level is honoured, not rejected. Model-agnostic (Phase 24 doctrine)."""
    args = args or {}
    props = dict(args.get("props") or {})
    for key, val in args.items():                      # fold flattened top-level props into props
        if key not in _WIDGET_STRUCT_KEYS and key not in props and not isinstance(val, dict):
            props[key] = val
    for canonical, aliases in _PROP_ALIASES.items():   # normalize a synonym → the required prop name
        if props.get(canonical) in (None, ""):
            for alias in aliases:
                if props.get(alias):
                    props[canonical] = props[alias]
                    break
    if wtype == "app":
        if not props.get("file") and not props.get("url"):
            # backfill from what THIS turn produced (files written / dev-server URL)
            url = getattr(engine, "_turn_url", None)
            files = [f for f in getattr(engine, "_turn_files", [])
                     if f.lower().endswith((".html", ".htm", ".svg"))]
            if url:
                props["url"] = url
            elif files:
                props["file"] = files[-1]
            else:
                return props, ("app widget needs props.file (a workspace html you wrote) "
                               "or props.url — write the file first, then create the widget")
        return props, None
    missing = [k for k in REQUIRED_PROPS.get(wtype, []) if props.get(k) in (None, "")]   # 95.15: 0 is a value
    if missing:
        return props, (f"{wtype} widget needs props {missing} — call create_widget again "
                       f"with real values, e.g. props={{{missing[0]!r}: ...}}")
    # 94.2: "real values" was an instruction the tool could not check, and a widget went out with a
    # temperature no tool had returned. A value that asserts a fact must be traceable to this turn's
    # evidence; otherwise the widget is not published and the reply says how to get one.
    # ... but only inside a TURN. That is exactly when a model is choosing the values and may supply a
    # plausible one; a direct programmatic call (the API, a test, a migration) supplies its own values
    # and owns them, and refusing those would break callers that never had a model in the loop
    # (Rule 11). `_turn_user_message` is set for every agent turn and for nothing else.
    evidence = _turn_evidence(engine)
    in_a_turn = bool(str(getattr(engine, "_turn_user_message", "") or "").strip())
    unsupported = [k for k in (OBSERVED_PROPS.get(wtype, []) if in_a_turn else [])
                   if props.get(k) is not None and not _traceable(props[k], evidence)]
    if unsupported:
        return props, (f"{wtype} widget not created: {unsupported} would state a fact this turn has "
                       f"no evidence for. Fetch it with a tool, or use a value the user gave you, "
                       f"then call create_widget again. Do not supply a plausible-looking value.")
    return props, None


def widget_action(engine, action: str, args: dict) -> dict:
    """create/update/remove a canvas widget on the engine's current turn session."""
    session_id = engine._turn_session or "default"
    if action == "create_widget":
        wtype = str(args.get("type", ""))
        if wtype not in WIDGET_TYPES:
            return {"error": f"unknown widget type '{wtype}'", "types": list(WIDGET_TYPES)}
        props, error = enrich_widget_args(engine, wtype, args)
        if error:
            return {"error": error}
        widget = {
            "id": "w_" + uuid.uuid4().hex[:8],
            "type": wtype,
            "title": str(args.get("title", wtype))[:60],
            "props": props,
            "generated": True,
        }
        engine.sessions.upsert_widget(session_id, widget)
        engine._emit({"type": "widget", "action": "create", "widget": widget})
        return {"ok": True, "widget_id": widget["id"], "type": wtype}
    if action == "update_widget":
        wid = str(args.get("id", ""))
        existing = {w["id"]: w for w in engine.sessions.widgets(session_id)}.get(wid)
        if existing is None:
            return {"error": f"widget '{wid}' not found"}
        if args.get("title"):
            existing["title"] = str(args["title"])[:60]
        if isinstance(args.get("props"), dict):
            existing["props"] = {**existing["props"], **args["props"]}
        engine.sessions.upsert_widget(session_id, existing)
        engine._emit({"type": "widget", "action": "update", "widget": existing})
        return {"ok": True, "widget_id": wid}
    if action == "remove_widget":
        wid = str(args.get("id", ""))
        engine.sessions.remove_widget(session_id, wid)
        engine._emit({"type": "widget", "action": "remove", "widget": {"id": wid}})
        return {"ok": True, "widget_id": wid}
    return {"error": f"unknown widget action '{action}'"}


_CODE_BLOCK_RE = None   # compiled lazily (keep import surface small)


def materialize_reply_artifacts(engine, user_message: str, reply: str) -> list:
    """Doctrine backstop: the model answered with a web app as a CHAT CODE BLOCK instead of
    writing a file. The system materializes it — extract the html block, write it to the
    workspace (name from the conversation if one was mentioned), record it as a turn artifact
    so auto_serve_built_apps puts it in the streaming widget."""
    global _CODE_BLOCK_RE
    import re
    if _CODE_BLOCK_RE is None:
        _CODE_BLOCK_RE = re.compile(r"```(?:html)?\s*\n(<!DOCTYPE|<html)(.*?)```",
                                    re.DOTALL | re.IGNORECASE)
    if getattr(engine, "_turn_files", None):
        return []                      # real files were written — nothing to cover
    m = _CODE_BLOCK_RE.search(reply or "")
    if not m:
        return []
    html = (m.group(1) + m.group(2)).strip()
    if len(html) < 80:                 # not a real page
        return []
    # filename: honor one mentioned in the conversation, else a stable default
    name_match = re.search(r"([\w-]+\.html?)\b", user_message + " " + reply)
    fname = os.path.basename(name_match.group(1)) if name_match else "app.html"
    from .authority import guard
    from .toolsys import classify_tool_result
    args = {"path": fname, "content": html}
    blocked = guard(engine, "write_file", args)  # 69.1 → 70.7: the SAME boundary, and a real dispatched action
    if blocked is not None:
        return [{"name": "write_file", "arguments": {"path": fname}, "result": blocked, "failed": False,
                 "blocked": True, "summary": "code block not materialized: needs confirmation", "synthetic": "materializer"}]
    from .receipts import close_for, open_for
    rid = open_for(engine, "write_file", args, getattr(engine, "_turn_seq", 0))
    outcome = engine.tools.execute_tool("write_file", args)      # the receipt: through the registry, in the trace
    failed, summary = classify_tool_result(outcome)
    close_for(engine, rid, "write_file", args, outcome, failed)
    engine._record_artifacts("write_file", outcome)
    return [{"name": "write_file", "arguments": {"path": fname, "content": html[:200] + ("…" if len(html) > 200 else "")},
             "result": outcome[:2000], "failed": failed, "blocked": False, "summary": summary or "materialized code block",
             "synthetic": "materializer"}]


def auto_serve_built_apps(engine) -> int:
    """Turn end: every web file written this turn MUST be reachable in a streaming (app)
    widget — if the model didn't create one, the system does (completion enforcement)."""
    session_id = engine._turn_session or "default"
    web_files = [f for f in getattr(engine, "_turn_files", [])
                 if f.lower().endswith((".html", ".htm", ".svg"))]
    if not web_files:
        return 0
    served = set()
    for w in engine.sessions.widgets(session_id):
        if w["type"] == "app":
            served.add(w["props"].get("file", ""))
    created = 0
    for f in web_files:
        if f in served:
            continue
        # 95.75 (P3): the system's own action is an action. Serving the app without a receipt left a
        # widget on the canvas that no plan step could ever cite, and the step that asked for it stayed
        # open with the work already on screen.
        args = {"type": "app", "title": os.path.basename(f), "props": {"file": f}}
        from .receipts import close_for, open_for
        rid = open_for(engine, "create_widget", args, int(getattr(engine, "_turn_seq", 0) or 0))
        out = widget_action(engine, "create_widget", args)
        close_for(engine, rid, "create_widget", args, json.dumps(out), bool(out.get("error")))
        served.add(f)
        created += 1
    return created
