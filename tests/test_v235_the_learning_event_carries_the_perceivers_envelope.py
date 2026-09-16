"""95.49 (instrument) — the learning trace event carries the perceiver's envelope and the decision's reason.

N4 on b9bedb4 (d95w13v3 reps 2-3: "did not write Lua") could not be reproduced offline because the
trace recorded only the receipt and the action; the perceiver's `memory_update` envelope -- the one
input that differs between the live run and the fake engine -- was never written down. Attribution on
the same execution needs it. Wiring test: the engine's learning event includes `envelope` and `reason`.
"""
from __future__ import annotations

import inspect


def test_the_learning_event_carries_envelope_and_reason():
    from hmgfu import agent
    src = inspect.getsource(agent)
    assert '"envelope": (query.extraction or {}).get("memory_update")' in src and '"reason": learning["decision"].get("reason")' in src
