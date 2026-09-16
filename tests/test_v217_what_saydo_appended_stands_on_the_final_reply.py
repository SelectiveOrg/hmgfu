"""95.36 (T4, d95w11c rep1) — a guarantee saydo appended stands on the FINAL reply.

saydo fired `asked_unknown` and appended UNKNOWN_SUFFIX; `verify_grounding` then repaired a claim by
re-asking the model, and the published reply carried neither the suffix nor any question ("did not
ask"). Positive: enforce records what it appended, and keep_guarantee re-applies it to a reply a later
stage replaced. Negative: nothing is appended twice when the suffix is still there; a report with
nothing appended changes nothing. Wiring: the engine calls keep_guarantee after the last stage that
rewrites the reply (directives.enforce).
"""
from __future__ import annotations

from hmgfu.saydo import UNKNOWN_SUFFIX, enforce, keep_guarantee, transactions_of
from tests.test_v2_agent import make_agent

TX = transactions_of([], [], None, 0)
MSG = "o que significa KLM-3?"


def _rerun(instruction, required=None):
    return "", []


def _engine(tmp_path):
    engine, _ = make_agent(tmp_path, [])
    engine.settings.set("grader_enabled", False)
    engine._turn_plan = None
    engine._turn_effects_allowed = False
    engine._turn_unconfirmed_effects = []
    engine._turn_step_tools = []
    engine._turn_user_message = MSG
    return engine


def test_enforce_records_what_it_appended_and_keep_guarantee_restores_it(tmp_path):
    """THE CONTRACT — fails before: no `appended`, no keep_guarantee."""
    e = _engine(tmp_path)
    reply, _t, report = enforce(e, "Kernel Lock Manager e um conceito tecnico dentro de sistemas operativos.", [], TX, "s1", MSG, _rerun, 2)
    suffix = UNKNOWN_SUFFIX.format(label="KLM-3")
    assert report.get("appended") == suffix and reply.endswith(suffix)
    repaired = "Como a busca nao retornou resultados para KLM-3, nao pude verificar uma definicao universal."   # a later stage's reply
    final = keep_guarantee(repaired, report)
    assert final == repaired.rstrip() + suffix


def test_nothing_is_appended_twice_and_no_report_changes_nothing():
    suffix = UNKNOWN_SUFFIX.format(label="KLM-3")
    kept = "Nao tenho registo." + suffix
    assert keep_guarantee(kept, {"appended": suffix}) == kept
    assert keep_guarantee("unchanged", {}) == "unchanged" and keep_guarantee("unchanged", None) == "unchanged"


def test_the_engine_applies_it_after_the_last_rewriting_stage():
    import inspect
    from hmgfu import agent
    src = inspect.getsource(agent)
    assert src.index("self.directives.enforce(") < src.index("keep_guarantee(reply, _saydo)")
