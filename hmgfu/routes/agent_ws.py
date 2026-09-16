"""Agentic surface: tool-enabled REST chat + the /ws live turn stream."""

from __future__ import annotations

import asyncio
import json
import logging
import queue as queue_mod

import anyio
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from ..runtime import get_engine

log = logging.getLogger("hmgfu.routes.agent")

router = APIRouter()


class ChatIn(BaseModel):
    message: str
    explicit: bool = False
    session_id: str | None = None


@router.post("/api/agent/chat")
async def agent_chat(body: ChatIn):
    """Tool-enabled chat: full agentic cycle incl. tool trace + grade card."""
    engine = get_engine()
    if not body.message.strip():
        raise HTTPException(400, "empty message")
    return await anyio.to_thread.run_sync(
        lambda: engine.agent_chat(body.message, body.explicit, session_id=body.session_id)
    )


@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    """One agent turn at a time per connection; events stream as they happen."""
    await ws.accept()
    engine = get_engine()
    loop = asyncio.get_event_loop()
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                await ws.send_json({"type": "error", "message": "invalid JSON"})
                continue
            if msg.get("type") == "ping":
                await ws.send_json({"type": "pong"})
                continue
            if msg.get("type") != "chat":
                await ws.send_json({"type": "error", "message": f"unknown type {msg.get('type')}"})
                continue
            text = str(msg.get("text") or msg.get("message") or "").strip()
            session_id = msg.get("session_id")
            if not text:
                await ws.send_json({"type": "error", "message": "empty message"})
                continue
            events: queue_mod.Queue = queue_mod.Queue()
            done_sentinel = object()
            result_box: dict = {}

            def run_turn():
                try:
                    result_box["result"] = engine.agent_chat(
                        text, session_id=session_id, emit=lambda ev: events.put(ev))
                except Exception as exc:
                    log.exception("agent turn failed")
                    events.put({"type": "error", "message": str(exc)[:400]})
                finally:
                    from ..turn_tail import wait_for_tail
                    wait_for_tail(engine)            # 73.4: late grade/timings events still flow to THIS socket turn
                    events.put(done_sentinel)

            task = loop.run_in_executor(None, run_turn)
            saw_done = False
            while True:
                event = await anyio.to_thread.run_sync(events.get)
                if event is done_sentinel:
                    break
                if isinstance(event, dict) and event.get("type") == "done":
                    saw_done = True
                await ws.send_json(event)
            await task
            # M-05: a busy/early-return turn (or one that never emitted 'done') MUST still get a
            # terminal event, or the client promise resolves only on socket close — which the UI
            # never triggers, so it hangs in "working" forever.
            if not saw_done:
                res = result_box.get("result") or {}
                await ws.send_json({"type": "done", "final_text": res.get("response", ""),
                                    "error": res.get("error"), "stats": res.get("stats")})
            await ws.send_json({"type": "turn_end"})   # 73.4: the tail is finished — the client may close the socket now
    except WebSocketDisconnect:
        pass
