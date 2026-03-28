from __future__ import annotations

from pathlib import Path

from agent1.memory.chroma_store import ChromaMemoryStore
from agent1.memory.markdown_store import MarkdownMemoryStore


class MemoryManager:
    def __init__(self, markdown_path: Path, chroma_path: Path):
        self.markdown = MarkdownMemoryStore(markdown_path)
        self.vector = ChromaMemoryStore(chroma_path)

    def build_context(self, user_id: str, query: str) -> str:
        recent_chat = self.markdown.recent_chat(user_id, max_chars=2200)
        facts = self.markdown.recent_facts(user_id, max_items=20)
        notes = self.markdown.recent_notes(user_id, max_items=15)
        tasks = self.list_tasks(user_id, status="open")
        vector_hits = self.recall(user_id, query, k=4)

        tasks_block = "\n".join([f"- ({task['id']}) {task['text']}" for task in tasks]) or "No open tasks."
        recall_block = "\n".join([f"- {item}" for item in vector_hits]) or "No vector matches."

        return (
            "=== RECENT CHAT ===\n"
            f"{recent_chat or 'No prior chat yet.'}\n\n"
            "=== FACTS ===\n"
            f"{facts or 'No saved facts yet.'}\n\n"
            "=== OPEN TASKS ===\n"
            f"{tasks_block}\n\n"
            "=== NOTES ===\n"
            f"{notes or 'No notes yet.'}\n\n"
            "=== VECTOR RECALL ===\n"
            f"{recall_block}"
        )

    def store_interaction(self, user_id: str, user_text: str, assistant_text: str) -> None:
        self.markdown.append_chat_turn(user_id=user_id, user_text=user_text, assistant_text=assistant_text)
        self.vector.add_text(user_id=user_id, text=user_text, kind="user_message")
        self.vector.add_text(user_id=user_id, text=assistant_text, kind="assistant_message")

    def remember_fact(self, user_id: str, key: str, value: str) -> str:
        self.markdown.add_fact(user_id, key, value)
        self.vector.add_text(user_id=user_id, text=f"{key}: {value}", kind="fact")
        return f"Saved fact `{key}`."

    def add_note(self, user_id: str, note: str) -> str:
        self.markdown.add_note(user_id, note)
        self.vector.add_text(user_id=user_id, text=note, kind="note")
        return "Saved note."

    def add_task(self, user_id: str, task: str, due_date: str | None = None) -> str:
        task_id = self.markdown.add_task(user_id, task, due_date)
        self.vector.add_text(user_id=user_id, text=f"Task {task_id}: {task}", kind="task")
        return task_id

    def list_tasks(self, user_id: str, status: str = "open") -> list[dict[str, str]]:
        return self.markdown.list_tasks(user_id, status=status)

    def complete_task(self, user_id: str, task_id: str) -> bool:
        return self.markdown.complete_task(user_id, task_id)

    def recall(self, user_id: str, query: str, k: int = 4) -> list[str]:
        return self.vector.search(user_id=user_id, query=query, k=k)

    def known_user_ids(self) -> list[str]:
        return self.markdown.list_known_user_ids()

