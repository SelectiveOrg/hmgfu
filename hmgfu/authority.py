"""The ONE authority boundary for side effects (Phase 69.1 → Phase 70 M1).

Every path that can change the world — a tool call (including a fuzzy alias of one), a shell command, a skill,
the code-block materializer — asks `decide()` the same question: *may THIS effect happen on THIS turn?*

Authority is a RECORD and turn state, never a phrase in the reply and never a boolean minted by the system:
  * `user_request` — the user asked for the effect in this message (turn_events) and did not prohibit it;
  * `approved_plan` — the active plan carries an authorization record `{origin, message, turn_seq, at}` written
    when the USER approved it (session_plans) or asked for it (plan_task on an order turn). Resume PRESERVES the
    record; it never creates one. A plan without a record is unapproved and must ask.
Scope: an approved plan authorizes the tools its steps name (and the tools it already used); when its steps name
files, `write_file` may only touch those files. A prohibition ("do not create…") or a cancellation closes authority
for the turn regardless of router pins or keywords.
Effects are DECLARED per tool (`x-effect`: none | read | external | write | shell); a tool without a declaration is
`unknown` and is treated as an effect (fail-closed). Shell is read-only only when it matches a tiny allow-list grammar.
Blocked effects are recorded in `engine._turn_unconfirmed_effects` so the say-do gate proposes them.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import List, Optional, Set, Tuple

# kept for compatibility (toolsys re-exports it; benches import it): the classic write tools
SIDE_EFFECT_TOOLS = {"create_widget", "update_widget", "remove_widget", "write_file", "create_skill"}
PLAN_TOOLS = {"plan_task", "update_plan"}
READ_ONLY_TOOLS = {"read_file", "list_files", "memory_search", "memory_timeline", "memory_zoom", "tool_search"}
BUILTIN_EFFECTS = {
    "memory_search": "read", "memory_timeline": "read", "memory_zoom": "read", "tool_search": "read",
    "read_file": "read", "list_files": "read", "brave_web_search": "external",
    "plan_task": "none", "update_plan": "none",
    "create_widget": "write", "update_widget": "write", "remove_widget": "write", "write_file": "write",
    "create_skill": "write", "bash": "shell",
}
EFFECT_KINDS = ("none", "read", "external", "write", "shell", "unknown")

# ---------------------------------------------------------------- shell: allow-list GRAMMAR (70.6) -----------------
# A command is read-only ONLY if: one segment (no ; && || | newline), no redirection/substitution, a known read-only
# program, and only flags from that program's known read-only set. Everything else is an effect — including any
# program we do not know (find, awk, sed, xargs, env, sort, python, tar, date…).
_FORBIDDEN = re.compile(r"[;&<>`]|\$\(|\n|\r")          # 95.23: `|` is judged per stage, below
_IN_REDIRECT = re.compile(r"(?<![<>])<(?![<(])\s*([\w./~\\:*-]+)")   # 95.57: "< path" reads the path; << <( > stay out
_REMOVAL_PROGRAMS = {"rm", "rmdir", "unlink", "shred", "del", "erase", "rd", "remove-item", "ri"}   # 95.56a
_QUOTED = re.compile(r"""^(?:"[^"`$;&|<>]*"|'[^'`$;&|<>]*')$""")   # a quoted plain word (grep "checksum")
_READ_PROGRAMS = {
    "ls": {"-l", "-a", "-la", "-al", "-lh", "-lah", "-alh", "-h", "-1", "-R", "-t", "-lt", "-lta"},
    "dir": set(), "pwd": set(), "cat": set(), "tree": {"-L"}, "wc": {"-l", "-w", "-c", "-m"}, "echo": {"-n", "-e"},
    "head": {"-n"}, "tail": {"-n"},
    "grep": {"-c", "-n", "-i", "-l", "-h", "-r", "-R", "-E", "-F", "-w", "-x", "-v", "-o", "-m", "-A", "-B", "-C", "-in", "-rn", "-ri", "-rl"},
}
_GIT_READ = {"status": {"-s", "--short", "-b", "--porcelain"}, "log": {"--oneline", "-n", "--stat", "--graph", "--decorate"},
             "diff": {"--stat", "--name-only", "--cached"}, "branch": {"--show-current", "-a", "--list"},
             "rev-parse": {"HEAD", "--abbrev-ref", "--short"}, "show": {"--stat", "--name-only"}}
_INT = re.compile(r"^-?\d+$")
_PATHLIKE = re.compile(r"^[\w./~\\:*-]+$")


def _split_pipeline(cmd: str) -> list:
    """95.23: the stages of `a | b | c`, split on a `|` that stands outside quotes."""
    stages, cur, quote = [], [], ""
    for ch in cmd:
        if quote:
            cur.append(ch); quote = "" if ch == quote else quote
        elif ch in "\"'":
            cur.append(ch); quote = ch
        elif ch == "|":
            stages.append("".join(cur)); cur = []
        else:
            cur.append(ch)
    stages.append("".join(cur))
    return stages if not quote else [cmd + "\x00"]        # an unclosed quote fails closed


def shell_removes(command: str) -> bool:
    """95.56a: a shell command REMOVES when one of its stages runs a removal program (or git rm / git clean);
    a write or a truncation ("echo x > f") creates. The op of a shell effect is what the command does."""
    for stage in re.split(r"\s*(?:\|\|?|&&|;)\s*", (command or "").strip()):
        toks = stage.split()
        prog = toks[0].lower().rsplit("/", 1)[-1] if toks else ""
        if prog in _REMOVAL_PROGRAMS or (prog == "git" and len(toks) > 1 and toks[1] in ("rm", "clean")):
            return True
    return False


def tool_removes(name: str, args) -> bool:
    """95.56a: the op of an effect is what the tool DID -- a widget removal, or a shell command that removes;
    a shell write creates (every bash effect used to count as a removal in saydo's ledger)."""
    return name == "remove_widget" or (name == "bash" and shell_removes(str((args or {}).get("command") or "")))


def shell_is_read_only(command: str) -> bool:
    cmd = _IN_REDIRECT.sub(lambda m: " " + m.group(1), (command or "").strip())   # 95.57: the redirected file is an argument
    if not cmd or _FORBIDDEN.search(cmd):
        return False
    stages = _split_pipeline(cmd)
    if len(stages) > 1:                                    # 95.23: a pipeline of reads is a read
        return all(shell_is_read_only(st) for st in stages)
    tokens = cmd.split()
    prog = tokens[0].lower()
    if prog == "git":
        if len(tokens) < 2 or tokens[1] not in _GIT_READ:
            return False
        allowed = _GIT_READ[tokens[1]]
        for tok in tokens[2:]:
            if tok in allowed or _INT.match(tok) or tok.startswith("HEAD"):
                continue
            if tok.startswith("-"):
                return False                       # an unknown flag can write (-d, -D, -m, --set-upstream…)
            if tokens[1] in ("branch", "rev-parse"):
                return False                       # a positional here CREATES a branch / is not a read
            if not _PATHLIKE.match(tok):
                return False
        return True
    if prog not in _READ_PROGRAMS:
        return False
    allowed = _READ_PROGRAMS[prog]
    expect_int = False
    for tok in tokens[1:]:
        if expect_int:
            if not _INT.match(tok):
                return False
            expect_int = False
            continue
        if tok in allowed:
            expect_int = tok in ("-n", "-L") and prog in ("head", "tail", "tree")   # grep -n takes no count
            continue
        if _INT.match(tok) and prog in ("head", "tail"):
            continue                               # head -3
        if tok.startswith("-"):
            return False
        if prog == "echo" or _QUOTED.match(tok):
            continue                               # plain words (the forbidden characters were rejected above)
        if not _PATHLIKE.match(tok):
            return False
    return not expect_int


_LEAVES_CWD = re.compile(r"""(?:^|[\s"'=>])(?:~[/\\]?|~\w|/(?!dev/null)|[A-Za-z]:[\\/]|\.\.(?:[/\\]|$))""")   # 95.61: path forms that leave cwd


def shell_leaves_workspace(command: str) -> bool:
    """95.61: does a MUTATING shell command name a path outside the workspace (absolute, home-relative,
    drive-qualified, or climbing with '..')? Relative paths stay inside the cwd the runner sets; reads are
    not this rule's business. Structural: path forms, no name list."""
    cmd = (command or "").strip()
    return bool(cmd) and not shell_is_read_only(cmd) and bool(_LEAVES_CWD.search(cmd))


def shell_is_mutating(command: str) -> bool:
    """Compatibility name: True unless the command matches the read-only grammar (fail-closed)."""
    return not shell_is_read_only(command)


# ---------------------------------------------------------------- effects -------------------------------------------
def effect_of(name: str, args: Optional[dict], schema: Optional[dict] = None) -> str:
    """Declared effect kind of a tool call. Undeclared → 'unknown' (an effect)."""
    declared = (schema or {}).get("x-effect") or BUILTIN_EFFECTS.get(name)
    if declared == "shell" or (declared is None and name == "bash"):
        return "read" if shell_is_read_only(str((args or {}).get("command") or "")) else "write"
    if declared not in EFFECT_KINDS:
        return "unknown"
    return declared


def is_side_effect(name: str, args: Optional[dict], schema: Optional[dict] = None) -> bool:
    return effect_of(name, args, schema) in ("write", "unknown")


def resolve_name(engine, name: str) -> str:
    """The tool that would actually RUN for `name` (toolsys reroutes unknown names to a confident match)."""
    tools = getattr(engine, "tools", None)
    schemas = getattr(tools, "schemas", {}) or {}
    if name in schemas or tools is None:
        return name
    closest = getattr(tools, "_closest_tool", None)
    try:
        match = closest(name) if closest else None
    except Exception:
        match = None
    return match or name


# ---------------------------------------------------------------- authorization + scope ------------------------------
_FILE_IN_TEXT = re.compile(r"\b([\w][\w.-]*\.[A-Za-z0-9]{1,5})\b")


def authorization(engine) -> Optional[dict]:
    """The authorization in force this turn: {'origin': 'user_request'|'approved_plan', ...} or None."""
    if getattr(engine, "_turn_prohibited", False):
        return None                                # "do not create…" wins over everything
    plan = getattr(engine, "_turn_plan", None)
    record = plan.get("authorization") if isinstance(plan, dict) else None
    if isinstance(record, dict) and record.get("origin"):
        return {"origin": "approved_plan", "plan": plan, "record": record}
    if getattr(engine, "_turn_effects_allowed", False):
        return {"origin": "user_request"}
    return None


def user_directly_requested(engine) -> bool:
    """Whether THIS turn carries the USER's own request for an effect.

    93.B: `_turn_effects_allowed` is broader than that — it is also true when the router or an approved
    plan pinned a side-effect tool, so an approval turn ("yes please") reads as a request. Widening the
    plan's scope on those turns would let the model wander out of the plan it is executing, which is
    the opposite of what the boundary is for."""
    from .speech_act import is_suggestion, requests_side_effect
    msg = str(getattr(engine, "_turn_user_message", "") or "")
    return (bool(msg.strip()) and requests_side_effect(msg) and not is_suggestion(msg)
            and not getattr(engine, "_turn_prohibited", False))


def plan_scope(plan: dict, tool_names) -> Tuple[Set[str], Set[str]]:
    """(tools, files) an approved plan authorizes: the tools its steps name (+ already used), and the file names
    its steps mention. Empty sets mean 'no restriction of that kind'."""
    from .session_plans import tools_for_step
    tools: Set[str] = set(plan.get("tools_used") or [])
    files: Set[str] = set()
    for step in plan.get("steps", []):
        text = step.get("text", "")
        tools.update(tools_for_step(text, tool_names))
        files.update(os.path.basename(f).lower() for f in _FILE_IN_TEXT.findall(text))
    return tools, files


@dataclass
class Decision:
    allowed: bool
    effect: str
    origin: Optional[str]
    reason: str = ""
    tool: str = ""


def decide(engine, name: str, args: Optional[dict]) -> Decision:
    real = resolve_name(engine, name)
    schemas = getattr(getattr(engine, "tools", None), "schemas", {}) or {}
    eff = effect_of(real, args, schemas.get(real))
    if eff in ("none", "read", "external"):
        return Decision(True, eff, None, "", real)
    if real == "bash" and shell_leaves_workspace(str((args or {}).get("command") or "")):   # 95.61: the workspace is
        return Decision(False, eff, None, "the command writes outside the workspace, which no request can authorise "
                                          "— use a path inside the workspace (relative to it) or write_file", real)   # the sandbox
    from .prohibitions import forbidden_target                  # 95.65b: a STORED prohibition binds every later turn
    hit = forbidden_target(getattr(getattr(engine, "directives", None), "active", lambda: [])(), real, args)
    if hit:
        return Decision(False, eff, None, f"a standing rule forbids writing {hit} \u2014 it stays until the user lifts it; "
                                          "do not write that file and say so", real)
    auth = authorization(engine)
    if auth is None:
        why = "an undeclared effect" if eff == "unknown" else "a side effect"
        return Decision(False, eff, None, f"{real} is {why} and needs the user's confirmation first — describe what "
                                          "you would do and ask; do not call it again this turn", real)
    if auth["origin"] == "approved_plan":
        tools, files = plan_scope(auth["plan"], list(schemas.keys()))
        # 93.B: a plan the user approved for one purpose does not shrink what they may ask for next.
        # When the CURRENT turn carries the user's own request, that is the authority in force and the
        # plan's scope does not apply to it. The plan still binds the model's unprompted work, and a
        # prohibition has already returned None above.
        direct = user_directly_requested(engine)
        if tools and real not in tools:
            if direct:
                return Decision(True, eff, "user_request", "", real)
            return Decision(False, eff, "approved_plan",
                            f"{real} is outside the approved plan's scope ({', '.join(sorted(tools))}) — ask before it", real)
        if real == "write_file" and files and not direct:
            target = os.path.basename(str((args or {}).get("path") or "")).lower()
            if target and target not in files:
                return Decision(False, eff, "approved_plan",
                                f"the approved plan names {sorted(files)}, not {target!r} — ask before writing it", real)
    return Decision(True, eff, auth["origin"], "", real)


def effect_authorized(engine) -> bool:
    """Compatibility: is ANY write authorized this turn (no scope)?"""
    return authorization(engine) is not None


def guard(engine, name: str, args: Optional[dict]) -> Optional[str]:
    """Blocked-outcome JSON when the call may not run this turn, else None (records the blocked effect)."""
    d = decide(engine, name, args)
    if d.allowed:
        return None
    getattr(engine, "_turn_unconfirmed_effects", []).append({"name": d.tool, "arguments": args or {}, "effect": d.effect})
    return json.dumps({"blocked": True, "reason": d.reason})
