"""94.5 — "I cannot execute curl commands directly" was true of five tools and false of twenty-two.

From the weather session. `bash`, `write_file`, `create_skill`, `read_file` and eighteen others were
REGISTERED. Tool selection is similarity to the question, capped at `question_max_tools` (5) for a
question, so for *"whats the wheater today?"* the five that scored highest were weather-shaped. A shell
is relevant to nearly everything and SIMILAR to nearly nothing, so it never appeared — and the model,
which can only see what it was offered, reported a limit of the system.

The user's point 3: confirm from the trace which tools were registered, offered and authorised, and do
NOT fix recovery by offering or authorising everything. A discovered alternative is still subject to
the matching authorisation.

So three separate things:

  * **registered** — what exists. The context pack now reports the count and, more usefully, the names
    it WITHHELD, which is the number that explains a refusal;
  * **offered** — what this turn put in front of the model. Unchanged, except that exactly one tool is
    pinned: `tool_search`, whose relevance is never topical because its job is finding the others.
    Pinning everything would put every side-effecting tool in front of the model on every turn;
  * **authorised** — per call, decided by `authority.decide` and already recorded on each receipt.
    Discovery grants visibility, never permission, and that is asserted here.

TARGETED tests. The integrated proof — that a live turn recovers from a failed tool by finding a
working one — belongs to the new pre-registered set, so this point stays PARTIAL.
"""
from __future__ import annotations

import pytest

from hmgfu.authority import decide
from hmgfu.session_plans import authorization_record
from hmgfu.tool_points import ALWAYS_OFFERED
from hmgfu.turn_events import registry_of

SCHEMAS = {"bash": {}, "write_file": {}, "create_widget": {}, "tool_search": {},
           "brave_web_search": {}, "memory_search": {}, "read_file": {}}


class _Tools:
    schemas = SCHEMAS


class _Engine:
    def __init__(self, plan=None):
        self.tools = _Tools()
        self._turn_plan = plan
        self._turn_effects_allowed = False
        self._turn_prohibited = False
        self._turn_user_message = "whats the wheater today?"


# --- the three states are distinguishable ---------------------------------------------------------------

def test_the_registry_is_reachable_for_the_trace():
    assert set(registry_of(_Engine()).schemas) == set(SCHEMAS)


def test_an_engine_without_a_registry_does_not_break_the_trace():
    class _Bare:
        pass
    assert registry_of(_Bare()).schemas == {}


def test_withheld_is_the_difference_that_explains_a_refusal():
    offered = {"brave_web_search", "create_widget", "tool_search"}
    withheld = sorted(n for n in SCHEMAS if n not in offered)
    assert "bash" in withheld and "write_file" in withheld


# --- exactly one tool is pinned, and it is the one that finds the others -----------------------------------

def test_tool_search_is_always_offered():
    assert "tool_search" in ALWAYS_OFFERED


def test_and_nothing_else_is():
    """The fix must not become "offer everything" — that is the failure mode the user named."""
    assert set(ALWAYS_OFFERED) == {"tool_search"}
    for risky in ("bash", "write_file", "create_widget", "create_skill", "remove_widget"):
        assert risky not in ALWAYS_OFFERED


# --- discovery is not permission ----------------------------------------------------------------------------

def _approved(step_text):
    return {"title": step_text[:80], "status": "active",
            "steps": [{"text": step_text, "status": "active"}],
            "authorization": authorization_record("user_approval", "yes", 4)}


def test_a_tool_found_by_discovery_still_needs_its_own_authorisation():
    """Finding `bash` does not authorise running it: the approved plan named a widget."""
    engine = _Engine(plan=_approved("create_widget: Valencia Weather"))
    got = decide(engine, "bash", {"command": "curl https://api.open-meteo.com/v1/forecast"})
    assert not got.allowed, "discovery granted permission"


def test_searching_for_tools_needs_no_authorisation_at_all():
    """`tool_search` reads; pinning it therefore adds no authority, only visibility."""
    engine = _Engine(plan=_approved("create_widget: Valencia Weather"))
    assert decide(engine, "tool_search", {"query": "http"}).allowed


def test_the_discovered_tool_is_allowed_once_the_plan_names_it():
    engine = _Engine(plan=_approved("bash: curl the forecast endpoint"))
    assert decide(engine, "bash", {"command": "curl https://api.open-meteo.com/v1/forecast"}).allowed


@pytest.mark.parametrize("tool", ["write_file", "create_widget"])
def test_no_side_effect_rides_in_on_a_search(tool):
    engine = _Engine(plan=_approved("tool_search: find an http client"))
    assert not decide(engine, tool, {"path": "x.txt", "type": "note"}).allowed


# --- 94.5c: discovery is for the turn that does not know what it needs ---------------------------------
#
# v2 states a precision contract: "an explicit memory-search request receives its applicable tool,
# without unrelated planning/tool-discovery noise." It is right, and my first pin broke it. Discovery
# exists for the turn that was never shown the capability it needed — the one that said "I cannot
# execute curl" while holding a shell. When the user named the tool, there is nothing to discover.

def test_discovery_is_not_added_when_the_turn_named_its_tools():
    from hmgfu.tool_points import retrieve_tools_for_turn

    class _Q:
        text = "search my memory for the launch party"
        requested_tools = ["memory_search"]
        action_requested = True
        intent = "task"
        conversation_act = "instruction"

    class _Reg:
        schemas = {"memory_search": {"name": "memory_search"}, "tool_search": {"name": "tool_search"}}

    class _Graph:
        points = {}

    class _Weights:
        def weights(self):
            return {}

    class _E:
        graph = _Graph()
        weight_learner = _Weights()

    names = [t["name"] for t in retrieve_tools_for_turn(_Reg(), _E(), _Q(), max_tools=4)]
    assert names == ["memory_search"], names
