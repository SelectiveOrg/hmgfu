"""92.E5b — a defect in our own code must not be reported as a model failure.

Found live, not by reading: a syntax error in `turn_router` was caught by the sensitizer's blanket
`except Exception` and logged as "nano extraction failed ...; using heuristic fallback". The router
never ran, every turn silently degraded to the heuristic path, and a C/L comparison that depended on
the router produced empty arms that *looked* like a negative result. Silence of that kind does not
just hide a bug, it manufactures evidence.

The gate has to discriminate, which is why there are two tests and not one:

  * a fault that can ONLY mean this codebase is broken -- SyntaxError, ImportError, NameError, none of
    which model output can provoke, since nothing here compiles or evals what a model returns -- must
    reach the caller;
  * a fault that means the MODEL or the transport misbehaved -- a reset connection, a timeout, an
    unparseable payload -- must still degrade to the heuristic extraction, because degrading is the
    correct answer there and this turn must not fail.
"""
from __future__ import annotations

import pytest

from hmgfu.sensitizer import Sensitizer


def _live_sensitizer(fault: BaseException) -> Sensitizer:
    """A sensitizer that believes it has a model, failing at the first step inside the guarded block."""
    s = Sensitizer(client=object(), enabled=True)

    def boom():
        raise fault

    s._action_catalog = boom
    return s


@pytest.mark.parametrize("fault", [
    SyntaxError("unterminated string literal (detected at line 206)"),
    ImportError("cannot import name 'start_route' from 'hmgfu.turn_router'"),
    NameError("name 'learning_text' is not defined"),
])
def test_our_own_defect_reaches_the_caller(fault):
    """Not a fallback and not a warning: these mean the module is broken, so the run must stop."""
    with pytest.raises(type(fault)):
        _live_sensitizer(fault).extract("In this project, ACME-7 means Atlas Control Mesh.", route=True)


@pytest.mark.parametrize("fault", [
    RuntimeError("connection reset by peer"),
    TimeoutError("nano timed out"),
    ValueError("expecting value: line 1 column 1"),
])
def test_a_model_or_transport_failure_still_degrades(fault):
    """The legitimate positive the gate above must not swallow: the turn continues on heuristics."""
    out = _live_sensitizer(fault).extract("In this project, ACME-7 means Atlas Control Mesh.", route=True)
    assert out["extractor"] not in ("nano",)
    assert out["summary"], "the heuristic extraction still has to produce something usable"
