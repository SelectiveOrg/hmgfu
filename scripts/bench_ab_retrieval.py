"""Phase 30.1/30.2: the A/B the theory has never had — claim "the relational field beats RAG"
is architecture, not evidence" until HMG-Fu retrieval is measured against plain vector-
similarity on the IDENTICAL corpus + queries.

BASELINE = plain cosine top-k over the same real embeddings stored on the graph. Bench-only
reference implementation (never imported by production code) — this is the "just use a vector
DB" comparator the theory claims to beat.
FU        = production retrieve_memory() (6-channel candidates + memory_score + expand_through_fu).

Corpus (real ingest: real embeddings + real nano sensitizer) is organised into 4 labeled query
categories so a Fu win/loss is attributable to a specific mechanism, not an average:
  direct       — paraphrase of one stored fact; BOTH systems should get this (control)
  relational   — correct answer requires an entity-link hop (expand_through_fu / kappa),
                 not lexical/semantic closeness to the query itself
  recency      — two same-topic statements at different times; correct = the NEWER one
                 (plain cosine has no time signal at all)
  contradiction— a later negation supersedes an earlier assertion; embeddings of positive
                 and negated statements on the same topic are close, so lexical overlap alone
                 can favor the STALE one

Metric per query: rank of the correct point id in each system's top-10 (None = not found).
Reports hit@1 / hit@3 / MRR per category for both systems, side by side, no cherry-picking.

Run: .venv/Scripts/python scripts/bench_ab_retrieval.py
"""

from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hmgfu import fu_math  # noqa: E402
from hmgfu.chat import HMGFuEngine  # noqa: E402
from hmgfu.retrieve import make_query_point, retrieve_memory  # noqa: E402

from _bench_paths import throwaway_db  # noqa: E402

DB = throwaway_db("ab_retrieval.db")
TOP_K = 10


def baseline_cosine_topk(query, points, k: int = TOP_K):
    """The comparator: plain vector similarity, nothing else. Bench-only — never used to serve."""
    scored = [(p, fu_math.cosine(query.embedding, p.embedding)) for p in points]
    scored.sort(key=lambda t: -t[1])
    return [p for p, _ in scored[:k]]


def age_point(engine, point_id: str, days_ago: float) -> None:
    """Backdate a point's timestamp to simulate 'said N days ago' (test setup, not scoring hack)."""
    import datetime
    p = engine.graph.points[point_id]
    p.timestamp = (datetime.datetime.now(datetime.timezone.utc)
                  - datetime.timedelta(days=days_ago)).isoformat()
    engine.graph.save_point(p)


def rank_of(target_id: str, ranked_points) -> int:
    for i, p in enumerate(ranked_points):
        if p.id == target_id:
            return i + 1
    return 0   # not found in top-k


def main() -> int:
    if os.path.exists(DB):
        os.remove(DB)
    engine = HMGFuEngine(db_path=DB)
    if not engine.client.available():
        print("FAIL: Ollama unreachable")
        return 1

    ids = {}

    def ingest(key, text, source="user"):
        ids[key] = engine.ingest(text, source=source).id

    print("Ingesting corpus (real embeddings + real nano sensitizer)...")

    # --- direct-semantic control (3) ---------------------------------------------------
    ingest("python", "My favorite programming language is Python, I've used it for eight years.")
    ingest("guitar_hobby", "I've been learning to play acoustic guitar as a weekend hobby.")
    ingest("marathon_goal", "My goal this year is to finish a full marathon under four hours.")

    # --- relational multi-hop (3): query shares little vocabulary with the correct answer,
    # which is only reachable via an entity-link edge to a more obviously-matching memory ------
    ingest("leo_school", "My son Leo started 3rd grade this year at Lincoln elementary.")
    ingest("leo_teacher", "Leo's teacher Ms. Rivera said he's doing great in math but needs "
          "extra help with reading comprehension.")
    ingest("leo_tutor", "I signed Leo up with a weekend reading tutor starting next month "
          "to work on comprehension.")
    ingest("coworker_daniel", "My coworker Daniel and I are learning chess together at lunch.")
    ingest("daniel_book", "Daniel lent me his old chess book, 'The Art of Attack', "
          "he said it changed how he thinks about the opening.")
    ingest("unrelated_filler1", "Repainted the fence this weekend, took way longer than planned.")

    # --- recency conflict (2 pairs): correct = the NEWER statement ---------------------
    ingest("cat_old", "My cat is named Nimbus.")
    age_point(engine, ids["cat_old"], days_ago=20)
    ingest("cat_new", "Correction: my cat's name is actually Shadow now, we renamed her "
          "after adopting her sister.")
    ingest("job_old", "I'm working as a backend engineer at a fintech startup.")
    age_point(engine, ids["job_old"], days_ago=30)
    ingest("job_new", "Update: I left the fintech startup and now work as a data engineer "
          "at a logistics company.")

    # --- contradiction (2): later negation supersedes earlier assertion ---------------
    ingest("spicy_old", "I love spicy food, the hotter the better, always order extra chili.")
    age_point(engine, ids["spicy_old"], days_ago=25)
    ingest("spicy_new", "Actually I don't handle spicy food well anymore, my stomach can't "
          "take it like it used to, ordering mild these days.")
    ingest("coffee_old", "I drink coffee every morning, at least two cups before work.")
    age_point(engine, ids["coffee_old"], days_ago=15)
    ingest("coffee_new", "I quit coffee entirely last month, switched to green tea instead.")

    # filler to make the corpus non-trivial (real content, unrelated topics)
    fillers = [
        "Finally organized the garage, found tools I forgot I owned.",
        "Started composting kitchen scraps, the bin fills up faster than expected.",
        "Switched banks for better savings interest rates this month.",
        "My upstairs neighbor's dog barks constantly during the day.",
        "Booked flights for a December trip to visit my parents.",
        "The office coffee machine broke again, third time this quarter.",
        "Trying a new budgeting app to track subscriptions I forgot about.",
        "Replaced the bike chain after it kept slipping on hills.",
    ]
    for i, text in enumerate(fillers):
        ingest(f"filler{i}", text)

    print(f"Corpus: {len(engine.graph.active_points())} active points\n")

    queries = [
        ("direct", "What programming language do I prefer?", ids["python"]),
        ("direct", "What's my marathon goal this year?", ids["marathon_goal"]),
        ("direct", "What hobby have I been learning on weekends?", ids["guitar_hobby"]),
        ("relational", "How is my kid doing with reading?", ids["leo_teacher"]),
        ("relational", "What book did my coworker recommend?", ids["daniel_book"]),
        ("recency", "What is my cat's name?", ids["cat_new"]),
        ("recency", "What is my current job?", ids["job_new"]),
        ("contradiction", "Do I like spicy food?", ids["spicy_new"]),
        ("contradiction", "Do I still drink coffee?", ids["coffee_new"]),
    ]

    points = engine.graph.active_points()
    rows = []
    for category, text, target_id in queries:
        q = make_query_point(text, engine.embed, engine.sensitizer)
        fu_ranked = [r.point for r in retrieve_memory(q, engine.graph)]
        base_ranked = baseline_cosine_topk(q, points)
        fu_rank = rank_of(target_id, fu_ranked)
        base_rank = rank_of(target_id, base_ranked)
        rows.append((category, text, fu_rank, base_rank))
        print(f"[{category:>13}] {text!r}\n"
              f"{'':>15} FU rank={fu_rank or '>10'}   BASELINE rank={base_rank or '>10'}")
        if fu_rank != 1:
            print(f"{'':>15} DIAGNOSTIC — target={target_id}, FU top 5:")
            fu_scored = [r for r in retrieve_memory(q, engine.graph)]
            for i, r in enumerate(fu_scored[:5]):
                mark = " <-- TARGET" if r.point.id == target_id else ""
                print(f"{'':>18} #{i+1} [{r.score:.3f}] {r.point.content[:55]!r} ({r.reason}){mark}")
            target_point = engine.graph.points.get(target_id)
            if target_point is not None:
                target_sem = fu_math.cosine(q.embedding, target_point.embedding)
                print(f"{'':>18} target semantic cosine={target_sem:.3f}, "
                      f"density={target_point.density:.2f}, utility={target_point.utility:.2f}, "
                      f"recency={fu_math.recency_score(target_point.timestamp):.2f}")

    print("\n=== A/B SUMMARY (rank of the correct memory; 0 = not in top-10) ===")
    by_cat = {}
    for category, _, fu_rank, base_rank in rows:
        by_cat.setdefault(category, []).append((fu_rank, base_rank))

    def stats(pairs, idx):
        ranks = [p[idx] for p in pairs]
        hit1 = sum(1 for r in ranks if r == 1) / len(ranks)
        hit3 = sum(1 for r in ranks if 0 < r <= 3) / len(ranks)
        mrr = sum((1.0 / r) if r else 0.0 for r in ranks) / len(ranks)
        return hit1, hit3, mrr

    print(f"{'category':>14} | {'FU hit@1':>9} {'hit@3':>7} {'MRR':>6} | "
          f"{'BASE hit@1':>10} {'hit@3':>7} {'MRR':>6}")
    for category, pairs in by_cat.items():
        fh1, fh3, fmrr = stats(pairs, 0)
        bh1, bh3, bmrr = stats(pairs, 1)
        print(f"{category:>14} | {fh1:>9.2f} {fh3:>7.2f} {fmrr:>6.2f} | "
              f"{bh1:>10.2f} {bh3:>7.2f} {bmrr:>6.2f}")
    all_pairs = [p for pairs in by_cat.values() for p in pairs]
    fh1, fh3, fmrr = stats(all_pairs, 0)
    bh1, bh3, bmrr = stats(all_pairs, 1)
    print(f"{'OVERALL':>14} | {fh1:>9.2f} {fh3:>7.2f} {fmrr:>6.2f} | "
          f"{bh1:>10.2f} {bh3:>7.2f} {bmrr:>6.2f}")

    engine.graph.close(); engine.client.close()
    try:
        os.remove(DB)
    except PermissionError:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
