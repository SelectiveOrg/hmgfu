"""Minimal MCP stdio client: initialize → tools/list → tools/call (JSON-RPC, newline-framed).

Enough to make `kind=mcp` connectors REAL: connect_and_register() spawns the server,
lists its tools, and registers each as `mcp__<connector>__<tool>` in the ToolRegistry —
from there they become HMG tool points like any other tool (self-growing architecture).
Fail-soft throughout: a dead/foreign server yields an error dict, never a crash.
"""

from __future__ import annotations

import json
import logging
import os
import queue
import subprocess
import threading
from typing import Dict, List, Optional

log = logging.getLogger("hmgfu.mcp")

_clients: Dict[str, "MCPClient"] = {}   # connector name -> live client


class MCPClient:
    def __init__(self, command: List[str], cwd: Optional[str] = None):
        self.command = command
        self.proc = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
            cwd=cwd, shell=(os.name == "nt" and command[0] in ("npx", "npm", "node")),
        )
        self._next_id = 0
        self._pending: Dict[int, queue.Queue] = {}
        self._lock = threading.Lock()
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def _read_loop(self) -> None:
        for line in self.proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            mid = msg.get("id")
            with self._lock:
                waiter = self._pending.pop(mid, None)
            if waiter is not None:
                waiter.put(msg)

    def _rpc(self, method: str, params: dict, timeout: float = 30.0) -> dict:
        with self._lock:
            self._next_id += 1
            mid = self._next_id
            waiter: queue.Queue = queue.Queue()
            self._pending[mid] = waiter
        payload = json.dumps({"jsonrpc": "2.0", "id": mid, "method": method, "params": params})
        try:
            self.proc.stdin.write(payload + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise RuntimeError(f"mcp server pipe closed: {exc}") from exc
        try:
            msg = waiter.get(timeout=timeout)
        except queue.Empty:
            raise RuntimeError(f"mcp {method} timed out after {timeout}s")
        if "error" in msg:
            raise RuntimeError(f"mcp {method}: {msg['error']}")
        return msg.get("result", {})

    def _notify(self, method: str) -> None:
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method}) + "\n")
        self.proc.stdin.flush()

    def initialize(self) -> dict:
        result = self._rpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "hmg-fu", "version": "0.3.0"},
        })
        self._notify("notifications/initialized")
        return result

    def list_tools(self) -> List[dict]:
        return self._rpc("tools/list", {}).get("tools", [])

    def call_tool(self, name: str, arguments: dict, timeout: float = 60.0) -> str:
        result = self._rpc("tools/call", {"name": name, "arguments": arguments or {}},
                           timeout=timeout)
        parts = []
        for block in result.get("content", []):
            if block.get("type") == "text":
                parts.append(block.get("text", ""))
        text = "\n".join(parts) or json.dumps(result)
        if result.get("isError"):
            return json.dumps({"error": text[:1500]})
        return text

    def close(self) -> None:
        try:
            self.proc.terminate()
        except OSError:
            pass


def connect_and_register(engine, name: str, command: List[str]) -> dict:
    """Spawn an MCP server and register its tools as mcp__<name>__<tool>."""
    old = _clients.pop(name, None)
    if old is not None:
        old.close()
    try:
        client = MCPClient(command)
        client.initialize()
        tools = client.list_tools()
    except Exception as exc:
        log.warning("mcp connect %s failed: %s", name, exc)
        return {"ok": False, "error": str(exc)[:400]}
    _clients[name] = client
    registered = []
    for tool in tools:
        full = f"mcp__{name}__{tool['name']}"
        engine.tools.schemas[full] = {
            "name": full,
            "description": f"[{name}] {tool.get('description', '')}"[:500],
            "parameters": tool.get("inputSchema") or {"type": "object", "properties": {}},
        }
        engine.tools.skill_handlers[full] = _make_handler(name, tool["name"])
        registered.append(full)
    try:
        from .tool_points import sync_tool_points
        sync_tool_points(engine.tools, engine)   # MCP tools become HMG points too
    except Exception as exc:
        log.warning("tool point sync after mcp connect failed: %s", exc)
    return {"ok": True, "tools": registered, "count": len(registered)}


def _make_handler(connector: str, tool_name: str):
    def handler(_full_name: str, arguments: dict) -> str:
        client = _clients.get(connector)
        if client is None or client.proc.poll() is not None:
            return json.dumps({"error": f"mcp connector '{connector}' is not connected"})
        try:
            return client.call_tool(tool_name, arguments)
        except Exception as exc:
            return json.dumps({"error": str(exc)[:400]})
    return handler


def connected_names() -> set:
    return {name for name, c in _clients.items() if c.proc.poll() is None}


def disconnect_all() -> None:
    for client in _clients.values():
        client.close()
    _clients.clear()
