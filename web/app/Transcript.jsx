/* Cowork — center transcript: user/thinking/tool/memory/assistant/grade cards + composer. */
function CoworkTranscript({ title, model, messages, onSend, streaming, live, stats, canvasOpen, onToggleCanvas, railOpen, onToggleRail, alarms, onAckAlarms }) {
  const { MessageBubble, PlanTracker, Pill, IconButton, Badge } = window.PersonalAgentDesignSystem_94ad89;
  const { VerifyPill, GradePill, TimingPill } = window;   // cards.jsx
  const ThinkingCard = window.ThinkingCard, ToolGroupCard = window.ToolGroupCard;
  const { Icon } = window.PA;
  const [text, setText] = React.useState("");
  const scrollRef = React.useRef(null);
  const taRef = React.useRef(null);

  // Elapsed ticks CLIENT-SIDE while streaming — the server's live.elapsed_s only refreshes once
  // per loop iteration, so it appeared frozen (e.g. "33.3s") during a slow model call. This keeps
  // the timer honest even when the backend is between/inside a long step.
  const [elapsed, setElapsed] = React.useState(0);
  const streamStartRef = React.useRef(null);
  React.useEffect(() => {
    if (!streaming) { streamStartRef.current = null; setElapsed(0); return; }
    if (streamStartRef.current == null) streamStartRef.current = Date.now();
    const id = setInterval(() => setElapsed((Date.now() - streamStartRef.current) / 1000), 200);
    return () => clearInterval(id);
  }, [streaming]);

  React.useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, streaming]);

  // auto-grow the composer with its content (was rows=1 fixed → long/multiline text got clipped)
  React.useEffect(() => {
    const el = taRef.current; if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  }, [text]);

  const send = () => { if (!text.trim()) return; onSend(text.trim()); setText(""); };
  const onKey = (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } };

  const renderMsg = (m) => {
    switch (m.kind) {
      case "user":
      case "assistant":
        return <MessageBubble key={m.id} role={m.kind} timestamp={m.time}>{m.text}</MessageBubble>;
      case "thinking":
        return (
          <div key={m.id} style={{ display: "flex", padding: "2px 16px" }}>
            <ThinkingCard text={m.text} expandable={m.expandable} />
          </div>
        );
      case "memory":
        if (!m.count) return null;
        return <div key={m.id} style={{ padding: "2px 16px" }}><MemoryPill count={m.count} items={m.items} /></div>;
      case "context":
        if (!(m.tools?.length || m.skills?.length || m.directives?.length)) return null;
        return <div key={m.id} style={{ padding: "2px 16px" }}><ContextPill tools={m.tools} skills={m.skills} directives={m.directives} /></div>;
      case "toolgroup":
        return <div key={m.id} style={{ padding: "3px 16px" }}><ToolGroupCard entries={m.entries} /></div>;
      case "plan":
        return (
          <div key={m.id} style={{ padding: "5px 16px" }}>
            <PlanTracker title={window.planTitle(m.plan)} steps={(m.plan.steps || []).map((s) => ({
              text: (s.note ? `${s.text} — ${s.note}` : s.text) + (s.evidence && s.evidence.length ? " ✓ verified" : ""),
              status: s.status,
            }))} />
          </div>
        );
      case "grade":
        return <div key={m.id} style={{ padding: "2px 16px" }}><GradePill grade={m.grade} /></div>;
      case "saydo":
      case "grounding":
        return <VerifyPill key={m.id} kind={m.kind} report={m.report || {}} />;   // 69.6 (cards.jsx)
      case "timings":
        return <TimingPill key={m.id} timings={m.timings || {}} />;              // 73.0 (cards.jsx)
      case "runbooks":
        return <RunbookPill key={m.id} items={m.items || []} />;                  // 75.1 (cards.jsx)
      case "prospective":
        return <ProspectivePill key={m.id} mode={m.mode} items={m.items || []} />;   // 75.2 (cards.jsx)
      case "error":
        return (
          <div key={m.id} style={{ padding: "3px 16px" }}>
            <Pill icon={<Icon name="alert-triangle" size={12} color="hsl(var(--destructive))" />}>{m.text}</Pill>
          </div>
        );
      default: return null;
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, minWidth: 0, minHeight: 0, background: "hsl(var(--background))" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, borderBottom: "1px solid hsl(var(--border))", height: 52, padding: "0 14px", flexShrink: 0 }}>
        {!railOpen && <IconButton title="Sessions" onClick={onToggleRail}><Icon name="panel-left-open" /></IconButton>}
        <span style={{ fontSize: 14, fontWeight: 600, color: "hsl(var(--foreground))", flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{title}</span>
        {(alarms || []).length > 0 && (   /* 77.6: reminders that came due while no conversation was open — click to show + acknowledge */
          <button onClick={onAckAlarms} title={(alarms || []).map((n) => n.text).join(" · ")}
            style={{ border: "none", background: "transparent", cursor: "pointer", padding: 0 }}>
            <Pill icon={<Icon name="bell" size={12} color="hsl(var(--warning))" />}>{`${alarms.length} reminder${alarms.length > 1 ? "s" : ""} due`}</Pill>
          </button>
        )}
        <Badge tone="neutral"><span style={{ fontFamily: "var(--font-mono)" }}>{model}</span></Badge>
        {!canvasOpen && <IconButton title="Canvas" onClick={onToggleCanvas}><Icon name="layout-grid" size={16} /></IconButton>}
      </div>

      <div ref={scrollRef} style={{ flex: 1, minHeight: 0, overflowY: "auto", padding: "16px 0" }}>
        <div style={{ maxWidth: 760, margin: "0 auto" }}>
          {messages.length === 0 && (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 10, color: "hsl(var(--muted-foreground))", padding: "72px 16px" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 44, width: 44, borderRadius: 999, background: "hsl(var(--memory) / 0.1)", border: "1px solid hsl(var(--memory) / 0.25)" }}>
                <Icon name="brain-circuit" size={20} color="hsl(var(--memory))" />
              </div>
              <div style={{ fontSize: 14, fontWeight: 600, color: "hsl(var(--foreground))" }}>Cowork remembers across sessions</div>
              <div style={{ fontSize: 12.5, textAlign: "center", maxWidth: 340, lineHeight: 1.5 }}>Ask it to recall something, build a widget, or run a command — every turn is scored and learned from.</div>
            </div>
          )}
          {messages.map(renderMsg)}
          {streaming && (
            <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 16px", fontSize: 13, color: "hsl(var(--muted-foreground))", fontFamily: "var(--font-mono)" }}>
              <span style={{ height: 7, width: 7, borderRadius: 999, background: "hsl(var(--primary))", animation: "pa-pulse-glow 1.2s ease-in-out infinite" }} />
              {live && live.iteration != null
                ? `working · step ${live.iteration} · ${live.tools_used} tools · ${elapsed.toFixed(1)}s`
                : (live && live.status) ? live.status : `working · ${elapsed.toFixed(1)}s`}
              <span className="pa-caret" style={{ color: "hsl(var(--primary))" }}>▋</span>
            </div>
          )}
        </div>
      </div>

      {/* 95.81: add the phone's own bottom inset, so the Send button is not under the home indicator */}
      <div style={{ padding: "0 14px calc(12px + env(safe-area-inset-bottom, 0px))" }}>
        <div style={{ maxWidth: 760, margin: "0 auto" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "4px 4px 6px", fontFamily: "var(--font-mono)", fontSize: 10.5, color: "hsl(var(--muted-foreground))" }}>
            <WorkspaceChip />
            <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}><Icon name="database" size={11} /> {stats ? stats.points + " mem" : "hmg-fu"}</span>
            <span>{stats ? stats.edges + " edges" : ""}</span>
            <span style={{ marginLeft: "auto", display: "inline-flex", alignItems: "center", gap: 4 }}>
              <Icon name="circle" size={8} color={streaming ? "hsl(var(--warning))" : "hsl(var(--status-done))"} /> {streaming ? "working" : "ready"}
            </span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", borderRadius: "var(--radius-xl)", border: "1px solid hsl(var(--border))", background: "hsl(var(--surface-2))" }}>
            <textarea ref={taRef} value={text} onChange={(e) => setText(e.target.value)} onKeyDown={onKey} rows={1}
              placeholder="Ask Cowork to build, recall, or run something…"
              style={{ width: "100%", resize: "none", background: "transparent", border: "none", outline: "none",
                padding: "12px 14px 4px", fontFamily: "var(--font-sans)", fontSize: 14, lineHeight: 1.45,
                color: "hsl(var(--foreground))", maxHeight: 200, overflowY: "auto" }} />
            <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", padding: "0 8px 8px" }}>
              <button onClick={send} disabled={!text.trim() || streaming} title="Send"
                style={{ display: "inline-flex", alignItems: "center", gap: 6, height: 30, padding: "0 12px", borderRadius: "var(--radius-md)", border: "none", cursor: text.trim() && !streaming ? "pointer" : "not-allowed",
                  background: text.trim() && !streaming ? "hsl(var(--primary))" : "hsl(var(--surface-3))", color: text.trim() && !streaming ? "hsl(var(--primary-foreground))" : "hsl(var(--muted-foreground))", fontFamily: "var(--font-sans)", fontSize: 12, fontWeight: 600 }}>
                Send <Icon name="corner-down-left" size={13} />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* Working-folder chip: shows folder + git branch; click → pick a project as the
   agent's working directory (bash/read/write follow it). */
function WorkspaceChip() {
  const { Icon } = window.PA;
  const [ws, setWs] = React.useState(null);
  const [open, setOpen] = React.useState(false);
  const [projects, setProjects] = React.useState(null);
  const ref = React.useRef(null);

  const load = () => window.HMGFU.systemStatus().then((d) => setWs(d.workspace)).catch(() => {});
  React.useEffect(() => { load(); }, []);   // wrapped: load returns a Promise, not a cleanup
  React.useEffect(() => {
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  const openPicker = async () => {
    setOpen((o) => !o);
    if (!projects) {
      try { setProjects((await window.HMGFU.projects()).projects); } catch { setProjects([]); }
    }
  };
  const pick = async (path) => {
    await window.HMGFU.putSettings({ workspace_dir: path || "" });
    setOpen(false);
    load();
  };

  return (
    <span ref={ref} style={{ position: "relative", display: "inline-flex" }}>
      <button onClick={openPicker} title="Select working folder"
        style={{ display: "inline-flex", alignItems: "center", gap: 4, border: "none", background: "transparent",
          color: "hsl(var(--muted-foreground))", cursor: "pointer", fontFamily: "var(--font-mono)", fontSize: 10.5, padding: 0 }}>
        <Icon name="folder" size={11} /> {ws ? ws.name : "workspace"}
        {ws && ws.git_branch && <span style={{ display: "inline-flex", alignItems: "center", gap: 3, marginLeft: 4 }}>
          <Icon name="git-branch" size={10} /> {ws.git_branch}</span>}
        <Icon name="chevron-down" size={10} />
      </button>
      {open && (
        <div style={{ position: "absolute", bottom: "100%", left: 0, zIndex: 70, marginBottom: 6, minWidth: 240, maxHeight: 260, overflowY: "auto",
          borderRadius: "var(--radius-md)", border: "1px solid hsl(var(--border))", background: "hsl(var(--popover))", boxShadow: "var(--shadow-lg)", padding: 4 }}>
          <form onSubmit={(e) => { e.preventDefault(); const v = e.target.elements.p.value.trim(); if (v) pick(v); }}
            style={{ display: "flex", gap: 4, padding: "4px 4px 6px" }}>
            <input name="p" placeholder="paste any folder path…" defaultValue={ws && ws.path || ""}
              style={{ flex: 1, minWidth: 0, background: "hsl(var(--surface-2))", border: "1px solid hsl(var(--border))",
                borderRadius: 5, padding: "5px 7px", fontSize: 11, color: "hsl(var(--foreground))", fontFamily: "var(--font-mono)" }} />
            <button type="submit" style={{ border: "none", borderRadius: 5, padding: "0 9px", cursor: "pointer",
              background: "hsl(var(--primary))", color: "hsl(var(--primary-foreground))", fontSize: 11 }}>Use</button>
          </form>
          <button onClick={() => pick("")} style={pickerItem()}>
            <Icon name="box" size={12} /> default (hmg-fu/workspace)
          </button>
          {(projects || []).map((p) => (
            <button key={p.path} onClick={() => pick(p.path)} style={pickerItem()}
              onMouseEnter={(e) => e.currentTarget.style.background = "hsl(var(--surface-hover))"}
              onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}>
              <Icon name={p.kinds.includes("git") ? "git-branch" : "folder"} size={12} />
              <span style={{ flex: 1, textAlign: "left" }}>{p.name}</span>
              {p.branch && <span style={{ fontSize: 9, opacity: 0.7 }}>{p.branch}</span>}
            </button>
          ))}
          {projects === null && <div style={{ padding: 8, fontSize: 11 }}>scanning…</div>}
          <div style={{ padding: "6px 8px 2px", fontSize: 9.5, color: "hsl(var(--muted-foreground))", borderTop: "1px solid hsl(var(--border))", marginTop: 4 }}>
            <Icon name="shield-check" size={10} /> Cowork gets full read · write · run access inside the selected folder.
          </div>
        </div>
      )}
    </span>
  );
}
function pickerItem() {
  return { display: "flex", alignItems: "center", gap: 7, width: "100%", padding: "6px 8px", border: "none",
    background: "transparent", color: "hsl(var(--foreground))", fontSize: 11.5, fontFamily: "var(--font-mono)",
    cursor: "pointer", borderRadius: 6 };
}

/* "Recalled N memories" pill — expands to show items + scores (PA3 memory_used). */
function MemoryPill({ count, items }) {
  const { Icon } = window.PA;
  const [open, setOpen] = React.useState(false);
  return (
    <div style={{ display: "inline-flex", flexDirection: "column", maxWidth: "100%" }}>
      <button onClick={() => setOpen((o) => !o)} style={{ display: "inline-flex", alignItems: "center", gap: 6, height: 24, padding: "0 10px", border: "1px solid hsl(var(--memory) / 0.4)", borderRadius: 999, background: "hsl(var(--memory) / 0.08)", color: "hsl(var(--memory))", fontSize: 12, cursor: "pointer", fontFamily: "var(--font-mono)" }}>
        <Icon name="brain-circuit" size={12} /> recalled {count} {count === 1 ? "memory" : "memories"}
        <Icon name={open ? "chevron-up" : "chevron-down"} size={12} />
      </button>
      {open && (
        <div style={{ marginTop: 6, display: "flex", flexDirection: "column", gap: 4, padding: "8px 10px", border: "1px solid hsl(var(--border))", borderRadius: "var(--radius-md)", background: "hsl(var(--surface-2))" }}>
          {(items || []).map((it, i) => (
            <div key={i} style={{ display: "flex", gap: 8, fontSize: 12, color: "hsl(var(--foreground))" }}>
              <span style={{ fontFamily: "var(--font-mono)", color: "hsl(var(--memory))", minWidth: 34 }}>{(it.score ?? 0).toFixed(2)}</span>
              <span style={{ flex: 1 }}>{it.text}</span>
              <span style={{ fontSize: 10, color: "hsl(var(--muted-foreground))" }}>{it.kind}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* "Recalled N tools · M skills · K directives" pill — the non-memory context this turn
   pulled in (HMG-ranked tools/skills offered to the model + active mandatory directives). */
function ContextPill({ tools, skills, directives }) {
  const { Icon } = window.PA;
  const [open, setOpen] = React.useState(false);
  const t = tools || [], s = skills || [], d = directives || [];
  const parts = [];
  if (t.length) parts.push(`${t.length} tool${t.length === 1 ? "" : "s"}`);
  if (s.length) parts.push(`${s.length} skill${s.length === 1 ? "" : "s"}`);
  if (d.length) parts.push(`${d.length} directive${d.length === 1 ? "" : "s"}`);
  if (!parts.length) return null;
  // rows mirror MemoryPill exactly: score (left, --memory) | label (flex) | type (right, muted)
  const nameOf = (x) => (typeof x === "string" ? x : x.name);      // tolerate old string payloads
  const scoreOf = (x) => (x && typeof x === "object" && typeof x.score === "number" ? x.score : null);
  const row = (key, score, label, type) => (
    <div key={key} style={{ display: "flex", gap: 8, fontSize: 12, color: "hsl(var(--foreground))" }}>
      <span style={{ fontFamily: "var(--font-mono)", color: "hsl(var(--memory))", minWidth: 34 }}>{score != null ? score.toFixed(2) : "—"}</span>
      <span style={{ flex: 1, wordBreak: "break-word" }}>{label}</span>
      <span style={{ fontSize: 10, color: "hsl(var(--muted-foreground))" }}>{type}</span>
    </div>
  );
  return (
    <div style={{ display: "inline-flex", flexDirection: "column", maxWidth: "100%" }}>
      <button onClick={() => setOpen((o) => !o)} style={{ display: "inline-flex", alignItems: "center", gap: 6, height: 24, padding: "0 10px", border: "1px solid hsl(var(--memory) / 0.4)", borderRadius: 999, background: "hsl(var(--memory) / 0.08)", color: "hsl(var(--memory))", fontSize: 12, cursor: "pointer", fontFamily: "var(--font-mono)" }}>
        <Icon name="hammer" size={12} /> recalled {parts.join(" · ")}
        <Icon name={open ? "chevron-up" : "chevron-down"} size={12} />
      </button>
      {open && (
        <div style={{ marginTop: 6, display: "flex", flexDirection: "column", gap: 4, padding: "8px 10px", border: "1px solid hsl(var(--border))", borderRadius: "var(--radius-md)", background: "hsl(var(--surface-2))" }}>
          {s.map((x, i) => row("s" + i, scoreOf(x), nameOf(x), "skill"))}
          {t.map((x, i) => row("t" + i, scoreOf(x), nameOf(x), "tool"))}
          {d.map((x, i) => row("d" + i, null, `${x.kind}: ${x.value}`, "always-on"))}
        </div>
      )}
    </div>
  );
}

window.CoworkTranscript = CoworkTranscript;
