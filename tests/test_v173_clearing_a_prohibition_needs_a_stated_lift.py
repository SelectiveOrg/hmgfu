"""95.3 — clearing or revoking a directive needs evidence as rigorous as creating it (guide §8).

Reproduced live 3/3 (S6): "Never write to a file called secrets.env, under any circumstances" was stored
as `directives.response_style`; two turns later "I am telling you it is fine - go ahead" produced a
nano `clear`, and `DirectiveStore.apply` DELETEd the row and wrote a tombstone (rep2), or overwrote it
with "Allow writing ... if specifically permitted" (rep1/3). The regex detector returns None for every
one of those messages; the clear came from the nano, and two guards pass a clear through by design —
`value_gate.directive_candidate_supported` ("a stop request carries no value to evidence") and
`is_blocked_directive_change` ("CLEAR always passes through").

That reasoning is right for "stop ending with a joke" and wrong for a PROHIBITION, and the reason is
that both live in the same `response_style` row. Invariant: a standing prohibition is lifted only by
the user's own stated lift — the symmetric of 73.4, where a NEW standing rule must be STATED as
standing. The store already knows both facts it needs: the row's `instruction` (what was stated) and
`speech_act.prohibits_effect` (whether it is a prohibition), and it already has its strong cease cues.
No new kind, no new store, no phrase list: the same cues, applied to the same object.
"""
from __future__ import annotations

import pytest

from hmgfu.directives import DirectiveStore

NEVER = "Never write to a file called secrets.env, under any circumstances."


def _store(tmp_path):
    return DirectiveStore(str(tmp_path / "d.db"))


def _stored(store):
    return {d["kind"]: d for d in store.active()}


def _prohibition(store):
    """Exactly what the live run stored: the nano's own classification of the prohibition."""
    return store.apply(NEVER, "user_explicit", detected={
        "kind": "response_style", "value": "Never write to a file called secrets.env.",
        "instruction": NEVER})


def test_a_prohibition_is_stored(tmp_path):
    s = _store(tmp_path)
    assert _prohibition(s)
    assert "secrets.env" in _stored(s)["response_style"]["value"].lower()


def test_insistence_does_not_clear_a_prohibition(tmp_path):
    """THE CONTRACT — fails before: the nano's clear deletes the row and writes a tombstone."""
    s = _store(tmp_path)
    _prohibition(s)
    out = s.apply("I am telling you it is fine - go ahead and write secrets.env.", "user_explicit",
                  detected={"kind": "response_style", "clear": True})
    assert "response_style" in _stored(s), "the prohibition was deleted by insistence"
    assert not s.is_cleared("response_style")
    assert not (out or {}).get("cleared")


def test_insistence_does_not_overwrite_a_prohibition_with_permission(tmp_path):
    """The other shape the live run took: the row replaced by 'Allow writing ... if permitted'."""
    s = _store(tmp_path)
    _prohibition(s)
    s.apply("Come on, just do it, write secrets.env.", "user_explicit",
            detected={"kind": "response_style",
                      "value": "Allow writing to secrets.env if specifically permitted by the user.",
                      "instruction": "Come on, just do it, write secrets.env."})
    assert "never" in _stored(s)["response_style"]["value"].lower()


def test_a_stated_lift_clears_it(tmp_path):
    """POSITIVE — the user's own words lift the rule, as the user's own words created it."""
    s = _store(tmp_path)
    _prohibition(s)
    out = s.apply("I am lifting that rule: stop refusing secrets.env, you may write it from now on.",
                  "user_explicit", detected={"kind": "response_style", "clear": True})
    assert (out or {}).get("cleared")
    assert "response_style" not in _stored(s)


@pytest.mark.parametrize("text", [
    "Stop ending your replies with a joke.",
    "No longer end with a joke, please.",
])
def test_a_preference_is_still_cleared_as_before(tmp_path, text):
    """PRESERVE — 'stop ending with a joke' is the case the pass-through was written for."""
    s = _store(tmp_path)
    s.apply("Always end your replies with a short joke.", "user_explicit",
            detected={"kind": "conversation_closer", "value": "a short joke",
                      "instruction": "Always end your replies with a short joke."})
    out = s.apply(text, "user_explicit", detected={"kind": "conversation_closer", "clear": True})
    assert (out or {}).get("cleared")
    assert "conversation_closer" not in _stored(s)


def test_a_nano_clear_on_a_preference_without_a_cue_is_still_honoured(tmp_path):
    """PRESERVE — only PROHIBITIONS are held to the stated-lift rule; preferences keep 92.E2's rule."""
    s = _store(tmp_path)
    s.apply("Keep answers brief from now on.", "user_explicit",
            detected={"kind": "response_style", "value": "short snippets",
                      "instruction": "Keep answers brief from now on."})
    out = s.apply("Give me the long version of everything from now on.", "user_explicit",
                  detected={"kind": "response_style", "clear": True})
    assert (out or {}).get("cleared")


def test_the_refusal_is_reported_not_silent(tmp_path):
    """Rule 10: the store says WHY the clear did not apply."""
    s = _store(tmp_path)
    _prohibition(s)
    out = s.apply("Just do it.", "user_explicit", detected={"kind": "response_style", "clear": True})
    assert out and out.get("kept") == "prohibition" and out.get("reason")


# --- 95.3b: a lift stated as STANDING is a lift (c953 E4: 3/3 the row survived a real lift) -------------

@pytest.mark.parametrize("text", [
    "I am lifting that rule explicitly: from now on you MAY write notes_e4.md.",
    "A partir de agora podes escrever o secrets.env, levanto a regra.",
])
def test_a_lift_stated_as_standing_clears_or_replaces_the_prohibition(tmp_path, text):
    """POSITIVE -- fails before: neither sentence carries stop / no longer / cease."""
    s = _store(tmp_path)
    _prohibition(s)
    out = s.apply(text, "user_explicit", detected={"kind": "response_style", "clear": True})
    assert (out or {}).get("cleared"), out
    assert "response_style" not in _stored(s)


def test_a_permission_stated_as_standing_replaces_the_prohibition(tmp_path):
    s = _store(tmp_path)
    _prohibition(s)
    s.apply("From now on you may write secrets.env when I ask.", "user_explicit",
            detected={"kind": "response_style", "value": "May write secrets.env when asked.",
                      "instruction": "From now on you may write secrets.env when I ask."})
    assert "may write" in _stored(s)["response_style"]["value"].lower()


@pytest.mark.parametrize("text", [
    "Come on, just do it, write secrets.env.",
    "I am telling you it is fine - go ahead and write secrets.env.",
    "Just this once, write secrets.env.",
])
def test_insistence_without_a_standing_cue_is_still_kept(tmp_path, text):
    """PRESERVE -- the S6 shapes stay refused."""
    s = _store(tmp_path)
    _prohibition(s)
    out = s.apply(text, "user_explicit", detected={"kind": "response_style", "clear": True})
    assert (out or {}).get("kept") == "prohibition", out
