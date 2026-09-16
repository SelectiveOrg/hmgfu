/* Cowork — transcript card renderers (extracted from Transcript to stay under the ceiling). */

/* Collapsible group of execution tools (PA3 tool-group pattern): one card, "N tools",
   expands to the individual ToolCallBlocks. */
function ToolGroupCard({ entries, streaming }) {
  const { ToolCallBlock, Pill } = window.PersonalAgentDesignSystem_94ad89;
  const { Icon } = window.PA;
  const [open, setOpen] = React.useState(false);
  const running = entries.some((e) => e.status === "running");
  const failed = entries.filter((e) => e.status === "error").length;
  const n = entries.length;
  const tone = failed ? "hsl(var(--destructive))" : running ? "hsl(var(--warning))" : "hsl(var(--status-done))";
  return (
    <div style={{ border: "1px solid hsl(var(--border))", borderRadius: "var(--radius-md)", background: "hsl(var(--surface-2))", overflow: "hidden" }}>
      <button onClick={() => setOpen((o) => !o)} style={{ display: "flex", alignItems: "center", gap: 8, width: "100%",
        padding: "7px 10px", border: "none", background: "transparent", cursor: "pointer",
        color: "hsl(var(--foreground))", fontSize: 12, fontFamily: "var(--font-mono)" }}>
        <Icon name="terminal" size={13} color={tone} />
        <span style={{ flex: 1, textAlign: "left" }}>
          {running ? "running" : "ran"} {n} tool{n === 1 ? "" : "s"}
          {failed ? ` · ${failed} failed` : ""}
        </span>
        <span style={{ fontSize: 10, color: "hsl(var(--muted-foreground))" }}>
          {entries.map((e) => e.name).slice(0, 4).join(" · ")}{n > 4 ? " …" : ""}
        </span>
        <Icon name={open ? "chevron-up" : "chevron-down"} size={13} color="hsl(var(--muted-foreground))" />
      </button>
      {open && (
        <div style={{ display: "flex", flexDirection: "column", gap: 4, padding: "0 8px 8px" }}>
          {entries.map((e, i) => (
            <ToolCallBlock key={i} command={e.command} name={e.name} status={e.status}
              exitCode={e.exitCode} output={e.output} defaultOpen={e.status === "error"} />
          ))}
        </div>
      )}
    </div>
  );
}

/* Thinking card: always a COLLAPSIBLE reasoning block (never a plain streaming bubble). */
function ThinkingCard({ text }) {
  const { Icon } = window.PA;
  const [open, setOpen] = React.useState(false);
  return (
    <div style={{ maxWidth: "100%" }}>
      <button onClick={() => setOpen((o) => !o)} style={{ display: "inline-flex", alignItems: "center", gap: 6,
        height: 24, padding: "0 10px", border: "1px solid hsl(var(--border))", borderRadius: 999,
        background: "hsl(var(--surface-2))", color: "var(--thinking, hsl(var(--muted-foreground)))",
        fontSize: 12, cursor: "pointer" }}>
        <Icon name="brain" size={12} /> thought for a moment
        <Icon name={open ? "chevron-up" : "chevron-down"} size={12} />
      </button>
      {open && (
        <div style={{ marginTop: 6, padding: "8px 11px", border: "1px solid hsl(var(--border))",
          borderRadius: "var(--radius-md)", background: "hsl(var(--surface-2))", fontSize: 12.5,
          color: "hsl(var(--muted-foreground))", whiteSpace: "pre-wrap", lineHeight: 1.5 }}>{text}</div>
      )}
    </div>
  );
}

window.ToolGroupCard = ToolGroupCard;
window.ThinkingCard = ThinkingCard;

/* 69.6: one line of verification feedback — what the harness did with the model's claims / values
   (say-do: proposal, correction, re-ask; grounding: values the reply could not trace). */
function verifyLabel(kind, r) {
  if (kind === "grounding") {
    const u = r.unverified || r.claims || [];
    return u.length ? `unverified: ${u.slice(0, 4).join(", ")}` : (r.ok === false ? "grounding check failed" : "");
  }
  const map = { proposed: "asked before acting", proposed_unconfirmed: "asked before acting", proposed_plan: "plan proposed",
    executed_intent: "promise executed", corrected_claim: "claim corrected", unfulfilled_plan_step: "plan step not done" };
  const bits = [];
  if (r.action && map[r.action]) bits.push(map[r.action]);
  if (r.false_exec_claim) bits.push(`unsupported claim${(r.unsupported_claims || []).length ? ": " + r.unsupported_claims.join(", ") : ""}`);
  return bits.join(" · ");
}
function VerifyPill({ kind, report }) {
  const { Pill } = window.PersonalAgentDesignSystem_94ad89;
  const { Icon } = window.PA;
  const text = verifyLabel(kind, report || {});
  if (!text) return null;
  const warn = report && (report.ok === false || report.false_exec_claim || (report.unverified || []).length);
  return (
    <div style={{ padding: "2px 16px" }}>
      <Pill icon={<Icon name={warn ? "alert-triangle" : "check"} size={12}
                        color={warn ? "hsl(var(--warning))" : "hsl(var(--status-done))"} />}>{text}</Pill>
    </div>
  );
}
window.VerifyPill = VerifyPill;
window.verifyLabel = verifyLabel;


/* 70.7 (M1.8): the plan card says WHO authorized the plan, before and after a restore. */
function planTitle(plan) {
  const a = plan.authorization;
  const st = plan.status || "active";
  if (st === "proposed") return `${plan.title} · awaiting your approval`;
  if (st === "abandoned") return `${plan.title} · cancelled`;
  if (st === "partial") return `${plan.title} · partial — some steps failed`;
  if (a && a.origin === "user_approval") return `${plan.title} · approved by you`;
  if (a && a.origin === "user_request") return `${plan.title} · requested by you`;
  if (st === "active") return `${plan.title} · unapproved — confirm first`;
  return `${plan.title} · ${st}`;
}
window.planTitle = planTitle;


/* Grader card — turn score + producer + counts (PA3 turn_classification). */
function GradePill({ grade }) {
  const { Icon } = window.PA;
  const score = typeof grade.turn_score === "number" ? grade.turn_score : null;
  const tone = score == null ? "var(--muted-foreground)" : (score >= 0.6 ? "hsl(var(--status-done))" : score >= 0.35 ? "hsl(var(--warning))" : "hsl(var(--destructive))");
  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: 8, height: 24, padding: "0 10px", border: "1px solid hsl(var(--border))", borderRadius: 999, background: "hsl(var(--surface-2))", fontSize: 11, fontFamily: "var(--font-mono)", color: "hsl(var(--muted-foreground))" }}>
      <Icon name="graduation-cap" size={12} color={tone} />
      graded by {grade.producer}
      {score != null && <span style={{ color: tone }}>· {(score * 100).toFixed(0)}%</span>}
      <span>· {grade.memories_graded} mem</span>
      {grade.playbook_id && <span title="playbook learned">· ✦ learned</span>}
      {grade.correction && <span style={{ color: "hsl(var(--warning))" }}>· correction</span>}
    </div>
  );
}
window.GradePill = GradePill;


/* 73.0 — where the turn's time went: total, time-to-reply, model calls by role, tokens. Data from `turn_timings`
   (live) or metadata.timings (restore). Display only — the numbers come from hmgfu/turn_timing.py. */
function fmtS(ms) { return ms == null ? "—" : (ms / 1000).toFixed(ms >= 10000 ? 0 : 1) + " s"; }
function TimingPill({ timings }) {
  const { Pill } = window.PersonalAgentDesignSystem_94ad89;
  const { Icon } = window.PA;
  const t = timings || {};
  if (t.total_ms == null) return null;
  const calls = t.calls || {};
  const tok = t.tokens || {};
  const parts = [`${fmtS(t.total_ms)} total`, `reply ${fmtS(t.reply_ms)}`,
    `${t.model_calls ?? 0} calls (chat ${calls.chat ?? 0} · nano ${calls.nano ?? 0} · embed ${calls.embed ?? 0})`];
  if ((tok.prompt || 0) + (tok.eval || 0) > 0) parts.push(`${((tok.prompt || 0) + (tok.eval || 0)).toLocaleString()} tok`);
  const slow = t.reply_ms != null && t.reply_ms > 12000;
  const title = Object.entries(t.stages || {}).map(([k, v]) => `${k} ${fmtS(v)}`).join(" · ");
  return (
    <div style={{ padding: "2px 16px" }} title={title}>
      <Pill icon={<Icon name="timer" size={12} color={slow ? "hsl(var(--warning))" : "hsl(var(--muted-foreground))"} />}>{parts.join(" · ")}</Pill>
    </div>
  );
}
window.TimingPill = TimingPill;


/* 75.1 — procedural memory offered this turn: runbooks (proven step sequences from earlier plans) whose task matched
   the request. Data from the `runbooks` event (hmgfu/runbooks.py). Display only. */
function RunbookPill({ items }) {
  const { Pill } = window.PersonalAgentDesignSystem_94ad89;
  const { Icon } = window.PA;
  const list = items || [];
  if (!list.length) return null;
  const text = list.map((r) => `${r.title} (${r.outcome || ""}${r.match != null ? ` · ${Math.round(r.match * 100)}%` : ""})`).join(" · ");
  return (
    <div style={{ padding: "2px 16px" }} title="Runbooks from earlier executed plans, offered beside the tools">
      <Pill icon={<Icon name="list-checks" size={12} color="hsl(var(--muted-foreground))" />}>{`runbook: ${text}`}</Pill>
    </div>
  );
}
window.RunbookPill = RunbookPill;


/* 75.2 — prospective memory: a reminder was set / fired / cancelled this turn (events prospective_set / _fired /
   _cancelled from hmgfu/prospective.py). Display only. */
function ProspectivePill({ mode, items }) {
  const { Pill } = window.PersonalAgentDesignSystem_94ad89;
  const { Icon } = window.PA;
  const list = items || [];
  if (!list.length) return null;
  const label = mode === "fired" ? "reminder due" : mode === "cancelled" ? "reminder cancelled" : "reminder set";
  const text = list.map((r) => `${r.text}${r.due ? ` · ${String(r.due).slice(0, 16)}` : r.condition ? ` · when: ${r.condition}` : ""}`).join(" · ");
  const color = mode === "fired" ? "hsl(var(--warning))" : "hsl(var(--muted-foreground))";
  return (
    <div style={{ padding: "2px 16px" }} title="Prospective memory — from the user's own words, deterministic">
      <Pill icon={<Icon name="bell" size={12} color={color} />}>{`${label}: ${text}`}</Pill>
    </div>
  );
}
window.ProspectivePill = ProspectivePill;
