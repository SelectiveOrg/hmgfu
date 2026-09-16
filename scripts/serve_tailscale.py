"""Serve the hmg-fu API on the TAILNET interface only, for testing from another device.

The API has no authentication, so where it listens is the whole access-control story:

  * 127.0.0.1 (the default) is this machine only, and unreachable from a phone or laptop;
  * 0.0.0.0 would accept connections from EVERY interface -- café wifi, hotel LAN, anything the
    machine is attached to -- and hand a stranger the real memory with no credential at all;
  * the Tailscale address is reachable only by devices already authenticated to the tailnet, and by
    this machine itself, which is what "test it over Tailscale" actually needs.

So the address is resolved at start-up and NEVER hardcoded (launch.json is versioned, and a tailnet
address is machine-specific). If it cannot be resolved this refuses to start rather than falling back
to a wider bind: a silent fallback to 0.0.0.0 is exactly the kind of hidden exposure that should
never happen by accident.

    python scripts/serve_tailscale.py
"""
from __future__ import annotations

import os
import subprocess
import sys

CANDIDATES = ("tailscale", r"C:\Program Files\Tailscale\tailscale.exe",
              r"C:\Program Files (x86)\Tailscale\tailscale.exe", "/usr/bin/tailscale")


def tailnet_ip() -> str:
    for exe in CANDIDATES:
        try:
            out = subprocess.check_output([exe, "ip", "-4"], text=True, timeout=15).split()
        except (OSError, subprocess.SubprocessError):
            continue
        if out and out[0].startswith("100."):
            return out[0]
    raise SystemExit("REFUSING TO START: no Tailscale IPv4 address found. Bring Tailscale up first.\n"
                     "This deliberately does not fall back to 0.0.0.0 -- the API has no auth, and a "
                     "wider bind would expose the real memory to every network this machine is on.")


def main() -> int:
    ip = tailnet_ip()
    os.environ["HMGFU_API_HOST"] = ip
    port = os.environ.get("HMGFU_API_PORT", "8777")
    print(f"hmg-fu API on the tailnet only: http://{ip}:{port}", flush=True)
    print("Reachable from your other Tailscale devices and from this machine; not from the LAN.", flush=True)
    from hmgfu.api import main as serve
    serve()
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    raise SystemExit(main())
