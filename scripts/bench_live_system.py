"""Complete live-corpus benchmark for HMG-Fu + gemma4:12b.

The production SQLite database is copied with SQLite's online-backup API. All model turns,
memory reinforcement, widgets, directives, and corrections happen only in that clone.

Coverage:
- every stored node: ontology, empty-content, macro-source, and ephemeral-injection invariants;
- live-corpus precision: greeting/no-match, identity/canonical conflict, retrieval bounds;
- cross-session facts, corrections, standing directives, and rolling session nodes;
- proactive execution: shell, workspace inspection, widget, memory search, live search, skill;
- tool precision: no action surface for a greeting, required action tool actually called.

Run: .venv/Scripts/python scripts/bench_live_system.py
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hmgfu import config  # noqa: E402
from hmgfu.agent import AgentEngine  # noqa: E402
from hmgfu.models import RetrievedMemory  # noqa: E402
from hmgfu.retrieve import organise_for_injection, render_injection  # noqa: E402
from hmgfu.taxonomy import node_class  # noqa: E402

SCRATCH = ROOT / "scratch"
CLONE_DB = SCRATCH / "bench_live_system.db"
# The chat model under test is overridable so the SAME suite can measure how the HMG-Fu
# scaffolding drives a DIFFERENT brain (default = the project's gemma4:12b). Every other role
# (nano/grader/embedder) stays fixed so a score delta is attributable to the chat model alone.
BENCH_CHAT_MODEL = os.environ.get("HMGFU_BENCH_CHAT_MODEL", "gemma4:12b")
WORKSPACE = SCRATCH / "bench_live_workspace"
RESULTS: list[dict] = []
_T0: list = [None]   # process-start perf_counter, set in main()


def check(name: str, ok: bool, detail: str = "", mandatory: bool = True) -> None:
    row = {"name": name, "pass": bool(ok), "mandatory": mandatory, "detail": detail[:500],
           "t": time.perf_counter()}   # stamp for wall-clock/latency reporting (model comparison)
    RESULTS.append(row)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail[:220]}" if detail else ""))


def timing_summary() -> dict:
    """Total wall-clock + mean seconds per LIVE (model-driven L*) check — the latency signal that
    makes a chat-model comparison meaningful (structural S* checks are model-free)."""
    stamps = [r["t"] for r in RESULTS if "t" in r]
    if len(stamps) < 2:
        return {"total_s": 0.0, "live_checks": 0, "mean_live_s": 0.0}
    total = stamps[-1] - _T0[0] if _T0[0] is not None else stamps[-1] - stamps[0]
    live = [r for r in RESULTS if r["name"].startswith("L") and "t" in r]
    prev = _T0[0] if _T0[0] is not None else stamps[0]
    live_secs, last = [], prev
    for r in RESULTS:
        if "t" not in r:
            continue
        if r["name"].startswith("L"):
            live_secs.append(r["t"] - last)
        last = r["t"]
    mean_live = sum(live_secs) / len(live_secs) if live_secs else 0.0
    return {"total_s": round(total, 1), "live_checks": len(live),
            "mean_live_s": round(mean_live, 1)}


def clone_live_db() -> None:
    SCRATCH.mkdir(exist_ok=True)
    if CLONE_DB.exists():
        CLONE_DB.unlink()
    source = sqlite3.connect(config.DB_PATH)
    target = sqlite3.connect(CLONE_DB)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()


def tools_used(result: dict) -> set[str]:
    return {t["name"] for t in result.get("tool_trace", [])
            if not t.get("failed") and not t.get("blocked")}


def tools_called(result: dict) -> set[str]:
    return {t["name"] for t in result.get("tool_trace", [])}


def structural_audit(engine: AgentEngine) -> None:
    print("\nSTRUCTURAL AUDIT — every node in cloned live graph")
    points = engine.graph.all_points()
    active = [p for p in points if p.status == "active"]
    classes = Counter(node_class(p) for p in active)
    check("S1 every node has a canonical ontology class",
          len(points) == sum(1 for p in points if node_class(p)),
          f"nodes={len(points)} active_classes={dict(classes)}")
    empty = [p.id for p in active if not (p.content or p.summary or p.title).strip()]
    check("S2 no active empty memories", not empty, f"empty={empty[:8]}")

    missing_sources = []
    for macro_id, source_ids in engine.graph.macro_sources.items():
        if macro_id not in engine.graph.points or not source_ids:
            missing_sources.append((macro_id, "empty/missing macro"))
        for source_id in source_ids:
            if source_id not in engine.graph.points:
                missing_sources.append((macro_id, source_id))
    check("S3 every macro containment link resolves", not missing_sources,
          f"macros={len(engine.graph.macro_sources)} broken={missing_sources[:8]}")

    ephemeral = [p for p in active if "_ephemeral" in p.keywords]
    leaked = []
    for point in ephemeral:
        injection = organise_for_injection([RetrievedMemory(point=point, score=1.0)], engine.graph)
        rendered = render_injection(injection, 600)
        if point.content and point.content in rendered:
            leaked.append(point.id)
    check("S4 every ephemeral memory is excluded from answer context", not leaked,
          f"checked={len(ephemeral)} leaked={leaked[:8]}")

    specials = {"skill", "tool", "directive", "session"}
    special_count = sum(1 for p in active if node_class(p) in specials)
    check("S5 special nodes are present for their dedicated mechanisms", special_count > 0,
          f"special_nodes={special_count}")

    canon = {f["key"]: f["value"] for f in engine.facts.active()}
    stale_identity = []
    current_name = canon.get("name", "").lower()
    if current_name:
        for p in active:
            text = f"{p.title} {p.summary} {p.content}".lower()
            if p.type in ("fact", "person") and re.search(r"\b(?:your|my) name is\b", text):
                if current_name not in text:
                    stale_identity.append((p.id, (p.summary or p.content)[:90]))
    check("S6 no active fact/person contradicts canonical identity", not stale_identity,
          f"canonical={canon.get('name')} stale={stale_identity[:5]}")

    derived_as_user = [p.id for p in active if p.source == "user" and
                       any(k.startswith("pa3:nodes:") for k in p.keywords)]
    check("S7 imported derived PA3 nodes are not falsely trusted as user-authored",
          not derived_as_user, f"mis-sourced={len(derived_as_user)}")


def live_scenarios(engine: AgentEngine) -> None:
    print(f"\nLIVE SCENARIOS — chat model under test: {BENCH_CHAT_MODEL.upper()}")
    provider, model = engine.registry.resolve("chat")
    check(f"L0 configured chat model ({BENCH_CHAT_MODEL}) is live",
          model == BENCH_CHAT_MODEL and provider.available(),
          f"provider={provider.name} model={model}")
    check("L0b evidence-based nano/grader role split is active",
          engine.settings.get("nano_model") == "qwen2.5:1.5b-instruct"
          and engine.settings.get("grader_model") == "gemma-cpu:latest"
          and engine.settings.get("grader_producer") == "nano",
          f"nano={engine.settings.get('nano_model')} grader={engine.settings.get('grader_model')} "
          f"producer={engine.settings.get('grader_producer')}")

    greeting = engine.agent_chat("hello")
    check("L1 greeting recall is precise (≤3 memories)", len(greeting["retrieved"]) <= 3,
          f"recalled={len(greeting['retrieved'])}")
    check("L2 greeting offers no action tools", not greeting["tools_offered"],
          f"offered={greeting['tools_offered']}")

    identity = engine.agent_chat("Do you know me? State only facts you are confident are current.")
    identity_low = identity["response"].lower()
    check("L3 canonical current name wins live answer",
          "teodoro" in identity_low and "[your name]" not in identity_low,
          identity["response"][:240])
    check("L4 stale identity names do not leak into answer",
          "sebastian" not in identity_low and "mary" not in identity_low,
          identity["response"][:240])
    check("L5 all live retrieval results obey configured limit",
          len(identity["retrieved"]) <= engine.settings.get("retrieval_limit"),
          f"recalled={len(identity['retrieved'])} limit={engine.settings.get('retrieval_limit')}")

    shell = engine.agent_chat("Run the shell command `echo PROACTIVE-FU-51` and report its output.")
    check("L6 explicit command is proactively executed", "bash" in tools_used(shell),
          f"used={sorted(tools_used(shell))}")
    check("L7 tool result is used in answer", "PROACTIVE-FU-51" in shell["response"],
          shell["response"][:180])

    project = engine.agent_chat(
        "Inspect the selected project folder before answering. What is its exact benchmark marker?"
    )
    check("L8 project question proactively inspects workspace",
          bool(tools_used(project) & {"read_file", "bash"}),
          f"used={sorted(tools_used(project))}")
    check("L9 workspace evidence reaches answer", "HMG-LIVE-BENCH-51" in project["response"],
          project["response"][:220])

    widget = engine.agent_chat(
        "Create a note widget titled Live Benchmark with text 'proactive widget complete'."
    )
    check("L10 requested widget is proactively created", "create_widget" in tools_used(widget),
          f"used={sorted(tools_used(widget))}")

    memory = engine.agent_chat(
        "Search your memory for the exact project codeword ORCA-7 and tell me what you find."
    )
    check("L11 explicit memory search calls memory_search", "memory_search" in tools_used(memory),
          f"used={sorted(tools_used(memory))}")
    memory_low = memory["response"].lower()
    check("L12 searched memory is reflected in answer",
          "ORCA-7" in memory["response"] and "couldn't find" not in memory_low
          and "not find" not in memory_low,
          memory["response"][:220])

    skill = engine.agent_chat("Use the gog_status skill to check whether Google gog is installed.")
    check("L13 explicit skill request calls gog_status", "gog_status" in tools_called(skill),
          f"called={sorted(tools_called(skill))} successful={sorted(tools_used(skill))}")

    zoom = engine.agent_chat("Use memory_zoom to inspect the high-level memory overview.")
    check("L14 explicit hierarchy request calls memory_zoom", "memory_zoom" in tools_used(zoom),
          f"used={sorted(tools_used(zoom))}")

    taught = engine.agent_chat(
        "From now on, always begin the first reply of every new conversation with a short joke.",
        explicit=True,
    )
    opener = next((d for d in engine.directives.active() if d["kind"] == "conversation_opener"), None)
    check("L15 conversation-opening instruction becomes a durable directive", opener is not None,
          str(opener))
    fresh = engine.agent_chat("hello", session_id=None)
    joke_low = fresh["response"].lower()
    joke_signal = any(x in joke_low for x in ("why did", "because", "walks into", "knock knock"))
    check("L16 new conversation proactively applies the joke opener", joke_signal,
          fresh["response"][:240])

    engine.agent_chat("My name is Benchmark Oldname.", explicit=True)
    engine.agent_chat("Correction: I am not Benchmark Oldname. My name is Benchmark Newname.",
                      explicit=True)
    corrected = engine.agent_chat("What is my name now?")
    corrected_low = corrected["response"].lower()
    check("L17 correction supersedes stale identity end-to-end",
          "benchmark newname" in corrected_low and "oldname" not in corrected_low,
          corrected["response"][:200])

    session_nodes = [p for p in engine.graph.active_points() if p.type == "session"]
    keyed = [k for p in session_nodes for k in p.keywords if k.startswith("session:")]
    check("L18 rolling session nodes remain one-per-session", len(keyed) == len(set(keyed)),
          f"session_nodes={len(session_nodes)} unique={len(set(keyed))}")

    clock = engine.agent_chat(
        "What is the exact current local date and time? Return YYYY-MM-DD HH:MM and UTC offset."
    )
    clock_ctx = clock["runtime_context"]
    clock_text = clock["response"]
    clock_ok = (not clock["tools_offered"] and not clock["tool_trace"]
                and clock_ctx["local_date"] in clock_text
                and clock_ctx["local_time"][:5] in clock_text
                and clock_ctx["utc_offset"] in clock_text)
    check("L19 main model uses the exact per-turn local clock", clock_ok,
          f"runtime={clock_ctx} answer={clock_text[:180]}")

    clock_pt = engine.agent_chat(
        "Que horas sao agora? Responda com YYYY-MM-DD HH:MM e o deslocamento UTC exatos."
    )
    pt_ctx = clock_pt["runtime_context"]
    pt_text = clock_pt["response"]
    pt_clock_ok = (not clock_pt["tools_offered"] and not clock_pt["tool_trace"]
                   and pt_ctx["local_date"] in pt_text
                   and pt_ctx["local_time"][:5] in pt_text
                   and pt_ctx["utc_offset"] in pt_text)
    check("L20 Portuguese current-time request uses the same exact clock", pt_clock_ok,
          f"runtime={pt_ctx} answer={pt_text[:180]}")

    shell_pt = engine.agent_chat(
        "Execute o comando shell `echo PROATIVO-PT-51` e informe o resultado."
    )
    check("L21 Portuguese action proactively calls bash",
          "bash" in tools_used(shell_pt) and "PROATIVO-PT-51" in shell_pt["response"],
          f"used={sorted(tools_used(shell_pt))} answer={shell_pt['response'][:140]}")

    memory_pt = engine.agent_chat(
        "Pesquise na sua memoria pelo codigo exato ORCA-7 e diga o que encontrou."
    )
    check("L22 Portuguese memory action calls memory_search",
          "memory_search" in tools_used(memory_pt) and "ORCA-7" in memory_pt["response"],
          f"used={sorted(tools_used(memory_pt))} answer={memory_pt['response'][:140]}")

    widget_pt = engine.agent_chat(
        "Crie um widget de nota chamado Teste Multilingue com o texto 'widget proativo pronto'."
    )
    check("L23 Portuguese canvas action calls create_widget",
          "create_widget" in tools_used(widget_pt),
          f"used={sorted(tools_used(widget_pt))}")

    engine.agent_chat(
        "De agora em diante, comece cada nova conversa com uma piada curta.", explicit=True
    )
    opener_pt = next((d for d in engine.directives.active()
                      if d["kind"] == "conversation_opener"), None)
    check("L24 Portuguese standing instruction is stored semantically",
          bool(opener_pt and opener_pt.get("fallback_text") and
               "De agora" in opener_pt.get("instruction", "")), str(opener_pt))
    fresh_pt = engine.agent_chat("ola", session_id=None)
    fallback = opener_pt.get("fallback_text", "") if opener_pt else ""
    check("L25 generated multilingual opener is deterministically applied",
          bool(fallback and fresh_pt["response"].lstrip().startswith(fallback)),
          fresh_pt["response"][:240])


def main() -> int:
    config.OLLAMA_TIMEOUT_S = min(config.OLLAMA_TIMEOUT_S, 180.0)
    _T0[0] = time.perf_counter()
    clone_live_db()
    if WORKSPACE.exists():
        shutil.rmtree(WORKSPACE)
    WORKSPACE.mkdir(parents=True)
    (WORKSPACE / "PROJECT_ID.md").write_text(
        "# Benchmark Workspace\n\nMarker: HMG-LIVE-BENCH-51\n", encoding="utf-8"
    )

    engine = AgentEngine(db_path=str(CLONE_DB))
    try:
        if not engine.client.available():
            print("FAIL: Ollama is not reachable")
            return 1
        engine.settings.update({
            "chat_provider": "ollama", "chat_model": BENCH_CHAT_MODEL,
            "workspace_dir": str(WORKSPACE), "grader_enabled": False,
            "mini_dream_every_n_turns": 0, "full_dream_every_n_turns": 0,
            "retrieval_limit": 12, "agent_max_iterations": 6,
        })
        engine._apply_nano_gates()
        structural_audit(engine)
        live_scenarios(engine)
    finally:
        engine.graph.close()
        engine.client.close()

    failed = [r for r in RESULTS if r["mandatory"] and not r["pass"]]
    timing = timing_summary()
    print("\n=== COMPLETE LIVE BENCHMARK ===")
    print(f"MODEL={BENCH_CHAT_MODEL}  PASS={len(RESULTS)-len(failed)}/{len(RESULTS)} FAIL={len(failed)}")
    print(f"TIMING total={timing['total_s']}s  live_checks={timing['live_checks']}  "
          f"mean_per_live_turn={timing['mean_live_s']}s")
    for row in failed:
        print(f"  FAIL {row['name']}: {row['detail']}")
    print("RESULT_JSON=" + json.dumps({"model": BENCH_CHAT_MODEL, "checks": RESULTS,
                                       "failed": len(failed), "timing": timing}))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
