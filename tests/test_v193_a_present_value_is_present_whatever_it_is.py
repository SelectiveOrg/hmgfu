"""95.15 (E7 c95c rep2) — a present value is present, whatever it is.

The model counted 0 and called create_widget(type=metric, props={value: 0}) twice; both were refused
with "metric widget needs props ['value']" because the required-props check used truthiness, so the
retry guard blocked the tool and the reply had to explain a "technical issue". Zero is a value; whether
it is traceable is the provenance guard's question. Positive: value 0 passes the props check. Negative:
a missing value and an empty string are still refused. Variant: a synonym does not overwrite a
canonical 0. Preserve: a real value still passes.
"""
from __future__ import annotations

from hmgfu.widgets import enrich_widget_args


def test_a_zero_value_is_a_value():
    """THE CONTRACT — fails before: 0 is 'missing'."""
    props, err = enrich_widget_args(None, "metric", {"type": "metric", "title": "Count", "props": {"value": 0}})
    assert err is None and props["value"] == 0, (props, err)


def test_a_missing_value_is_still_refused():
    _p, err = enrich_widget_args(None, "metric", {"type": "metric", "title": "Count"})
    assert err and "value" in err


def test_an_empty_string_is_still_refused():
    _p, err = enrich_widget_args(None, "metric", {"type": "metric", "title": "Count", "props": {"value": ""}})
    assert err and "value" in err


def test_a_synonym_does_not_overwrite_a_canonical_zero():
    props, err = enrich_widget_args(None, "metric", {"type": "metric", "props": {"value": 0, "number": 7}})
    assert err is None and props["value"] == 0


def test_a_real_value_still_passes():
    props, err = enrich_widget_args(None, "metric", {"type": "metric", "props": {"value": 11}})
    assert err is None and props["value"] == 11
