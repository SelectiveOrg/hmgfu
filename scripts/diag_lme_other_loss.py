"""Phase 85.1 — reproduce the 'other' losses of diag_lme_prod_context (gold retrieved, absent from the context even with an
unlimited budget) and name the mechanism per gold-bearing retrieved item: the injection path it took (history timeline,
ephemeral, stale, section) and what its rendered line contains. Usage: LME_EXCERPT=480 python scripts/diag_lme_other_loss.py cat:qi[,cat:qi]"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import bench_longmemeval_e2 as H  # noqa: E402
from diag_lme_prod_context import has_gold, throwaway_db  # noqa: E402
from hmgfu.context_render import excerpt_for_query  # noqa: E402
from hmgfu.retrieve import organise_for_injection, user_fact_question  # noqa: E402
from hmgfu.utterance import past_cue  # noqa: E402

EXCERPT = int(os.environ.get("LME_EXCERPT", "480"))
K = int(os.environ.get("LME_K", "10"))


def main() -> int:
    data = json.load(open(H.DATA, encoding="utf-8"))
    by_cat = {}
    for item in data:
        cat = "abstention" if str(item.get("question_id", "")).endswith("_abs") else item["question_type"]
        by_cat.setdefault(cat, []).append(item)
    targets = [t.split(":") for t in sys.argv[1].split(",")]
    for cat, qi in targets:
        q = by_cat[cat][int(qi)]
        turns = H.session_turns(q)
        gold, question = str(q.get("answer", "")), q["question"]
        db = throwaway_db(f"diag_other_{cat}_{qi}.db")
        if os.path.exists(db):
            os.remove(db)
        e = H._make_engine(db, full=False)
        e.settings.set("excerpt_max_chars", EXCERPT)
        for key, val in {"grader_enabled": False, "tail_async": False, "full_dream_every_n_turns": 0, "mini_dream_every_n_turns": 0,
                         "runbooks_enabled": False, "prospective_enabled": False}.items():
            e.settings.set(key, val)
        H.ingest_session_like_agent(e, turns)
        qp, ret, _ms = e.retrieve(question, limit=K)
        ef = user_fact_question(qp, e.facts)
        canonical = e.facts.render_lines() + (e.facts.render_history_lines() if past_cue(question) else [])
        inj = organise_for_injection(ret, e.graph, canonical=canonical, superseded=e.facts.superseded_values(),
                                     reverted=e.facts.reverted_values(), echo_free=ef, query=qp, excerpt_chars=EXCERPT,
                                     echo_scope=e.settings.get("echo_guard_scope"), echo_pairs=e.facts.active_pairs())
        print(f"\n### {cat} qi={qi} gold={gold[:60]!r}\n    Q: {question[:120]!r}\n    echo_free={ef} · past_cue={past_cue(question)} · canonical lines={len(canonical)}")
        for r in ret:
            p = r.point
            if not has_gold(p.content or "", gold):
                continue
            exc = excerpt_for_query(p.content, question, EXCERPT)
            where = [sec for sec, items in inj.items() if isinstance(items, list) and any(has_gold(str(x), gold) for x in items)]
            print(f"    · gold-bearing point {p.id[:8]} source={p.source} reason={r.reason!r} type={p.type} layer={p.layer} status={p.status} "
                  f"ephemeral={'_ephemeral' in (p.keywords or [])} content={len(p.content or '')}ch excerpt_has_gold={has_gold(exc, gold)} "
                  f"lands_in={where or 'NOWHERE'}")
            if not where:
                print(f"      excerpt: {exc[:200]!r}")
        e.graph.close(); e.client.close()
        try:
            os.remove(db)
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
