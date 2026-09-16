"""Phase 56 bench-L22 fix — tool points learn the user's phrasings through successful use.

Registry descriptions are English and the embedder is English-centric, so a Portuguese
instruction couldn't reach the semantic-fallback floor when the router degraded. After the
first successful use with a novel phrasing, the phrasing becomes part of the tool point's
embedded content — multilingual coverage that GROWS from real usage. Deterministic (fake
bag-of-words embedder): cross-language phrases share no tokens → cosine ≈ 0 → novel.
"""

from __future__ import annotations

from hmgfu import fu_math
from hmgfu.models import QueryPoint
from hmgfu.tool_points import (MAX_USAGE_PHRASES, compose_tool_content, learn_usage_phrase,
                               sync_tool_points, tool_phrases)
from tests.conftest import fake_embed
from tests.test_v2_agent import make_agent

PT = "Pesquise na sua memoria pelo codigo exato ORCA-7"


def _q(text):
    return QueryPoint(text=text, embedding=fake_embed(text), intent="task",
                      conversation_act="instruction")


def test_novel_phrase_is_learned_and_improves_semantic_match(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    point = engine._tool_point("memory_search")
    before = fu_math.memory_score(_q(PT), point)

    assert learn_usage_phrase(engine, point, PT) is True
    assert PT in tool_phrases(point)
    assert PT in point.content                                   # folded into embedded content
    after = fu_math.memory_score(_q(PT), point)
    assert after > before                                        # the PT query now reaches the tool

    # exact duplicate and semantically-covered phrasings are NOT stored again
    assert learn_usage_phrase(engine, point, PT) is False
    covered = " ".join(point.content.split()[:10])               # literally the content's tokens
    assert learn_usage_phrase(engine, point, covered) is False
    assert len(tool_phrases(point)) == 1


def test_phrase_store_is_capped_fifo(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    point = engine._tool_point("bash")
    for i in range(MAX_USAGE_PHRASES + 1):
        assert learn_usage_phrase(engine, point, f"frase distinta numero{i} palavra{i} coisa{i}")
    phrases = tool_phrases(point)
    assert len(phrases) == MAX_USAGE_PHRASES                     # capped
    assert not any("numero0" in p for p in phrases)              # oldest evicted


def test_sync_preserves_learned_phrases(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    point = engine._tool_point("memory_search")
    learn_usage_phrase(engine, point, PT)
    content_before = point.content
    sync_tool_points(engine.tools, engine)                       # startup re-sync
    point2 = engine._tool_point("memory_search")
    assert PT in tool_phrases(point2)                            # keyword survives
    assert point2.content == content_before                      # composed content stable
    assert compose_tool_content("memory_search", point2.summary, tool_phrases(point2)) \
        == point2.content


def test_agent_learns_phrase_only_on_success_and_when_enabled(tmp_path, monkeypatch):
    engine, fake = make_agent(tmp_path, [
        {"content": "", "tool_calls": [{"name": "bash", "arguments": {"command": "echo OI"}}]},
        {"content": "O resultado é OI.", "tool_calls": []},
    ])
    engine.settings.set("tool_points_enabled", True)
    real = engine.retrieve
    def routed(text, **kw):
        q, r, ms = real(text, **kw)
        q.action_requested = True
        q.requested_tools = ["bash"]
        return q, r, ms
    monkeypatch.setattr(engine, "retrieve", routed)

    engine.agent_chat("execute o comando de terminal imprimir OI")
    assert any("execute o comando" in p for p in tool_phrases(engine._tool_point("bash")))

    engine.settings.set("learning_enabled", False)               # off-switch honoured
    fake.script = [
        {"content": "", "tool_calls": [{"name": "bash", "arguments": {"command": "echo X"}}]},
        {"content": "X.", "tool_calls": []},
    ]
    engine.agent_chat("outra frase totalmente diferente aqui agora")
    assert not any("outra frase" in p for p in tool_phrases(engine._tool_point("bash")))
