"""Shared fixtures: deterministic fake embedder + heuristic-only sensitizer (no Ollama)."""

from __future__ import annotations

import hashlib
import math
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from hmgfu.sensitizer import Sensitizer  # noqa: E402
from hmgfu.store import HMGGraph  # noqa: E402

DIM = 64


def fake_embed(text: str):
    """Bag-of-words hashed embedding: shared words → higher cosine. Deterministic."""
    vec = [0.0] * DIM
    for word in re.findall(r"[\wÀ-ÿ]+", text.lower()):
        if len(word) < 3:
            continue
        h = int(hashlib.md5(word.encode()).hexdigest(), 16)
        vec[h % DIM] += 1.0
        vec[(h // DIM) % DIM] += 0.5
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


@pytest.fixture
def graph(tmp_path):
    g = HMGGraph(db_path=str(tmp_path / "test.db"))
    yield g
    g.close()


@pytest.fixture
def sensitizer():
    return Sensitizer(client=None, enabled=False)  # heuristic fallback only


@pytest.fixture
def embed():
    return fake_embed
