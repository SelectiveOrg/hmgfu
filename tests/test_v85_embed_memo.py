"""Phase 89.2 — the embed memo: one provider call per text even when a second thread asks while the first call is in flight
(retrieval embeds on a worker while the kNN router asks on the main thread); a failure is not cached; a new text is a new call."""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from hmgfu.embed_memo import EmbedMemo


def test_concurrent_same_text_is_one_call():
    memo = EmbedMemo()
    started = threading.Event()

    def slow(text):
        started.set(); time.sleep(0.2)
        return [1.0, float(len(text))]

    with ThreadPoolExecutor(max_workers=2) as ex:
        a = ex.submit(memo, "hello", slow)
        assert started.wait(2.0)
        b = ex.submit(memo, "hello", slow)
        assert a.result() == b.result() == [1.0, 5.0]
    assert memo.calls == 1
    assert memo("hello", slow) == [1.0, 5.0] and memo.calls == 1         # settled memo
    assert memo("other", slow) == [1.0, 5.0] and memo.calls == 2          # a new text is a new call


def test_failure_is_shared_and_not_cached():
    memo = EmbedMemo()
    n = {"k": 0}

    def flaky(text):
        n["k"] += 1
        if n["k"] == 1:
            time.sleep(0.1); raise RuntimeError("provider down")
        return [2.0]

    with ThreadPoolExecutor(max_workers=2) as ex:
        a = ex.submit(memo, "x", flaky); time.sleep(0.02); b = ex.submit(memo, "x", flaky)
        with pytest.raises(RuntimeError):
            a.result()
        with pytest.raises(RuntimeError):
            b.result()
    assert memo("x", flaky) == [2.0]                                        # retried after the failure, not served from cache


def test_agent_embed_uses_the_memo():
    from hmgfu.agent import AgentEngine
    src = open(AgentEngine.embed.__code__.co_filename, encoding="utf-8").read()
    assert "EmbedMemo" in src
