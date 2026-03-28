from __future__ import annotations

import logging
import time
from typing import Literal, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from agent1.approvals_bridge import ExternalApprovalsBridge
from agent1.config import Settings
from agent1.diagnostics import Doctor
from agent1.llm import build_openai_compatible_llm
from agent1.memory.manager import MemoryManager
from agent1.policy import ToolPolicyManager
from agent1.plugins.manager import PluginManager
from agent1.provider_router import ProviderRouter
from agent1.prompts import (
    EXECUTOR_PROMPT,
    GENERALIST_PROMPT,
    MORNING_BRIEFING_PROMPT,
    ORCHESTRATOR_SOUL,
    RESEARCHER_PROMPT,
    ROUTER_PROMPT,
    SUMMARIZER_PROMPT,
)
from agent1.session_engine import SessionEngine
from agent1.tools.approval import ApprovalManager
from agent1.tools.loader import UniversalSkillLoader
from agent1.tools.registry import ToolRegistry
from agent1.usage_meter import UsageMeter
from agent1.workspace_profile import WorkspaceProfile

logger = logging.getLogger(__name__)


class RouteDecision(BaseModel):
    route: Literal["researcher", "executor", "summarizer", "general"] = Field(
        description="The best specialist route for this request."
    )
    handoff: str = Field(description="One-sentence specialist brief.")


class AgentState(TypedDict):
    user_id: str
    user_input: str
    memory_context: str
    route: str
    handoff: str
    specialist_output: str
    final_output: str


def _content_to_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out: list[str] = []
        for item in content:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict):
                if "text" in item:
                    out.append(str(item["text"]))
        return "\n".join(out).strip()
    return str(content)


class AgentOrchestrator:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.settings.ensure_paths()
        self.providers = ProviderRouter(settings)
        self.policy_manager = ToolPolicyManager(settings)
        self.usage_meter = UsageMeter(settings)
        self.doctor = Doctor(settings)
        self.plugins = PluginManager(settings)
        self.workspace_profile = WorkspaceProfile(settings.workspace_profile_path)
        self.workspace_profile.ensure_scaffold()
        self.memory = MemoryManager(settings.markdown_memory_path, settings.vector_memory_path)
        self.sessions = SessionEngine(settings)
        self.external_approvals = ExternalApprovalsBridge(settings)
        self.approvals = ApprovalManager(settings.approval_store_path, external_bridge=self.external_approvals)
        self.tools = ToolRegistry(settings=settings, memory=self.memory, approvals=self.approvals, usage_meter=self.usage_meter)
        self.skill_loader = UniversalSkillLoader(
            settings=settings,
            policy_manager=self.policy_manager,
            usage_meter=self.usage_meter,
        )
        self.skill_loader.reindex(force=True)
        self.graph = self._build_graph()

    def _llm_for_user(self, user_id: str):
        runtime = self.providers.get_runtime_config(user_id)
        return build_openai_compatible_llm(self.settings, runtime=runtime)

    def _system_context(self, specialist_prompt: str = "") -> str:
        workspace_context = self.workspace_profile.core_context()
        parts = [ORCHESTRATOR_SOUL]
        if workspace_context:
            parts.append(f"Workspace context:\n{workspace_context}")
        if specialist_prompt:
            parts.append(specialist_prompt)
        return "\n\n".join(parts)

    def _build_graph(self):
        graph = StateGraph(AgentState)
        graph.add_node("load_memory", self._load_memory_node)
        graph.add_node("route", self._route_node)
        graph.add_node("researcher", self._researcher_node)
        graph.add_node("executor", self._executor_node)
        graph.add_node("summarizer", self._summarizer_node)
        graph.add_node("general", self._general_node)
        graph.add_node("finalize", self._finalize_node)
        graph.add_node("save", self._save_node)

        graph.add_edge(START, "load_memory")
        graph.add_edge("load_memory", "route")
        graph.add_conditional_edges(
            "route",
            self._select_route,
            {
                "researcher": "researcher",
                "executor": "executor",
                "summarizer": "summarizer",
                "general": "general",
            },
        )
        graph.add_edge("researcher", "finalize")
        graph.add_edge("executor", "finalize")
        graph.add_edge("summarizer", "finalize")
        graph.add_edge("general", "finalize")
        graph.add_edge("finalize", "save")
        graph.add_edge("save", END)
        return graph.compile()

    def _heuristic_route(self, user_input: str) -> str | None:
        text = user_input.lower()
        research_markers = ("search", "look up", "find on web", "browse", "news", "research")
        execute_markers = ("run", "shell", "command", "file", "write", "email", "calendar", "create event")
        summarize_markers = ("summarize", "summary", "recap", "briefing", "digest", "what happened")

        if any(marker in text for marker in summarize_markers):
            return "summarizer"
        if any(marker in text for marker in execute_markers):
            return "executor"
        if any(marker in text for marker in research_markers):
            return "researcher"
        return None

    def _load_memory_node(self, state: AgentState) -> dict[str, str]:
        memory_context = self.memory.build_context(state["user_id"], state["user_input"])
        return {"memory_context": memory_context}

    def _route_node(self, state: AgentState) -> dict[str, str]:
        heuristic = self._heuristic_route(state["user_input"])
        if heuristic:
            return {"route": heuristic, "handoff": "Fast heuristic route selected."}

        llm = self._llm_for_user(state["user_id"])
        router = llm.with_structured_output(RouteDecision)
        started = time.perf_counter()
        try:
            decision = router.invoke(
                [
                    SystemMessage(content=self._system_context(ROUTER_PROMPT)),
                    HumanMessage(
                        content=(
                            f"User request:\n{state['user_input']}\n\n"
                            f"Relevant memory:\n{state['memory_context']}"
                        )
                    ),
                ]
            )
            runtime = self.providers.get_runtime_config(state["user_id"])
            self.usage_meter.record_llm_call(
                user_id=state["user_id"],
                provider=runtime.provider,
                model=runtime.model,
                stage="route",
                duration_ms=int((time.perf_counter() - started) * 1000),
                response=None,
                extra={"route": decision.route},
            )
            return {"route": decision.route, "handoff": decision.handoff}
        except Exception as exc:
            logger.warning("Router fallback due to error: %s", exc)
            return {"route": "general", "handoff": "Fallback route after router error."}

    @staticmethod
    def _select_route(state: AgentState) -> str:
        route = state.get("route", "general")
        if route not in {"researcher", "executor", "summarizer", "general"}:
            return "general"
        return route

    def _build_specialist(self, user_id: str, role: Literal["researcher", "executor", "summarizer", "general"]):
        llm = self._llm_for_user(user_id)
        all_tools = self.tools.build_for_user(user_id)
        dynamic_tools = self.skill_loader.get_tools(user_id=user_id, refresh=True)
        by_role = {
            "researcher": [
                "search_web",
                "browse_url",
                "recall_memory",
                "remember_fact",
                "add_note",
                "list_tasks",
            ],
            "executor": [
                "safe_shell",
                "list_files",
                "read_file",
                "write_file",
                "read_recent_emails",
                "send_email",
                "list_upcoming_events",
                "create_calendar_event",
                "remember_fact",
                "add_note",
                "add_task",
                "list_tasks",
                "complete_task",
                "list_pending_approvals",
            ],
            "summarizer": [
                "recall_memory",
                "list_tasks",
                "list_pending_approvals",
            ],
            "general": [
                "recall_memory",
                "remember_fact",
                "add_note",
                "add_task",
                "list_tasks",
                "complete_task",
                "list_pending_approvals",
            ],
        }
        prompts = {
            "researcher": RESEARCHER_PROMPT,
            "executor": EXECUTOR_PROMPT,
            "summarizer": SUMMARIZER_PROMPT,
            "general": GENERALIST_PROMPT,
        }
        selected = [all_tools[name] for name in by_role[role] if name in all_tools]
        # Dynamic skills are injected into LangGraph's ToolNode via create_react_agent.
        selected.extend(dynamic_tools.values())

        deduped = []
        seen_names: set[str] = set()
        for tool in selected:
            if tool.name in seen_names:
                continue
            allowed, _reason = self.policy_manager.is_tool_allowed(user_id, tool.name)
            if not allowed:
                continue
            seen_names.add(tool.name)
            deduped.append(tool)

        specialist_prompt = self._system_context(prompts[role])
        return create_react_agent(llm, deduped, prompt=specialist_prompt)

    def _run_specialist(self, state: AgentState, role: Literal["researcher", "executor", "summarizer", "general"]) -> str:
        specialist = self._build_specialist(user_id=state["user_id"], role=role)
        payload = (
            f"Coordinator handoff: {state['handoff']}\n\n"
            f"User request: {state['user_input']}\n\n"
            f"Memory context:\n{state['memory_context']}\n\n"
            "Solve the request now."
        )
        started = time.perf_counter()
        try:
            result = specialist.invoke({"messages": [HumanMessage(content=payload)]})
        except Exception as exc:
            logger.exception("Specialist invocation failed")
            return f"Specialist error: {exc}"

        messages = result.get("messages", [])
        runtime = self.providers.get_runtime_config(state["user_id"])
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                self.usage_meter.record_llm_call(
                    user_id=state["user_id"],
                    provider=runtime.provider,
                    model=runtime.model,
                    stage=f"specialist_{role}",
                    duration_ms=int((time.perf_counter() - started) * 1000),
                    response=msg,
                )
                return _content_to_text(msg.content)
        return "No specialist output returned."

    def _researcher_node(self, state: AgentState) -> dict[str, str]:
        return {"specialist_output": self._run_specialist(state, "researcher")}

    def _executor_node(self, state: AgentState) -> dict[str, str]:
        return {"specialist_output": self._run_specialist(state, "executor")}

    def _summarizer_node(self, state: AgentState) -> dict[str, str]:
        return {"specialist_output": self._run_specialist(state, "summarizer")}

    def _general_node(self, state: AgentState) -> dict[str, str]:
        return {"specialist_output": self._run_specialist(state, "general")}

    def _finalize_node(self, state: AgentState) -> dict[str, str]:
        return {"final_output": state["specialist_output"].strip()}

    def _save_node(self, state: AgentState) -> dict[str, str]:
        self.memory.store_interaction(
            user_id=state["user_id"],
            user_text=state["user_input"],
            assistant_text=state["final_output"],
        )
        return {}

    def _process_message_core(self, user_id: str, user_input: str) -> str:
        initial: AgentState = {
            "user_id": str(user_id),
            "user_input": user_input,
            "memory_context": "",
            "route": "general",
            "handoff": "",
            "specialist_output": "",
            "final_output": "",
        }
        result = self.graph.invoke(initial, config={"recursion_limit": 80})
        return result.get("final_output", "No response generated.")

    def process_message(self, user_id: str, user_input: str) -> str:
        return self.sessions.run_sync(user_id=str(user_id), user_input=user_input, handler=self._process_message_core)

    def _pending_approvals_for_user(self, user_id: str) -> str:
        rows = [item for item in self.approvals.list_pending(limit=30) if item.requested_by == str(user_id)]
        if not rows:
            return "None"
        return "\n".join([f"- {row.id} | {row.action_type} | {row.reason}" for row in rows])

    def get_pending_approvals_summary(self, user_id: str) -> str:
        return self._pending_approvals_for_user(user_id)

    def generate_morning_briefing(self, user_id: str) -> str:
        context = self.memory.build_context(user_id=user_id, query="morning briefing")
        pending = self._pending_approvals_for_user(user_id)

        fallback_tasks = self.memory.list_tasks(user_id=user_id, status="open")
        fallback = "Good morning. No open tasks yet. Ask me to plan your day."
        if fallback_tasks:
            fallback = "Good morning. Open tasks:\n" + "\n".join(
                [f"- {item['id']}: {item['text']}" for item in fallback_tasks[:5]]
            )

        try:
            llm = self._llm_for_user(user_id)
            started = time.perf_counter()
            response = llm.invoke(
                [
                    SystemMessage(content=self._system_context(MORNING_BRIEFING_PROMPT)),
                    HumanMessage(content=f"User id: {user_id}\nPending approvals:\n{pending}\n\nContext:\n{context}"),
                ]
            )
            runtime = self.providers.get_runtime_config(user_id)
            self.usage_meter.record_llm_call(
                user_id=user_id,
                provider=runtime.provider,
                model=runtime.model,
                stage="morning_briefing",
                duration_ms=int((time.perf_counter() - started) * 1000),
                response=response,
            )
            text = _content_to_text(response.content).strip()
            return text or fallback
        except Exception as exc:
            logger.warning("Morning briefing generation failed: %s", exc)
            return fallback

    def list_available_providers(self) -> list[str]:
        return self.providers.list_available_provider_names()

    def get_provider_status(self, user_id: str) -> dict[str, str]:
        return self.providers.get_user_status(user_id)

    def set_provider_for_user(self, user_id: str, provider: str) -> tuple[bool, str]:
        return self.providers.set_user_provider(user_id, provider)

    def set_model_for_user(self, user_id: str, model: str) -> tuple[bool, str]:
        return self.providers.set_user_model(user_id, model)

    def clear_model_override_for_user(self, user_id: str) -> tuple[bool, str]:
        return self.providers.clear_user_model_override(user_id)

    def list_dynamic_skill_tools(self) -> list[str]:
        return self.skill_loader.get_tool_names(refresh=True)

    def list_dynamic_skill_states(self) -> list[dict[str, str]]:
        return self.skill_loader.list_skill_states(refresh=True)

    def set_skill_enabled(self, folder_name: str, enabled: bool) -> tuple[bool, str]:
        return self.skill_loader.set_skill_enabled(folder_name=folder_name, enabled=enabled)

    def list_tool_profiles(self) -> list[str]:
        return self.policy_manager.list_profiles()

    def get_tool_policy_status(self, user_id: str) -> dict[str, str]:
        policy = self.policy_manager.get_effective_policy(user_id)
        return {
            "profile": policy.profile,
            "allow_tools": ", ".join(sorted(policy.allow_tools)) or "[none]",
            "deny_tools": ", ".join(sorted(policy.deny_tools)) or "[none]",
            "deny_permissions": ", ".join(sorted(policy.deny_permissions)) or "[none]",
        }

    def set_tool_profile_for_user(self, user_id: str, profile: str) -> tuple[bool, str]:
        return self.policy_manager.set_user_profile(user_id, profile)

    def set_tool_override(self, user_id: str, mode: str, tool_name: str) -> tuple[bool, str]:
        return self.policy_manager.set_user_tool_override(user_id=user_id, mode=mode, tool_name=tool_name)

    def set_permission_override(self, user_id: str, mode: str, permission: str) -> tuple[bool, str]:
        return self.policy_manager.set_user_permission_override(user_id=user_id, mode=mode, permission=permission)

    def clear_policy_overrides(self, user_id: str) -> tuple[bool, str]:
        return self.policy_manager.clear_user_overrides(user_id=user_id)

    def doctor_report(self) -> str:
        return self.doctor.report_text()

    def usage_report(self, user_id: str) -> str:
        return self.usage_meter.summary_text(user_id=user_id)

    def list_plugins(self) -> list[dict[str, str]]:
        rows = self.plugins.list_plugins()
        return [
            {
                "name": row.name,
                "source_type": row.source_type,
                "installed_at": row.installed_at,
                "pin_ref": row.pin_ref or "[none]",
                "enabled": "yes" if row.enabled else "no",
                "skills": ", ".join(row.skill_folders),
            }
            for row in rows
        ]

    def install_plugin(self, source: str, name: str = "", ref: str = "") -> tuple[bool, str]:
        ok, message = self.plugins.install_plugin(source=source, name=name, ref=ref)
        if ok:
            self.skill_loader.reindex(force=True)
        return ok, message

    def update_plugin(self, name: str) -> tuple[bool, str]:
        ok, message = self.plugins.update_plugin(name=name)
        if ok:
            self.skill_loader.reindex(force=True)
        return ok, message

    def set_plugin_pin(self, name: str, ref: str) -> tuple[bool, str]:
        return self.plugins.set_plugin_pin(name=name, ref=ref)

    def set_plugin_enabled(self, name: str, enabled: bool) -> tuple[bool, str]:
        ok, message, skill_folders = self.plugins.set_plugin_enabled(name=name, enabled=enabled)
        if not ok:
            return False, message
        for folder in skill_folders:
            self.skill_loader.set_skill_enabled(folder_name=folder, enabled=enabled)
        self.skill_loader.reindex(force=True)
        return True, message

    def uninstall_plugin(self, name: str) -> tuple[bool, str]:
        ok, message = self.plugins.uninstall_plugin(name=name)
        if ok:
            self.skill_loader.reindex(force=True)
        return ok, message

    def list_session_jobs(self, user_id: str, limit: int = 10) -> list[dict[str, str]]:
        rows = self.sessions.list_jobs(user_id=user_id, limit=limit)
        return [
            {
                "id": row.id,
                "status": row.status,
                "created_ts": str(row.created_ts),
                "completed_ts": str(row.completed_ts),
                "error": row.error or "",
                "output_preview": row.output_preview or "",
            }
            for row in rows
        ]

    def resume_session_job(self, job_id: str) -> tuple[bool, str]:
        return self.sessions.resume_job(job_id=job_id, handler=self._process_message_core)
