/* Cowork — HMG-Fu agent workspace: login → 3-pane (rail · transcript · canvas), live WS turns. */
/* max-width media hook — drives the mobile (single-pane + drawers) layout */
function useIsMobile() {
  const [mobile, setMobile] = React.useState(() => window.matchMedia("(max-width: 768px)").matches);
  React.useEffect(() => {
    const mq = window.matchMedia("(max-width: 768px)");
    const h = (e) => setMobile(e.matches);
    mq.addEventListener("change", h);
    return () => mq.removeEventListener("change", h);
  }, []);
  return mobile;
}

function CoworkApp() {
  const API = window.HMGFU;
  const isMobile = useIsMobile();
  const [authed, setAuthed] = React.useState(false);
  const [theme, setTheme] = React.useState("pa-cowork-dark");
  const [railOpen, setRailOpen] = React.useState(!isMobile);
  const [canvasOpen, setCanvasOpen] = React.useState(!isMobile);
  React.useEffect(() => { if (isMobile) { setRailOpen(false); setCanvasOpen(false); } }, [isMobile]);
  const [settingsOpen, setSettingsOpen] = React.useState(false);
  const [streaming, setStreaming] = React.useState(false);
  const toggleTheme = () => setTheme((t) => t.indexOf("dark") >= 0 ? "pa-cowork-light" : "pa-cowork-dark");

  const [sessions, setSessions] = React.useState([]);
  const [activeId, setActiveId] = React.useState(null);
  const activeIdRef = React.useRef(null);   // async-safe mirror (send/refresh race, Phase 31)
  React.useEffect(() => { activeIdRef.current = activeId; }, [activeId]);
  const [messages, setMessages] = React.useState([]);
  const [widgets, setWidgets] = React.useState([]);
  const [stats, setStats] = React.useState(null);
  const [live, setLive] = React.useState(null);
  const [activated, setActivated] = React.useState(null);   // last turn's recalled memory ids/items
  const [graded, setGraded] = React.useState(null);       // last turn's grade card (grader widget feed)
  const [extraGroups, setExtraGroups] = React.useState([]);   // empty groups pending first member
  const [modelLabel, setModelLabel] = React.useState("gemma4:12b");
  const [alarms, setAlarms] = React.useState([]);            // 77.6: reminders that fired while no turn was open (undelivered)
  const groups = [...new Set([...sessions.map((s) => s.group).filter(Boolean), ...extraGroups])];
  const newGroup = (name) => { if (name && !groups.includes(name)) setExtraGroups((g) => [...g, name]); };
  const assignGroup = async (id, group) => {
    try { await window.HMGFU.setGroup(id, group || ""); } catch (e) { console.error(e); }
    refreshSessions();
  };

  // --- load sessions after auth --------------------------------------------------
  const refreshSessions = React.useCallback(async () => {
    try {
      const { sessions } = await API.sessions();
      setSessions(sessions);
      if (sessions.length && !activeIdRef.current) selectSession(sessions[0].id);
    } catch (e) { console.error(e); }
  }, []);

  React.useEffect(() => {
    if (!authed) return;
    refreshSessions();
    API.providers().then((p) => setModelLabel(p.roles?.chat?.model || "gemma4:12b")).catch(() => {});
  }, [authed]);

  // 77.6: the WS lives per turn, so out-of-turn reminders reach the UI by POLL (20 s) — the next turn delivers them too
  React.useEffect(() => {
    if (!authed) return;
    const load = () => API.prospectiveNotifications().then((r) => setAlarms(r.undelivered || [])).catch(() => {});
    load(); const t = setInterval(load, 20000); return () => clearInterval(t);
  }, [authed]);
  const ackAlarms = async () => {
    const items = alarms; if (!items.length) return;
    setMessages((m) => [...m, { id: "alarm_" + Date.now(), kind: "prospective", mode: "fired",
      items: items.map((n) => ({ id: n.trigger_id, text: n.text, kind: n.kind, due: n.due })) }]);
    setAlarms([]);
    try { await API.ackProspective(items.map((n) => n.id)); } catch (e) { console.error(e); }
  };

  // --- session selection → load history + widgets --------------------------------
  const selectSession = async (id) => {
    setActiveId(id);
    try {
      const { history, widgets } = await API.history(id);
      setMessages(historyToMessages(history, id));
      setWidgets((widgets || []).map(fromServerWidget));
    } catch (e) { console.error(e); setMessages([]); setWidgets([]); }
  };

  const newChat = async () => {
    const { session } = await API.createSession();
    await refreshSessions();
    setActiveId(session.id);
    setMessages([]);
    setWidgets([]);
  };

  // --- widgets: agent (WS) + manual + backend --------------------------------------
  const addWidget = (type, title, extra) => {
    const id = (extra && extra.id) || "w_" + Math.random().toString(36).slice(2, 10);
    setWidgets((ws) => [...ws, { id, type, title, icon: iconFor(type), justAdded: true, ...extra }]);
    setTimeout(() => setWidgets((ws) => ws.map((w) => w.id === id ? { ...w, justAdded: false } : w)), 500);
    if (activeIdRef.current && !(extra && extra.generated))   // agent widgets persist via WS path
      API.upsertWidget(activeIdRef.current, { id, type, title }).catch(() => {});
  };
  const removeWidget = (id) => {
    setWidgets((ws) => ws.filter((w) => w.id !== id));          // instant UI
    if (activeId) API.deleteWidget(activeId, id).catch(() => {}); // persist so it stays gone
  };

  // --- send a turn over WS ---------------------------------------------------------
  const send = async (text) => {
    let sid = activeId;
    if (!sid) {   // create a session WITHOUT wiping the current canvas/messages
      const { session } = await API.createSession();
      sid = session.id;
      activeIdRef.current = sid;   // before any await — refreshSessions must not re-select
      setActiveId(sid);
      refreshSessions();
    }
    const turn = new TurnBuilder(setMessages);
    turn.pushUser(text);
    setStreaming(true);
    setLive(null);
    try {
      await API.chat(text, sid, (ev) => handleEvent(ev, turn, { addWidget, setWidgets, setStats, setLive, setActivated, setGraded, sid }));
    } catch (e) {
      turn.pushError(String(e.message || e));
    } finally {
      setStreaming(false);
      setLive(null);
      refreshSessions();
    }
  };

  const activeTitle = sessions.find((s) => s.id === activeId)?.title || "Cowork";

  return (
    <div className={theme} style={{ height: "100%", width: "100%" }}>
      {!authed ? (
        <CoworkLogin onAuth={() => setAuthed(true)} />
      ) : (
        <div style={{ position: "relative", display: "flex", height: "100%", width: "100%", background: "hsl(var(--background))", overflow: "hidden" }}>
          {/* mobile: rail/canvas become overlay drawers; desktop: normal 3-pane flex */}
          {!isMobile && (
            <CoworkRail sessions={sessions} groups={groups} activeId={activeId} onSelect={selectSession} onNew={newChat}
              onNewGroup={newGroup} onAssignGroup={assignGroup}
              onOpenSettings={() => setSettingsOpen(true)} theme={theme} onToggleTheme={toggleTheme}
              open={railOpen} onToggle={() => setRailOpen((o) => !o)} />
          )}
          <CoworkTranscript title={activeTitle} model={modelLabel} messages={messages} onSend={send} streaming={streaming}
            live={live} stats={stats} alarms={alarms} onAckAlarms={ackAlarms} railOpen={railOpen && !isMobile} onToggleRail={() => setRailOpen((o) => !o)}
            canvasOpen={canvasOpen && !isMobile} onToggleCanvas={() => setCanvasOpen((o) => !o)} />
          {!isMobile && (
            <CoworkCanvas widgets={widgets} onRemove={removeWidget} onAdd={(type, title) => addWidget(type, title)}
              activated={activated} graded={graded} open={canvasOpen} onToggle={() => setCanvasOpen((o) => !o)} />
          )}
          {isMobile && railOpen && (
            <div style={{ position: "absolute", inset: 0, zIndex: 70, display: "flex" }}>
              <CoworkRail sessions={sessions} groups={groups} activeId={activeId}
                onSelect={(id) => { selectSession(id); setRailOpen(false); }} onNew={() => { newChat(); setRailOpen(false); }}
                onNewGroup={newGroup} onAssignGroup={assignGroup}
                onOpenSettings={() => { setSettingsOpen(true); setRailOpen(false); }} theme={theme} onToggleTheme={toggleTheme}
                open onToggle={() => setRailOpen(false)} />
              <div style={{ flex: 1, background: "rgba(0,0,0,.55)" }} onClick={() => setRailOpen(false)} />
            </div>
          )}
          {isMobile && canvasOpen && (
            <div style={{ position: "absolute", inset: 0, zIndex: 70, display: "flex", justifyContent: "flex-end" }}>
              <div style={{ flex: 1, background: "rgba(0,0,0,.55)" }} onClick={() => setCanvasOpen(false)} />
              <CoworkCanvas widgets={widgets} onRemove={removeWidget} onAdd={(type, title) => addWidget(type, title)}
                activated={activated} graded={graded} open resizable={false} onToggle={() => setCanvasOpen(false)} />
            </div>
          )}
          <CoworkSettings open={settingsOpen} onClose={() => setSettingsOpen(false)} theme={theme} onToggleTheme={toggleTheme} />
        </div>
      )}
    </div>
  );
}

/* --- login: real token check against /api/health ------------------------------- */
function CoworkLogin({ onAuth }) {
  const { Input, Button } = window.PersonalAgentDesignSystem_94ad89;
  const { Icon } = window.PA;
  const [t, setT] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const [err, setErr] = React.useState("");
  const submit = async (e) => {
    e.preventDefault();
    setLoading(true); setErr("");
    window.HMGFU.setToken(t.trim());
    try { await window.HMGFU.health(); onAuth(); }
    catch (ex) { setErr("Could not reach the agent. Check the token / server."); }
    finally { setLoading(false); }
  };
  return (
    <div style={{ display: "flex", height: "100%", width: "100%", alignItems: "center", justifyContent: "center", background: "hsl(var(--background))",
      backgroundImage: "radial-gradient(120% 80% at 50% -10%, hsl(var(--primary) / 0.10), transparent 55%)" }}>
      <div style={{ width: 350, padding: "0 16px" }}>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 14, marginBottom: 26 }}>
          <div style={{ display: "flex", height: 56, width: 56, alignItems: "center", justifyContent: "center", borderRadius: 18, background: "hsl(var(--primary) / 0.14)", border: "1px solid hsl(var(--primary) / 0.25)" }}>
            <Icon name="bot" size={28} color="hsl(var(--primary))" />
          </div>
          <div style={{ textAlign: "center" }}>
            <h1 style={{ margin: 0, fontSize: 22, fontWeight: 700, color: "hsl(var(--foreground))", letterSpacing: "-0.02em" }}>Cowork</h1>
            <p style={{ margin: "6px 0 0", fontSize: 13, color: "hsl(var(--muted-foreground))" }}>HMG-Fu — the agent that remembers relationally.</p>
          </div>
        </div>
        <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <Input leftIcon={<Icon name="key-round" size={16} />} type="password" value={t} onChange={(e) => setT(e.target.value)} placeholder="Access token (blank = dev mode)" autoFocus />
          <Button type="submit" disabled={loading} rightIcon={!loading && <Icon name="arrow-right" size={16} />} style={{ width: "100%" }}>
            {loading ? "Connecting…" : "Enter workspace"}
          </Button>
        </form>
        {err && <p style={{ fontSize: 12, color: "hsl(var(--destructive))", textAlign: "center", marginTop: 12 }}>{err}</p>}
      </div>
    </div>
  );
}

function iconFor(type) {
  return { "memory-graph": "network", "memory-hex": "hexagon", "memory-trace": "footprints", layers: "layers", canon: "shield", dream: "moon", grader: "graduation-cap", plan: "list-todo", diff: "file-diff",
    table: "table", metric: "activity", weather: "cloud-sun", note: "sticky-note", timeline: "clock" }[type] || "square";
}
function fromServerWidget(w) {
  return { id: w.id, type: w.type, title: w.title, icon: iconFor(w.type), generated: w.generated, ...(w.props || {}) };
}
window.CoworkApp = CoworkApp;
