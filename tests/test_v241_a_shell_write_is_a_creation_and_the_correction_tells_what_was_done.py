"""95.56a + 95.56b (X5 on v5, d95w16v5 rep1 and g5cand rep2/rep3) — the op of a shell effect is what
the command does; a correction tells what the turn did.

The model wrote memorando.md with `echo "MEMORANDO-IBIS" > memorando.md` and reported it; every bash
effect was recorded as a REMOVAL (a pre-93 table), so the true "create" claim had no supporting
operation and the reply was replaced by "(Correction: nothing was actually written ...)" — a false
correction of a true report, 3/3. Positive: a shell write is a creation, a shell removal a removal,
the report stands; a class mismatch with operations on file names the claim and the work, never
"nothing was written". Preserve: remove_widget removes; with no operation the old correction stands.
"""
from __future__ import annotations

from hmgfu.authority import shell_removes
from hmgfu.saydo import CORRECTION, classify, transactions_of
from hmgfu.saydo_corrections import correction_for


def _correction_for(classes, tx):
    return correction_for(classes, tx.get("operations") or [])

WRITE = [{"name": "bash", "arguments": {"command": 'echo "MEMORANDO-IBIS" > memorando.md && echo "5566778899" >> memorando.md'}}]
REMOVE = [{"name": "bash", "arguments": {"command": "rm memorando.md"}}]


def test_a_shell_write_creates_and_a_shell_removal_removes():
    """THE CONTRACT — fails before: the write is recorded as a removal."""
    assert [o["op"] for o in transactions_of(WRITE, [], None)["operations"]] == ["create"]
    assert [o["op"] for o in transactions_of(REMOVE, [], None)["operations"]] == ["remove"]
    assert transactions_of(WRITE, [], None)["effects_remove"] == 0
    assert [o["op"] for o in transactions_of([{"name": "remove_widget", "arguments": {"id": "w1"}}], [], None)["operations"]] == ["remove"]
    for c, want in (("cat a.txt && rm b.txt", True), ("git rm old.md", True), ("/bin/rm -f x", True),
                    ("echo x > f", False), ("printf 'a' >> f", False), ("mkdir out", False), ("", False)):
        assert shell_removes(c) is want, c


def test_the_true_report_of_a_shell_write_stands():
    tx = transactions_of(WRITE, [], None, episode=True)
    c = classify("Criei o memorando.md com o texto MEMORANDO-IBIS e adicionei o numero 5566778899.", WRITE, tx)
    assert c["exec_claim"] and not c["false_exec_claim"], c


def test_a_correction_with_operations_on_file_tells_what_was_done():
    """THE CONTRACT (95.56b) — fails before: the correction says nothing was written after a write."""
    tx = transactions_of(WRITE, [], None, episode=True)
    c = classify("Apaguei o memorando.md.", WRITE, tx)
    assert c["false_exec_claim"] and c["unsupported_claims"] == ["remove"]
    text = _correction_for(c["unsupported_claims"], tx)
    assert "did not remove" in text and "create tool:bash" in text and "nothing was actually written" not in text
    assert _correction_for(["create"], transactions_of([], [], None)) == CORRECTION
