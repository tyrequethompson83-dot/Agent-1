from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Agent 1"
    environment: str = "dev"
    timezone: str = "America/Jamaica"
    agent1_home_path: Path = Field(default=Path.home() / ".agent1")
    agent1_home_scaffold_enabled: bool = False

    llm_default_provider: str = "custom"

    # Legacy + custom single-provider profile.
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = "changeme"
    llm_model: str = "gpt-4o"

    # Multi-provider profiles (OpenAI-compatible endpoints).
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    xai_base_url: str = "https://api.x.ai/v1"
    xai_api_key: str = ""
    xai_model: str = "grok-3-latest"

    anthropic_compat_base_url: str = ""
    anthropic_compat_api_key: str = ""
    anthropic_compat_model: str = "claude-3-5-sonnet-latest"

    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_api_key: str = "ollama"
    ollama_model: str = "llama3.1:8b-instruct"

    llm_temperature: float = 0.2
    llm_timeout_seconds: int = 45
    llm_max_tokens: int = 1800

    telegram_bot_token: str = ""
    telegram_allowed_user_ids: str = ""
    telegram_default_chat_id: str = ""

    data_dir: Path = Field(default=Path("./data"))
    safe_files_root: Path = Field(default=Path("./data/safe_workspace"))
    safe_shell_workdir: Path = Field(default=Path("./data/safe_workspace"))
    safe_shell_allowed_commands: str = "ls,pwd,echo,cat,rg,python,python3,pip,git,pytest"
    safe_shell_timeout_seconds: int = 20
    auto_approve_risky_actions: bool = False
    default_tool_profile: str = "full"
    tool_policy_global_allow: str = ""
    tool_policy_global_deny: str = ""
    tool_policy_global_deny_permissions: str = ""

    markdown_memory_path: Path = Field(default=Path("./data/memory"))
    vector_memory_path: Path = Field(default=Path("./data/chroma"))
    approval_store_path: Path = Field(default=Path("./data/approvals/pending.json"))
    subscribers_store_path: Path = Field(default=Path("./data/approvals/subscribers.json"))
    provider_preferences_path: Path = Field(default=Path("./data/approvals/provider_preferences.json"))
    tool_policy_store_path: Path = Field(default=Path("./data/approvals/tool_policy.json"))
    app_log_path: Path = Field(default=Path("./data/logs/app.log"))
    tool_log_path: Path = Field(default=Path("./data/logs/tool_calls.log"))
    agentguard_audit_log_path: Path = Field(default=Path("./data/logs/agentguard_audit.log"))
    usage_meter_path: Path = Field(default=Path("./data/logs/usage_meter.jsonl"))
    workspace_profile_path: Path = Field(default=Path("./workspace"))
    skills_root_path: Path = Field(default=Path("./workspace/skills"))
    skills_registry_path: Path = Field(default=Path("./workspace/skills/registry.json"))
    skill_exec_timeout_seconds: int = 45
    skill_use_venv_if_present: bool = True
    skill_runtime_mode: str = "auto"  # auto | process | docker
    skill_docker_image: str = "python:3.11-slim"
    skill_docker_memory_mb: int = 512
    skill_docker_cpus: float = 1.0
    skill_block_unsafe_args: bool = True
    plugins_root_path: Path = Field(default=Path("./workspace/plugins"))
    plugins_registry_path: Path = Field(default=Path("./workspace/plugins/registry.json"))
    plugin_git_timeout_seconds: int = 120

    external_approvals_enabled: bool = False
    external_approvals_config_path: Path = Field(default=Path.home() / ".agent1" / "exec-approvals.json")
    external_approvals_timeout_seconds: int = 2

    session_max_concurrency: int = 2
    session_jobs_path: Path = Field(default=Path("./data/sessions/jobs.json"))
    session_history_path: Path = Field(default=Path("./data/sessions/history.jsonl"))
    session_max_history_per_user: int = 200

    schema_state_path: Path = Field(default=Path("./data/schema_state.json"))

    chat_adapter: str = "telegram"  # telegram | discord | slack | whatsapp | bridge | cli
    discord_bot_token: str = ""
    discord_allowed_user_ids: str = ""
    slack_bot_token: str = ""
    slack_app_token: str = ""
    slack_allowed_user_ids: str = ""
    whatsapp_verify_token: str = ""
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_allowed_phone_numbers: str = ""
    whatsapp_host: str = "0.0.0.0"
    whatsapp_port: int = 8790
    whatsapp_api_version: str = "v21.0"
    bridge_host: str = "0.0.0.0"
    bridge_port: int = 8787
    bridge_auth_token: str = ""
    bridge_allowed_channels: str = "whatsapp,imessage,custom"

    proactive_mode_enabled: bool = True
    morning_briefing_hour: int = 8
    morning_briefing_minute: int = 0
    pending_task_digest_hours: int = 6

    max_search_results: int = 5
    browser_max_chars: int = 5000
    web_user_agent: str = "Agent1/0.1 (+local-self-hosted)"

    email_enabled: bool = False
    email_address: str = ""
    email_password: str = ""
    email_imap_host: str = "imap.gmail.com"
    email_imap_port: int = 993
    email_smtp_host: str = "smtp.gmail.com"
    email_smtp_port: int = 587
    email_smtp_use_starttls: bool = True
    email_mailbox: str = "INBOX"

    calendar_enabled: bool = False
    google_calendar_id: str = "primary"
    google_calendar_credentials_path: Path = Field(default=Path("./data/google_credentials.json"))
    google_calendar_token_path: Path = Field(default=Path("./data/google_token.json"))

    @field_validator(
        "agent1_home_path",
        "data_dir",
        "safe_files_root",
        "safe_shell_workdir",
        "markdown_memory_path",
        "vector_memory_path",
        "approval_store_path",
        "subscribers_store_path",
        "provider_preferences_path",
        "tool_policy_store_path",
        "app_log_path",
        "tool_log_path",
        "agentguard_audit_log_path",
        "usage_meter_path",
        "workspace_profile_path",
        "skills_root_path",
        "skills_registry_path",
        "plugins_root_path",
        "plugins_registry_path",
        "external_approvals_config_path",
        "session_jobs_path",
        "session_history_path",
        "schema_state_path",
        "google_calendar_credentials_path",
        "google_calendar_token_path",
        mode="before",
    )
    @classmethod
    def _resolve_paths(cls, value: str | Path) -> Path:
        raw = str(value)
        expanded = os.path.expandvars(os.path.expanduser(raw))
        path = Path(expanded)
        if path.is_absolute():
            return path.resolve()
        return (PROJECT_ROOT / path).resolve()

    @property
    def allowed_telegram_user_ids(self) -> set[str]:
        if not self.telegram_allowed_user_ids.strip():
            return set()
        return {item.strip() for item in self.telegram_allowed_user_ids.split(",") if item.strip()}

    @property
    def safe_shell_allowlist(self) -> set[str]:
        return {item.strip() for item in self.safe_shell_allowed_commands.split(",") if item.strip()}

    @property
    def allowed_discord_user_ids(self) -> set[str]:
        if not self.discord_allowed_user_ids.strip():
            return set()
        return {item.strip() for item in self.discord_allowed_user_ids.split(",") if item.strip()}

    @property
    def allowed_slack_user_ids(self) -> set[str]:
        if not self.slack_allowed_user_ids.strip():
            return set()
        return {item.strip() for item in self.slack_allowed_user_ids.split(",") if item.strip()}

    @property
    def allowed_whatsapp_phone_numbers(self) -> set[str]:
        if not self.whatsapp_allowed_phone_numbers.strip():
            return set()
        return {item.strip() for item in self.whatsapp_allowed_phone_numbers.split(",") if item.strip()}

    @property
    def allowed_bridge_channels(self) -> set[str]:
        if not self.bridge_allowed_channels.strip():
            return set()
        return {item.strip().lower() for item in self.bridge_allowed_channels.split(",") if item.strip()}

    def runtime_directories(self) -> tuple[Path, ...]:
        return (
            self.data_dir,
            self.safe_files_root,
            self.safe_shell_workdir,
            self.markdown_memory_path,
            self.vector_memory_path,
            self.approval_store_path.parent,
            self.subscribers_store_path.parent,
            self.provider_preferences_path.parent,
            self.tool_policy_store_path.parent,
            self.app_log_path.parent,
            self.tool_log_path.parent,
            self.agentguard_audit_log_path.parent,
            self.usage_meter_path.parent,
            self.workspace_profile_path,
            self.workspace_profile_path / "memory",
            self.skills_root_path,
            self.skills_registry_path.parent,
            self.plugins_root_path,
            self.plugins_registry_path.parent,
            self.session_jobs_path.parent,
            self.session_history_path.parent,
            self.schema_state_path.parent,
            self.google_calendar_credentials_path.parent,
            self.google_calendar_token_path.parent,
        )

    def ensure_paths(self) -> None:
        for path in self.runtime_directories():
            path.mkdir(parents=True, exist_ok=True)

        if self.agent1_home_scaffold_enabled:
            from agent1.home_layout import scaffold_agent1_home

            scaffold_agent1_home(
                home_path=self.agent1_home_path,
                workspace_path=self.workspace_profile_path,
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_paths()
    return settings
