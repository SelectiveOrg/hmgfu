/* Cowork — debug-grade memory widgets (Phase 31): live hex field, memory trace, layers.
   The hex field is the v1 /debug canvas brought into the canvas widget system: layer colors,
   size=density, glow=energy, pan/zoom, click-inspector — plus LIVE activation (gold pulse on
   the memories each turn recalls, driven by the memory_used WS event). */

/* explicit window globals: babel-standalone evals each script in its own scope, so a bare
   top-level const would NOT be visible to MemoryPanels.jsx / HexZoom.jsx */
const HMG_LAYER_COLORS = window.HMG_LAYER_COLORS = { L0_raw: "#8b949e", L1_session: "#58a6ff",
  L2_project: "#3fb950", L3_identity: "#d29922", L4_world_model: "#f85149", L5_deep_pattern: "#bc8cff" };
const HMG_LAYER_LABELS = window.HMG_LAYER_LABELS = { L0_raw: "L0 raw", L1_session: "L1 session",
  L2_project: "L2 project", L3_identity: "L3 identity", L4_world_model: "L4 world model",
  L5_deep_pattern: "L5 pattern" };

/* ONE source for the ontology palette (Phase 44) — every widget + HexZoom read these globals */
const HMG_CLASS_COLORS = window.HMG_CLASS_COLORS = { session: "#4c8fff", message: "#8b949e",
  fact: "#d29922", self: "#db61a2", micro: "#6b7280", macro: "#3fb950", directive: "#f85149",
  tool: "#39c5cf", skill: "#bc8cff" };
const HMG_CLASS_LABELS = window.HMG_CLASS_LABELS = { session: "session", message: "message",
  fact: "fact", self: "self-aware", micro: "micro", macro: "macro", directive: "directive",
  tool: "tool", skill: "skill" };
const HMG_CAT_COLORS = window.HMG_CAT_COLORS = { positive: "#3fb950", negative: "#f85149",
  neutral: "#8b949e", factual: "#d29922", contradictory: "#db61a2" };

/* --- live hex field ------------------------------------------------------------- */
function HexFieldBody({ viz, activated, height }) {
  const { HmgHexGrid } = window.PersonalAgentDesignSystem_94ad89;
  const canvasRef = React.useRef(null);
  const [selected, setSelected] = React.useState(null);
  // "zoom" (DEFAULT: coarse frontier, big green macros that auto-bloom on zoom — the Nanite view),
  // "field" (flat live field), "compression" (DS animation)
  const [mode, setMode] = React.useState("zoom");
  const [drill, setDrill] = React.useState({ stack: [], viz: null });   // macro drill-down (P6)
  const cam = React.useRef({ x: 0, y: 0, zoom: 1, fitted: false });
  const raf = React.useRef(0);
  const HEXR = 16;
  const view = drill.stack.length ? drill.viz : viz;   // drilled level or the root field
  const nodes = (view && view.hex_nodes) || [];
  const edges = (view && view.edges) || [];
  const activeIds = React.useMemo(() => new Set((activated && activated.ids) || []), [activated]);
  const byId = React.useMemo(() => Object.fromEntries(nodes.map((n) => [n.id, n])), [nodes]);
  const compressionNodes = React.useMemo(() => {
    const clusters = new Set(nodes.filter((n) => n.type === "macro" && n.cluster != null).map((n) => n.cluster));
    const counts = {}; nodes.forEach((n) => { if (n.type !== "macro" && clusters.has(n.cluster)) counts[n.cluster] = (counts[n.cluster] || 0) + 1; });
    return nodes.filter((n) => clusters.has(n.cluster)).map((n) => ({ ...n,
      count: n.type === "macro" ? (counts[n.cluster] || 0) : n.count, active: activeIds.has(n.id) }));
  }, [nodes, activeIds]);
  const macroLinks = React.useMemo(() => edges.map((e) => [byId[e.src], byId[e.dst]])
    .filter(([a, b]) => a && b && a.type === "macro" && b.type === "macro" && a.cluster != null && b.cluster != null)
    .map(([a, b]) => [a.cluster, b.cluster]), [edges, byId]);
  const px = (n) => ({ x: HEXR * 1.5 * n.q, y: HEXR * Math.sqrt(3) * (n.r + n.q / 2) });

  const draw = React.useCallback(() => {
    const canvas = canvasRef.current; if (!canvas) return;
    const ctx = canvas.getContext("2d"), c = cam.current;
    const W = canvas.width, H = canvas.height;
    const scr = (p) => ({ x: (p.x - c.x) * c.zoom + W / 2, y: (p.y - c.y) * c.zoom + H / 2 });
    ctx.clearRect(0, 0, W, H);
    ctx.lineWidth = Math.max(0.4, c.zoom * 0.7);
    for (const e of edges) {                       // one pass, styled per edge kind
      const a = byId[e.src], b = byId[e.dst]; if (!a || !b) continue;
      const pa = scr(px(a)), pb = scr(px(b));
      if ((pa.x < 0 && pb.x < 0) || (pa.x > W && pb.x > W) || (pa.y < 0 && pb.y < 0) || (pa.y > H && pb.y > H)) continue;
      const hot = activeIds.has(e.src) && activeIds.has(e.dst);
      ctx.strokeStyle = e.type === "Wormhole" ? "#bc8cff" : (e.tension > 0.4 ? "#f8514977" : hot ? "#d29922" : "#3d444d66");
      ctx.setLineDash(e.type === "Wormhole" ? [5, 4] : []);
      ctx.beginPath(); ctx.moveTo(pa.x, pa.y); ctx.lineTo(pb.x, pb.y); ctx.stroke();
    }
    ctx.setLineDash([]);
    for (const n of nodes) {
      const pos = scr(px(n));
      if (pos.x < -60 || pos.x > W + 60 || pos.y < -60 || pos.y > H + 60) continue;
      const hot = activeIds.has(n.id);
      const size = (HEXR * 0.5 + HEXR * 0.45 * (n.density || 0)) * c.zoom;
      const color = HMG_LAYER_COLORS[n.layer] || "#8b949e";
      const glow = hot ? 1 : (n.energy || 0);
      if (glow > 0.15) { ctx.save(); ctx.shadowColor = hot ? "#d29922" : color; ctx.shadowBlur = 20 * glow * c.zoom; }
      ctx.beginPath();
      for (let i = 0; i < 6; i++) {
        const a = Math.PI / 3 * i;
        const x = pos.x + size * Math.cos(a), y = pos.y + size * Math.sin(a);
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      }
      ctx.closePath();
      ctx.fillStyle = n.status === "superseded" ? "#3d1d1d" : color + (hot ? "ff" : "bb");
      ctx.fill();
      if (glow > 0.15) ctx.restore();
      ctx.lineWidth = (hot ? 2.4 : selected === n.id ? 2 : 0.8) * c.zoom;
      ctx.strokeStyle = hot ? "#d29922" : selected === n.id ? "#fff" : n.type === "macro" ? "#fff9" : "#0d1117";
      ctx.stroke();
      if (c.zoom > 1.1) {
        ctx.fillStyle = "#e6edf3"; ctx.font = `${9 * c.zoom}px system-ui`; ctx.textAlign = "center";
        ctx.fillText((n.type === "macro" ? "◈ " : "") + (n.label || ""), pos.x, pos.y + size + 10 * c.zoom);
      }
    }
  }, [nodes, edges, byId, activeIds, selected]);

  const schedule = React.useCallback(() => {          // rAF-throttled redraws (pan floods)
    cancelAnimationFrame(raf.current); raf.current = requestAnimationFrame(draw);
  }, [draw]);

  React.useEffect(() => {                              // fit view once data arrives
    if (!nodes.length || cam.current.fitted) { schedule(); return; }
    const xs = nodes.map((n) => px(n).x), ys = nodes.map((n) => px(n).y);
    const cx = (Math.min(...xs) + Math.max(...xs)) / 2, cy = (Math.min(...ys) + Math.max(...ys)) / 2;
    const span = Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys), 1);
    const canvas = canvasRef.current;
    cam.current = { x: cx, y: cy, zoom: Math.min(1.6, (canvas ? canvas.width : 380) * 0.85 / span), fitted: true };
    schedule();
  }, [nodes, schedule]);
  React.useEffect(schedule, [activated, selected, viz, schedule]);

  React.useEffect(() => {                              // trace-widget → focus this node
    const onFocus = (ev) => {
      const n = byId[ev.detail && ev.detail.id]; if (!n) return;
      setMode("field");
      const p = px(n);
      cam.current = { ...cam.current, x: p.x, y: p.y, zoom: Math.max(cam.current.zoom, 1.6) };
      setSelected(n.id); schedule();
    };
    window.addEventListener("hmg-focus", onFocus);
    return () => window.removeEventListener("hmg-focus", onFocus);
  }, [byId, schedule]);

  React.useEffect(() => {                              // size canvas to widget box
    const canvas = canvasRef.current; if (!canvas) return;
    canvas.width = canvas.clientWidth * devicePixelRatio;
    canvas.height = canvas.clientHeight * devicePixelRatio;
    schedule();
  }, [height, schedule, mode]);

  const onPointerDown = (e) => {
    const el = e.currentTarget; try { el.setPointerCapture(e.pointerId); } catch {}
    const start = { x: e.clientX, y: e.clientY, cx: cam.current.x, cy: cam.current.y, moved: false };
    const move = (ev) => {
      const dx = ev.clientX - start.x, dy = ev.clientY - start.y;
      if (Math.abs(dx) + Math.abs(dy) > 3) start.moved = true;
      cam.current.x = start.cx - dx * devicePixelRatio / cam.current.zoom;
      cam.current.y = start.cy - dy * devicePixelRatio / cam.current.zoom;
      schedule();
    };
    const up = (ev) => {
      el.removeEventListener("pointermove", move); el.removeEventListener("pointerup", up);
      if (!start.moved) clickSelect(ev);
    };
    el.addEventListener("pointermove", move); el.addEventListener("pointerup", up);
  };
  const clickSelect = (e) => {
    const canvas = canvasRef.current, rect = canvas.getBoundingClientRect(), c = cam.current;
    const mx = (e.clientX - rect.left) * devicePixelRatio, my = (e.clientY - rect.top) * devicePixelRatio;
    let best = null, bd = 1e9;
    for (const n of nodes) {
      const p = px(n);
      const sx = (p.x - c.x) * c.zoom + canvas.width / 2, sy = (p.y - c.y) * c.zoom + canvas.height / 2;
      const d = Math.hypot(sx - mx, sy - my);
      if (d < HEXR * 1.2 * c.zoom && d < bd) { best = n; bd = d; }
    }
    setSelected(best ? best.id : null);
  };
  const drillIn = (n) => {
    if (!n || !n.children) return;
    window.HMGFU.graphViz(220, n.id).then((v) => {
      cam.current.fitted = false; setSelected(null);
      setDrill((d) => ({ stack: [...d.stack, { id: n.id, label: n.label }], viz: v }));
    }).catch(() => {});
  };
  const drillTo = (i) => {                       // -1 = back to the root field
    if (i < 0) { cam.current.fitted = false; setSelected(null); setDrill({ stack: [], viz: null }); return; }
    const target = drill.stack[i];
    window.HMGFU.graphViz(220, target.id).then((v) => {
      cam.current.fitted = false; setSelected(null);
      setDrill((d) => ({ stack: d.stack.slice(0, i + 1), viz: v }));
    }).catch(() => {});
  };
  const onWheel = (e) => {
    e.preventDefault();
    const z = Math.min(5, Math.max(0.12, cam.current.zoom * (e.deltaY < 0 ? 1.12 : 0.89)));
    cam.current.zoom = z;
    const sel0 = selected ? byId[selected] : null;
    if (z >= 4.9 && sel0 && sel0.children) drillIn(sel0);          // zoom-to-level: descend
    else if (z <= 0.13 && drill.stack.length) drillTo(drill.stack.length - 2);   // ascend
    else schedule();
  };

  const sel = selected ? byId[selected] : null;
  return (
    <div style={{ position: "relative", height: "100%", background: "hsl(228 12% 7%)", borderRadius: "0 0 var(--radius-md) var(--radius-md)", overflow: "hidden" }}>
      {mode === "zoom" ? <window.HexZoom.HexZoomBody height={height} />
        : mode === "field" ? <canvas ref={canvasRef} onPointerDown={onPointerDown} onWheel={onWheel}
        style={{ width: "100%", height: "100%", display: "block", cursor: "grab", touchAction: "none" }} />
        : compressionNodes.length ? <HmgHexGrid nodes={compressionNodes} macroLinks={macroLinks} size={22}
            height={Math.max(120, height || 240)} showEdges showLabels style={{ borderRadius: 0 }} />
          : <div style={{ padding: "52px 16px", color: "hsl(var(--muted-foreground))", fontSize: 12, textAlign: "center" }}>No macro clusters to compress yet.</div>}
      <div style={{ position: "absolute", top: 7, left: 7, zIndex: 5, display: "flex", gap: 3, padding: 2, borderRadius: 6, background: "rgba(13,17,23,.86)", border: "1px solid #30363d" }}>
        <button data-hex-mode="zoom" onClick={() => { setMode("zoom"); setDrill({ stack: [], viz: null }); cam.current.fitted = false; }} style={hexModeButton(mode === "zoom")}>Λ Zoom</button>
        <button data-hex-mode="field" onClick={() => { setMode("field"); setDrill({ stack: [], viz: null }); cam.current.fitted = false; }} style={hexModeButton(mode === "field")}>Live field</button>
        <button data-hex-mode="compression" onClick={() => setMode("compression")} style={hexModeButton(mode === "compression")}>Λ Compression</button>
      </div>
      {mode === "field" && drill.stack.length > 0 && (
        <div style={{ position: "absolute", top: 34, left: 8, zIndex: 5, display: "flex", gap: 4, alignItems: "center", fontSize: 10, fontFamily: "var(--font-mono)", background: "rgba(13,17,23,.86)", border: "1px solid #30363d", borderRadius: 6, padding: "2px 6px" }}>
          <span onClick={() => drillTo(-1)} style={{ cursor: "pointer", color: "#58a6ff" }}>Field</span>
          {drill.stack.map((c, i) => (
            <span key={c.id}>
              <span style={{ color: "#8b949e" }}> / </span>
              <span onClick={() => i < drill.stack.length - 1 && drillTo(i)}
                style={{ cursor: i < drill.stack.length - 1 ? "pointer" : "default", color: i < drill.stack.length - 1 ? "#58a6ff" : "#e6edf3" }}>{c.label}</span>
            </span>))}
        </div>)}
      {mode === "field" && activated && activated.ids && activated.ids.length > 0 && drill.stack.length === 0 && (
        <div style={{ position: "absolute", top: 34, left: 8, fontSize: 10, color: "#d29922", fontFamily: "var(--font-mono)" }}>
          ⚡ {activated.ids.length} activated
        </div>)}
      {mode === "field" && sel && (
        <div style={{ position: "absolute", left: 6, bottom: 6, right: 6, maxHeight: "48%", overflowY: "auto", background: "rgba(13,17,23,.94)", border: "1px solid #30363d", borderRadius: 8, padding: "8px 10px", fontSize: 11, color: "#e6edf3" }}>
          <b style={{ color: HMG_LAYER_COLORS[sel.layer] || "#58a6ff" }}>{sel.label || "(untitled)"}</b>
          <span style={{ color: "#8b949e" }}> · {sel.kind} · {HMG_LAYER_LABELS[sel.layer] || sel.layer} · {sel.status} · src {sel.source}</span>
          <div style={{ margin: "4px 0", color: "#c9d1d9" }}>{sel.summary}</div>
          {sel.children > 0 && (
            <button onClick={() => drillIn(sel)} style={{ float: "right", border: "1px solid #d29922", background: "transparent", color: "#d29922", borderRadius: 5, padding: "2px 8px", fontSize: 10, cursor: "pointer", fontFamily: "var(--font-mono)" }}>
              zoom in ({sel.children})
            </button>)}
          <div style={{ color: "#8b949e" }}>ρ {sel.density} · stability {sel.stability} · energy {sel.energy} · accessed {sel.access}×
            {sel.entities && sel.entities.length ? <><br />entities: {sel.entities.join(", ")}</> : null}
            {sel.topics && sel.topics.length ? <><br />topics: {sel.topics.join(", ")}</> : null}</div>
        </div>)}
    </div>
  );
}

function hexModeButton(active) {
  return { border: "none", borderRadius: 4, padding: "3px 7px", cursor: "pointer", fontSize: 9.5,
    fontFamily: "var(--font-mono)", background: active ? "#d29922" : "transparent",
    color: active ? "#17130a" : "#c9d1d9" };
}

window.MemoryWidgets = { HexFieldBody };
