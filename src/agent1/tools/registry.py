from __future__ import annotations

import time

from langchain_core.tools import StructuredTool

from agent1.config import Settings
from agent1.memory.manager import MemoryManager
from agent1.tools.approval import ApprovalManager
from agent1.tools.calendar_tool import CalendarTool
from agent1.tools.email_tool import EmailTool
from agent1.tools.safe_files import SafeFileTool
from agent1.tools.safe_shell import SafeShellTool
from agent1.tools.web_tools import WebTools
from agent1.usage_meter import UsageMeter


class ToolRegistry:
    def __init__(
        self,
        settings: Settings,
        memory: MemoryManager,
        approvals: ApprovalManager,
        usage_meter: UsageMeter | None = None,
    ):
        self.settings = settings
        self.memory = memory
        self.approvals = approvals
        self.usage_meter = usage_meter
        self.safe_shell = SafeShellTool(settings=settings, approvals=approvals)
        self.safe_files = SafeFileTool(settings=settings, approvals=approvals)
        self.web = WebTools(settings=settings)
        self.email = EmailTool(settings=settings, approvals=approvals)
        self.calendar = CalendarTool(settings=settings, approvals=approvals)

    def build_for_user(self, user_id: str) -> dict[str, StructuredTool]:
        def tracked(tool_name: str, fn):
            def wrapped(*args, **kwargs):
                started = time.perf_counter()
                success = True
                try:
                    return fn(*args, **kwargs)
                except Exception:
                    success = False
                    raise
                finally:
                    if self.usage_meter:
                        self.usage_meter.record_tool_call(
                            user_id=user_id,
                            tool_name=tool_name,
                            duration_ms=int((time.perf_counter() - started) * 1000),
                            success=success,
                        )

            return wrapped

        def remember_fact(key: str, value: str) -> str:
            return self.memory.remember_fact(user_id=user_id, key=key, value=value)

        def add_note(note: str) -> str:
            return self.memory.add_note(user_id=user_id, note=note)

        def add_task(task: str, due_date: str = "") -> str:
            task_id = self.memory.add_task(user_id=user_id, task=task, due_date=due_date or None)
            return f"Added task {task_id}."

        def list_tasks(status: str = "open") -> str:
            tasks = self.memory.list_tasks(user_id=user_id, status=status)
            if not tasks:
                return "No tasks found."
            return "\n".join([f"- [{item['status']}] {item['id']} | {item['text']}" for item in tasks])

        def complete_task(task_id: str) -> str:
            done = self.memory.complete_task(user_id=user_id, task_id=task_id)
            return "Task marked complete." if done else "Task not found or already completed."

        def recall_memory(query: str, k: int = 4) -> str:
            rows = self.memory.recall(user_id=user_id, query=query, k=k)
            if not rows:
                return "No matching memory items."
            return "\n".join([f"- {row}" for row in rows])

        def list_pending_approvals() -> str:
            rows = self.approvals.list_pending(limit=10)
            if not rows:
                return "No pending approvals."
            return "\n".join(
                [f"- {row.id} | type={row.action_type} | reason={row.reason} | requested_by={row.requested_by}" for row in rows]
            )

        def run_safe_shell(command: str) -> str:
            return self.safe_shell.run(user_id=user_id, command=command)

        def list_files(relative_path: str = ".") -> str:
            return self.safe_files.list_files(user_id=user_id, relative_path=relative_path)

        def read_file(relative_path: str) -> str:
            return self.safe_files.read_file(user_id=user_id, relative_path=relative_path)

        def write_file(relative_path: str, content: str, append: bool = False) -> str:
            return self.safe_files.write_file(
                user_id=user_id,
                relative_path=relative_path,
                content=content,
                append=append,
            )

        def search_web(query: str, max_results: int = 5) -> str:
            return self.web.search_web(user_id=user_id, query=query, max_results=max_results)

        def browse_url(url: str) -> str:
            return self.web.browse_url(user_id=user_id, url=url)

        def read_recent_emails(limit: int = 5) -> str:
            return self.email.read_recent(user_id=user_id, limit=limit)

        def send_email(to: str, subject: str, body: str) -> str:
            return self.email.send_email(user_id=user_id, to=to, subject=subject, body=body)

        def list_upcoming_events(max_results: int = 10) -> str:
            return self.calendar.list_upcoming(user_id=user_id, max_results=max_results)

        def create_calendar_event(
            summary: str,
            start_iso: str,
            end_iso: str,
            description: str = "",
            timezone_name: str = "UTC",
        ) -> str:
            return self.calendar.create_event(
                user_id=user_id,
                summary=summary,
                start_iso=start_iso,
                end_iso=end_iso,
                description=description,
                timezone_name=timezone_name,
            )

        remember_fact_fn = tracked("remember_fact", remember_fact)
        add_note_fn = tracked("add_note", add_note)
        add_task_fn = tracked("add_task", add_task)
        list_tasks_fn = tracked("list_tasks", list_tasks)
        complete_task_fn = tracked("complete_task", complete_task)
        recall_memory_fn = tracked("recall_memory", recall_memory)
        list_pending_approvals_fn = tracked("list_pending_approvals", list_pending_approvals)
        run_safe_shell_fn = tracked("safe_shell", run_safe_shell)
        list_files_fn = tracked("list_files", list_files)
        read_file_fn = tracked("read_file", read_file)
        write_file_fn = tracked("write_file", write_file)
        search_web_fn = tracked("search_web", search_web)
        browse_url_fn = tracked("browse_url", browse_url)
        read_recent_emails_fn = tracked("read_recent_emails", read_recent_emails)
        send_email_fn = tracked("send_email", send_email)
        list_upcoming_events_fn = tracked("list_upcoming_events", list_upcoming_events)
        create_calendar_event_fn = tracked("create_calendar_event", create_calendar_event)

        return {
            "remember_fact": StructuredTool.from_function(
                func=remember_fact_fn,
                name="remember_fact",
                description="Save a durable user fact in memory. Inputs: key, value.",
            ),
            "add_note": StructuredTool.from_function(
                func=add_note_fn,
                name="add_note",
                description="Save a short note in user memory. Input: note.",
            ),
            "add_task": StructuredTool.from_function(
                func=add_task_fn,
                name="add_task",
                description="Create an open task. Inputs: task, optional due_date.",
            ),
            "list_tasks": StructuredTool.from_function(
                func=list_tasks_fn,
                name="list_tasks",
                description="List tasks. Input: status=open|done|all.",
            ),
            "complete_task": StructuredTool.from_function(
                func=complete_task_fn,
                name="complete_task",
                description="Mark task complete by task_id.",
            ),
            "recall_memory": StructuredTool.from_function(
                func=recall_memory_fn,
                name="recall_memory",
                description="Vector recall from memory. Inputs: query, optional k.",
            ),
            "list_pending_approvals": StructuredTool.from_function(
                func=list_pending_approvals_fn,
                name="list_pending_approvals",
                description="List pending risky action approvals.",
            ),
            "safe_shell": StructuredTool.from_function(
                func=run_safe_shell_fn,
                name="safe_shell",
                description=(
                    "Run allowlisted shell command inside sandboxed working directory. "
                    "Requires human approval unless AUTO_APPROVE_RISKY_ACTIONS=true."
                ),
            ),
            "list_files": StructuredTool.from_function(
                func=list_files_fn,
                name="list_files",
                description="List files under SAFE_FILES_ROOT. Input: relative_path.",
            ),
            "read_file": StructuredTool.from_function(
                func=read_file_fn,
                name="read_file",
                description="Read a UTF-8 file under SAFE_FILES_ROOT. Input: relative_path.",
            ),
            "write_file": StructuredTool.from_function(
                func=write_file_fn,
                name="write_file",
                description=(
                    "Write a UTF-8 file under SAFE_FILES_ROOT. Inputs: relative_path, content, append. "
                    "Requires human approval unless AUTO_APPROVE_RISKY_ACTIONS=true."
                ),
            ),
            "search_web": StructuredTool.from_function(
                func=search_web_fn,
                name="search_web",
                description="Search the web using DuckDuckGo. Inputs: query, optional max_results.",
            ),
            "browse_url": StructuredTool.from_function(
                func=browse_url_fn,
                name="browse_url",
                description="Open a URL using Playwright (fallback: HTTP scrape). Input: url.",
            ),
            "read_recent_emails": StructuredTool.from_function(
                func=read_recent_emails_fn,
                name="read_recent_emails",
                description="Read recent emails from configured inbox. Input: limit.",
            ),
            "send_email": StructuredTool.from_function(
                func=send_email_fn,
                name="send_email",
                description=(
                    "Send outbound email with configured account. Inputs: to, subject, body. "
                    "Requires human approval unless AUTO_APPROVE_RISKY_ACTIONS=true."
                ),
            ),
            "list_upcoming_events": StructuredTool.from_function(
                func=list_upcoming_events_fn,
                name="list_upcoming_events",
                description="List upcoming Google Calendar events. Input: max_results.",
            ),
            "create_calendar_event": StructuredTool.from_function(
                func=create_calendar_event_fn,
                name="create_calendar_event",
                description=(
                    "Create Google Calendar event. Inputs: summary, start_iso, end_iso, optional description, timezone_name. "
                    "Requires human approval unless AUTO_APPROVE_RISKY_ACTIONS=true."
                ),
            ),
        }
