"""E.1 (THEORY v2 test) — does surfacing timestamps (Σ/Θ) let the model answer temporal questions
that pure cosine + no-timestamp context cannot? LoCoMo cat-2, bge-m3, run-once, no tuning.

THREE measurements (Trailblazer), one-change-one-measurement to the end:
 M1 TIMESTAMP-IN-CONTEXT (DETERMINISTIC, no LLM, measures Σ/Θ): does cosine(+Θ) put the gold turn —
    carrying its date — into the top-k answerable context? Isolates the MECHANISM from the model.
 M2 ANSWER ACCURACY (CO-PRIMARY, LLM end-to-end): the model answers from the injected context.
    v2 arm = the SAME top-k turns WITH dates; BASE = the SAME turns WITHOUT dates injected
    (same-retriever control → the delta attributes to v2's timestamp-surfacing, not chance/LLM-prior).
 M3 MRR (SECONDARY, anchored subset only, by subtype): cosine vs cosine+Θ-date-filter, split
    date-in-query vs duration. Point "when did X" don't re-rank → not in M3 (that is M2's job).

Σ/Θ are BENCH-LOCAL here (Rule 3 — never patched into production retrieve_memory). Rebased fair
window (constant shift, gaps preserved). BASE embeds identically (bge-m3). Run:
  LOCOMO_N=3 HMGFU_EMBED_MODEL=bge-m3 .venv/Scripts/python scripts/bench_locomo_v2.py
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hmgfu import config, fu_math                       # noqa: E402
from hmgfu.chat import HMGFuEngine                       # noqa: E402
from hmgfu.taxonomy import node_class                    # noqa: E402
from hmgfu.retrieve import make_query_point             # noqa: E402
from _bench_paths import throwaway_db                    # noqa: E402

DATA = ROOT / "scratch" / "locomo10.json"
N = int(os.environ.get("LOCOMO_N", "3"))
K = 10
CHAT_MODEL = os.environ.get("HMGFU_BENCH_CHAT_MODEL", "gemma4:12b")
_SKIP = ("skill", "tool", "directive", "session")

_ANCHOR = re.compile(r"\b(before|after|between|since|until|prior to|following|first time|last time|"
                     r"how long|how many (days|weeks|months|years)|how often)\b", re.I)
_DURATION = re.compile(r"\b(how long|how many (days|weeks|months|years)|how often)\b", re.I)
_MONTHS = ("january february march april may june july august september october november december")
_DATE_IN_Q = re.compile(r"\b(\d{1,2}\s+(" + _MONTHS.replace(" ", "|") + r")|(" +
                        _MONTHS.replace(" ", "|") + r")\s+\d{1,2}|\b20\d\d)\b", re.I)


def parse_date(s: str) -> dt.datetime:
    return dt.datetime.strptime(s.strip(), "%I:%M %p on %d %B, %Y")


def classify(q: str) -> str:
    if _DURATION.search(q):
        return "anchored_duration"
    if _DATE_IN_Q.search(q):
        return "anchored_date"
    return "point"


def date_tokens(s: str):
    """Loose date signature for matching an LLM answer against the gold answer / for Θ."""
    s = s.lower()
    toks = set(re.findall(r"\b(\d{1,2})\b", s)) | set(re.findall(r"\b(20\d\d)\b", s))
    for m in _MONTHS.split():
        if m in s:
            toks.add(m[:3])
    return toks


def answer_matches(output: str, gold: str) -> bool:
    g = date_tokens(gold)
    if not g:
        return gold.strip().lower() in (output or "").lower()
    o = date_tokens(output)
    return g.issubset(o)   # every day/month/year token of the gold date present in the answer


def main() -> int:
    if config.EMBED_MODEL != "bge-m3":
        print(f"WARN: EMBED_MODEL={config.EMBED_MODEL} (want bge-m3).")
    convs = json.load(open(DATA, encoding="utf-8"))[:N]
    now = dt.datetime.now()
    # per-metric accumulators
    m1 = {"cos": {"point": [], "anchored_date": [], "anchored_duration": []}}
    m2 = {"v2": {"point": [], "anchored_date": [], "anchored_duration": []},
          "base": {"point": [], "anchored_date": [], "anchored_duration": []}}
    m3 = {"cos": {"anchored_date": [], "anchored_duration": []},
          "theta": {"anchored_date": [], "anchored_duration": []}}
    llm_calls = 0

    for ci, conv in enumerate(convs):
        c = conv["conversation"]
        sess = sorted((k for k in c if k.startswith("session_") and not k.endswith("date_time")),
                      key=lambda k: int(k.split("_")[1]))
        dates = {s: parse_date(c[s + "_date_time"]) for s in sess if c.get(s + "_date_time")}
        if not dates:
            continue
        delta = now - max(dates.values())
        DB = throwaway_db(f"locomo2_{ci}.db")
        if os.path.exists(DB):
            os.remove(DB)
        engine = HMGFuEngine(db_path=DB)
        if not engine.client.available():
            print("FAIL: Ollama unreachable"); return 1
        g = engine.graph
        dia_to_id, id_date, id_text = {}, {}, {}
        for s in sess:
            if s not in dates:
                continue
            reb = (dates[s] + delta).replace(tzinfo=dt.timezone.utc).isoformat()
            human = dates[s].strftime("%d %B %Y")
            for t in c.get(s, []):
                txt, did = (t.get("text") or "").strip(), t.get("dia_id")
                if not txt or not did:
                    continue
                line = f"{t.get('speaker','')}: {txt}"
                p = engine.ingest(line, source="user")
                p.timestamp = reb
                g.save_point(p)
                dia_to_id[did] = p.id
                id_date[p.id] = human
                id_text[p.id] = line
        # retrieval pool = the ingested DIALOGUE TURNS only (evidence points to turns; exclude any
        # macro/derived nodes ingest may have created — and guarantees id_date/id_text coverage)
        points = [p for p in g.active_points() if p.id in id_date and node_class(p) not in _SKIP]
        print(f"conv{ci}: {len(points)} turns, {len(sess)} sessions")

        def cos_ranked(qv):
            return sorted(points, key=lambda p: -fu_math.cosine(qv, p.embedding))

        def theta_date_filter(q, ranked):
            """Θ: for a date-in-query question, boost candidates whose ingest date matches a date
            token in the query. Deterministic filter over cosine's candidates, never a score blend."""
            qtok = date_tokens(q)
            if not qtok:
                return ranked
            keyed = [p for p in ranked if date_tokens(id_date.get(p.id, "")) & qtok]
            rest = [p for p in ranked if p not in keyed]
            return keyed + rest

        # PASS 1 — bge-m3 only (embed + cosine + M1/M3 deterministic); collect the M2 work items.
        # Batching the two model phases (all bge-m3 here, all gemma below) keeps ONE model resident
        # at a time and kills the per-question bge-m3<->gemma VRAM thrash that timed the run out.
        m2_work = []   # (intent, question, ctx_v2, ctx_bs, gold_answer)
        for qa in conv["qa"]:
            if str(qa.get("category")) != "2":
                continue
            ev = qa.get("evidence") or []
            if isinstance(ev, str):
                try: ev = json.loads(ev.replace("'", '"'))
                except Exception: ev = []
            gold = [dia_to_id[e] for e in ev if e in dia_to_id]
            if not gold:
                continue
            intent = classify(qa["question"])
            qv = engine.embed(qa["question"])   # bge-m3 only (cosine needs just the vector)
            ranked = cos_ranked(qv)
            top = ranked[:K]
            top_ids = {p.id for p in top}
            m1["cos"][intent].append(1 if any(gid in top_ids for gid in gold) else 0)
            if intent in ("anchored_date", "anchored_duration"):
                def rank_of(rk):
                    return next((i + 1 for i, p in enumerate(rk) if p.id in set(gold)), 0)
                r_cos, r_th = rank_of(ranked), rank_of(theta_date_filter(qa["question"], ranked))
                m3["cos"][intent].append(1.0 / r_cos if r_cos else 0.0)
                m3["theta"][intent].append(1.0 / r_th if r_th else 0.0)
            m2top = top[:6]                      # smaller prompt = faster gemma
            m2_work.append((intent, qa["question"],
                            "\n".join(f"[{id_date[p.id]}] {id_text[p.id]}" for p in m2top),
                            "\n".join(id_text[p.id] for p in m2top), str(qa["answer"])))
        # PASS 2 — gemma only (bge-m3 no longer touched this conv → gemma stays resident, no thrash).
        for intent, question, ctx_v2, ctx_bs, gold_ans in m2_work:
            for arm, ctx in (("v2", ctx_v2), ("base", ctx_bs)):
                msgs = [{"role": "system", "content": "Answer the question concisely using ONLY the "
                         "conversation excerpts. If a date is asked, give the exact date."},
                        {"role": "user", "content": f"Excerpts:\n{ctx}\n\nQuestion: {question}"}]
                try:                              # a single timeout must not kill the whole run
                    out = engine.client.chat(CHAT_MODEL, msgs, temperature=0.0, timeout=240.0)
                except Exception:
                    out = ""                      # failure counts as a wrong answer, not a crash
                llm_calls += 1
                m2[arm][intent].append(1 if answer_matches(out, gold_ans) else 0)
        engine.graph.close(); engine.client.close()
        try: os.remove(DB)
        except PermissionError: pass

    def mean(xs): return sum(xs) / len(xs) if xs else 0.0
    def allcat(d): return [x for v in d.values() for x in v]
    print(f"\n=== E.1 LoCoMo cat-2 (bge-m3, N={N}, chat={CHAT_MODEL}, {llm_calls} LLM calls) ===")
    print("M1 TIMESTAMP-IN-CONTEXT (deterministic, recall@%d of gold turn+date):" % K)
    for it in ("point", "anchored_date", "anchored_duration"):
        print(f"   {it:>17}: n={len(m1['cos'][it]):3d}  recall {mean(m1['cos'][it]):.3f}")
    print("M2 ANSWER ACCURACY (co-primary) — v2 (dates injected) vs BASE (same turns, NO dates):")
    for it in ("point", "anchored_date", "anchored_duration"):
        n = len(m2["v2"][it])
        print(f"   {it:>17}: n={n:3d}  v2 {mean(m2['v2'][it]):.3f}  BASE {mean(m2['base'][it]):.3f}"
              f"  Δ {mean(m2['v2'][it]) - mean(m2['base'][it]):+.3f}")
    print(f"   {'ALL cat-2':>17}: n={len(allcat(m2['v2'])):3d}  v2 {mean(allcat(m2['v2'])):.3f}  "
          f"BASE {mean(allcat(m2['base'])):.3f}  Δ {mean(allcat(m2['v2'])) - mean(allcat(m2['base'])):+.3f}  <<< DECISIVE")
    print("M3 MRR (secondary, anchored only) — cosine vs cosine+Θ-date-filter, by subtype:")
    for it in ("anchored_date", "anchored_duration"):
        n = len(m3["cos"][it])
        print(f"   {it:>17}: n={n:3d}  cos {mean(m3['cos'][it]):.3f}  Θ {mean(m3['theta'][it]):.3f}"
              f"  Δ {mean(m3['theta'][it]) - mean(m3['cos'][it]):+.3f}")
    print("\nVERDICT (Gate 1): M2 ALL-cat-2 Δ (v2 − BASE) is decisive — does surfacing timestamps let "
          "the model answer temporal Qs that the same retrieval WITHOUT timestamps cannot? "
          "M1 shows the mechanism reached the turn; M3 shows Θ's re-rank value where it fires.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
