"""Phase 90.D1 — where do the facts disappear? Replays `fact_spans.extract_spans` STAGE BY STAGE on the DEV sentences, for both roles
and for two decoding factors (grammar-constrained `format_schema` as in production vs plain JSON mode), recording: the raw model
response, the parsed `facts`, every validation filter that drops a fact, and the slot mapping. No product change; a probe only.
Throwaway clone of the live DB (settings/registry), the production DB is not touched."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _bench_paths import SCRATCH, write_versioned  # noqa: E402
from bench_recall_truth import clone_live  # noqa: E402
from hmgfu.agent import AgentEngine  # noqa: E402
from hmgfu.fact_detect import _clean_value  # noqa: E402
from hmgfu.fact_spans import SPAN_PROMPT, SPAN_SCHEMA, _ORIGIN, _tokens  # noqa: E402
from hmgfu.slots import infer_slot_from_value, is_slot, normalise_key, value_in_text  # noqa: E402
from hmgfu.value_gate import is_attribute_value, third_party_attr  # noqa: E402

DEV = ["we are actually working on HMG, this memory system of yours", "My main project is a Java billing API.",
       "Gosto muito de café.", "Ultimamente prefiro chá de gengibre.",
       "heres the updated link: http://198.51.100.7/ui/sharing/0123456789abcdef0123456789abcdef"]


def stages(text: str, raw) -> dict:
    """The validation + mapping stages of extract_spans, each recorded."""
    out = {"raw": raw, "parsed": None, "facts": []}
    facts = raw.get("facts") if isinstance(raw, dict) else None
    out["parsed"] = f"{len(facts)} facts" if isinstance(facts, list) else f"not a facts list ({type(raw).__name__})"
    for f in facts or []:
        rec = {"attribute": f.get("attribute"), "value": f.get("value"), "dropped_at": None, "key": None}
        attr, val = str(f.get("attribute") or "").strip(), str(f.get("value") or "").strip().strip("'\"")
        if not attr or not val or len(val) > 80 or not value_in_text(val, text):
            rec["dropped_at"] = "validation: grounding (value not in text / empty / >80)"
        else:
            val = _clean_value(val)
            if not val or third_party_attr(attr) or not is_attribute_value(val):
                rec["dropped_at"] = "validation: value gate (predicate-shaped / third party / empty after clean)"
            elif set(_tokens(attr)) & _ORIGIN:
                rec["dropped_at"] = "validation: origin attribute"
            else:
                key = normalise_key(attr.lower())
                rec["mapped_from_attribute"] = key
                if not is_slot(key):
                    inferred = infer_slot_from_value(val)
                    rec["inferred_from_value"] = inferred
                    key = inferred or key
                if not is_slot(key):
                    rec["dropped_at"] = f"mapping: '{attr}' → '{key}' is not a closed slot"
                elif re.match(r"https?://", val, re.IGNORECASE) and not key.endswith("_link"):
                    rec["dropped_at"] = "mapping: URL value on a non-link slot"
                else:
                    rec["key"] = key
        out["facts"].append(rec)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--roles", default="chat,nano")
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--db", default=None)
    args = ap.parse_args()
    clone = os.path.join(SCRATCH, f"span_stages_{os.getpid()}.db"); clone_live(clone, args.db)
    e = AgentEngine(db_path=clone)
    rows = []
    for role in args.roles.split(","):
        model = e.registry.model_for_role(role) if hasattr(e.registry, "model_for_role") else "?"
        for factor in ("schema", "json_only"):
            for text in DEV:
                for rep in range(1, args.reps + 1):
                    kw = {"json_mode": True, "temperature": 0.0, "think": False}
                    if factor == "schema":
                        kw["format_schema"] = SPAN_SCHEMA
                    try:
                        out = e.registry.chat_for_role(role, [{"role": "user", "content": SPAN_PROMPT + "\n\nUSER MESSAGE:\n" + text}], **kw)
                        content = out.get("content") if isinstance(out, dict) else out
                        raw_text = content if isinstance(content, str) else json.dumps(content)
                        try:
                            raw = json.loads(raw_text) if isinstance(raw_text, str) else content
                            parse_err = None
                        except Exception as exc:
                            raw, parse_err = {}, f"{type(exc).__name__}: {exc}"[:100]
                    except Exception as exc:
                        raw_text, raw, parse_err = "", {}, f"model call failed: {type(exc).__name__}: {exc}"[:120]
                    st = stages(text, raw)
                    rows.append({"role": role, "model": model, "factor": factor, "text": text, "rep": rep, "raw_text": (raw_text or "")[:300],
                                 "parse_error": parse_err, **st})
                    kept = [f["key"] for f in st["facts"] if f["key"]]
                    drops = [(f["attribute"], f["dropped_at"]) for f in st["facts"] if f["dropped_at"]]
                    print(f"[{role}/{factor}] rep{rep} {text[:42]!r}: raw={str(raw_text)[:110]!r} parse={parse_err or st['parsed']} kept={kept} drops={drops}")
    # summary per role × factor: how many DEV sentences yielded ≥1 raw fact, ≥1 kept slot
    from collections import defaultdict
    agg = defaultdict(lambda: {"raw_nonempty": 0, "kept": 0, "n": 0})
    for r in rows:
        a = agg[(r["role"], r["factor"])]; a["n"] += 1
        a["raw_nonempty"] += int(bool((r["raw"] or {}).get("facts")))
        a["kept"] += int(any(f["key"] for f in r["facts"]))
    print("\nSUMMARY (calls with ≥1 raw fact / with ≥1 kept slot / calls):")
    for k, a in sorted(agg.items()):
        print(f"  {k[0]:5s} {k[1]:9s} raw {a['raw_nonempty']}/{a['n']} · kept {a['kept']}/{a['n']}")
    print("versioned:", write_versioned("span_stages", {"rows": rows}))
    e.graph.close()
    try:
        os.remove(clone)
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
