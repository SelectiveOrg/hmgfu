/* Cowork — Dream loop + Grader canvas widgets (Phase 33).
   DreamBody: run the dream loop and see the macros / wormholes / contradictions it forms, with
   labels + insights + recent history. GraderBody: a live per-turn feed of the learning loop
   (turn score, memories cited/implied/unused, tools graded, corrections, playbooks). */

const _DREAM_COLORS = { macro: "#3fb950", wormhole: "#bc8cff", contradiction: "#f85149",
  decayed: "#8b949e", promoted: "#58a6ff" };

function _statPill(label, n, color) {
  return (
    <span key={label} style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 11,
      fontFamily: "var(--font-mono)", color: "hsl(var(--foreground))", border: "1px solid hsl(var(--border))",
      borderRadius: 999, padding: "1px 8px" }}>
      <span style={{ width: 8, height: 8, borderRadius: "50%", background: color }} />{n} {label}
    </span>);
}

/* --- Dream loop ------------------------------------------------------------------- */
function DreamBody({ height }) {
  const { Button, Icon } = { ...window.PersonalAgentDesignSystem_94ad89, ...window.PA };
  const [running, setRunning] = React.useState(false);
  const [res, setRes] = React.useState(null);        // { report, detail }
  const [history, setHistory] = React.useState([]);
  const [err, setErr] = React.useState(null);

  const loadHistory = React.useCallback(() => {
    window.HMGFU.reports().then((d) => setHistory(d.reports || [])).catch(() => {});
  }, []);
  React.useEffect(() => { loadHistory(); }, [loadHistory]);

  const runDream = async () => {
    setRunning(true); setErr(null);
    try {
      const r = await window.HMGFU.dream();
      setRes(r);
      loadHistory();
      window.dispatchEvent(new CustomEvent("hmg-graph-changed"));   // refresh the hex/graph/layers
    } catch (e) { setErr(String(e.message || e)); }
    finally { setRunning(false); }
  };

  const d = res && res.detail;
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0 }}>
      <div style={{ padding: "10px 12px", borderBottom: "1px solid hsl(var(--border))" }}>
        <Button size="sm" onClick={runDream} disabled={running}
          leftIcon={<Icon name={running ? "loader" : "moon"} size={14} />} style={{ width: "100%" }}>
          {running ? "Dreaming — consolidating memory…" : "Run dream loop"}
        </Button>
        {err && <div style={{ fontSize: 11, color: "hsl(var(--destructive))", marginTop: 6 }}>{err}</div>}
      </div>
      <div style={{ flex: 1, overflowY: "auto", padding: "10px 12px" }}>
        {!res && !running && (
          <div style={{ fontSize: 12, color: "hsl(var(--muted-foreground))" }}>
            Run the dream loop to consolidate clusters into macros, form wormholes between distant
            analogies, resolve contradictions, and decay/promote memories.
          </div>)}
        {d && (
          <>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 5, marginBottom: 10 }}>
              {_statPill("macros", d.macros.length, _DREAM_COLORS.macro)}
              {_statPill("wormholes", d.wormholes.length, _DREAM_COLORS.wormhole)}
              {_statPill("contradictions", d.contradictions, _DREAM_COLORS.contradiction)}
              {_statPill("decayed", d.decayed, _DREAM_COLORS.decayed)}
              {_statPill("promoted", d.promoted, _DREAM_COLORS.promoted)}
            </div>
            {d.macros.length > 0 && <_Section title="Macros formed" color={_DREAM_COLORS.macro}
              items={d.macros.map((m) => "◈ " + m.title)} />}
            {d.wormholes.length > 0 && <_Section title="Wormholes formed" color={_DREAM_COLORS.wormhole}
              items={d.wormholes.map((w) => `${w.from}  ⟿  ${w.to}`)} />}
            {(res.report.insights || []).length > 0 && <_Section title="Insights" color="#d29922"
              items={res.report.insights.map((i) => "💡 " + i)} />}
          </>)}
        {history.length > 0 && (
          <div style={{ marginTop: 12 }}>
            <_Heading>Recent dreams</_Heading>
            {history.slice(0, 6).map((r, i) => (
              <div key={i} style={{ fontSize: 11, color: "hsl(var(--muted-foreground))", padding: "3px 0",
                borderTop: i ? "1px solid hsl(var(--border))" : "none" }}>
                <span style={{ fontFamily: "var(--font-mono)", color: "hsl(var(--primary))" }}>
                  {(r.created_at || "").slice(5, 16).replace("T", " ")}</span> — {r.summary}
              </div>))}
          </div>)}
      </div>
    </div>
  );
}

/* --- Grader (learning loop) ------------------------------------------------------- */
function GraderBody({ graded }) {
  const [feed, setFeed] = React.useState([]);
  const [openIdx, setOpenIdx] = React.useState(null);   // expanded turn row (P3)
  React.useEffect(() => {
    if (!graded) return;
    const g = graded;
    if (g.kind === "feedback") {                        // user-feedback tool grading (Phase 43/44)
      setFeed((f) => [{ feedback: true, at: g.at, verdict: g.verdict,
        tool_count: g.tool_count, tools: g.tools || [] }, ...f].slice(0, 40));
      return;
    }
    const cited = (g.memories_graded != null) ? g.memories_graded : 0;
    setFeed((f) => [{ at: g.at, score: g.turn_score, graded: cited, tools: g.tools_graded || 0,
      correction: g.correction, playbook: g.playbook_id, producer: g.producer, source: g.source,
      mem: g.memory_details || [], toolsDetail: g.tool_details || [] },
      ...f].slice(0, 40));
    setOpenIdx(0);                                       // newest turn opens expanded
  }, [graded]);

  if (!feed.length) return (
    <div style={{ padding: 14, fontSize: 12, color: "hsl(var(--muted-foreground))" }}>
      Send messages — after each turn the grader scores it and this feed shows the learning loop:
      memories reinforced, tools graded, corrections applied, playbooks extracted.
    </div>);
  return (
    <div style={{ padding: "8px 10px", overflowY: "auto", height: "100%" }}>
      {feed.map((g, i) => g.feedback ? (
        <div key={i} style={{ padding: "6px 8px", marginBottom: 6, borderRadius: 6, fontSize: 11.5,
          border: `1px solid ${g.verdict ? "hsl(var(--status-done))" : "hsl(var(--destructive))"}55`,
          background: (g.verdict ? "hsl(var(--status-done))" : "hsl(var(--destructive))") + "0f" }}>
          <div style={{ fontWeight: 600, color: g.verdict ? "hsl(var(--status-done))" : "hsl(var(--destructive))" }}>
            {g.verdict ? "👍 user liked it" : "👎 user said no"} — grading {g.tool_count} tool{g.tool_count === 1 ? "" : "s"} by feedback
          </div>
          {(g.tools || []).map((t, k) => (
            <div key={k} style={{ display: "flex", gap: 6, padding: "1px 0", fontSize: 10.5, color: "hsl(var(--muted-foreground))" }}>
              <span style={{ flex: 1, color: "hsl(var(--foreground))" }}>{t.tool}</span>
              <span style={{ fontFamily: "var(--font-mono)" }}>{t.before} → {t.after}</span>
            </div>))}
        </div>
      ) : (
        <div key={i} onClick={() => setOpenIdx(openIdx === i ? null : i)}
          style={{ padding: "6px 8px", marginBottom: 6, border: "1px solid hsl(var(--border))",
          borderRadius: 6, fontSize: 11.5, cursor: "pointer" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontFamily: "var(--font-mono)", fontWeight: 600,
              color: g.score >= 0.6 ? "hsl(var(--status-done))" : g.score != null ? "hsl(var(--warning))" : "hsl(var(--muted-foreground))" }}>
              {g.score != null ? "score " + Number(g.score).toFixed(2) : "graded"}</span>
            <span style={{ fontSize: 9.5, fontFamily: "var(--font-mono)", color: "hsl(var(--muted-foreground))" }}>
              {g.producer}{g.source ? "·" + g.source : ""}</span>
          </div>
          <div style={{ color: "hsl(var(--muted-foreground))", marginTop: 2 }}>
            {g.graded} memories reinforced · {g.tools} tools graded
            {g.correction ? " · ✎ correction applied" : ""}
            {g.playbook ? " · ✦ playbook extracted" : ""}
            <span style={{ float: "right", fontSize: 9 }}>{openIdx === i ? "▾" : "▸"}</span>
          </div>
          {openIdx === i && (g.mem.length > 0 || g.toolsDetail.length > 0) && (
            <div style={{ marginTop: 6, borderTop: "1px solid hsl(var(--border))", paddingTop: 5 }}>
              {g.mem.map((m, k) => (
                <div key={k} style={{ display: "flex", gap: 6, alignItems: "baseline", padding: "2px 0", fontSize: 10.5 }}>
                  <span style={{ fontFamily: "var(--font-mono)", fontSize: 8.5, minWidth: 42,
                    color: m.grade === "cited" ? "hsl(var(--status-done))" : m.grade === "implied" ? "hsl(var(--warning))" : "hsl(var(--muted-foreground))" }}>{m.grade}</span>
                  <span style={{ flex: 1, color: "hsl(var(--foreground))", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{m.title || m.id}</span>
                  <span style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "hsl(var(--muted-foreground))" }}>{m.before} → {m.after}</span>
                </div>))}
              {g.toolsDetail.map((t, k) => (
                <div key={"t" + k} style={{ display: "flex", gap: 6, padding: "2px 0", fontSize: 10.5 }}>
                  <span style={{ fontFamily: "var(--font-mono)", fontSize: 8.5, minWidth: 62, color: "hsl(var(--muted-foreground))" }}>nano: {t.helpful ? "helpful" : "not"}</span>
                  <span style={{ flex: 1 }}>{t.name}</span>
                  <span style={{ fontFamily: "var(--font-mono)", fontSize: 8.5, color: "hsl(var(--muted-foreground))" }}>observed (user grades)</span>
                </div>))}
            </div>)}
        </div>))}
    </div>
  );
}

function _Heading({ children }) {
  return <div style={{ fontSize: 9.5, fontWeight: 600, letterSpacing: "0.05em", textTransform: "uppercase",
    color: "hsl(var(--muted-foreground))", margin: "0 0 4px" }}>{children}</div>;
}
function _Section({ title, color, items }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <_Heading>{title}</_Heading>
      {items.map((t, i) => (
        <div key={i} style={{ fontSize: 11.5, color: "hsl(var(--foreground))", padding: "2px 0",
          borderLeft: `2px solid ${color}`, paddingLeft: 8, marginBottom: 2 }}>{t}</div>))}
    </div>);
}

window.DreamGraderWidgets = { DreamBody, GraderBody };
