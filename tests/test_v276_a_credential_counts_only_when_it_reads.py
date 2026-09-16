"""95.76 — the settings panel offered no way to enter an API key, and the agent said there was none.

Live, 16/09: the Brave card showed a green "connected" badge while brave_web_search answered "web
search is NOT configured (no Brave API key)". Both were reading the same vault: `_configured` said yes
because a ROW existed, and the key in that row could not be decrypted on this instance. The UI shows
the key input only when a provider is not configured, so the one action that would fix it — type the
key again — was the one action the panel did not offer.

Invariant: a credential counts as configured only when it can be READ, and a provider that takes a key
can always be given a new one.
"""

from __future__ import annotations

import sqlite3

from hmgfu.connectors import CredentialVault, connector_status


def _vault(tmp_path, monkeypatch):
    from hmgfu import config
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "v.db"))
    return CredentialVault(str(tmp_path / "v.db"))


def test_a_readable_key_is_configured(tmp_path, monkeypatch):
    v = _vault(tmp_path, monkeypatch)
    assert v.put("brave", {"api_key": "k-123"})
    row = next(c for c in connector_status() if c["kind"] == "brave")
    assert row["configured"] and row["source"] == "vault"


def test_a_row_that_cannot_be_read_is_not_configured(tmp_path, monkeypatch):
    """A database carried to another machine keeps its rows and loses its key."""
    v = _vault(tmp_path, monkeypatch)
    v.put("brave", {"api_key": "k-123"})
    db = sqlite3.connect(str(tmp_path / "v.db"))
    db.execute("UPDATE credentials SET blob=? WHERE kind='brave'", (b"gAAAAAB-not-this-instance",))
    db.commit()
    db.close()

    assert CredentialVault(str(tmp_path / "v.db")).get("brave") is None
    row = next(c for c in connector_status() if c["kind"] == "brave")
    assert not row["configured"], "a key that cannot be read is not a key"
    assert row["source"] == "unreadable", "and the panel is told why, so it can ask for a new one"


def test_the_other_providers_are_unaffected(tmp_path, monkeypatch):
    _vault(tmp_path, monkeypatch)
    rows = {c["kind"]: c for c in connector_status()}
    assert rows["tailscale"]["auth"] == "cli"
    assert not rows["github"]["configured"] and rows["github"]["source"] is None
