"""Built-in tool schemas and their standalone bodies (bash, file I/O).

Growth path: a new BUILT-IN tool = schema here + a dispatch branch in
toolsys._execute_inner. New CAPABILITIES should normally be skills instead
(drop a file in skills/ or let the agent create_skill one) — zero code here.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from typing import List

REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
SKILLS_DIR = os.path.join(REPO_ROOT, "skills")
WORKSPACE_DIR = os.path.join(REPO_ROOT, "workspace")   # default; see get_workspace()

_workspace_override: str | None = None


def set_workspace(path: str | None) -> None:
    """Select the working folder for bash/read/write (Settings: workspace_dir)."""
    global _workspace_override
    _workspace_override = path if path and os.path.isdir(path) else None


def get_workspace() -> str:
    p = _workspace_override or WORKSPACE_DIR
    os.makedirs(p, exist_ok=True)
    return p

_BLOCKED_BASH = re.compile(
    r"(rm\s+-rf\s+[/~]|mkfs|dd\s+if=|shutdown|reboot|format\s+[a-z]:|del\s+/s\s+/q\s+c:\\)",
    re.IGNORECASE,
)

BUILTIN_TOOLS: List[dict] = [
    {
        "name": "memory_search",
        "x-effect": "read",
        "description": "Search the HMG-Fu relational memory. Returns the top memories with scores and reasons.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "what to search for"},
            "limit": {"type": "integer", "description": "max results (default 8)"},
        }, "required": ["query"]},
    },
    {
        "name": "memory_timeline",
        "x-effect": "read",
        "description": "List memories chronologically (newest first), optionally filtered by type or day.",
        "parameters": {"type": "object", "properties": {
            "limit": {"type": "integer", "description": "max results (default 20)"},
            "type": {"type": "string", "description": "optional memory type filter (fact, goal, ...)"},
            "before": {"type": "string", "description": "optional ISO timestamp upper bound"},
        }},
    },
    {
        "name": "tool_search",
        "x-effect": "read",
        "description": "Search the tool/skill gallery by capability when you need a tool you don't currently see.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "capability you need"},
        }, "required": ["query"]},
    },
    {
        "name": "create_skill",
        "x-effect": "write",
        "description": ("Create a NEW reusable skill (Python). Provide a snake_case name and the full "
                        "python source of a module exporting TOOLS (list of tool schemas) and "
                        "execute(name, arguments) returning a JSON string. It is validated and installed."),
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string", "description": "snake_case skill name"},
            "source": {"type": "string", "description": "full python module source"},
        }, "required": ["name", "source"]},
    },
    {
        "name": "create_widget",
        "x-effect": "write",
        "description": ("Create a live widget on the user's canvas. Types: metric (value, caption, "
                        "spark:[numbers]), table (rows:[[label,value],...]), weather (temp, place, "
                        "detail), note (text), plan (steps), diff (filename, diff), timeline, "
                        "memory-hex / memory-graph (live memory views), and 'app' (props: {file: "
                        "'<path-in-workspace>.html'} OR {url: '<dev-server-url>'}) — use 'app' to SERVE "
                        "a web app/page you built so the user can see and use it live. "
                        "ALWAYS fill props with the real values, e.g. "
                        '{"type":"weather","title":"Lisbon","props":{"temp":"22°C","place":"Lisbon · clear"}} '
                        "or {\"type\":\"app\",\"title\":\"Todo App\",\"props\":{\"file\":\"todo.html\"}}."),
        "parameters": {"type": "object", "properties": {
            "type": {"type": "string", "description": "widget type (see description)"},
            "title": {"type": "string", "description": "short widget title"},
            "props": {"type": "object", "description": "type-specific properties"},
        }, "required": ["type", "title"]},
        "x-max-successful-calls-per-turn": 1,
    },
    {
        "name": "update_widget",
        "x-effect": "write",
        "description": "Update an existing canvas widget's title or props by its id.",
        "parameters": {"type": "object", "properties": {
            "id": {"type": "string"},
            "title": {"type": "string"},
            "props": {"type": "object"},
        }, "required": ["id"]},
    },
    {
        "name": "remove_widget",
        "x-effect": "write",
        "description": "Remove a widget from the canvas by id.",
        "parameters": {"type": "object", "properties": {"id": {"type": "string"}},
                       "required": ["id"]},
    },
    {
        "name": "memory_zoom",
        "x-effect": "read",
        "description": ("Zoom your hierarchical memory like a map. scope='overview' returns the "
                        "coarse macro frontier (big-picture memories); scope='in' with macro_id "
                        "descends into that macro's finer child memories; scope='out' with "
                        "macro_id ascends to its parent context. Use it to recall at the right "
                        "level of detail instead of flooding context."),
        "parameters": {"type": "object", "properties": {
            "scope": {"type": "string", "description": "overview | in | out"},
            "macro_id": {"type": "string", "description": "required for scope=in/out"},
            "limit": {"type": "integer", "description": "max items (default 12)"},
        }, "required": ["scope"]},
        "x-auto-execute-defaults": {"scope": "overview"},
    },
    {
        "name": "brave_web_search",
        "x-effect": "external",
        "description": ("Search the live web with Brave. Use for anything happening NOW — weather, "
                        "news, prices, current events — never answer those from memory. The query must be "
                        "SPECIFIC: include the place and date the user means (e.g. 'Valencia weather 2026-09-04'), "
                        "never the user's sentence verbatim."),
        "x-search-query-arg": "query",     # 66.3: the harness completes place/date deixis in this argument
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "search query"},
            "count": {"type": "integer", "description": "max results (default 5)"},
        }, "required": ["query"]},
    },
    {
        "name": "bash",
        "x-effect": "shell",
        "description": ("Run a shell command (Git Bash) to inspect the project folder / workspace or "
                        "carry out a task — list files, read or search files, check the repository. "
                        "Destructive commands are blocked. Working dir defaults to the workspace."),
        "parameters": {"type": "object", "properties": {
            "command": {"type": "string", "description": "The exact shell command line to run, e.g. "
                                                          "grep -c widget-B inventory.txt. Never the user's request in prose."},
            "timeout": {"type": "integer", "description": "seconds (default 30, max 300)"},
        }, "required": ["command"]},
    },
    {
        "name": "read_file",
        "x-effect": "read",
        "description": ("Read a text file from the workspace to inspect the project's files, config, "
                        "or documents before answering. Max 400 lines from offset."),
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"},
            "offset": {"type": "integer", "description": "start line (default 0)"},
        }, "required": ["path"]},
    },
    {
        "name": "app_errors",
        "x-effect": "read",
        "description": ("What an app you BUILT reported while it ran in the user's canvas: console errors, "
                        "rejected promises, failed requests, with the file and line. Call it when the user "
                        "says a widget or page shows an error, or before you change a page you built. This "
                        "is observed from the running page, not the user's description."),
        "parameters": {"type": "object", "properties": {
            "file": {"type": "string", "description": "one built file (default: every app on this canvas)"},
        }},
    },
    {
        "name": "list_files",
        "x-effect": "read",
        "description": ("List the files in the workspace (or one of its sub-folders): the READ-ONLY way to see what "
                        "exists. Use this instead of a shell `ls`."),
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "folder relative to the workspace (default '.')"},
            "pattern": {"type": "string", "description": "glob such as '*.txt' (default '*')"},
        }},
    },
    {
        "name": "write_file",
        "x-effect": "write",
        "description": "Write a text file. NEW files must be inside the workspace directory.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
        }, "required": ["path", "content"]},
    },
]


def run_web_search(query: str, count: int = 5) -> dict:
    """Brave web search. Key from env or the encrypted vault; honest error when absent —
    the agent must SAY it can't fetch live data, not silently fall back to stale memory."""
    key = os.environ.get("BRAVE_API_KEY")
    if not key:
        try:
            from .connectors import CredentialVault
            secret = CredentialVault().get("brave") or {}
            key = secret.get("api_key")
        except Exception:
            key = None
    if not key:
        return {"error": ("web search is NOT configured (no Brave API key). Tell the user you "
                          "cannot fetch live data right now and that a Brave key can be added "
                          "in Settings → Connectors. Do NOT answer from stale memories.")}
    import httpx
    try:
        r = httpx.get("https://api.search.brave.com/res/v1/web/search",
                      params={"q": query[:200], "count": max(1, min(count, 10))},
                      headers={"X-Subscription-Token": key, "Accept": "application/json"},
                      timeout=15)
        r.raise_for_status()
        results = [{"title": w.get("title", ""), "url": w.get("url", ""),
                    "snippet": w.get("description", "")[:240]}
                   for w in (r.json().get("web", {}).get("results") or [])[:count]]
        return {"results": results, "query": query}
    except httpx.HTTPError as exc:
        return {"error": f"web search failed: {exc}"}


def environment_hint() -> str:
    """Live host facts appended to the bash tool description so a model targets the ACTUAL shell,
    not its training prior (Phase 57 P5 — ornith, a Linux-trained coder, emitted Windows-broken
    commands). Derived from platform/shutil each process start → dynamic and correct on any host,
    never a hardcoded phrase list."""
    import platform
    import shutil
    osname = platform.system() or "unknown"
    has_bash = "bash" in (shutil.which("bash") or "").lower()
    if osname == "Windows":
        return (" | HOST OS: Windows. This shell is Git Bash (POSIX sh): use FORWARD slashes and "
                "Unix commands (ls, cat, grep, echo); the path /c/... maps to C:\\.... Do NOT emit "
                "PowerShell cmdlets or Windows backslash paths, and do NOT assume Linux-only "
                "binaries are installed.")
    return f" | HOST OS: {osname} ({'POSIX sh' if has_bash else 'shell'}); standard Unix commands."


def run_bash(command: str, timeout: int = 30) -> dict:
    if not command.strip():
        return {"error": "empty command"}
    if _BLOCKED_BASH.search(command):
        return {"blocked": True, "reason": "destructive command pattern"}
    timeout = max(1, min(timeout, 300))
    workspace = get_workspace()
    # WindowsApps bash.exe is WSL. Translate model-supplied Windows absolute paths; relative
    # commands already run in the selected workspace and remain unchanged.
    bash_bin = shutil.which("bash") or "bash"
    if os.name == "nt" and "windowsapps" in bash_bin.lower():
        def _wsl_path(match):
            drive, rest = match.group(1).lower(), match.group(2).replace("\\", "/")
            return f"/mnt/{drive}/{rest}"
        command = re.sub(r"\b([A-Za-z]):[\\/]([^\s\"'\r\n]+)", _wsl_path, command)
    try:
        # PA3 lesson: plain subprocess.run (thread offload happens at the API layer)
        proc = subprocess.run(
            [bash_bin, "-lc", command] if os.name != "nt" else [bash_bin, "-c", command],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, cwd=workspace,
        )
        return {"stdout": proc.stdout[-6000:], "stderr": proc.stderr[-2000:],
                "exit_code": proc.returncode}
    except subprocess.TimeoutExpired:
        return {"error": f"timed out after {timeout}s"}
    except FileNotFoundError:
        # no bash on PATH — fall back to cmd
        proc = subprocess.run(command, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=timeout, cwd=workspace)
        return {"stdout": proc.stdout[-6000:], "stderr": proc.stderr[-2000:],
                "exit_code": proc.returncode}


_BINARY_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".exe", ".dll", ".db", ".bin"}


def workspace_names(path: str = "") -> list:
    """95.16/95.19: the workspace's top-level entries (dirs with a trailing slash), from the same native
    read the model would call; [] when the workspace cannot be listed."""
    try:
        out = list_files(path or get_workspace())
    except Exception:
        return []
    return [f["name"] + ("/" if f.get("kind") == "dir" else "") for f in out.get("files") or []]


def fold_path_alias(name: str, args: dict) -> dict:
    """71.7: models drift on the argument name (`filename`, `file`, `target`) — fold it into `path` for the file tools."""
    if name in ("read_file", "write_file", "list_files") and isinstance(args, dict) and not args.get("path"):
        for alias in ("filename", "file", "file_path", "filepath", "name", "target"):
            if args.get(alias):
                args["path"] = str(args[alias])
                break
    return args


def list_files(path: str = ".", pattern: str = "*") -> dict:
    """70.6: workspace-bound listing (names, sizes) — the native read that replaces `bash ls`."""
    import glob as _glob
    workspace = os.path.realpath(get_workspace())
    raw = path if os.path.isabs(path or ".") else os.path.join(workspace, path or ".")
    full = os.path.realpath(raw)
    if full != workspace and not full.startswith(workspace + os.sep):
        return {"blocked": True, "reason": "listing must stay inside the workspace directory"}
    if not os.path.isdir(full):
        return {"error": f"not a folder: {full}"}
    entries = sorted(_glob.glob(os.path.join(full, pattern or "*")))[:200]
    return {"path": full, "count": len(entries),
            "files": [{"name": os.path.relpath(e, full), "kind": "dir" if os.path.isdir(e) else "file",
                       "bytes": (os.path.getsize(e) if os.path.isfile(e) else None)} for e in entries]}


def read_file(path: str, offset: int = 0) -> dict:
    full = path if os.path.isabs(path) else os.path.join(get_workspace(), path)
    if os.path.splitext(full)[1].lower() in _BINARY_EXTS:
        return {"blocked": True, "reason": "binary file — refusing to read as text"}
    if not os.path.isfile(full):
        return {"error": f"not found: {full}"}
    with open(full, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    chunk = lines[offset:offset + 400]
    return {"path": full, "lines": len(lines), "offset": offset,
            "content": "".join(chunk)[:24000]}


def write_file(path: str, content: str) -> dict:
    # H-02 / M-13: EVERY write target must resolve to inside the workspace — existing or not,
    # symlinks/junctions resolved. The old guard blocked only NON-existing outside paths, so a
    # model-supplied absolute path could overwrite an existing external file.
    workspace = os.path.realpath(get_workspace())
    if not (path or "").strip():
        return {"error": "write_file needs a file name in `path` (e.g. notes/report.txt)"}
    raw = path if os.path.isabs(path) else os.path.join(workspace, path)
    full = os.path.realpath(raw)
    if full != workspace and not full.startswith(workspace + os.sep):
        return {"blocked": True, "reason": "writes must stay inside the workspace directory"}
    if full == workspace or os.path.isdir(full):
        return {"error": f"`path` points at a folder ({os.path.relpath(full, workspace) or '.'}) — give a file name"}
    os.makedirs(os.path.dirname(full), exist_ok=True)
    if os.path.isfile(full):                                     # 71.4: identical content already on disk → idempotent
        try:
            with open(full, "r", encoding="utf-8") as f:
                if f.read() == content:
                    return {"path": full, "bytes": len(content.encode("utf-8")), "already_present": True}
        except (OSError, UnicodeDecodeError):
            pass
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)
    return {"path": full, "bytes": len(content.encode("utf-8"))}
