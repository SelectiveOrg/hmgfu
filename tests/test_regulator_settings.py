"""FASE A — Regulator/perceiver flags as UI-toggleable settings with a WRITTEN env-vs-setting
precedence (config._env_is_set): env-set wins; else the persisted setting; else default OFF. The
config.<NAME> read sites stay byte-identical when neither env nor setting is on."""

import pytest

from hmgfu import config
from tests.test_v2_agent import make_agent


def test_flags_default_off(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    assert engine.settings.get("regulator_enabled") is False
    assert engine.settings.get("chat_correction_signal") is False
    assert engine.settings.get("observe_first_n") == 0


def test_setting_reconciles_to_config_when_env_unset(tmp_path, monkeypatch):
    monkeypatch.delenv("HMGFU_REGULATOR_ENABLED", raising=False)
    monkeypatch.setattr(config, "REGULATOR_ENABLED", False)
    engine, _ = make_agent(tmp_path, [])
    engine.settings.set("regulator_enabled", True)
    config.reconcile_flags(engine.settings)
    assert config.REGULATOR_ENABLED is True          # setting drives config.X at runtime


def test_env_wins_over_setting(tmp_path, monkeypatch):
    """The inverse of the embed_model footgun: a deployment env flag is authoritative, never clobbered."""
    monkeypatch.setenv("HMGFU_REGULATOR_ENABLED", "0")   # env explicitly OFF
    monkeypatch.setattr(config, "REGULATOR_ENABLED", False)
    engine, _ = make_agent(tmp_path, [])
    engine.settings.set("regulator_enabled", True)       # UI toggled ON...
    config.reconcile_flags(engine.settings)
    assert config.REGULATOR_ENABLED is False             # ...env (OFF) wins


def test_observe_first_n_typed_and_ranged(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    engine.settings.set("observe_first_n", 50)
    assert engine.settings.get("observe_first_n") == 50
    with pytest.raises(ValueError):
        engine.settings.set("observe_first_n", 5000)     # out of range (0,1000)
    with pytest.raises(ValueError):
        engine.settings.set("regulator_enabled", "yes")  # bool type-checked


def test_engine_init_reconciles_persisted_flags(tmp_path, monkeypatch):
    """P0.2 finding: a RESTART must arm the persisted flags at ENGINE INIT — not lazily at the
    first retrieve (the observation window was disarmed until someone queried)."""
    from hmgfu.settings import Settings
    from hmgfu.agent import AgentEngine
    db = str(tmp_path / "agent.db")
    Settings(db).update({"regulator_enabled": True, "chat_correction_signal": True,
                         "observe_first_n": 50})
    monkeypatch.setattr(config, "REGULATOR_ENABLED", False)
    monkeypatch.setattr(config, "OBSERVE_FIRST_N", 0)
    AgentEngine(db_path=db)                       # offline: client.available() is fail-soft False
    assert config.REGULATOR_ENABLED is True and config.OBSERVE_FIRST_N == 50
