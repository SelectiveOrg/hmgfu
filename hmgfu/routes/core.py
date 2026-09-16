"""Core v1 surface: UI pages, health, plain chat, ingest, retrieve, graph, dream."""

from __future__ import annotations

import os
import re

import anyio
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, HTMLResponse
from pydantic import BaseModel

from .. import config
from ..retrieve import build_llm_context
from ..providers import model_for_role
from ..runtime import get_engine

router = APIRouter()

WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "web")


class ChatIn(BaseModel):
    message: str
    explicit: bool = False


class IngestIn(BaseModel):
    content: str
    source: str = "user"
    type: str | None = None


@router.get("/")
async def index():
    # L-01: rewrite every `?v=` asset marker to the value written by rebuild() so a rebuild
    # ACTUALLY busts caches. The marker was previously written but never read by anything.
    path = os.path.join(WEB_DIR, "index.html")
    marker = os.path.join(WEB_DIR, ".asset_version")
    try:
        version = open(marker, encoding="utf-8").read().strip()
    except OSError:
        version = ""
    if not version:
        return FileResponse(path)
    try:
        html = open(path, encoding="utf-8").read()
    except OSError:
        return FileResponse(path)
    return HTMLResponse(re.sub(r"\?v=\d+", f"?v={version}", html))


@router.get("/debug")
async def debug_ui():
    """The original v1 hex-debug UI, preserved (Rule 11)."""
    return FileResponse(os.path.join(WEB_DIR, "debug.html"))


@router.get("/workspace-file")
async def workspace_file(path: str):
    """Serve a file from the active workspace so an 'app' widget can iframe a built app.
    Confined to the workspace dir (Rule 14: no path traversal outside it)."""
    from ..tool_builtins import get_workspace
    ws = os.path.abspath(get_workspace())
    full = os.path.abspath(os.path.join(ws, path))
    if not full.startswith(ws + os.sep) and full != ws:
        raise HTTPException(403, "outside workspace")
    if not os.path.isfile(full):
        raise HTTPException(404, "not found")
    if full.lower().endswith((".html", ".htm")):
        # 95.75 (P6): the page carries its own reporter, installed before its scripts run. Only the
        # RESPONSE is instrumented — the file on disk is untouched, so the receipt hash still matches.
        from ..app_errors import instrument_html
        try:
            with open(full, "r", encoding="utf-8") as fh:
                return HTMLResponse(instrument_html(fh.read()))
        except (OSError, UnicodeDecodeError):
            return FileResponse(full)
    return FileResponse(full)


class AppErrorsIn(BaseModel):
    file: str
    errors: list = []


@router.post("/api/app-errors")
async def app_errors_report(body: AppErrorsIn):
    """The running page reports a fault. Keyed by FILE, which is what the app widget points at."""
    from ..app_errors import store_for
    store = store_for(get_engine())
    if store is None:
        return {"ok": False, "recorded": 0}
    return {"ok": True, "recorded": store.record(body.file, body.errors[:20])}


@router.get("/api/app-errors")
async def app_errors_list(file: str = "", session_id: str = ""):
    engine = get_engine()
    from ..app_errors import session_app_files, store_for
    store = store_for(engine)
    if store is None:
        return {"errors": []}
    files = [file] if file else session_app_files(engine, session_id)
    return {"errors": store.recent(files), "files": files}


@router.get("/api/health")
async def health():
    engine = get_engine()
    return {
        "ok": True,
        "ollama": engine.client.available(),
        # 95.77: the models a TURN would use (the chosen ones), not the compiled-in defaults.
        # The three original keys stay; "router" joins them because 73.2 made it a role of its own.
        "models": {role: model_for_role(engine, role) for role in ("chat", "router", "nano", "embed")},
        "stats": engine.graph.stats(),
    }


@router.post("/api/chat")
async def chat(body: ChatIn):
    """Plain memory cycle (no tools) — kept for compatibility; the UI uses /ws."""
    engine = get_engine()
    if not body.message.strip():
        raise HTTPException(400, "empty message")
    return await anyio.to_thread.run_sync(lambda: engine.chat(body.message, body.explicit))


# M-14: a public client may only ingest as the user — never spoof assistant/system/dream
# source-trust — and only into a real memory type.
_PUBLIC_INGEST_SOURCES = {"user", "user_explicit"}


@router.post("/api/ingest")
async def ingest(body: IngestIn):
    engine = get_engine()
    if not body.content.strip():
        raise HTTPException(400, "empty content")
    if body.source not in _PUBLIC_INGEST_SOURCES:
        raise HTTPException(400, f"source must be one of {sorted(_PUBLIC_INGEST_SOURCES)}")
    if body.type is not None and body.type not in config.MEMORY_TYPES:
        raise HTTPException(400, f"type must be one of {config.MEMORY_TYPES}")
    point = await anyio.to_thread.run_sync(
        lambda: engine.ingest(body.content, body.source, body.type)
    )
    return {"point": point.public(), "stats": engine.graph.stats()}


@router.get("/api/retrieve")
async def retrieve(q: str):
    engine = get_engine()
    if not q.strip():
        raise HTTPException(400, "empty query")
    def run():
        query, retrieved, elapsed_ms = engine.retrieve(q)
        context, _ = build_llm_context(query, engine.graph, retrieved=retrieved,
                                       excerpt_chars=engine.settings.get("excerpt_max_chars"))   # 78.2
        return {
            "query": {"text": q, "entities": query.entities, "topics": query.topics,
                      "intent": query.intent},
            "retrieved": [r.public() for r in retrieved],
            "injected_context": context,
            "retrieval_ms": round(elapsed_ms, 1),
        }
    return await anyio.to_thread.run_sync(run)


@router.get("/api/graph")
async def graph():
    g = get_engine().graph
    return {
        "points": [p.public() for p in g.points.values()],
        "edges": [e.public() for e in g.edges.values()],
        "stats": g.stats(),
    }


def _dream_detail(engine, report) -> dict:
    """Resolve a dream report's id-lists into human labels for the dream widget: macros →
    titles, wormholes → the two endpoint labels. (contradictions are edge-tensions, not points,
    so only their count is meaningful.)"""
    g = engine.graph
    macros = [{"id": mid, "title": (g.points[mid].title or g.points[mid].summary or "")[:60]}
              for mid in report.macros_created if mid in g.points]
    wormholes = []
    for eid in report.wormholes_created:
        e = g.edges.get(eid)
        if e is None:
            continue
        a, b = g.points.get(e.from_id), g.points.get(e.to_id)
        wormholes.append({"id": eid,
                          "from": (a.title or a.summary or "")[:40] if a else e.from_id,
                          "to": (b.title or b.summary or "")[:40] if b else e.to_id})
    return {"macros": macros, "wormholes": wormholes,
            "contradictions": len(report.contradictions_found),
            "decayed": len(report.memories_decayed),
            "promoted": len(report.memories_promoted)}


@router.post("/api/dream")
async def dream():
    engine = get_engine()
    report = await anyio.to_thread.run_sync(engine.dream)
    return {"report": report.public(), "detail": _dream_detail(engine, report),
            "stats": engine.graph.stats()}


@router.get("/api/reports")
async def reports():
    return {"reports": [r.public() for r in get_engine().graph.dream_reports()]}
