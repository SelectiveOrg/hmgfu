/* Cowork — Connectors: ONE card per provider (PA3 model). A provider's services are the
   scopes ONE connection grants (listed inside as chips), NOT connected individually. */
function CoworkConnectors() {
  const { Badge, Button, IconButton } = window.PersonalAgentDesignSystem_94ad89;
  const { Icon } = window.PA;
  const API = window.HMGFU;
  const [items, setItems] = React.useState([]);
  const [adding, setAdding] = React.useState(false);
  const [form, setForm] = React.useState({ name: "", auth: "mcp", display: "", services: "", config: "" });
  const [keyFor, setKeyFor] = React.useState(null);
  const [keyVal, setKeyVal] = React.useState("");
  const [busy, setBusy] = React.useState("");
  const [googleAuth, setGoogleAuth] = React.useState(null);

  const load = () => API.connectors().then((d) => setItems(d.connectors || [])).catch(() => {});
  React.useEffect(() => { load(); }, []);

  const submitAdd = async () => {
    try {
      let config = {};
      if (form.auth === "mcp") config = { command: form.config.trim().split(/\s+/) };
      if (form.auth === "cli") config = { cli: form.config.trim() };
      if (form.auth === "api_key") config = { env: form.config.split(",").map((s) => s.trim()).filter(Boolean) };
      const services = form.services.split(",").map((s) => s.trim()).filter(Boolean);
      await API.addConnector({ name: form.name, display: form.display || form.name, auth: form.auth, services, config });
      setAdding(false); setForm({ name: "", auth: "mcp", display: "", services: "", config: "" });
      load();
    } catch (e) { alert(e.message); }
  };

  const saveKey = async (name) => {
    try { await API.connectorSecret(name, { api_key: keyVal }); setKeyFor(null); setKeyVal(""); load(); }
    catch (e) { alert(e.message); }
  };
  const connect = async (name) => {
    setBusy(name);
    try {
      const r = await API.connectorConnect(name);
      if (name === "google" && r.auth_url) {
        setGoogleAuth({ url: r.auth_url, redirect: "" });
        window.open(r.auth_url, "_blank", "noopener,noreferrer");
      } else alert(`Connected ${name}: ${r.count} tools registered`);
      load();
    }
    catch (e) { alert("Connect failed: " + e.message); }
    finally { setBusy(""); }
  };
  const finishGoogle = async () => {
    if (!googleAuth?.redirect.trim()) return;
    setBusy("google");
    try {
      await API.connectorFinish("google", googleAuth.redirect.trim());
      setGoogleAuth(null); alert("Google connected"); load();
    } catch (e) { alert("Google authorization failed: " + e.message); }
    finally { setBusy(""); }
  };

  const AUTH_TONE = { mcp: "hsl(var(--primary))", cli: "hsl(var(--warning))", api_key: "hsl(var(--memory))", oauth: "hsl(var(--accent-foreground, var(--primary)))" };
  const AUTH_LABEL = { mcp: "MCP", cli: "CLI", api_key: "API KEY", oauth: "OAUTH" };
  const inp = { height: 30, padding: "0 8px", fontSize: 12, borderRadius: "var(--radius-sm)",
    border: "1px solid hsl(var(--border))", background: "hsl(var(--background))",
    color: "hsl(var(--foreground))", fontFamily: "var(--font-mono)", outline: "none" };

  // one global connect control per provider (its services come with it)
  // M-09: an MCP provider is "connected" ONLY when a live process exists (c.connected).
  // Merely having a command (configured) must still show a Connect button. api_key/cli are
  // usable as soon as they are configured, so "configured" counts as connected for them.
  const usable = (c) => c.connected || (c.configured && c.auth !== "mcp");
  const keyInput = (c) => (
    <span style={{ display: "flex", gap: 4 }}>
      <input style={{ ...inp, width: 150, height: 28 }} type="password" placeholder="API key / token" value={keyVal}
        onChange={(e) => setKeyVal(e.target.value)} autoFocus />
      <Button size="sm" style={{ height: 28, fontSize: 12 }} onClick={() => saveKey(c.kind)}>Save</Button>
    </span>);

  const connectControl = (c) => {
    if (c.kind === "google" && googleAuth) return (
      <span style={{ display: "flex", gap: 4, alignItems: "center" }}>
        <a href={googleAuth.url} target="_blank" rel="noreferrer" style={{ fontSize: 11, color: "hsl(var(--primary))" }}>Open Google</a>
        <input style={{ ...inp, width: 170, height: 28 }} placeholder="paste redirected URL"
          value={googleAuth.redirect} onChange={(e) => setGoogleAuth({ ...googleAuth, redirect: e.target.value })} />
        <Button size="sm" style={{ height: 28, fontSize: 12 }} onClick={finishGoogle}
          disabled={busy === "google" || !googleAuth.redirect.trim()}>Finish</Button>
      </span>);
    if (c.kind === "google") return (
      <Button size="sm" variant="outline" style={{ height: 28, fontSize: 12 }}
        onClick={() => connect(c.kind)} disabled={busy === c.kind}>
        {busy === c.kind ? "…" : "Connect"}
      </Button>);
    /* 95.76: a provider that takes a key can ALWAYS be given a new one. The green badge used to
       replace the input, so a key that had expired, changed, or could not be read here was
       unchangeable from the panel. */
    if (usable(c)) return (
      <span style={{ display: "flex", gap: 4, alignItems: "center" }}>
        <Badge tone="emerald">connected</Badge>
        {c.auth === "api_key" && (keyFor === c.kind ? keyInput(c)
          : <Button size="sm" variant="outline" style={{ height: 28, fontSize: 12 }}
              onClick={() => setKeyFor(c.kind)}>Change key</Button>)}
      </span>);
    if (c.auth === "mcp") return (
      <Button size="sm" variant="outline" style={{ height: 28, fontSize: 12 }}
        onClick={() => connect(c.kind)} disabled={busy === c.kind}>
        {busy === c.kind ? "…" : "Connect"}
      </Button>);
    if (c.auth === "cli") return <Badge tone="neutral">install {c.kind}</Badge>;
    // api_key / oauth → paste one credential for the whole provider
    return keyFor === c.kind ? keyInput(c)
      : <Button size="sm" variant="outline" style={{ height: 28, fontSize: 12 }}
          onClick={() => setKeyFor(c.kind)}>{c.source === "unreadable" ? "Set key again" : "Connect"}</Button>;
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 8 }}>
        <Button size="sm" variant="outline" onClick={() => setAdding((v) => !v)}
          leftIcon={<Icon name="plus" size={13} />} style={{ height: 28, fontSize: 12 }}>Add provider</Button>
      </div>
      {adding && (
        <div style={{ display: "flex", flexDirection: "column", gap: 6, padding: 10, marginBottom: 10,
          border: "1px solid hsl(var(--primary) / 0.4)", borderRadius: "var(--radius-md)", background: "hsl(var(--surface-2))" }}>
          <div style={{ display: "flex", gap: 6 }}>
            {["mcp", "cli", "api_key"].map((k) => (
              <button key={k} onClick={() => setForm((f) => ({ ...f, auth: k }))}
                style={{ flex: 1, padding: "5px 0", borderRadius: "var(--radius-sm)", cursor: "pointer", fontSize: 11, textTransform: "uppercase",
                  border: `1px solid ${form.auth === k ? "hsl(var(--primary))" : "hsl(var(--border))"}`,
                  background: form.auth === k ? "hsl(var(--primary) / 0.1)" : "transparent",
                  color: form.auth === k ? "hsl(var(--primary))" : "hsl(var(--muted-foreground))" }}>{AUTH_LABEL[k]}</button>
            ))}
          </div>
          <input style={inp} placeholder="provider name (e.g. linear)" value={form.name}
            onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
          <input style={inp} placeholder="services, comma-separated (e.g. Issues, Projects)" value={form.services}
            onChange={(e) => setForm((f) => ({ ...f, services: e.target.value }))} />
          <input style={inp} placeholder={
            form.auth === "mcp" ? "command (e.g. npx -y @modelcontextprotocol/server-x)"
            : form.auth === "cli" ? "binary (e.g. gh)" : "env var names, comma-separated"}
            value={form.config} onChange={(e) => setForm((f) => ({ ...f, config: e.target.value }))} />
          <Button size="sm" onClick={submitAdd} disabled={!form.name || !form.config}
            style={{ height: 28, fontSize: 12 }}>Save provider</Button>
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {items.map((c) => (
          <div key={c.kind} style={{ borderRadius: "var(--radius-md)", border: "1px solid hsl(var(--border))", background: "hsl(var(--surface-2))", padding: "10px 12px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <Icon name={providerIcon(c.kind)} size={16} color="hsl(var(--foreground))" />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: "hsl(var(--foreground))" }}>{c.display}</span>
                  <span style={{ fontSize: 8.5, fontWeight: 700, color: AUTH_TONE[c.auth],
                    border: `1px solid ${AUTH_TONE[c.auth]}`, borderRadius: 4, padding: "0 4px" }}>{AUTH_LABEL[c.auth]}</span>
                </div>
                <div style={{ fontSize: 10, color: c.source === "unreadable" ? "hsl(var(--destructive, 0 70% 50%))" : "hsl(var(--muted-foreground))" }}>
                  {c.source === "unreadable" ? "a key is stored but cannot be read on this machine — enter it again"
                    : c.source ? "via " + c.source : c.category}</div>
              </div>
              {connectControl(c)}
              {!c.builtin && (
                <IconButton size="sm" title="Remove" onClick={async () => { await API.removeConnector(c.kind); load(); }}>
                  <Icon name="x" size={13} />
                </IconButton>
              )}
            </div>
            {/* services this ONE connection grants (informational scope chips, not actions) */}
            {c.services && c.services.length > 0 && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 8, paddingLeft: 26 }}>
                {c.services.map((s) => (
                  <span key={s} style={{ display: "inline-flex", alignItems: "center", gap: 3, fontSize: 10,
                    color: usable(c) ? "hsl(var(--status-done))" : "hsl(var(--muted-foreground))",
                    border: "1px solid hsl(var(--border))", borderRadius: 999, padding: "1px 7px" }}>
                    {usable(c) && <Icon name="check" size={9} />} {s}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function providerIcon(kind) {
  return { google: "mail", meta: "message-circle", github: "github", slack: "slack",
    notion: "file-text", tailscale: "globe-lock", brave: "globe", openai: "sparkles",
    anthropic: "sparkles", filesystem: "folder" }[kind] || "plug";
}
window.CoworkConnectors = CoworkConnectors;
