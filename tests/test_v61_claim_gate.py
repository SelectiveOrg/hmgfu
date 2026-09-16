"""Phase 77.4 — claim-level abstention: the reply's novel words must be in the evidence; the gate re-asks once, then
abstains with an explicit no-record statement; OFF by default until the measurement."""
from __future__ import annotations

from hmgfu.grounding import NO_RECORD, unsupported_answer_terms, unsupported_share, verify_claims


def test_unsupported_terms_are_the_replys_novel_words_absent_from_the_evidence():
    ev = ["Your favorite color is chartreuse", "I fixed the broken fence on the east side."]
    q = "Which task did I complete first, fixing the fence or purchasing three cows from Peter?"
    u, n = unsupported_answer_terms("You purchased the cows from Peter before fixing the fence.", q, ev)
    assert u == [] and n == ["purchased", "before"] or ("purchased" in n and "cows" not in n)   # question words are not novel
    u2, n2 = unsupported_answer_terms("Your favorite color is chartreuse.", "what is my favorite color?", ev)
    assert u2 == [] and n2 == ["chartreuse"]
    u3, n3 = unsupported_answer_terms("Your favorite color is magenta, chosen in Lisbon.", "what is my favorite color?", ev)
    assert set(u3) == {"magenta", "chosen", "lisbon"} and unsupported_share("Your favorite color is magenta, chosen in Lisbon.", "what is my favorite color?", ev) == 1.0
    assert unsupported_share("", "q", ev) == 0.0


class _S:
    def __init__(self, on, floor): self.d = {"claim_gate_enabled": on, "claim_gate_floor": floor}
    def get(self, k): return self.d.get(k)


class _E:
    def __init__(self, on, floor=0.5): self.settings = _S(on, floor); self.events = []
    def _emit(self, ev): self.events.append(ev)


class _Provider:
    def __init__(self, fixed): self.fixed = fixed
    def chat(self, model, messages, **kw): return {"content": self.fixed}


def test_gate_off_passes_through_and_on_reasks_then_abstains():
    ev = ["Your favorite color is chartreuse"]
    q = "what is my favorite color?"
    reply = "Your favorite color is magenta, chosen in Lisbon."
    e = _E(False)
    assert verify_claims(e, reply, q, ev, [], _Provider("x"), "m", 1) == (reply, None)
    e = _E(True)
    fixed, rep = verify_claims(e, reply, q, ev, [], _Provider("Your favorite color is chartreuse."), "m", 1)
    assert fixed == "Your favorite color is chartreuse." and rep["repaired"] == ["magenta", "chosen", "lisbon"] and e.events[-1]["ok"]
    e = _E(True)
    fixed, rep = verify_claims(e, reply, q, ev, [], _Provider("It is magenta, from Lisbon."), "m", 2)
    assert fixed == NO_RECORD and rep["abstained"] and e.events[-1]["abstained"]
    e = _E(True)
    assert verify_claims(e, "Your favorite color is chartreuse.", q, ev, [], _Provider("x"), "m", 3)[1] is None   # supported: untouched
