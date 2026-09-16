"""Bench/probe isolation and evidence identity (Phase 31 → Phase 70 M0).

INCIDENT LESSONS: (Phase 31) throwaway dbs next to the live hmgfu.db were wiped by a cleanup wildcard → every
throwaway db lives in <root>/scratch/ (gitignored). (Phase 69) a live replay wrote a test fact into the REAL
ledger → `guard_scratch` refuses the production DB and the repo root before any engine is built, and every bench
result is written to an immutable, identified run directory (`write_versioned`) so a historical number can never
be mistaken for a current one.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from typing import Optional

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRATCH = os.path.join(_ROOT, "scratch")
RUNS = os.path.join(_ROOT, "outputs", "runs")


def throwaway_db(name: str) -> str:
    os.makedirs(SCRATCH, exist_ok=True)
    return os.path.join(SCRATCH, name)


class ProductionPathError(RuntimeError):
    pass


def guard_scratch(db_path: Optional[str], workspace: Optional[str] = None) -> None:
    """Refuse to build a mutable engine on the production database or with the repo root as workspace."""
    from hmgfu import config
    prod = os.path.realpath(str(config.DB_PATH))
    if db_path is None or os.path.realpath(str(db_path)) == prod:
        raise ProductionPathError(f"refusing to run a bench/probe on the production database {prod}")
    if workspace is not None:
        ws = os.path.realpath(str(workspace))
        if ws == os.path.realpath(_ROOT) or ws == os.path.dirname(prod):
            raise ProductionPathError(f"refusing to use {ws} as a bench workspace")
    for w in environment_warnings():                      # 72.6: never let the environment change a number silently
        print(f"ENVIRONMENT WARNING: {w}", file=sys.stderr)


def _git(*args: str) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=_ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def _ollama_digests() -> dict:
    try:
        import urllib.request
        from hmgfu import config
        raw = urllib.request.urlopen(config.OLLAMA_URL.rstrip("/") + "/api/tags", timeout=3).read()
        return {m.get("name"): (m.get("digest") or "")[:12] for m in json.loads(raw).get("models", [])}
    except Exception:
        return {}


def environment_warnings() -> list:
    """Environment facts that silently change a bench number (Phase 72.6 finding: the tool bench fell to 4/8 because
    the shell's `python` was the system interpreter without `cryptography`, so the credential vault could not be read
    and every search case failed honestly). Printed by `guard_scratch` and recorded in the manifest."""
    warnings = []
    try:
        import cryptography  # noqa: F401
    except Exception:
        warnings.append("cryptography not importable -> credential vault unreadable (web search will report 'not configured')")   # ASCII: cp1252 consoles
    venv = os.path.join(_ROOT, ".venv")
    if os.path.isdir(venv) and not os.path.abspath(sys.executable).lower().startswith(os.path.abspath(venv).lower()):
        warnings.append(f"interpreter {sys.executable} is not the project venv ({venv})")
    return warnings


def production_model_settings(db_path: Optional[str] = None) -> dict:
    """87 (Codex review 3): the model roles PRODUCTION runs — read from the LIVE settings table (read-only URI, never the
    config defaults, which the live DB may shadow: embed_model was bge-m3 in the DB while the default said nomic)."""
    import sqlite3
    from hmgfu import config as _cfg
    path = db_path or _cfg.DB_PATH
    out = {}
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        for key, val in con.execute("SELECT key, value FROM settings WHERE key IN ('embed_model','embed_provider','chat_model',"
                                    "'nano_model','router_model','nano_provider')").fetchall():
            try:
                out[key] = json.loads(val)
            except Exception:
                out[key] = val
        con.close()
    except Exception:
        pass
    return out


def settings_hash(settings) -> str:
    """81.3: a stable hash of the EFFECTIVE settings (a Settings object or a dict) — the configuration a number was made under."""
    import hashlib
    try:
        d = settings.all() if hasattr(settings, "all") else dict(settings or {})
        return hashlib.sha256(json.dumps(d, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:12]
    except Exception:
        return ""


def run_manifest(extra: Optional[dict] = None, settings=None) -> dict:
    """Everything a number needs to be reproducible: code (+ a hash of the dirty diff), models, the effective settings hash
    when the caller passes its engine's settings, runtime, host, time."""
    import hashlib
    settings_sha = settings_hash(settings) if settings is not None else ""
    dirty = bool(_git("status", "--porcelain"))
    diff_sha = hashlib.sha256((_git("diff", "HEAD") or "").encode("utf-8", "replace")).hexdigest()[:12] if dirty else ""
    man = {
        "commit": _git("rev-parse", "HEAD"), "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": dirty, "dirty_diff_sha": diff_sha,
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "python": sys.version.split()[0], "executable": sys.executable, "platform": platform.platform(), "host": platform.node(),
        "ollama_models": _ollama_digests(), "settings_sha": settings_sha,
        "environment_warnings": environment_warnings(),
    }
    if extra:
        man.update(extra)
    return man


def write_versioned(name: str, payload: dict, manifest: Optional[dict] = None, settings=None) -> str:
    """Write `payload` (+ manifest) under outputs/runs/<utc>-<sha7>-<uid>/<name>.json — exclusive, never overwritten (81.3)."""
    import uuid
    man = manifest or run_manifest(settings=settings)
    stamp = man["utc"].replace(":", "").replace("-", "")
    folder = os.path.join(RUNS, f"{stamp}-{(man.get('commit') or 'nogit')[:7]}-{uuid.uuid4().hex[:6]}")
    os.makedirs(folder, exist_ok=False)
    path = os.path.join(folder, f"{name}.json")
    with open(path, "x", encoding="utf-8") as f:
        json.dump({"manifest": man, **payload}, f, indent=1, ensure_ascii=False)
    with open(os.path.join(folder, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(man, f, indent=1, ensure_ascii=False)
    return path


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
