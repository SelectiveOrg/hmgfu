"""95.77 — the system reported a model it was not going to use.

Live, 16/09: the user had chosen gemma4:26b in Settings and every turn did use it, while
GET /api/health answered gemma4:12b. Health read `config.CHAT_MODEL`, the compiled-in default, instead
of resolving the role the way a turn resolves it. The same root cause sits in the plain chat path,
where HMGFuEngine.chat calls `config.CHAT_MODEL` directly and quietly ignores the chosen model.

Invariant: wherever the system names or uses the model for a role, it is the model that role RESOLVES
to — the persisted setting — and the compiled-in default only when nothing is configured at all.
"""

from __future__ import annotations

from types import SimpleNamespace

from hmgfu import config
from hmgfu.providers import ProviderRegistry, model_for_role
from hmgfu.settings import Settings


def _settings(tmp_path, **chosen):
    s = Settings(str(tmp_path / "s.db"))
    for k, v in chosen.items():
        s.set(k, v)
    return s


def test_the_role_resolves_to_what_was_chosen(tmp_path):
    s = _settings(tmp_path, chat_model="gemma4:26b", router_model="gemma4:26b")
    owner = SimpleNamespace(registry=ProviderRegistry(s), settings=s)
    assert model_for_role(owner, "chat") == "gemma4:26b"
    assert model_for_role(owner, "router") == "gemma4:26b"
    assert model_for_role(owner, "nano") == config.NANO_MODEL, "untouched roles keep their default"


def test_without_a_registry_the_setting_still_wins(tmp_path):
    s = _settings(tmp_path, chat_model="gemma4:26b")
    assert model_for_role(SimpleNamespace(settings=s), "chat") == "gemma4:26b"


def test_with_nothing_configured_the_compiled_default_is_the_honest_answer():
    assert model_for_role(SimpleNamespace(), "chat") == config.CHAT_MODEL
    assert model_for_role(SimpleNamespace(), "embed") == config.EMBED_MODEL


def test_health_reports_the_models_a_turn_would_use(tmp_path):
    from fastapi.testclient import TestClient

    from hmgfu import runtime
    from hmgfu.api import app

    s = _settings(tmp_path, chat_model="gemma4:26b", router_model="gemma4:26b", embed_model="bge-m3")
    engine = SimpleNamespace(registry=ProviderRegistry(s), settings=s,
                             client=SimpleNamespace(available=lambda: False),
                             graph=SimpleNamespace(stats=lambda: {"points": 0}))
    saved = runtime._engine
    runtime.set_engine(engine)
    try:
        models = TestClient(app).get("/api/health").json()["models"]
    finally:
        runtime.set_engine(saved)
    assert models["chat"] == "gemma4:26b", "health must not name a model the turn will not use"
    assert models["embed"] == "bge-m3"
    assert models["router"] == "gemma4:26b", "the router is a role of its own since 73.2"
    assert set(models) >= {"chat", "nano", "embed"}, "the existing keys stay (compatibility)"
