"""Terminal chat REPL. Commands: :dream :stats :why :quit

Run: python -m hmgfu.cli
"""

from __future__ import annotations

import logging

from .chat import HMGFuEngine

logging.basicConfig(level=logging.WARNING)


def main():
    engine = HMGFuEngine()
    if not engine.client.available():
        print("! Ollama is not reachable — start it first (chat needs gemma4:12b).")
        return
    print("HMG-Fu chat (gemma4:12b + relational memory). Commands: :dream :stats :why :quit")
    last = None
    while True:
        try:
            line = input("\nyou> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            continue
        if line == ":quit":
            break
        if line == ":stats":
            print(engine.graph.stats())
            continue
        if line == ":dream":
            report = engine.dream()
            print(f"dream> {report.summary}")
            for insight in report.insights:
                print(f"  insight: {insight}")
            continue
        if line == ":why":
            if not last:
                print("no previous turn")
                continue
            print(f"retrieval took {last['retrieval_ms']} ms; memories used:")
            for r in last["retrieved"]:
                print(f"  [{r['score']:.2f}] {r['point']['title'][:50]} — {r['reason']}")
            continue
        last = engine.chat(line)
        print(f"\nhmg-fu> {last['response']}")
        print(f"        ({len(last['retrieved'])} memories, {last['retrieval_ms']} ms retrieval)")
    engine.graph.close()
    engine.client.close()


if __name__ == "__main__":
    main()
