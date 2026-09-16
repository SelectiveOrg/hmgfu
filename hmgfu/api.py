"""FastAPI app assembly. All endpoints live in hmgfu/routes/* (Phase 18 modular split).

Run: python -m hmgfu.api  (serves http://127.0.0.1:8777)
Growth path: add a module with an APIRouter to hmgfu/routes/ and list it in
routes.ALL_ROUTERS — this file should not need to change.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import config, runtime
from .agent import AgentEngine
from .routes import ALL_ROUTERS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("hmgfu.api")

WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")

engine: AgentEngine = None   # kept for backward compatibility; runtime.get_engine() is canonical


@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine
    engine = AgentEngine()
    runtime.set_engine(engine)
    log.info("HMG-Fu agent engine up — %s", engine.graph.stats())
    from .prospective_alarm import start_ticker, stop_ticker
    start_ticker(engine)                                   # 77.6: due reminders fire without a turn
    yield
    stop_ticker(engine)
    engine.graph.close()
    engine.client.close()


app = FastAPI(title="HMG-Fu", version="0.3.0", lifespan=lifespan)

for router in ALL_ROUTERS:
    app.include_router(router)

# static assets for the Cowork UI (design system, vendor UMDs, app JSX)
for mount in ("ds", "vendor", "app"):
    path = os.path.join(WEB_DIR, mount)
    if os.path.isdir(path):
        app.mount(f"/{mount}", StaticFiles(directory=path), name=mount)


def main():
    import uvicorn
    uvicorn.run(app, host=config.API_HOST, port=config.API_PORT)


if __name__ == "__main__":
    main()
