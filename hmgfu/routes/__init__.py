"""API route modules. Growth path: new endpoint group = new module here with an
APIRouter named `router`, then add it to ALL_ROUTERS — api.py needs no edits."""

from . import agent_ws, control, core, memory

ALL_ROUTERS = [core.router, memory.router, control.router, agent_ws.router]
