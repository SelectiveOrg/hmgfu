/* Cowork ↔ HMG-Fu backend client: REST + one WebSocket turn stream. */
(function () {
  const TOKEN_KEY = "hmgfu_token";
  const base = "";

  function token() { return localStorage.getItem(TOKEN_KEY) || ""; }
  function setToken(t) { localStorage.setItem(TOKEN_KEY, t || ""); }

  async function req(method, path, body) {
    const headers = { "Content-Type": "application/json" };
    const t = token();
    if (t) headers["Authorization"] = "Bearer " + t;
    const res = await fetch(base + path, {
      method, headers, body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) throw new Error((await res.text()) || res.statusText);
    return res.json();
  }

  const API = {
    setToken, token,
    health: () => req("GET", "/api/health"),
    // sessions
    sessions: () => req("GET", "/api/sessions"),
    createSession: (title) => req("POST", "/api/sessions", { title: title || "New session" }),
    history: (id) => req("GET", `/api/sessions/${id}/history`),
    deleteWidget: (sid, wid) => req("DELETE", `/api/sessions/${sid}/widgets/${wid}`),
    upsertWidget: (sid, w) => req("PUT", `/api/sessions/${sid}/widgets`, w),
    renameSession: (id, title) => req("PATCH", `/api/sessions/${id}`, { title }),
    setGroup: (id, group) => req("PATCH", `/api/sessions/${id}`, { group }),
    deleteSession: (id) => req("DELETE", `/api/sessions/${id}`),
    // memory
    memorySearch: (q, limit) => req("GET", `/api/memory/search?q=${encodeURIComponent(q)}&limit=${limit || 12}`),
    memoryTimeline: (limit) => req("GET", `/api/memory/timeline?limit=${limit || 50}`),
      graphViz: (cap, root, frontier, roots) => req("GET", `/api/graph/viz?cap=${cap || 220}${root ? "&root=" + encodeURIComponent(root) : ""}${frontier ? "&frontier=1" : ""}${roots ? "&roots=1" : ""}`),
    // tools / skills / providers / settings / connectors
    tools: () => req("GET", "/api/tools"),
    skills: () => req("GET", "/api/skills"),
    providers: () => req("GET", "/api/providers"),
    getSettings: () => req("GET", "/api/settings"),
    putSettings: (patch) => req("PUT", "/api/settings", patch),
    connectors: () => req("GET", "/api/connectors"),
    addConnector: (c) => req("POST", "/api/connectors", c),
    removeConnector: (name) => req("DELETE", `/api/connectors/${name}`),
    connectorSecret: (name, secret) => req("POST", `/api/connectors/${name}/secret`, { secret }),
    connectorConnect: (name) => req("POST", `/api/connectors/${name}/connect`),
    connectorFinish: (name, redirect_url) => req("POST", `/api/connectors/${name}/connect/finish`, { redirect_url }),
    dream: () => req("POST", "/api/dream"),
    reports: () => req("GET", "/api/reports"),
    directives: () => req("GET", "/api/directives"),
    prospectiveNotifications: () => req("GET", "/api/prospective/notifications"),          // 77.6
    ackProspective: (ids) => req("POST", "/api/prospective/notifications/ack", { ids }),  // 77.6
    facts: () => req("GET", "/api/facts"),
    now: () => req("GET", "/api/now"),
    // system
    systemStatus: () => req("GET", "/api/system/status"),
    projects: () => req("GET", "/api/system/projects"),
    restart: () => req("POST", "/api/system/restart"),
    rebuild: () => req("POST", "/api/system/rebuild"),
    tailscale: (action) => req("POST", "/api/system/tailscale", { action }),

    /* Open a chat turn over WS. Calls onEvent for each streamed event.
       Returns a promise that resolves on the 'done' event; the socket stays open until 'turn_end' so the
       events the asynchronous tail emits afterwards (grade, turn_timings) still reach this turn (73.4). */
    chat(message, sessionId, onEvent) {
      return new Promise((resolve, reject) => {
        const proto = location.protocol === "https:" ? "wss" : "ws";
        const t = token();
        const url = `${proto}://${location.host}/ws${t ? "?token=" + encodeURIComponent(t) : ""}`;
        const ws = new WebSocket(url);
        let done = null;
        ws.onopen = () => ws.send(JSON.stringify({ type: "chat", message, session_id: sessionId }));
        ws.onmessage = (e) => {
          let ev; try { ev = JSON.parse(e.data); } catch { return; }
          if (ev.type === "done") { done = ev; onEvent(ev); resolve(done); }   // 73.4: the reply is final here…
          else if (ev.type === "turn_end") { ws.close(); }                      // …but late grade/timings still arrive until the tail ends
          else if (ev.type === "error") { onEvent(ev); }
          else onEvent(ev);
        };
        ws.onerror = () => reject(new Error("websocket error"));
        ws.onclose = () => resolve(done);
      });
    },
  };
  window.HMGFU = API;
})();
