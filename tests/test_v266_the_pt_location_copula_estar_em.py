"""95.68 (N2/N4 on v6, 0/3 both arms) — the PT location copula "estou/estás/está/estamos em" joins the location class.

"Mudanca de casa: ja nao estou em Chimoio, agora estou em Xai-Xai." wrote nothing (the class knew moro/vivo/resido
and the "agora estou em" half only inside the relocation chain). Positive: the sentence writes Xai-Xai, the denied
Chimoio is not written, and the store supersedes. Preserve: "moro em" unchanged; a third party's "está em" writes
nothing; the relocation chain still keeps the last place.
"""
from __future__ import annotations

from hmgfu.facts import FactStore
from hmgfu.fact_detect import detect_facts

N2 = "Mudanca de casa: ja nao estou em Chimoio, agora estou em Xai-Xai."


def _pairs(dets):
    return [(d["key"], d["value"]) for d in dets if d.get("value")]


def test_estar_em_writes_the_current_place_and_not_the_denied_one():
    """THE CONTRACT — fails before: nothing is written."""
    assert _pairs(detect_facts(N2)) == [("identity.location", "Xai-Xai")], detect_facts(N2)
    assert _pairs(detect_facts("Agora estou em Xai-Xai.")) == [("identity.location", "Xai-Xai")]
    assert _pairs(detect_facts("Estamos em Valencia desde marco.")) and _pairs(detect_facts("Estamos em Valencia desde marco."))[0][1].startswith("Valencia")


def test_the_store_supersedes_and_the_other_forms_hold(tmp_path):
    store = FactStore(str(tmp_path / "a.db"))
    store.apply_all("I live in Chimoio.", "user_explicit", session="s0")
    store.apply_all(N2, "user_explicit", session="s1")
    assert [f["value"] for f in store.active() if f["key"] == "identity.location"] == ["Xai-Xai"]
    assert _pairs(detect_facts("Moro em Xai-Xai.")) == [("identity.location", "Xai-Xai")]
    assert _pairs(detect_facts("O Rui esta em Valencia.")) == []
    assert _pairs(detect_facts("Mudei para Aveiro. Depois para Tete. Agora estou em Quelimane."))[-1] == ("identity.location", "Quelimane")
