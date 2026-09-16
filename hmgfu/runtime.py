"""Process-wide runtime holder: the one AgentEngine instance shared by all routers.

Routers call get_engine() per request instead of importing a module-level global,
which keeps route modules import-safe before the app has started (tests, tooling).
"""

from __future__ import annotations

from typing import Optional

_engine = None


def set_engine(engine) -> None:
    global _engine
    _engine = engine


def get_engine():
    if _engine is None:
        raise RuntimeError("engine not initialised — app lifespan has not run")
    return _engine
