"""92.E5R — watch one turn at the two boundaries that decide attribution.

Shared by the C/L probe and the learning matrix, because both need the same two facts and neither
should carry its own copy: what the MODEL was actually given (the composed system message, not the
argument some producer was handed) and what the CONTROLLER decided (what was proposed, what was
resolved). With those two, a failure can be placed in the router, the contract, the store or the
reader instead of being blamed on "the model".

Nothing here is imported by the product: it wraps the two functions from the outside, for the length
of one turn, and puts them back.
"""
from __future__ import annotations

HEADER = "CONFIRMED INTERPRETATIONS"


class TurnCapture:
    """Context manager: `with TurnCapture() as t:` around one turn."""

    def __init__(self):
        self.payloads = []
        self.decisions = []

    def __enter__(self):
        from hmgfu import learning_protocol, turn_router
        self._tr, self._lp = turn_router, learning_protocol
        self._classify, self._decide = turn_router.classify_turn, learning_protocol.decide

        def classify(chat, *a, **kw):
            def capture(role, messages, **kwargs):
                self.payloads.append("\n".join(m.get("content", "") for m in messages))
                return chat(role, messages, **kwargs)
            return self._classify(capture, *a, **kw)

        def decide(snap, env):
            out = self._decide(snap, env)
            props = (env or {}).get("proposals") or []
            self.decisions.append({
                "proposed": [{"kind": p.get("kind"), "subject_ref": p.get("subject_ref"),
                              "value": p.get("value")} for p in props],
                "action": out.get("action"), "reason": out.get("reason"),
                "envelope_present": env is not None and env != {}})
            return out

        turn_router.classify_turn, learning_protocol.decide = classify, decide
        return self

    def __exit__(self, *exc):
        self._tr.classify_turn, self._lp.decide = self._classify, self._decide
        return False

    @property
    def router_called(self) -> bool:
        return bool(self.payloads)

    def delivered_block(self) -> str:
        """The confirmed-interpretation block as the MODEL received it, or "".

        Read by its header rather than by a fixed needle: selection is by the newest case's context,
        so once a turn commits, the block offered next is a DIFFERENT example -- a fixed needle would
        report a delivered example as missing."""
        for payload in self.payloads:
            if HEADER in payload:
                tail = payload.split(HEADER, 1)[1]
                lines = [ln for ln in tail.split(chr(10)) if ln.strip().startswith("-")]
                if lines:
                    return chr(10).join(lines).strip()
        return ""

    def contains(self, needle: str) -> bool:
        return bool(needle) and any(needle in p for p in self.payloads)

    def decision(self) -> dict:
        return self.decisions[-1] if self.decisions else {
            "proposed": [], "action": None, "reason": "no envelope", "envelope_present": False}
