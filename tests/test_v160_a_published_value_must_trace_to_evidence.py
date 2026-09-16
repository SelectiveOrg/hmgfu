"""94.2 — the widget showed a temperature nobody measured.

From the first real-memory conversation (`0ad8e72e`, 2026-09-12). `brave_web_search` ran and its
receipt (`ee02ccc69494`) came back with link snippets only — *"Valencia - Weather forecast for 14 days,
information from meteorological stations, webcams…"*. It contains no "19", no degree sign, no
temperature of any kind. `create_widget` was then called with

    props={"place": "Valencia City, Spain", "temp": 19}

and succeeded (`w_f127a958`). The user looked at it and said "looks good thanks". A number that no
tool returned is now on the canvas as a reading.

The tool's own error had invited it: *"weather widget needs props ['temp','place'] — call
create_widget again with real values, e.g. props={'temp': ...}"*. It asked for real values and had no
way to tell a real one from a plausible one.

`widgets.py` already holds the principle for one type: an `app` widget is backfilled from what THIS
turn produced and refused otherwise — *"write the file first, then the widget"*. This extends that
same idea rather than adding a second mechanism (Rule 5): a prop that ASSERTS something about the
world must trace to the turn's evidence — a tool result, the user's own message, or the fact ledger.

What this deliberately does NOT do: invent a placeholder channel. There is no UI for "unverified", so
inventing a prop the canvas ignores would be a hidden feature. The tool refuses and says how to
satisfy it. A fabricated *string* in an unchecked prop is still possible; that limit is stated rather
than papered over.
"""
from __future__ import annotations

import json

import pytest

from hmgfu.widgets import enrich_widget_args


class _Facts:
    def __init__(self, lines):
        self._lines = lines

    def render_lines(self):
        return list(self._lines)


class _Engine:
    """Only what the validator reads: the turn's artifacts, message and ledger."""

    def __init__(self, evidence=(), message="a turn is running", facts=()):
        self._turn_files = []
        self._turn_url = None
        self._turn_evidence = list(evidence)
        self._turn_user_message = message
        self.facts = _Facts(facts)


WEATHER = {"type": "weather", "title": "Valencia Weather Widget"}


def _call(engine, **props):
    return enrich_widget_args(engine, "weather", dict(WEATHER, props=props))


# --- the defect, exactly as it happened -------------------------------------------------------------

def test_a_temperature_no_tool_returned_is_refused():
    search = json.dumps({"results": [{"title": "Weather - Valencia - 14-Day Forecast & Rain",
                                      "snippet": "information from meteorological stations, webcams"}]})
    engine = _Engine(evidence=[search], message="whats the wheater today?")
    _props, error = _call(engine, temp=19, place="Valencia City, Spain")
    assert error, "a fabricated reading was published as an observation"
    assert "temp" in error


def test_the_refusal_says_how_to_satisfy_it():
    engine = _Engine(evidence=["{}"], message="whats the wheater today?")
    _props, error = _call(engine, temp=19, place="Valencia")
    assert "evidence" in error.lower() or "tool" in error.lower(), error


# --- the three sources of evidence that make it legitimate -------------------------------------------

def test_a_value_a_tool_returned_is_accepted():
    engine = _Engine(evidence=[json.dumps({"place": "Valencia", "current": {"temperature_2m": 19}})],
                     message="whats the weather?")
    _props, error = _call(engine, temp=19, place="Valencia")
    assert error is None, error


def test_a_value_the_user_gave_is_accepted():
    engine = _Engine(message="it is 19 degrees here in Valencia right now")
    _props, error = _call(engine, temp=19, place="Valencia")
    assert error is None, error


def test_a_value_the_fact_ledger_holds_is_accepted():
    """`place` came from the stored location, not from this turn — that is still evidence."""
    engine = _Engine(evidence=[json.dumps({"temp": 19})],
                     facts=["identity.location = Valencia City, Spain"])
    _props, error = _call(engine, temp=19, place="Valencia City, Spain")
    assert error is None, error


# --- what must not change ----------------------------------------------------------------------------

def test_a_missing_prop_still_gets_its_old_message():
    engine = _Engine(message="anything")
    _props, error = _call(engine, place="Valencia")
    assert error and "needs props" in error


def test_a_prop_that_asserts_nothing_is_not_checked():
    """A note is what the user dictated, not a reading; checking it would refuse ordinary use."""
    engine = _Engine(message="write this down")
    _props, error = enrich_widget_args(engine, "note",
                                       {"type": "note", "props": {"text": "buy milk"}})
    assert error is None, error


@pytest.mark.parametrize("given,evidence", [(19, "19"), ("19", "19"), (19.0, "19")])
def test_a_number_matches_however_it_is_spelled(given, evidence):
    engine = _Engine(evidence=[json.dumps({"t": evidence, "place": "Valencia"})])
    _props, error = _call(engine, temp=given, place="Valencia")
    assert error is None, error
