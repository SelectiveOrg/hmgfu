"""Tool system core: registry, skill discovery, ONE dispatch entry point.

Split for modularity (ROADMAP Phase 18):
- tool_builtins.py — built-in schemas + bash/file bodies
- tool_points.py   — tools-as-HMG-points sync & retrieval
- skills/*.py      — hot-loadable capabilities (the self-growing surface)
This module re-exports the split symbols so existing imports keep working (Rule 11).

PA3-proven invariants (docs/PA3_LESSONS.md): one dispatch entry, every result a JSON
string, every hook fail-soft, blocked:true is the safety layer working (not a failure).
"""

from __future__ import annotations

import ast
import importlib.util
import json
import logging
import os
import re
from typing import Callable, Dict, List

# Re-exported for callers/tests that import them from toolsys (compat façade).
from .plans import PLAN_TOOLS
from .tool_builtins import (BUILTIN_TOOLS, REPO_ROOT, SKILLS_DIR, fold_path_alias, list_files, WORKSPACE_DIR, read_file, run_bash, run_web_search, write_file)  # noqa: F401
from .tool_points import retrieve_tools_for_turn, sync_tool_points  # noqa: F401

log = logging.getLogger("hmgfu.toolsys")


# Phase 66.6: tools with side effects on the user's canvas/disk — never run unasked on a plain question
from .authority import SIDE_EFFECT_TOOLS  # noqa: F401  — 69.1: ONE canonical effect list (re-exported)
from .speech_act import is_interrogative as _is_question   # 95.40: a question is never a shell command


from .memory_tools import (_recall_record, memory_search,  # noqa: E402,F401
                           memory_timeline, memory_zoom)


_SHELL_WORDS = {"cd", "echo", "export", "set", "unset", "pwd", "test", "[", "[[", "source", ".", "alias", "type", "printf",
                "read", "eval", "exec", "true", "false", "for", "while", "until", "if", "then", "else", "fi", "do", "done", "case",
                "esac", "shopt", "ulimit", "command", "builtin", "let", "local", "return", "exit", "trap", "wait", "kill", "jobs",
                "time", "declare", "readonly", "function", "{", "(", "!"}   # 95.64: bash builtins and keywords (no program file)


def _first_program(command: str) -> str:
    """The first program of a shell command: the token after leading VAR=value assignments, unquoted."""
    import re
    toks = re.split(r"\s*(?:;|&&|\|\||\||\n)\s*", (command or "").strip(), maxsplit=1)[0].split()   # 95.64b: the FIRST stage
    while toks and re.fullmatch(r"[A-Za-z_]\w*=.*", toks[0]):
        toks.pop(0)
    return toks[0].strip("\"'`(") if toks else ""


def _is_program(tok: str) -> bool:
    """A builtin/keyword, a path (the shell will say if it is missing), or a program on this host's PATH."""
    import os
    import shutil
    if tok in _SHELL_WORDS or "/" in tok or "\\" in tok or tok.startswith((".", "~", "$")):
        return True
    return shutil.which(tok) is not None or shutil.which(tok.lower()) is not None


class ToolRegistry:
    """All callable tools: built-ins + discovered skills. Skills carry their handler."""

    def __init__(self, engine=None):
        self.engine = engine                      # HMGFuEngine, set by AgentEngine
        # shallow-copy each schema so per-registry augmentation never mutates the module constants
        self.schemas: Dict[str, dict] = {t["name"]: dict(t) for t in BUILTIN_TOOLS + PLAN_TOOLS}
        if "bash" in self.schemas:                 # P5: ground the shell tool in the LIVE host OS
            from .tool_builtins import environment_hint
            self.schemas["bash"]["description"] = self.schemas["bash"]["description"] + environment_hint()
        self.skill_handlers: Dict[str, Callable] = {}   # tool name -> execute fn
        self.skill_meta: Dict[str, dict] = {}           # skill file name -> {tools, summary, path}
        self.usage: Dict[str, dict] = {}                # tool name -> {calls, failures}
        os.makedirs(SKILLS_DIR, exist_ok=True)
        os.makedirs(WORKSPACE_DIR, exist_ok=True)
        self.load_skills()

    # --- skills (the self-growing surface) --------------------------------------

    @staticmethod
    def validate_skill_source(source: str) -> str | None:
        """AST validation: parseable, exports TOOLS and execute. Returns error or None."""
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            return f"syntax error: {exc}"
        names = set()
        for node in tree.body:
            if isinstance(node, ast.Assign):
                names.update(t.id for t in node.targets if isinstance(t, ast.Name))
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                names.add(node.target.id)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names.add(node.name)
        if "TOOLS" not in names:
            return "module must export TOOLS (list of tool schemas)"
        if "execute" not in names:
            return "module must export execute(name, arguments)"
        return None

    def register_skill_module(self, path: str) -> dict:
        """Import a skill file and register its tools. Fail-soft: returns {ok, error?}."""
        fname = os.path.basename(path)
        try:
            spec = importlib.util.spec_from_file_location(f"hmgfu_skill_{fname[:-3]}", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            tools = getattr(mod, "TOOLS", None)
            execute = getattr(mod, "execute", None)
            if not isinstance(tools, list) or not callable(execute):
                return {"ok": False, "error": "skill must export TOOLS list and execute()"}
            registered = []
            for schema in tools:
                name = schema.get("name")
                if not name:
                    continue
                schema.setdefault("x-effect", "unknown")   # 70.6: an undeclared effect is UNKNOWN (fail-closed)
                self.schemas[name] = schema
                self.skill_handlers[name] = execute
                registered.append(name)
            summary = (mod.__doc__ or "").strip().split("\n")[0]
            self.skill_meta[fname] = {"tools": registered, "summary": summary, "path": path}
            log.info("skill %s registered: %s", fname, registered)
            return {"ok": True, "tools": registered, "summary": summary}
        except Exception as exc:
            log.warning("skill %s failed to load: %s", fname, exc)
            return {"ok": False, "error": str(exc)}

    def load_skills(self) -> None:
        for fname in sorted(os.listdir(SKILLS_DIR)):
            if fname.endswith(".py") and not fname.startswith("_"):
                self.register_skill_module(os.path.join(SKILLS_DIR, fname))

    def install_skill(self, name: str, source: str) -> dict:
        """create_skill implementation: validate → write → register (hot)."""
        safe = re.sub(r"[^a-z0-9_]", "", name.lower().replace(".py", ""))
        if not safe:
            return {"ok": False, "error": "invalid skill name"}
        error = self.validate_skill_source(source)
        if error:
            return {"ok": False, "error": error}
        path = os.path.join(SKILLS_DIR, f"{safe}.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write(source)
        result = self.register_skill_module(path)
        result["path"] = path
        return result

    # --- gallery ------------------------------------------------------------------

    def gallery(self) -> List[dict]:
        out = []
        for name, schema in self.schemas.items():
            stats = self.usage.get(name, {})
            out.append({
                "name": name,
                "description": schema.get("description", ""),
                "kind": "skill" if name in self.skill_handlers else "builtin",
                "calls": stats.get("calls", 0),
                "failures": stats.get("failures", 0),
            })
        return out

    def search(self, query: str, limit: int = 10) -> List[dict]:
        terms = [t for t in re.findall(r"\w+", query.lower()) if len(t) > 2]
        scored = []
        for item in self.gallery():
            hay = (item["name"] + " " + item["description"]).lower()
            score = sum(1 for t in terms if t in hay)
            if score:
                scored.append((score, item))
        return [item for _, item in sorted(scored, key=lambda t: -t[0])[:limit]]

    # --- dispatch (the ONE entry point) ----------------------------------------------

    def execute_tool(self, name: str, arguments: dict) -> str:
        stats = self.usage.setdefault(name, {"calls": 0, "failures": 0})
        stats["calls"] += 1
        from .recall_budget import budget_for                # 93.R5: one answer per search, per turn
        repeat = budget_for(self).seen(name, arguments or {})
        if repeat is not None:
            return repeat
        echoed = self.echoes_the_request(name, arguments or {})      # 95.64: the same judgement at both dispatch points
        if echoed is not None:
            return echoed
        try:
            result = self._execute_inner(name, arguments or {})
        except Exception as exc:
            stats["failures"] += 1
            return json.dumps({"error": f"{type(exc).__name__}: {exc}"})
        failed, _ = classify_tool_result(result)
        if failed:
            stats["failures"] += 1
        return budget_for(self).record(name, arguments or {}, result, owner=self)

    def echoes_the_request(self, name: str, args: dict):
        """95.40: the loop asks this BEFORE the authority guard -- an echoed request has no effect to authorise.
        95.64: nor has a text whose first program is not a program on this host -- it is not a command."""
        return self._echoes_the_request(name, args) or self._not_a_command(name, args)

    def _not_a_command(self, name: str, args: dict):
        """95.64: a `bash` call is a command only if its first program (after leading VAR=value assignments) is a
        program on this host, a shell builtin/keyword, or a path. A prose sentence ("Read the content of the file
        project.txt ...") is refused with the true reason instead of being sent to the authority as a side effect."""
        if name != "bash":
            return None
        prog = _first_program(str(args.get("command") or ""))
        if not prog or _is_program(prog):
            return None
        return json.dumps({"error": f"that text is not a shell command - '{prog}' is not a program on this host; "
                                    "use read_file / list_files, or a real command"})

    def _echoes_the_request(self, name: str, args: dict):
        """95.9: a `bash` command that IS the turn's user message (or a sentence-long prefix of it) is
        the request echoed, not a command -- E7 burned both attempts on "Show: command not found".
        Structural: equality with the turn's message at the one dispatch point; a short message that
        really is a command ("ls") passes."""
        if name != "bash" or self.engine is None:
            return None
        msg = " ".join(str(getattr(self.engine, "_turn_user_message", "") or "").split()).casefold()
        cmd = " ".join(str(args.get("command", "") or "").split()).casefold()
        if not msg or not cmd or not msg.startswith(cmd):
            return None
        if len(cmd) < 40 and not (cmd == msg and _is_question(msg)):
            return None                      # 95.40: a short command is an echo only when it is the WHOLE message and a question
        others = [k for k, v in args.items() if k != "command" and isinstance(v, str) and v.strip()   # 95.9b -> 95.60a:
                  and not msg.startswith(" ".join(v.split()).casefold())]                             # the ONE other string
        if len(others) == 1:                                                                          # argument that is not
            args["command"] = str(args[others[0]]).strip()             # the command was under another name   # the echo IS the
            return None                                                                               # command (no name list)
        return json.dumps({"error": "that text is the user's request, not a shell command - read the "
                                    "request and choose the command that answers it"})

    def _execute_inner(self, name: str, args: dict) -> str:
        if name == "memory_search":
            return memory_search(self.engine, args)
        if name == "memory_timeline":
            return memory_timeline(self.engine, args)
        if name == "tool_search":
            return json.dumps({"results": self.search(str(args.get("query", "")))})
        if name == "create_skill":
            result = self.install_skill(str(args.get("name", "")), str(args.get("source", "")))
            if result.get("ok") and self.engine is not None:
                sync_tool_points(self, self.engine)   # new skill becomes an HMG point
            return json.dumps(result)
        if name == "app_errors":       # 95.75 (P6): what the built app reported while it ran
            from .app_errors import session_app_files, store_for
            store = store_for(self.engine) if self.engine is not None else None
            if store is None:
                return json.dumps({"error": "runtime error capture not available"})
            one = str(args.get("file", "")).strip()
            files = [one] if one else session_app_files(self.engine, getattr(self.engine, "_turn_session", "") or "")
            rows = store.recent(files)
            return json.dumps({"errors": rows, "files": files,
                               "hint": ("no error has been reported by these pages" if not rows else
                                        "read the file at the line named and fix the cause, then write it again")})
        if name in ("create_widget", "update_widget", "remove_widget"):
            if self.engine is None or not hasattr(self.engine, "widget_action"):
                return json.dumps({"error": "widget canvas not available"})
            return json.dumps(self.engine.widget_action(name, args))
        if name in ("plan_task", "update_plan"):
            if self.engine is None or not hasattr(self.engine, "_turn_plan"):
                return json.dumps({"error": "planning not available"})
            from .plans import plan_action
            return json.dumps(plan_action(self.engine, name, args))
        if name == "memory_zoom":
            return memory_zoom(self.engine, args)
        if name in ("brave_web_search", "web_search"):   # web_search kept as a back-compat alias
            return json.dumps(run_web_search(str(args.get("query", "")),
                                             int(args.get("count") or 5)))
        args = fold_path_alias(name, args)   # 71.7 alias → path
        if name == "list_files":
            return json.dumps(list_files(str(args.get("path") or "."), str(args.get("pattern") or "*")))
        if name == "bash":
            return json.dumps(run_bash(str(args.get("command", "")),
                                       int(args.get("timeout") or 30)))
        if name == "read_file":
            return json.dumps(read_file(str(args.get("path", "")), int(args.get("offset") or 0)))
        if name == "write_file":
            return json.dumps(write_file(str(args.get("path", "")), str(args.get("content", ""))))
        handler = self.skill_handlers.get(name)
        if handler is not None:
            result = handler(name, args)
            if hasattr(result, "__await__"):
                result = _run_coroutine(result)   # M-07: works in a loopless worker thread
            return result if isinstance(result, str) else json.dumps(result)
            # unknown-tool recovery: a confident fuzzy match auto-routes; else suggest candidates
        match = self._closest_tool(name)
        if match is not None:
            rerouted = self._execute_inner(match, args)
            try:
                data = json.loads(rerouted)
                if isinstance(data, dict):
                    data["_rerouted"] = f"'{name}' does not exist — ran '{match}' instead"
                    return json.dumps(data)
            except (json.JSONDecodeError, ValueError):
                pass
            return rerouted
        import difflib
        near = difflib.get_close_matches(name, list(self.schemas), n=3, cutoff=0.5)
        return json.dumps({"error": f"unknown tool: {name}",
                           "hint": (f"did you mean: {', '.join(near)}?" if near
                                    else "use tool_search to find available tools")})

    # 93.Q4: the three memory tools live in `memory_tools` now. These keep the method names every
    # existing caller has always used -- `engine.tools._memory_search(...)` among them -- so the
    # split moved code and moved nothing else.
    def _memory_search(self, args: dict) -> str:
        return memory_search(self.engine, args)

    def _memory_zoom(self, args: dict) -> str:
        return memory_zoom(self.engine, args)

    def _memory_timeline(self, args: dict) -> str:
        return memory_timeline(self.engine, args)

    def _semantic_tool(self, name: str):
        """66.4: an invented tool NAME ('weather') is resolved semantically against the tool points
        (the same HMG surface used for tool selection): confident top hit only (≥0.45, margin ≥0.05)."""
        eng = self.engine
        if eng is None or not hasattr(eng, "graph") or not hasattr(eng, "embed"):
            return None
        try:
            emb = eng.embed(name.replace("_", " "))
        except Exception:
            return None
        from . import fu_math
        scored = []
        for p in eng.graph.points.values():
            if p.type != "skill" or p.status != "active" or not p.embedding:
                continue
            tool = next((kw[5:] for kw in p.keywords if kw.startswith("tool:")), None)
            if tool and tool in self.schemas:
                scored.append((fu_math.cosine(emb, p.embedding), tool))
        scored.sort(reverse=True)
        if scored and scored[0][0] >= 0.45 and (len(scored) == 1 or scored[0][0] - scored[1][0] >= 0.05):
            return scored[0][1]
        return None

    def _closest_tool(self, name: str):
        """Confident single match only: substring containment either way, or one token shared
        with exactly one tool. Never guess between multiple candidates."""
        low = name.lower()
        contains = [t for t in self.schemas
                    if t.lower() in low or low in t.lower()]
        if len(contains) == 1:
            return contains[0]
        tokens = set(low.replace("-", "_").split("_"))
        scored = [(len(tokens & set(t.lower().split("_"))), t) for t in self.schemas]
        best = sorted((s for s in scored if s[0] >= 2), reverse=True)
        if len(best) == 1 or (len(best) > 1 and best[0][0] > best[1][0]):
            return best[0][1]
        return self._semantic_tool(name)          # 66.4: last resort, still confident-only

    # --- built-ins that need the engine ---------------------------------------------

def classify_tool_result(result_str: str) -> tuple:
    """(failed, summary). blocked:true is NOT a failure — the safety layer worked."""
    try:
        data = json.loads(result_str)
    except (json.JSONDecodeError, ValueError):
        return False, ""
    if not isinstance(data, dict):
        return False, ""
    if data.get("blocked"):
        return False, "blocked by safety guard"
    if data.get("error"):
        return True, str(data["error"])[:200]
    if "exit_code" in data and data["exit_code"] not in (0, None):
        return True, f"exit_code={data['exit_code']}: {str(data.get('stderr', ''))[:150]}"
    return False, ""


def _run_coroutine(coro):
    """Run an async skill handler to completion from a SYNC caller (M-07). Agent turns run in an
    AnyIO worker thread with NO event loop, where get_event_loop().run_until_complete() raised
    'no current event loop'. asyncio.run() creates a fresh loop; if a loop is already running
    (unlikely here) fall back to a helper thread so we never nest run() inside a live loop."""
    import asyncio
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(asyncio.run, coro).result()


def tool_signature(name: str, arguments: dict) -> str:
    """Stuck-loop signature: STANDALONE numbers collapse (`sleep 5`/`sleep 500`, offsets, pages) but digits glued to a
    word keep their identity — 73.2(e): note1/note2/note3.txt collapsed to one signature and the third write was blocked."""
    parts = [name]
    for key, value in sorted((arguments or {}).items()):
        parts.append(f"{key}=" + re.sub(r"(?<![\w./-])\d+(?![\w./-])", "#", str(value)[:120]))
    return "|".join(parts)
