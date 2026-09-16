"""Phase 90.1 — the grounding gate must read a URL the way a reader does: markdown emphasis and surrounding punctuation are not
part of the address. Live defect (2026-09-07, turn 8): a correct URL found by memory_search was stripped from the reply because the
claim kept the trailing `**` and matched no evidence. Synthetic URLs only. A URL absent from the evidence stays flagged."""
from __future__ import annotations

import pytest

from hmgfu.grounding import ungrounded_claims

URL = "http://198.51.100.7/ui/sharing/0123456789abcdef0123456789abcdef"
EVIDENCE = ["The user provided a new tracking link: `" + URL + "`. Noted.", "Macro: links were shared recently."]


@pytest.mark.parametrize("reply", [
    "Here is the new link: **" + URL + "**",
    "Here is the new link: " + URL + ".",
    "Here it is (" + URL + ")",
    "Here it is [" + URL + "]",
    "Two forms: " + URL + ", as before.",
    "In markdown: [tracking](" + URL + ")",
    "Emphasis: *" + URL + "*",
    "Underscored: __" + URL + "__",
])
def test_markdown_and_punctuation_are_not_part_of_the_url(reply):
    assert ungrounded_claims(reply, EVIDENCE) == []


def test_a_url_absent_from_the_evidence_is_still_flagged():
    other = "http://198.51.100.7/ui/sharing/ffffffffffffffffffffffffffffffff"
    assert ungrounded_claims("The link is **" + other + "**", EVIDENCE) == [other]
    assert ungrounded_claims("The link is " + other, EVIDENCE) == [other]


def test_a_different_path_is_not_grounded_by_a_prefix_match():
    longer = URL + "extra"
    assert ungrounded_claims("Link: " + longer, EVIDENCE) == [longer]
