from __future__ import annotations

from langchain_openai import ChatOpenAI

from agent1.config import Settings
from agent1.provider_router import LLMRuntimeConfig


def build_openai_compatible_llm(settings: Settings, runtime: LLMRuntimeConfig | None = None) -> ChatOpenAI:
    # Shadow Gateway later: only change LLM_BASE_URL + LLM_API_KEY in .env.
    if runtime is None:
        runtime = LLMRuntimeConfig(
            provider="custom",
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key or "not-needed",
            model=settings.llm_model,
        )

    return ChatOpenAI(
        model=runtime.model,
        api_key=runtime.api_key or "not-needed",
        base_url=runtime.base_url,
        temperature=settings.llm_temperature,
        timeout=settings.llm_timeout_seconds,
        max_tokens=settings.llm_max_tokens,
        max_retries=2,
    )
