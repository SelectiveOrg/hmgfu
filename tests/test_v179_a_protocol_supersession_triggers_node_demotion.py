"""95.2b — a canonical supersession written by the PROTOCOL demotes stale nodes like one written by the
regex path (guide §4: corrections govern ledger, assertions, summaries and derived answers).

Seen in c952 rep3 (95.2 integrated, L2): `project.main` moved Nimbus→Vega with `prev=Nimbus` through
`learning_apply` (95.2), the grader's correction path did not fire (the 95.7 miss), and the old
teaching and the assistant's echo stayed `active`. `agent.py:261` triggers `_supersede_stale_fact_nodes`
only on `fact_changes` — the regex path's output — so a supersession the protocol wrote never reaches
94.6's demotion. That is the reason 94.6 has been through three validations without executing once.

Invariant: the demotion trigger reads every canonical supersession of the turn, whichever writer made
it. Change: `fact_nodes.has_supersession(fact_changes, learning)`; the agent's trigger line calls it.
"""
from __future__ import annotations

import pytest

from hmgfu.fact_nodes import has_supersession


def _learning(*effects):
    return {"effects": [{"kind": "domain_definition", "effects": list(effects)}]}


def test_a_protocol_write_with_prev_is_a_supersession():
    """THE CONTRACT — fails before: the helper does not exist / the trigger ignores learning."""
    assert has_supersession([], _learning({"key": "project.main", "value": "Vega", "prev": "Nimbus"}))


def test_a_protocol_write_without_prev_is_not():
    assert not has_supersession([], _learning({"key": "project.main", "value": "Vega", "prev": None}))


def test_the_regex_path_still_counts():
    """PRESERVE — what triggered before triggers now."""
    assert has_supersession([{"key": "identity.name", "value": "Teodoro", "prev": "Sebastian"}], None)
    assert has_supersession([{"key": "identity.name", "cleared": "Sebastian"}], None)


def test_nothing_written_is_nothing():
    assert not has_supersession([], None)
    assert not has_supersession([], {"effects": []})
    assert not has_supersession([], {"effects": [{"kind": "behavior_policy", "effects": {"kind": "x"}}]})


def test_the_agent_trigger_reads_the_helper():
    """Wiring (Rule 9): the trigger line in agent.py uses the helper, not only fact_changes."""
    import inspect
    from hmgfu import agent
    src = inspect.getsource(agent)
    assert "has_supersession(" in src
