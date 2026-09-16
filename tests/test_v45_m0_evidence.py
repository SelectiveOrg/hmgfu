"""Phase 70 M0 — evidence identity, production guard, frozen-oracle expectations, evaluator integrity."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from hmgfu.models import MemoryPoint  # noqa: E402
from hmgfu.taxonomy import is_user_grounded  # noqa: E402


def test_guard_scratch_refuses_production_and_repo_root(tmp_path):
    from _bench_paths import ProductionPathError, guard_scratch
    from hmgfu import config
    with pytest.raises(ProductionPathError):
        guard_scratch(str(config.DB_PATH))
    with pytest.raises(ProductionPathError):
        guard_scratch(str(tmp_path / "x.db"), str(ROOT))
    guard_scratch(str(tmp_path / "x.db"), str(tmp_path))                 # a scratch pair is fine


def test_write_versioned_is_identified_and_never_overwritten(tmp_path, monkeypatch):
    import _bench_paths as bp
    monkeypatch.setattr(bp, "RUNS", str(tmp_path / "runs"))
    man = bp.run_manifest({"note": "test"})
    assert man["commit"] and man["utc"].endswith("Z") and man["python"]
    p1 = bp.write_versioned("demo", {"summary": {"n": 1}}, man)
    data = json.load(open(p1, encoding="utf-8"))
    assert data["manifest"]["note"] == "test" and data["summary"] == {"n": 1}
    assert os.path.exists(os.path.join(os.path.dirname(p1), "manifest.json"))
    man2 = dict(man, utc="2030-01-01T00:00:00Z")
    p2 = bp.write_versioned("demo", {"summary": {"n": 2}}, man2)
    assert p1 != p2 and json.load(open(p1, encoding="utf-8"))["summary"] == {"n": 1}   # the old run is untouched


def test_expected_oracle_sets_are_disjoint_and_complete():
    exp = json.load(open(ROOT / "scripts" / "oracles" / "expected.json", encoding="utf-8"))
    c = exp["phase68_contracts"]
    names = set(c["accepted"]) | set(c["superseded"]) | set(c["downgraded"])
    assert len(names) == 56 and not (set(c["accepted"]) & set(c["superseded"]))
    d = exp["phase69_delta"]
    names = set(d["accepted"]) | set(d["deferred"])
    assert len(names) == 35 and not (set(d["accepted"]) & set(d["deferred"]))


def test_heldout_set_is_sealed_and_well_formed():
    h = json.load(open(ROOT / "scripts" / "oracles" / "heldout_m1.json", encoding="utf-8"))
    assert len(h["shell"]) >= 12 and len(h["turns"]) >= 10
    assert {t["family"] for t in h["turns"]} >= {"prohibition", "resume", "scope", "alias", "skill", "materializer", "legacy", "cancellation"}


def test_user_grounded_never_accepts_assistant_lines_and_present_rejects_contractions():
    fake = MemoryPoint(content="Invented claim.", summary="x", type="message", source="assistant", entities=["Imaginary"])
    assert not is_user_grounded(fake)
    real = MemoryPoint(content="My dog is Green", summary="x", type="message", source="user_explicit")
    assert is_user_grounded(real)
    from bench_recall_truth import _present
    assert _present("Your favorite language isn't Java.", ["Java"]) == []
    assert _present("A tua linguagem favorita não é Java.", ["Java"]) == []
    assert _present("Your favorite language is Java.", ["Java"]) == ["Java"]


def test_environment_warnings_are_recorded_in_manifest():
    """72.6: a bench number must carry the interpreter and any environment fact that silently changes it."""
    from _bench_paths import environment_warnings, run_manifest
    man = run_manifest()
    assert man["executable"] and isinstance(man["environment_warnings"], list)
    assert man["environment_warnings"] == environment_warnings()
    for w in man["environment_warnings"]:
        assert "cryptography" in w or "venv" in w
