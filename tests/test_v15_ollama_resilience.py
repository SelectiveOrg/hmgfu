"""Phase 52 — Ollama empty-response resilience.

Under sustained multi-model load Ollama answers a 200 with EMPTY content. That silent
degradation used to be accepted as success, zeroing nano routing/action signals (the L6/L7
'not proactive' failure). Chat now retries empty responses with backoff, mirroring embed(),
without falsely retrying a legitimate tool-only turn. No Ollama needed — httpx.post is faked.
"""

from __future__ import annotations


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_ollama_client_chat_retries_empty_then_recovers(monkeypatch):
    from hmgfu.ollama_client import OllamaClient
    client = OllamaClient()
    calls = {"n": 0}

    def fake_post(url, **kw):
        calls["n"] += 1
        content = "" if calls["n"] == 1 else "recovered"
        return _Resp({"message": {"content": content}})

    monkeypatch.setattr(client._client, "post", fake_post)
    monkeypatch.setattr("hmgfu.ollama_client.time.sleep", lambda s: None)
    assert client.chat("m", [{"role": "user", "content": "hi"}]) == "recovered"
    assert calls["n"] == 2                       # did NOT accept the empty response


def test_ollama_client_chat_raises_when_persistently_empty(monkeypatch):
    from hmgfu.ollama_client import OllamaClient, OllamaError
    client = OllamaClient()
    monkeypatch.setattr(client._client, "post", lambda url, **kw: _Resp({"message": {"content": ""}}))
    monkeypatch.setattr("hmgfu.ollama_client.time.sleep", lambda s: None)
    try:
        client.chat("m", [{"role": "user", "content": "hi"}])
        assert False, "should raise after exhausting retries on empty responses"
    except OllamaError:
        pass


def test_provider_chat_keeps_legitimate_tool_only_turn(monkeypatch):
    """Empty content WITH tool_calls is a valid tool-only turn — must return immediately."""
    from hmgfu.providers import OllamaProvider
    from hmgfu.ollama_client import OllamaClient
    prov = OllamaProvider(OllamaClient())
    calls = {"n": 0}

    def fake_post(url, **kw):
        calls["n"] += 1
        return _Resp({"message": {"content": "",
                                  "tool_calls": [{"function": {"name": "bash",
                                                               "arguments": {"command": "ls"}}}]}})

    monkeypatch.setattr(prov.client._client, "post", fake_post)
    out = prov.chat("m", [{"role": "user", "content": "run ls"}])
    assert calls["n"] == 1                        # not retried away
    assert out["tool_calls"][0]["name"] == "bash"


def test_provider_chat_retries_fully_empty_response(monkeypatch):
    """Empty content AND no tool call = degradation → retry with backoff, then recover."""
    from hmgfu.providers import OllamaProvider
    from hmgfu.ollama_client import OllamaClient
    prov = OllamaProvider(OllamaClient())
    calls = {"n": 0}

    def fake_post(url, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            return _Resp({"message": {"content": "", "tool_calls": []}})
        return _Resp({"message": {"content": "answer", "tool_calls": []}})

    monkeypatch.setattr(prov.client._client, "post", fake_post)
    monkeypatch.setattr("hmgfu.providers.time.sleep", lambda s: None)
    out = prov.chat("m", [{"role": "user", "content": "hi"}])
    assert calls["n"] == 2 and out["content"] == "answer"
