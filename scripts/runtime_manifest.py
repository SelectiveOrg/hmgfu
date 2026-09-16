"""Phase 91.S0 — record what is ACTUALLY loaded and configured, instead of inferring it.

The audit's objection is exact: being hundreds of commits ahead of `main` says nothing about the code a running
process executes, and a README naming an embedder is not evidence that the embedder is in use. This reads the state
from the objects themselves — the module file the interpreter imported, the effective settings row, the model names
the engine would call, and the database path it resolves — and writes a versioned manifest.

    python scripts/runtime_manifest.py            # this checkout
    python scripts/runtime_manifest.py --probe    # also ask Ollama which models are loaded (one HTTP call, no GPU work)
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts")); sys.path.insert(0, ROOT)
from _bench_paths import write_versioned  # noqa: E402


def _git(*args) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception as exc:
        return f"(unavailable: {exc})"


def _ollama(path: str):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:11434/api/{path}", timeout=8) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as exc:
        return {"error": str(exc)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true", help="also ask the local Ollama what is loaded")
    args = ap.parse_args()

    import hmgfu
    from hmgfu import config
    from hmgfu.settings import DEFAULTS, Settings

    m = {
        "checkout": {"root": ROOT, "head": _git("rev-parse", "HEAD"), "head_short": _git("rev-parse", "--short", "HEAD"),
                     "branch": _git("rev-parse", "--abbrev-ref", "HEAD"), "dirty": bool(_git("status", "--porcelain")),
                     "describe": _git("describe", "--always", "--dirty")},
        "package": {"imported_from": os.path.dirname(os.path.abspath(hmgfu.__file__)),
                    "is_this_checkout": os.path.dirname(os.path.abspath(hmgfu.__file__)) == os.path.join(ROOT, "hmgfu")},
        "interpreter": {"executable": sys.executable, "version": sys.version.split()[0], "platform": platform.platform()},
        "database": {"config_db_path": config.DB_PATH, "exists": os.path.exists(config.DB_PATH),
                     "size_bytes": os.path.getsize(config.DB_PATH) if os.path.exists(config.DB_PATH) else None},
        "models_from_config": {"nano": getattr(config, "NANO_MODEL", None), "chat": getattr(config, "CHAT_MODEL", None),
                               "embed": getattr(config, "EMBED_MODEL", None)},
    }
    try:                                     # the EFFECTIVE settings, not the defaults, and the overrides made explicit
        st = Settings(config.DB_PATH)
        eff = st.all()
        m["settings_effective"] = eff
        m["settings_overridden"] = {k: {"default": DEFAULTS[k], "effective": eff[k]}
                                    for k in DEFAULTS if k in eff and eff[k] != DEFAULTS[k]}
    except Exception as exc:
        m["settings_effective"] = {"error": str(exc)}
    if args.probe:
        m["ollama"] = {"version": _ollama("version"), "loaded_now": _ollama("ps")}
    m["listening_8777"] = _git("--version") and _port_open(8777)
    print(json.dumps({k: v for k, v in m.items() if k != "settings_effective"}, indent=1, ensure_ascii=False)[:2600])
    print("\nsettings overridden vs defaults:", json.dumps(m.get("settings_overridden", {}), ensure_ascii=False))
    print("versioned:", write_versioned("runtime_manifest", m))
    return 0


def _port_open(port: int) -> bool:
    import socket
    with socket.socket() as s:
        s.settimeout(0.6)
        try:
            s.connect(("127.0.0.1", port)); return True
        except OSError:
            return False


if __name__ == "__main__":
    raise SystemExit(main())
