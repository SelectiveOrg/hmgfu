/* Cowork — Settings overlay: appearance, roles/models, grader, connectors, SYSTEM (restart/rebuild/tailscale). */
function CoworkSettings({ open, onClose, theme, onToggleTheme }) {
  const { IconButton, Badge, Button } = window.PersonalAgentDesignSystem_94ad89;
  const { Icon } = window.PA;
  const API = window.HMGFU;
  const { NumberRow, Toggle, RegFlag, Choice, selStyle } = window.SettingsRows;   // 77.6: rows split out (module ceiling); 84.3 Choice
  const [settings, setSettings] = React.useState(null);
  const [providers, setProviders] = React.useState(null);
  const [sys, setSys] = React.useState(null);
  const [reg, setReg] = React.useState(null);   // regulator status: observed/target + env-lock
  const [busy, setBusy] = React.useState("");
  const isDark = theme.indexOf("dark") >= 0;

  const load = React.useCallback(() => {
    API.getSettings().then((d) => { setSettings(d.settings); setReg(d.regulator || null); }).catch(() => {});
    API.providers().then(setProviders).catch(() => {});
    API.systemStatus().then(setSys).catch(() => {});
  }, []);
  React.useEffect(() => { if (open) load(); }, [open]);

  if (!open) return null;

  const patch = async (p) => {
    try { const d = await API.putSettings(p); setSettings(d.settings); if (d.regulator) setReg(d.regulator); }
    catch (e) { alert(e.message); }
  };
  const providerNames = providers ? Object.keys(providers.providers) : ["ollama"];

  const Section = ({ title, children }) => (
    <div style={{ marginBottom: 22 }}>
      <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: "0.05em", textTransform: "uppercase", color: "hsl(var(--muted-foreground))", marginBottom: 10 }}>{title}</div>
      {children}
    </div>
  );

  const doSystem = async (label, fn) => {
    setBusy(label);
    try { const r = await fn(); if (r && r.error) alert(r.error); else load(); }
    catch (e) { alert(e.message); }
    finally { setBusy(""); }
  };

  const ROLES = ["chat", "router", "nano", "dream", "grader", "embed"];   // 73.2: router role
  const tsServing = sys?.tailscale?.serving;

  return (
    <div onClick={onClose} style={{ position: "absolute", inset: 0, zIndex: 60, display: "flex", alignItems: "center", justifyContent: "center", background: "hsl(0 0% 0% / 0.5)", backdropFilter: "blur(3px)" }}>
      <div onClick={(e) => e.stopPropagation()} style={{ width: 540, maxWidth: "94%", maxHeight: "88%", overflow: "auto", borderRadius: "var(--radius-lg)", border: "1px solid hsl(var(--border))", background: "hsl(var(--popover))", boxShadow: "var(--shadow-xl)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "14px 16px", borderBottom: "1px solid hsl(var(--border))", position: "sticky", top: 0, background: "hsl(var(--popover))", zIndex: 2 }}>
          <Icon name="settings" size={16} color="hsl(var(--primary))" />
          <span style={{ flex: 1, fontSize: 15, fontWeight: 600, color: "hsl(var(--foreground))" }}>Settings</span>
          <IconButton size="sm" title="Close" onClick={onClose}><Icon name="x" size={16} /></IconButton>
        </div>

        <div style={{ padding: 16 }}>
          <Section title="Appearance">
            <div style={{ display: "flex", gap: 8 }}>
              {[{ id: "light", label: "Light", icon: "sun" }, { id: "dark", label: "Dark", icon: "moon" }].map((m) => {
                const active = (m.id === "dark") === isDark;
                return (
                  <button key={m.id} onClick={() => { if (!active) onToggleTheme(); }}
                    style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 8, padding: "10px", borderRadius: "var(--radius-md)", cursor: "pointer",
                      border: `1px solid ${active ? "hsl(var(--primary))" : "hsl(var(--border))"}`, background: active ? "hsl(var(--primary) / 0.1)" : "transparent",
                      color: active ? "hsl(var(--primary))" : "hsl(var(--muted-foreground))", fontSize: 13, fontWeight: 500, fontFamily: "var(--font-sans)" }}>
                    <Icon name={m.icon} size={15} />{m.label}
                  </button>
                );
              })}
            </div>
          </Section>

          {settings && providers && (
            <Section title="Models — per role">
              {ROLES.map((role) => (
                <div key={role} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                  {(() => {
                    const providerModels = ((providers.providers[settings[role + "_provider"]] || {}).models || []);
                    const roleProviders = role === "embed"
                      ? providerNames.filter((p) => providers.providers[p]?.embeddings !== false && p !== "anthropic")
                      : providerNames;
                    const current = settings[role + "_model"];
                    return <>
                  <span style={{ width: 58, fontSize: 12, color: "hsl(var(--muted-foreground))", textTransform: "capitalize" }}>{role}</span>
                  <select value={settings[role + "_provider"]} onChange={(e) => patch({ [role + "_provider"]: e.target.value })}
                    style={selStyle()}>
                    {roleProviders.map((p) => <option key={p} value={p}>{p}</option>)}
                  </select>
                  <select value={settings[role + "_model"]}
                    onChange={(e) => patch({ [role + "_model"]: e.target.value })}
                    style={{ ...selStyle(), flex: 1, fontFamily: "var(--font-mono)" }}>
                    {current && !providerModels.includes(current) && <option value={current}>{current} (current)</option>}
                    {providerModels.map((m) => <option key={m} value={m}>{m}</option>)}
                  </select>
                    </>;
                  })()}
                </div>
              ))}
            </Section>
          )}

          {settings && (
            <Section title="Nano workers">
              <Toggle label="Memory sensitizer (extraction nano)" value={settings.nano_sensitizer_enabled}
                onChange={(v) => patch({ nano_sensitizer_enabled: v })} />
              <Toggle label="Dream worker (summaries · analogies · insights)" value={settings.nano_dream_enabled}
                onChange={(v) => patch({ nano_dream_enabled: v })} />
              <Toggle label="Turn grader" value={settings.grader_enabled} onChange={(v) => patch({ grader_enabled: v })} />
              <Toggle label="Answer grounding gate (numbers/URLs must come from a tool result or memory)" value={settings.grounding_gate_enabled}
                onChange={(v) => patch({ grounding_gate_enabled: v })} />
              <Toggle label="Say-do gate (promises become actions or proposals; false 'I've updated' corrected)" value={settings.saydo_gate_enabled}
                onChange={(v) => patch({ saydo_gate_enabled: v })} />
              <Toggle label="Recall memory for each plan step (self-instructed recall)" value={settings.plan_step_recall}
                onChange={(v) => patch({ plan_step_recall: v })} />
              <div style={{ display: "flex", alignItems: "center", gap: 10, margin: "8px 0 2px" }}>
                <span style={{ flex: 1, fontSize: 13, color: "hsl(var(--foreground))" }}>Thinking mode</span>
                {["dynamic", "always", "off"].map((p) => (
                  <button key={p} onClick={() => patch({ thinking_mode: p })}
                    style={{ padding: "5px 10px", borderRadius: "var(--radius-md)", cursor: "pointer", fontSize: 12, textTransform: "capitalize",
                      border: `1px solid ${settings.thinking_mode === p ? "hsl(var(--primary))" : "hsl(var(--border))"}`,
                      background: settings.thinking_mode === p ? "hsl(var(--primary) / 0.1)" : "transparent",
                      color: settings.thinking_mode === p ? "hsl(var(--primary))" : "hsl(var(--muted-foreground))" }}>{p}</button>
                ))}
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 10, margin: "8px 0 2px" }}>
                <span style={{ flex: 1, fontSize: 13, color: "hsl(var(--foreground))" }}>Grader trained by</span>
                {["nano", "main"].map((p) => (
                  <button key={p} onClick={() => patch({ grader_producer: p })}
                    style={{ padding: "5px 12px", borderRadius: "var(--radius-md)", cursor: "pointer", fontSize: 12,
                      border: `1px solid ${settings.grader_producer === p ? "hsl(var(--primary))" : "hsl(var(--border))"}`,
                      background: settings.grader_producer === p ? "hsl(var(--primary) / 0.1)" : "transparent",
                      color: settings.grader_producer === p ? "hsl(var(--primary))" : "hsl(var(--muted-foreground))" }}>
                    {p === "nano" ? "Nano" : "Main LLM"}
                  </button>
                ))}
              </div>
              <div style={{ fontSize: 10, color: "hsl(var(--muted-foreground))", marginTop: 6 }}>
                Off = deterministic fallbacks (heuristic extraction, no dream insights). Nano models are set per role above.
              </div>
            </Section>
          )}

          {settings && (
            <Section title="Memory recall">
              <NumberRow label="Recalled memories per turn" value={settings.retrieval_limit} min={2} max={40}
                onCommit={(v) => patch({ retrieval_limit: v })} />
              <NumberRow label="Recalled memories on an aggregation question ('how many … in total'; 0 = same as above) (86.1)" value={settings.retrieval_limit_aggregate} min={0} max={50}
                onCommit={(v) => patch({ retrieval_limit_aggregate: v })} />
              <NumberRow label="Activation-score floor" value={settings.retrieval_min_score} min={0} max={0.9} step={0.05}
                onCommit={(v) => patch({ retrieval_min_score: v })} />
              <NumberRow label="Fu expansion depth" value={settings.expansion_depth} min={0} max={4}
                onCommit={(v) => patch({ expansion_depth: v })} />
              <Toggle label="Nano extraction after the reply (heuristic + router before it; the stored memory still gets the nano's fields) (80.2)" value={settings.nano_in_tail}
                onChange={(v) => patch({ nano_in_tail: v })} />
              <Toggle label="Pre-router — decide plain recall questions and fact statements without a model call (79.3)" value={settings.router_bypass_enabled}
                onChange={(v) => patch({ router_bypass_enabled: v })} />
              <Toggle label="Nearest-exemplar router — the turn's embedding decides the route when the labelled exemplars agree; the model router is the fallback (89.1)" value={settings.knn_router_enabled}
                onChange={(v) => patch({ knn_router_enabled: v })} />
              <NumberRow label="Exemplars that must agree (k) (89.1)" value={settings.knn_router_k} min={1} max={7} onCommit={(v) => patch({ knn_router_k: v })} />
              <NumberRow label="Minimum similarity to claim a route (89.1)" value={settings.knn_router_min_sim} min={0.5} max={0.99} step={0.01} onCommit={(v) => patch({ knn_router_min_sim: v })} />
              <Toggle label="Open-slot writes from the regex ('my X is Y' may mint an open key; off = closed slots only, open keys from the model mapper) (84.2)" value={settings.open_slot_regex_writes}
                onChange={(v) => patch({ open_slot_regex_writes: v })} />
              <Choice label="Model-backed fact writes (fallback = today's single-slot mapper before the reply; spans = span extractor after the reply, adds what the regex missed; off) (84.3)"
                value={settings.fact_mapper_mode} options={["fallback", "spans", "off"]} onChange={(v) => patch({ fact_mapper_mode: v })} />
              <Choice label="Model role for fact writes (84.3)" value={settings.fact_mapper_role} options={["nano", "chat"]}
                onChange={(v) => patch({ fact_mapper_role: v })} />
              <Toggle label="…and on those turns skip the nano extraction too (heuristic extraction; 2 calls per turn) (79.6)" value={settings.bypass_skips_nano}
                onChange={(v) => patch({ bypass_skips_nano: v })} />
              <NumberRow label="Excerpt per memory — chars of the query-matched span (0 = head cut, today)" value={settings.excerpt_max_chars} min={0} max={2000} step={40}
                onCommit={(v) => patch({ excerpt_max_chars: v })} />
              <Toggle label="Echo guard drops only restatements (off = every assistant memory on a user-fact question)" value={settings.echo_guard_scope === "echoes"}
                onChange={(v) => patch({ echo_guard_scope: v ? "echoes" : "all" })} />
              <NumberRow label="Context token budget" value={settings.token_budget} min={200} max={6000} step={100}
                onCommit={(v) => patch({ token_budget: v })} />
              <NumberRow label="Mini-dream every N turns (0 = off)" value={settings.mini_dream_every_n_turns} min={0} max={50}
                onCommit={(v) => patch({ mini_dream_every_n_turns: v })} />
              <NumberRow label="Tools offered per turn" value={settings.max_tools_per_turn} min={2} max={20}
                onCommit={(v) => patch({ max_tools_per_turn: v })} />
              <NumberRow label="Tools offered on a plain question" value={settings.question_max_tools} min={1} max={20}
                onCommit={(v) => patch({ question_max_tools: v })} />
              <NumberRow label="Tool rounds on a plain question" value={settings.question_max_iterations} min={1} max={20}
                onCommit={(v) => patch({ question_max_iterations: v })} />
              <NumberRow label="Recent turns injected verbatim (0 = recall only)" value={settings.recent_turns_window} min={0} max={12}
                onCommit={(v) => patch({ recent_turns_window: v })} />
            </Section>
          )}

          {settings && (   /* 77.6 — the 75.2 toggle was never in the UI (Rule 10); the alarm cadence lives next to it */
            <Section title="Prospective memory">
              <Toggle label="Reminders from the user's words (time / condition)" value={settings.prospective_enabled}
                onChange={(v) => patch({ prospective_enabled: v })} />
              <NumberRow label="Alarm ticker — check due reminders every N s (0 = idle)" value={settings.prospective_tick_s} min={0} max={600} step={5}
                onCommit={(v) => patch({ prospective_tick_s: v })} />
              <div style={{ fontSize: 10, color: "hsl(var(--muted-foreground))", marginTop: 6 }}>
                A reminder that comes due while no conversation is open fires on the ticker and shows as a bell pill; the next turn delivers it too.
              </div>
            </Section>
          )}

          {settings && (
            <Section title="Learning">
              <Toggle label="Playbook extraction" value={settings.playbook_extraction} onChange={(v) => patch({ playbook_extraction: v })} />
              <Toggle label="Tools as memory points" value={settings.tool_points_enabled} onChange={(v) => patch({ tool_points_enabled: v })} />
            </Section>
          )}

          {settings && (
            <Section title="Lifecycle · Regulator">
              <RegFlag label="Chat correction signal — strong perceiver" k="chat_correction_signal"
                settings={settings} reg={reg} onToggle={patch} />
              <RegFlag label="Regulator — lifecycle · absorbing corrections" k="regulator_enabled"
                settings={settings} reg={reg} onToggle={patch}
                confirmMsg="Enable the Regulator LIVE? It records ABSORBING correction signals in production and auto-engages the 50-turn observation window. Reversible by this same toggle." />
              {reg && reg.observe_target > 0 && (
                <div style={{ display: "flex", alignItems: "center", gap: 8, margin: "6px 0", padding: "6px 10px", borderRadius: "var(--radius-sm)", background: "hsl(var(--surface-2))", fontSize: 12, color: "hsl(var(--foreground))" }}>
                  <Icon name="eye" size={13} color="hsl(var(--primary))" />
                  <span style={{ flex: 1 }}>Observation window {reg.observed}/{reg.observe_target}</span>
                  <a href="/api/observation_log" target="_blank" rel="noreferrer" style={{ fontSize: 11, color: "hsl(var(--primary))", textDecoration: "none" }}>view log →</a>
                </div>
              )}
              <NumberRow label="Observation window — first N corrections (0 = off)" value={settings.observe_first_n} min={0} max={200}
                onCommit={(v) => patch({ observe_first_n: v })} />
              <div style={{ fontSize: 10, color: "hsl(var(--muted-foreground))", marginTop: 6 }}>
                Defaults OFF (production byte-identical). An <code>HMGFU_*</code> env var overrides the toggle (precedence: env wins). The Regulator is an absorbing signal in production — enabling requires confirmation.
              </div>
            </Section>
          )}

          <Section title="Connectors — MCP · CLI · API keys">
            <CoworkConnectors />
          </Section>

          {/* SYSTEM — user-requested: restart, rebuild, tailscale serve */}
          <Section title="System">
            <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
              <Button variant="outline" onClick={() => doSystem("restart", API.restart)} disabled={!!busy}
                leftIcon={<Icon name="rotate-cw" size={14} />} style={{ flex: 1 }}>
                {busy === "restart" ? "Restarting…" : "Restart"}
              </Button>
              <Button variant="outline" onClick={() => doSystem("rebuild", API.rebuild)} disabled={!!busy}
                leftIcon={<Icon name="hammer" size={14} />} style={{ flex: 1 }}>
                {busy === "rebuild" ? "Rebuilding…" : "Rebuild"}
              </Button>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6, padding: "10px 12px", borderRadius: "var(--radius-md)", border: "1px solid hsl(var(--border))", background: "hsl(var(--surface-2))" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <Icon name="globe-lock" size={16} color={tsServing ? "hsl(var(--status-done))" : "hsl(var(--muted-foreground))"} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "hsl(var(--foreground))" }}>Tailscale serve</div>
                  <div style={{ fontSize: 11, color: "hsl(var(--muted-foreground))" }}>
                    {sys?.tailscale?.running ? (tsServing ? "serving on your tailnet" : "connected · not serving")
                      : `not connected (${sys?.tailscale?.backend_state || "?"} — log in with tailscale up)`}
                  </div>
                </div>
                <Toggle value={!!tsServing} onChange={(v) => doSystem("tailscale", () => API.tailscale(v ? "on" : "off"))} />
              </div>
              {tsServing && sys?.tailscale?.url && (
                <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 8px", borderRadius: "var(--radius-sm)", background: "hsl(var(--background))", border: "1px solid hsl(var(--border))" }}>
                  <a href={sys.tailscale.url} target="_blank" rel="noreferrer"
                    style={{ flex: 1, fontSize: 12, fontFamily: "var(--font-mono)", color: "hsl(var(--primary))", textDecoration: "none", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {sys.tailscale.url}
                  </a>
                  <Button size="sm" variant="outline" style={{ height: 24, fontSize: 11 }}
                    onClick={() => { navigator.clipboard.writeText(sys.tailscale.url); }}
                    leftIcon={<Icon name="copy" size={12} />}>Copy</Button>
                </div>
              )}
            </div>
            {sys && <div style={{ fontSize: 10, color: "hsl(var(--muted-foreground))", marginTop: 8, fontFamily: "var(--font-mono)" }}>
              uptime {Math.round(sys.uptime_s)}s · pid {sys.pid} · py {sys.python}
            </div>}
          </Section>
        </div>
      </div>
    </div>
  );
}

window.CoworkSettings = CoworkSettings;
