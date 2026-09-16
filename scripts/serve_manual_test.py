"""Serve an ISOLATED instance of the current candidate for manual testing, on loopback only.

Sibling of `serve_tailscale.py`, and it exists for the same reason: the API has no authentication, so
what it binds to and what base it opens are the whole of the safety story. This one is narrower — it
never leaves this machine, and it never opens the real memory.

Three guarantees, each a refusal rather than a fallback:

  * **loopback only.** 127.0.0.1, never 0.0.0.0 and never the tailnet.
  * **a disposable synthetic base** under `scratch/` (gitignored), created empty. The real memory is
    refused by name, and so is any path outside `scratch/`.
  * **confirm, never adapt.** Written to THAT BASE'S settings row and read back before serving.
    `HMGFU_INTERACTIVE_LEARNING_MODE` alone does NOT do this: `config` would say `confirm` while
    `Settings` — which is what `run_learning_turn` actually reads — still said `off`, because the
    settings defaults are literals and the documented env precedence covers only the regulator keys.

**Why the import order below is load-bearing, and is asserted rather than assumed.** `hmgfu.config`
resolves every `HMGFU_*` variable at IMPORT time and caches it. An earlier version of this script set
the environment inside a helper that had already imported `hmgfu.settings`, so config had cached
`DB_PATH=hmgfu.db` and `API_PORT=8777` before being told otherwise — and the "isolated" instance
opened the **production memory** on the **production port**. The startup provenance repair then wrote
to it. Nothing warned, because setting an environment variable always succeeds.

So: every variable is set before ANY hmgfu import, and then `config` is read back and compared with
what was intended. If they disagree the process refuses. A guarantee that is only a comment is not a
guarantee.

    python scripts/serve_manual_test.py                 # 127.0.0.1:8781, scratch/manual_test.db
    HMGFU_MANUAL_PORT=8782 python scripts/serve_manual_test.py
    HMGFU_MANUAL_DB=scratch/my_probe.db python scripts/serve_manual_test.py

Re-running with the same base KEEPS what you taught it: that is how a second conversation, or a later
session, tests recall across sessions. Delete the file to start clean.
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRATCH = os.path.join(ROOT, "scratch")
REAL_MEMORY = os.path.join(ROOT, "hmgfu.db")
DEFAULT_DB = os.path.join(SCRATCH, "manual_test.db")
DEFAULT_PORT = "8781"              # not 8777: production's port stays free even if it is restarted
HOST = "127.0.0.1"


def _commit() -> str:
    try:
        out = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
        mine = [ln for ln in dirty.splitlines() if not ln.strip().endswith(".claude/launch.json")]
        return out + ("   (working tree has uncommitted changes)" if mine else "")
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def resolve_base() -> str:
    """The disposable base, or a refusal. Pure path work: imports nothing from hmgfu."""
    raw = os.environ.get("HMGFU_MANUAL_DB") or DEFAULT_DB
    path = os.path.abspath(os.path.join(ROOT, raw))
    if path == os.path.abspath(REAL_MEMORY):
        raise SystemExit("REFUSING TO START: that is the REAL memory. This script exists to keep a "
                         "manual test off it; point HMGFU_MANUAL_DB at a file under scratch/.")
    if os.path.commonpath([path, SCRATCH]) != SCRATCH:
        raise SystemExit(f"REFUSING TO START: {path} is outside scratch/. A manual-test base must be "
                         "disposable and gitignored, so it lives there and nowhere else.")
    os.makedirs(SCRATCH, exist_ok=True)
    if not os.path.exists(path):
        sqlite3.connect(path).close()          # empty; the engine migrates its own schema
    return path


def verify_config(base: str, port: str) -> None:
    """Read back what `config` actually resolved, and refuse if it is not what we asked for.

    This is the check whose absence let an earlier version serve production. It must run after the
    FIRST hmgfu import and before anything opens a database."""
    from hmgfu import config
    problems = []
    if os.path.abspath(config.DB_PATH) != os.path.abspath(base):
        problems.append(f"base is {config.DB_PATH!r}, expected {base!r}")
    if str(config.API_PORT) != str(port):
        problems.append(f"port is {config.API_PORT!r}, expected {port!r}")
    if str(config.API_HOST) != HOST:
        problems.append(f"host is {config.API_HOST!r}, expected {HOST!r}")
    if os.path.abspath(config.DB_PATH) == os.path.abspath(REAL_MEMORY):
        problems.append("it resolved to the REAL MEMORY")
    if problems:
        raise SystemExit("REFUSING TO START: the environment did not reach hmgfu.config — "
                         + "; ".join(problems) + ".\nconfig caches HMGFU_* at import time, so every "
                         "variable must be set before the first hmgfu import.")


# The models the candidate was actually MEASURED with. A fresh base takes config's defaults, and
# config defaults the embedder to nomic-embed-text while every run behind the 93.V gate used bge-m3 --
# so an unaligned base would have you testing a different retrieval surface than the one that was
# validated. Declared here rather than copied out of the production base, which this never opens.
CANDIDATE_MODELS = {"embed_model": "bge-m3"}


def set_confirm(base: str) -> str:
    """Write the learning mode into THIS base and read it back. Returns what it actually reads."""
    from hmgfu.settings import Settings
    settings = Settings(base)
    for key, value in CANDIDATE_MODELS.items():
        settings.set(key, value)
    settings.set("interactive_learning_mode", "confirm")
    mode = str(settings.get("interactive_learning_mode"))
    if mode != "confirm":
        raise SystemExit(f"REFUSING TO START: the base reads interactive_learning_mode={mode!r} after "
                         "being set to 'confirm'. Serving it would mean testing something other than "
                         "what you were told you are testing.")
    return mode


def main() -> int:
    if str(os.environ.get("HMGFU_INTERACTIVE_LEARNING_MODE", "")).lower() == "adapt":
        raise SystemExit("REFUSING TO START: adapt is not authorised. This serves confirm only.")

    base = resolve_base()                       # no hmgfu import has happened yet
    port = os.environ.get("HMGFU_MANUAL_PORT", DEFAULT_PORT)
    os.environ["HMGFU_DB_PATH"] = base          # ... so these are still in time
    os.environ["HMGFU_API_HOST"] = HOST
    os.environ["HMGFU_API_PORT"] = port

    verify_config(base, port)                   # the first hmgfu import, and the proof it took effect
    mode = set_confirm(base)

    print("=" * 74, flush=True)
    print(f"  address   http://{HOST}:{port}        (this machine only)", flush=True)
    print(f"  commit    {_commit()}", flush=True)
    print(f"  base      {base}", flush=True)
    print(f"  learning  {mode}   (adapt refused; the real memory is not opened)", flush=True)
    print("=" * 74, flush=True)
    print("Open the address in a browser. Ctrl+C stops THIS process and nothing else.", flush=True)

    from hmgfu.api import main as serve
    serve()
    return 0


if __name__ == "__main__":
    sys.path.insert(0, ROOT)
    raise SystemExit(main())
