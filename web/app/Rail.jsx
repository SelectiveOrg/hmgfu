/* Cowork — left sessions rail with GROUP folders (design-kit feature), backed by the sessions API. */
function CoworkSessionItem({ s, active, groups, onSelect, onAssign }) {
  const { SessionRow } = window.PersonalAgentDesignSystem_94ad89;
  const { Icon } = window.PA;
  const [menu, setMenu] = React.useState(false);
  const ref = React.useRef(null);
  React.useEffect(() => {
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) setMenu(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);
  const item = (on) => ({ display: "flex", alignItems: "center", gap: 7, width: "100%", padding: "6px 8px", border: "none",
    background: on ? "hsl(var(--primary) / 0.1)" : "transparent", color: on ? "hsl(var(--primary))" : "hsl(var(--foreground))",
    fontSize: 12, fontFamily: "var(--font-sans)", cursor: "pointer", borderRadius: 6, textAlign: "left" });
  return (
    <div ref={ref} style={{ position: "relative" }} onContextMenu={(e) => { e.preventDefault(); setMenu(true); }}>
      <SessionRow active={active} title={s.title || "Untitled"} meta={`${s.messages} msgs · ${relTime(s.updated_at)}`}
        onClick={() => onSelect(s.id)} />
      {menu && (
        <div style={{ position: "absolute", right: 6, top: 26, zIndex: 60, minWidth: 158, borderRadius: "var(--radius-md)", border: "1px solid hsl(var(--border))", background: "hsl(var(--popover))", boxShadow: "var(--shadow-lg)", overflow: "hidden", padding: 4 }}>
          <div style={{ fontSize: 9, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "hsl(var(--muted-foreground))", padding: "3px 8px" }}>Move to group</div>
          {groups.map((g) => (
            <button key={g} onClick={() => { onAssign(s.id, g); setMenu(false); }} style={item(s.group === g)}
              onMouseEnter={(e) => { if (s.group !== g) e.currentTarget.style.background = "hsl(var(--surface-hover))"; }}
              onMouseLeave={(e) => { if (s.group !== g) e.currentTarget.style.background = "transparent"; }}>
              <Icon name="folder" size={12} /><span style={{ flex: 1 }}>{g}</span>{s.group === g && <Icon name="check" size={12} />}
            </button>
          ))}
          {s.group && (
            <button onClick={() => { onAssign(s.id, ""); setMenu(false); }} style={item(false)}
              onMouseEnter={(e) => e.currentTarget.style.background = "hsl(var(--surface-hover))"}
              onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}>
              <Icon name="folder-minus" size={12} /><span style={{ flex: 1 }}>Remove from group</span>
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function CoworkRail({ sessions, groups = [], activeId, onSelect, onNew, onNewGroup, onAssignGroup, onOpenSettings, theme, onToggleTheme, open, onToggle }) {
  const { IconButton, Input, Button } = window.PersonalAgentDesignSystem_94ad89;
  const { Icon } = window.PA;
  const [q, setQ] = React.useState("");
  const [collapsed, setCollapsed] = React.useState({});
  const [creating, setCreating] = React.useState(false);
  const [newName, setNewName] = React.useState("");
  const isDark = theme.indexOf("dark") >= 0;
  const toggleGroup = (g) => setCollapsed((c) => ({ ...c, [g]: !c[g] }));

  if (!open) {
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8, width: 52, borderRight: "1px solid hsl(var(--border))", background: "hsl(var(--sidebar-background))", padding: "12px 0", flexShrink: 0 }}>
        <div style={{ height: 30, width: 30, display: "flex", alignItems: "center", justifyContent: "center", borderRadius: "var(--radius-md)", background: "hsl(var(--primary) / 0.14)", marginBottom: 4 }}>
          <Icon name="bot" size={17} color="hsl(var(--primary))" />
        </div>
        <IconButton title="Open" onClick={onToggle}><Icon name="chevron-right" /></IconButton>
        <IconButton title="New chat" onClick={onNew}><Icon name="plus" /></IconButton>
        <div style={{ flex: 1 }} />
        <IconButton title={isDark ? "Light" : "Dark"} onClick={onToggleTheme}><Icon name={isDark ? "sun" : "moon"} size={16} /></IconButton>
        <IconButton title="Settings" onClick={onOpenSettings}><Icon name="settings" size={16} /></IconButton>
      </div>
    );
  }

  const match = (s) => (s.title || "").toLowerCase().includes(q.toLowerCase());
  const ungrouped = sessions.filter((s) => !s.group && match(s));
  const commitGroup = () => { if (newName.trim()) onNewGroup(newName.trim()); setNewName(""); setCreating(false); };
  const label = { fontSize: 10, fontWeight: 600, letterSpacing: "0.05em", textTransform: "uppercase", color: "hsl(var(--muted-foreground))" };

  return (
    <div style={{ display: "flex", flexDirection: "column", width: 248, borderRight: "1px solid hsl(var(--border))", background: "hsl(var(--sidebar-background))", flexShrink: 0, overflow: "hidden" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, height: 52, padding: "0 12px", borderBottom: "1px solid hsl(var(--border))", flexShrink: 0 }}>
        <div style={{ height: 28, width: 28, display: "flex", alignItems: "center", justifyContent: "center", borderRadius: "var(--radius-md)", background: "hsl(var(--primary) / 0.14)" }}>
          <Icon name="bot" size={16} color="hsl(var(--primary))" />
        </div>
        <span style={{ flex: 1, fontSize: 14, fontWeight: 700, color: "hsl(var(--foreground))", letterSpacing: "-0.01em" }}>Cowork</span>
        <IconButton size="sm" title="Collapse" onClick={onToggle}><Icon name="chevron-left" /></IconButton>
      </div>

      <div style={{ padding: "10px 10px 8px" }}>
        <Button variant="secondary" onClick={onNew} leftIcon={<Icon name="plus" size={15} />}
          style={{ width: "100%", height: 34, fontSize: 13, justifyContent: "flex-start", gap: 8 }}>New chat</Button>
      </div>
      <div style={{ padding: "0 10px 8px" }}>
        <Input surface="flush" leftIcon={<Icon name="search" size={14} />} value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="Search" style={{ height: 32, fontSize: 12, paddingLeft: 32 }} />
      </div>

      <div style={{ flex: 1, overflowY: "auto", padding: "0 6px 6px" }}>
        <div style={{ display: "flex", alignItems: "center", padding: "4px 6px 4px" }}>
          <span style={{ ...label, flex: 1 }}>Groups</span>
          <button onClick={() => setCreating((v) => !v)} title="New group"
            style={{ display: "inline-flex", alignItems: "center", gap: 3, border: "none", background: "transparent", color: "hsl(var(--muted-foreground))", cursor: "pointer", fontSize: 10, fontWeight: 600 }}>
            <Icon name="folder-plus" size={12} /> New
          </button>
        </div>
        {creating && (
          <div style={{ padding: "0 6px 6px" }}>
            <input autoFocus value={newName} onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") commitGroup(); if (e.key === "Escape") { setCreating(false); setNewName(""); } }}
              onBlur={commitGroup} placeholder="Group name…"
              style={{ width: "100%", height: 28, padding: "0 10px", fontFamily: "var(--font-sans)", fontSize: 12, color: "hsl(var(--foreground))", background: "hsl(var(--background))", border: "1px solid hsl(var(--primary))", borderRadius: "var(--radius-sm)", outline: "none" }} />
          </div>
        )}
        {groups.map((g) => {
          const items = sessions.filter((s) => s.group === g && match(s));
          const col = collapsed[g];
          return (
            <div key={g} style={{ marginBottom: 2 }}>
              <button onClick={() => toggleGroup(g)}
                style={{ display: "flex", alignItems: "center", gap: 6, width: "100%", padding: "5px 8px", border: "none", background: "transparent", cursor: "pointer", ...label }}>
                <Icon name="chevron-down" size={11} style={{ transform: col ? "rotate(-90deg)" : "none", transition: "transform .15s" }} />
                <Icon name="folder" size={12} color="hsl(var(--primary))" />
                <span style={{ flex: 1, textAlign: "left" }}>{g}</span>
                <span style={{ opacity: .7 }}>{items.length}</span>
              </button>
              {!col && items.map((s) => (
                <CoworkSessionItem key={s.id} s={s} active={s.id === activeId} groups={groups} onSelect={onSelect} onAssign={onAssignGroup} />
              ))}
              {!col && items.length === 0 && (
                <div style={{ fontSize: 11, color: "hsl(var(--muted-foreground))", padding: "2px 8px 4px 26px", fontStyle: "italic" }}>empty · right-click a chat to add</div>
              )}
            </div>
          );
        })}

        <div style={{ ...label, padding: "8px 8px 4px" }}>Recent</div>
        {ungrouped.map((s) => (
          <CoworkSessionItem key={s.id} s={s} active={s.id === activeId} groups={groups} onSelect={onSelect} onAssign={onAssignGroup} />
        ))}
        {ungrouped.length === 0 && <div style={{ fontSize: 11, color: "hsl(var(--muted-foreground))", padding: "2px 8px" }}>—</div>}
        <div style={{ fontSize: 10, color: "hsl(var(--muted-foreground))", padding: "8px 8px 2px", opacity: .7 }}>Right-click a chat to move it to a group.</div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 4, borderTop: "1px solid hsl(var(--border))", padding: "8px 10px" }}>
        <div style={{ height: 26, width: 26, borderRadius: 999, background: "hsl(var(--surface-3))", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 600, color: "hsl(var(--foreground))" }}>H</div>
        <span style={{ flex: 1, fontSize: 12, color: "hsl(var(--foreground))" }}>HMG-Fu</span>
        <IconButton size="sm" title={isDark ? "Light mode" : "Dark mode"} onClick={onToggleTheme}><Icon name={isDark ? "sun" : "moon"} size={15} /></IconButton>
        <IconButton size="sm" title="Settings" onClick={onOpenSettings}><Icon name="settings" size={15} /></IconButton>
      </div>
    </div>
  );
}

function relTime(iso) {
  if (!iso) return "";
  const d = new Date(iso); const s = (Date.now() - d.getTime()) / 1000;
  if (s < 60) return "now"; if (s < 3600) return Math.floor(s / 60) + "m ago";
  if (s < 86400) return Math.floor(s / 3600) + "h ago"; return Math.floor(s / 86400) + "d ago";
}
window.CoworkRail = CoworkRail;
