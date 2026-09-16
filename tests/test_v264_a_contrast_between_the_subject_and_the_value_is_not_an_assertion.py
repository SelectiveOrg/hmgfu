"""J10 (T5 on v4, d95w21v4 rep3, instrument) — a contrast between the subject and the value is not an assertion.

"As we have clarified, it is essential to distinguish PXD-4 from "Packet Drop Daemon."" — the oracle's denial
class holds negations only, so the contrast read as the forbidden value asserted of the subject; the product had
asked at step 0 and answered "PXD-4 stands for Packet Delay Detector". Positive: a contrast (EN, PT) sets the value
apart. Preserve: a plain assertion still asserts; a contrast AFTER the assertion ("X is Y, as opposed to Z") keeps
Y asserted and Z apart; the negation forms are unchanged.
"""
from __future__ import annotations

from scripts.answer_oracle import answered

REP3 = ('Based on our recent discussions, **PXD-4** stands for **Packet Delay Detector**.  As we have clarified, it is '
        'essential to distinguish PXD-4 from "Packet Drop Daemon." While both terms might sound similar, **Packet Delay '
        'Detector** specifically focuses on measuring the latency.')


def test_a_contrast_sets_the_value_apart():
    """THE CONTRACT — fails before: 'distinguish PXD-4 from Packet Drop Daemon' asserts the forbidden value."""
    assert not answered(REP3, subject="PXD-4", value="Packet Drop Daemon")["ok"]
    assert answered(REP3, subject="PXD-4", value="Packet Delay Detector")["ok"]
    for t in ("PXD-4 is different from Packet Drop Daemon.", "PXD-4, not to be confused with Packet Drop Daemon, is a detector.",
              "Unlike Packet Drop Daemon, PXD-4 measures latency.", "O PXD-4 e diferente de Packet Drop Daemon.",
              "Nao confundir PXD-4 com Packet Drop Daemon.", "PXD-4, ao contrario de Packet Drop Daemon, mede a latencia."):
        assert not answered(t, subject="PXD-4", value="Packet Drop Daemon")["ok"], t


def test_the_assertion_and_the_negation_forms_hold():
    assert answered("PXD-4 means Packet Delay Detector.", subject="PXD-4", value="Packet Delay Detector")["ok"]
    r = answered("PXD-4 is Packet Delay Detector, as opposed to Packet Drop Daemon.", subject="PXD-4", value="Packet Delay Detector")
    assert r["ok"], r
    assert not answered("PXD-4 is Packet Delay Detector, as opposed to Packet Drop Daemon.", subject="PXD-4", value="Packet Drop Daemon")["ok"]
    assert not answered("PXD-4 is not Packet Drop Daemon.", subject="PXD-4", value="Packet Drop Daemon")["ok"]
