"""Phase 90.D2 — the span extractor's contract text must name every closed slot family the store has, and must say that a stated
current preference counts as a favourite. Live/DEV defect (90.D1): 'My main project is a Java billing API' and 'Ultimamente prefiro chá
de gengibre' were returned as no-fact by the chat-role model because the prompt listed no 'project' and read 'prefer' as an excluded
opinion. Deterministic: no model call."""
from __future__ import annotations

from hmgfu import slots
from hmgfu.fact_spans import SPAN_PROMPT

# slot family → at least one of these cue words must appear in the prompt
CUES = {
    "identity": ["name", "live", "job", "employer", "birthday"],
    "family": ["family member"],
    "pet": ["pet"],
    "pref": ["favourite"],
    "project": ["project"],
    "asset": ["car", "link"],
    "misc": ["number", "timezone"],
}


def test_every_slot_family_has_a_cue_in_the_prompt():
    prompt = SPAN_PROMPT.lower()
    families = sorted({k.split(".")[0] for k in slots.SLOTS})
    missing = [f for f in families if not any(c in prompt for c in CUES[f])]
    assert not missing, f"slot families the extractor is never asked about: {missing}"


def test_a_stated_preference_counts_as_a_favourite():
    prompt = SPAN_PROMPT.lower()
    assert "prefer" in prompt and "favourite" in prompt


def test_the_exclusions_still_stand():
    prompt = SPAN_PROMPT.lower()
    for word in ("questions", "hypotheticals", "fiction", "other people", "quotes", "past facts", "plans", "guesses", "advice"):
        assert word in prompt, word
