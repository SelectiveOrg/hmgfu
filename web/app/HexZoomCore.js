/* Spatial semantic LOD: stable macro footprints with center-convergent child packing. */

(() => {
  const HZ_BAND_COLORS = ["#43d766", "#ef3f45", "#6290dc", "#b66be2", "#f0aa38", "#46c7c7"];
  const HZ_REL = {
    wormhole: "#bc8cff", contradiction: "#f85149", causal: "#e0a83a",
    same_entity: "#58a6ff", temporal: "#6b7280", emotional: "#db61a2",
    part_of: "#43c463", goal_related: "#43c463", project_related: "#43c463",
    semantic_similarity: "#47515f",
  };
  const HZ_ROOT_CAP = 36;   // v3 port colours/tints: HexV3Ports.js (window.hzEdgeColor/hzNodeTint)
  const HZ_CHILD_CAP = 180;
  const HZ_ROOT_RADIUS = 58;
  const HZ_EXPAND_DIAM = 170;
  const HZ_COLLAPSE_DIAM = 118;
  const HZ_MIN_ZOOM = 0.12;
  const HZ_MAX_ZOOM = 96;
  const HZ_CHILD_FILL = 0.92;

  function hzHexDist(a, b = { q: 0, r: 0 }) {
    return (Math.abs(a.q - b.q) + Math.abs(a.q + a.r - b.q - b.r) + Math.abs(a.r - b.r)) / 2;
  }

  function hzSpiral(n) {
    if (n <= 0) return [];
    const out = [{ q: 0, r: 0 }];
    const dirs = [[1, 0], [1, -1], [0, -1], [-1, 0], [-1, 1], [0, 1]];
    for (let ring = 1; out.length < n; ring++) {
      let q = dirs[4][0] * ring, r = dirs[4][1] * ring;
      for (let side = 0; side < 6 && out.length < n; side++) {
        for (let step = 0; step < ring && out.length < n; step++) {
          out.push({ q, r }); q += dirs[side][0]; r += dirs[side][1];
        }
      }
    }
    return out;
  }

  function hzAxial(cell, radius) {
    return {
      x: Math.sqrt(3) * radius * (cell.q + cell.r / 2),
      y: 1.5 * radius * cell.r,
    };
  }

  function hzHexPath(ctx, x, y, radius) {
    ctx.beginPath();
    for (let i = 0; i < 6; i++) {
      const angle = Math.PI / 180 * (60 * i - 90);
      const px = x + radius * Math.cos(angle), py = y + radius * Math.sin(angle);
      i ? ctx.lineTo(px, py) : ctx.moveTo(px, py);
    }
    ctx.closePath();
  }

  function hzIsMacro(entry) {
    return entry.n.kind === "macro" && (entry.n.children || 0) > 0;
  }

  function hzBandColor(entry) {   // Phase 44: color by ONTOLOGY class; depth band is the fallback
    return (window.HMG_CLASS_COLORS || {})[entry.n && entry.n.nodeClass] || HZ_BAND_COLORS[Math.min(entry.depth || 0, HZ_BAND_COLORS.length - 1)];
  }

  function hzStableSort(entries) {
    return [...entries].sort((a, b) => {
      const aq = Number(a.n.q) || 0, bq = Number(b.n.q) || 0;
      const ar = Number(a.n.r) || 0, br = Number(b.n.r) || 0;
      if (ar !== br) return ar - br;
      if (aq !== bq) return aq - bq;
      return String(a.n.id).localeCompare(String(b.n.id));
    });
  }

  function hzChildRingRadius(parentRadius, ring) {
    return parentRadius / (2 * ring + 1);
  }

  function hzHexNorm(x, y) {
    return Math.abs(x) / Math.sqrt(3) + Math.abs(y);
  }

  function hzCenteredCells(count) {
    const cells = hzSpiral(count).map((cell) => ({ ...cell, ...hzAxial(cell, 1) }));
    if (!cells.length) return cells;
    const cx = cells.reduce((sum, cell) => sum + cell.x, 0) / cells.length;
    const cy = cells.reduce((sum, cell) => sum + cell.y, 0) / cells.length;
    return cells.map((cell) => ({ ...cell, x: cell.x - cx, y: cell.y - cy }));
  }

  function hzFitsInside(parentRadius, cells, childRadius, ox, oy) {
    for (const cell of cells) {
      for (let corner = 0; corner < 6; corner++) {
        const angle = Math.PI / 180 * (60 * corner - 90);
        const x = cell.x * childRadius + ox + childRadius * Math.cos(angle);
        const y = cell.y * childRadius + oy + childRadius * Math.sin(angle);
        if (hzHexNorm(x, y) > parentRadius + 1e-7) return false;
      }
    }
    return true;
  }

  function hzConvergeOffset(parent, cells, childRadius) {
    const dx = -parent.tx, dy = -parent.ty;
    const length = Math.hypot(dx, dy);
    if (!cells.length || length < 1e-7) return { x: 0, y: 0 };
    const ux = dx / length, uy = dy / length;
    let low = 0, high = parent.radius * 2;
    for (let i = 0; i < 36; i++) {
      const mid = (low + high) / 2;
      if (hzFitsInside(parent.radius, cells, childRadius, ux * mid, uy * mid)) low = mid;
      else high = mid;
    }
    return { x: ux * low * 0.985, y: uy * low * 0.985 };
  }

  function hzChildFootprint(parent, children) {
    const cells = hzCenteredCells(children.length);
    const ring = Math.max(0, ...cells.map((cell) => hzHexDist(cell)));
    const childRadius = hzChildRingRadius(parent.radius, ring) * HZ_CHILD_FILL;
    const offset = hzConvergeOffset(parent, cells, childRadius);
    const out = new Map();
    children.forEach((entry, index) => {
      out.set(entry.n.id, {
        x: parent.tx + cells[index].x * childRadius + offset.x,
        y: parent.ty + cells[index].y * childRadius + offset.y,
        radius: childRadius,
      });
    });
    return out;
  }

  function hzLayoutSpatialLod(state) {
    const roots = hzStableSort((state.rootIds || []).map((id) => state.loaded.get(id)).filter(Boolean));
    const rootCells = hzCenteredCells(roots.length);
    const seen = new Set();

    function place(entry, geometry, depth, targetAlpha) {
      if (!entry || seen.has(entry.n.id)) return;
      seen.add(entry.n.id);
      entry.depth = depth;
      entry.tx = geometry.x; entry.ty = geometry.y; entry.radius = geometry.radius;
      if (!entry.hasPos) {
        entry.x = entry.tx; entry.y = entry.ty; entry.drawRadius = entry.radius;
        entry.alpha = depth ? 0 : 1; entry.reveal = 0; entry.hasPos = true;
      }
      entry.x += (entry.tx - entry.x) * 0.20;
      entry.y += (entry.ty - entry.y) * 0.20;
      entry.drawRadius += (entry.radius - entry.drawRadius) * 0.20;
      entry.alpha += (targetAlpha - entry.alpha) * 0.18;
      const revealTarget = state.expanded.has(entry.n.id) ? 1 : 0;
      entry.reveal += (revealTarget - entry.reveal) * 0.16;

      const childIds = state.childrenOf.get(entry.n.id) || [];
      const children = hzStableSort(childIds.map((id) => state.loaded.get(id)).filter(Boolean));
      const childGeometry = hzChildFootprint(entry, children);
      for (const child of children) {
        place(child, childGeometry.get(child.n.id), depth + 1, targetAlpha * entry.reveal);
      }
    }

    roots.forEach((entry, index) => {
      place(entry, {
        x: rootCells[index].x * HZ_ROOT_RADIUS,
        y: rootCells[index].y * HZ_ROOT_RADIUS,
        radius: HZ_ROOT_RADIUS,
      }, 0, 1);
    });
    return roots;
  }

  function hzFitCamera(state, width, height) {
    const roots = (state.rootIds || []).map((id) => state.loaded.get(id)).filter(Boolean);
    if (!roots.length) return false;
    const minX = Math.min(...roots.map((e) => e.tx - e.radius));
    const maxX = Math.max(...roots.map((e) => e.tx + e.radius));
    const minY = Math.min(...roots.map((e) => e.ty - e.radius));
    const maxY = Math.max(...roots.map((e) => e.ty + e.radius));
    state.cam.x = (minX + maxX) / 2;
    state.cam.y = (minY + maxY) / 2;
    state.cam.zoom = Math.max(HZ_MIN_ZOOM, Math.min(1.25,
      width * 0.88 / Math.max(1, maxX - minX),
      height * 0.76 / Math.max(1, maxY - minY)));
    state.cam.fitted = true;
    return true;
  }

  function hzScreen(entry, state, width, height) {
    return {
      x: (entry.x - state.cam.x) * state.cam.zoom + width / 2,
      y: (entry.y - state.cam.y) * state.cam.zoom + height / 2,
      radius: entry.drawRadius * state.cam.zoom,
    };
  }

  function hzOnscreen(entry, state, width, height, margin = 36) {
    const p = hzScreen(entry, state, width, height);
    return p.x + p.radius >= -margin && p.x - p.radius <= width + margin
      && p.y + p.radius >= -margin && p.y - p.radius <= height + margin;
  }

  function hzLodAction(entry, zoom, onscreen, expanded) {
    const diameter = entry.radius * zoom * 2;
    if (onscreen && diameter >= HZ_EXPAND_DIAM && !expanded) return "expand";
    if (diameter <= HZ_COLLAPSE_DIAM && expanded) return "collapse";
    return null;
  }

  function hzDrawEdge(ctx, edge, state, width, height) {
    const a = state.loaded.get(edge.src), b = state.loaded.get(edge.dst);
    if (!a || !b || a.alpha < 0.04 || b.alpha < 0.04) return;
    const pa = hzScreen(a, state, width, height), pb = hzScreen(b, state, width, height);
    const worm = edge.worm || edge.relation === "wormhole" || edge.portType === "wormhole";
    const color = window.hzEdgeColor(edge, HZ_REL, worm);   // v3 portType, HZ_REL fallback
    ctx.save();
    ctx.globalAlpha = Math.min(a.alpha, b.alpha) * (worm ? 0.78 : 0.42);
    ctx.strokeStyle = color; ctx.lineWidth = worm ? 2 : 1;
    ctx.setLineDash(worm ? [5, 4] : []);
    if (worm) { ctx.shadowColor = color; ctx.shadowBlur = 8; }
    ctx.beginPath(); ctx.moveTo(pa.x, pa.y); ctx.lineTo(pb.x, pb.y); ctx.stroke();
    ctx.restore();
  }

  function drawHexZoom(canvas, state, selectedId) {
    const ctx = canvas.getContext("2d"), width = canvas.width, height = canvas.height;
    ctx.clearRect(0, 0, width, height);
    const edgeGroups = new Map();
    for (const edge of state.edges.values()) {
      const pa = state.parentOf.get(edge.src) || "__root__";
      const pb = state.parentOf.get(edge.dst) || "__root__";
      if (pa === pb) (edgeGroups.get(pa) || edgeGroups.set(pa, []).get(pa)).push(edge);
    }
    for (const edge of edgeGroups.get("__root__") || []) hzDrawEdge(ctx, edge, state, width, height);

    function drawBranch(entry) {
      if (!entry || entry.alpha < 0.025) return;
      const p = hzScreen(entry, state, width, height);
      if (p.radius < 0.45) return;
      const color = hzBandColor(entry), macro = hzIsMacro(entry), selected = entry.n.id === selectedId;
      const coarse = macro && entry.reveal < 0.78;

      ctx.save();
      hzHexPath(ctx, p.x, p.y, p.radius * 1.002);
      ctx.globalAlpha = entry.alpha * (macro ? 0.88 - entry.reveal * 0.64 : 0.84) * (window.HZ_STATE_ALPHA[window.hzLifeState(entry.n)] || 1);
      ctx.fillStyle = window.hzNodeTint(entry.n, entry.n.active ? "#e0a83a" : color);   // v3 lifecycle tint
      if (macro || entry.n.active) { ctx.shadowColor = color; ctx.shadowBlur = Math.min(18, p.radius * 0.18); }
      ctx.fill();
      ctx.restore();

      ctx.save();
      hzHexPath(ctx, p.x, p.y, p.radius);
      ctx.globalAlpha = Math.max(0.22, entry.alpha) * (selected ? 1 : 0.82);
      ctx.strokeStyle = selected ? "#ffffff" : color;
      ctx.lineWidth = selected ? 2.5 : Math.max(1, Math.min(2.2, p.radius * 0.035));
      ctx.stroke();
      ctx.restore();
      window.hzDrawState(ctx, entry.n, p.x, p.y, p.radius, entry.alpha);   // v3 lifecycle shape overlay

      const childIds = state.childrenOf.get(entry.n.id) || [];
      if (childIds.length && entry.reveal > 0.015) {
        for (const edge of edgeGroups.get(entry.n.id) || []) hzDrawEdge(ctx, edge, state, width, height);
        for (const childId of childIds) drawBranch(state.loaded.get(childId));
      }

      if (coarse && p.radius >= 18) {
        ctx.save();
        ctx.globalAlpha = entry.alpha;
        ctx.fillStyle = "#08110b"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
        ctx.font = `700 ${Math.max(10, Math.min(24, p.radius * 0.34))}px system-ui`;
        ctx.fillText(String(entry.n.children || ""), p.x, p.y);
        if (p.radius >= 29) {
          ctx.fillStyle = "#12351b"; ctx.textBaseline = "middle";
          ctx.font = `${Math.max(8, Math.min(11, p.radius * 0.16))}px system-ui`;
          ctx.fillText((entry.n.label || "macro").replace(/^Macro:\s*/i, "").slice(0, 22), p.x, p.y + p.radius * 0.58);
        }
        ctx.restore();
      } else if (!macro && p.radius >= 16 && entry.alpha > 0.55) {
        ctx.save();
        ctx.globalAlpha = Math.min(1, entry.alpha * 0.92);
        ctx.fillStyle = "#f3f5f7"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
        ctx.font = `${Math.max(7, Math.min(11, p.radius * 0.42))}px system-ui`;
        let label = (entry.n.label || "").slice(0, 28);
        while (label.length > 3 && ctx.measureText(label + "…").width > p.radius * 1.48) label = label.slice(0, -1);
        if (label !== (entry.n.label || "").slice(0, 28)) label += "…";
        ctx.fillText(label, p.x, p.y);
        ctx.restore();
      }
    }

    for (const id of state.rootIds || []) drawBranch(state.loaded.get(id));
  }

  window.HexZoomCore = {
    HZ_BAND_COLORS, HZ_REL, HZ_ROOT_CAP, HZ_CHILD_CAP, HZ_ROOT_RADIUS,
    HZ_EXPAND_DIAM, HZ_COLLAPSE_DIAM, HZ_MIN_ZOOM, HZ_MAX_ZOOM, HZ_CHILD_FILL,
    hzHexDist, hzSpiral, hzAxial, hzHexPath, hzIsMacro, hzBandColor, hzChildRingRadius,
    hzHexNorm, hzCenteredCells, hzConvergeOffset, hzChildFootprint, hzLayoutSpatialLod,
    hzFitCamera, hzScreen, hzOnscreen, hzLodAction,
    drawHexZoom,
  };
})();
