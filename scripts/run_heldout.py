"""Phase 70 M0.5 — run the sealed held-out set (scripts/oracles/heldout_m1.json) ONCE against the current code.
Fake provider, scratch DB/workspace (guard_scratch), no production, no network. Results are reported as they are."""
from __future__ import annotations

import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from _bench_paths import SCRATCH, guard_scratch, write_versioned  # noqa: E402
from tests.test_v2_agent import make_agent  # noqa: E402

import argparse
_ap = argparse.ArgumentParser()
_ap.add_argument("--set", default="m1", help="which sealed set: m1 | m2 | …")
_ARGS, _ = _ap.parse_known_args()
CASES = json.load(open(os.path.join(ROOT, "scripts", "oracles", f"heldout_{_ARGS.set}.json"), encoding="utf-8"))


def _script(items):
    out = []
    for it in items:
        if isinstance(it, str):
            out.append({"content": it, "tool_calls": []})
        else:
            out.append({"content": "", "tool_calls": [{"name": it[0], "arguments": it[1]}]})
    return out


def run_turn_case(case):
    os.makedirs(SCRATCH, exist_ok=True)
    folder = tempfile.mkdtemp(prefix="heldout_", dir=SCRATCH)
    guard_scratch(os.path.join(folder, "agent.db"), folder)
    import pathlib
    engine, _ = make_agent(pathlib.Path(folder), _script(case["script"]))   # the factory expects a Path
    for k, v in {"grader_enabled": False, "workspace_dir": folder, "plan_step_recall": False, "thinking_mode": "off",
                 "full_dream_every_n_turns": 0, "mini_dream_every_n_turns": 0}.items():
        engine.settings.set(k, v)
    act = case.get("act", "statement")
    orig = engine.retrieve
    def retrieve(text, **kw):
        q, rs, ms = orig(text, **kw)
        q.conversation_act = act; q.requested_tools = []; q.action_requested = False
        return q, rs, ms
    engine.retrieve = retrieve
    called = []
    if case.get("skill"):
        engine.tools.schemas[case["skill"]] = {"name": case["skill"], "description": "synthetic skill without effect declaration",
                                              "parameters": {"type": "object", "properties": {}}}
        engine.tools.skill_handlers[case["skill"]] = lambda name, args: (called.append(name) or json.dumps({"ok": True}))
    sid = engine.sessions.create_session("heldout")["id"]
    if case.get("preplan"):
        engine.session_plans.save(sid, case["preplan"])
    traces = []
    for msg in case["messages"]:
        r = engine.agent_chat(msg, session_id=sid)
        traces += r["tool_trace"]
    exp, actual, ok = case["expect"], {}, True
    names_exec = [t["name"] for t in traces if not t.get("blocked") and not t.get("failed")]
    names_blocked = [t["name"] for t in traces if t.get("blocked")]
    if "widgets" in exp:
        actual["widgets"] = len(engine.sessions.widgets(sid)); ok &= actual["widgets"] == exp["widgets"]
    for f in exp.get("files_absent", []):
        present = os.path.exists(os.path.join(folder, f)); actual[f"absent:{f}"] = not present; ok &= not present
    for f in exp.get("files_present", []):
        present = os.path.exists(os.path.join(folder, f)); actual[f"present:{f}"] = present; ok &= present
    for n in exp.get("blocked", []):
        actual[f"blocked:{n}"] = n in names_blocked; ok &= n in names_blocked
    for n in exp.get("executed", []):
        actual[f"executed:{n}"] = n in names_exec; ok &= n in names_exec
    if "skill_called" in exp:
        actual["skill_called"] = bool(called); ok &= bool(called) == exp["skill_called"]
    if "plan_status" in exp:
        p = engine.session_plans.get(sid) or {}; actual["plan_status"] = p.get("status"); ok &= p.get("status") == exp["plan_status"]
    if "steps" in exp:
        p = engine.session_plans.get(sid) or {}; got = [s.get("status") for s in p.get("steps", [])]
        actual["steps"] = got; ok &= got == exp["steps"]
    if exp.get("no_failed"):
        failed = [t["name"] for t in traces if t.get("failed")]; actual["failed"] = failed; ok &= not failed
    return {"id": case["id"], "family": case["family"], "passed": bool(ok), "actual": actual,
            "trace": [(t["name"], "blocked" if t.get("blocked") else ("failed" if t.get("failed") else "ok")) for t in traces]}


def run_facts_case(case):
    from hmgfu.facts import FactStore
    import pathlib
    os.makedirs(SCRATCH, exist_ok=True)
    folder = tempfile.mkdtemp(prefix="heldout_facts_", dir=SCRATCH)
    st = FactStore(os.path.join(folder, "f.db"))
    if case.get("mapper"):
        m = case["mapper"]
        st.bind_mapper(lambda text, *a, **k: {"slot": m["slot"], "value": m["value"], "op": "set"})
    for msg in case["messages"]:
        st.apply_all(msg, "user_explicit")
    active = {f["key"]: f["value"] for f in st.active()}
    exp, actual, ok = case["expect"], {"active": active}, True
    if "active" in exp:
        ok &= active == exp["active"]
    if "active_subset" in exp:
        ok &= all(active.get(k) == v for k, v in exp["active_subset"].items())
    for spec in exp.get("active_absent_values", []):
        val, key = spec.split("@"); ok &= active.get(key) != val
    if "active_values_contain" in exp:
        blob = json.dumps(active, ensure_ascii=False); ok &= all(v in blob for v in exp["active_values_contain"])
    if "render_absent" in exp or "render_contains" in exp:
        lines = " ".join(st.render_lines()); actual["render"] = lines
        ok &= all(v not in lines for v in exp.get("render_absent", [])) and all(v in lines for v in exp.get("render_contains", []))
    if "history_contains" in exp:
        hist = " ".join(st.render_history_lines()) if hasattr(st, "render_history_lines") else ""
        actual["history"] = hist; ok &= all(v in hist for v in exp["history_contains"])
    st._db.close()
    return {"id": case["id"], "family": case["family"], "passed": bool(ok), "actual": actual}


def run_prospective_case(case):
    """75.2: the deterministic trigger detector against one utterance at a frozen clock."""
    from hmgfu.prospective import detect
    got = detect(case["text"], case["now"]) or {"kind": "none"}
    exp, actual, ok = case["expect"], {"kind": got.get("kind"), "due": got.get("due"), "text": got.get("text"),
                                       "keywords": got.get("keywords")}, True
    ok &= got.get("kind") == exp["kind"]
    if "due" in exp:
        ok &= got.get("due") == exp["due"]
    if "due_prefix" in exp:
        ok &= str(got.get("due") or "").startswith(exp["due_prefix"])
    if "text_contains" in exp:
        ok &= exp["text_contains"].lower() in (got.get("text") or "").lower()
    if "keywords_contain" in exp:
        ok &= all(k in (got.get("keywords") or []) for k in exp["keywords_contain"])
    return {"id": case["id"], "family": case["family"], "passed": bool(ok), "actual": actual}


def main() -> int:
    from hmgfu.authority import shell_is_mutating
    rows = []
    for c in CASES.get("prospective", []):
        try:
            rows.append(run_prospective_case(c))
        except Exception as exc:
            rows.append({"id": c["id"], "family": c["family"], "passed": False, "actual": {"error": repr(exc)[:200]}})
    for c in CASES.get("facts", []):
        try:
            rows.append(run_facts_case(c))
        except Exception as exc:
            rows.append({"id": c["id"], "family": c["family"], "passed": False, "actual": {"error": repr(exc)[:200]}})
    for s in CASES["shell"]:
        got = not shell_is_mutating(s["cmd"])
        rows.append({"id": "shell:" + s["cmd"][:40], "family": "shell", "passed": got == s["read_only"], "actual": {"read_only": got}})
    for c in CASES["turns"]:
        try:
            rows.append(run_turn_case(c))
        except Exception as exc:
            rows.append({"id": c["id"], "family": c["family"], "passed": False, "actual": {"error": repr(exc)[:200]}})
    by_family = {}
    for r in rows:
        f = by_family.setdefault(r["family"], [0, 0]); f[1] += 1; f[0] += int(r["passed"])
    for r in rows:
        print(("PASS" if r["passed"] else "FAIL"), r["id"], "|", json.dumps(r["actual"], ensure_ascii=False)[:120])
    print("BY FAMILY:", {k: f"{v[0]}/{v[1]}" for k, v in by_family.items()})
    print("TOTAL", sum(r["passed"] for r in rows), "/", len(rows))
    print("versioned:", write_versioned(f"heldout_{_ARGS.set}", {"by_family": by_family, "results": rows}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
