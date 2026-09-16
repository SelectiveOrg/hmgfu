"""System actions for the Settings UI: restart, rebuild, tailscale serve.

Rule 10: all three are visible buttons in Settings and documented in README.
- restart: re-exec the server process (in-place, same args) after the response flushes.
- rebuild: this UI has NO build step (design system served as-is), so rebuild ≡ asset
  version bump + restart — documented honestly in the UI label.
- tailscale serve: exposes the local server on the tailnet via `tailscale serve`.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
import time

from . import config

log = logging.getLogger("hmgfu.system")

STARTED_AT = time.time()
TAILSCALE = r"C:\Program Files\Tailscale\tailscale.exe"


def _tailscale_bin() -> str:
    return TAILSCALE if os.path.exists(TAILSCALE) else "tailscale"


def _run(args: list, timeout: int = 20) -> dict:
    try:
        proc = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        return {"exit_code": proc.returncode, "stdout": proc.stdout[-3000:],
                "stderr": proc.stderr[-1500:]}
    except FileNotFoundError:
        return {"error": f"{args[0]} not found"}
    except subprocess.TimeoutExpired:
        return {"error": f"timed out after {timeout}s"}


def restart_server(delay_s: float = 0.6) -> dict:
    """Re-exec the current process after the HTTP response has flushed."""
    def _do():
        time.sleep(delay_s)
        log.info("restarting: exec %s %s", sys.executable, sys.argv)
        os.execv(sys.executable, [sys.executable, "-m", "hmgfu.api"])
    threading.Thread(target=_do, daemon=True).start()
    return {"ok": True, "message": "server restarting"}


def rebuild() -> dict:
    """No build step exists (no-build UI): bump the asset version marker and restart."""
    marker = os.path.join(os.path.dirname(config.DB_PATH), "web", ".asset_version")
    try:
        os.makedirs(os.path.dirname(marker), exist_ok=True)
        with open(marker, "w", encoding="utf-8") as f:
            f.write(str(int(time.time())))
    except OSError:
        pass
    result = restart_server()
    result["message"] = "assets version bumped; server restarting (UI has no build step)"
    return result


def tailscale_status() -> dict:
    binary = _tailscale_bin()
    status = _run([binary, "status", "--json"], timeout=10)
    serve = _run([binary, "serve", "status"], timeout=10)
    backend_state = "unknown"
    try:
        import json as _json
        backend_state = _json.loads(status.get("stdout") or "{}").get("BackendState", "unknown")
    except (ValueError, TypeError):
        pass
    serving = serve.get("exit_code") == 0 and bool((serve.get("stdout") or "").strip()) \
        and "No serve config" not in (serve.get("stdout") or "")
    url = None
    if serving:
        try:
            import json as _json
            dns = _json.loads(status.get("stdout") or "{}").get("Self", {}).get("DNSName", "")
            if dns:
                url = f"https://{dns.rstrip('.')}"
        except (ValueError, TypeError, AttributeError):
            pass
    return {"installed": "error" not in status or status.get("exit_code") is not None,
            # 'Running' = logged in + connected; NoState/NeedsLogin/Starting are not usable
            "running": backend_state == "Running",
            "backend_state": backend_state,
            "serving": serving,
            "url": url,
            "serve_status": (serve.get("stdout") or serve.get("error") or "")[:800]}


def tailscale_serve(action: str) -> dict:
    """action: 'on' → serve this API over the tailnet (https); 'off' → stop serving."""
    binary = _tailscale_bin()
    port = config.API_PORT
    if action == "on":
        result = _run([binary, "serve", "--bg", f"http://127.0.0.1:{port}"], timeout=30)
    elif action == "off":
        result = _run([binary, "serve", "reset"], timeout=30)
    else:
        return {"error": f"unknown action '{action}' (use on|off)"}
    result["ok"] = result.get("exit_code") == 0
    if result["ok"] and action == "on":
        result["url"] = tailscale_status().get("url")   # the shareable tailnet link
    return result


def git_branch(path: str) -> str | None:
    result = _run(["git", "-C", path, "rev-parse", "--abbrev-ref", "HEAD"], timeout=8)
    return result.get("stdout", "").strip() or None if result.get("exit_code") == 0 else None


def list_projects(root: str | None = None) -> list:
    """Depth-1 scan of the home dir for selectable working folders (git/npm/python)."""
    root = root or os.path.expanduser("~")
    projects = []
    try:
        entries = sorted(os.listdir(root))
    except OSError:
        return projects
    for name in entries:
        if name.startswith(".") or name.startswith("_"):
            continue
        path = os.path.join(root, name)
        if not os.path.isdir(path):
            continue
        markers = {
            "git": os.path.isdir(os.path.join(path, ".git")),
            "npm": os.path.isfile(os.path.join(path, "package.json")),
            "python": os.path.isfile(os.path.join(path, "pyproject.toml"))
                      or os.path.isdir(os.path.join(path, ".venv")),
        }
        if any(markers.values()):
            projects.append({"name": name, "path": path,
                             "kinds": [k for k, v in markers.items() if v],
                             "branch": git_branch(path) if markers["git"] else None})
    return projects


def workspace_info() -> dict:
    from .tool_builtins import get_workspace
    path = get_workspace()
    return {"path": path, "name": os.path.basename(path.rstrip("\\/")),
            "git_branch": git_branch(path)}


def system_status() -> dict:
    return {
        "uptime_s": round(time.time() - STARTED_AT, 1),
        "pid": os.getpid(),
        "python": sys.version.split()[0],
        "workspace": workspace_info(),
        "tailscale": tailscale_status(),
    }
