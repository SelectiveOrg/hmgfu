/* Cowork — right widget CANVAS: agent-generated + manual widgets; memory views fed by /api/graph/viz. */
const CANVAS_PANEL_MIN = 280;
const canvasPanelMaxWidth = () => Math.max(CANVAS_PANEL_MIN, Math.min(720, window.innerWidth - 520));
function CoworkCanvas({ widgets, onRemove, onAdd, open, onToggle, activated, graded, resizable = true }) {
  const { CanvasWidget, HmgGraph, PlanTracker, DiffView, IconButton } = window.PersonalAgentDesignSystem_94ad89;
  const { HexFieldBody } = window.MemoryWidgets || {};
  const { TraceBody, LayersBody, NowBody, CanonBody } = window.MemoryPanels || {};
  const { DreamBody, GraderBody } = window.DreamGraderWidgets || {};
  const { Icon } = window.PA;
  const bodyRef = React.useRef(null);
  const [menuOpen, setMenuOpen] = React.useState(false);
  const [layout, setLayout] = React.useState({});
  const [zmap, setZmap] = React.useState({});
  const [expandedId, setExpandedId] = React.useState(null);
  const [viz, setViz] = React.useState(null);
  const [panelWidth, setPanelWidth] = React.useState(() => Math.min(400, canvasPanelMaxWidth()));
  const zTop = React.useRef(1);

  const needsViz = widgets.some((w) => ["memory-hex", "memory-graph", "layers"].includes(w.type));
  const refreshViz = React.useCallback(() => {
    if (!needsViz) return;
    window.HMGFU.graphViz(220).then(setViz).catch(() => {});
  }, [needsViz]);
  React.useEffect(() => { refreshViz(); }, [needsViz]);
  // each turn's memory_used → refresh the field so new/reinforced hexes appear, then glow
  React.useEffect(() => { if (activated) refreshViz(); }, [activated]);
  // a dream run reshapes the graph (macros/wormholes) → refresh the memory views
  React.useEffect(() => {
    const h = () => refreshViz();
    window.addEventListener("hmg-graph-changed", h);
    return () => window.removeEventListener("hmg-graph-changed", h);
  }, [refreshViz]);

  const bodyW = () => (bodyRef.current ? bodyRef.current.clientWidth : 388);
  React.useEffect(() => {
    setLayout((prev) => {
      const next = { ...prev }; const bw = bodyW() - 24; let maxY = 12;
      Object.keys(next).forEach((id) => { if (widgets.find((w) => w.id === id)) maxY = Math.max(maxY, next[id].y + next[id].h + 12); });
      widgets.forEach((w) => { if (!next[w.id]) { next[w.id] = { x: 12, y: maxY, w: Math.max(200, bw), h: defaultH(w.type) }; maxY += next[w.id].h + 12; } });
      Object.keys(next).forEach((id) => { if (!widgets.find((w) => w.id === id)) delete next[id]; });
      return next;
    });
  }, [widgets]);

  React.useEffect(() => {
    if (!resizable) return;
    const maxW = Math.max(190, panelWidth - 25), contentRight = panelWidth - 13;
    setLayout((prev) => Object.fromEntries(Object.entries(prev).map(([id, l]) => {
      const w = Math.min(l.w, maxW); return [id, { ...l, w, x: Math.max(0, Math.min(l.x, contentRight - w)) }];
    })));
  }, [panelWidth, resizable]);
  React.useEffect(() => {
    if (!resizable) return;
    const clamp = () => setPanelWidth((w) => Math.max(CANVAS_PANEL_MIN, Math.min(w, canvasPanelMaxWidth())));
    window.addEventListener("resize", clamp); return () => window.removeEventListener("resize", clamp);
  }, [resizable]);

  const bringFront = (id) => setZmap((m) => ({ ...m, [id]: ++zTop.current }));
  // setPointerCapture keeps events flowing even when the pointer crosses an iframe/canvas
  // (the app + memory widgets) — without it drag/resize "stick" over child content.
  const startDrag = (id) => (e) => {
    if (expandedId) return; e.preventDefault(); bringFront(id);
    const l = layout[id]; if (!l) return;
    const handle = e.currentTarget; try { handle.setPointerCapture(e.pointerId); } catch {}
    const sx = e.clientX, sy = e.clientY, ox = l.x, oy = l.y, bw = bodyW();
    const move = (ev) => setLayout((p) => ({ ...p, [id]: { ...p[id], x: Math.max(0, Math.min(ox + (ev.clientX - sx), bw - l.w)), y: Math.max(0, oy + (ev.clientY - sy)) } }));
    const up = () => { handle.removeEventListener("pointermove", move); handle.removeEventListener("pointerup", up); };
    handle.addEventListener("pointermove", move); handle.addEventListener("pointerup", up);
  };
  const startResize = (id) => (e) => {
    if (expandedId) return; e.preventDefault(); e.stopPropagation(); bringFront(id);
    const l = layout[id]; if (!l) return;
    const handle = e.currentTarget; try { handle.setPointerCapture(e.pointerId); } catch {}
    const sx = e.clientX, sy = e.clientY, ow = l.w, oh = l.h, bw = bodyW();
    const move = (ev) => setLayout((p) => ({ ...p, [id]: { ...p[id], w: Math.max(190, Math.min(ow + (ev.clientX - sx), bw - l.x)), h: Math.max(96, oh + (ev.clientY - sy)) } }));
    const up = () => { handle.removeEventListener("pointermove", move); handle.removeEventListener("pointerup", up); };
    handle.addEventListener("pointermove", move); handle.addEventListener("pointerup", up);
  };
  const startPanelResize = (e) => {
    if (!resizable) return; e.preventDefault();
    const handle = e.currentTarget; try { handle.setPointerCapture(e.pointerId); } catch {}
    const sx = e.clientX, ow = panelWidth;
    const move = (ev) => {
      setPanelWidth(Math.max(CANVAS_PANEL_MIN, Math.min(ow + sx - ev.clientX, canvasPanelMaxWidth())));
    };
    const up = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); window.removeEventListener("pointercancel", up); };
    window.addEventListener("pointermove", move); window.addEventListener("pointerup", up); window.addEventListener("pointercancel", up);
  };
  const tidy = () => setLayout(() => { const bw = bodyW() - 24; let y = 12; const next = {}; widgets.forEach((w) => { next[w.id] = { x: 12, y, w: Math.max(200, bw), h: defaultH(w.type) }; y += next[w.id].h + 12; }); return next; });

  if (!open) {
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6, width: 48, borderLeft: "1px solid hsl(var(--border))", background: "hsl(var(--surface-2))", padding: "12px 4px", flexShrink: 0 }}>
        <IconButton title="Open canvas" onClick={onToggle}><Icon name="layout-grid" size={16} /></IconButton>
      </div>
    );
  }

  const ADDABLE = [
    { type: "now", title: "Now", icon: "sun" },
    { type: "memory-graph", title: "Memory · Graph", icon: "network" },
    { type: "memory-hex", title: "Memory · Hex field", icon: "hexagon" },
    { type: "memory-trace", title: "Memory · Trace", icon: "footprints" },
    { type: "layers", title: "Memory · Layers", icon: "layers" },
    { type: "canon", title: "Canon · Directives+Facts", icon: "shield" },
    { type: "dream", title: "Dream loop", icon: "moon" },
    { type: "grader", title: "Grader · Learning", icon: "graduation-cap" },
    { type: "timeline", title: "Memory · Timeline", icon: "clock" },
    { type: "metric", title: "Metric", icon: "activity" },
    { type: "note", title: "Note", icon: "sticky-note" },
  ];

  const body = (w, innerH) => {
    const gh = Math.max(120, Math.round((innerH - 12) / 24) * 24);
    switch (w.type) {
      case "memory-graph":
        return <div style={{ padding: 6, height: "100%" }}><HmgGraph height={gh} nodes={viz?.graph_nodes} edges={viz?.edges} showLabels="hover" /></div>;
      case "memory-hex":
        return <HexFieldBody viz={viz} activated={activated} height={innerH} />;
      case "memory-trace":
        return <TraceBody activated={activated} />;
      case "canon":
        return <CanonBody />;
      case "layers":
        return <LayersBody viz={viz} />;
      case "dream":
        return <DreamBody height={innerH} />;
      case "grader":
        return <GraderBody graded={graded} />;
      case "timeline":
        return <TimelineBody />;
      case "now":
        return <NowBody />;
      case "app":
        return <window.CoworkAppBody file={w.file} url={w.url} />;
      case "plan":
        return <PlanTracker compact title={w.title} steps={w.steps || []} style={{ border: "none", background: "transparent" }} />;
      case "diff":
        return <div style={{ padding: 8 }}><DiffView filename={w.filename || "file"} diff={w.diff || ""} /></div>;
      case "note":
        return <div style={{ padding: "12px 14px", fontSize: 13, color: "hsl(var(--foreground))", whiteSpace: "pre-wrap" }}>{w.text || ""}</div>;
      case "table":
        return (<div>{(w.rows || []).map((r, i) => (
          <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "6px 12px", borderTop: i ? "1px solid hsl(var(--border))" : "none", fontSize: 12, color: "hsl(var(--foreground))" }}>
            <span>{r[0]}</span><span style={{ fontFamily: "var(--font-mono)", color: "hsl(var(--muted-foreground))" }}>{r[1]}</span>
          </div>))}</div>);
      case "metric":
        return (
          <div style={{ padding: "14px 14px 16px" }}>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 30, fontWeight: 600, color: "hsl(var(--foreground))", lineHeight: 1 }}>{w.value ?? "—"}</div>
            <div style={{ fontSize: 11, color: "hsl(var(--muted-foreground))", marginTop: 4 }}>{w.caption || ""}</div>
            {w.spark && (<div style={{ display: "flex", gap: 3, marginTop: 12, alignItems: "flex-end", height: 34 }}>
              {w.spark.map((v, i) => <span key={i} style={{ flex: 1, height: (v / Math.max(...w.spark) * 100) + "%", background: "hsl(var(--primary) / " + (0.35 + i / 22) + ")", borderRadius: 2 }} />)}
            </div>)}
          </div>);
      case "weather":
        return (
          <div style={{ padding: "12px 14px", display: "flex", alignItems: "center", gap: 10 }}>
            <Icon name="cloud-sun" size={30} color="hsl(var(--warning))" />
            <div><div style={{ fontFamily: "var(--font-mono)", fontSize: 24, fontWeight: 600, color: "hsl(var(--foreground))" }}>{w.temp || "—"}</div>
            <div style={{ fontSize: 11, color: "hsl(var(--muted-foreground))" }}>{w.place || ""}</div></div>
          </div>);
      default: return <div style={{ padding: 14, fontSize: 12, color: "hsl(var(--muted-foreground))" }}>{w.type}</div>;
    }
  };

  const bodyH = bodyRef.current ? bodyRef.current.clientHeight : 500;
  return (
    <div data-canvas-panel style={{ display: "flex", flexDirection: "column", width: resizable ? panelWidth : "100vw", maxWidth: resizable ? "none" : 400, borderLeft: "1px solid hsl(var(--border))", background: "hsl(var(--background))", flexShrink: 0, minHeight: 0, position: "relative" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, borderBottom: "1px solid hsl(var(--border))", height: 52, padding: "0 12px", flexShrink: 0, position: "relative" }}>
        <Icon name="layout-grid" size={15} color="hsl(var(--primary))" />
        <span style={{ flex: 1, fontSize: 13, fontWeight: 600, color: "hsl(var(--foreground))" }}>Canvas</span>
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "hsl(var(--muted-foreground))" }}>{widgets.length}</span>
        <IconButton size="sm" title="Refresh memory views" onClick={refreshViz}><Icon name="refresh-cw" size={14} /></IconButton>
        <IconButton size="sm" title="Tidy layout" onClick={tidy}><Icon name="layout-dashboard" size={15} /></IconButton>
        <IconButton size="sm" active={menuOpen} title="Add widget" onClick={() => setMenuOpen((v) => !v)}><Icon name="plus" size={15} /></IconButton>
        <IconButton size="sm" title="Collapse" onClick={onToggle}><Icon name="panel-right-close" size={15} /></IconButton>
        {menuOpen && (
          <div style={{ position: "absolute", top: "100%", right: 8, zIndex: 40, marginTop: 4, minWidth: 172, borderRadius: "var(--radius-md)", border: "1px solid hsl(var(--border))", background: "hsl(var(--popover))", boxShadow: "var(--shadow-lg)", overflow: "hidden" }}>
            {ADDABLE.map((a) => (
              <button key={a.type} onClick={() => { onAdd(a.type, a.title); setMenuOpen(false); }}
                style={{ display: "flex", alignItems: "center", gap: 8, width: "100%", padding: "8px 12px", border: "none", background: "transparent", cursor: "pointer", color: "hsl(var(--foreground))", fontSize: 12, fontFamily: "var(--font-sans)", textAlign: "left" }}
                onMouseEnter={(e) => e.currentTarget.style.background = "hsl(var(--surface-hover))"} onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}>
                <Icon name={a.icon} size={14} color="hsl(var(--muted-foreground))" />{a.title}
              </button>
            ))}
          </div>
        )}
      </div>

      <div ref={bodyRef} style={{ flex: 1, minHeight: 0, overflow: expandedId ? "hidden" : "auto", position: "relative" }}>
        {widgets.length === 0 && (
          <div style={{ textAlign: "center", color: "hsl(var(--muted-foreground))", fontSize: 12, padding: "48px 16px" }}>
            Empty canvas. Add a memory view, or ask Cowork to build a widget.
          </div>
        )}
        {widgets.map((w) => {
          const l = layout[w.id]; if (!l) return null;
          const isExp = expandedId === w.id;
          if (expandedId && !isExp) return null;
          const wrap = isExp ? { position: "absolute", left: 12, top: 12, right: 12, bottom: 12, zIndex: 50 }
            : { position: "absolute", left: l.x, top: l.y, width: l.w, height: l.h, zIndex: zmap[w.id] || 1 };
          const innerH = (isExp ? bodyH - 24 : l.h) - 38 - (w.footer ? 28 : 0);
          return (
            <div key={w.id} className={w.justAdded ? "pa-widget-in" : ""} style={wrap}>
              <CanvasWidget fill title={w.title} generated={w.generated} icon={<Icon name={w.icon || iconFor(w.type)} size={14} />}
                footer={w.generated ? "✦ agent" : w.footer} expanded={isExp}
                onExpand={() => setExpandedId((x) => x === w.id ? null : w.id)}
                onClose={() => onRemove(w.id)} onRefresh={refreshViz}
                dragHandleProps={{ onPointerDown: startDrag(w.id) }} resizeHandleProps={{ onPointerDown: startResize(w.id) }}>
                {body(w, Math.max(80, innerH))}
              </CanvasWidget>
            </div>
          );
        })}
      </div>
      {resizable && <div role="separator" aria-label="Resize canvas panel" aria-orientation="vertical" data-canvas-resizer
        aria-valuemin={CANVAS_PANEL_MIN} aria-valuemax={canvasPanelMaxWidth()} aria-valuenow={panelWidth} tabIndex={0}
        onKeyDown={(e) => { const d = e.key === "ArrowLeft" ? 24 : e.key === "ArrowRight" ? -24 : 0; if (d) { e.preventDefault(); setPanelWidth((w) => Math.max(CANVAS_PANEL_MIN, Math.min(w + d, canvasPanelMaxWidth()))); } }}
        onPointerDown={startPanelResize} style={{ position: "absolute", left: -4, top: 0, bottom: 0, width: 8, zIndex: 60, cursor: "col-resize", touchAction: "none", outlineOffset: -2 }} />}
    </div>
  );
}


function TimelineBody() {
  const { Icon } = window.PA;
  const [items, setItems] = React.useState(null);
  React.useEffect(() => { window.HMGFU.memoryTimeline(30).then((d) => setItems(d.timeline || [])).catch(() => setItems([])); }, []);
  if (items === null) return <div style={{ padding: 14, fontSize: 12, color: "hsl(var(--muted-foreground))" }}>loading…</div>;
  return (
    <div style={{ padding: "8px 10px", overflowY: "auto", height: "100%" }}>
      {items.map((it, i) => (
        <div key={i} style={{ display: "flex", gap: 8, padding: "5px 0", borderTop: i ? "1px solid hsl(var(--border))" : "none" }}>
          <span title={it.nodeClass || it.type} style={{ display: "inline-block", width: 8, height: 8, borderRadius: 2, marginTop: 4, flexShrink: 0, background: (window.HMG_CLASS_COLORS || {})[it.nodeClass] || "#8b949e" }} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 12, color: "hsl(var(--foreground))" }}>{it.title || it.summary}</div>
            <div style={{ fontSize: 10, color: "hsl(var(--muted-foreground))" }}>{(it.timestamp || "").slice(0, 16).replace("T", " ")} · {(window.HMG_CLASS_LABELS || {})[it.nodeClass] || it.type}{it.category ? " · " + it.category : ""}</div>
          </div>
        </div>
      ))}
      {items.length === 0 && <div style={{ fontSize: 12, color: "hsl(var(--muted-foreground))" }}>No memories yet.</div>}
    </div>
  );
}

function defaultH(type) {  // canon panel
  return { "memory-graph": 260, "memory-hex": 300, "memory-trace": 240, layers: 210, dream: 320, grader: 260, timeline: 240, now: 250, app: 360, plan: 168, diff: 208, table: 168, metric: 150, weather: 120, note: 140 }[type] || 180;
}
function iconFor(type) {
  return { "memory-graph": "network", "memory-hex": "hexagon", "memory-trace": "footprints", layers: "layers", canon: "shield", dream: "moon", grader: "graduation-cap", plan: "list-todo", diff: "file-diff", table: "table", metric: "activity", weather: "cloud-sun", note: "sticky-note", timeline: "clock", now: "sun", app: "app-window" }[type] || "square";
}
window.CoworkCanvas = CoworkCanvas;
