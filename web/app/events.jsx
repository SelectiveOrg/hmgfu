/* Cowork — translate WS turn events into transcript cards (PA3 block-sequencing model). */

/* Builds/patches the message list for one turn. Cards: user, thinking, tool (paired
   call+result), memory (recalled-N pill), assistant, grade, error. */
class TurnBuilder {
  constructor(setMessages) {
    this.setMessages = setMessages;
    this.planMsgId = null;    // the turn's PlanTracker card (updated in place)
    this.toolGroupId = null;  // current collapsible tool-group card
    this.thinkingId = null;   // current collapsible thinking card
    this.lastKind = null;     // block sequencing (PA3 lastBlockByTurn): interleave in order
  }
  // thinking block: append to the OPEN thinking card only if it is still the last block,
  // else start a NEW card at the chronological position (so thinking→tool→thinking reads right)
  upsertThinking(text) {
    if (!text || !text.trim()) return;
    if (this.lastKind === "thinking" && this.thinkingId) {
      this.setMessages((m) => m.map((x) => x.id === this.thinkingId
        ? { ...x, text: x.text ? x.text + "\n\n" + text : text } : x));
    } else {
      this.thinkingId = rid();
      this.setMessages((m) => [...m, { id: this.thinkingId, kind: "thinking", text, expandable: true }]);
    }
    this.lastKind = "thinking";
  }
  upsertPlan(plan) {
    const snapshot = JSON.parse(JSON.stringify(plan));
    if (this.planMsgId) {
      this._patch(this.planMsgId, { plan: snapshot });
    } else {
      this.planMsgId = rid();
      this.setMessages((m) => [...m, { id: this.planMsgId, kind: "plan", plan: snapshot }]);
    }
    this.lastKind = "plan";
  }
  _push(msg) { this.setMessages((m) => [...m, { id: rid(), ...msg }]); this.lastKind = msg.kind; }
  _patch(id, patch) {
    this.setMessages((m) => m.map((x) => x.id === id ? { ...x, ...patch } : x));
  }
  pushUser(text) { this._push({ kind: "user", text, time: nowLabel() }); }
  pushMemory(count, items) { this._push({ kind: "memory", count, items }); }
  pushContext(ev) { this._push({ kind: "context", tools: ev.tools || [], skills: ev.skills || [], directives: ev.directives || [] }); }
  pushToolCall(ev) {
    // consecutive tool calls collapse into ONE tool-group card (PA3 block-sequencing)
    const entry = { callId: ev.id, command: describeTool(ev.name, ev.arguments),
                    status: "running", name: ev.name, args: ev.arguments, output: "" };
    if (this.lastKind === "toolgroup" && this.toolGroupId) {
      this.setMessages((m) => m.map((x) => x.id === this.toolGroupId
        ? { ...x, entries: [...x.entries, entry] } : x));
    } else {
      this.toolGroupId = rid();
      this.setMessages((m) => [...m, { id: this.toolGroupId, kind: "toolgroup", entries: [entry] }]);
    }
    this.lastKind = "toolgroup";
  }
  patchToolResult(ev) {
    let out = ev.result;
    try { out = JSON.stringify(JSON.parse(ev.result), null, 2); } catch {}
    const status = ev.blocked ? "blocked" : (ev.failed ? "error" : "success");
    this.setMessages((m) => m.map((x) => {
      if (x.kind !== "toolgroup") return x;
      return { ...x, entries: x.entries.map((e) => e.callId === ev.id
        ? { ...e, status, exitCode: ev.failed ? 1 : 0, output: (out || "").slice(0, 4000) } : e) };
    }));
  }
  pushAssistant(text) { this._push({ kind: "assistant", text, time: nowLabel() }); }
  pushGrade(grade) { this._push({ kind: "grade", grade }); }
  pushTimings(timings) { this._push({ kind: "timings", timings }); }   // 73.0: where the turn's time went
  pushRunbooks(items) { this._push({ kind: "runbooks", items }); }     // 75.1: procedural memory offered
  pushProspective(mode, items) { this._push({ kind: "prospective", mode, items }); }   // 75.2
  pushVerify(kind, report) { this._push({ kind, report }); }   // 69.6: "saydo" | "grounding" feedback
  pushError(text) { this._push({ kind: "error", text }); }
}

/* Route one event; may also drive the canvas (widget events) + stats. */
function handleEvent(ev, turn, canvas) {
  switch (ev.type) {
    case "thinking": turn.upsertThinking(ev.text); break;
    case "memory_used":
      if (ev.count > 0) turn.pushMemory(ev.count, ev.items || []);
      // live hex-field activation + trace widget (Phase 31 debug view in-canvas)
      if (canvas.setActivated) canvas.setActivated({ ids: (ev.items || []).map((i) => i.id), items: ev.items || [], at: Date.now() });
      break;
    case "context_pack":
      if ((ev.tools || []).length || (ev.skills || []).length || (ev.directives || []).length) {
        turn.pushContext(ev);
        if (canvas.sid) saveContext(canvas.sid, ev);   // survive refresh (restored in historyToMessages)
      }
      break;
    case "tool_call": turn.pushToolCall(ev); break;
    case "tool_result": turn.patchToolResult(ev); break;
    case "text": /* interim; final arrives on done */ break;
    case "plan":
    case "plan_update": turn.upsertPlan(ev.plan); break;
    case "status": if (canvas.setLive) canvas.setLive(ev); break;
    case "turn_timings": turn.pushTimings(ev); break;   // 73.0
    case "runbooks": turn.pushRunbooks(ev.items || []); break;   // 75.1
    case "prospective_set": turn.pushProspective("set", [ev.item]); break;          // 75.2
    case "prospective_fired": turn.pushProspective("fired", ev.items || []); break;
    case "prospective_cancelled": turn.pushProspective("cancelled", [ev.item]); break;
    case "grade":
      turn.pushGrade(ev);
      if (canvas.setGraded) canvas.setGraded({ ...ev, at: Date.now() });
      break;
    case "saydo":        // 69.6: the say-do gate acted (proposal, correction, re-ask) — say so
    case "grounding":    // 69.6: values the reply could not trace — say so
      turn.pushVerify(ev.type, ev);
      break;
    case "tool_feedback":
      if (canvas.setGraded) canvas.setGraded({ kind: "feedback", ...ev, at: Date.now() });
      break;
    case "correction":   // live: a correction fired in the (post-turn) drain → animate + refetch real state
      if (canvas.setGraded) canvas.setGraded({ kind: "correction", ...ev, at: Date.now() });
      window.dispatchEvent(new CustomEvent("hmg-graph-changed"));   // hex map re-pulls real lifecycle/ledger
      break;
    case "widget": handleWidgetEvent(ev, canvas); break;
    case "done":
      if (ev.final_text) turn.pushAssistant(ev.final_text);
      if (ev.stats) canvas.setStats(ev.stats);
      break;
    case "error": turn.pushError(ev.message || "error"); break;
    default: break;
  }
}

function handleWidgetEvent(ev, canvas) {
  const w = ev.widget || {};
  if (ev.action === "create") {
    canvas.addWidget(w.type, w.title, { id: w.id, generated: true, ...(w.props || {}) });
  } else if (ev.action === "remove") {
    canvas.setWidgets((ws) => ws.filter((x) => x.id !== w.id));
  } else if (ev.action === "update") {
    canvas.setWidgets((ws) => ws.map((x) => x.id === w.id ? { ...x, title: w.title || x.title, ...(w.props || {}) } : x));
  }
}

/* Reconstruct transcript cards from persisted history (PA3 metadata contract).
   `sid` lets us restore the recalled-tools card (context_pack) from localStorage, since it is
   a live-only event and not part of the server-persisted message metadata. */
function historyToMessages(history, sid) {
  const out = [];
  (history || []).forEach((h) => {
    const meta = h.metadata || {};
    if (h.role === "user") { out.push({ id: rid(), kind: "user", text: h.content, time: "" }); return; }
    // recalled memory + context FIRST (matches the live event order — "recalled at the top")
    if (meta.memory_count > 0) out.push({ id: rid(), kind: "memory", count: meta.memory_count, items: meta.memory_items || [] });
    const ctx = sid ? loadContext(sid, h.turn_seq) : null;   // recalled tools/skills/directives
    if (ctx && (ctx.tools.length || ctx.skills.length || ctx.directives.length))
      out.push({ id: rid(), kind: "context", tools: ctx.tools, skills: ctx.skills, directives: ctx.directives });
    if (meta.thinking) out.push({ id: rid(), kind: "thinking", text: meta.thinking, expandable: true });
    if (meta.plan) out.push({ id: rid(), kind: "plan", plan: meta.plan });
    if ((meta.tool_calls || []).length) {
      out.push({ id: rid(), kind: "toolgroup", entries: meta.tool_calls.map((tc) => {
        let out2 = tc.result;
        try { out2 = JSON.stringify(JSON.parse(tc.result), null, 2); } catch {}
        return { callId: rid(), command: describeTool(tc.name, tc.arguments), name: tc.name,
          status: tc.blocked ? "blocked" : (tc.failed ? "error" : "success"), exitCode: tc.failed ? 1 : 0,
          output: (out2 || "").slice(0, 4000) };
      }) });
    }
    out.push({ id: rid(), kind: "assistant", text: h.content, time: "" });
    if (meta.saydo) out.push({ id: rid(), kind: "saydo", report: meta.saydo });          // 69.6: self-grade survives
    if (meta.grounding) out.push({ id: rid(), kind: "grounding", report: meta.grounding });
    if (meta.grade) out.push({ id: rid(), kind: "grade", grade: meta.grade });
    if (meta.timings) out.push({ id: rid(), kind: "timings", timings: meta.timings });   // 73.0
  });
  return out;
}

function describeTool(name, args) {
  if (!args) return name;
  if (name === "bash") return "$ " + (args.command || "");
  if (name === "memory_search") return `memory_search "${(args.query || "").slice(0, 40)}"`;
  if (name === "read_file") return `read ${args.path || ""}`;
  if (name === "write_file") return `write ${args.path || ""}`;
  if (name === "create_widget") return `create_widget ${args.type || ""} "${args.title || ""}"`;
  const keys = Object.keys(args || {});
  return name + (keys.length ? " " + keys.map((k) => `${k}=${String(args[k]).slice(0, 24)}`).join(" ") : "");
}
/* context_pack (recalled tools/skills/directives) is a live-only WS event — cache it per
   session+turn so it survives a refresh, then rehydrate in historyToMessages. */
function ctxKey(sid, turnSeq) { return `hmgfu.ctx.${sid}.${turnSeq}`; }
function saveContext(sid, ev) {
  if (!sid || ev.turn_seq == null) return;
  try {
    localStorage.setItem(ctxKey(sid, ev.turn_seq),
      JSON.stringify({ tools: ev.tools || [], skills: ev.skills || [], directives: ev.directives || [] }));
  } catch (e) { /* quota / private mode — degrade to no-restore */ }
}
function loadContext(sid, turnSeq) {
  try { const raw = localStorage.getItem(ctxKey(sid, turnSeq)); return raw ? JSON.parse(raw) : null; }
  catch (e) { return null; }
}
function rid() { return "m" + Math.random().toString(36).slice(2, 10); }
function nowLabel() { const d = new Date(); return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); }

window.TurnBuilder = TurnBuilder;
window.handleEvent = handleEvent;
window.historyToMessages = historyToMessages;
