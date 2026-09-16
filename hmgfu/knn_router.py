"""Phase 89.1 — a nearest-exemplar router with the model as fallback.

The router decides from the turn's text, and the turn's embedding is computed anyway for retrieval. When the k most similar
LABELLED exemplars agree on the decision and are close enough, that decision is the route and the model router is not
called; when they disagree, are far, or carry a standing directive (whose value must be read by the model), the router
returns None and the model runs — through the pre-router hook that already exists (`Sensitizer.bind_pre_router`, 79.3).

Exemplar base: the sealed routing set (`scripts/oracles/routing_v1.json`, the reference model's decisions) and the
author-adjudicated decision set (`scripts/oracles/decision_v1.json`, the first admissible decision per turn). Embeddings
are computed once per embedder and cached under scratch/ (keyed by the base's text hash + the embedder's name), so the
runtime cost of the router is one cosine sweep over ~180 vectors. Setting-gated, OFF by default.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Callable, List, Optional

from . import fu_math

DECISION = ("action_requested", "requested_tools", "conversation_act", "needs_memory")
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SOURCES = (os.path.join(_ROOT, "scripts", "oracles", "routing_v1.json"),
                   os.path.join(_ROOT, "scripts", "oracles", "decision_v1.json"))


def _decision_of(turn: dict) -> Optional[dict]:
    """The labelled decision of a sealed turn: the model reference (routing set) or the first admissible entry (decision set)."""
    ref = turn.get("reference")
    if isinstance(ref, dict):
        d = {k: ref.get(k) for k in DECISION}
        d["freshness"] = ref.get("freshness") or "none"; d["directive_kind"] = ref.get("directive_kind")
    else:
        adm = turn.get("admissible") or []
        if not adm:
            return None
        e = adm[0]
        d = {"action_requested": e.get("action_requested", False), "requested_tools": list(e.get("requested_tools") or []),
             "conversation_act": e["conversation_act"][0] if isinstance(e.get("conversation_act"), list) else e.get("conversation_act", "statement"),
             "needs_memory": e.get("needs_memory", False), "freshness": "none", "directive_kind": e.get("directive_kind")}
        if isinstance(d["directive_kind"], list):
            d["directive_kind"] = d["directive_kind"][0]
    d["requested_tools"] = sorted({str(t) for t in (d.get("requested_tools") or [])})
    return d


def load_exemplars(sources=DEFAULT_SOURCES) -> List[dict]:
    out = []
    for path in sources:
        try:
            turns = json.load(open(path, encoding="utf-8"))["turns"]
        except Exception:
            continue
        for t in turns:
            d = _decision_of(t)
            if d is not None and t.get("text"):
                out.append({"text": t["text"], "decision": d, "source": os.path.basename(path)})
    return out


class ExemplarBase:
    """Texts + labelled decisions + embeddings (cached per embedder)."""

    def __init__(self, embed: Callable[[str], List[float]], embed_name: str, sources=DEFAULT_SOURCES, cache_dir: Optional[str] = None):
        self.items = load_exemplars(sources)
        key = hashlib.md5(("\n".join(i["text"] for i in self.items) + "|" + embed_name).encode("utf-8")).hexdigest()[:12]
        cache_dir = cache_dir or os.path.join(_ROOT, "scratch")
        os.makedirs(cache_dir, exist_ok=True)
        path = os.path.join(cache_dir, f"knn_router_base_{key}.json")
        vecs = None
        if os.path.exists(path):
            try:
                vecs = json.load(open(path, encoding="utf-8"))
            except Exception:
                vecs = None
        if not vecs or len(vecs) != len(self.items):
            vecs = [embed(i["text"]) for i in self.items]
            json.dump(vecs, open(path, "w", encoding="utf-8"))
        for i, v in zip(self.items, vecs):
            i["embedding"] = v


def knn_route(embedding: List[float], base: ExemplarBase, k: int = 3, min_sim: float = 0.80, exclude_text: Optional[str] = None) -> Optional[dict]:
    """The decision the k nearest exemplars agree on, when the k-th is at least `min_sim` close; None otherwise. A turn
    whose neighbours carry a standing directive is never claimed (its value must be read by the model)."""
    if not base.items or k < 1:
        return None
    pool = [i for i in base.items if exclude_text is None or i["text"] != exclude_text]   # leave-one-out when measuring on a base set
    scored = sorted(((fu_math.cosine(embedding, i["embedding"]), i) for i in pool), key=lambda t: -t[0])[:k]
    if len(scored) < k or scored[-1][0] < min_sim:
        return None
    first = scored[0][1]["decision"]
    for _s, item in scored[1:]:
        d = item["decision"]
        if any(d.get(f) != first.get(f) for f in DECISION):
            return None
    if first.get("directive_kind"):
        return None
    return {"action_requested": bool(first["action_requested"]), "requested_tools": list(first["requested_tools"]),
            "conversation_act": first["conversation_act"], "needs_memory": bool(first["needs_memory"]),
            "freshness": first.get("freshness") or "none", "feedback_polarity": None, "directive": None,
            "route_source": "knn", "knn_similarity": round(scored[-1][0], 3)}


def make_knn_pre_router(engine):
    """The agent's kNN pre-router: setting-gated (`knn_router_enabled`, OFF = today), the exemplar base built lazily per
    embedder, every failure advisory (the model router runs)."""
    import logging
    log = logging.getLogger("hmgfu.knn_router")
    state = {"name": None, "base": None}

    def _knn(text):
        if not engine.settings.get("knn_router_enabled"):
            return None
        try:
            name = str(engine.settings.get("embed_model") or "")
            if state["base"] is None or state["name"] != name:
                state["name"], state["base"] = name, ExemplarBase(engine.embed, name)
            return knn_route(engine.embed(text), state["base"], k=int(engine.settings.get("knn_router_k") or 3),
                             min_sim=float(engine.settings.get("knn_router_min_sim") or 0.8))
        except Exception as exc:
            log.warning("knn router failed (%s); model router runs", exc)
            return None
    return _knn
