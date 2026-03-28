from __future__ import annotations

import os
from pathlib import Path

from agent1.config import PROJECT_ROOT, Settings
from agent1.diagnostics import Doctor
from agent1.home_layout import scaffold_agent1_home
from agent1.workspace_profile import WorkspaceProfile

PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "custom": {
        "base_url": "https://api.openai.com/v1",
        "api_key": "",
        "model": "gpt-4o",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "api_key": "",
        "model": "gpt-4o",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": "",
        "model": "llama-3.3-70b-versatile",
    },
    "xai": {
        "base_url": "https://api.x.ai/v1",
        "api_key": "",
        "model": "grok-3-latest",
    },
    "anthropic_compat": {
        "base_url": "",
        "api_key": "",
        "model": "claude-3-5-sonnet-latest",
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "api_key": "ollama",
        "model": "llama3.1:8b-instruct",
    },
}

PROVIDER_ENV_PREFIX: dict[str, str] = {
    "openai": "OPENAI",
    "groq": "GROQ",
    "xai": "XAI",
    "anthropic_compat": "ANTHROPIC_COMPAT",
    "ollama": "OLLAMA",
}

GITIGNORE_SENSITIVE_ENTRIES = [
    ".env",
    ".env.*",
    "!.env.example",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "*.crt",
    ".venv/",
    "venv/",
    "__pycache__/",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    "*.egg-info/",
    ".pytest_cache/",
    ".mypy_cache/",
    ".ruff_cache/",
    ".coverage",
    "htmlcov/",
    "build/",
    "dist/",
    "*.spec",
    "data/*",
    "!data/.keep",
    "workspace/*",
    "!workspace/.keep",
    "logs/",
    "sessions/",
    ".agent1-test/",
    ".release_smoke/",
    ".release_smoke*/",
    ".tmp-approvals.json",
    "tmp_approvals*.json",
]


def _expand_path(raw: str) -> Path:
    value = raw.strip()
    if not value:
        return PROJECT_ROOT
    expanded = Path(os.path.expandvars(value)).expanduser()
    if expanded.is_absolute():
        return expanded.resolve()
    return (PROJECT_ROOT / expanded).resolve()


def _portable_join(base: str, suffix: str) -> str:
    root = base.replace("\\", "/").rstrip("/")
    leaf = suffix.replace("\\", "/").lstrip("/")
    if not root:
        return leaf
    if not leaf:
        return root
    return f"{root}/{leaf}"


def _home_layout_overrides(home_root: str) -> dict[str, str]:
    home_root = home_root.replace("\\", "/").rstrip("/")
    workspace = _portable_join(home_root, "workspace")
    data = _portable_join(home_root, "data")
    credentials = _portable_join(home_root, "credentials")

    return {
        "AGENT1_HOME_PATH": home_root,
        "AGENT1_HOME_SCAFFOLD_ENABLED": "true",
        "DATA_DIR": data,
        "SAFE_FILES_ROOT": _portable_join(workspace, "safe"),
        "SAFE_SHELL_WORKDIR": _portable_join(workspace, "safe"),
        "MARKDOWN_MEMORY_PATH": _portable_join(workspace, "memory"),
        "VECTOR_MEMORY_PATH": _portable_join(data, "chroma"),
        "APPROVAL_STORE_PATH": _portable_join(data, "approvals/pending.json"),
        "SUBSCRIBERS_STORE_PATH": _portable_join(data, "approvals/subscribers.json"),
        "PROVIDER_PREFERENCES_PATH": _portable_join(data, "approvals/provider_preferences.json"),
        "TOOL_POLICY_STORE_PATH": _portable_join(data, "approvals/tool_policy.json"),
        "APP_LOG_PATH": _portable_join(data, "logs/app.log"),
        "TOOL_LOG_PATH": _portable_join(data, "logs/tool_calls.log"),
        "AGENTGUARD_AUDIT_LOG_PATH": _portable_join(data, "logs/agentguard_audit.log"),
        "USAGE_METER_PATH": _portable_join(data, "logs/usage_meter.jsonl"),
        "WORKSPACE_PROFILE_PATH": workspace,
        "SKILLS_ROOT_PATH": _portable_join(workspace, "skills"),
        "SKILLS_REGISTRY_PATH": _portable_join(workspace, "skills/registry.json"),
        "PLUGINS_ROOT_PATH": _portable_join(workspace, "plugins"),
        "PLUGINS_REGISTRY_PATH": _portable_join(workspace, "plugins/registry.json"),
        "SESSION_JOBS_PATH": _portable_join(data, "sessions/jobs.json"),
        "SESSION_HISTORY_PATH": _portable_join(data, "sessions/history.jsonl"),
        "SCHEMA_STATE_PATH": _portable_join(data, "schema_state.json"),
        "GOOGLE_CALENDAR_CREDENTIALS_PATH": _portable_join(credentials, "google_credentials.json"),
        "GOOGLE_CALENDAR_TOKEN_PATH": _portable_join(credentials, "google_token.json"),
    }


def _prompt(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value if value else default


def _prompt_yes_no(prompt: str, default_yes: bool = True) -> bool:
    default_hint = "Y/n" if default_yes else "y/N"
    value = input(f"{prompt} ({default_hint}): ").strip().lower()
    if not value:
        return default_yes
    return value in {"y", "yes", "true", "1"}


def _prompt_choice(prompt: str, choices: list[str], default: str) -> str:
    allowed = {item.lower(): item for item in choices}
    while True:
        value = _prompt(prompt + " (" + ", ".join(choices) + ")", default=default).strip().lower()
        if value in allowed:
            return allowed[value]
        print(f"Invalid choice `{value}`. Allowed: {', '.join(choices)}")


def _env_escape(value: str) -> str:
    if not value:
        return ""
    if any(ch.isspace() for ch in value) or "#" in value or value != value.strip():
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def _portable_path(raw: str) -> str:
    value = raw.strip()
    if not value:
        return ""
    normalized = value.replace("\\", "/")
    if normalized.startswith("${"):
        return normalized

    expanded = Path(os.path.expandvars(value)).expanduser()
    if not expanded.is_absolute():
        return normalized

    project = PROJECT_ROOT.resolve()
    try:
        rel = expanded.resolve().relative_to(project)
        rel_text = str(rel).replace("\\", "/")
        return f"./{rel_text}"
    except Exception:
        pass

    home = Path.home().resolve()
    try:
        rel_home = expanded.resolve().relative_to(home)
        home_var = "USERPROFILE" if os.name == "nt" else "HOME"
        rel_home_text = str(rel_home).replace("\\", "/")
        return f"${{{home_var}}}/{rel_home_text}"
    except Exception:
        # Keep this portable instead of hard-coding machine-specific paths.
        return "./data/approvals/external_exec_approvals.json"


def _render_env(template: str, overrides: dict[str, str]) -> str:
    lines = template.splitlines()
    output: list[str] = []
    replaced: set[str] = set()

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            output.append(line)
            continue
        key, _rest = line.split("=", 1)
        key = key.strip()
        if key in overrides:
            output.append(f"{key}={_env_escape(overrides[key])}")
            replaced.add(key)
        else:
            output.append(line)

    for key, value in overrides.items():
        if key not in replaced:
            output.append(f"{key}={_env_escape(value)}")

    return "\n".join(output).rstrip() + "\n"


def _ensure_gitignore(project_root: Path) -> None:
    gitignore_path = project_root / ".gitignore"
    if gitignore_path.exists():
        current_lines = gitignore_path.read_text(encoding="utf-8").splitlines()
    else:
        current_lines = []

    existing = {line.strip() for line in current_lines}
    additions = [entry for entry in GITIGNORE_SENSITIVE_ENTRIES if entry not in existing]
    if not additions:
        return

    if current_lines and current_lines[-1].strip():
        current_lines.append("")
    current_lines.append("# Agent 1 generated sensitive paths")
    current_lines.extend(additions)
    gitignore_path.write_text("\n".join(current_lines).rstrip() + "\n", encoding="utf-8")


def _render_soul_content(app_name: str, style: str, proactive: bool) -> str:
    proactive_line = "Take initiative and suggest next actions." if proactive else "Stay reactive unless asked to initiate."
    return (
        "# SOUL.md - Core Behavior\n\n"
        f"Identity:\n- Name: {app_name}\n- Style: {style}\n\n"
        "Operating principles:\n"
        "- Prioritize useful, concrete execution.\n"
        "- Keep responses concise and structured.\n"
        "- Ask for approval before risky actions.\n"
        f"- {proactive_line}\n"
        "- Explain tradeoffs when multiple options exist.\n"
    )


def _render_user_content(use_cases: str, comms: str, timezone: str) -> str:
    return (
        "# USER.md - User Context\n\n"
        "Profile:\n"
        f"- Preferred communication style: {comms}\n"
        f"- Timezone: {timezone}\n"
        f"- Main use cases: {use_cases}\n\n"
        "Notes:\n"
        "- Keep this file free of secrets and personal identifiers.\n"
        "- Store only durable preferences and workflow constraints.\n"
    )


def run_init_walkthrough(default_style: str | None = None, default_home_path: str | None = None) -> None:
    print("Agent 1 Interactive Walkthrough")
    print("This will configure .env, scaffold workspace, and generate SOUL.md + USER.md.")
    print("")

    style_seed = (default_style or os.environ.get("AGENT1_INIT_STYLE") or "home").strip().lower()
    if style_seed not in {"home", "project"}:
        style_seed = "home"
    setup_style = _prompt_choice("Setup style", ["home", "project"], default=style_seed)
    home_var = "USERPROFILE" if os.name == "nt" else "HOME"
    home_default = default_home_path or os.environ.get("AGENT1_INIT_HOME_PATH") or f"${{{home_var}}}/.agent1"
    selected_home_root = ""
    workspace: Path
    if setup_style == "home":
        selected_home_root = _portable_path(_prompt("Agent home directory", home_default))
        home_expanded = _expand_path(selected_home_root)
        layout = scaffold_agent1_home(home_expanded, home_expanded / "workspace")
        workspace = layout["workspace"]
    else:
        workspace = PROJECT_ROOT / "workspace"

    app_name = _prompt("Agent name", "Agent 1")
    timezone = _prompt("Timezone", "America/Jamaica")
    use_cases = _prompt("Main use cases", "general assistant, coding, research, automation")
    communication_style = _prompt("Preferred response style", "concise and practical")
    proactive = _prompt_yes_no("Enable proactive behavior by default", default_yes=True)

    provider = _prompt_choice(
        "Default provider",
        ["custom", "openai", "groq", "xai", "anthropic_compat", "ollama"],
        default="custom",
    )
    defaults = PROVIDER_DEFAULTS[provider]
    base_url = _prompt("Base URL", defaults["base_url"])
    api_key = _prompt("API key (leave blank for local/no-key providers)", defaults["api_key"])
    model = _prompt("Model", defaults["model"])
    skill_runtime_mode = _prompt_choice("Skill runtime isolation mode", ["auto", "process", "docker"], default="auto")

    chat_adapter = _prompt_choice(
        "Primary adapter",
        ["telegram", "discord", "slack", "whatsapp", "bridge", "cli"],
        default="telegram",
    )
    telegram_token = _prompt("Telegram bot token (optional)", "")
    telegram_allowed = _prompt("Telegram allowed user IDs (comma-separated, optional)", "")
    discord_token = _prompt("Discord bot token (optional)", "")
    discord_allowed = _prompt("Discord allowed user IDs (comma-separated, optional)", "")
    slack_bot_token = _prompt("Slack bot token (optional)", "")
    slack_app_token = _prompt("Slack app token (optional)", "")
    slack_allowed = _prompt("Slack allowed user IDs (comma-separated, optional)", "")
    whatsapp_verify_token = _prompt("WhatsApp verify token (optional)", "")
    whatsapp_access_token = _prompt("WhatsApp access token (optional)", "")
    whatsapp_phone_number_id = _prompt("WhatsApp phone number ID (optional)", "")
    whatsapp_allowed_numbers = _prompt("WhatsApp allowed phone numbers (comma-separated, optional)", "")
    whatsapp_host = _prompt("WhatsApp webhook host", "0.0.0.0")
    whatsapp_port = _prompt("WhatsApp webhook port", "8790")
    bridge_host = _prompt("Bridge host", "0.0.0.0")
    bridge_port = _prompt("Bridge port", "8787")
    bridge_auth_token = _prompt("Bridge auth token (recommended)", "")
    bridge_channels = _prompt("Bridge allowed channels", "whatsapp,imessage,custom")

    external_enabled = _prompt_yes_no("Enable external approvals daemon bridge", default_yes=False)
    default_bridge_path = (
        _portable_join(selected_home_root, "exec-approvals.json")
        if setup_style == "home"
        else f"${{{home_var}}}/.openclaw/exec-approvals.json"
    )
    external_config_path = default_bridge_path if setup_style == "home" else ""
    if external_enabled:
        raw_path = _prompt("External approvals config path", default_bridge_path)
        external_config_path = _portable_path(raw_path)

    env_path = PROJECT_ROOT / ".env"
    overwrite_env = True
    if env_path.exists():
        overwrite_env = _prompt_yes_no(".env already exists. Overwrite it", default_yes=False)

    profile = WorkspaceProfile(workspace)
    profile.ensure_scaffold()
    (workspace / "skills").mkdir(parents=True, exist_ok=True)
    (workspace / "plugins").mkdir(parents=True, exist_ok=True)
    (workspace / "memory").mkdir(parents=True, exist_ok=True)

    soul_path = workspace / "SOUL.md"
    user_path = workspace / "USER.md"
    overwrite_profile_docs = True
    if soul_path.exists() or user_path.exists():
        overwrite_profile_docs = _prompt_yes_no(
            "SOUL.md/USER.md already exist. Rewrite from walkthrough answers",
            default_yes=False,
        )
    if overwrite_profile_docs:
        soul_path.write_text(_render_soul_content(app_name=app_name, style=communication_style, proactive=proactive), encoding="utf-8")
        user_path.write_text(
            _render_user_content(use_cases=use_cases, comms=communication_style, timezone=timezone),
            encoding="utf-8",
        )

    if overwrite_env or not env_path.exists():
        template_path = PROJECT_ROOT / ".env.example"
        template = template_path.read_text(encoding="utf-8") if template_path.exists() else ""
        overrides = {
            "APP_NAME": app_name,
            "TIMEZONE": timezone,
            "LLM_DEFAULT_PROVIDER": provider,
            "LLM_BASE_URL": base_url,
            "LLM_API_KEY": api_key,
            "LLM_MODEL": model,
            "CHAT_ADAPTER": chat_adapter,
            "TELEGRAM_BOT_TOKEN": telegram_token,
            "TELEGRAM_ALLOWED_USER_IDS": telegram_allowed,
            "DISCORD_BOT_TOKEN": discord_token,
            "DISCORD_ALLOWED_USER_IDS": discord_allowed,
            "SLACK_BOT_TOKEN": slack_bot_token,
            "SLACK_APP_TOKEN": slack_app_token,
            "SLACK_ALLOWED_USER_IDS": slack_allowed,
            "WHATSAPP_VERIFY_TOKEN": whatsapp_verify_token,
            "WHATSAPP_ACCESS_TOKEN": whatsapp_access_token,
            "WHATSAPP_PHONE_NUMBER_ID": whatsapp_phone_number_id,
            "WHATSAPP_ALLOWED_PHONE_NUMBERS": whatsapp_allowed_numbers,
            "WHATSAPP_HOST": whatsapp_host,
            "WHATSAPP_PORT": whatsapp_port,
            "BRIDGE_HOST": bridge_host,
            "BRIDGE_PORT": bridge_port,
            "BRIDGE_AUTH_TOKEN": bridge_auth_token,
            "BRIDGE_ALLOWED_CHANNELS": bridge_channels,
            "PROACTIVE_MODE_ENABLED": "true" if proactive else "false",
            "SKILL_RUNTIME_MODE": skill_runtime_mode,
            "EXTERNAL_APPROVALS_ENABLED": "true" if external_enabled else "false",
            "EXTERNAL_APPROVALS_CONFIG_PATH": external_config_path,
        }
        if setup_style == "home":
            overrides.update(_home_layout_overrides(selected_home_root))
        prefix = PROVIDER_ENV_PREFIX.get(provider)
        if prefix:
            overrides[f"{prefix}_BASE_URL"] = base_url
            overrides[f"{prefix}_API_KEY"] = api_key
            overrides[f"{prefix}_MODEL"] = model

        rendered = _render_env(template, overrides)
        env_path.write_text(rendered, encoding="utf-8")

    _ensure_gitignore(PROJECT_ROOT)

    # Validate runtime and daemon-bridge reachability (when enabled).
    settings = Settings(_env_file=str(env_path))
    settings.ensure_paths()
    doctor = Doctor(settings)
    report = doctor.report_text()

    print("")
    print("Walkthrough complete.")
    print(f"- Setup style: {setup_style}")
    if setup_style == "home":
        print(f"- Agent home: {_expand_path(selected_home_root)}")
    print(f"- Wrote workspace scaffold under: {workspace}")
    if overwrite_env or not env_path.exists():
        print(f"- Updated environment file: {env_path}")
    else:
        print("- Kept existing .env unchanged.")
    print("- Ensured sensitive entries are present in .gitignore.")
    print("")
    print(report)
