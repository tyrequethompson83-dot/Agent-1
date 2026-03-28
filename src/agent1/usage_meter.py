from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

from agent1.config import Settings


def extract_usage_metadata(response: Any) -> dict[str, Any]:
    usage: dict[str, Any] = {}

    usage_meta = getattr(response, "usage_metadata", None)
    if isinstance(usage_meta, dict):
        usage.update(usage_meta)

    response_meta = getattr(response, "response_metadata", None)
    if isinstance(response_meta, dict):
        token_usage = response_meta.get("token_usage")
        if isinstance(token_usage, dict):
            usage.update(token_usage)

    if not usage and isinstance(response, dict):
        maybe = response.get("usage_metadata") or response.get("token_usage")
        if isinstance(maybe, dict):
            usage.update(maybe)

    return usage


MODEL_PRICING_PER_1K: dict[str, tuple[float, float]] = {
    "gpt-4o": (0.005, 0.015),
    "gpt-4o-mini": (0.00015, 0.0006),
    "claude-3-5-sonnet-latest": (0.003, 0.015),
    "grok-3-latest": (0.003, 0.015),
    "llama-3.3-70b-versatile": (0.00059, 0.00079),
}


def _extract_token_pair(usage: dict[str, Any]) -> tuple[int, int]:
    def _safe_int(value: Any) -> int:
        try:
            return int(value or 0)
        except Exception:
            return 0

    prompt = _safe_int(
        usage.get("input_tokens")
        or usage.get("prompt_tokens")
        or usage.get("input_token_count")
        or 0
    )
    completion = _safe_int(
        usage.get("output_tokens")
        or usage.get("completion_tokens")
        or usage.get("output_token_count")
        or 0
    )
    return prompt, completion


def _estimate_cost_usd(model: str, usage: dict[str, Any]) -> float:
    model_l = (model or "").strip().lower()
    if model_l in MODEL_PRICING_PER_1K:
        in_rate, out_rate = MODEL_PRICING_PER_1K[model_l]
    else:
        # Fallback heuristic for unknown models.
        in_rate, out_rate = (0.002, 0.006)
    prompt_tokens, completion_tokens = _extract_token_pair(usage)
    in_cost = (prompt_tokens / 1000.0) * in_rate
    out_cost = (completion_tokens / 1000.0) * out_rate
    return round(in_cost + out_cost, 8)


class UsageMeter:
    def __init__(self, settings: Settings):
        self.path: Path = settings.usage_meter_path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def record_llm_call(
        self,
        user_id: str,
        provider: str,
        model: str,
        stage: str,
        duration_ms: int,
        response: Any = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        usage = extract_usage_metadata(response)
        est_cost = _estimate_cost_usd(model=model, usage=usage)
        payload = {
            "ts": int(time.time()),
            "event": "llm_call",
            "user_id": str(user_id),
            "provider": provider,
            "model": model,
            "stage": stage,
            "duration_ms": int(duration_ms),
            "usage": usage,
            "estimated_cost_usd": est_cost,
            "extra": extra or {},
        }
        with self._lock:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, ensure_ascii=True) + "\n")

    def record_tool_call(
        self,
        user_id: str,
        tool_name: str,
        duration_ms: int,
        success: bool,
        extra: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "ts": int(time.time()),
            "event": "tool_call",
            "user_id": str(user_id),
            "tool_name": tool_name,
            "duration_ms": int(duration_ms),
            "success": bool(success),
            "extra": extra or {},
        }
        with self._lock:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, ensure_ascii=True) + "\n")

    def summary_text(self, user_id: str | None = None, max_lines: int = 5000) -> str:
        if not self.path.exists():
            return "No usage data yet."

        with self._lock:
            lines = self.path.read_text(encoding="utf-8").splitlines()[-max_lines:]

        llm_calls = 0
        tool_calls = 0
        total_cost = 0.0
        by_model: dict[str, float] = {}
        by_tool: dict[str, int] = {}

        for line in lines:
            try:
                row = json.loads(line)
            except Exception:
                continue
            if user_id and str(row.get("user_id", "")) != str(user_id):
                continue
            event = str(row.get("event", ""))
            if event == "llm_call":
                llm_calls += 1
                cost = float(row.get("estimated_cost_usd", 0.0) or 0.0)
                total_cost += cost
                model = str(row.get("model", "unknown"))
                by_model[model] = by_model.get(model, 0.0) + cost
            elif event == "tool_call":
                tool_calls += 1
                tool = str(row.get("tool_name", "unknown"))
                by_tool[tool] = by_tool.get(tool, 0) + 1

        model_rows = ", ".join([f"{name}=${value:.4f}" for name, value in sorted(by_model.items(), key=lambda x: x[0])]) or "[none]"
        top_tools = sorted(by_tool.items(), key=lambda item: item[1], reverse=True)[:10]
        tool_rows = ", ".join([f"{name}:{count}" for name, count in top_tools]) or "[none]"

        return (
            "Usage Summary\n"
            f"- LLM calls: {llm_calls}\n"
            f"- Tool calls: {tool_calls}\n"
            f"- Estimated LLM cost: ${total_cost:.4f}\n"
            f"- Cost by model: {model_rows}\n"
            f"- Top tools: {tool_rows}"
        )
