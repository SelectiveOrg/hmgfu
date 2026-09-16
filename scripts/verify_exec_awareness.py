"""4th reported symptom — 'execution harnesses and awareness'. Drive a LIVE gemma turn that must
call the bash tool and then REPORT its output, proving the execution harness runs AND the agent is
aware of the result. Read-only, deterministic sentinel. Talks to the live server on :8777.

NB: /api/agent/chat returns `response` (the reply text) and `tool_trace` (the executed tool calls
with results) — NOT `reply`/`tools`. Reading the wrong keys made this look empty once (false alarm)."""
import json, urllib.request

SENTINEL = "HMGFU_ALIVE_42"
body = json.dumps({"message": f"Run this shell command and tell me exactly what it printed: echo {SENTINEL}"}).encode()
req = urllib.request.Request("http://127.0.0.1:8777/api/agent/chat", data=body,
                             headers={"Content-Type": "application/json"})
print("=== exec + awareness end-to-end ===")
try:
    r = json.loads(urllib.request.urlopen(req, timeout=180).read())
    reply = r.get("response") or ""
    offered = r.get("tools_offered") or []
    trace = r.get("tool_trace") or []
    bash_calls = [t for t in trace if t.get("name") == "bash"]
    ran_ok = any(not t.get("failed") and SENTINEL in (t.get("result") or "") for t in bash_calls)
    print("REPLY:", reply[:400])
    print("---")
    print("bash offered           :", "bash" in offered)
    print("bash executed OK        :", ran_ok, f"({len(bash_calls)} bash call(s))")
    print("forced_finalization    :", r.get("forced_finalization"))
    print("agent AWARE (echoed)    :", SENTINEL in reply)
    print("VERDICT:", "PASS" if ("bash" in offered and ran_ok and SENTINEL in reply) else "FAIL")
except Exception as e:
    print("ERROR:", type(e).__name__, e)
