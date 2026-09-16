"""77.2 diagnosis — WHY the production arms read far below the plain base arm on the LongMemEval sample.

Deterministic (no reader): for each sampled item (the same first-N-per-category order as the run), ONE throwaway engine
ingests the sessions exactly as `run_prod_arm` does (source by role, observed time). Then, from the same engine:
  base_ctx   = the base arm's context (top-k cosine over every turn point, FULL turn text)
  prod_ret   = the production retrieval list (`engine.retrieve`, the arm's mode)
  prod_ctx   = the production context (`build_llm_context`: excerpt policy + token budget)
and asks, per item, where the gold answer survives: in base_ctx, in the FULL text of prod_ret's points, in prod_ctx —
so a miss is attributed to RETRIEVAL (gold not in prod_ret) or to the CONTEXT POLICY (gold in prod_ret, gone from
prod_ctx: assistant-source exclusion or the 200/160-char excerpt cut). Also records whether the gold-bearing turns are
assistant turns. Reported per category; versioned output; throwaway DBs only.
"""
from __future__ import annotations

import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from _bench_paths import throwaway_db, write_versioned  # noqa: E402
import bench_longmemeval_e2 as H  # noqa: E402
from hmgfu import fu_math  # noqa: E402
from hmgfu.context_render import excerpt_for_query, is_echo  # noqa: E402
from hmgfu.retrieve import build_llm_context, user_fact_question  # noqa: E402
from hmgfu.utterance import past_cue  # noqa: E402

N = int(os.environ.get("LME_N", "20"))
K = int(os.environ.get("LME_K", "10"))
CATS = [c for c in os.environ.get("LME_CATS", "knowledge-update,temporal-reasoning,multi-session,single-session-user,"
                                             "single-session-assistant,single-session-preference").split(",") if c]
MODE = os.environ.get("LME_MODE", "fu")
EXCERPT = int(os.environ.get("LME_EXCERPT", "0"))          # 78: 0 = the setting's default (OFF = head cut); else the candidate to measure
ECHO_SCOPE = os.environ.get("LME_ECHO_SCOPE", "")           # 78: '' = default (all) | echoes


def has_gold(text: str, gold: str) -> bool:
    g = H.norm(gold)
    return bool(g) and g in H.norm(text)


def main() -> int:
    data = json.load(open(H.DATA, encoding="utf-8"))
    by_cat = {}
    for item in data:
        cat = "abstention" if str(item.get("question_id", "")).endswith("_abs") else item["question_type"]
        by_cat.setdefault(cat, []).append(item)
    rows = []
    t0 = time.time()
    for cat in CATS:
        for qi, q in enumerate(by_cat.get(cat, [])[:N]):
            turns = H.session_turns(q)
            gold, question = str(q.get("answer", "")), q["question"]
            db = throwaway_db(f"diag_lme_{cat}_{qi}.db")
            if os.path.exists(db):
                os.remove(db)
            e = H._make_engine(db, full=False)
            if not e.client.available():
                print("FAIL: Ollama unreachable"); return 1
            e.settings.set("retrieval_mode", MODE)
            if EXCERPT:
                e.settings.set("excerpt_max_chars", EXCERPT)
            if ECHO_SCOPE:
                e.settings.set("echo_guard_scope", ECHO_SCOPE)
            for key, val in {"grader_enabled": False, "tail_async": False, "full_dream_every_n_turns": 0, "mini_dream_every_n_turns": 0,
                             "runbooks_enabled": False, "prospective_enabled": False}.items():
                e.settings.set(key, val)
            H.ingest_session_like_agent(e, turns)                              # 85.1: the agent's own paths (81.1), not the 77.2 defect
            by_content = {}
            for p_ in e.graph.points.values():
                by_content.setdefault((p_.content or "").strip(), p_)
            pts = []
            for iso, human, role, txt, has_ans in turns:
                p = by_content.get(f"{role}: {txt}".strip()) or by_content.get(txt.strip())
                if p is not None:
                    pts.append((p, role, txt, has_ans))
            gold_turn_roles = sorted({role for _, role, txt, _ in pts if has_gold(txt, gold)})
            qv = e.embed(question)
            top = sorted(pts, key=lambda x: -fu_math.cosine(qv, x[0].embedding))[:K]
            base_ctx = "\n".join(t for _, _, t, _ in top)
            qp, ret, _ms = e.retrieve(question, limit=K, mode=MODE)
            ret_full = "\n".join((r.point.content or "") for r in ret)
            canonical = e.facts.render_lines() + (e.facts.render_history_lines() if past_cue(question) else [])
            prod_ctx, _ = build_llm_context(qp, e.graph, retrieved=ret, token_budget=e.settings.get("token_budget"),
                                            canonical=canonical, superseded=e.facts.superseded_values(),
                                            reverted=e.facts.reverted_values(), echo_free=user_fact_question(qp, e.facts),
                                            excerpt_chars=e.settings.get("excerpt_max_chars"), echo_scope=e.settings.get("echo_guard_scope"),
                                            echo_pairs=e.facts.active_pairs())
            why = ""
            if has_gold(ret_full, gold) and not has_gold(prod_ctx, gold):        # 78.4: name the mechanism of the loss
                ef = user_fact_question(qp, e.facts)
                chars = e.settings.get("excerpt_max_chars")
                scope = e.settings.get("echo_guard_scope")
                pairs = e.facts.active_pairs()
                keeps, dropped = [], []
                for r_ in ret:
                    if not has_gold(r_.point.content or "", gold):
                        continue
                    text = (excerpt_for_query(r_.point.content, question, chars) if chars
                            else ((r_.point.content or "").strip()[:200] if r_.point.source in ("user", "user_explicit")
                                  else (r_.point.summary or r_.point.title or (r_.point.content or "")[:160])))
                    if not has_gold(text, gold):
                        continue
                    keeps.append(r_)
                    if ef and r_.point.source in ("assistant", "dream") and (scope != "echoes" or is_echo(r_.point, question, pairs)):
                        dropped.append(r_)
                if not keeps:
                    why = "span_miss"
                elif len(dropped) == len(keeps):
                    why = "echo_drop"
                else:
                    from hmgfu.slots import mentions_attribute, value_in_text
                    stale = [(k, v.lower()) for k, v in e.facts.superseded_values() if v and len(v) >= 4]
                    live = [r_ for r_ in keeps if r_ not in dropped]
                    def _stale(pt):
                        blob = f"{pt.summary} {pt.title} {pt.content}"
                        return any(value_in_text(v, blob) and mentions_attribute(k, blob) for k, v in stale)
                    if live and all(_stale(r_.point) for r_ in live):
                        why = "stale_excluded"
                    else:                                                          # 85.1: greedy break vs a real budget hit
                        big_ctx, _ = build_llm_context(qp, e.graph, retrieved=ret, token_budget=100000,
                                                       canonical=canonical, superseded=e.facts.superseded_values(),
                                                       reverted=e.facts.reverted_values(), echo_free=ef,
                                                       excerpt_chars=chars, echo_scope=scope, echo_pairs=pairs)
                        char_budget = int(e.settings.get("token_budget")) * 4
                        if not has_gold(big_ctx, gold):
                            why = "other"
                        elif len(prod_ctx) < char_budget - 400:
                            why = "greedy_break"
                        else:
                            why = "budget"
            rows.append({"cat": cat, "qi": qi, "qid": q.get("question_id", ""), "gold_turn_roles": gold_turn_roles, "loss": why,
                         "gold_in_base_ctx": has_gold(base_ctx, gold), "gold_in_prod_retrieved_full": has_gold(ret_full, gold),
                         "gold_in_prod_ctx": has_gold(prod_ctx, gold), "n_prod_retrieved": len(ret),
                         "n_prod_retrieved_assistant": sum(1 for r in ret if r.point.source == "assistant"),
                         "base_ctx_chars": len(base_ctx), "prod_ctx_chars": len(prod_ctx), "n_turns": len(pts)})
            e.graph.close(); e.client.close()
            try: os.remove(db)
            except OSError: pass
            if (qi + 1) % 5 == 0:
                print(f"   {cat}: {qi + 1}/{min(N, len(by_cat.get(cat, [])))} ({time.time() - t0:.0f}s)")
    print(f"\n=== 85.1 diagnosis, faithful harness (mode={MODE}, k={K}, n={N}/category, excerpt={EXCERPT or 'default'}, echo_scope={ECHO_SCOPE or 'default'}) — where the gold answer survives ===")
    print(f"{'category':>26} {'n':>3}  {'base_ctx':>8} {'prod_ret':>8} {'prod_ctx':>8}  {'ret→ctx lost':>12}  {'gold in asst turn':>17}  {'ctx chars b/p':>14}")
    summary = {}
    for cat in CATS:
        rs = [r for r in rows if r["cat"] == cat]
        if not rs:
            continue
        n = len(rs)
        b = sum(r["gold_in_base_ctx"] for r in rs); rr = sum(r["gold_in_prod_retrieved_full"] for r in rs); pc = sum(r["gold_in_prod_ctx"] for r in rs)
        lost = sum(1 for r in rs if r["gold_in_prod_retrieved_full"] and not r["gold_in_prod_ctx"])
        asst = sum(1 for r in rs if r["gold_turn_roles"] == ["assistant"])
        bc = sum(r["base_ctx_chars"] for r in rs) / n; pcc = sum(r["prod_ctx_chars"] for r in rs) / n
        why = {k: sum(1 for r in rs if r.get("loss") == k) for k in ("span_miss", "echo_drop", "stale_excluded", "greedy_break", "budget", "other")}
        summary[cat] = {"n": n, "gold_in_base_ctx": b, "gold_in_prod_retrieved_full": rr, "gold_in_prod_ctx": pc,
                        "retrieved_but_cut_by_context_policy": lost, "gold_only_in_assistant_turns": asst,
                        "mean_base_ctx_chars": round(bc), "mean_prod_ctx_chars": round(pcc), "loss_breakdown": why}
        print(f"{cat:>26} {n:>3}  {b:>8} {rr:>8} {pc:>8}  {lost:>12}  {asst:>17}  {round(bc):>6}/{round(pcc):<6}  "
              f"loss: span {why['span_miss']} · echo {why['echo_drop']} · stale-excluded {why['stale_excluded']} · greedy-break {why['greedy_break']} · budget {why['budget']} · other {why['other']}")
    print("\nReading: 'prod_ret' counts items whose gold is in the FULL text of what production retrieval returned; the gap to "
          "'prod_ctx' is the context POLICY (assistant-source exclusion, 200/160-char excerpts, budget), not retrieval.")
    print("versioned:", write_versioned("diag_lme_prod_context", {"mode": MODE, "k": K, "n": N, "excerpt": EXCERPT, "echo_scope": ECHO_SCOPE,
                                                                 "summary": summary, "rows": rows}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
