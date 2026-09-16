"""Phase 57 P4 — deterministic clock-grounding verifier + re-ask.

When the constrained router flags runtime_context_sufficient with clock keys, the answer MUST
carry the authoritative value; on a miss we re-ask once with the literal values (external-signal
correction, data-derived, not a static prompt rule). Deterministic — no Ollama.
"""

from __future__ import annotations

from hmgfu.models import QueryPoint
from hmgfu.runtime_context import RuntimeContext, _grounding_missing, ground_reply
from tests.test_v2_agent import make_agent

RT = RuntimeContext(now_local="2026-07-05T18:30:00+02:00", now_utc="2026-07-05T16:30:00+00:00",
                    local_date="2026-07-05", local_time="18:30:00",
                    timezone_name="SAST", utc_offset="+02:00", unix_seconds=1783269000)


def test_grounding_missing_is_value_and_format_tolerant():
    keys = ["local_time", "local_date"]
    assert _grounding_missing("It is 18:30 right now.", keys, RT) is False   # HH:MM of HH:MM:SS
    assert _grounding_missing("Today is 2026-07-05.", keys, RT) is False     # date present
    assert _grounding_missing("It's around tea time.", keys, RT) is True     # neither value
    assert _grounding_missing("qualquer coisa", [], RT) is False             # no keys → not checked
    # ISO datetime key: the HH:MM and date sub-forms both count as grounded
    assert _grounding_missing("agora sao 18:30", ["now_local"], RT) is False


def test_ground_reply_noop_when_not_sufficient_or_already_grounded(tmp_path):
    engine, fake = make_agent(tmp_path, [])
    q_ns = QueryPoint(runtime_context_sufficient=False, runtime_context_keys=["local_time"])
    assert ground_reply(engine, "no time here", "que horas?", q_ns, RT, "sys") == "no time here"
    q_ok = QueryPoint(conversation_act="question", freshness="current", runtime_context_sufficient=True,
                      runtime_context_keys=["local_time"])
    assert ground_reply(engine, "It is 18:30.", "que horas?", q_ok, RT, "sys") == "It is 18:30."
    assert fake.calls == []                                                  # never re-asked


def test_ground_reply_reasks_with_literal_values_on_miss(tmp_path):
    engine, fake = make_agent(tmp_path, [
        {"content": "Agora sao exatamente 18:30 (UTC+02:00).", "tool_calls": []},
    ])
    # 91.X1: the gate also requires that the turn ASKED. "que horas?" is a question, which is what
    # this fixture always modelled; the assertions below are unchanged.
    # 91.Y5: and it wants a CURRENT value, which is what `freshness` carries. The assertions below
    # are unchanged; only the classification this fixture always modelled is now stated.
    q = QueryPoint(conversation_act="question", freshness="current", runtime_context_sufficient=True,
                   runtime_context_keys=["local_time", "utc_offset"])
    out = ground_reply(engine, "Sao Paulo esta em UTC-3, entao 13:30.", "que horas?", q, RT, "sys")
    assert out == "Agora sao exatamente 18:30 (UTC+02:00)."                  # corrected reply used
    assert len(fake.calls) == 1                                              # exactly one re-ask
    # the re-ask carried the literal authoritative values
    reask = fake.calls[0]["messages"][-1]["content"]
    assert "18:30:00" in reask and "+02:00" in reask
