"""Phase 81.3 — reproducibility: exclusive versioned files, dirty-diff and effective-settings hashes, nearest-rank quantiles."""
from __future__ import annotations

import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _mod(name):
    sys.path.insert(0, os.path.join(ROOT, "scripts")); sys.path.insert(0, ROOT)
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "scripts", name + ".py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def test_manifest_hashes_and_exclusive_names(tmp_path, monkeypatch):
    bp = _mod("_bench_paths")
    monkeypatch.setattr(bp, "RUNS", str(tmp_path))
    man = bp.run_manifest(settings={"a": 1, "b": "x"})
    assert man["settings_sha"] == bp.settings_hash({"b": "x", "a": 1}) and len(man["settings_sha"]) == 12
    assert "dirty_diff_sha" in man
    p1 = bp.write_versioned("t", {"x": 1}, manifest=dict(man)); p2 = bp.write_versioned("t", {"x": 2}, manifest=dict(man))
    assert p1 != p2 and os.path.exists(p1) and os.path.exists(p2)            # same second + commit → still two files


def test_nearest_rank_quantiles():
    bl = _mod("bench_latency")
    assert bl.pct([1.0, 2.0], 0.5) == 1.0 and bl.pct([1.0, 2.0, 3.0], 0.5) == 2.0
    assert bl.pct(list(range(1, 13)), 0.95) == 12 and bl.pct([5.0], 0.95) == 5.0 and bl.pct([], 0.5) is None
