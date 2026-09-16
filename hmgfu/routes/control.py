"""Control plane: tools/skills galleries, providers, settings, connectors, sessions, system."""

from __future__ import annotations

import anyio
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..providers import ROLES
from ..runtime import get_engine

router = APIRouter()


class SettingsPatch(BaseModel):
    model_config = {"extra": "allow"}


class SessionIn(BaseModel):
    title: str = "New session"
    group: str | None = None


class TailscaleIn(BaseModel):
    action: str  # on | off


# --- tools & skills -------------------------------------------------------------

@router.get("/api/tools")
async def tools_gallery():
    """Tool gallery with usage stats + the HMG utility each tool has earned."""
    engine = get_engine()
    gallery = engine.tools.gallery()
    for item in gallery:
        point = engine._tool_point(item["name"])
        item["utility"] = round(point.utility, 3) if point else None
        item["access_count"] = point.access_count if point else 0
    return {"tools": gallery}


@router.get("/api/tools/search")
async def tools_search(q: str):
    return {"results": get_engine().tools.search(q)}


@router.get("/api/skills")
async def skills_list():
    return {"skills": [
        {"file": fname, **meta} for fname, meta in get_engine().tools.skill_meta.items()
    ]}


# --- providers & settings ---------------------------------------------------------

@router.get("/api/providers")
async def providers_status():
    engine = get_engine()
    return {
        "providers": engine.registry.status(),
        "roles": {role: {"provider": engine.settings.get(f"{role}_provider"),
                         "model": engine.settings.get(f"{role}_model")}
                  for role in ROLES},                        # 73.2: one role list (providers.ROLES)
    }


def _regulator_status(engine) -> dict:
    """Live status for the UI: observation progress (n/target) + which flags are ENV-LOCKED (an env
    var is set, so the persisted setting is ignored — precedence, config._env_is_set)."""
    from .. import config
    env_locked = {key: config._env_is_set(env) for env, key in (
        ("REGULATOR_ENABLED", "regulator_enabled"),
        ("CHAT_CORRECTION_SIGNAL", "chat_correction_signal"),
        ("OBSERVE_FIRST_N", "observe_first_n"))}
    target = int(config.OBSERVE_FIRST_N or 0)
    return {"observed": int(getattr(engine, "_observed", 0)), "observe_target": target,
            "env_locked": env_locked}


@router.get("/api/settings")
async def settings_get():
    engine = get_engine()
    return {"settings": engine.settings.all(), "regulator": _regulator_status(engine)}


@router.put("/api/settings")
async def settings_put(body: SettingsPatch):
    engine = get_engine()
    try:
        applied = engine.settings.update(body.model_dump())
    except (KeyError, ValueError) as exc:
        raise HTTPException(400, str(exc))
    if "workspace_dir" in applied:   # take effect immediately, not at the next turn
        from ..tool_builtins import set_workspace
        set_workspace(applied["workspace_dir"])
    # Turning the Regulator ON auto-engages the observation window (Rule 10 — the toggle can't ship a
    # silent live change): default the first-N window to 50 and reset the counter so it counts from now.
    if applied.get("regulator_enabled") and engine.settings.get("observe_first_n") == 0:
        engine.settings.set("observe_first_n", 50)
    if applied.get("regulator_enabled") is not None:
        engine._observed = 0
    from .. import config
    config.reconcile_flags(engine.settings)   # reconcile settings -> config.<NAME> now, not at next turn
    return {"applied": applied, "settings": engine.settings.all(), "regulator": _regulator_status(engine)}


@router.get("/api/observation_log")
async def observation_log_get(limit: int = 50):
    """P-AUDIT-3b post-flip observation window: the first-N corrections' source + lifecycle-ledger."""
    from pathlib import Path
    from .. import config
    path = Path(config.DB_PATH).with_name("observation_log.jsonl")
    if not path.exists():
        return {"entries": [], "count": 0}
    lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    entries = [json.loads(l) for l in lines[-limit:]]
    return {"entries": entries, "count": len(lines)}


class ConnectorIn(BaseModel):
    name: str
    display: str = ""
    auth: str            # api_key | cli | mcp | oauth
    category: str = "custom"
    services: list = []
    config: dict = {}


class SecretIn(BaseModel):
    secret: dict         # e.g. {"api_key": "..."} — stored encrypted, never echoed


class ConnectorFinishIn(BaseModel):
    redirect_url: str


@router.get("/api/directives")
async def directives_list():
    """Active standing directives (visible, not hidden — Rule 10)."""
    return {"directives": get_engine().directives.active()}


@router.get("/api/prospective")
async def prospective_list():
    """75.2: reminders by time / condition, all statuses (visible, not hidden — Rule 10)."""
    from ..prospective import list_triggers
    return {"triggers": list_triggers(get_engine())}


@router.post("/api/prospective/{tid}/cancel")
async def prospective_cancel(tid: str):
    row = get_engine().prospective.get(tid)
    if row is None:
        return {"ok": False, "error": "unknown trigger"}
    if row["status"] != "pending":
        return {"ok": False, "error": f"trigger is {row['status']}"}
    return {"ok": True, "trigger": get_engine().prospective.set_status(tid, "cancelled")}


class AckIn(BaseModel):
    ids: list


@router.get("/api/prospective/notifications")
async def prospective_notifications(limit: int = 100):
    """77.6: reminders that fired WITHOUT a turn (the alarm ticker) — delivered by the next turn or acknowledged here."""
    store = get_engine().prospective
    ticker = getattr(get_engine(), "_alarm_ticker", None)
    return {"notifications": store.notifications(limit), "undelivered": store.undelivered(),
            "ticker": {"alive": bool(ticker and ticker.alive), "ticks": getattr(ticker, "ticks", 0), "fired": getattr(ticker, "fired", 0),
                       "every_s": get_engine().settings.get("prospective_tick_s")}}


@router.post("/api/prospective/notifications/ack")
async def prospective_ack(body: AckIn):
    n = get_engine().prospective.mark_delivered([str(i) for i in body.ids], "ui")
    return {"ok": True, "delivered": n}


@router.get("/api/runbooks")
async def runbooks_list():
    """75.1: procedural memory — runbooks derived from executed plans (visible, not hidden — Rule 10)."""
    from ..runbooks import list_runbooks
    return {"runbooks": list_runbooks(get_engine())}


@router.get("/api/facts")
async def facts_list():
    """Canonical first-class facts (literal value, supersede-aware) — visible (Rule 10)."""
    facts = get_engine().facts
    return {"facts": facts.active(), "history": facts.history(limit=100)}


@router.get("/api/learning")
async def learning_state():
    """Phase 56 self-tuning state: learned score-weight multipliers vs config baseline, update
    counts, and every raw learned parameter (wormhole calibration included) — nothing hidden."""
    engine = get_engine()
    return {
        "enabled": engine.settings.get("learning_enabled"),
        "memory_score": engine.weight_learner.snapshot(),
        "routing": engine.route_memory.stats(),
        "bandit": {"enabled": engine.settings.get("bandit_enabled"), "arms": engine.bandit.snapshot()},   # 75.5
        "params": engine.learned_params.all(),
    }


@router.get("/api/connectors")
async def connectors_status():
    from ..connectors import connector_status
    from ..mcp_client import connected_names
    return {"connectors": connector_status(connected_mcp=connected_names())}


@router.post("/api/connectors")
async def connectors_add(body: ConnectorIn):
    from ..connectors import add_provider
    result = add_provider(body.name, body.display, body.auth, body.config,
                          body.category, body.services)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.delete("/api/connectors/{name}")
async def connectors_remove(name: str):
    from ..connectors import remove_provider
    result = remove_provider(name)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/api/connectors/{name}/secret")
async def connectors_secret(name: str, body: SecretIn):
    """Save ONE credential for the whole provider (grants all its services)."""
    from ..connectors import CredentialVault
    ok = CredentialVault().put(name, body.secret)
    if not ok:
        raise HTTPException(500, "vault unavailable (cryptography not installed)")
    return {"ok": True, "stored": name}


@router.post("/api/connectors/{name}/connect")
async def connectors_connect(name: str):
    """Start an MCP connection or Google's two-stage gog remote OAuth flow."""
    from ..connectors import all_providers
    spec = all_providers().get(name)
    if spec is None:
        raise HTTPException(404, f"unknown provider '{name}'")
    engine = get_engine()
    if name == "google" and spec["auth"] == "cli":
        from ..connectors import google_connect
        result = await anyio.to_thread.run_sync(lambda: google_connect(engine))
        if not result.get("ok"):
            raise HTTPException(502, result.get("error", "Google connect failed"))
        return result
    if spec["auth"] != "mcp":
        raise HTTPException(400, f"'{name}' uses auth={spec['auth']} — only mcp providers connect")
    from ..mcp_client import connect_and_register
    result = await anyio.to_thread.run_sync(
        lambda: connect_and_register(engine, name, spec["config"]["command"])
    )
    if not result.get("ok"):
        raise HTTPException(502, result.get("error", "connect failed"))
    return result


@router.post("/api/connectors/{name}/connect/finish")
async def connectors_connect_finish(name: str, body: ConnectorFinishIn):
    if name != "google":
        raise HTTPException(400, "two-stage connect is only supported for Google gog")
    from ..connectors import google_connect
    result = await anyio.to_thread.run_sync(
        lambda: google_connect(get_engine(), body.redirect_url.strip())
    )
    if not result.get("ok"):
        raise HTTPException(502, result.get("error", "Google authorization failed"))
    return result


# --- sessions ------------------------------------------------------------------------

@router.get("/api/sessions")
async def sessions_list():
    return {"sessions": get_engine().sessions.list_sessions()}


@router.post("/api/sessions")
async def sessions_create(body: SessionIn):
    return {"session": get_engine().sessions.create_session(body.title)}


@router.get("/api/sessions/{session_id}/history")
async def session_history(session_id: str):
    engine = get_engine()
    return {"history": engine.sessions.history(session_id),
            "widgets": engine.sessions.widgets(session_id)}


@router.delete("/api/sessions/{session_id}/widgets/{widget_id}")
async def session_widget_delete(session_id: str, widget_id: str):
    get_engine().sessions.remove_widget(session_id, widget_id)
    return {"ok": True}


@router.put("/api/sessions/{session_id}/widgets")
async def session_widget_upsert(session_id: str, widget: dict):
    """Persist a manually-added canvas widget (agent widgets persist via the WS path);
    without this, a session switch dropped every hand-added widget (Phase 31)."""
    from ..sessions import WIDGET_TYPES
    if not widget.get("id") or not widget.get("type"):
        raise HTTPException(400, "widget needs id and type")
    # M-14: validate the widget type and that the session actually exists (no orphan rows)
    if widget["type"] not in WIDGET_TYPES:
        raise HTTPException(400, f"widget type must be one of {list(WIDGET_TYPES)}")
    sessions = get_engine().sessions
    if not sessions.exists(session_id):
        raise HTTPException(404, "session not found")
    sessions.upsert_widget(session_id, widget)
    return {"ok": True}


@router.patch("/api/sessions/{session_id}")
async def session_patch(session_id: str, body: SessionIn):
    sessions = get_engine().sessions
    if body.title and body.title != "New session":
        sessions.rename_session(session_id, body.title)
    if body.group is not None:
        sessions.set_group(session_id, body.group)
    return {"ok": True}


@router.delete("/api/sessions/{session_id}")
async def session_delete(session_id: str):
    get_engine().sessions.delete_session(session_id)
    return {"ok": True}


# --- system (Settings UI: restart / rebuild / tailscale) --------------------------------

@router.get("/api/system/status")
async def system_status():
    from .. import system
    return await anyio.to_thread.run_sync(system.system_status)


@router.get("/api/system/projects")
async def system_projects():
    from .. import system
    return {"projects": await anyio.to_thread.run_sync(system.list_projects)}


@router.get("/api/now")
async def now_feed():
    """The 'Now' widget feed: time, workspace, fresh memories, dream state, tensions."""
    from datetime import datetime
    from .. import system
    from ..dream import unresolved_tension_count
    from ..taxonomy import category_of as _category_of, node_class as _node_class
    engine = get_engine()
    g = engine.graph
    recent = sorted((p for p in g.points.values() if p.type not in ("skill",)),
                    key=lambda p: p.last_accessed_at, reverse=True)[:6]
    reports = g.dream_reports(limit=1)
    return {
        "time": datetime.now().strftime("%H:%M"),
        "date": datetime.now().strftime("%a, %d %b"),
        "workspace": system.workspace_info(),
        "stats": g.stats(),
        "tensions": unresolved_tension_count(g),
        "last_dream": reports[0].summary if reports else None,
        "directives": len(engine.directives.active()), "facts": len(engine.facts.active()),
        "recent": [{"title": p.title or p.summary[:40], "type": p.type,
                    "nodeClass": _node_class(p), "category": _category_of(p),
                    "when": p.last_accessed_at[:16].replace("T", " ")} for p in recent],
    }


@router.post("/api/system/restart")
async def system_restart():
    from .. import system
    return system.restart_server()


@router.post("/api/system/rebuild")
async def system_rebuild():
    from .. import system
    return system.rebuild()


@router.post("/api/system/tailscale")
async def system_tailscale(body: TailscaleIn):
    from .. import system
    return await anyio.to_thread.run_sync(lambda: system.tailscale_serve(body.action))
