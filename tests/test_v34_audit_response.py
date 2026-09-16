"""Phase 62.10 — regression tests for the Phase 63 audit findings that were fixed."""

from __future__ import annotations

import os
import tempfile

from hmgfu.facts import FactStore, detect_facts, supersede_stale_nodes
from hmgfu.models import MemoryPoint
from hmgfu.slots import map_to_slot, value_in_text
from hmgfu.speech_act import is_interrogative
from hmgfu.store import HMGGraph


def test_c1_mapper_rejects_value_absent_from_utterance():
    hallucinate = lambda p, s: {"slot": "family.mother_name", "value": "Alice", "op": "set"}
    assert map_to_slot("a minha cor favorita é azul", hallucinate) is None
    assert map_to_slot("a minha mãe chama-se Alice", hallucinate) == {"key": "family.mother_name", "value": "Alice"}


def test_h_supersession_matches_whole_tokens_not_substrings(tmp_path):
    g = HMGGraph(str(tmp_path / "g.db"))
    trust = MemoryPoint(type="message", content="Trust the process and keep going", summary="",
                        source="user", embedding=[0.1] * 4)
    rust = MemoryPoint(type="message", content="I said my favorite language is Rust", summary="",
                       source="user", embedding=[0.1] * 4)
    g.save_point(trust); g.save_point(rust)
    fs = FactStore(str(tmp_path / "f.db"))
    fs.apply("my favorite language is Rust"); fs.apply("actually my favorite language is Java")
    assert supersede_stale_nodes(fs, g) == 1
    assert g.points[trust.id].status == "active"          # 'Trust' is not 'Rust'
    assert g.points[rust.id].status == "superseded"
    assert not value_in_text("Rust", "Trust the process") and value_in_text("rust", "I love Rust.")


def test_h_polite_remember_request_is_a_declaration():
    assert not is_interrogative("Could you remember that my favorite music is marrabenta?")
    assert not is_interrogative("Can you please note that I live in Aveiro")
    assert is_interrogative("Could you tell me my favorite music?")


def test_h_multi_fact_utterance_writes_every_fact(tmp_path):
    fs = FactStore(str(tmp_path / "f.db"))
    changes = fs.apply_all("My name is Amara, I live in Aveiro, and my dog is Rex")
    keys = sorted(c["key"] for c in changes)
    assert keys == ["identity.location", "identity.name", "pet.dog.name"]
    assert {f["key"]: f["value"] for f in fs.active()} == {
        "identity.name": "Amara", "identity.location": "Aveiro", "pet.dog.name": "Rex"}
    assert fs.apply("my brother is Tomas")["key"] == "family.brother_name"   # compat wrapper still works


def test_h_two_pets_no_longer_produce_a_malformed_value():
    found = detect_facts("My cat is Luna and my dog is Rex")
    values = [d["value"] for d in found]
    assert "My cat is Luna" not in values
    assert "Luna" in values and "Rex" in values      # cardinality (one slot) is a Phase 64 item; values are clean


def test_h_retraction_by_selector_clears_without_repeating_value(tmp_path):
    fs = FactStore(str(tmp_path / "f.db"))
    fs.apply("my dog is Rex")
    assert fs.apply_all("I no longer have a dog") == [{"key": "pet.dog.name", "cleared": "Rex"}]
    assert fs.active() == []
    assert fs.history("pet.dog.name")[-1]["op"] == "clear"
    assert fs.apply_all("I no longer have a dog") == []                     # idempotent, no ghost clear


def test_m_active_exposes_source_for_trust_boundary(tmp_path):
    fs = FactStore(str(tmp_path / "f.db"))
    fs.apply("my name is Amara", source="user_explicit")
    assert fs.active()[0]["source"] == "user_explicit"
