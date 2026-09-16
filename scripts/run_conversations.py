"""Phase 90.C — run a conversation set (DEV `conv_v1`, later the reserved `conv_v2`) through the REAL agent, recording every stage of
the user's cycle per turn: (1) message → (2) structured information (the turn's route/extraction and the ledger delta the write side
produced) → (3) related memory (what is now in the ledger, with provenance) → (4) retrieval (what was recalled and whether the expected
value reached the injected context) → (5) reply (allowed / forbidden values, abstention, time to reply, time to a usable memory).

Reuses the say-do runner's engine construction, sessions and turn wrapper (`bench_say_do.fresh_engine / new_session / turn`), the
clone + guard discipline and `write_versioned`. One clone per conversation (a fresh memory each time, so the set's own facts never
leak between conversations). `--set key=value` applies a candidate configuration to every clone (79.4 mechanism)."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _bench_paths import SCRATCH, write_versioned  # noqa: E402
import bench_say_do as sd  # noqa: E402
from hmgfu.turn_tail import wait_for_tail  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ledger(e) -> dict:
    return {r["key"]: r["value"] for r in e.facts.active()}


def _contains(text: str, needles) -> list:
    """Substring presence. Kept for the historical scores; the verdict no longer uses it (91.S0)."""
    low = (text or "").lower()
    return [n for n in needles if n.lower() in low]


# 91.S0 — the five counter-proofs the audit reproduced were all "the value appears in the text", which cannot tell an
# affirmation from a denial, a current claim from a remembered one, an answer from an abstention, or `Amaro` from
# `AmaroOther`. The predicates below judge the CLAUSE that carries the value, the same way the status diagnostic does.
_CLAUSE = re.compile(r"[,.;:!?\n()\[\]\u2014\u2013]+|\s+(?:but|however|mas|por[e\u00e9]m|contudo|embora|although|though)\s+", re.IGNORECASE)
_NEG = re.compile(r"\b(?:not|n[o\u00e3]o|never|nunca|no longer|n[a\u00e3]o mais|isn'?t|aren'?t|don'?t|doesn'?t|didn'?t|"
                  r"won'?t|can'?t|cannot|nem)\b", re.IGNORECASE)
_HISTORY = re.compile(r"\b(?:used to|previously|formerly|before|until|till|at[e\u00e9]|antes|anteriormente|dantes|no longer|"
                      r"j[a\u00e1] n[a\u00e3]o|era|foi|ficou|ficaram|deixou|deixei|was|were|had been|costumava|passado|past|old|antig[oa])\b", re.IGNORECASE)
_ABSTAIN = re.compile(r"(?:don'?t (?:have|know)|do not (?:have|know)|no record|not sure|cannot|can'?t (?:find|recall|tell)|"
                      r"n[a\u00e3]o (?:tenho|sei|encontrei|consigo)|sem registo|desconhe[c\u00e7]o|n[a\u00e3]o me recordo)", re.IGNORECASE)


# 91.V4 — the independent verification passed four wrong replies through the judge. Each needed a CONTRACT, not a
# wider word list: an abstention that then answers is not an abstention; a third party's answer does not answer for the
# user; a stored value that merely CONTAINS the expected token is a different value; and history alone does not answer
# a present-tense question.
_THIRD_PARTY_SUBJ = re.compile(r"\b(?:your|his|her|their|o teu|a tua|o seu|a sua|do teu|da tua)\s+"
                               r"(?:sister|brother|wife|husband|mother|father|son|daughter|friend|colleague|boss|manager|"
                               r"neighbou?r|cousin|aunt|uncle|partner|irm[ãa]o?|esposa|marido|m[ãa]e|pai|amig[oa]|colega|"
                               r"chefe|vizinh[oa]|prim[oa]|tia|tio)\b", re.IGNORECASE)
# 91.W1 — the abstention contract stops matching answer FORMS. What matters is whether the reply puts forward a
# candidate the question did not contain: "I don't know for sure. Her name: Mirela." offers one and is an invention;
# "I don't know her name. Your sister is a person you have not named." offers none and is a correct refusal. A proper
# noun is recognised by shape (capitalised, not sentence-initial, not a pronoun or calendar word), not by a phrase list.
_STOPCAP = {"i", "you", "your", "yours", "we", "our", "he", "she", "they", "their", "his", "her", "it", "its", "the",
            "a", "an", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "january",
            "february", "march", "april", "may", "june", "july", "august", "september", "october", "november",
            "december", "trailblazer", "não", "nao", "sim", "ok"}


def _offered_candidates(reply: str, question: str) -> list:
    """Capitalised tokens the reply puts forward and the question did not contain — the shape of an offered value."""
    q = (question or "").lower()
    out = []
    for sent in re.split(r"[.!?\n]+", reply or ""):
        toks = re.findall(r"[\w\u00c0-\u00ff'-]+", sent.strip())
        for i, t in enumerate(toks):
            if i == 0 or not t[:1].isupper() or t.lower() in _STOPCAP or t.lower() in q:
                continue
            out.append(t)
    return out


_PRESENT_CUE = re.compile(r"\b(?:now|currently|today|these days|still|agora|atualmente|actualmente|hoje|ainda)\b", re.IGNORECASE)


def _clauses(text: str):
    return [c for c in _CLAUSE.split((text or "").lower()) if c.strip()]


def _has_value(clause: str, value: str) -> bool:
    """Canonical containment: the value as WHOLE tokens, so `Amaro` does not match `AmaroOther`."""
    v = re.escape((value or "").strip().lower())
    return bool(v) and re.search(rf"(?<![\w'-]){v}(?![\w'-])", clause) is not None


def _about_someone_else(clause: str, question: str) -> bool:
    """A third-party subject disqualifies the clause ONLY when the question was not about that person. "Your brother is
    Amaro." answers "what is my brother's name?" and must keep passing; it does not answer "where do I work?"."""
    m = _THIRD_PARTY_SUBJ.search(clause)
    if not m:
        return False
    relation = m.group(0).split()[-1].lower()
    return relation[:5] not in (question or "").lower()


def _stated(text: str, values, question: str = "") -> list:
    """Affirmed OF THE USER: the value sits in a clause that neither negates it nor attributes it to someone else
    (91.V4 — "Your sister works at Zenvira." was answering a question about the user's own employer)."""
    return [v for v in (values or []) if any(_has_value(c, v) and not _NEG.search(c) and not _about_someone_else(c, question)
                                             for c in _clauses(text))]


def _stated_as_current(text: str, values, question: str = "") -> list:
    """Asserted as the CURRENT state: affirmed, and not framed as history in the same clause."""
    return [v for v in (values or []) if any(_has_value(c, v) and not _NEG.search(c) and not _HISTORY.search(c)
                                             and not _about_someone_else(c, question) for c in _clauses(text))]


def _value_matches(actual: str, expected: str, prefix: bool = False) -> bool:
    """The stored value IS the expected one. 91.V4: whole-token containment accepted "Zenvira Other" for "Zenvira",
    so equality is now the DEFAULT; `prefix` is opt-in for the oracles whose own `_doc` declares prefix matching (two
    expectations depend on it: "Kia" for a stored "Kia Sportage", and a shortened URL)."""
    a, e = (actual or "").strip().lower(), (expected or "").strip().lower()
    return a == e or (prefix and bool(e) and (a.startswith(e) or _has_value(a, e)))


def _abstained(reply: str, tools=None) -> bool:
    """An explicit refusal. Whether it then ANSWERS is decided by `_offered_candidates` at the call site, not by
    matching answer forms here: 91.V4's `_ANSWER_FRAME` guard rejected "Your sister is a person you have not named.",
    a correct refusal, because it has the shape of an answer. Reading the shape was the defect."""
    return bool(_ABSTAIN.search(reply or ""))


# 92.E1 — learning-specific evaluator classes. These cues belong to the INSTRUMENT: to check a claim
# against its receipt the judge must first recognise the claim. They are deliberately narrow and
# listed here so a reviewer can audit them; no product path reads them.
_CLAIMS_UPDATE = re.compile(r"\b(?:i(?:'ve| have)? (?:saved|stored|recorded|updated|remembered|noted)|"
                            r"i(?:'ll| will) remember|memory (?:has been )?updated|noted (?:that|it)|"
                            r"gravei|guardei|memorizei|actualizei|atualizei|vou lembrar)\b", re.IGNORECASE)
_CLAIMS_SEARCH = re.compile(r"\b(?:i (?:searched|looked (?:it )?up|checked my memory)|"
                            r"pesquisei|procurei|consultei a memoria)\b", re.IGNORECASE)


def learning_verdict(conv: dict, reply: str, injected: str, ledger: dict, tools=None,
                     written=None) -> dict:
    """The judge's learning half, kept beside `judge` so both read the same recorded evidence.

    Returns only FINDINGS; the caller decides how they aggregate into P/A/D/B/H. Nothing here calls a
    model, and nothing reads the product's own modality/learning classifier -- an instrument that asks
    the system under test for its own verdict measures nothing."""
    reply = reply or ""
    tools = list(tools or [])
    allowed = conv.get("allowed") or []
    q = conv.get("question", "")
    stated = _stated(reply, allowed, q)
    wrote_here = bool(written)
    claims_update = bool(_CLAIMS_UPDATE.search(reply))
    claims_search = bool(_CLAIMS_SEARCH.search(reply))
    searched = any("memory_search" in str(t) for t in tools)
    out = {
        # H: an assertion of having updated or searched, with no corresponding receipt
        "claimed_update_without_write": claims_update and not wrote_here,
        "claimed_search_without_tool": claims_search and not searched,
        # a search whose result never reached the answer
        "searched_without_using": searched and not stated and not conv.get("abstain"),
        # D: the question required the term to be expanded and the reply did not expand it
        "expansion_missing": bool(conv.get("requires_expansion")) and not stated,
        # a clarifying question that proposes a value the case marks as wrong
        "question_suggests_wrong_value": bool(_offered_candidates(reply, q)) and bool(
            _stated(reply, conv.get("forbidden_as_current") or [], q)),
    }
    out["safety_negative"] = any(out[k] for k in (
        "claimed_update_without_write", "claimed_search_without_tool",
        "question_suggests_wrong_value"))
    return out


def judge(conv: dict, reply: str, injected: str, ledger: dict, tools=None, written=None) -> dict:
    """91.S0 — the verdict, as a PURE function of what was recorded, so the evaluator itself can be tested.

    Four outputs are kept apart, because they fail for different reasons and belong to different layers:
      write_ok      the ledger holds what the conversation was supposed to teach
      delivered     the value actually reached the reader in the INJECTED CONTEXT (the ledger is not delivery)
      answer_ok     the reply states the right thing, judged for negation, history framing and abstention
      (cost is recorded by the caller, never mixed into correctness)
    """
    exp = conv.get("expected_ledger") or {}
    allowed = conv.get("allowed") or []
    forbidden = conv.get("forbidden_as_current") or []
    prefix = str(conv.get("value_match", "")).lower() == "prefix"      # 91.V4: exact unless the oracle declares prefix
    # 91.V6: the value must have been written BY THIS CONVERSATION. The benches clone the live memory, so a value that
    # was already there satisfies an expectation the conversation never taught — l12 passed on "valencia city spain"
    # from the clone while every stage delta was empty. `written` is the union of the run's own ledger deltas; when the
    # caller does not supply it (an older archive), the check falls back to the final ledger alone and says so.
    write_ok = {k: _value_matches(str(ledger.get(k) or ""), v, prefix) and (written is None or k in written)
                for k, v in exp.items()}
    delivered = _stated(injected, allowed)                      # the CONTEXT only — a value sitting in the ledger was not delivered
    in_ledger = _stated(json.dumps(ledger, ensure_ascii=False), allowed)
    q = conv.get("question", "")
    stated = _stated(reply, allowed, q)                            # affirmed in the reply, not merely present
    current = _stated_as_current(reply, allowed, q)                # 91.V4: and, when asked for the present, as CURRENT
    stated_forbidden = _stated_as_current(reply, forbidden, q)     # a value named as HISTORY is not a false current claim
    offered = _offered_candidates(reply, q)
    abstained = _abstained(reply, tools) and not offered      # 91.W1: a refusal that then offers a value is not one
    # 91.W1: the tense is a declared contract of the case, not an assumption baked into the judge
    asks_present = str(conv.get("tense", "present")).lower() == "present"
    inconclusive = False
    if conv.get("abstain"):
        answer_ok = abstained and not stated and not stated_forbidden
        inconclusive = not _ABSTAIN.search(reply or "") and not offered and not stated and not stated_forbidden
    else:
        answer_ok = bool(current if asks_present else stated) and not stated_forbidden
        # neither the expected value nor any alternative appears: a careful reader could not score this either, so the
        # judge says so instead of guessing (the analysis: "casos sem julgamento fiável ficam inconclusivos")
        inconclusive = not stated and not stated_forbidden and not offered and not _NEG.search(reply or "")
    out = {"write_ok": write_ok, "written_here": written is not None, "delivered": sorted(set(delivered)),
           "in_ledger": sorted(set(in_ledger)),
           "stated_in_reply": stated, "stated_forbidden": stated_forbidden, "abstained": abstained,
           "offered": offered, "inconclusive": inconclusive, "answer_ok": answer_ok}
    if inconclusive:
        out["verdict"] = "INCONCLUSIVE (the reply neither states nor denies the value)"
    elif all(write_ok.values()) and (delivered or conv.get("abstain")) and answer_ok:
        out["verdict"] = "OK"
    elif not all(write_ok.values()):
        out["verdict"] = "FAIL@write (fact not in ledger)"
    elif not delivered and not conv.get("abstain"):
        out["verdict"] = ("FAIL@retrieval (fact in memory, not delivered)" if in_ledger
                          else "FAIL@write (fact not in ledger)")
    elif not answer_ok:
        out["verdict"] = "FAIL@reader (should abstain)" if conv.get("abstain") else "FAIL@reader (evidence delivered, reply wrong)"
    else:
        out["verdict"] = "OK"
    return out


NEW_SESSION_QUESTION = False   # 90.G3: ask the final question in a NEW session on the same memory (written in one conversation, recovered in the next)


def run_conversation(conv: dict, db: str | None, rep: int) -> dict:
    clone = os.path.join(SCRATCH, f"conv_{conv['id']}_{rep}_{os.getpid()}.db")
    sd.clone_live(clone, db)
    e = sd.fresh_engine(clone, None)
    sid = sd.new_session(e, conv["id"])
    stages = []
    for msg in conv["turns"]:
        before = _ledger(e)
        r = sd.turn(e, sid, msg)
        waited = wait_for_tail(e)
        after = _ledger(e)
        delta = {k: after[k] for k in after if before.get(k) != after.get(k)}
        stages.append({"message": msg, "route_source": r.get("route_source"), "tools": r["_tools"], "secs": r["_secs"],
                       "tail_waited": bool(waited), "ledger_delta": delta, "reply": (r.get("response") or "")[:200],
                       "timings": {k: (r.get("timings") or {}).get(k) for k in ("reply_ms", "total_ms", "model_calls", "calls")}})
    # the final question — 90.G3: optionally in a NEW session (cross-conversation recovery, the user's logic)
    if NEW_SESSION_QUESTION:
        sid = sd.new_session(e, conv["id"] + "-Q")
    r = sd.turn(e, sid, conv["question"])
    wait_for_tail(e)
    reply = r.get("response") or ""
    injected = r.get("injected_context") or ""
    retrieved = [{"title": x.get("title"), "score": x.get("score"), "kind": x.get("type") or x.get("kind")} for x in (r.get("retrieved") or [])][:12]
    ledger = _ledger(e)
    exp = conv.get("expected_ledger") or {}
    written = {k for s in stages for k in (s.get("ledger_delta") or {})}   # 91.V6: what THIS conversation wrote
    # 91.W3: not every correct case must force a NEW write. Separate what actually happened to each expected key.
    revised = {k for s in stages for k, v in (s.get("ledger_delta") or {}).items()
               if sum(1 for t in stages if k in (t.get("ledger_delta") or {})) > 1}
    learning = {k: ("revision" if k in revised else "new learning") if k in written
                   else ("pre-existing" if str(ledger.get(k) or "") else "absent")
                for k in (conv.get("expected_ledger") or {})}
    j = judge(conv, reply, injected, ledger, r.get("tool_trace"), written)   # 91.S0: one contract, run and tests alike
    ledger_ok, allowed_in_context = j["write_ok"], j["delivered"]
    allowed_in_reply, forbidden_in_reply = j["stated_in_reply"], j["stated_forbidden"]
    abstained, answer_ok = j["abstained"], j["answer_ok"]
    # 91.W3: the record says what it does NOT hold. A field being present is not proof the whole reply or context was
    # kept, and a later errata must be able to see the difference rather than assume completeness.
    truncated = {"reply": len(reply) > 4000, "injected_context": len(injected) > 8000, "prompt": "never recorded"}
    out = {"id": conv["id"], "family": conv["family"], "rep": rep, "stages": stages, "question": conv["question"],
           "reply": reply[:4000], "truncated": truncated,
           "route_source": r.get("route_source"), "tools": r["_tools"], "secs": r["_secs"],
           "timings": {k: (r.get("timings") or {}).get(k) for k in ("reply_ms", "total_ms", "model_calls", "calls")},
           "retrieved": retrieved, "injected_context": injected[:8000],   # 91.V5: record what was DELIVERED, so a later
           "allowed_in_context": sorted(set(allowed_in_context)), "allowed_in_reply": allowed_in_reply,   # errata can attribute
           "forbidden_in_reply": forbidden_in_reply, "abstained": abstained, "ledger_expected_ok": ledger_ok,
           "in_ledger": j["in_ledger"], "learning": learning,   # 91.W3: new learning / revision / pre-existing / absent
           "ledger_final": {k: str(v)[:60] for k, v in ledger.items() if k in exp or k.split(".")[0] in {kk.split(".")[0] for kk in exp}},
           "answer_ok": answer_ok}
    out["verdict"] = j["verdict"]
    try:
        e.graph.close()
    except Exception:
        pass
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--oracle", default=os.path.join(ROOT, "scripts", "oracles", "conv_v1.json"))
    ap.add_argument("--only", default=None, help="comma-separated conversation ids")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--db", default=None)
    ap.add_argument("--set", action="append", default=[], help="key=value applied to every clone (79.4)")
    ap.add_argument("--question-in-new-session", action="store_true", help="90.G3: ask the final question in a new session on the same memory")
    args = ap.parse_args()
    global NEW_SESSION_QUESTION
    NEW_SESSION_QUESTION = bool(args.question_in_new_session)
    sd.parse_set_args(args.set)
    _oracle = json.load(open(args.oracle, encoding="utf-8"))
    convs = _oracle["conversations"]
    for _c in convs:                                   # 91.V4: the value-match contract is declared once, per FILE
        _c.setdefault("value_match", _oracle.get("value_match", "exact"))
    if args.only:
        keep = set(args.only.split(",")); convs = [c for c in convs if c["id"] in keep]
    os.makedirs(SCRATCH, exist_ok=True)
    rows = []
    t0 = time.time()
    label = os.path.basename(args.oracle) + (" " + " ".join(args.set) if args.set else "") + (" [question in NEW session]" if NEW_SESSION_QUESTION else "")
    print(f"CONVERSATIONS [{label}] n={len(convs)} × reps {args.reps}")
    for rep in range(1, args.reps + 1):
        for c in convs:
            out = run_conversation(c, args.db, rep)
            rows.append(out)
            print(f"\n[{out['verdict']}] {c['id']} ({c['family']}) rep {rep} · {out['secs']}s · tools {out['tools']} · route {out['route_source']}")
            for st in out["stages"]:
                print(f"   turn {st['message'][:60]!r} → ledger Δ {st['ledger_delta']} · route {st['route_source']} · {st['secs']}s")
            print(f"   Q {c['question']!r} → {out['reply'][:160]!r}")
            print(f"   ledger expected ok {out['ledger_expected_ok']} · allowed in context {out['allowed_in_context']} · in reply {out['allowed_in_reply']} · forbidden in reply {out['forbidden_in_reply']} · abstained {out['abstained']}")
    ok = sum(1 for r in rows if r["verdict"] == "OK")
    from collections import Counter
    print(f"\nSUMMARY [{label}] ok {ok}/{len(rows)} · verdicts {dict(Counter(r['verdict'] for r in rows))} · {time.time() - t0:.0f}s")
    print("versioned:", write_versioned("conversations", {"label": label, "rows": rows}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
