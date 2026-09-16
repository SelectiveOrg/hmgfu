"""E.2 — LongMemEval, the DETERMINISTIC LEG's external arbiter (THEORY_V2 §E.2, pre-registered in
ROADMAP BEFORE any number). Harness/clone; production untouched; measured-path code FROZEN.

Two arms, one-change-one-measurement (BASE first, FULL as delta), on the LongMemEval **oracle**
(evidence-sessions-only → isolates supersession/canon from retrieval-at-scale):
  BASE = pure cosine bge-m3, honest fixed k=10 (top_k=50 retrieve-everything is BARRED, R2). Context
         = the top-k turns, NO dates, NO supersession.
  FULL = the system as-is: cosine + D.3 timestamp injection + canon/Σ supersession + Regulator ON.
         The correction DETECTOR (grader, gemma) processes the UPDATE turns of the knowledge-update
         category (the mechanism on trial, invoked directly to isolate it from the router action-gate);
         secondaries get the deterministic canon + D.3 (no per-turn gemma). Superseded turns are Σ-
         filtered out of the answerable context; dates are surfaced (D.3).

DECISIVE line = knowledge-update (IS supersession). Secondary = temporal-reasoning + abstention.
Per-category, n pre-counted; aggregates NEVER decide. FALSIFIER: FULL ≤ BASE on knowledge-update ⇒
the deterministic-leg advantage does not generalise; NO retuning to save a negative.

JUDGE (fixed before running): normalized contains/exact on the dataset's short answers; abstention =
the model must decline (no gold value asserted). SAME judge both arms. Zero source fallbacks in the
decisive run else INCONCLUSIVE. VRAM/latency recorded as secondary.

Run (env sets the FULL flags for that arm; BASE runs flags-off):
  LME_N=3 LME_CATS=knowledge-update .venv/Scripts/python scripts/bench_longmemeval_e2.py
  LME_N=0 (0 = full category n).  LME_ARMS=base,full  LME_K=10
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hmgfu import config, fu_math                      # noqa: E402
from _bench_paths import throwaway_db                   # noqa: E402

DATA = ROOT / "scratch" / "longmemeval_oracle.json"
K = int(os.environ.get("LME_K", "10"))
N = int(os.environ.get("LME_N", "0"))                   # 0 = full category n (pre-counted)
CATS = [c.strip() for c in os.environ.get("LME_CATS", "knowledge-update").split(",") if c.strip()]
# arms: base=pure cosine · full=canon/Σ+D.3 · canon=canon/Σ WITHOUT dates · d3=D.3 dates WITHOUT canon/Σ
ARMS = [a.strip() for a in os.environ.get("LME_ARMS", "base,full").split(",") if a.strip()]
CHAT_MODEL = os.environ.get("HMGFU_BENCH_CHAT_MODEL", "gemma4:12b")
PERITEM = os.environ.get("LME_PERITEM", str(ROOT / "scratch" / "lme_peritem.jsonl"))   # paired per-item verdicts
LME_EXCERPT = int(os.environ.get("LME_EXCERPT", "0"))
LME_SET = os.environ.get("LME_SET", "")                     # 85.4: key=value[,key=value] applied to the prod engine settings (e.g. token_budget=3000)        # 78: prod arms' excerpt_max_chars (0 = the setting's default = OFF, head cut)
LME_ECHO_SCOPE = os.environ.get("LME_ECHO_SCOPE", "")         # 78: prod arms' echo_guard_scope ('' = default, all)

_WORD = re.compile(r"[\w']+")
_ABSTAIN_CUES = ("not mention", "no mention", "don't know", "do not know", "not sure", "isn't mentioned",
                 "is not mentioned", "no information", "not provided", "not specified", "cannot find",
                 "can't find", "not in", "haven't mentioned", "did not mention", "unable to", "não menciona",
                 "não sei", "no record", "not stated", "not available")


def norm(s: str) -> str:
    return " ".join(_WORD.findall((s or "").lower()))


def judge(output: str, gold: str, abstention: bool) -> bool:
    """Fixed judge (both arms): abstention → the model must DECLINE (assert no value); else normalized
    contains of the gold short answer (LongMemEval answers are short; number words matched loosely)."""
    o = norm(output)
    if abstention:
        return any(cue in (output or "").lower() for cue in _ABSTAIN_CUES)
    g = norm(gold)
    if not g:
        return False
    if g in o:
        return True
    # digit/word number leniency ("four" ↔ "4") + all gold content tokens present for multi-word golds
    num = {"zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6",
           "seven": "7", "eight": "8", "nine": "9", "ten": "10"}
    gtoks = [num.get(t, t) for t in g.split()]
    otoks = set(num.get(t, t) for t in o.split())
    return all(t in otoks for t in gtoks)


_NEG_WINDOW = re.compile(r"\b(not|no|never|isn't|isnt|wasn't|wasnt|aren't|arent|don't|dont|didn't|didnt|no longer|rather than|instead of|"
                         r"n[aã]o|nunca|j[aá] n[aã]o|em vez de)\b", re.IGNORECASE)
_HEDGE = re.compile(r"\b(but|however|maybe|perhaps|probably|likely|possibly|might be|could be|i think|i'd guess|my guess|i believe|"
                    r"mas|talvez|provavelmente|possivelmente|acho que|deve ser)\b", re.IGNORECASE)


# 81.2: declines phrased without a v1 cue, found by the audit set (in-sample extension of the cue list, said plainly)
_ABSTAIN_CUES_V2 = _ABSTAIN_CUES + ("don't say", "do not say", "never came up", "nothing on that", "rather not guess", "never told me",
                                    "nunca foi falado", "nunca falaste", "sem registo", "não tenho registo", "nao tenho registo", "not on record")
_NUM_PT = {"zero": "0", "um": "1", "uma": "1", "dois": "2", "duas": "2", "três": "3", "tres": "3", "quatro": "4", "cinco": "5",
           "seis": "6", "sete": "7", "oito": "8", "nove": "9", "dez": "10"}


def judge_v2(output: str, gold: str, abstention: bool) -> bool:
    """81.2 (Codex A6b): like `judge`, but (a) a gold occurrence preceded within 4 words by a negation does not count
    ("it is not Paris" ≠ Paris), and (b) an abstention that hedges a guess after the cue ("I don't know, but probably X")
    is not a decline. Deterministic; audited on `scripts/oracles/judge_set_v1.json`."""
    low = (output or "").lower()
    if abstention:
        pos = [low.find(c) for c in _ABSTAIN_CUES_V2 if c in low]
        if not pos:
            return False
        after = low[min(pos):]
        return not _HEDGE.search(after)
    o_toks = norm(output).split()
    g = norm(gold)
    if not g:
        return False
    num = {"zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6",
           "seven": "7", "eight": "8", "nine": "9", "ten": "10"}
    num = {**num, **_NUM_PT}
    o_n = [num.get(t, t) for t in o_toks]
    g_n = [num.get(t, t) for t in g.split()]
    n = len(g_n)
    for i in range(0, max(0, len(o_n) - n + 1)):
        if o_n[i:i + n] == g_n:
            window = " ".join(o_n[max(0, i - 4):i])
            if not _NEG_WINDOW.search(window):
                return True                                       # a non-negated exact occurrence
    if n > 1 and all(t in set(o_n) for t in g_n):                  # multi-word golds: all tokens present, none negated nearby
        for t in g_n:
            for i, w in enumerate(o_n):
                if w == t and not _NEG_WINDOW.search(" ".join(o_n[max(0, i - 4):i])):
                    break
            else:
                return False
        return True
    return False


from _bench_paths import production_model_settings  # noqa: E402
PROD_MODELS = production_model_settings()                        # 87: {embed_model, embed_provider, chat_model, …} as production runs them
JUDGE = os.environ.get("LME_JUDGE", "v1")          # 81.2: the run declares its judge; v1 = the 77.2 judge, v2 = negation-aware


def parse_lme_date(s: str):
    """LongMemEval date '2023/05/25 (Thu) 20:21' → datetime (None if unparseable)."""
    try:
        return dt.datetime.strptime((s or "").strip(), "%Y/%m/%d (%a) %H:%M")
    except Exception:
        return None


def session_turns(q):
    """Flatten the oracle question's evidence sessions to (iso, human, role, text, has_answer) turns —
    keeping the ACTUAL session dates (temporal-reasoning needs the real before/after ordering)."""
    dates = q.get("haystack_dates") or []
    out = []
    for si, sess in enumerate(q["haystack_sessions"]):
        d = parse_lme_date(dates[si]) if si < len(dates) else None
        iso = d.replace(tzinfo=dt.timezone.utc).isoformat() if d else ""
        human = d.strftime("%d %b %Y") if d else ""
        for t in sess:
            txt = (t.get("content") or "").strip()
            if txt:
                out.append((iso, human, t.get("role", "user"), txt, bool(t.get("has_answer"))))
    return out


def ingest_turns(engine, turns):
    """Ingest every turn as a memory point, stamped with its ISO session date (so the ingest temporal
    edges parse) and carrying the human date for D.3. Returns (point, human_date, text) in turn order."""
    pts = []
    for iso, human, role, txt, _ in turns:
        p = engine.ingest(f"{role}: {txt}", source="user")
        if iso:
            p.timestamp = iso
            engine.graph.save_point(p)
        pts.append((p, human, txt))
    return pts


def cos_topk(engine, question, pool, k):
    qv = engine.embed(question)
    ranked = sorted(pool, key=lambda pd: -fu_math.cosine(qv, pd[0].embedding))
    return ranked[:k]


INGEST_COST = {"calls": 0, "s": 0.0, "writes": 0}   # 88.1: the span extractor's cost during ingest (harness-side; production pays it in the tail)
LAST_ERROR = {"kind": ""}      # 87: the reader's infrastructure failure on the last answer() call, if any


def answer(engine, question, context):
    msgs = [{"role": "system", "content": "Answer the question concisely using ONLY the conversation "
             "excerpts. If the answer is not in the excerpts, say you don't know. State only current "
             "values."},
            {"role": "user", "content": f"Excerpts:\n{context}\n\nQuestion: {question}"}]
    LAST_ERROR["kind"] = ""
    try:
        out = engine.client.chat(CHAT_MODEL, msgs, temperature=0.0, timeout=240.0) or ""
        if not out.strip():
            LAST_ERROR["kind"] = "empty_reply"
        return out
    except Exception as exc:                                       # a timeout or a provider error is NOT a wrong answer
        LAST_ERROR["kind"] = type(exc).__name__
        return ""


def ingest_session_like_agent(engine, turns, extractor=None) -> dict:
    """81.1 (Codex A6): ingest exactly as the agent does. USER turns write the fact ledger (`facts.apply_all`, source
    user_explicit) and are ingested as user memories at the session's observed time; ASSISTANT turns go through the
    assistant path only — `_store_assistant_reply` (never the ledger; source `assistant`; the same trivia and echo gates as
    production, with the turn's own retrieval as the echo reference). Returns counts for the record."""
    counts = {"user": 0, "assistant_stored": 0, "assistant_skipped": 0, "extractor_calls": 0, "extractor_s": 0.0, "extractor_writes": 0}
    try:
        engine.facts.open_slot_regex_writes = bool(engine.settings.get("open_slot_regex_writes"))     # 84.2, as the agent sets it per turn
        engine.facts.use_mapper = engine.settings.get("fact_mapper_mode") == "fallback"              # 84.3
    except Exception:
        pass
    for iso, human, role, txt, _ in turns:
        if role == "user":
            changes = engine.facts.apply_all(txt, "user_explicit")
            point = engine.ingest(f"user: {txt}", source="user", timestamp=iso or None)
            if extractor is not None:                                              # 88.1: the tail's span extractor, per user turn
                from hmgfu.fact_spans import apply_spans
                t0 = time.perf_counter()
                added = apply_spans(engine.facts, txt, "user_explicit", extractor,
                                    skip_keys=[c["key"] for c in changes if c.get("key")],
                                    skip_values=[c.get("value") for c in changes if c.get("value")])   # 90.G2, as the tail does
                counts["extractor_calls"] += 1; counts["extractor_s"] += time.perf_counter() - t0
                counts["extractor_writes"] += len(added); changes = list(changes) + list(added)
            if point is not None:
                for c in changes:
                    if c.get("key"):
                        try:
                            engine.facts.link_source(c["key"], point.id)                   # provenance, as turn_tail does
                        except Exception:
                            pass
            counts["user"] += 1
        else:
            try:
                _q, retrieved, _ms = engine.retrieve(txt, limit=k_for_echo(engine))
            except Exception:
                retrieved = []
            stored = engine._store_assistant_reply(txt, retrieved)
            counts["assistant_stored" if stored else "assistant_skipped"] += 1
            if stored and iso:                                     # the observed time, as the user turns carry it
                p = max(engine.graph.points.values(), key=lambda x: x.timestamp)
                if p.source == "assistant" and (p.content or "") == txt:
                    p.timestamp = iso
                    engine.graph.save_point(p)
    return counts


def k_for_echo(engine) -> int:
    try:
        return int(engine.settings.get("retrieval_limit") or 12)
    except Exception:
        return 12


def run_prod_arm(engine, turns, question, mode: str, k: int) -> str:
    """77.2: the PRODUCTION path — observed-time ingest, `retrieval_mode` = mode, the production context policy."""
    from hmgfu.retrieve import build_llm_context, user_fact_question
    from hmgfu.utterance import past_cue
    engine.sensitizer.enabled = False
    for key, val in {"grader_enabled": False, "tail_async": False, "full_dream_every_n_turns": 0, "mini_dream_every_n_turns": 0,
                     "runbooks_enabled": False, "prospective_enabled": False, "retrieval_mode": mode}.items():
        engine.settings.set(key, val)
    if LME_EXCERPT:
        engine.settings.set("excerpt_max_chars", LME_EXCERPT)
    for kv in [x for x in LME_SET.split(",") if "=" in x]:                     # 85.4
        key, val = kv.split("=", 1)
        engine.settings.set(key.strip(), int(val) if val.strip().lstrip("-").isdigit() else (val.strip().lower() == "true" if val.strip().lower() in ("true", "false") else val.strip()))          # 78 candidate (throwaway engine)
    if LME_ECHO_SCOPE:
        engine.settings.set("echo_guard_scope", LME_ECHO_SCOPE)
    extractor = None
    if engine.settings.get("fact_mapper_mode") == "spans":            # 88.1: the write-side candidate under measurement
        from hmgfu.fact_spans import registry_span_extractor
        extractor = registry_span_extractor(engine.registry, engine.settings.get("fact_mapper_role") or "nano")
    counts = ingest_session_like_agent(engine, turns, extractor)      # 81.1: the agent's own paths, per role (Codex A6); 88.1 + extractor
    if extractor is not None:
        INGEST_COST["calls"] += counts["extractor_calls"]; INGEST_COST["s"] += counts["extractor_s"]; INGEST_COST["writes"] += counts["extractor_writes"]
    from hmgfu.query_depth import depth_for
    q, retrieved, _ms = engine.retrieve(question, limit=depth_for(question, engine.settings, default=k), mode=mode)   # 86.1: the agent's depth rule
    canonical = engine.facts.render_lines() + (engine.facts.render_history_lines() if past_cue(question) else [])
    ctx, _ = build_llm_context(q, engine.graph, retrieved=retrieved, token_budget=engine.settings.get("token_budget"),
                               canonical=canonical, superseded=engine.facts.superseded_values(),
                               reverted=engine.facts.reverted_values(), echo_free=user_fact_question(q, engine.facts),
                               excerpt_chars=engine.settings.get("excerpt_max_chars"), echo_scope=engine.settings.get("echo_guard_scope"),
                               echo_pairs=engine.facts.active_pairs())                        # 78: the production policy, as set
    return ctx


def run_supersession(engine, turns, mode="regex"):
    """KU supersession, the two mechanisms measured against each other. Both leave stale graph nodes
    status='superseded' for the caller's Σ filter. Returns {calls, errs} (gemma perceiver calls + hard
    errors; errs>0 in a decisive run ⇒ INCONCLUSIVE — the "zero source fallbacks" bar).
      mode='regex'     → DETERMINISTIC canon: facts.detect_fact → FactStore per user turn, then
                         supersede_stale_nodes demotes graph nodes carrying a superseded value. NO gemma.
      mode='perceiver' → the REAL B6 path (E.2-P): the gemma chat-correction perceiver
                         (_detect_correction_via_chat) per user turn → _apply_correction (ingest the
                         corrected fact + supersede_named_stale on the NAMED stale value). Tests whether
                         the perceiver's coverage catches the conversational updates the regex misses."""
    calls = errs = 0
    if mode == "regex":
        from hmgfu.facts import supersede_stale_nodes
        for iso, human, role, txt, _ in turns:
            if role == "user":
                try:
                    engine.facts.apply(txt)             # detect_fact → keyed canon (deterministic)
                except Exception:
                    pass
        supersede_stale_nodes(engine.facts, engine.graph)   # demote nodes carrying a superseded value
    elif mode == "perceiver":
        from hmgfu.grader import _detect_correction_via_chat, _apply_correction, facts_summary
        for iso, human, role, txt, _ in turns:
            if role != "user":
                continue
            calls += 1
            try:
                mem = engine.retrieve(txt)[1]           # [1] = retrieved MEMORIES (bug was [0]=QueryPoint)
                corr = _detect_correction_via_chat(engine, txt, "", facts_summary(mem))
                if corr:
                    _apply_correction(engine, corr, txt)   # B6: ingest right + supersede_named_stale(wrong)
            except Exception as exc:
                errs += 1
                if errs <= 3:
                    print(f"   [perceiver err] {type(exc).__name__}: {str(exc)[:140]}")
    return {"calls": calls, "errs": errs}


def main() -> int:
    eff = PROD_MODELS.get("embed_model") or config.EMBED_MODEL
    print(f"EMBEDDER: {eff} (production settings) — config default {config.EMBED_MODEL}; throwaway engines use the production embedder (87)")
    data = json.load(open(DATA, encoding="utf-8"))
    by_cat = {}
    for item in data:
        cat = "abstention" if str(item.get("question_id", "")).endswith("_abs") else item["question_type"]
        by_cat.setdefault(cat, []).append(item)
    # accumulators[arm][cat] = list of 0/1
    acc = {a: {c: [] for c in CATS} for a in ARMS}
    meta = {"llm_calls": 0, "corr_calls": 0, "errs": 0, "t0": None}
    started = time.strftime("%Y-%m-%d %H:%M:%S")
    open(PERITEM, "w", encoding="utf-8").close()          # fresh paired-verdict log for this run

    want = {int(x) for x in os.environ.get("LME_QIS", "").split(",") if x.strip()}   # pre-declared sample qi
    for cat in CATS:
        items = by_cat.get(cat, [])
        items = items if N == 0 else items[:N]
        abstention = (cat == "abstention")
        sel = [qi for qi in range(len(items)) if not want or qi in want]   # original qi preserved (pairing)
        print(f"\n### category={cat}  n={len(sel)}{'' if not want else ' (sampled qi=' + ','.join(map(str, sel)) + ')'}  arms={ARMS}  k={K}")
        for qi in sel:
            q = items[qi]
            turns = session_turns(q)
            gold = str(q.get("answer", ""))
            question = q["question"]
            for arm in ARMS:
                DB = throwaway_db(f"lme_{cat}_{qi}_{arm}.db")
                if os.path.exists(DB):
                    os.remove(DB)
                engine = _make_engine(DB, full=(arm not in ("base", "prod", "prodcos")))
                if not engine.client.available():
                    print("FAIL: Ollama unreachable"); return 1
                if arm in ("prod", "prodcos"):                                  # 77.2: production path, nothing shared below
                    ctx = run_prod_arm(engine, turns, question, "fu" if arm == "prod" else "cosine", K)
                    out = answer(engine, question, ctx)
                    meta["llm_calls"] += 1
                    v = 1 if (judge_v2 if JUDGE == "v2" else judge)(out, gold, abstention) else 0
                    acc[arm][cat].append(v)
                    err = LAST_ERROR["kind"]
                    if err:
                        meta.setdefault("infra", {}).setdefault(cat, 0)
                        meta["infra"][cat] += 1                              # 87: an infrastructure failure is counted as WRONG and reported apart
                    with open(PERITEM, "a", encoding="utf-8") as fh:
                        fh.write(json.dumps({"cat": cat, "arm": arm, "qi": qi, "qid": q.get("question_id", ""), "correct": v,
                                             "reply": (out or "")[:600], "gold": gold, "judge": JUDGE, "error": err}) + "\n")   # 81.2 / 87
                    engine.graph.close(); engine.client.close()
                    try: os.remove(DB)
                    except OSError: pass
                    continue
                pool = ingest_turns(engine, turns)
                # decomposition: full = canon/Σ+dates · canon = canon/Σ (regex) no dates · d3 = dates only ·
                # pcanon (E.2-P) = canon/Σ driven by the gemma PERCEIVER (B6) · canonann (E.2-A) = canon/Σ
                # but ANNOTATE not REMOVE (keep superseded turns in the pool, tag them [superseded])
                supersede = arm in ("full", "canon", "pcanon", "canonann")   # canon supersession
                mode = "perceiver" if arm == "pcanon" else "regex"
                annotate = arm == "canonann"             # E.2-A: keep superseded turns, tag instead of drop
                dates = arm in ("full", "d3")            # D.3 timestamp surfacing in the excerpt body
                usecanon = arm in ("full", "canon")      # D.4 FactStore canon front (regex only; pcanon has none)
                if supersede:
                    r = run_supersession(engine, turns, mode=mode)
                    meta["corr_calls"] += r["calls"]
                    meta["errs"] += r["errs"]
                    if annotate:
                        eff = pool                       # Σ-annotate: KEEP superseded turns (tagged below)
                    else:
                        eff = [pd for pd in pool if engine.graph.points.get(pd[0].id) is not None
                               and engine.graph.points[pd[0].id].status == "active"]   # Σ-remove: drop superseded
                else:
                    eff = pool
                top = cos_topk(engine, question, eff, K)
                canon = ""
                if usecanon:
                    try:
                        lines = engine.facts.render_lines()                   # D.4 canon current values
                        canon = "\n".join(lines) if isinstance(lines, list) else str(lines or "")
                    except Exception:
                        pass
                body_lines = []
                for point, d, t in top:
                    sup = (annotate and engine.graph.points.get(point.id) is not None
                           and engine.graph.points[point.id].status == "superseded")
                    body_lines.append(f"{'[superseded] ' if sup else ''}{('[' + d + '] ') if dates else ''}{t}")
                body = "\n".join(body_lines)             # D.3 dates iff `dates`; [superseded] tag iff annotate
                ctx = (canon + "\n" if canon else "") + body
                out = answer(engine, question, ctx)
                meta["llm_calls"] += 1
                v = 1 if (judge_v2 if JUDGE == "v2" else judge)(out, gold, abstention) else 0
                acc[arm][cat].append(v)
                with open(PERITEM, "a", encoding="utf-8") as fh:              # paired per-item verdict (McNemar)
                    fh.write(json.dumps({"cat": cat, "arm": arm, "qi": qi,
                                         "qid": q.get("question_id", ""), "correct": v,
                                         "reply": (out or "")[:600], "gold": gold, "judge": JUDGE}) + "\n")   # 81.2
                engine.graph.close(); engine.client.close()
                try: os.remove(DB)
                except OSError: pass
            if (qi + 1) % 5 == 0:
                infra = (meta.get("infra") or {}).get(cat, 0)
                cost = f", extractor {INGEST_COST['calls']} calls {INGEST_COST['s']:.0f}s {INGEST_COST['writes']} writes" if INGEST_COST["calls"] else ""
                print(f"   {cat}: {qi + 1}/{len(items)} done ({meta['llm_calls']} llm, {meta['corr_calls']} corr, {infra} reader infra failures counted as wrong{cost})")

    def mean(xs): return sum(xs) / len(xs) if xs else 0.0
    print(f"\n=== E.2 LongMemEval oracle (embedder={PROD_MODELS.get('embed_model') or config.EMBED_MODEL}, k={K}, chat={CHAT_MODEL}, judge={JUDGE}) — started {started} ===")
    print(f"    {meta['llm_calls']} answer calls, {meta['corr_calls']} perceiver calls, "
          f"{meta['errs']} perceiver errors {'(INCONCLUSIVE if decisive!)' if meta['errs'] else '(clean)'}")
    print(f"\n{'category':>26} {'n':>4}  " + "  ".join(f"{a:>7}" for a in ARMS) +
          ("   Δ(full-base)" if set(ARMS) >= {"base", "full"} else ""))
    for cat in CATS:
        n = len(acc[ARMS[0]][cat])
        row = f"{cat:>26} {n:>4}  " + "  ".join(f"{mean(acc[a][cat]):.3f}".rjust(7) for a in ARMS)
        if set(ARMS) >= {"base", "full"}:
            delta = mean(acc["full"][cat]) - mean(acc["base"][cat])
            row += f"   {delta:+.3f}" + ("  <<< DECISIVE" if cat == "knowledge-update" else "")
        print(row)
    print("\nVERDICT (pre-registered): FULL ≤ BASE on knowledge-update FALSIFIES the deterministic-leg "
          "external generalisation. Per-category only; aggregates never decide. n reported above.")
    report_discordant(PERITEM, CATS, ARMS)
    return 0


def report_discordant(peritem_path, cats, arms):
    """McNemar discordant pairs from the paired per-item verdicts: for each non-base arm vs BASE, on the
    SAME items, b = arm-right/base-wrong (gains), c = arm-wrong/base-right (losses). Net = b − c seals or
    downgrades a mean delta (a +0.15 mean from b=11/c=0 is solid; from b=18/c=7 is fragile — recorded
    as-is, NOT re-run to improve, Rule 3)."""
    try:
        rows = [json.loads(l) for l in open(peritem_path, encoding="utf-8") if l.strip()]
    except OSError:
        print("\n(no per-item file — discordant analysis skipped)"); return
    idx = {(r["cat"], r["qi"], r["arm"]): r["correct"] for r in rows}
    qis = {}
    for r in rows:
        qis.setdefault(r["cat"], set()).add(r["qi"])
    print("\n=== DISCORDANT PAIRS (McNemar, vs BASE, same items) ===")
    for cat in cats:
        for a2 in arms:
            if a2 == "base":
                continue
            b = c = both1 = both0 = 0
            for qi in sorted(qis.get(cat, ())):
                x, y = idx.get((cat, qi, "base")), idx.get((cat, qi, a2))
                if x is None or y is None:
                    continue
                if y and not x:
                    b += 1
                elif x and not y:
                    c += 1
                elif x and y:
                    both1 += 1
                else:
                    both0 += 1
            net = b - c
            print(f"   {cat:>22}  {a2:>6} vs base:  b({a2}✓/base✗)={b:3d}  c({a2}✗/base✓)={c:3d}  "
                  f"net={net:+d}  both✓={both1} both✗={both0}")
    return


def _make_engine(db_path, full):
    """One engine per (question, arm). FULL sets the Regulator flags in config for this process; BASE
    runs flags-off. config.X are per-call lookups, so setting them here binds the arm's behaviour.

    HEURISTIC sensitization (nano OFF) for BOTH arms: batch-ingesting each haystack while gemma4 answers
    thrashes the shared GPU — the qwen nano sensitizer times out and falls back UNEVENLY (some items nano,
    some heuristic), which is noise, not signal. Forcing heuristic makes ingestion DETERMINISTIC and equal
    across arms; the FULL mechanisms under test (canon = regex detect_fact; D.3 = date metadata; Sigma =
    status filter) do NOT use the nano, and BASE is pure cosine which ignores extracted entities entirely."""
    config.REGULATOR_ENABLED = bool(full)
    config.CHAT_CORRECTION_SIGNAL = bool(full)
    from hmgfu.agent import AgentEngine
    engine = AgentEngine(db_path=db_path)
    for key in ("embed_model", "embed_provider"):                    # 87: the PRODUCTION embedder, not the config default
        if PROD_MODELS.get(key):
            engine.settings.set(key, PROD_MODELS[key])
    engine.sensitizer.enabled = False                 # deterministic heuristic extraction, no GPU thrash
    return engine


if __name__ == "__main__":
    raise SystemExit(main())
