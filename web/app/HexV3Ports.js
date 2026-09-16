/* THEORY v3 (The Governed Hexagon) — hex UI colour logic, extracted from HexZoomCore to keep it
   under the frontend line ceiling. window globals for the no-build loader; loaded before HexZoomCore. */
(function () {
  // v3 B.2: the six typed side-ports + the center wormhole-port. Ports never affect ranking (A1/A2).
  window.HZ_PORT = {
    factual: "#58a6ff", temporal: "#6b7280", contradictory: "#f85149",
    positive: "#43c463", negative: "#db61a2", context: "#47515f", wormhole: "#bc8cff",
  };
  window.HZ_PORT_LABEL = {
    factual: "1 · factual", temporal: "2 · temporal", contradictory: "3 · contradiction",
    positive: "4 · positive", negative: "5 · negative", context: "6 · context", wormhole: "◇ wormhole",
  };
  // v3 REAL lifecycle state (from the Regulator ledger when live; else the provisional status-derived
  // `lifecycle`). Normalise either to ONE lowercase token the renderer keys on — so the viz draws what
  // the system DOES (real state) and gracefully falls back when the Regulator is off.
  window.hzLifeState = function (n) {
    return (n && (n.state || (n.lifecycle || "").toLowerCase())) || "";
  };
  window.HZ_STATE_FADE = { superseded: "#6e2b2b", evaporated: "#2a3340" };   // faded tints
  window.HZ_STATE_LABEL = {
    temp: "temp", candidate: "candidate", fact: "fact", superseded: "superseded", evaporated: "evaporated",
  };
  // Fill-alpha per state: TEMP ~empty, CANDIDATE partial, FACT full volume (shape completes the story).
  window.HZ_STATE_ALPHA = { temp: 0.14, candidate: 0.5, fact: 1 };
  window.HZ_LEDGER_COLOR = { silent: "#3a5a78", praise: "#7a6a2a", explicit: "#2f7d4a" };  // event tiers

  function _hexPath(ctx, x, y, r) {
    ctx.beginPath();
    for (var i = 0; i < 6; i++) {
      var a = Math.PI / 180 * (60 * i - 30), px = x + r * Math.cos(a), py = y + r * Math.sin(a);
      i ? ctx.lineTo(px, py) : ctx.moveTo(px, py);
    }
    ctx.closePath();
  }

  // v3 lifecycle SHAPE overlay (called by HexZoomCore after fill/stroke). TEMP = dashed empty ring;
  // FACT = internal hexes, ONE per recorded ledger event (silent use / praise / explicit) — the volume
  // is drawn from the REAL signal ledger, no new storage. CANDIDATE/SUPERSEDED handled by alpha/tint.
  window.hzDrawState = function (ctx, node, x, y, r, alpha) {
    var st = window.hzLifeState(node);
    if (st === "temp") {
      ctx.save(); ctx.globalAlpha = Math.max(0.35, alpha); ctx.setLineDash([4, 3]);
      ctx.strokeStyle = "#8aa0b4"; ctx.lineWidth = 1.2; _hexPath(ctx, x, y, r * 0.9); ctx.stroke(); ctx.restore();
      return;
    }
    if (st !== "fact" || !node.ledger || r < 12) return;
    var led = node.ledger, ev = [], t, i;
    for (t of ["silent", "praise", "explicit"])
      for (i = 0; i < Math.min(led[t] || 0, t === "silent" ? 6 : t === "praise" ? 4 : 8); i++) ev.push(window.HZ_LEDGER_COLOR[t]);
    ev = ev.slice(0, 12);
    if (!ev.length) return;
    var cols = Math.ceil(Math.sqrt(ev.length)), rows = Math.ceil(ev.length / cols), ir = r * 0.16, gap = r * 0.44;
    ctx.save(); ctx.globalAlpha = alpha;
    for (i = 0; i < ev.length; i++) {
      var cx = x + ((i % cols) - (cols - 1) / 2) * gap, cy = y + (Math.floor(i / cols) - (rows - 1) / 2) * gap;
      ctx.fillStyle = ev[i]; _hexPath(ctx, cx, cy, ir); ctx.fill();
    }
    ctx.restore();
  };

  // Edge colour: the v3 portType when the backend provides it, else the legacy relation map (compat).
  window.hzEdgeColor = function (edge, relMap, worm) {
    return (edge.portType && window.HZ_PORT[edge.portType])
      || (worm ? window.HZ_PORT.wormhole : (relMap[edge.relation] || relMap.semantic_similarity));
  };
  // Node tint: SUPERSEDED/EVAPORATED fade the base colour; TEMP/CANDIDATE/FACT keep `fallback` (they
  // differ by SHAPE — dashed-empty / partial / volume+internal-hexes — drawn in HexZoomCore).
  window.hzNodeTint = function (node, fallback) {
    return window.HZ_STATE_FADE[window.hzLifeState(node)] || fallback;
  };
})();
