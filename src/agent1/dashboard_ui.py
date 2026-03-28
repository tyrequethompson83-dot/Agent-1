from __future__ import annotations


def _dashboard_css() -> str:
    return """
:root {
  --bg: #0a0f19;
  --bg-alt: #10182a;
  --panel: rgba(17, 24, 39, 0.9);
  --panel-soft: rgba(21, 32, 55, 0.84);
  --panel-strong: #121d31;
  --line: rgba(120, 142, 177, 0.18);
  --line-strong: rgba(120, 142, 177, 0.3);
  --ink: #edf3ff;
  --muted: #8da2c8;
  --accent: #ff6b5f;
  --accent-2: #4cb8ff;
  --accent-soft: rgba(255, 107, 95, 0.14);
  --ok: #35d08a;
  --warn: #ffb85c;
  --fail: #ff6d6d;
  --shadow: 0 22px 50px rgba(0, 0, 0, 0.28);
}

* { box-sizing: border-box; }
html, body { height: 100%; }
body {
  margin: 0;
  font-family: Aptos, "Segoe UI Variable", "Trebuchet MS", sans-serif;
  background:
    radial-gradient(circle at top left, rgba(76, 184, 255, 0.16), transparent 26%),
    radial-gradient(circle at top right, rgba(255, 107, 95, 0.14), transparent 24%),
    linear-gradient(180deg, #09101b 0%, #0d1421 100%);
  color: var(--ink);
}

button, input, textarea, select {
  font: inherit;
}

.app-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 250px minmax(0, 1fr);
}

.sidebar {
  background: rgba(7, 12, 22, 0.92);
  border-right: 1px solid var(--line);
  padding: 24px 18px;
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.brand {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.brand-kicker {
  font-size: 11px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--accent);
}

.brand-title {
  font-size: 24px;
  font-weight: 700;
}

.brand-copy {
  color: var(--muted);
  font-size: 13px;
  line-height: 1.5;
}

.nav-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.nav-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  color: #6d83ab;
  padding: 0 8px;
}

.nav-btn {
  width: 100%;
  border: 1px solid transparent;
  background: transparent;
  color: #c7d6f3;
  text-align: left;
  padding: 11px 12px;
  border-radius: 12px;
  cursor: pointer;
  transition: 0.18s ease;
}

.nav-btn:hover,
.nav-btn.active {
  background: linear-gradient(180deg, rgba(255, 107, 95, 0.18), rgba(255, 107, 95, 0.08));
  border-color: rgba(255, 107, 95, 0.24);
  color: #fff4f2;
}

.sidebar-foot {
  margin-top: auto;
  border: 1px solid var(--line);
  background: var(--panel-soft);
  border-radius: 18px;
  padding: 14px;
}

.sidebar-foot h4 {
  margin: 0 0 10px;
  font-size: 14px;
}

.stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.main-shell {
  min-width: 0;
  padding: 22px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 18px 22px;
  border: 1px solid var(--line);
  border-radius: 24px;
  background: rgba(10, 17, 29, 0.85);
  backdrop-filter: blur(14px);
  box-shadow: var(--shadow);
}

.headline {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.eyebrow {
  font-size: 11px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--accent-2);
}

.headline h1 {
  margin: 0;
  font-size: 34px;
  line-height: 1.05;
}

.headline p {
  margin: 0;
  color: var(--muted);
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 999px;
  border: 1px solid var(--line);
  color: #dde9ff;
  background: rgba(18, 29, 49, 0.92);
  font-size: 12px;
  font-weight: 600;
}

.pill.ok { border-color: rgba(53, 208, 138, 0.35); color: #9ff0c7; background: rgba(14, 50, 33, 0.72); }
.pill.fail { border-color: rgba(255, 109, 109, 0.35); color: #ffb6b6; background: rgba(59, 22, 22, 0.82); }
.pill.warn { border-color: rgba(255, 184, 92, 0.35); color: #ffd79f; background: rgba(70, 44, 12, 0.82); }

.btn,
.ghost-btn,
.danger-btn {
  border-radius: 12px;
  border: 1px solid transparent;
  padding: 10px 14px;
  cursor: pointer;
  transition: 0.18s ease;
}

.btn {
  color: #fff4f2;
  background: linear-gradient(135deg, var(--accent), #ff8868);
}

.btn:hover { transform: translateY(-1px); box-shadow: 0 10px 24px rgba(255, 107, 95, 0.25); }

.ghost-btn {
  color: #d4e1f9;
  background: rgba(20, 29, 49, 0.9);
  border-color: var(--line);
}

.ghost-btn:hover { border-color: var(--line-strong); }

.danger-btn {
  color: #ffd8d8;
  background: rgba(96, 24, 24, 0.88);
  border-color: rgba(255, 109, 109, 0.26);
}

.views {
  min-width: 0;
}

.view {
  display: none;
}

.view.active {
  display: block;
}

.grid {
  display: grid;
  gap: 18px;
}

.overview-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.card,
.panel {
  min-width: 0;
  border: 1px solid var(--line);
  border-radius: 24px;
  background: var(--panel);
  box-shadow: var(--shadow);
}

.card {
  padding: 20px;
}

.card h3,
.panel h3,
.panel h4 {
  margin: 0;
}

.metric-value {
  margin-top: 12px;
  font-size: 34px;
  font-weight: 700;
}

.metric-copy {
  margin-top: 8px;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.5;
}

.split {
  display: grid;
  gap: 18px;
  grid-template-columns: minmax(0, 1.5fr) minmax(320px, 0.9fr);
}

.chat-layout {
  display: grid;
  gap: 18px;
  grid-template-columns: 290px minmax(0, 1fr) 320px;
}

.panel-head {
  padding: 18px 18px 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.panel-copy {
  color: var(--muted);
  font-size: 13px;
  margin-top: 6px;
}

.panel-body {
  padding: 18px;
}

.session-list,
.row-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.session-item,
.list-row,
.approval-card,
.job-card {
  border-radius: 18px;
  border: 1px solid var(--line);
  background: rgba(14, 23, 40, 0.88);
}

.session-item {
  width: 100%;
  text-align: left;
  padding: 14px;
  cursor: pointer;
}

.session-item.active {
  border-color: rgba(255, 107, 95, 0.28);
  background: linear-gradient(180deg, rgba(255, 107, 95, 0.14), rgba(16, 24, 38, 0.94));
}

.session-title,
.row-title {
  font-size: 14px;
  font-weight: 700;
}

.session-meta,
.row-meta,
.subtle {
  color: var(--muted);
  font-size: 12px;
}

.chat-shell {
  display: flex;
  flex-direction: column;
  min-height: 720px;
}

.chat-feed {
  flex: 1;
  overflow: auto;
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.bubble {
  max-width: 88%;
  border-radius: 20px;
  padding: 14px 16px;
  border: 1px solid var(--line);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.bubble.user {
  align-self: flex-end;
  background: linear-gradient(135deg, rgba(255, 107, 95, 0.16), rgba(255, 136, 104, 0.12));
  border-color: rgba(255, 107, 95, 0.25);
}

.bubble.assistant {
  align-self: flex-start;
  background: rgba(17, 27, 46, 0.94);
}

.bubble.error {
  border-color: rgba(255, 109, 109, 0.36);
  background: rgba(71, 22, 22, 0.86);
}

.bubble-meta {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 8px;
  color: var(--muted);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.composer {
  border-top: 1px solid var(--line);
  padding: 16px 18px 18px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.composer textarea,
.input,
.select {
  width: 100%;
  border-radius: 16px;
  border: 1px solid var(--line);
  background: rgba(10, 16, 28, 0.88);
  color: var(--ink);
  padding: 12px 14px;
}

.composer textarea {
  min-height: 110px;
  resize: vertical;
}

.composer-bar,
.inline-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.two-up,
.three-up {
  display: grid;
  gap: 16px;
}

.two-up { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.three-up { grid-template-columns: repeat(3, minmax(0, 1fr)); }

.pre {
  margin: 0;
  padding: 14px;
  border-radius: 16px;
  border: 1px solid var(--line);
  background: rgba(9, 15, 25, 0.92);
  color: #dce8ff;
  white-space: pre-wrap;
  font-family: Consolas, "Courier New", monospace;
  font-size: 12px;
  line-height: 1.6;
}

.empty {
  padding: 18px;
  border-radius: 18px;
  border: 1px dashed var(--line-strong);
  color: var(--muted);
  background: rgba(11, 18, 30, 0.72);
}

.table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.table th,
.table td {
  padding: 12px 10px;
  border-bottom: 1px solid var(--line);
  text-align: left;
  vertical-align: top;
}

.table th {
  color: #b9c9e8;
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.table-wrap {
  overflow: auto;
}

.kv {
  display: grid;
  grid-template-columns: 140px minmax(0, 1fr);
  gap: 8px 14px;
  font-size: 13px;
}

.kv .k {
  color: var(--muted);
}

.mini {
  font-size: 11px;
}

@media (max-width: 1220px) {
  .overview-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .chat-layout { grid-template-columns: 260px minmax(0, 1fr); }
  .chat-aside { grid-column: 1 / -1; }
}

@media (max-width: 960px) {
  .app-shell { grid-template-columns: 1fr; }
  .sidebar { border-right: 0; border-bottom: 1px solid var(--line); }
  .topbar { flex-direction: column; align-items: flex-start; }
  .split,
  .chat-layout,
  .overview-grid,
  .two-up,
  .three-up { grid-template-columns: 1fr; }
  .main-shell { padding: 16px; }
}
"""


def _dashboard_js() -> str:
    return """
const NAV_ITEMS = [
  { id: 'overview', label: 'Overview' },
  { id: 'chat', label: 'Chat' },
  { id: 'approvals', label: 'Approvals' },
  { id: 'sessions', label: 'Sessions' },
  { id: 'skills', label: 'Skills' },
  { id: 'plugins', label: 'Plugins' },
  { id: 'config', label: 'Config' },
  { id: 'debug', label: 'Debug' },
];

window.App = window.App || {};

const state = {
  view: 'chat',
  sessions: [],
  activeSessionId: '',
  activeSession: null,
  messages: [],
  jobs: [],
  runtime: null,
  overview: null,
  approvals: null,
  skills: null,
  plugins: null,
  config: null,
  doctor: null,
  service: null,
  health: null,
  sending: false,
  flash: null,
};

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function linesToHtml(value) {
  return escapeHtml(value || '').replace(/\\n/g, '<br />');
}

function shortText(value, limit = 72) {
  const text = String(value || '').trim();
  if (text.length <= limit) {
    return text;
  }
  return text.slice(0, limit - 3).trimEnd() + '...';
}

function fmtTime(value) {
  if (!value && value !== 0) {
    return '--';
  }
  if (/^\\d+$/.test(String(value))) {
    const date = new Date(Number(value) * 1000);
    if (!Number.isNaN(date.getTime())) {
      return date.toLocaleString();
    }
  }
  const date = new Date(value);
  if (!Number.isNaN(date.getTime())) {
    return date.toLocaleString();
  }
  return String(value);
}

function showFlash(message, kind = 'warn') {
  state.flash = { message: String(message || ''), kind };
  renderChrome();
  window.clearTimeout(showFlash._timer);
  showFlash._timer = window.setTimeout(() => {
    state.flash = null;
    renderChrome();
  }, 4200);
}

async function api(path, options = {}) {
  const merged = { ...options };
  merged.headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };
  const response = await fetch(path, merged);
  const text = await response.text();
  let payload = {};
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch (_error) {
      payload = { text };
    }
  }
  if (!response.ok) {
    const detail = payload.detail || payload.message || payload.text || response.statusText;
    throw new Error(detail);
  }
  return payload;
}

function metricCard(label, value, copy) {
  return `
    <article class="card">
      <div class="subtle">${escapeHtml(label)}</div>
      <div class="metric-value">${escapeHtml(value)}</div>
      <div class="metric-copy">${escapeHtml(copy)}</div>
    </article>
  `;
}

function renderJobCard(job) {
  const failed = String(job.status || '').toLowerCase() === 'failed';
  return `
    <div class="job-card panel-body">
      <div class="row-title">${escapeHtml(job.status || 'unknown')}</div>
      <div class="row-meta">${escapeHtml(job.id || '')} • ${escapeHtml(fmtTime(job.created_ts))}</div>
      <div class="subtle" style="margin-top:8px;">${escapeHtml(shortText(job.output_preview || job.error || 'No output recorded yet.', 180))}</div>
      <div class="inline-actions" style="margin-top:12px;">
        <button class="ghost-btn" onclick="App.resumeJob('${escapeHtml(job.id || '')}')">Resume</button>
        ${failed ? '<span class="pill fail">Failed</span>' : '<span class="pill ok">Tracked</span>'}
      </div>
    </div>
  `;
}

function renderSessionButton(session, active) {
  return `
    <button class="session-item ${active ? 'active' : ''}" onclick="App.selectSession('${escapeHtml(session.id)}')">
      <div class="session-title">${escapeHtml(session.title || 'Untitled session')}</div>
      <div class="session-meta">${escapeHtml(shortText(session.last_message_preview || 'No messages yet.', 90))}</div>
      <div class="session-meta" style="margin-top:8px;">${escapeHtml(fmtTime(session.updated_at))} • ${escapeHtml(String(session.message_count || 0))} msgs</div>
    </button>
  `;
}

function renderChrome() {
  const navRoot = document.getElementById('nav-root');
  navRoot.innerHTML =
    '<div class="nav-label">Views</div>' +
    NAV_ITEMS.map((item) => `
      <button class="nav-btn ${state.view === item.id ? 'active' : ''}" onclick="App.setView('${item.id}')">${escapeHtml(item.label)}</button>
    `).join('');

  const provider = state.runtime?.provider_status?.provider || state.health?.provider || 'unknown';
  const model = state.runtime?.provider_status?.model || state.health?.model || 'unknown';
  const sessionTitle = state.activeSession?.title || 'No session';
  const healthOk = state.health?.ok;
  const healthClass = healthOk === true ? 'pill ok' : (healthOk === false ? 'pill fail' : 'pill warn');
  const healthLabel = healthOk === true ? 'Health OK' : (healthOk === false ? 'Health Degraded' : 'Health Pending');

  document.getElementById('topbar-actions').innerHTML = `
    <span class="${healthClass}">${healthLabel}</span>
    <span class="pill">${escapeHtml(provider)}</span>
    <span class="pill">${escapeHtml(shortText(model, 28))}</span>
    <span class="pill">${escapeHtml(shortText(sessionTitle, 28))}</span>
    <button class="ghost-btn" onclick="App.refreshCurrent()">Refresh</button>
    <button class="btn" onclick="App.createSession()">New Session</button>
  `;

  const sessionRows = state.sessions.length
    ? state.sessions.slice(0, 8).map((session) => renderSessionButton(session, session.id === state.activeSessionId)).join('')
    : '<div class="empty">No dashboard sessions yet.</div>';
  const flashClass = !state.flash ? '' : (state.flash.kind === 'success' ? 'pill ok' : (state.flash.kind === 'error' ? 'pill fail' : 'pill warn'));
  const flash = state.flash ? `<div class="${flashClass}" style="justify-content:center;">${escapeHtml(state.flash.message)}</div>` : '';
  document.getElementById('sidebar-foot').innerHTML = `
    <h4>Sessions</h4>
    <div class="stack">
      <button class="btn" onclick="App.createSession()">Start New Control Session</button>
      <div class="session-list">${sessionRows}</div>
      ${flash}
    </div>
  `;

  NAV_ITEMS.forEach((item) => {
    const section = document.getElementById('view-' + item.id);
    if (section) {
      section.classList.toggle('active', item.id === state.view);
    }
  });
}

function renderOverviewView() {
  const root = document.getElementById('view-overview');
  if (!state.overview) {
    root.innerHTML = '<div class="empty">Loading overview...</div>';
    return;
  }

  const provider = state.overview.provider_status || {};
  const recentSessions = (state.overview.recent_sessions || []).map((session) => `
    <div class="list-row panel-body">
      <div class="row-title">${escapeHtml(session.title || 'Untitled session')}</div>
      <div class="row-meta">${escapeHtml(fmtTime(session.updated_at))}</div>
      <div class="subtle" style="margin-top:8px;">${escapeHtml(shortText(session.last_message_preview || 'No transcript yet.', 120))}</div>
    </div>
  `).join('') || '<div class="empty">No dashboard sessions recorded yet.</div>';

  const recentJobs = (state.overview.recent_jobs || []).map(renderJobCard).join('') || '<div class="empty">No recent jobs for the active session.</div>';

  root.innerHTML = `
    <div class="grid overview-grid">
      ${metricCard('Health', `${state.overview.health?.passed || 0}/${state.overview.health?.total || 0}`, 'Doctor checks currently passing.')}
      ${metricCard('Sessions', String(state.overview.session_count || 0), 'Dashboard-native control sessions tracked locally.')}
      ${metricCard('Pending Approvals', String(state.overview.pending_approvals_count || 0), 'Queued approval requests waiting for review.')}
      ${metricCard('Provider', provider.provider || 'unknown', 'Current provider for the most recent dashboard session.')}
    </div>
    <div class="split" style="margin-top:18px;">
      <section class="panel">
        <div class="panel-head">
          <div>
            <h3>Operational Pulse</h3>
            <div class="panel-copy">Snapshot of the local runtime, workspace, and current control session.</div>
          </div>
          <button class="ghost-btn" onclick="App.refreshOverview()">Refresh</button>
        </div>
        <div class="panel-body two-up">
          <div class="card">
            <h3>Runtime</h3>
            <div class="kv" style="margin-top:14px;">
              <div class="k">Session</div><div>${escapeHtml(state.overview.active_session_id || '--')}</div>
              <div class="k">Model</div><div>${escapeHtml(provider.model || '--')}</div>
              <div class="k">Workspace</div><div>${escapeHtml(state.overview.workspace_dir || '--')}</div>
              <div class="k">Data</div><div>${escapeHtml(state.overview.data_dir || '--')}</div>
            </div>
          </div>
          <div class="card">
            <h3>Usage</h3>
            <pre class="pre" style="margin-top:14px;">${escapeHtml(state.overview.usage_report || 'No usage data yet.')}</pre>
          </div>
        </div>
      </section>
      <section class="panel">
        <div class="panel-head">
          <div>
            <h3>Recent Sessions</h3>
            <div class="panel-copy">Quick view of the latest dashboard conversations.</div>
          </div>
          <button class="ghost-btn" onclick="App.setView('chat')">Open Chat</button>
        </div>
        <div class="panel-body row-list">${recentSessions}</div>
      </section>
    </div>
    <div class="split" style="margin-top:18px;">
      <section class="panel">
        <div class="panel-head">
          <div>
            <h3>Recent Jobs</h3>
            <div class="panel-copy">Most recent session-engine executions for the active dashboard session.</div>
          </div>
        </div>
        <div class="panel-body row-list">${recentJobs}</div>
      </section>
      <section class="panel">
        <div class="panel-head">
          <div>
            <h3>Doctor Report</h3>
            <div class="panel-copy">Raw health report from the local runtime doctor.</div>
          </div>
        </div>
        <div class="panel-body">
          <pre class="pre">${escapeHtml(state.overview.doctor_report || 'No doctor data available.')}</pre>
        </div>
      </section>
    </div>
  `;
}

function renderChatView() {
  const root = document.getElementById('view-chat');
  const providerStatus = state.runtime?.provider_status || {};
  const session = state.activeSession;
  const providers = state.runtime?.available_providers || [];
  const sessionRows = state.sessions.length
    ? state.sessions.map((item) => renderSessionButton(item, item.id === state.activeSessionId)).join('')
    : '<div class="empty">Create a dashboard session to begin.</div>';
  const messages = state.messages.length
    ? state.messages.map((message) => {
        const bubbleClass = message.kind === 'error' ? 'bubble assistant error' : 'bubble ' + (message.role === 'user' ? 'user' : 'assistant');
        const label = message.role === 'user' ? 'Operator' : 'Agent';
        return `
          <div class="${bubbleClass}">
            <div class="bubble-meta">
              <span>${escapeHtml(label)}</span>
              <span>${escapeHtml(fmtTime(message.created_at))}</span>
            </div>
            <div>${linesToHtml(message.content || '')}</div>
          </div>
        `;
      }).join('')
    : '<div class="empty">No transcript yet. Send a direct message from this dashboard to start the session.</div>';

  const providerOptions = providers.length
    ? providers.map((provider) => `<option value="${escapeHtml(provider)}" ${provider === providerStatus.provider ? 'selected' : ''}>${escapeHtml(provider)}</option>`).join('')
    : '<option value="">No providers</option>';

  const jobs = state.jobs.length ? state.jobs.map(renderJobCard).join('') : '<div class="empty">No session jobs recorded yet.</div>';

  root.innerHTML = `
    <div class="chat-layout">
      <section class="panel">
        <div class="panel-head">
          <div>
            <h3>Dashboard Sessions</h3>
            <div class="panel-copy">Switch sessions without leaving the local control panel.</div>
          </div>
          <button class="ghost-btn" onclick="App.createSession()">New</button>
        </div>
        <div class="panel-body session-list">${sessionRows}</div>
      </section>

      <section class="panel chat-shell">
        <div class="panel-head">
          <div>
            <h3>${escapeHtml(session?.title || 'Control Session')}</h3>
            <div class="panel-copy">${escapeHtml(session?.user_id || 'Dashboard session not selected yet.')}</div>
          </div>
          <div class="inline-actions">
            <span class="pill">${escapeHtml(providerStatus.provider || 'unknown')}</span>
            <span class="pill">${escapeHtml(shortText(providerStatus.model || 'unknown', 26))}</span>
          </div>
        </div>
        <div id="chat-feed" class="chat-feed">${messages}</div>
        <form class="composer" onsubmit="App.submitMessage(event)">
          <textarea id="composer-text" placeholder="Send a direct message to Agent 1. Shift+Enter for a new line." onkeydown="App.handleComposerKey(event)"></textarea>
          <div class="composer-bar">
            <span class="subtle">Local dashboard control path. Telegram is not used for this session.</span>
            <button class="btn" type="submit">${state.sending ? 'Sending...' : 'Send Message'}</button>
          </div>
        </form>
      </section>

      <aside class="panel chat-aside">
        <div class="panel-head">
          <div>
            <h3>Runtime Controls</h3>
            <div class="panel-copy">Adjust provider routing for the active dashboard session.</div>
          </div>
        </div>
        <div class="panel-body stack">
          <label class="subtle">Provider</label>
          <select id="provider-select" class="select">${providerOptions}</select>
          <button class="ghost-btn" onclick="App.saveProvider()">Apply Provider</button>

          <label class="subtle">Model Override</label>
          <input id="model-input" class="input" value="${escapeHtml(providerStatus.model || '')}" placeholder="Enter model override" />
          <div class="inline-actions">
            <button class="ghost-btn" onclick="App.saveModel()">Save Model</button>
            <button class="danger-btn" onclick="App.clearModel()">Clear Override</button>
          </div>

          <div class="card">
            <h3>Policy</h3>
            <div class="kv" style="margin-top:14px;">
              <div class="k">Profile</div><div>${escapeHtml(state.runtime?.policy_status?.profile || '--')}</div>
              <div class="k">Tools</div><div>${escapeHtml(state.runtime?.policy_status?.allow_tools || '--')}</div>
              <div class="k">Denied</div><div>${escapeHtml(state.runtime?.policy_status?.deny_tools || '--')}</div>
            </div>
          </div>

          <div class="card">
            <h3>Usage</h3>
            <pre class="pre" style="margin-top:14px;">${escapeHtml(state.runtime?.usage_report || 'No usage data yet.')}</pre>
          </div>

          <div>
            <h3>Recent Jobs</h3>
            <div class="row-list" style="margin-top:12px;">${jobs}</div>
          </div>
        </div>
      </aside>
    </div>
  `;

  window.requestAnimationFrame(() => {
    const feed = document.getElementById('chat-feed');
    if (feed) {
      feed.scrollTop = feed.scrollHeight;
    }
  });
}

function renderApprovalsView() {
  const root = document.getElementById('view-approvals');
  if (!state.approvals) {
    root.innerHTML = '<div class="empty">Loading approvals...</div>';
    return;
  }
  const rows = state.approvals.length
    ? state.approvals.map((item) => `
        <div class="approval-card panel-body">
          <div class="row-title">${escapeHtml(item.action_type || 'approval')}</div>
          <div class="row-meta">${escapeHtml(item.id || '')} • requested by ${escapeHtml(item.requested_by || 'unknown')}</div>
          <div class="subtle" style="margin-top:10px;">${escapeHtml(item.reason || 'No reason provided.')}</div>
          <pre class="pre" style="margin-top:12px;">${escapeHtml(JSON.stringify(item.payload || {}, null, 2))}</pre>
          <div class="inline-actions" style="margin-top:12px;">
            <button class="btn" onclick="App.approve('${escapeHtml(item.id || '')}')">Approve</button>
            <button class="danger-btn" onclick="App.deny('${escapeHtml(item.id || '')}')">Deny</button>
          </div>
        </div>
      `).join('')
    : '<div class="empty">No pending approvals.</div>';

  root.innerHTML = `
    <section class="panel">
      <div class="panel-head">
        <div>
          <h3>Approval Center</h3>
          <div class="panel-copy">Review queued approval requests directly from the dashboard.</div>
        </div>
        <button class="ghost-btn" onclick="App.refreshApprovals()">Refresh</button>
      </div>
      <div class="panel-body row-list">${rows}</div>
    </section>
  `;
}

function renderSessionsView() {
  const root = document.getElementById('view-sessions');
  const sessionRows = state.sessions.length
    ? state.sessions.map((session) => renderSessionButton(session, session.id === state.activeSessionId)).join('')
    : '<div class="empty">No dashboard sessions yet.</div>';
  const jobs = state.jobs.length ? state.jobs.map(renderJobCard).join('') : '<div class="empty">No jobs yet for this session.</div>';
  const transcript = state.messages.length
    ? state.messages.slice(-8).map((item) => `
        <div class="list-row panel-body">
          <div class="row-title">${escapeHtml(item.role || 'assistant')}</div>
          <div class="row-meta">${escapeHtml(fmtTime(item.created_at))}</div>
          <div class="subtle" style="margin-top:8px;">${escapeHtml(shortText(item.content || '', 180))}</div>
        </div>
      `).join('')
    : '<div class="empty">No message history in this session yet.</div>';

  root.innerHTML = `
    <div class="split">
      <section class="panel">
        <div class="panel-head">
          <div>
            <h3>Session Registry</h3>
            <div class="panel-copy">All dashboard-native control sessions stored on this machine.</div>
          </div>
          <button class="btn" onclick="App.createSession()">New Session</button>
        </div>
        <div class="panel-body session-list">${sessionRows}</div>
      </section>
      <section class="panel">
        <div class="panel-head">
          <div>
            <h3>Selected Session</h3>
            <div class="panel-copy">${escapeHtml(state.activeSession?.title || 'No session selected')}</div>
          </div>
          <button class="ghost-btn" onclick="App.setView('chat')">Open Chat</button>
        </div>
        <div class="panel-body">
          <div class="three-up">
            <div class="card">
              <h3>User Id</h3>
              <div class="metric-copy" style="margin-top:14px;">${escapeHtml(state.activeSession?.user_id || '--')}</div>
            </div>
            <div class="card">
              <h3>Updated</h3>
              <div class="metric-copy" style="margin-top:14px;">${escapeHtml(fmtTime(state.activeSession?.updated_at))}</div>
            </div>
            <div class="card">
              <h3>Messages</h3>
              <div class="metric-copy" style="margin-top:14px;">${escapeHtml(String(state.activeSession?.message_count || 0))}</div>
            </div>
          </div>
          <div class="split" style="margin-top:18px;">
            <div>
              <h4>Recent Jobs</h4>
              <div class="row-list" style="margin-top:12px;">${jobs}</div>
            </div>
            <div>
              <h4>Transcript Preview</h4>
              <div class="row-list" style="margin-top:12px;">${transcript}</div>
            </div>
          </div>
        </div>
      </section>
    </div>
  `;
}

function renderSkillsView() {
  const root = document.getElementById('view-skills');
  if (!state.skills) {
    root.innerHTML = '<div class="empty">Loading skills...</div>';
    return;
  }
  const rows = state.skills.length
    ? state.skills.map((item) => `
        <tr>
          <td>${escapeHtml(item.display_name || item.folder || '--')}</td>
          <td>${escapeHtml(item.tool_name || '--')}</td>
          <td>${escapeHtml(item.status || '--')}</td>
          <td>${escapeHtml(item.runtime_mode || '--')}</td>
          <td>${escapeHtml(item.permissions || '--')}</td>
        </tr>
      `).join('')
    : '<tr><td colspan="5">No skills discovered.</td></tr>';

  root.innerHTML = `
    <section class="panel">
      <div class="panel-head">
        <div>
          <h3>Skills</h3>
          <div class="panel-copy">Current dynamic skill registry exposed to the orchestrator.</div>
        </div>
        <button class="ghost-btn" onclick="App.refreshSkills()">Refresh</button>
      </div>
      <div class="panel-body table-wrap">
        <table class="table">
          <thead>
            <tr><th>Name</th><th>Tool</th><th>Status</th><th>Runtime</th><th>Permissions</th></tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </section>
  `;
}

function renderPluginsView() {
  const root = document.getElementById('view-plugins');
  if (!state.plugins) {
    root.innerHTML = '<div class="empty">Loading plugins...</div>';
    return;
  }
  const rows = state.plugins.length
    ? state.plugins.map((item) => `
        <tr>
          <td>${escapeHtml(item.name || '--')}</td>
          <td>${escapeHtml(item.enabled || '--')}</td>
          <td>${escapeHtml(item.source_type || '--')}</td>
          <td>${escapeHtml(item.pin_ref || '--')}</td>
          <td>${escapeHtml(item.skills || '--')}</td>
        </tr>
      `).join('')
    : '<tr><td colspan="5">No plugins registered.</td></tr>';

  root.innerHTML = `
    <section class="panel">
      <div class="panel-head">
        <div>
          <h3>Plugins</h3>
          <div class="panel-copy">Installed plugin inventory for this local runtime.</div>
        </div>
        <button class="ghost-btn" onclick="App.refreshPlugins()">Refresh</button>
      </div>
      <div class="panel-body table-wrap">
        <table class="table">
          <thead>
            <tr><th>Name</th><th>Enabled</th><th>Source</th><th>Pin</th><th>Skills</th></tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </section>
  `;
}

function renderConfigView() {
  const root = document.getElementById('view-config');
  if (!state.config) {
    root.innerHTML = '<div class="empty">Loading config...</div>';
    return;
  }
  const integrations = Object.entries(state.config.integrations || {}).map(([key, value]) => `
    <div class="list-row panel-body">
      <div class="row-title">${escapeHtml(key)}</div>
      <div class="row-meta">${value ? 'configured' : 'not configured'}</div>
    </div>
  `).join('');

  root.innerHTML = `
    <div class="split">
      <section class="panel">
        <div class="panel-head">
          <div>
            <h3>Runtime Summary</h3>
            <div class="panel-copy">Sanitized runtime configuration surfaced for the dashboard.</div>
          </div>
          <button class="ghost-btn" onclick="App.refreshConfig()">Refresh</button>
        </div>
        <div class="panel-body two-up">
          <div class="card">
            <h3>LLM</h3>
            <div class="kv" style="margin-top:14px;">
              <div class="k">Default provider</div><div>${escapeHtml(state.config.llm?.default_provider || '--')}</div>
              <div class="k">Default model</div><div>${escapeHtml(state.config.llm?.default_model || '--')}</div>
              <div class="k">Base URL</div><div>${escapeHtml(state.config.llm?.base_url || '--')}</div>
              <div class="k">Adapter</div><div>${escapeHtml(state.config.chat_adapter || '--')}</div>
            </div>
          </div>
          <div class="card">
            <h3>Paths</h3>
            <div class="kv" style="margin-top:14px;">
              <div class="k">Data</div><div>${escapeHtml(state.config.paths?.data_dir || '--')}</div>
              <div class="k">Workspace</div><div>${escapeHtml(state.config.paths?.workspace_dir || '--')}</div>
              <div class="k">Logs</div><div>${escapeHtml(state.config.paths?.logs_dir || '--')}</div>
              <div class="k">Jobs</div><div>${escapeHtml(state.config.paths?.session_jobs || '--')}</div>
            </div>
          </div>
        </div>
      </section>
      <section class="panel">
        <div class="panel-head">
          <div>
            <h3>Integrations</h3>
            <div class="panel-copy">Presence flags only. Secrets are never shown here.</div>
          </div>
        </div>
        <div class="panel-body row-list">${integrations || '<div class="empty">No integration data available.</div>'}</div>
      </section>
    </div>
    <section class="panel" style="margin-top:18px;">
      <div class="panel-head">
        <div>
          <h3>Raw Config Snapshot</h3>
          <div class="panel-copy">Useful for debugging dashboard state without exposing credentials.</div>
        </div>
      </div>
      <div class="panel-body">
        <pre class="pre">${escapeHtml(JSON.stringify(state.config, null, 2))}</pre>
      </div>
    </section>
  `;
}

function renderDebugView() {
  const root = document.getElementById('view-debug');
  if (!state.doctor && !state.service) {
    root.innerHTML = '<div class="empty">Loading debug panels...</div>';
    return;
  }
  root.innerHTML = `
    <div class="split">
      <section class="panel">
        <div class="panel-head">
          <div>
            <h3>Service Status</h3>
            <div class="panel-copy">Docker compose status if services are available on this machine.</div>
          </div>
          <button class="ghost-btn" onclick="App.refreshService()">Refresh</button>
        </div>
        <div class="panel-body">
          <pre class="pre">${escapeHtml(state.service?.output || 'No service output yet.')}</pre>
        </div>
      </section>
      <section class="panel">
        <div class="panel-head">
          <div>
            <h3>Doctor Report</h3>
            <div class="panel-copy">Full local doctor output for debugging runtime issues.</div>
          </div>
          <button class="ghost-btn" onclick="App.refreshDoctor()">Refresh</button>
        </div>
        <div class="panel-body">
          <pre class="pre">${escapeHtml(state.doctor?.report || 'No doctor output yet.')}</pre>
        </div>
      </section>
    </div>
    <section class="panel" style="margin-top:18px;">
      <div class="panel-head">
        <div>
          <h3>Active Session Runtime</h3>
          <div class="panel-copy">Provider, policy, and usage state for the selected dashboard session.</div>
        </div>
      </div>
      <div class="panel-body">
        <pre class="pre">${escapeHtml(JSON.stringify(state.runtime || {}, null, 2))}</pre>
      </div>
    </section>
  `;
}

function renderViews() {
  renderOverviewView();
  renderChatView();
  renderApprovalsView();
  renderSessionsView();
  renderSkillsView();
  renderPluginsView();
  renderConfigView();
  renderDebugView();
}

async function refreshHealth() {
  state.health = await api('/api/health');
  renderChrome();
}

async function loadSessions(preferredId = '') {
  const data = await api('/api/chat/sessions');
  state.sessions = data.items || [];
  if (preferredId) {
    state.activeSessionId = preferredId;
  } else if (!state.activeSessionId || !state.sessions.some((item) => item.id === state.activeSessionId)) {
    state.activeSessionId = data.default_session_id || state.sessions[0]?.id || '';
  }
  renderChrome();
}

async function loadSession(sessionId) {
  if (!sessionId) {
    return;
  }
  const payload = await api('/api/chat/sessions/' + encodeURIComponent(sessionId));
  state.activeSessionId = payload.session?.id || sessionId;
  state.activeSession = payload.session || null;
  state.messages = payload.messages || [];
  state.jobs = payload.jobs || [];
  state.runtime = payload.runtime || null;
  renderChrome();
  renderViews();
}

async function refreshOverview() {
  state.overview = await api('/api/overview');
  renderViews();
}

async function refreshApprovals() {
  state.approvals = await api('/api/approvals/pending?limit=60');
  renderViews();
}

async function refreshSkills() {
  state.skills = await api('/api/skills');
  renderViews();
}

async function refreshPlugins() {
  state.plugins = await api('/api/plugins');
  renderViews();
}

async function refreshConfig() {
  state.config = await api('/api/config');
  renderViews();
}

async function refreshDoctor() {
  state.doctor = await api('/api/doctor');
  renderViews();
}

async function refreshService() {
  state.service = await api('/api/service');
  renderViews();
}

async function refreshViewData(view, force = false) {
  if (view === 'overview' && (force || !state.overview)) {
    await refreshOverview();
  }
  if (view === 'approvals' && (force || !state.approvals)) {
    await refreshApprovals();
  }
  if (view === 'skills' && (force || !state.skills)) {
    await refreshSkills();
  }
  if (view === 'plugins' && (force || !state.plugins)) {
    await refreshPlugins();
  }
  if (view === 'config' && (force || !state.config)) {
    await refreshConfig();
  }
  if (view === 'debug') {
    if (force || !state.doctor) {
      await refreshDoctor();
    }
    if (force || !state.service) {
      await refreshService();
    }
  }
}

window.App.setView = async function(view) {
  state.view = view;
  renderChrome();
  renderViews();
  try {
    await refreshViewData(view, false);
  } catch (error) {
    showFlash(error.message || String(error), 'error');
  }
};

window.App.selectSession = async function(sessionId) {
  try {
    await loadSession(sessionId);
    if (state.view !== 'sessions' && state.view !== 'chat') {
      state.view = 'chat';
    }
    renderChrome();
    renderViews();
  } catch (error) {
    showFlash(error.message || String(error), 'error');
  }
};

window.App.createSession = async function() {
  try {
    const payload = await api('/api/chat/sessions', {
      method: 'POST',
      body: JSON.stringify({ title: '' }),
    });
    const sessionId = payload.session?.id || '';
    await loadSessions(sessionId);
    await loadSession(sessionId);
    state.view = 'chat';
    renderChrome();
    renderViews();
    showFlash('New dashboard session created.', 'success');
  } catch (error) {
    showFlash(error.message || String(error), 'error');
  }
};

window.App.submitMessage = async function(event) {
  if (event) {
    event.preventDefault();
  }
  const box = document.getElementById('composer-text');
  const text = (box?.value || '').trim();
  if (!text || !state.activeSessionId || state.sending) {
    return false;
  }
  state.sending = true;
  renderViews();
  try {
    const payload = await api('/api/chat/sessions/' + encodeURIComponent(state.activeSessionId) + '/messages', {
      method: 'POST',
      body: JSON.stringify({ text }),
    });
    if (box) {
      box.value = '';
    }
    state.activeSession = payload.session || null;
    state.messages = payload.messages || [];
    state.jobs = payload.jobs || [];
    state.runtime = payload.runtime || null;
    await loadSessions(state.activeSessionId);
    await refreshHealth();
    if (state.view === 'overview') {
      await refreshOverview();
    }
  } catch (error) {
    showFlash(error.message || String(error), 'error');
  } finally {
    state.sending = false;
    renderChrome();
    renderViews();
  }
  return false;
};

window.App.handleComposerKey = function(event) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    window.App.submitMessage();
  }
};

window.App.saveProvider = async function() {
  const select = document.getElementById('provider-select');
  if (!select || !state.activeSessionId) {
    return;
  }
  try {
    const payload = await api('/api/chat/sessions/' + encodeURIComponent(state.activeSessionId) + '/provider', {
      method: 'POST',
      body: JSON.stringify({ provider: select.value }),
    });
    state.runtime = payload.runtime || state.runtime;
    await refreshHealth();
    renderChrome();
    renderViews();
    showFlash(payload.message || 'Provider updated.', payload.ok ? 'success' : 'error');
  } catch (error) {
    showFlash(error.message || String(error), 'error');
  }
};

window.App.saveModel = async function() {
  const input = document.getElementById('model-input');
  if (!input || !state.activeSessionId) {
    return;
  }
  try {
    const payload = await api('/api/chat/sessions/' + encodeURIComponent(state.activeSessionId) + '/model', {
      method: 'POST',
      body: JSON.stringify({ model: input.value }),
    });
    state.runtime = payload.runtime || state.runtime;
    await refreshHealth();
    renderChrome();
    renderViews();
    showFlash(payload.message || 'Model updated.', payload.ok ? 'success' : 'error');
  } catch (error) {
    showFlash(error.message || String(error), 'error');
  }
};

window.App.clearModel = async function() {
  if (!state.activeSessionId) {
    return;
  }
  try {
    const payload = await api('/api/chat/sessions/' + encodeURIComponent(state.activeSessionId) + '/model', {
      method: 'POST',
      body: JSON.stringify({ clear: true }),
    });
    state.runtime = payload.runtime || state.runtime;
    await refreshHealth();
    renderChrome();
    renderViews();
    showFlash(payload.message || 'Model override cleared.', payload.ok ? 'success' : 'error');
  } catch (error) {
    showFlash(error.message || String(error), 'error');
  }
};

window.App.approve = async function(approvalId) {
  try {
    const payload = await api('/api/approvals/' + encodeURIComponent(approvalId) + '/approve', {
      method: 'POST',
      body: JSON.stringify({ actor: 'dashboard-ui' }),
    });
    await refreshApprovals();
    await refreshOverview();
    showFlash(payload.message || 'Approval completed.', payload.ok ? 'success' : 'error');
  } catch (error) {
    showFlash(error.message || String(error), 'error');
  }
};

window.App.deny = async function(approvalId) {
  const reason = window.prompt('Optional deny reason:', '') || '';
  try {
    const payload = await api('/api/approvals/' + encodeURIComponent(approvalId) + '/deny', {
      method: 'POST',
      body: JSON.stringify({ actor: 'dashboard-ui', reason }),
    });
    await refreshApprovals();
    await refreshOverview();
    showFlash(payload.message || 'Approval denied.', payload.ok ? 'success' : 'error');
  } catch (error) {
    showFlash(error.message || String(error), 'error');
  }
};

window.App.resumeJob = async function(jobId) {
  try {
    const payload = await api('/api/jobs/' + encodeURIComponent(jobId) + '/resume', {
      method: 'POST',
      body: JSON.stringify({}),
    });
    if (state.activeSessionId) {
      await loadSession(state.activeSessionId);
    }
    if (state.view === 'overview') {
      await refreshOverview();
    }
    showFlash(payload.message || 'Resume attempted.', payload.ok ? 'success' : 'error');
  } catch (error) {
    showFlash(error.message || String(error), 'error');
  }
};

window.App.refreshCurrent = async function() {
  try {
    await refreshHealth();
    await loadSessions(state.activeSessionId);
    if (state.activeSessionId) {
      await loadSession(state.activeSessionId);
    }
    await refreshViewData(state.view, true);
    if (state.view !== 'overview' && !state.overview) {
      await refreshOverview();
    }
    renderChrome();
    renderViews();
    showFlash('Dashboard refreshed.', 'success');
  } catch (error) {
    showFlash(error.message || String(error), 'error');
  }
};

window.App.refreshOverview = refreshOverview;
window.App.refreshApprovals = refreshApprovals;
window.App.refreshSkills = refreshSkills;
window.App.refreshPlugins = refreshPlugins;
window.App.refreshConfig = refreshConfig;
window.App.refreshDoctor = refreshDoctor;
window.App.refreshService = refreshService;

window.addEventListener('DOMContentLoaded', async () => {
  renderChrome();
  renderViews();
  try {
    await refreshHealth();
    await loadSessions();
    if (state.activeSessionId) {
      await loadSession(state.activeSessionId);
    }
    await refreshOverview();
    renderChrome();
    renderViews();
  } catch (error) {
    showFlash(error.message || String(error), 'error');
  }
});
"""


def dashboard_html() -> str:
    return (
        """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>Agent 1 Control</title>
    <style>"""
        + _dashboard_css()
        + """</style>
  </head>
  <body>
    <div class="app-shell">
      <aside class="sidebar">
        <div class="brand">
          <div class="brand-kicker">Local Agent Control</div>
          <div class="brand-title">Agent 1</div>
          <div class="brand-copy">Dashboard-native sessions, direct chat control, approvals, and runtime visibility.</div>
        </div>
        <div class="nav-group" id="nav-root"></div>
        <div class="sidebar-foot" id="sidebar-foot"></div>
      </aside>

      <main class="main-shell">
        <header class="topbar">
          <div class="headline">
            <div class="eyebrow">Operational Dashboard</div>
            <h1>Control Panel</h1>
            <p>Direct access to the agent without Telegram in the loop.</p>
          </div>
          <div class="topbar-actions" id="topbar-actions"></div>
        </header>

        <div class="views">
          <section id="view-overview" class="view active"></section>
          <section id="view-chat" class="view"></section>
          <section id="view-approvals" class="view"></section>
          <section id="view-sessions" class="view"></section>
          <section id="view-skills" class="view"></section>
          <section id="view-plugins" class="view"></section>
          <section id="view-config" class="view"></section>
          <section id="view-debug" class="view"></section>
        </div>
      </main>
    </div>
    <script>"""
        + _dashboard_js()
        + """</script>
  </body>
</html>"""
    )
