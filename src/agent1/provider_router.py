from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass
from pathlib import Path

from agent1.config import Settings


@dataclass
class LLMRuntimeConfig:
    provider: str
    base_url: str
    api_key: str
    model: str


@dataclass
class ProviderProfile:
    name: str
    base_url: str
    api_key: str
    model: str


class ProviderRouter:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.store_path: Path = settings.provider_preferences_path
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        if not self.store_path.exists():
            self._save({"users": {}})

    def _load(self) -> dict:
        if not self.store_path.exists():
            return {"users": {}}
        raw = self.store_path.read_text(encoding="utf-8").strip()
        if not raw:
            return {"users": {}}
        return json.loads(raw)

    def _save(self, data: dict) -> None:
        self.store_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _profiles(self) -> dict[str, ProviderProfile]:
        return {
            "custom": ProviderProfile(
                name="custom",
                base_url=self.settings.llm_base_url,
                api_key=self.settings.llm_api_key,
                model=self.settings.llm_model,
            ),
            "openai": ProviderProfile(
                name="openai",
                base_url=self.settings.openai_base_url,
                api_key=self.settings.openai_api_key,
                model=self.settings.openai_model,
            ),
            "groq": ProviderProfile(
                name="groq",
                base_url=self.settings.groq_base_url,
                api_key=self.settings.groq_api_key,
                model=self.settings.groq_model,
            ),
            "xai": ProviderProfile(
                name="xai",
                base_url=self.settings.xai_base_url,
                api_key=self.settings.xai_api_key,
                model=self.settings.xai_model,
            ),
            "anthropic_compat": ProviderProfile(
                name="anthropic_compat",
                base_url=self.settings.anthropic_compat_base_url,
                api_key=self.settings.anthropic_compat_api_key,
                model=self.settings.anthropic_compat_model,
            ),
            "ollama": ProviderProfile(
                name="ollama",
                base_url=self.settings.ollama_base_url,
                api_key=self.settings.ollama_api_key,
                model=self.settings.ollama_model,
            ),
        }

    @staticmethod
    def _is_enabled(name: str, profile: ProviderProfile) -> bool:
        if not (profile.base_url.strip() and profile.model.strip()):
            return False
        if name in {"openai", "groq", "xai", "anthropic_compat"} and not profile.api_key.strip():
            return False
        return True

    def list_available_provider_profiles(self) -> dict[str, ProviderProfile]:
        profiles = self._profiles()
        return {name: profile for name, profile in profiles.items() if self._is_enabled(name, profile)}

    def list_available_provider_names(self) -> list[str]:
        return sorted(self.list_available_provider_profiles().keys())

    def _read_user_pref(self, user_id: str) -> dict:
        data = self._load()
        return data.get("users", {}).get(str(user_id), {})

    def get_runtime_config(self, user_id: str) -> LLMRuntimeConfig:
        pref = self._read_user_pref(user_id)
        profiles = self.list_available_provider_profiles()

        preferred_provider = str(pref.get("provider") or self.settings.llm_default_provider or "custom").strip()
        selected_provider = preferred_provider if preferred_provider in profiles else None

        if not selected_provider:
            selected_provider = "custom" if "custom" in profiles else None
        if not selected_provider and profiles:
            selected_provider = sorted(profiles.keys())[0]
        if not selected_provider:
            selected_provider = "custom"
            profiles = self._profiles()

        profile = profiles[selected_provider]
        model_override = str(pref.get("model") or "").strip()
        model = model_override or profile.model

        return LLMRuntimeConfig(
            provider=selected_provider,
            base_url=profile.base_url,
            api_key=profile.api_key or "not-needed",
            model=model,
        )

    def set_user_provider(self, user_id: str, provider: str) -> tuple[bool, str]:
        provider = provider.strip().lower()
        profiles = self.list_available_provider_profiles()
        if provider not in profiles:
            available = ", ".join(sorted(profiles.keys())) or "[none]"
            return False, f"Provider `{provider}` is unavailable. Available: {available}"

        with self._lock:
            data = self._load()
            users = data.setdefault("users", {})
            user_pref = users.setdefault(str(user_id), {})
            user_pref["provider"] = provider
            self._save(data)
        return True, f"Provider set to `{provider}`."

    def set_user_model(self, user_id: str, model: str) -> tuple[bool, str]:
        model = model.strip()
        if not model:
            return False, "Model cannot be empty."
        with self._lock:
            data = self._load()
            users = data.setdefault("users", {})
            user_pref = users.setdefault(str(user_id), {})
            user_pref["model"] = model
            self._save(data)
        return True, f"Model override set to `{model}`."

    def clear_user_model_override(self, user_id: str) -> tuple[bool, str]:
        with self._lock:
            data = self._load()
            users = data.setdefault("users", {})
            user_pref = users.setdefault(str(user_id), {})
            if "model" in user_pref:
                del user_pref["model"]
                self._save(data)
                return True, "Model override cleared."
        return True, "No model override was set."

    def get_user_status(self, user_id: str) -> dict[str, str]:
        runtime = self.get_runtime_config(user_id)
        pref = self._read_user_pref(user_id)
        return {
            "provider": runtime.provider,
            "base_url": runtime.base_url,
            "model": runtime.model,
            "has_model_override": "yes" if pref.get("model") else "no",
            "available_providers": ", ".join(self.list_available_provider_names()),
        }

    def export_profiles(self) -> list[dict]:
        out: list[dict] = []
        for _, profile in sorted(self.list_available_provider_profiles().items()):
            row = asdict(profile)
            row["api_key"] = "***" if row.get("api_key") else ""
            out.append(row)
        return out
