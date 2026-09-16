"""A/B the production grader prompt without mutating the live memory database."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hmgfu.grader import _GRADE_PROMPT  # noqa: E402
from hmgfu.ollama_client import OllamaClient  # noqa: E402
from hmgfu.sensitizer import parse_nano_json  # noqa: E402

MODELS = ("qwen2.5:1.5b-instruct", "gemma-cpu:latest")
CASES = [
    {"name": "cited_memory", "user": "What is my dog's name?",
     "assistant": "Your dog's name is Baltazar.",
     "memories": "0. [fact] The user's dog is named Baltazar.", "tools": "(none)",
     "memory": (0, {"cited"})},
    {"name": "unused_memory", "user": "What is 2 + 2?", "assistant": "4.",
     "memories": "0. [fact] The weather in Aveiro was rainy.", "tools": "(none)",
     "memory": (0, {"unused"})},
    {"name": "implied_memory", "user": "Do I enjoy mountains?",
     "assistant": "Yes, you enjoy alpine hiking.",
     "memories": "0. [fact] The user loves hiking in the Alps.", "tools": "(none)",
     "memory": (0, {"cited", "implied"})},
    {"name": "grounded_correction",
     "user": "Correction: my dog's name is Green, not Baltazar.",
     "assistant": "Understood; your dog's name is Green.",
     "memories": "0. [fact] The user's dog is named Baltazar.", "tools": "(none)",
     "correction": True},
    {"name": "helpful_tool", "user": "Run echo READY.",
     "assistant": "The command returned READY.", "memories": "(none)", "tools": "bash",
     "tool": ("bash", True)},
    {"name": "no_false_correction", "user": "Tell me a short joke.",
     "assistant": "Why did the node cross the grid? To connect.",
     "memories": "(none)", "tools": "(none)", "correction": False},
]


def grade_case(client: OllamaClient, model: str, case: dict) -> dict:
    content = client.chat(model, [
        {"role": "system", "content": _GRADE_PROMPT},
        {"role": "user", "content":
         f"USER: {case['user']}\n\nASSISTANT: {case['assistant']}\n\n"
         f"MEMORIES RECALLED:\n{case['memories']}\n\nTOOLS USED: {case['tools']}"},
    ], json_mode=True, temperature=0.0)
    payload = parse_nano_json(content)
    reasons = []
    if not isinstance(payload, dict):
        return {"name": case["name"], "pass": False, "reasons": ["invalid JSON object"]}
    if "memory" in case:
        index, accepted = case["memory"]
        grades = payload.get("memory_grades") if isinstance(payload.get("memory_grades"), list) else []
        if not any(isinstance(g, dict) and g.get("index") == index and g.get("grade") in accepted
                   for g in grades):
            reasons.append(f"memory expected {sorted(accepted)} got {grades}")
    if "correction" in case:
        got = isinstance(payload.get("user_correction"), dict)
        if got != case["correction"]:
            reasons.append(f"correction expected {case['correction']} got {payload.get('user_correction')}")
    if "tool" in case:
        name, helpful = case["tool"]
        grades = payload.get("tool_grades") if isinstance(payload.get("tool_grades"), list) else []
        if not any(isinstance(g, dict) and g.get("name") == name and g.get("helpful") is helpful
                   for g in grades):
            reasons.append(f"tool expected {case['tool']} got {grades}")
    return {"name": case["name"], "pass": not reasons, "reasons": reasons,
            "turn_score": payload.get("turn_score"), "payload": payload}


def main() -> int:
    client, results = OllamaClient(), {}
    try:
        for model in MODELS:
            rows = [grade_case(client, model, case) for case in CASES]
            results[model] = {"passed": sum(r["pass"] for r in rows),
                              "total": len(rows), "cases": rows}
            print(f"{model}: {results[model]['passed']}/{len(rows)}")
            for row in rows:
                print(f"  [{'PASS' if row['pass'] else 'FAIL'}] {row['name']}"
                      + (f" - {'; '.join(row['reasons'])}" if row['reasons'] else ""))
    finally:
        client.close()
    print("RESULT_JSON=" + json.dumps(results, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
