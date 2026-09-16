"""Definitively locate the cross-session recall channel: dump the ACTUAL injected context that the
LLM would see for an ask in a different session, and show which section carries the answer. No gemma
generation (only embeds), and we RETRY until the query embed is healthy so the semantic channel is
fairly exercised (Ollama degrades under bursty load). Throwaway db."""
from __future__ import annotations
import os, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hmgfu.agent import AgentEngine          # noqa: E402
from hmgfu.retrieve import build_llm_context   # noqa: E402
from hmgfu.taxonomy import node_class          # noqa: E402
from _bench_paths import throwaway_db          # noqa: E402

DB = throwaway_db("diag_recall_channel.db")
if os.path.exists(DB):
    os.remove(DB)
e = AgentEngine(db_path=DB)
if not e.client.available():
    print("Ollama unreachable"); raise SystemExit(1)

# store in session A; verify the stored node actually got a real embedding (retry the burst)
p = None
for attempt in range(6):
    p = e.ingest("I have a cat named Pushkin.", source="user")
    node = e.graph.points[p.id]
    if node.embedding and any(abs(x) > 1e-9 for x in node.embedding):
        print(f"stored Pushkin node WITH healthy embedding (attempt {attempt+1}), len={len(node.embedding)}")
        break
    print(f"attempt {attempt+1}: embedding empty/degraded, retrying ingest")
else:
    print("WARNING: could not get a healthy embedding for the stored node")

# build the ask-side context exactly as agent_chat would (session is irrelevant to retrieval — the
# graph is global; that IS the cross-session mechanism)
q, retrieved, _ = e.retrieve("what is my cat called")
ctx, _ = build_llm_context(q, e.graph, retrieved=retrieved,
                           canonical=e.facts.render_lines(),
                           superseded=e.facts.superseded_values())
print("\n--- CHANNELS ---")
print("canon render_lines():", e.facts.render_lines())
print("retrieved nodes:", [(r.point.content[:45], f"reason={r.reason}", node_class(r.point)) for r in retrieved])
print("query embedding healthy:", bool(q.embedding) and any(abs(x) > 1e-9 for x in (q.embedding or [])))
print("\n'pushkin' IN injected context:", "pushkin" in ctx.lower())
# show the section that carries it
for block in ctx.split("\n\n"):
    if "pushkin" in block.lower():
        print("  --> carried in section:\n   ", block.replace("\n", "\n    ")[:400])
e.graph.close(); e.client.close()
