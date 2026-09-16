/* Cowork - memory side panels (Trace / Layers / Now / Canon). Reads the shared HMG_CLASS and
   HMG_LAYER window-global palettes (Phase 44: the ontology is visible in every panel). */

function _classDot(cls) {
  return <span title={cls} style={{ display: "inline-block", width: 8, height: 8, borderRadius: 2,
    background: (window.HMG_CLASS_COLORS || {})[cls] || "#8b949e", marginRight: 5, verticalAlign: -1 }} />;
}
function _catTag(cat) {
  if (!cat) return null;
  return <span style={{ fontSize: 8.5, fontFamily: "var(--font-mono)", padding: "0 4px", borderRadius: 3,
    color: (window.HMG_CAT_COLORS || {})[cat] || "#8b949e",
    border: `1px solid ${(window.HMG_CAT_COLORS || {})[cat] || "#8b949e"}55` }}>{cat}</span>;
}

/* --- memory trace ("where the AI walked" this turn) ------------------------------- */
function TraceBody({ activated }) {
  const items = (activated && activated.items) || [];
  if (!items.length) return (
    <div style={{ padding: 14, fontSize: 12, color: "hsl(var(--muted-foreground))" }}>
      Send a message — the memories each turn activates (class, category and the Fu path) appear here.
    </div>);
  return (
    <div style={{ padding: "8px 10px", overflowY: "auto", height: "100%" }}>
      {items.map((it, i) => (
        <div key={i} onClick={() => window.dispatchEvent(new CustomEvent("hmg-focus", { detail: { id: it.id } }))}
          style={{ padding: "6px 8px", marginBottom: 6, border: "1px solid hsl(var(--border))", borderRadius: 6, cursor: "pointer", fontSize: 11.5 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ fontFamily: "var(--font-mono)", color: "hsl(var(--warning))", fontWeight: 600 }}>{(it.score ?? 0).toFixed(2)}</span>
            {_classDot(it.nodeClass || it.kind)}
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 9.5, color: "hsl(var(--muted-foreground))" }}>
              {(window.HMG_CLASS_LABELS || {})[it.nodeClass] || it.kind}</span>
            <span style={{ flex: 1 }} />{_catTag(it.category)}
          </div>
          <div style={{ color: "hsl(var(--foreground))", margin: "2px 0" }}>{it.text}</div>
          {it.reason && <div style={{ fontSize: 10, color: "hsl(var(--muted-foreground))" }}>{it.reason}</div>}
        </div>))}
    </div>
  );
}

/* --- layers: L0..L5 population + the ontology node-class breakdown ------------------ */
function LayersBody({ viz }) {
  const layers = (viz && viz.stats && viz.stats.layers) || null;
  const classes = (viz && viz.classes) || null;
  if (!layers) return <div style={{ padding: 14, fontSize: 12, color: "hsl(var(--muted-foreground))" }}>loading…</div>;
  const bar = (label, count, total, color) => (
    <div style={{ marginBottom: 7 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11.5, marginBottom: 3 }}>
        <span style={{ color: "hsl(var(--foreground))" }}>
          <span style={{ display: "inline-block", width: 9, height: 9, borderRadius: "50%", background: color, marginRight: 6, verticalAlign: -1 }} />{label}</span>
        <span style={{ fontFamily: "var(--font-mono)", color: "hsl(var(--muted-foreground))" }}>{count}</span>
      </div>
      <div style={{ height: 4, background: "hsl(var(--surface-2))", borderRadius: 2 }}>
        <div style={{ height: "100%", width: (count / (total || 1) * 100) + "%", background: color, borderRadius: 2 }} />
      </div>
    </div>);
  const layerTotal = Object.values(layers).reduce((a, b) => a + b, 0) || 1;
  const classTotal = classes ? Object.values(classes).reduce((a, b) => a + b, 0) || 1 : 1;
  return (
    <div style={{ padding: "10px 12px", overflowY: "auto", height: "100%" }}>
      <_Head>Layers (L0 → L5)</_Head>
      {Object.entries(layers).map(([layer, count]) => bar(HMG_LAYER_LABELS[layer] || layer, count, layerTotal, HMG_LAYER_COLORS[layer]))}
      {classes && (<><div style={{ height: 8 }} /><_Head>Node classes (ontology)</_Head>
        {Object.entries(classes).sort((a, b) => b[1] - a[1]).map(([cls, count]) =>
          bar((window.HMG_CLASS_LABELS || {})[cls] || cls, count, classTotal, (window.HMG_CLASS_COLORS || {})[cls] || "#8b949e"))}</>)}
      <div style={{ fontSize: 10.5, color: "hsl(var(--muted-foreground))", marginTop: 4, fontFamily: "var(--font-mono)" }}>
        {layerTotal} points · {(viz.stats && viz.stats.wormholes) || 0} wormholes · {(viz.stats && viz.stats.macros) || 0} macros
      </div>
    </div>
  );
}

/* "Now": time + workspace + canon counts + live memory activity + dream state. */
function NowBody() {
  const { Icon } = window.PA;
  const [d, setD] = React.useState(null);
  React.useEffect(() => {
    const load = () => window.HMGFU.now().then(setD).catch(() => {});
    load(); const t = setInterval(load, 30000); return () => clearInterval(t);
  }, []);
  if (!d) return <div style={{ padding: 14, fontSize: 12, color: "hsl(var(--muted-foreground))" }}>loading…</div>;
  const row = { display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "hsl(var(--muted-foreground))" };
  return (
    <div style={{ padding: "10px 12px", overflowY: "auto", height: "100%" }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 26, fontWeight: 600, color: "hsl(var(--foreground))" }}>{d.time}</span>
        <span style={{ fontSize: 12, color: "hsl(var(--muted-foreground))" }}>{d.date}</span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 3, marginTop: 8 }}>
        <span style={row}><Icon name="folder" size={11} /> {d.workspace.name}{d.workspace.git_branch ? " · " + d.workspace.git_branch : ""}</span>
        <span style={row}><Icon name="database" size={11} /> {d.stats.active} memories · {d.stats.edges} edges · {d.stats.macros} macros</span>
        <span style={row}><Icon name="shield" size={11} /> {d.directives || 0} directives · {d.facts || 0} canon facts</span>
        {d.tensions > 0 && <span style={{ ...row, color: "hsl(var(--warning))" }}><Icon name="zap" size={11} /> {d.tensions} unresolved tensions</span>}
        {d.last_dream && <span style={row}><Icon name="moon" size={11} /> last dream: {d.last_dream}</span>}
      </div>
      <div style={{ margin: "10px 0 4px" }}><_Head>Recently active</_Head></div>
      {(d.recent || []).map((r, i) => (
        <div key={i} style={{ display: "flex", gap: 6, alignItems: "center", padding: "3px 0", fontSize: 11.5 }}>
          {_classDot(r.nodeClass || r.type)}
          <span style={{ flex: 1, color: "hsl(var(--foreground))", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.title}</span>
          {_catTag(r.category)}
        </div>))}
    </div>
  );
}

/* Canon: the compression-immune high-importance layer — directives + canonical facts. */
function CanonBody() {
  const { Icon } = window.PA;
  const [d, setD] = React.useState({ directives: [], facts: [], history: [] });
  const [showHistory, setShowHistory] = React.useState(false);        // 72.4: what WAS true, on demand
  React.useEffect(() => {
    const load = () => Promise.all([window.HMGFU.directives().catch(() => ({ directives: [] })),
      window.HMGFU.facts().catch(() => ({ facts: [], history: [] }))])
      .then(([a, b]) => setD({ directives: a.directives || [], facts: b.facts || [], history: b.history || [] }));
    load(); const t = setInterval(load, 15000); return () => clearInterval(t);
  }, []);
  const empty = !d.directives.length && !d.facts.length;
  return (
    <div style={{ padding: "10px 12px", overflowY: "auto", height: "100%" }}>
      {empty && <div style={{ fontSize: 12, color: "hsl(var(--muted-foreground))" }}>
        No standing directives or canonical facts yet. Teach a rule ("always end with X") or a fact
        ("my name is …") — they land here, survive every compression, and never decay.</div>}
      {d.directives.length > 0 && <><_Head>Directives (survive compression)</_Head>
        {d.directives.map((x, i) => (
          <div key={i} style={{ display: "flex", gap: 6, alignItems: "center", padding: "4px 0", fontSize: 12 }}>
            <Icon name="shield" size={12} color={HMG_CLASS_COLORS.directive} />
            <span style={{ color: "hsl(var(--foreground))" }}>{(x.kind || "").replace("output_", "").replace("_", " ")}: <b>{x.value}</b></span>
          </div>))}</>}
      {d.history.length > 0 && <div style={{ padding: "6px 0 0" }}>
        <button onClick={() => setShowHistory(!showHistory)} style={{ fontSize: 11, background: "none", border: "1px solid hsl(var(--border))", borderRadius: 6, padding: "2px 8px", color: "hsl(var(--muted-foreground))", cursor: "pointer" }}>
          {showHistory ? "hide history" : `history (${d.history.length})`}</button>
        {showHistory && d.history.slice().reverse().map((h, i) => (
          <div key={i} style={{ fontSize: 11, color: "hsl(var(--muted-foreground))", padding: "2px 0 0 4px" }}>
            {(h.updated_at || "").slice(0, 10)} · {h.key}: {h.op === "clear" ? `${h.prev} → (cleared)` : `${h.prev ? h.prev + " → " : ""}${h.value}`}</div>))}
      </div>}
      {d.facts.length > 0 && <><div style={{ height: 8 }} /><_Head>Canonical facts</_Head>
        {d.facts.map((x, i) => (
          <div key={i} style={{ padding: "4px 0", fontSize: 12 }}>
            <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
              <Icon name="check-circle" size={12} color={HMG_CLASS_COLORS.fact} />
              <span style={{ color: "hsl(var(--foreground))" }}>{x.label || (x.key || "").replace("_", " ")}: <b>{x.value}</b>
                {x.prev ? <span style={{ color: "hsl(var(--muted-foreground))" }}> (was {x.prev})</span> : null}</span>
            </div>
            {x.verbatim ? <div style={{ fontSize: 10.5, fontStyle: "italic", color: "hsl(var(--muted-foreground))", margin: "1px 0 0 18px" }}
              title={x.source_turn_id ? "source turn " + x.source_turn_id : undefined}>
              source: “{x.verbatim}” ({(x.updated_at || "").slice(0, 10)})</div> : null}
          </div>))}</>}
    </div>
  );
}

function _Head({ children }) {
  return <div style={{ fontSize: 9.5, fontWeight: 600, letterSpacing: "0.05em", textTransform: "uppercase",
    color: "hsl(var(--muted-foreground))", marginBottom: 4 }}>{children}</div>;
}

window.MemoryPanels = { TraceBody, LayersBody, NowBody, CanonBody };
