"""95.71 (X7 on v6, 0/3) — the deferral "nao avances sem a minha luz verde" and the end-of-need cancel "ja nao e preciso".

"Prepara um ficheiro rascunho.md com o texto RASCUNHO-HERON, mas nao avances sem a minha luz verde." was not read
as deferred (the class knew "wait for / espera pela / so quando eu mandar"), so the model's plan was born ACTIVE,
and "Deixa la, ja nao e preciso." declined a proposal that did not exist while the cancel class did not hold a
stated end of need, so the plan stayed active. Positive: the deferral defers (EN, PT) and the end of need cancels
an active plan. Preserve: the earlier deferral wordings; a plain order; a "deixa" that is not an end of need.
"""
from __future__ import annotations

from hmgfu.session_plans import _CANCEL, begin_turn
from hmgfu.speech_act import is_deferred_to_confirmation, is_suggestion
from tests.test_v2_agent import make_agent

X7 = "Prepara um ficheiro rascunho.md com o texto RASCUNHO-HERON, mas nao avances sem a minha luz verde."


def test_the_green_light_deferral_and_its_kin_defer():
    """THE CONTRACT — fails before: X7's wording is not a deferral."""
    for t in (X7, "Escreve o resumo.md, mas nao prossigas sem a minha autorizacao.",
              "Draft summary.md, but don't proceed without my go-ahead.", "Write it, but never start without my green light."):
        assert is_deferred_to_confirmation(t) and is_suggestion(t), t
    assert is_deferred_to_confirmation("Prepara um ficheiro sumario.md com o texto SUMARIO-IBIS, mas fica a espera da minha ordem.")
    assert not is_deferred_to_confirmation("Prepara um ficheiro rascunho.md com o texto RASCUNHO-HERON.")


def test_the_end_of_need_cancels_an_active_plan(tmp_path):
    """THE CONTRACT — fails before: 'Deixa la, ja nao e preciso.' is no cancel and the plan stays active."""
    for t in ("Deixa la, ja nao e preciso.", "Ja nao e necessario, obrigado.", "Never mind, it's no longer needed."):
        assert _CANCEL.search(t), t
    assert not _CANCEL.search("Deixa-me pensar um pouco.")
    engine, _ = make_agent(tmp_path, [])
    engine._turn_user_message = "Cria o rascunho.md"
    engine.session_plans.save("s1", {"title": "Criar o ficheiro rascunho.md", "status": "active",
                                     "steps": [{"text": "Criar o ficheiro rascunho.md", "status": "active"}],
                                     "authorization": {"origin": "user_request", "message": "Cria o rascunho.md", "turn_seq": 1}})
    engine._turn_plan = None
    begin_turn(engine, "s1", "Deixa la, ja nao e preciso.")
    assert engine.session_plans.get("s1")["status"] == "abandoned"
