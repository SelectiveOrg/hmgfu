/* Cowork - the "app" widget: a page the agent BUILT, served in a sandboxed frame, with the
   runtime faults it reported while it ran (95.75 P6). It lives apart from Canvas.jsx, which
   is at the frontend module ceiling. */
/* "app" widget: serves a built app (workspace html file, or a dev-server URL) in an iframe. */
function CoworkAppBody({ file, url }) {
  const { Icon } = window.PA;
  const [nonce, setNonce] = React.useState(0);
  /* 95.75 (P6): the served page reports its own runtime faults; show the user what the agent sees. */
  const [errs, setErrs] = React.useState([]);
  const [showErrs, setShowErrs] = React.useState(false);
  React.useEffect(() => {
    if (!file) return undefined;
    let alive = true;
    const poll = () => fetch(`/api/app-errors?file=${encodeURIComponent(file)}`)
      .then((r) => r.json()).then((d) => { if (alive) setErrs(d.errors || []); }).catch(() => {});
    poll();
    const t = setInterval(poll, 4000);
    return () => { alive = false; clearInterval(t); };
  }, [file, nonce]);
  const src = url || (file ? `/workspace-file?path=${encodeURIComponent(file)}&_=${nonce}` : null);
  if (!src) return <div style={{ padding: 14, fontSize: 12, color: "hsl(var(--muted-foreground))" }}>No app source (needs file or url).</div>;
  return (
    <div style={{ position: "relative", height: "100%" }}>
      <div style={{ position: "absolute", top: 4, right: 4, zIndex: 2, display: "flex", gap: 2 }}>
        <button title="Reload app" onClick={() => setNonce((n) => n + 1)}
          style={{ width: 22, height: 22, borderRadius: 4, border: "1px solid hsl(var(--border))", background: "hsl(var(--surface-2))", color: "hsl(var(--muted-foreground))", cursor: "pointer" }}>
          <Icon name="refresh-cw" size={11} />
        </button>
        <a href={src} target="_blank" rel="noreferrer" title="Open in a tab"
          style={{ width: 22, height: 22, borderRadius: 4, border: "1px solid hsl(var(--border))", background: "hsl(var(--surface-2))", color: "hsl(var(--muted-foreground))", display: "inline-flex", alignItems: "center", justifyContent: "center" }}>
          <Icon name="external-link" size={11} />
        </a>
      </div>
      {errs.length > 0 && (
        <button title="runtime errors this page reported" onClick={() => setShowErrs((v) => !v)}
          style={{ position: "absolute", top: 4, left: 4, zIndex: 2, height: 22, padding: "0 7px", borderRadius: 4,
            border: "1px solid hsl(var(--destructive, 0 70% 50%))", background: "hsl(var(--destructive, 0 70% 50%) / 0.12)",
            color: "hsl(var(--destructive, 0 70% 50%))", fontSize: 11, cursor: "pointer" }}>
          {errs.length} error{errs.length > 1 ? "s" : ""}
        </button>)}
      {showErrs && (
        <div style={{ position: "absolute", top: 30, left: 4, right: 4, zIndex: 3, maxHeight: "60%", overflowY: "auto",
          padding: 8, borderRadius: "var(--radius-sm)", border: "1px solid hsl(var(--border))",
          background: "hsl(var(--surface-2))", fontSize: 11, fontFamily: "var(--font-mono)" }}>
          {errs.map((e) => (
            <div key={e.id} style={{ padding: "3px 0", borderTop: "1px solid hsl(var(--border))", color: "hsl(var(--foreground))" }}>
              <span style={{ color: "hsl(var(--muted-foreground))" }}>{e.kind}{e.line ? ` · line ${e.line}` : ""}: </span>
              {e.message}
            </div>))}
          <div style={{ marginTop: 6, color: "hsl(var(--muted-foreground))" }}>The agent sees these on its next turn.</div>
        </div>)}
      <iframe src={src} title="app" sandbox="allow-scripts allow-forms allow-popups allow-same-origin"
        style={{ width: "100%", height: "100%", border: "none", background: "#fff" }} />
    </div>
  );
}
window.CoworkAppBody = CoworkAppBody;
