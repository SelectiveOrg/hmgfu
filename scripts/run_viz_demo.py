"""Run the hmg-fu API against the seeded viz-demo DB with the Regulator + chat-correction flags ON,
on port 8778 (production 8777 untouched). For preview/screenshots of the live honest hex viz."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("HMGFU_DB_PATH", str(ROOT / "scratch" / "hmgfu_viz_demo.db"))
os.environ.setdefault("HMGFU_REGULATOR_ENABLED", "1")
os.environ.setdefault("HMGFU_CHAT_CORRECTION_SIGNAL", "1")
os.environ.setdefault("HMGFU_OBSERVE_FIRST_N", "50")
os.environ.setdefault("HMGFU_API_PORT", "8778")

from hmgfu.api import main   # noqa: E402  (imports config AFTER the env is set → picks up 8778 + flags)

if __name__ == "__main__":
    main()
