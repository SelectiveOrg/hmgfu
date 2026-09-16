/* Cowork — Settings ROW helpers (77.6 split at the 300-line module ceiling): numeric adjuster, toggle, env-lockable
   feature flag, select style. Behaviour unchanged; Settings.jsx reads them from window.SettingsRows. */
/* Numeric adjuster row: - value + with direct input; commits on change. */
function NumberRow({ label, value, min, max, step = 1, onCommit }) {
  const [v, setV] = React.useState(value);
  React.useEffect(() => setV(value), [value]);
  const clamp = (x) => Math.min(max, Math.max(min, x));
  const commit = (x) => { const c = clamp(step < 1 ? Math.round(x * 100) / 100 : Math.round(x)); setV(c); onCommit(c); };
  const btn = { width: 24, height: 24, borderRadius: "var(--radius-sm)", border: "1px solid hsl(var(--border))",
    background: "hsl(var(--surface-2))", color: "hsl(var(--foreground))", cursor: "pointer", fontSize: 13 };
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "4px 0" }}>
      <span style={{ flex: 1, fontSize: 13, color: "hsl(var(--foreground))" }}>{label}</span>
      <button style={btn} onClick={() => commit((Number(v) || 0) - step)}>−</button>
      <input value={v} onChange={(e) => setV(e.target.value)}
        onBlur={() => commit(Number(v) || min)}
        onKeyDown={(e) => { if (e.key === "Enter") commit(Number(v) || min); }}
        style={{ width: 56, height: 24, textAlign: "center", fontSize: 12, fontFamily: "var(--font-mono)",
          borderRadius: "var(--radius-sm)", border: "1px solid hsl(var(--border))",
          background: "hsl(var(--background))", color: "hsl(var(--foreground))", outline: "none" }} />
      <button style={btn} onClick={() => commit((Number(v) || 0) + step)}>+</button>
    </div>
  );
}

function Toggle({ label, value, onChange }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "4px 0" }}>
      {label && <span style={{ flex: 1, fontSize: 13, color: "hsl(var(--foreground))" }}>{label}</span>}
      <button onClick={() => onChange(!value)} style={{ width: 40, height: 22, borderRadius: 999, border: "none", cursor: "pointer", position: "relative",
        background: value ? "hsl(var(--primary))" : "hsl(var(--surface-3))", transition: "background .15s" }}>
        <span style={{ position: "absolute", top: 2, left: value ? 20 : 2, height: 18, width: 18, borderRadius: 999, background: "#fff", transition: "left .15s" }} />
      </button>
    </div>
  );
}
/* A feature-flag row: env-locked → shows "env" (env wins, no toggle); else a Toggle with an optional
   confirmation (the Regulator is an absorbing signal in production). */
function RegFlag({ label, k, settings, reg, confirmMsg, onToggle }) {
  const locked = reg && reg.env_locked && reg.env_locked[k];
  const onChange = (v) => { if (v && confirmMsg && !window.confirm(confirmMsg)) return; onToggle({ [k]: v }); };
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "4px 0" }}>
      <span style={{ flex: 1, fontSize: 13, color: "hsl(var(--foreground))" }}>{label}
        {locked && <span style={{ fontSize: 10, color: "hsl(var(--muted-foreground))", marginLeft: 6 }}>· env-locked</span>}</span>
      {locked
        ? <span style={{ fontSize: 11, color: "hsl(var(--muted-foreground))", fontFamily: "var(--font-mono)" }}>env</span>
        : <Toggle value={!!settings[k]} onChange={onChange} />}
    </div>
  );
}
function selStyle() {
  return { height: 30, padding: "0 8px", fontSize: 12, borderRadius: "var(--radius-sm)", border: "1px solid hsl(var(--border))",
    background: "hsl(var(--background))", color: "hsl(var(--foreground))", fontFamily: "var(--font-sans)", outline: "none" };
}
/* 84.3: a fixed-choice row for enum settings (fact_mapper_mode, fact_mapper_role). */
function Choice({ label, value, options, onChange }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "4px 0" }}>
      <span style={{ flex: 1, fontSize: 13, color: "hsl(var(--foreground))" }}>{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)} style={selStyle()}>
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </div>
  );
}
window.SettingsRows = { NumberRow, Toggle, RegFlag, Choice, selStyle };
