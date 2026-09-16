"""Google Workspace via the `gog` CLI (gogcli.sh) — PA3 pattern, ported (Phase 45).

Remote headless OAuth: set client credentials → step 1 returns an auth URL to open in the
browser → paste the redirect URL back → step 2 completes. Then Gmail / Calendar / Tasks work.
Every tool degrades gracefully (honest error) when `gog` is not installed. The LLM recalls
these by user intent because create_skill/sync makes them HMG points.
"""

from __future__ import annotations

import json
import shutil
import subprocess

TOOLS = [
    {"name": "gog_status", "description": "Show gog version, installed status, authorized Google accounts and stored OAuth client credentials.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "gog_auth_credentials", "description": "Store Google OAuth client credentials (paste the client_secret.json contents or a path) so gog can log in.",
     "parameters": {"type": "object", "properties": {"client_secret": {"type": "string", "description": "client_secret.json JSON blob or file path"}}, "required": ["client_secret"]}},
    {"name": "gog_login_start", "description": "Start Google login (remote OAuth). Returns an auth URL — open it in your browser, approve, then call gog_login_finish with the redirected URL.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "gog_login_finish", "description": "Finish Google login by pasting the full redirect URL the browser landed on after approving.",
     "parameters": {"type": "object", "properties": {"redirect_url": {"type": "string"}}, "required": ["redirect_url"]}},
    {"name": "gog_gmail_search", "description": "Search Gmail threads/messages by query (e.g. 'from:boss is:unread').",
     "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "account": {"type": "string", "description": "optional Google account email"}}, "required": ["query"]}},
    {"name": "gog_gmail_send", "description": "Send an email from a logged-in Google account.",
     "parameters": {"type": "object", "properties": {"to": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"}, "account": {"type": "string"}}, "required": ["to", "subject", "body"]}},
    {"name": "gog_calendar_events", "description": "List upcoming Google Calendar events.",
     "parameters": {"type": "object", "properties": {"days": {"type": "integer", "description": "window in days (default 7)"}, "account": {"type": "string"}}}},
]


def _run(args, stdin_text=None, timeout=60):
    if shutil.which("gog") is None:
        return {"error": "gog is not installed. Install the Google Workspace CLI from https://gogcli.sh, "
                         "then set OAuth client credentials with gog_auth_credentials and log in with gog_login_start."}
    try:
        proc = subprocess.run(["gog", *args], input=stdin_text, capture_output=True,
                              text=True, timeout=timeout)
        out = (proc.stdout or "").strip()
        if proc.returncode != 0:
            return {"error": (proc.stderr or out or f"gog exited {proc.returncode}")[:1500]}
        return {"output": out[:6000]}
    except subprocess.TimeoutExpired:
        return {"error": "gog timed out"}
    except Exception as exc:                                   # noqa: BLE001 (fail-soft)
        return {"error": f"{type(exc).__name__}: {exc}"}


def _acct(args, account):
    return [*args, "--account", account] if account else args


def execute(name, arguments):
    a = arguments or {}
    if name == "gog_status":
        parts = {"version": _run(["--version"]), "auth": _run(["auth", "status"]),
                 "accounts": _run(["auth", "list"])}
        return json.dumps(parts)
    if name == "gog_auth_credentials":
        return json.dumps(_run(["auth", "credentials", "set", str(a.get("client_secret", ""))]))
    if name == "gog_login_start":
        r = _run(["auth", "add", "--remote", "--step", "1"])
        if "output" in r:
            r["hint"] = "Open the URL above in your browser, approve, then call gog_login_finish with the redirected URL."
        return json.dumps(r)
    if name == "gog_login_finish":
        return json.dumps(_run(["auth", "add", "--remote", "--step", "2", str(a.get("redirect_url", ""))]))
    if name == "gog_gmail_search":
        return json.dumps(_run(_acct(["gmail", "search", str(a.get("query", ""))], a.get("account"))))
    if name == "gog_gmail_send":
        return json.dumps(_run(_acct(
            ["gmail", "send", "--to", str(a.get("to", "")), "--subject", str(a.get("subject", "")),
             "--body", str(a.get("body", ""))], a.get("account"))))
    if name == "gog_calendar_events":
        return json.dumps(_run(_acct(["calendar", "events", "--days", str(int(a.get("days") or 7))], a.get("account"))))
    return json.dumps({"error": f"unknown gog tool: {name}"})
