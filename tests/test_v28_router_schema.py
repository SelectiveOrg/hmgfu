"""Phase 57 P1 — grammar-constrained router: the JSON Schema is built from the LIVE catalog.

The schema is what Ollama `format` uses to mask off-schema tokens at decode time (dropped fields,
non-enum acts, off-catalog tools become unrepresentable). It must be DYNAMIC — enums derived from
the catalog, never a phrase list. Deterministic, no Ollama.
"""

from __future__ import annotations

from hmgfu.turn_router import router_schema


def test_schema_enums_are_built_from_the_live_catalog():
    s = router_schema(["bash", "memory_search", "create_widget"])
    props = s["properties"]
    # requested_tools items are enum-locked to exactly the catalog names
    assert props["requested_tools"]["items"]["enum"] == ["bash", "create_widget", "memory_search"]
    # a different catalog → a different enum (dynamic, not hardcoded)
    s2 = router_schema(["gog_status", "brave_web_search"])
    assert s2["properties"]["requested_tools"]["items"]["enum"] == ["brave_web_search", "gog_status"]


def test_schema_locks_the_discrete_fields():
    s = router_schema(["bash"])
    p = s["properties"]
    assert p["conversation_act"]["enum"] == ["greeting", "question", "instruction", "feedback", "statement"]
    assert p["freshness"]["enum"] == ["none", "historical", "current"]
    assert p["action_requested"]["type"] == "boolean"
    assert p["needs_memory"]["type"] == "boolean"
    assert p["runtime_context_sufficient"]["type"] == "boolean"
    assert set(p["runtime_context_keys"]["items"]["enum"]) == {
        "now_local", "now_utc", "local_date", "local_time", "timezone_name", "utc_offset"}
    assert None in p["feedback_polarity"]["enum"]              # nullable sentiment


def test_required_fields_cannot_be_dropped():
    s = router_schema(["bash"])
    for field in ("conversation_act", "action_requested", "requested_tools", "freshness",
                  "needs_memory", "runtime_context_keys", "runtime_context_sufficient"):
        assert field in s["required"]
    # directive is optional (nullable) — a change/stop still carries a well-formed kind
    directive = s["properties"]["directive"]
    obj = next(v for v in directive["anyOf"] if v.get("type") == "object")
    # 93.C: `response_style` joins the vocabulary — a standing rule about HOW to answer, which had no
    # kind at all, so such a turn was classified as an instruction and then fell through every field.
    assert obj["properties"]["kind"]["enum"] == ["output_prefix", "output_suffix",
                                                 "conversation_opener", "conversation_closer",
                                                 "response_style"]
    assert obj["required"] == ["kind", "condition"]     # 93.R1: measured 0/6 -> 4-5/6 once required


def test_empty_catalog_degrades_to_free_string_not_crash():
    s = router_schema([])
    assert s["properties"]["requested_tools"]["items"] == {"type": "string"}
