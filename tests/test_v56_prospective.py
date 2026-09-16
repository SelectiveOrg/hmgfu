"""Phase 75.2 — prospective memory: deterministic PT/EN trigger detection (time / condition / cancel; recall questions
are NOT triggers), due resolution against a frozen clock, firing at turn start (never on the setting turn), store
lifecycle, and the turn hook's prompt block + events."""
from __future__ import annotations

from hmgfu.prospective import (ProspectiveStore, begin_turn, condition_fires, detect, due_now, render_fired, salient)

NOW = "2026-09-05T14:30:00+02:00"          # a Saturday


def test_detect_time_triggers_pt_en():
    t = detect("lembra-me amanhã às 9 de ligar ao João", NOW)
    assert t["kind"] == "time" and t["due"] == "2026-09-06T09:00:00+02:00" and t["text"] == "ligar ao João"
    t = detect("Remind me to send the invoice tomorrow at 5pm", NOW)
    assert t["kind"] == "time" and t["due"] == "2026-09-06T17:00:00+02:00" and t["text"] == "send the invoice"
    t = detect("please remind me in 20 minutes to check the oven", NOW)
    assert t["kind"] == "time" and t["due"] == "2026-09-05T14:50:00+02:00" and "check the oven" in t["text"]
    t = detect("avisa-me daqui a 2 horas para tirar a roupa", NOW)
    assert t["kind"] == "time" and t["due"] == "2026-09-05T16:30:00+02:00"
    t = detect("remind me on monday to call the clinic", NOW)
    assert t["kind"] == "time" and t["due"].startswith("2026-09-07T09:00")          # next Monday, default hour
    t = detect("lembra-me na segunda-feira de pagar a renda", NOW)
    assert t["kind"] == "time" and t["due"].startswith("2026-09-07T09:00")
    t = detect("remind me at 9 to take the pills", NOW)                             # 9 is past today → tomorrow 9
    assert t["kind"] == "time" and t["due"] == "2026-09-06T09:00:00+02:00"
    t = detect("remind me tonight to water the plants", NOW)
    assert t["kind"] == "time" and t["due"] == "2026-09-05T20:00:00+02:00"


def test_detect_condition_triggers_and_cancel():
    t = detect("remind me to send the invoice when Nelson replies", NOW)
    assert t["kind"] == "condition" and "nelson" in t["keywords"] and t["text"] == "send the invoice"
    t = detect("lembra-me de comprar pão quando eu falar do mercado", NOW)
    assert t["kind"] == "condition" and "mercado" in t["keywords"] and t["text"] == "comprar pão"
    assert detect("cancel that reminder", NOW) == {"kind": "cancel"}
    assert detect("cancela o lembrete, por favor", NOW) == {"kind": "cancel"}


def test_recall_questions_and_plain_statements_are_not_triggers():
    for text in ("remind me what I said about the printer", "lembra-me o que eu disse ontem", "remind me who Nelson is",
                 "what is my favourite colour?", "if it rains tomorrow I will stay home", "I need to call João tomorrow",
                 "remind me to call João", ""):
        assert detect(text, NOW) is None, text


def test_condition_fires_on_salient_words_only():
    kw = salient("Nelson replies about the invoice")
    assert "nelson" in kw and "invoice" in kw and "replies" not in kw
    assert condition_fires(kw, "Nelson just replied about the invoice, what now?")
    assert not condition_fires(kw, "what is the weather like today?")
    assert not condition_fires([], "anything")


def test_store_and_due_now_never_fire_on_the_setting_turn(tmp_path):
    st = ProspectiveStore(str(tmp_path / "p.db"))
    t = st.add("s", detect("remind me in 10 minutes to stretch", NOW), 3, "remind me in 10 minutes to stretch")
    c = st.add("s", detect("remind me to send the invoice when Nelson replies", NOW), 3, "…")
    assert [x["status"] for x in st.pending()] == ["pending", "pending"]
    assert due_now(st, "2026-09-05T14:45:00+02:00", "hello", 3) == []                # same turn: never
    assert [x["id"] for x in due_now(st, "2026-09-05T14:35:00+02:00", "hello", 4)] == []   # not yet due
    assert [x["id"] for x in due_now(st, "2026-09-05T14:45:00+02:00", "hello", 4)] == [t["id"]]
    assert [x["id"] for x in due_now(st, "2026-09-05T14:31:00+02:00", "Nelson replied", 5)] == [c["id"]]
    st.set_status(t["id"], "fired", 4)
    assert st.get(t["id"])["status"] == "fired" and st.get(t["id"])["fired_turn"] == 4
    assert st.cancel_latest()["id"] == c["id"] and st.pending() == []
    assert "reminders the user asked for" in render_fired([t])
    st.close()


class _Runtime:
    def __init__(self, now): self.now_local = now


class _Settings:
    def __init__(self, on): self._on = on
    def get(self, k): return self._on if k == "prospective_enabled" else None


class _Engine:
    def __init__(self, tmp_path, on=True):
        self.prospective = ProspectiveStore(str(tmp_path / "p.db"))
        self.settings = _Settings(on)
        self.events = []
    def _emit(self, ev): self.events.append(ev)


def test_begin_turn_sets_fires_and_cancels_with_events(tmp_path):
    e = _Engine(tmp_path, on=False)
    assert begin_turn(e, "s", "remind me in 5 minutes to stretch", _Runtime(NOW), 1) == "" and e.events == []
    e = _Engine(tmp_path / "on", on=True) if False else _Engine.__new__(_Engine)
    e.prospective = ProspectiveStore(str(tmp_path / "p2.db")); e.settings = _Settings(True); e.events = []
    block = begin_turn(e, "s", "remind me in 5 minutes to stretch", _Runtime(NOW), 1)
    assert "REMINDER SET" in block and e.events[-1]["type"] == "prospective_set"
    assert begin_turn(e, "s", "how are you?", _Runtime("2026-09-05T14:33:00+02:00"), 2) == ""     # not due yet
    block = begin_turn(e, "s", "anything new?", _Runtime("2026-09-05T14:36:00+02:00"), 3)
    assert "PROSPECTIVE" in block and "stretch" in block and e.events[-1]["type"] == "prospective_fired"
    assert e.prospective.pending() == []
    begin_turn(e, "s", "remind me to buy bread when I mention the market", _Runtime(NOW), 4)
    block = begin_turn(e, "s", "cancel the reminder", _Runtime(NOW), 5)
    assert "REMINDER CANCELLED" in block and e.events[-1]["type"] == "prospective_cancelled" and e.prospective.pending() == []



def test_75_3b_textnorm_shared_and_coverage_signal():
    from hmgfu.abstention import coverage_strength
    from hmgfu.models import MemoryPoint, RetrievedMemory
    from hmgfu.textnorm import norm, salient
    assert norm("Dário respondeu à Sónia") == "dario respondeu a sonia"
    assert salient("Which task did I complete first, fixing the fence or purchasing three cows from Peter?", min_len=4) == \
        ["task", "complete", "fixing", "fence", "purchasing", "three", "cows", "peter"]
    mem = [RetrievedMemory(point=MemoryPoint(type="message", content="I just fixed that broken fence on the east side.", summary="", source="user"))]
    cov = coverage_strength("Which task did I complete first, fixing the fence or purchasing three cows from Peter?", mem)
    assert 0.1 < cov < 0.5                                   # fence covered; cows / Peter / purchasing absent
    assert coverage_strength("What is my personal best time in the charity 5K run?",
                             [RetrievedMemory(point=MemoryPoint(type="message", content="My personal best in the charity 5K run was 25:50", summary="", source="user"))]) >= 0.8
    assert coverage_strength("?", []) == 1.0
