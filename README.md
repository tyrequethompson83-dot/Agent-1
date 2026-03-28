# Agent 1

Fast, self-hosted, OpenAI-compatible autonomous AI agent with:
- LangGraph orchestrator + specialist agents
- Telegram + Discord + Slack + WhatsApp + bridge webhook interfaces
- Persistent Markdown + Chroma memory
- Safe tool execution with human approval gates
- Proactive scheduler (daily briefing + task digest)
- Dockerized runtime for isolation and speed

## Why LangGraph (instead of CrewAI)
This starter uses **LangGraph** because it is stronger for reliable long-running agent flows:
- Explicit state graph for predictable orchestration
- Better control over tool usage and routing
- Easier human-in-the-loop gates for risky actions
- Cleaner path to durable workflows as you scale autonomy

CrewAI is great for fast role-play prototyping, but for operational reliability and controllable autonomy, LangGraph is the better base.

## Project Structure
```text
agent_1/
  .env.example
  docker-compose.yml
  Dockerfile
  pyproject.toml
  README.md
  data/
    .keep
    # runtime-generated on first run:
    # approvals/ chroma/ logs/ memory/ parity/ safe_workspace/ sessions/
  workspace/
    .keep
    # runtime-generated on first run:
    # AGENTS.md HEARTBEAT.md IDENTITY.md MEMORY.md SOUL.md TOOLS.md USER.md
    # memory/ plugins/ skills/
  scripts/
    bootstrap.ps1
    bootstrap.sh
    install.ps1
    install.sh
    build_binary.ps1
    build_binary.sh
    setup_google_calendar.py
  src/agent1/
    agents/
      orchestrator.py
    integrations/
      bridge_webhook.py
      discord_bot.py
      slack_bot.py
      telegram_bot.py
      whatsapp_bot.py
    memory/
      markdown_store.py
      chroma_store.py
      manager.py
    scheduler/
      proactive.py
    tools/
      approval.py
      loader.py
      safe_shell.py
      safe_files.py
      web_tools.py
      email_tool.py
      calendar_tool.py
      registry.py
    config.py
    llm.py
    provider_router.py
    prompts.py
    session_engine.py
    migrations.py
    service_manager.py
    workspace_profile.py
    cli/
      init.py
      parity.py
    plugins/
      manager.py
    main.py
```
`data/` and `workspace/` are treated as local runtime state. The public repo keeps only `.keep` placeholders; the app recreates the real contents on first run.

By default, `agent1 init` now supports an OpenClaw-style home profile under `~/.agent1` (or `%USERPROFILE%\.agent1`) so runtime files live in one place.

## Core Capabilities
- **OpenAI-compatible LLM client**: OpenAI, Groq, Ollama, Anthropic-compat, xAI-compatible endpoints.
- **Per-user provider switching**:
  - choose provider via `/provider`
  - choose model via `/model`
  - see runtime profile via `/profile`
- **No gateway/proxy required now**: direct model API call path for lower latency.
- **Shadow Gateway ready**: swap `LLM_BASE_URL` + `LLM_API_KEY` only.
- **OpenClaw-style workspace files**:
  - `workspace/IDENTITY.md`
  - `workspace/SOUL.md`
  - `workspace/AGENTS.md`
  - `workspace/TOOLS.md`
  - `workspace/MEMORY.md`
  - `workspace/HEARTBEAT.md`
  - `workspace/USER.md`
- **Universal skill compatibility**:
  - auto-discovers folders in `workspace/skills/`
  - parses `SKILL.md` (`Name`, `Description`, `Usage`, `Permissions`)
  - wraps `main.py`/shell entrypoints as dynamic tools
  - supports process runtime or optional Docker runtime isolation (`SKILL_RUNTIME_MODE`)
  - hot-reloads skill index at runtime (no restart needed)
- **Tool permission profiles**:
  - profiles: `full`, `safe`, `messaging`
  - per-user profile switching in chat
  - per-user custom tool/permission overrides (`/policy_tool`, `/policy_permission`)
  - skill permission-aware blocking for risky capabilities
- **Operational diagnostics + metering**:
  - `/doctor` runtime checks
  - `/doctor_fix` quick self-healing for common runtime state issues
  - LLM + tool telemetry in `data/logs/usage_meter.jsonl`
  - estimated LLM cost tracking by provider/model
- **Onboarding + operations CLI**:
  - `agent1 onboard` guided setup flow
  - `agent1 approvals ...` external approvals config + check
  - `agent1 parity` automated OpenClaw parity report
  - `agent1 gateway ...` docker service lifecycle aliases
  - `agent1 dashboard` lightweight local control UI (includes approve/deny actions for pending approvals)
- **Plugin lifecycle basics**:
  - install plugin from local path or git source
  - enable/disable plugin skills without uninstall
  - pin plugin version/tag/commit
  - update plugin from saved source
  - uninstall plugin
  - plugin registry persisted in `workspace/plugins/registry.json`
- **External approvals bridge (optional)**:
  - OpenClaw-style exec-approvals config bridge
  - supports external allow/deny/pending decisions before local approval flow
- **Persistent memory**:
  - Markdown: chat history, facts, tasks, notes
  - Chroma: local vector recall
- **Tooling**:
  - Safe shell execution (allowlisted commands only + approval)
  - Safe file read/write in sandbox directory
  - Web search + browser fetch (DuckDuckGo + Playwright)
  - Email read/send (Gmail/Outlook style IMAP/SMTP)
  - Google Calendar list/create
- **Human-in-the-loop** for risky actions:
  - shell execution
  - file writes
  - email send
  - calendar event creation
- **Proactive mode** via APScheduler:
  - morning briefing
  - pending task digest
- **Session engine safeguards**:
  - per-user queueing + global concurrency limits
  - persistent session job/history records
  - resume support for completed/failed jobs

## 1) Configure Environment
```bash
cp .env.example .env
```

Select adapter in `.env`:
- `CHAT_ADAPTER=telegram` with `TELEGRAM_BOT_TOKEN`
- `CHAT_ADAPTER=discord` with `DISCORD_BOT_TOKEN`
- `CHAT_ADAPTER=slack` with `SLACK_BOT_TOKEN` + `SLACK_APP_TOKEN`
- `CHAT_ADAPTER=whatsapp` with `WHATSAPP_VERIFY_TOKEN` + `WHATSAPP_ACCESS_TOKEN` + `WHATSAPP_PHONE_NUMBER_ID`
- `CHAT_ADAPTER=bridge` with `BRIDGE_AUTH_TOKEN` (for WhatsApp/iMessage-style connectors)
- `CHAT_ADAPTER=cli` for terminal-only mode

### LLM quick examples
Use provider profiles in `.env`:
- `LLM_DEFAULT_PROVIDER=custom|openai|groq|xai|anthropic_compat|ollama`
- Set credentials/model for the profile you want.
- Cloud providers appear in `/providers` only after API key + base URL + model are set.
- Ollama URL tip:
  - local Python run: `OLLAMA_BASE_URL=http://localhost:11434/v1`
  - Docker + compose `ollama` service: `OLLAMA_BASE_URL=http://ollama:11434/v1`
- In Telegram, users can switch at runtime:
  - `/providers`
  - `/provider <name>`
  - `/model <model_name>`
  - `/model default` (clear override)

### Shadow Gateway later
Change only:
- `LLM_BASE_URL`
- `LLM_API_KEY`

The rest of the project stays the same.

## 2) Telegram Bot Setup
1. In Telegram, open **@BotFather**
2. Run `/newbot` and create bot
3. Copy token into `.env` as `TELEGRAM_BOT_TOKEN`
4. Optional hardening: set `TELEGRAM_ALLOWED_USER_IDS=<your_user_id>`

Discord setup (optional):
1. Create a Discord bot in the Developer Portal
2. Enable Message Content intent
3. Set `CHAT_ADAPTER=discord` and `DISCORD_BOT_TOKEN` in `.env`
4. Optional hardening: set `DISCORD_ALLOWED_USER_IDS=<comma-separated ids>`

Slack setup (optional):
1. Create a Slack app with Socket Mode enabled
2. Add bot scopes and install app to workspace
3. Set `CHAT_ADAPTER=slack`, `SLACK_BOT_TOKEN`, and `SLACK_APP_TOKEN`
4. Optional hardening: set `SLACK_ALLOWED_USER_IDS=<comma-separated ids>`

WhatsApp setup (optional, Meta Cloud API):
1. In Meta Developer, configure WhatsApp Cloud API + webhook
2. Set in `.env`:
   - `CHAT_ADAPTER=whatsapp`
   - `WHATSAPP_VERIFY_TOKEN`
   - `WHATSAPP_ACCESS_TOKEN`
   - `WHATSAPP_PHONE_NUMBER_ID`
3. Point webhook URL to `http://<host>:<WHATSAPP_PORT>/webhook`
4. Optional hardening: `WHATSAPP_ALLOWED_PHONE_NUMBERS=<comma-separated E.164>`

Bridge setup (optional, for WhatsApp/iMessage-style connectors):
1. Set `CHAT_ADAPTER=bridge`
2. Set `BRIDGE_HOST`, `BRIDGE_PORT`, `BRIDGE_AUTH_TOKEN`
3. POST inbound messages to `/v1/message` with header `X-Agent1-Token`
4. Optional callback: include `reply_url` in payload

Bridge request example:
```bash
curl -X POST http://localhost:8787/v1/message \
  -H "Content-Type: application/json" \
  -H "X-Agent1-Token: <BRIDGE_AUTH_TOKEN>" \
  -d '{"channel":"whatsapp","user_id":"12345","text":"Summarize my tasks"}'
```

Useful commands:
- `/help`
- `/providers`
- `/provider <name>`
- `/model <name>`
- `/profile`
- `/policy`
- `/policy_set <full|safe|messaging>`
- `/policy_tool <allow|deny|clear> <tool>`
- `/policy_permission <allow|deny|clear> <permission>`
- `/policy_reset`
- `/skills`
- `/skill_enable <folder>`
- `/skill_disable <folder>`
- `/plugins`
- `/plugin_install <source> [name] [ref]`
- `/plugin_update <name>`
- `/plugin_uninstall <name>`
- `/plugin_pin <name> <ref|clear>`
- `/plugin_enable <name>`
- `/plugin_disable <name>`
- `/doctor`
- `/doctor_fix`
- `/usage`
- `/approve <approval_id>`
- `/pending`
- `/tasks`
- `/jobs`
- `/resume_job <job_id>`

## 3) Run Locally
One-command bootstrap:
```bash
powershell -ExecutionPolicy Bypass -File scripts/bootstrap.ps1 -RunInit -InitStyle home
# or
RUN_INIT=1 INIT_STYLE=home bash scripts/bootstrap.sh
```

One-command installer (bootstrap + onboard):
```bash
powershell -ExecutionPolicy Bypass -File scripts/install.ps1 -Style home
# or
STYLE=home bash scripts/install.sh
```

Recommended first run (full onboarding):
```bash
powershell -ExecutionPolicy Bypass -File scripts/bootstrap.ps1 -RunOnboard -InitStyle home
# or
RUN_ONBOARD=1 INIT_STYLE=home bash scripts/bootstrap.sh
```

Optional pipx install for cleaner user setup:
```bash
pipx install .
agent1 init
agent1 doctor
```

Manual setup:
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -U pip
pip install -e .
playwright install chromium
python -m agent1.main
```

Interactive first-time setup wizard:
```bash
python -m agent1.main init
```
The wizard configures `.env`, scaffolds workspace, writes `SOUL.md` + `USER.md`, and updates `.gitignore` for sensitive files.
It also normalizes absolute paths into portable project-relative or `${HOME}`/`${USERPROFILE}` forms.
It defaults to `home` setup style, which creates an OpenClaw-like layout in `~/.agent1`.

Force style explicitly:
```bash
python -m agent1.main init --style home
python -m agent1.main init --style project
```

OpenClaw-style guided flow:
```bash
python -m agent1.main onboard --style home
python -m agent1.main onboard --style home --up
```

If `TELEGRAM_BOT_TOKEN` is empty, it falls back to CLI mode.

CLI one-shot diagnostics:
```bash
python -m agent1.main doctor
python -m agent1.main doctor_fix
python -m agent1.main parity
python -m agent1.main parity --json --output data/parity/report.json
```

Service lifecycle:
```bash
python -m agent1.main up
python -m agent1.main down
python -m agent1.main status
python -m agent1.main gateway status
python -m agent1.main gateway up
python -m agent1.main gateway down
python -m agent1.main upgrade
```

Approvals daemon management:
```bash
python -m agent1.main approvals get
python -m agent1.main approvals set --socket-path /tmp/exec-approvals.sock --token <token>
python -m agent1.main approvals set --host 127.0.0.1 --port 7777 --token <token>
python -m agent1.main approvals allowlist add safe_shell
python -m agent1.main approvals denylist add safe_files
python -m agent1.main approvals check
```

Local dashboard:
```bash
python -m agent1.main dashboard --host 127.0.0.1 --port 8765
```

Prebuilt binary build:
```bash
powershell -ExecutionPolicy Bypass -File scripts/build_binary.ps1 -Clean
# or
CLEAN_BUILD=1 bash scripts/build_binary.sh
```

Automated release binaries:
- GitHub Actions workflow: `.github/workflows/build-binaries.yml`
- Produces artifacts for Windows, Linux, and macOS on tag push (`v*`) or manual trigger.

## 4) Run with Docker
```bash
docker compose up --build -d
```

Optional local Ollama service:
```bash
docker compose --profile local-llm up -d ollama
```

## 5) Google Calendar Setup
1. Create OAuth desktop app credentials in Google Cloud
2. Save JSON at `./data/google_credentials.json`
3. Run:
```bash
python scripts/setup_google_calendar.py
```
4. Set `CALENDAR_ENABLED=true` in `.env`

## 6) Email Setup (Gmail/Outlook)
Use app passwords or account-specific credentials:
- `EMAIL_ENABLED=true`
- `EMAIL_ADDRESS`, `EMAIL_PASSWORD`
- IMAP/SMTP hosts and ports

Email sending is approval-gated by default.

## Security Model
- Containerized runtime
- Non-root container user
- Safe file root isolation (`SAFE_FILES_ROOT`)
- Shell command allowlist (`SAFE_SHELL_ALLOWED_COMMANDS`)
- Explicit approval gates for risky actions
- Tool call logging (`data/logs/tool_calls.log`)
- Optional external approvals bridge (`EXTERNAL_APPROVALS_*`)

## How To Add New Tools
1. Implement tool class/function in `src/agent1/tools/`
2. Register it in `ToolRegistry.build_for_user()` in `src/agent1/tools/registry.py`
3. Add tool name to a specialist in `AgentOrchestrator._build_specialist()` in `src/agent1/agents/orchestrator.py`

## OpenClaw Skill Compatibility
- Drop any skill folder under `workspace/skills/<skill_name>/`
- Include a `SKILL.md` and an executable entrypoint (`main.py`, `.sh`, `.ps1`, etc.)
- Agent 1 automatically re-indexes and injects the skill into LangGraph tool execution
- Registrations are logged to `data/logs/agentguard_audit.log`
- Skills can be enabled/disabled live via `/skill_enable` and `/skill_disable`

## Bridge Existing OpenClaw Setup
Use this script to import useful compatibility data from `~/.openclaw`:

```bash
python scripts/import_openclaw_profile.py
```

What it does:
- reads all `openclaw.json*` snapshots and picks the newest
- maps compatible model/provider hints into `agent_1/.env`
- copies discovered OpenClaw skill folders into `workspace/skills/`
- includes `node.json` + `update-check.json` signals in a sanitized report at `workspace/OPENCLAW_IMPORT.md`

Optional:
- include API keys from OpenClaw env vars:
```bash
python scripts/import_openclaw_profile.py --include-secrets
```
- skip copying skills:
```bash
python scripts/import_openclaw_profile.py --skip-skill-copy
```

## OpenClaw-Style Home Layout
When setup style is `home`, Agent 1 scaffolds:
- `~/.agent1/agents`
- `~/.agent1/bin`
- `~/.agent1/canvas`
- `~/.agent1/credentials`
- `~/.agent1/cron`
- `~/.agent1/devices`
- `~/.agent1/identity`
- `~/.agent1/telegram`
- `~/.agent1/workspace`
- `~/.agent1/exec-approvals.json`
- `~/.agent1/node.json`
- `~/.agent1/agent1.json` + `agent1.json.bak*`
- `~/.agent1/update-check.json`

## Plugin Lifecycle
Telegram/CLI supports:
- list plugins: `/plugins`
- install plugin: `/plugin_install <source> [name] [ref]`
- update plugin: `/plugin_update <name>`
- uninstall plugin: `/plugin_uninstall <name>`
- pin version/tag/commit: `/plugin_pin <name> <ref|clear>`
- enable plugin skills: `/plugin_enable <name>`
- disable plugin skills: `/plugin_disable <name>`

Install sources can be:
- local folder path
- git URL (requires git installed and network access)

Installed plugin metadata is stored in:
- `workspace/plugins/registry.json`

`/doctor` includes external approvals daemon validation when `EXTERNAL_APPROVALS_ENABLED=true`, including socket/auth handshake reachability (Unix socket or TCP endpoint).

## How To Add New Specialist Agents
1. Add a prompt in `src/agent1/prompts.py`
2. Add route label to `RouteDecision` in `orchestrator.py`
3. Add graph node + edge in `_build_graph()`
4. Add tool subset in `_build_specialist()`

## Add More Adapters
Telegram, Discord, Slack, WhatsApp, and bridge webhook adapters are included. For additional adapters:
1. Create a new adapter under `src/agent1/integrations/` that implements `ChatAdapter` from `src/agent1/interfaces/base.py`.
2. Reuse `AgentOrchestrator` exactly as-is.
3. Add adapter selection logic in `src/agent1/main.py`.

## Performance Notes
- Router uses heuristics first to cut LLM round-trips.
- Direct API calls (no gateway) for lower latency.
- Keep `LLM_MAX_TOKENS` and prompt context tight for speed.
- Playwright is used only when needed; simple pages fall back to HTTP scrape.
