"""92.E5R — the oracle itself, before it is trusted to grade anything.

An instrument that grades a campaign has to be shown to fail the cases it is meant to catch. The one
it replaces passed all of them: `bool(new_definition) == should_commit` accepted an inverted
definition, a definition of the wrong term, and could not see an undue write in another store at all.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from learning_oracle import (DEFINITION_RELATION, definition_written, delta, judge_turn,  # noqa: E402
                             undue_writes)

CTX = "project terminology"


def _def(term, meaning, ctx=CTX):
    return ("assertions", (f"{ctx}::{term}", DEFINITION_RELATION), None, meaning)


def test_a_correct_definition_passes():
    assert definition_written([_def("ACME-7", "Atlas Control Mesh")], "ACME-7", "Atlas Control Mesh")


def test_an_inverted_definition_fails():
    """The case the old oracle scored as a PASS, and the reason the teaching looked successful."""
    inverted = [_def("Cluster Routing Daemon", "CRD-3")]
    assert not definition_written(inverted, "CRD-3", "Cluster Routing Daemon")
    assert judge_turn(inverted, expect_definition=("CRD-3", "Cluster Routing Daemon"))["correct"] is False


def test_a_definition_of_the_wrong_term_fails():
    assert not definition_written([_def("BETA-2", "Atlas Control Mesh")], "ACME-7", "Atlas Control Mesh")


def test_the_context_is_checked_when_one_is_required():
    other = [_def("ACME-7", "Atlas Control Mesh", ctx="internal naming conventions")]
    assert definition_written(other, "ACME-7", "Atlas Control Mesh")
    assert not definition_written(other, "ACME-7", "Atlas Control Mesh", context=CTX)


def test_punctuation_and_spacing_do_not_decide_correctness():
    assert definition_written([_def("ACME-7", " Atlas  Control Mesh. ")], "ACME-7", "Atlas Control Mesh")


def test_a_write_in_another_store_is_visible():
    """The old oracle only read definitions, so this delta was invisible to every negative."""
    changes = [("facts", "pref.ticket", None, "IOTA-7 - my favourite ticket this week.")]
    assert undue_writes(changes) == changes
    assert judge_turn(changes, expect_definition=None)["correct"] is False


def test_a_declared_allowance_is_not_an_undue_write():
    """A negative may legitimately state a preference; what is allowed is labelled up front."""
    changes = [("facts", "pref.ticket", None, "IOTA-7")]
    assert undue_writes(changes, [{"store": "facts", "key": "pref."}]) == []
    assert judge_turn(changes, expect_definition=None,
                      allowed=[{"store": "facts", "key": "pref."}])["correct"] is True


def test_a_turn_that_must_define_nothing_fails_when_it_defines_something():
    assert judge_turn([_def("GAMMA-3", "a nice name")], expect_definition=None)["definition_ok"] is False


def test_delta_sees_changes_removals_and_additions():
    before = {"facts": {"a": "1", "b": "2"}, "assertions": {}, "directives": {}}
    after = {"facts": {"a": "9", "c": "3"}, "assertions": {}, "directives": {}}
    assert delta(before, after) == [("facts", "a", "1", "9"), ("facts", "b", "2", None),
                                    ("facts", "c", None, "3")]


def test_the_required_definition_is_not_counted_as_an_undue_write():
    changes = [_def("DELTA-9", "Dynamic Ledger Transfer Adapter")]
    assert judge_turn(changes, expect_definition=("DELTA-9", "Dynamic Ledger Transfer Adapter"))["correct"]


def test_the_term_comes_from_the_entities_table_not_from_the_opaque_id():
    """What the pilot caught: upsert_entity mints `definition:<hash8>` and keeps `<ctx>::<term>`
    elsewhere, so an oracle that parses the id grades a CORRECT definition as wrong."""
    opaque = [("assertions", ("definition:4c528072", DEFINITION_RELATION), None,
               "Dynamic Ledger Transfer Adapter")]
    names = {"definition:4c528072": f"{CTX}::delta-9"}
    assert not definition_written(opaque, "DELTA-9", "Dynamic Ledger Transfer Adapter")
    assert definition_written(opaque, "DELTA-9", "Dynamic Ledger Transfer Adapter", names=names)
    assert judge_turn(opaque, expect_definition=("DELTA-9", "Dynamic Ledger Transfer Adapter"),
                      names=names)["correct"]


def test_an_inverted_definition_still_fails_once_names_resolve():
    inverted = [("assertions", ("definition:aa11bb22", DEFINITION_RELATION), None, "CRD-3")]
    names = {"definition:aa11bb22": f"{CTX}::cluster routing daemon"}
    assert not definition_written(inverted, "CRD-3", "Cluster Routing Daemon", names=names)
