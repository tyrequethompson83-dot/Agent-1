from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_OPENCLAW_FILES = [
    "openclaw.json",
    "openclaw.json.bak",
    "openclaw.json.bak.1",
    "openclaw.json.bak.2",
    "openclaw.json.bak.3",
    "openclaw.json.bak.4",
    "openclaw.json.bak.reset",
]


@dataclass
class LoadedConfig:
    path: Path
    data: dict[str, Any]
    touched_at: datetime


def parse_iso_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def load_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_optional_json(path: Path) -> dict[str, Any]:
    data = load_json(path)
    return data if isinstance(data, dict) else {}


def discover_configs(openclaw_root: Path) -> list[LoadedConfig]:
    configs: list[LoadedConfig] = []
    for name in DEFAULT_OPENCLAW_FILES:
        path = openclaw_root / name
        if not path.exists():
            continue
        data = load_json(path)
        if not isinstance(data, dict):
            continue
        touched = parse_iso_datetime(data.get("meta", {}).get("lastTouchedAt"))
        if touched.timestamp() == 0:
            touched = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        configs.append(LoadedConfig(path=path, data=data, touched_at=touched))
    configs.sort(key=lambda item: item.touched_at, reverse=True)
    return configs


def first_agent(config: dict[str, Any]) -> dict[str, Any]:
    agents = config.get("agents", {}).get("list", [])
    if not isinstance(agents, list) or not agents:
        return {}
    for item in agents:
        if isinstance(item, dict) and item.get("id") == "main":
            return item
    return agents[0] if isinstance(agents[0], dict) else {}


def parse_model_ref(model_ref: str) -> tuple[str, str]:
    model_ref = (model_ref or "").strip()
    if not model_ref:
        return "", ""
    if "/" not in model_ref:
        return "", model_ref
    provider, model = model_ref.split("/", 1)
    return provider.strip().lower(), model.strip()


def parse_duration_to_minutes(value: str) -> int | None:
    value = (value or "").strip().lower()
    if not value:
        return None
    match = re.match(r"^(\d+)\s*([smhd])$", value)
    if not match:
        return None
    amount = int(match.group(1))
    unit = match.group(2)
    factor = {"s": 1 / 60, "m": 1, "h": 60, "d": 1440}[unit]
    return int(amount * factor)


def read_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip()
    return out


def write_env_file(path: Path, data: dict[str, str]) -> None:
    lines = [f"{key}={value}" for key, value in sorted(data.items())]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def discover_skill_dirs(openclaw_workspace: Path) -> list[Path]:
    out: list[Path] = []
    if not openclaw_workspace.exists():
        return out
    # Top-level custom skills: <workspace>/<skill>/SKILL.md
    for candidate in sorted(openclaw_workspace.iterdir(), key=lambda p: p.name.lower()):
        if not candidate.is_dir():
            continue
        if (candidate / "SKILL.md").exists():
            out.append(candidate)
    # Nested skills bucket: <workspace>/skills/<skill>/SKILL.md
    nested = openclaw_workspace / "skills"
    if nested.exists() and nested.is_dir():
        for candidate in sorted(nested.iterdir(), key=lambda p: p.name.lower()):
            if candidate.is_dir() and (candidate / "SKILL.md").exists():
                out.append(candidate)
    dedup: dict[str, Path] = {}
    for path in out:
        dedup[path.resolve().as_posix().lower()] = path
    return list(dedup.values())


def copy_skills(skill_dirs: list[Path], dest_root: Path, overwrite: bool) -> list[tuple[str, str]]:
    results: list[tuple[str, str]] = []
    dest_root.mkdir(parents=True, exist_ok=True)
    for source in skill_dirs:
        dest = dest_root / source.name
        if dest.exists():
            if not overwrite:
                results.append((source.name, "skipped_exists"))
                continue
            shutil.rmtree(dest)
        shutil.copytree(source, dest)
        results.append((source.name, "copied"))
    return results


def sanitize_copied_skill_files(dest_root: Path, openclaw_root: Path) -> int:
    replacements = {
        str(openclaw_root): "${OPENCLAW_ROOT}",
        str(openclaw_root).replace("\\", "/"): "${OPENCLAW_ROOT}",
        str(Path.home()): "${HOME}",
        str(Path.home()).replace("\\", "/"): "${HOME}",
    }
    changed = 0
    for path in dest_root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".md", ".txt", ".py", ".ps1", ".sh", ".json", ".yaml", ".yml"}:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            continue

        updated = content
        for old, new in replacements.items():
            updated = updated.replace(old, new)
        if updated != content:
            try:
                path.write_text(updated, encoding="utf-8")
                changed += 1
            except Exception:
                continue
    return changed


def apply_mappings_to_env(
    env_data: dict[str, str],
    config: dict[str, Any],
    include_secrets: bool,
) -> dict[str, str]:
    agent = first_agent(config)
    model_ref = str(agent.get("model", "")).strip()
    provider, model_name = parse_model_ref(model_ref)
    defaults = config.get("agents", {}).get("defaults", {})
    heartbeat_every = defaults.get("heartbeat", {}).get("every", "")
    heartbeat_minutes = parse_duration_to_minutes(str(heartbeat_every))
    env_vars = config.get("env", {}).get("vars", {})
    tool_profile = str(agent.get("tools", {}).get("profile", "")).strip().lower()

    if model_ref:
        env_data["OPENCLAW_SOURCE_MODEL"] = model_ref
    if provider:
        env_data["OPENCLAW_SOURCE_PROVIDER"] = provider
    if heartbeat_minutes:
        env_data["OPENCLAW_HEARTBEAT_MINUTES"] = str(heartbeat_minutes)
    if tool_profile in {"full", "safe", "messaging"}:
        env_data["DEFAULT_TOOL_PROFILE"] = tool_profile

    provider_key_map = {
        "groq": ("GROQ_MODEL", "LLM_DEFAULT_PROVIDER"),
        "openai": ("OPENAI_MODEL", "LLM_DEFAULT_PROVIDER"),
        "xai": ("XAI_MODEL", "LLM_DEFAULT_PROVIDER"),
        "anthropic": ("ANTHROPIC_COMPAT_MODEL", "LLM_DEFAULT_PROVIDER"),
    }
    if provider in provider_key_map:
        model_key, provider_key = provider_key_map[provider]
        if model_name:
            env_data[model_key] = model_name
        if provider == "anthropic":
            env_data[provider_key] = "anthropic_compat"
        else:
            env_data[provider_key] = provider
    elif not provider and model_name:
        env_data["LLM_MODEL"] = model_name
        env_data.setdefault("LLM_DEFAULT_PROVIDER", "custom")

    if include_secrets and isinstance(env_vars, dict):
        secret_keys = {
            "GROQ_API_KEY",
            "OPENAI_API_KEY",
            "XAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "GOOGLE_API_KEY",
        }
        for key in secret_keys:
            if key in env_vars and str(env_vars[key]).strip():
                target = "ANTHROPIC_COMPAT_API_KEY" if key == "ANTHROPIC_API_KEY" else key
                env_data[target] = str(env_vars[key]).strip()

    return env_data


def render_report(
    selected: LoadedConfig,
    all_configs: list[LoadedConfig],
    env_updates: dict[str, str],
    skill_import_results: list[tuple[str, str]],
    node_data: dict[str, Any],
    update_check_data: dict[str, Any],
    report_path: Path,
) -> None:
    agent = first_agent(selected.data)
    defaults = selected.data.get("agents", {}).get("defaults", {})
    model_ref = str(agent.get("model", "")).strip() or "[none]"
    tool_profile = str(agent.get("tools", {}).get("profile", "")).strip() or "[none]"
    skills = agent.get("skills", [])
    skills_count = len(skills) if isinstance(skills, list) else 0
    heartbeat_every = str(defaults.get("heartbeat", {}).get("every", "")).strip() or "[none]"
    context_pruning = defaults.get("contextPruning", {})
    plugins = selected.data.get("plugins", {}).get("entries", {})
    telegram_enabled = plugins.get("telegram", {}).get("enabled")

    lines: list[str] = []
    lines.append("# OpenClaw Bridge Import Report")
    lines.append("")
    lines.append(f"- Source config: `${{OPENCLAW_ROOT}}\\{selected.path.name}`")
    lines.append(f"- Source touched at (UTC): `{selected.touched_at.isoformat()}`")
    lines.append(f"- Model ref: `{model_ref}`")
    lines.append(f"- Tool profile: `{tool_profile}`")
    lines.append(f"- Skill inventory count: `{skills_count}`")
    lines.append(f"- Heartbeat every: `{heartbeat_every}`")
    lines.append(f"- Context pruning: `{json.dumps(context_pruning) if context_pruning else '[none]'}`")
    lines.append(f"- Telegram plugin enabled: `{telegram_enabled}`")
    node_id = str(node_data.get("nodeId", "")).strip() or ""
    node_id_masked = (node_id[:8] + "...") if node_id else "[none]"
    gateway_cfg = node_data.get("gateway", {}) if isinstance(node_data.get("gateway"), dict) else {}
    gateway_host = str(gateway_cfg.get("host", "")).strip() or "[none]"
    gateway_port = str(gateway_cfg.get("port", "")).strip() or "[none]"
    update_checked_at = str(update_check_data.get("lastCheckedAt", "")).strip() or "[none]"
    update_notified = str(update_check_data.get("lastNotifiedVersion", "")).strip() or "[none]"
    lines.append(f"- Node ID (masked): `{node_id_masked}`")
    lines.append(f"- Node gateway: `{gateway_host}:{gateway_port}`")
    lines.append(f"- Last update check: `{update_checked_at}`")
    lines.append(f"- Last notified version: `{update_notified}`")
    lines.append("")
    lines.append("## Config snapshots considered")
    for item in all_configs:
        lines.append(f"- `{item.path.name}` @ `{item.touched_at.isoformat()}`")
    lines.append("")
    lines.append("## Env keys updated")
    for key in sorted(env_updates.keys()):
        if "KEY" in key or "TOKEN" in key or "SECRET" in key:
            lines.append(f"- `{key}` = `[redacted]`")
        else:
            lines.append(f"- `{key}` = `{env_updates[key]}`")
    lines.append("")
    lines.append("## Skill import results")
    if skill_import_results:
        for name, status in skill_import_results:
            lines.append(f"- `{name}`: `{status}`")
    else:
        lines.append("- No skills discovered or copied.")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import OpenClaw profile hints into Agent 1.")
    parser.add_argument("--openclaw-root", default=str(Path.home() / ".openclaw"))
    parser.add_argument("--agent-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--include-secrets", action="store_true", help="Also import API keys from OpenClaw env.vars")
    parser.add_argument("--skip-skill-copy", action="store_true")
    parser.add_argument("--overwrite-skills", action="store_true")
    args = parser.parse_args()

    openclaw_root = Path(args.openclaw_root).resolve()
    agent_root = Path(args.agent_root).resolve()
    env_path = agent_root / ".env"
    env_example_path = agent_root / ".env.example"
    report_path = agent_root / "workspace" / "OPENCLAW_IMPORT.md"
    skill_dest_root = agent_root / "workspace" / "skills"
    node_data = load_optional_json(openclaw_root / "node.json")
    update_check_data = load_optional_json(openclaw_root / "update-check.json")

    configs = discover_configs(openclaw_root)
    if not configs:
        raise SystemExit(f"No valid OpenClaw config snapshots found under {openclaw_root}")
    selected = configs[0]

    base_env = read_env_file(env_path if env_path.exists() else env_example_path)
    before_env = dict(base_env)
    updated_env = apply_mappings_to_env(base_env, selected.data, include_secrets=args.include_secrets)
    if env_path.exists():
        write_env_file(env_path, updated_env)
    else:
        write_env_file(env_path, updated_env)

    skill_results: list[tuple[str, str]] = []
    openclaw_workspace = Path(str(first_agent(selected.data).get("workspace", ""))).resolve()
    if not args.skip_skill_copy and openclaw_workspace.exists():
        skill_dirs = discover_skill_dirs(openclaw_workspace)
        skill_results = copy_skills(skill_dirs, skill_dest_root, overwrite=args.overwrite_skills)
        sanitize_copied_skill_files(skill_dest_root, openclaw_root)

    changed_keys = {key: value for key, value in updated_env.items() if before_env.get(key) != value}
    render_report(selected, configs, changed_keys, skill_results, node_data, update_check_data, report_path)

    print(f"Imported from: {selected.path}")
    print(f"Wrote env: {env_path}")
    print(f"Wrote report: {report_path}")
    if skill_results:
        copied = len([1 for _, status in skill_results if status == "copied"])
        skipped = len(skill_results) - copied
        print(f"Skill copy results: copied={copied} skipped={skipped}")
    else:
        print("Skill copy results: none")
    if args.include_secrets:
        print("Secret import mode: enabled")
    else:
        print("Secret import mode: disabled")


if __name__ == "__main__":
    main()
