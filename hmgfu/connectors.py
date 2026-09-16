"""Connectors — ONE global connection per provider (PA3 ApiConnectorCard model).

A provider is the connectable unit. Its `services` are the scopes that ONE connection grants
(e.g. Google → Gmail + Calendar + Drive on a single credential) — they are NOT connected
individually. Auth methods:
- api_key: works when its env vars (or a vault secret) are present.
- cli:     works when its binary is on PATH.
- mcp:     one MCP stdio server; /connect spawns it and registers its tools (mcp_client.py).
- oauth:   needs the OAuth broker (deferred, docs/PA3_PARITY.md #7) — shown, connect explains.

Custom providers persist in SQLite. Secrets ONLY in the Fernet vault (Rule 14). Status never
contains secret values.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import sqlite3
from typing import Dict, List, Optional

from . import config

log = logging.getLogger("hmgfu.connectors")

# One entry per PROVIDER. `services` = human scope labels the single connection grants.
PROVIDERS: Dict[str, dict] = {
    # Google via the `gog` Workspace CLI (PA3 pattern) — remote-OAuth login, not MCP. Usable
    # once `gog` is on PATH; the LLM drives auth + access through the gog skill (skills/gog.py).
    "google": {"display": "Google", "category": "productivity", "auth": "cli",
               "services": ["Gmail", "Calendar", "Tasks", "Drive"],
               "config": {"cli": "gog", "hint": "install from gogcli.sh, then use the gog_* tools to log in"}},
    "meta": {"display": "Meta", "category": "social", "auth": "api_key",
             "services": ["WhatsApp", "Instagram", "Messenger"],
             "config": {"env": ["META_ACCESS_TOKEN"]}},
    "github": {"display": "GitHub", "category": "dev", "auth": "api_key",
               "services": ["Repos", "Issues", "Pull requests", "Actions"],
               "config": {"env": ["GITHUB_TOKEN"], "cli": "gh"}},
    "slack": {"display": "Slack", "category": "chat", "auth": "api_key",
              "services": ["Messages", "Channels"], "config": {"env": ["SLACK_BOT_TOKEN"]}},
    "notion": {"display": "Notion", "category": "notes", "auth": "api_key",
               "services": ["Pages", "Databases"], "config": {"env": ["NOTION_API_KEY"]}},
    "openai": {"display": "OpenAI", "category": "llm", "auth": "api_key",
               "services": ["Chat", "Embeddings"], "config": {"env": ["OPENAI_API_KEY"]}},
    "anthropic": {"display": "Anthropic", "category": "llm", "auth": "api_key",
                  "services": ["Claude"], "config": {"env": ["ANTHROPIC_API_KEY"]}},
    "brave": {"display": "Brave Search", "category": "search", "auth": "api_key",
              "services": ["Web search"], "config": {"env": ["BRAVE_API_KEY"]}},
    "filesystem": {"display": "Filesystem", "category": "files", "auth": "mcp",
                   "services": ["Read", "Write", "List"],
                   "config": {"command": ["npx", "-y", "@modelcontextprotocol/server-filesystem", "."]}},
    "tailscale": {"display": "Tailscale", "category": "network", "auth": "cli",
                  "services": ["Serve", "Status"], "config": {"cli": "tailscale"}},
}

VALID_AUTH = ("api_key", "cli", "mcp", "oauth")


def google_connect(engine, redirect_url: Optional[str] = None) -> dict:
    """Drive the existing gog skill's two-step remote OAuth flow for the Connect UI."""
    name = "gog_login_finish" if redirect_url else "gog_login_start"
    args = {"redirect_url": redirect_url} if redirect_url else {}
    try:
        payload = json.loads(engine.tools.execute_tool(name, args))
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        return {"ok": False, "error": f"invalid gog response: {exc}"}
    if payload.get("error"):
        return {"ok": False, "error": payload["error"]}
    output = str(payload.get("output", ""))
    if redirect_url:
        return {"ok": True, "stage": "complete", "output": output}
    match = re.search(r"https://[^\s<>\"]+", output)
    if not match:
        return {"ok": False, "error": output or "gog did not return an authorization URL"}
    return {"ok": True, "stage": "authorize", "auth_url": match.group(0), "output": output}


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    conn.execute("CREATE TABLE IF NOT EXISTS custom_connectors ("
                 "name TEXT PRIMARY KEY, display TEXT, auth TEXT, category TEXT, "
                 "services TEXT, config TEXT, created_at TEXT)")
    # migrate the Phase-20 schema (kind/no-services) → provider schema (auth/services)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(custom_connectors)")]
    if "auth" not in cols:
        conn.execute("DROP TABLE custom_connectors")   # only held old per-service customs
        conn.execute("CREATE TABLE custom_connectors ("
                     "name TEXT PRIMARY KEY, display TEXT, auth TEXT, category TEXT, "
                     "services TEXT, config TEXT, created_at TEXT)")
        log.info("migrated custom_connectors → provider schema")
    conn.commit()
    return conn


def add_provider(name: str, display: str, auth: str, config_dict: dict,
                 category: str = "custom", services: Optional[list] = None) -> dict:
    name = name.strip().lower().replace(" ", "_")
    if not name:
        return {"error": "empty name"}
    if auth not in VALID_AUTH:
        return {"error": f"auth must be one of {VALID_AUTH}"}
    if name in PROVIDERS:
        return {"error": f"'{name}' is a built-in provider"}
    if auth == "mcp" and not (isinstance(config_dict.get("command"), list) and config_dict["command"]):
        return {"error": "mcp provider needs config.command (argv list)"}
    if auth == "cli" and not config_dict.get("cli"):
        return {"error": "cli provider needs config.cli (binary)"}
    if auth == "api_key" and not (isinstance(config_dict.get("env"), list) and config_dict["env"]):
        return {"error": "api_key provider needs config.env (list of variable names)"}
    conn = _db()
    conn.execute("INSERT OR REPLACE INTO custom_connectors VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
                 (name, display or name, auth, category,
                  json.dumps(services or []), json.dumps(config_dict)))
    conn.commit()
    conn.close()
    return {"ok": True, "name": name}


def remove_provider(name: str) -> dict:
    if name in PROVIDERS:
        return {"error": "cannot remove a built-in provider"}
    conn = _db()
    conn.execute("DELETE FROM custom_connectors WHERE name=?", (name,))
    conn.commit()
    conn.close()
    return {"ok": True}


def all_providers() -> Dict[str, dict]:
    out = {name: {**spec, "builtin": True} for name, spec in PROVIDERS.items()}
    conn = _db()
    for name, display, auth, category, services, cfg in conn.execute(
            "SELECT name, display, auth, category, services, config FROM custom_connectors"):
        def _load(s):
            try:
                return json.loads(s or "[]")
            except (json.JSONDecodeError, ValueError):
                return []
        out[name] = {"display": display, "auth": auth, "category": category,
                     "services": _load(services), "config": _load(cfg) if cfg else {},
                     "builtin": False}
    conn.close()
    return out


def _configured(name: str, spec: dict, stored: set, unreadable: Optional[set] = None) -> tuple:
    """(configured, source) — never touches secret values. One flag for the whole provider.
    95.76: `stored` holds only the credentials that DECRYPT here. A row carried in with a database but
    without its vault key is reported unreadable, not connected: the panel showed a green badge while
    the tool answered "no API key", and the badge hid the one control that could fix it."""
    auth = spec["auth"]
    cfg = spec.get("config", {})
    if name in stored:
        return True, "vault"
    if name in (unreadable or set()):
        return False, "unreadable"
    if auth == "api_key" and cfg.get("env") and all(os.environ.get(k) for k in cfg["env"]):
        return True, "env"
    if auth == "cli" and shutil.which(cfg.get("cli", "")):
        return True, "path"
    if auth == "mcp" and cfg.get("command"):
        return True, "command"     # runnable; 'connected' reflects a live MCP session
    return False, None


def connector_status(connected_mcp: Optional[set] = None) -> List[dict]:
    """One row per provider; services listed inside; single connection flag."""
    vault = CredentialVault()
    present = set(vault.kinds())
    stored = {k for k in present if vault.get(k)}      # 95.76: readable is the only kind that counts
    unreadable = present - stored
    out = []
    for name, spec in all_providers().items():
        configured, source = _configured(name, spec, stored, unreadable)
        out.append({
            "kind": name, "display": spec["display"], "category": spec.get("category", ""),
            "auth": spec["auth"], "services": spec.get("services", []),
            "builtin": spec.get("builtin", False),
            "configured": configured, "source": source,
            "connected": name in (connected_mcp or set()),
        })
    return out


def _fernet():
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        return None
    key_path = os.path.join(os.path.dirname(config.DB_PATH), ".vault_key")
    if not os.path.exists(key_path):
        with open(key_path, "wb") as f:
            f.write(Fernet.generate_key())
    with open(key_path, "rb") as f:
        return Fernet(f.read())


class CredentialVault:
    def __init__(self, db_path: Optional[str] = None):
        self._db = sqlite3.connect(db_path or config.DB_PATH, check_same_thread=False)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS credentials (kind TEXT PRIMARY KEY, blob BLOB, created_at TEXT)"
        )
        self._db.commit()
        self._fernet = _fernet()

    def put(self, kind: str, secret: dict) -> bool:
        if self._fernet is None:
            log.warning("vault write refused: cryptography not installed")
            return False
        blob = self._fernet.encrypt(json.dumps(secret).encode())
        self._db.execute("INSERT OR REPLACE INTO credentials VALUES (?, ?, datetime('now'))",
                         (kind, blob))
        self._db.commit()
        return True

    def get(self, kind: str) -> Optional[dict]:
        if self._fernet is None:
            return None
        row = self._db.execute("SELECT blob FROM credentials WHERE kind=?", (kind,)).fetchone()
        if row is None:
            return None
        try:
            return json.loads(self._fernet.decrypt(row[0]))
        except Exception:
            return None

    def kinds(self) -> List[str]:
        return [r[0] for r in self._db.execute("SELECT kind FROM credentials")]
