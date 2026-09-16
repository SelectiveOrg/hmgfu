/* HMG-Fu spatial LOD map: wheel zoom reveals detail inside stable macro footprints. */

const {
  HZ_ROOT_CAP, HZ_CHILD_CAP, HZ_EXPAND_DIAM, HZ_COLLAPSE_DIAM,
  HZ_MIN_ZOOM, HZ_MAX_ZOOM, hzIsMacro, hzLayoutSpatialLod,
  hzFitCamera, hzScreen, hzOnscreen, hzLodAction, drawHexZoom,
} = window.HexZoomCore;

function HexZoomBody() {
  const canvasRef = React.useRef(null);
  const [selected, setSelected] = React.useState(null);
  const [status, setStatus] = React.useState("loading");
  const stateRef = React.useRef(null);
  if (!stateRef.current) stateRef.current = {
    loaded: new Map(), parentOf: new Map(), childrenOf: new Map(), rootIds: [],
    expanded: new Set(), edges: new Map(), cache: new Map(), pending: new Set(),
    cam: { x: 0, y: 0, zoom: 1, fitted: false },
  };

  const ingest = React.useCallback((payload, parentId = null) => {
    const state = stateRef.current;
    const childIds = [];
    for (const node of payload.hex_nodes || []) {
      let entry = state.loaded.get(node.id);
      if (!entry) {
        entry = { n: node, x: 0, y: 0, tx: 0, ty: 0, radius: 1,
          drawRadius: 1, alpha: 0, reveal: 0, hasPos: false, depth: 0 };
        state.loaded.set(node.id, entry);
      } else entry.n = node;
      if (parentId) {
        state.parentOf.set(node.id, parentId);
        childIds.push(node.id);
      }
    }
    if (parentId) state.childrenOf.set(parentId, childIds);
    for (const edge of payload.edges || []) {
      state.edges.set(`${edge.src}|${edge.dst}`, {
        src: edge.src, dst: edge.dst, relation: edge.relation,
        worm: edge.type === "Wormhole" || edge.relation === "wormhole",
      });
    }
  }, []);

  const collapseBranch = React.useCallback((id) => {
    const state = stateRef.current, stack = [id];
    while (stack.length) {
      const current = stack.pop();
      state.expanded.delete(current);
      for (const child of state.childrenOf.get(current) || []) stack.push(child);
    }
  }, []);

  const expandBranch = React.useCallback((id) => {
    const state = stateRef.current;
    if (state.expanded.has(id) || state.pending.has(id)) return;
    if (state.cache.has(id)) {
      ingest(state.cache.get(id), id);
      state.expanded.add(id);
      return;
    }
    state.pending.add(id);
    window.HMGFU.graphViz(HZ_CHILD_CAP, id).then((payload) => {
      const current = stateRef.current;
      current.pending.delete(id);
      current.cache.set(id, payload);
      if (!(payload.hex_nodes || []).length) {
        const entry = current.loaded.get(id);
        if (entry) entry.n.children = 0;
        current.expanded.delete(id);
        return;
      }
      ingest(payload, id);
      current.expanded.add(id);
    }).catch(() => stateRef.current.pending.delete(id));
  }, [ingest]);

  const syncAutoLod = React.useCallback((canvas) => {
    const state = stateRef.current;
    for (const entry of state.loaded.values()) {
      if (!hzIsMacro(entry) || entry.alpha < 0.06) continue;
      const onscreen = hzOnscreen(entry, state, canvas.width, canvas.height);
      const action = hzLodAction(entry, state.cam.zoom, onscreen, state.expanded.has(entry.n.id));
      if (action === "expand") {
        expandBranch(entry.n.id);
      } else if (action === "collapse") {
        collapseBranch(entry.n.id);
      }
    }
    if (selected) {
      const entry = state.loaded.get(selected);
      if (!entry || entry.alpha < 0.03) setSelected(null);
    }
  }, [collapseBranch, expandBranch, selected]);

  React.useEffect(() => {
    let alive = true;
    const load = () => {
      setStatus("loading");
      window.HMGFU.graphViz(HZ_ROOT_CAP, null, false, true).then((payload) => {
        if (!alive) return;
        const state = stateRef.current;
        state.loaded.clear(); state.parentOf.clear(); state.childrenOf.clear();
        state.expanded.clear(); state.edges.clear(); state.cache.clear(); state.pending.clear();
        state.rootIds = (payload.hex_nodes || []).map((node) => node.id);
        state.cam.fitted = false;
        ingest(payload);
        setSelected(null);
        setStatus(state.rootIds.length ? "ready" : "empty");
      }).catch(() => alive && setStatus("error"));
    };
    load();
    window.addEventListener("hmg-graph-changed", load);
    return () => { alive = false; window.removeEventListener("hmg-graph-changed", load); };
  }, [ingest]);

  React.useEffect(() => {
    let alive = true, raf = 0;
    const frame = () => {
      if (!alive) return;
      const canvas = canvasRef.current, state = stateRef.current;
      if (canvas) {
        const width = Math.max(1, Math.round(canvas.clientWidth * devicePixelRatio));
        const height = Math.max(1, Math.round(canvas.clientHeight * devicePixelRatio));
        if (canvas.width !== width || canvas.height !== height) {
          canvas.width = width; canvas.height = height; state.cam.fitted = false;
        }
        hzLayoutSpatialLod(state);
        if (!state.cam.fitted) hzFitCamera(state, canvas.width, canvas.height);
        drawHexZoom(canvas, state, selected);
        syncAutoLod(canvas);
      }
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
    return () => { alive = false; cancelAnimationFrame(raf); };
  }, [selected, syncAutoLod]);

  React.useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const onWheel = (event) => {
      event.preventDefault();
      const state = stateRef.current, rect = canvas.getBoundingClientRect();
      const sx = canvas.width / Math.max(1, rect.width), sy = canvas.height / Math.max(1, rect.height);
      const mx = (event.clientX - rect.left) * sx, my = (event.clientY - rect.top) * sy;
      const oldZoom = state.cam.zoom;
      const nextZoom = Math.min(HZ_MAX_ZOOM, Math.max(HZ_MIN_ZOOM,
        oldZoom * Math.exp(-event.deltaY * 0.0018)));
      const worldX = state.cam.x + (mx - canvas.width / 2) / oldZoom;
      const worldY = state.cam.y + (my - canvas.height / 2) / oldZoom;
      state.cam.zoom = nextZoom;
      state.cam.x = worldX - (mx - canvas.width / 2) / nextZoom;
      state.cam.y = worldY - (my - canvas.height / 2) / nextZoom;
    };
    canvas.addEventListener("wheel", onWheel, { passive: false });
    return () => canvas.removeEventListener("wheel", onWheel);
  }, []);

  const pick = React.useCallback((event) => {
    const canvas = canvasRef.current, state = stateRef.current;
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    const mx = (event.clientX - rect.left) * canvas.width / Math.max(1, rect.width);
    const my = (event.clientY - rect.top) * canvas.height / Math.max(1, rect.height);
    const entries = [...state.loaded.values()].filter((entry) => entry.alpha > 0.16)
      .sort((a, b) => (b.depth || 0) - (a.depth || 0));
    for (const entry of entries) {
      const p = hzScreen(entry, state, canvas.width, canvas.height);
      const dx = Math.abs(mx - p.x), dy = Math.abs(my - p.y);
      if (dy <= p.radius && dx <= p.radius * 0.90 && dx * 0.58 + dy <= p.radius) return entry;
    }
    return null;
  }, []);

  const onPointerDown = (event) => {
    const canvas = event.currentTarget, state = stateRef.current;
    try { canvas.setPointerCapture(event.pointerId); } catch {}
    const scaleX = canvas.width / Math.max(1, canvas.clientWidth);
    const scaleY = canvas.height / Math.max(1, canvas.clientHeight);
    const start = { x: event.clientX, y: event.clientY, camX: state.cam.x,
      camY: state.cam.y, moved: false };
    const move = (next) => {
      if (Math.abs(next.clientX - start.x) + Math.abs(next.clientY - start.y) > 3) start.moved = true;
      state.cam.x = start.camX - (next.clientX - start.x) * scaleX / state.cam.zoom;
      state.cam.y = start.camY - (next.clientY - start.y) * scaleY / state.cam.zoom;
    };
    const finish = (next) => {
      canvas.removeEventListener("pointermove", move);
      canvas.removeEventListener("pointerup", finish);
      canvas.removeEventListener("pointercancel", finish);
      if (!start.moved && next.type === "pointerup") {
        const hit = pick(next);
        setSelected(hit ? hit.n.id : null);
      }
    };
    canvas.addEventListener("pointermove", move);
    canvas.addEventListener("pointerup", finish);
    canvas.addEventListener("pointercancel", finish);
  };

  const selectedEntry = selected ? stateRef.current.loaded.get(selected) : null;
  return (
    <div style={{ position: "relative", height: "100%", overflow: "hidden", background: "hsl(228 12% 6%)" }}>
      <canvas ref={canvasRef} data-testid="hex-lod-canvas" onPointerDown={onPointerDown}
        style={{ width: "100%", height: "100%", display: "block", cursor: "grab", touchAction: "none" }} />
      {status !== "ready" && (
        <div style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center", color: "#8b949e", fontSize: 11, pointerEvents: "none" }}>
          {status === "loading" ? "Loading memory map…" : status === "empty" ? "No memory macros yet." : "Memory map unavailable."}
        </div>)}
      {status === "ready" && (
        <div style={{ position: "absolute", left: 8, bottom: 7, color: "#8b949e", fontSize: 9, fontFamily: "var(--font-mono)", pointerEvents: "none", background: "rgba(13,17,23,.72)", padding: "2px 5px", borderRadius: 4 }}>
          wheel zoom · detail replaces each macro in place · drag pan · click inspect
        </div>)}
      {stateRef.current.pending.size > 0 && (
        <div style={{ position: "absolute", right: 8, bottom: 7, color: "#d29922", fontSize: 9, fontFamily: "var(--font-mono)", pointerEvents: "none" }}>loading detail…</div>)}
      {selectedEntry && (
        <div style={{ position: "absolute", left: 6, right: 6, bottom: 28, maxHeight: "46%", overflowY: "auto", background: "rgba(13,17,23,.95)", border: "1px solid #30363d", borderRadius: 8, padding: "8px 10px", color: "#e6edf3", fontSize: 11 }}>
          <b style={{ color: window.HexZoomCore.HZ_BAND_COLORS[Math.min(selectedEntry.depth || 0, 5)] }}>{selectedEntry.n.label || "(untitled)"}</b>
          <span style={{ color: "#8b949e" }}> · {selectedEntry.n.kind}{selectedEntry.n.children ? ` · contains ${selectedEntry.n.children}` : ""} · {window.HMG_LAYER_LABELS[selectedEntry.n.layer] || selectedEntry.n.layer}</span>
          <div style={{ marginTop: 4, color: "#c9d1d9" }}>{selectedEntry.n.summary}</div>
          {selectedEntry.n.state && (
            <div style={{ marginTop: 6, display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              <span style={{ padding: "1px 7px", borderRadius: 999, fontSize: 10, fontWeight: 600, textTransform: "uppercase",
                color: window.HZ_STATE_FADE[selectedEntry.n.state] || "#58a6ff",
                border: `1px solid ${window.HZ_STATE_FADE[selectedEntry.n.state] || "#1f6feb"}` }}>{selectedEntry.n.state}</span>
              {selectedEntry.n.c != null && <span style={{ color: "#8b949e", fontFamily: "var(--font-mono)" }}>c {Number(selectedEntry.n.c).toFixed(2)}</span>}
              {selectedEntry.n.ledger && <span style={{ color: "#8b949e" }}>
                ledger {["silent", "praise", "explicit"].map((t) => `${t[0]}${selectedEntry.n.ledger[t] || 0}`).join(" ")}
                {selectedEntry.n.ledger.correction ? " · corrected" : ""}</span>}
              {selectedEntry.n.superseded_by && (
                <a href="#" title="jump to the successor fact" onClick={(ev) => { ev.preventDefault(); setSelected(selectedEntry.n.superseded_by.id); }}
                  style={{ color: "#d29922", textDecoration: "none", borderBottom: "1px dotted #d29922" }}>
                  → superseded by “{selectedEntry.n.superseded_by.label}”</a>)}
            </div>)}
        </div>)}
    </div>
  );
}

window.HexZoom = { HexZoomBody };
