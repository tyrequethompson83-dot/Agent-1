from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from agent1.agents.orchestrator import AgentOrchestrator
from agent1.config import Settings
from agent1.interfaces.base import ChatAdapter
from agent1.scheduler.proactive import ProactiveScheduler

logger = logging.getLogger(__name__)


class TelegramBotAdapter(ChatAdapter):
    def __init__(self, settings: Settings, orchestrator: AgentOrchestrator):
        self.settings = settings
        self.orchestrator = orchestrator
        self.approvals = orchestrator.approvals
        self.scheduler = ProactiveScheduler(
            settings=settings,
            orchestrator=orchestrator,
            send_message=self._send_message,
        )
        self.application = (
            Application.builder()
            .token(settings.telegram_bot_token)
            .post_init(self._on_startup)
            .post_shutdown(self._on_shutdown)
            .build()
        )
        self._register_handlers()

    def _register_handlers(self) -> None:
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("providers", self.providers_command))
        self.application.add_handler(CommandHandler("provider", self.provider_command))
        self.application.add_handler(CommandHandler("model", self.model_command))
        self.application.add_handler(CommandHandler("profile", self.profile_command))
        self.application.add_handler(CommandHandler("policy", self.policy_command))
        self.application.add_handler(CommandHandler("policy_set", self.policy_set_command))
        self.application.add_handler(CommandHandler("skills", self.skills_command))
        self.application.add_handler(CommandHandler("skill_enable", self.skill_enable_command))
        self.application.add_handler(CommandHandler("skill_disable", self.skill_disable_command))
        self.application.add_handler(CommandHandler("plugins", self.plugins_command))
        self.application.add_handler(CommandHandler("plugin_install", self.plugin_install_command))
        self.application.add_handler(CommandHandler("plugin_update", self.plugin_update_command))
        self.application.add_handler(CommandHandler("plugin_uninstall", self.plugin_uninstall_command))
        self.application.add_handler(CommandHandler("plugin_pin", self.plugin_pin_command))
        self.application.add_handler(CommandHandler("plugin_enable", self.plugin_enable_command))
        self.application.add_handler(CommandHandler("plugin_disable", self.plugin_disable_command))
        self.application.add_handler(CommandHandler("doctor", self.doctor_command))
        self.application.add_handler(CommandHandler("doctor_fix", self.doctor_fix_command))
        self.application.add_handler(CommandHandler("usage", self.usage_command))
        self.application.add_handler(CommandHandler("approve", self.approve_command))
        self.application.add_handler(CommandHandler("deny", self.deny_command))
        self.application.add_handler(CommandHandler("pending", self.pending_command))
        self.application.add_handler(CommandHandler("tasks", self.tasks_command))
        self.application.add_handler(CommandHandler("policy_tool", self.policy_tool_command))
        self.application.add_handler(CommandHandler("policy_permission", self.policy_permission_command))
        self.application.add_handler(CommandHandler("policy_reset", self.policy_reset_command))
        self.application.add_handler(CommandHandler("jobs", self.jobs_command))
        self.application.add_handler(CommandHandler("resume_job", self.resume_job_command))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.message_handler))

    @staticmethod
    def _chunk_text(text: str, chunk_size: int = 3900) -> list[str]:
        text = text or ""
        if len(text) <= chunk_size:
            return [text]
        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start = end
        return chunks

    async def _send_message(self, chat_id: int, text: str) -> None:
        for chunk in self._chunk_text(text):
            await self.application.bot.send_message(chat_id=chat_id, text=chunk, disable_web_page_preview=True)

    def _is_allowed(self, user_id: str) -> bool:
        allowed = self.settings.allowed_telegram_user_ids
        if not allowed:
            return True
        return str(user_id) in allowed

    async def _deny_if_blocked(self, update: Update) -> bool:
        user = update.effective_user
        user_id = str(user.id) if user else ""
        if self._is_allowed(user_id):
            return False
        if update.message:
            await update.message.reply_text("Access denied for this bot.")
        return True

    def _track_subscriber(self, update: Update) -> None:
        user = update.effective_user
        chat = update.effective_chat
        if not user or not chat:
            return
        self.scheduler.register_subscriber(str(user.id), int(chat.id))

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._deny_if_blocked(update):
            return
        self._track_subscriber(update)
        await update.message.reply_text(
            "Agent 1 online.\n"
            "Use /help for commands.\n"
            "Risky actions require /approve <id>."
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._deny_if_blocked(update):
            return
        self._track_subscriber(update)
        text = (
            "Commands:\n"
            "/providers - List configured model providers\n"
            "/provider [name] - Show or switch your provider\n"
            "/model [name|default] - Show or set model override\n"
            "/profile - Show your current provider/model profile\n"
            "/policy - Show your tool policy profile\n"
            "/policy_set <full|safe|messaging> - Set your tool policy profile\n"
            "/skills - List discovered skills and status\n"
            "/skill_enable <folder> - Enable a skill folder\n"
            "/skill_disable <folder> - Disable a skill folder\n"
            "/plugins - List installed plugins\n"
            "/plugin_install <source> [name] [ref] - Install plugin from local path or git url\n"
            "/plugin_update <name> - Reinstall plugin from its saved source\n"
            "/plugin_uninstall <name> - Remove installed plugin and linked skills\n"
            "/plugin_pin <name> <ref|clear> - Pin plugin updates to a version/tag/commit\n"
            "/plugin_enable <name> - Enable a plugin's skill set\n"
            "/plugin_disable <name> - Disable a plugin's skill set\n"
            "/doctor - Run runtime diagnostics\n"
            "/doctor_fix - Apply quick runtime fixes then re-run doctor\n"
            "/usage - Show usage/cost summary\n"
            "/approve <id> - Approve a pending risky action\n"
            "/deny <id> [reason] - Deny a pending risky action\n"
            "/pending - List pending approvals\n"
            "/tasks - List open tasks\n"
            "/policy_tool <allow|deny|clear> <tool> - Override one tool policy\n"
            "/policy_permission <allow|deny|clear> <permission> - Override one permission policy\n"
            "/policy_reset - Clear custom policy overrides\n"
            "/jobs - List recent session jobs\n"
            "/resume_job <job_id> - Re-run a completed/failed job\n"
            "/help - Show this help\n\n"
            "Send any normal message to run the agent."
        )
        await update.message.reply_text(text)

    async def plugins_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._deny_if_blocked(update):
            return
        self._track_subscriber(update)
        rows = self.orchestrator.list_plugins()
        if not rows:
            await update.message.reply_text("No plugins installed.")
            return
        text = "Installed plugins:\n" + "\n".join(
            [
                f"- {row['name']} [{row['source_type']}] enabled={row['enabled']} "
                f"pin={row['pin_ref']} skills={row['skills']}"
                for row in rows
            ]
        )
        await update.message.reply_text(text)

    async def plugin_install_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._deny_if_blocked(update):
            return
        self._track_subscriber(update)
        if not context.args:
            await update.message.reply_text("Usage: /plugin_install <source> [name] [ref]")
            return
        source = context.args[0].strip()
        name = context.args[1].strip() if len(context.args) > 1 else ""
        ref = context.args[2].strip() if len(context.args) > 2 else ""
        ok, message = self.orchestrator.install_plugin(source=source, name=name, ref=ref)
        await update.message.reply_text(message if ok else f"Error: {message}")

    async def plugin_update_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._deny_if_blocked(update):
            return
        self._track_subscriber(update)
        if not context.args:
            await update.message.reply_text("Usage: /plugin_update <name>")
            return
        name = context.args[0].strip()
        ok, message = self.orchestrator.update_plugin(name)
        await update.message.reply_text(message if ok else f"Error: {message}")

    async def plugin_uninstall_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._deny_if_blocked(update):
            return
        self._track_subscriber(update)
        if not context.args:
            await update.message.reply_text("Usage: /plugin_uninstall <name>")
            return
        name = context.args[0].strip()
        ok, message = self.orchestrator.uninstall_plugin(name)
        await update.message.reply_text(message if ok else f"Error: {message}")

    async def plugin_pin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._deny_if_blocked(update):
            return
        self._track_subscriber(update)
        if len(context.args) < 2:
            await update.message.reply_text("Usage: /plugin_pin <name> <ref|clear>")
            return
        name = context.args[0].strip()
        ref = " ".join(context.args[1:]).strip()
        if ref.lower() in {"clear", "none", "unset"}:
            ref = ""
        ok, message = self.orchestrator.set_plugin_pin(name=name, ref=ref)
        await update.message.reply_text(message if ok else f"Error: {message}")

    async def plugin_enable_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._deny_if_blocked(update):
            return
        self._track_subscriber(update)
        if not context.args:
            await update.message.reply_text("Usage: /plugin_enable <name>")
            return
        ok, message = self.orchestrator.set_plugin_enabled(name=context.args[0].strip(), enabled=True)
        await update.message.reply_text(message if ok else f"Error: {message}")

    async def plugin_disable_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._deny_if_blocked(update):
            return
        self._track_subscriber(update)
        if not context.args:
            await update.message.reply_text("Usage: /plugin_disable <name>")
            return
        ok, message = self.orchestrator.set_plugin_enabled(name=context.args[0].strip(), enabled=False)
        await update.message.reply_text(message if ok else f"Error: {message}")

    async def doctor_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._deny_if_blocked(update):
            return
        self._track_subscriber(update)
        report = self.orchestrator.doctor_report()
        for chunk in self._chunk_text(report):
            await update.message.reply_text(chunk)

    async def doctor_fix_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._deny_if_blocked(update):
            return
        self._track_subscriber(update)
        fixes = self.orchestrator.doctor.apply_quick_fixes()
        report = self.orchestrator.doctor_report()
        for chunk in self._chunk_text(fixes + "\n\n" + report):
            await update.message.reply_text(chunk)

    async def usage_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._deny_if_blocked(update):
            return
        self._track_subscriber(update)
        user = update.effective_user
        user_id = str(user.id) if user else "unknown"
        text = self.orchestrator.usage_report(user_id=user_id)
        for chunk in self._chunk_text(text):
            await update.message.reply_text(chunk)

    async def policy_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._deny_if_blocked(update):
            return
        self._track_subscriber(update)
        user = update.effective_user
        user_id = str(user.id) if user else "unknown"
        status = self.orchestrator.get_tool_policy_status(user_id)
        profiles = ", ".join(self.orchestrator.list_tool_profiles())
        await update.message.reply_text(
            "Tool Policy\n"
            f"- Profile: {status['profile']}\n"
            f"- Allowed tools: {status['allow_tools']}\n"
            f"- Denied tools: {status['deny_tools']}\n"
            f"- Denied permissions: {status['deny_permissions']}\n"
            f"- Available profiles: {profiles}"
        )

    async def policy_set_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._deny_if_blocked(update):
            return
        self._track_subscriber(update)
        user = update.effective_user
        user_id = str(user.id) if user else "unknown"
        if not context.args:
            await update.message.reply_text("Usage: /policy_set <full|safe|messaging>")
            return
        profile = context.args[0].strip().lower()
        ok, message = self.orchestrator.set_tool_profile_for_user(user_id=user_id, profile=profile)
        await update.message.reply_text(message if ok else f"Error: {message}")

    async def policy_tool_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._deny_if_blocked(update):
            return
        self._track_subscriber(update)
        user = update.effective_user
        user_id = str(user.id) if user else "unknown"
        if len(context.args) < 2:
            await update.message.reply_text("Usage: /policy_tool <allow|deny|clear> <tool_name>")
            return
        mode = context.args[0].strip().lower()
        tool_name = " ".join(context.args[1:]).strip()
        ok, message = self.orchestrator.set_tool_override(user_id=user_id, mode=mode, tool_name=tool_name)
        await update.message.reply_text(message if ok else f"Error: {message}")

    async def policy_permission_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._deny_if_blocked(update):
            return
        self._track_subscriber(update)
        user = update.effective_user
        user_id = str(user.id) if user else "unknown"
        if len(context.args) < 2:
            await update.message.reply_text("Usage: /policy_permission <allow|deny|clear> <permission>")
            return
        mode = context.args[0].strip().lower()
        permission = " ".join(context.args[1:]).strip()
        ok, message = self.orchestrator.set_permission_override(user_id=user_id, mode=mode, permission=permission)
        await update.message.reply_text(message if ok else f"Error: {message}")

    async def policy_reset_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._deny_if_blocked(update):
            return
        self._track_subscriber(update)
        user = update.effective_user
        user_id = str(user.id) if user else "unknown"
        ok, message = self.orchestrator.clear_policy_overrides(user_id=user_id)
        await update.message.reply_text(message if ok else f"Error: {message}")

    async def skills_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._deny_if_blocked(update):
            return
        self._track_subscriber(update)
        rows = self.orchestrator.list_dynamic_skill_states()
        if not rows:
            await update.message.reply_text("No dynamic skills loaded from workspace/skills.")
            return
        text = "Dynamic skills:\n" + "\n".join(
            [f"- {row['folder']} ({row['status']}) runtime={row['runtime_mode']} -> {row['tool_name']}" for row in rows]
        )
        await update.message.reply_text(text)

    async def skill_enable_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._deny_if_blocked(update):
            return
        self._track_subscriber(update)
        if not context.args:
            await update.message.reply_text("Usage: /skill_enable <folder_name>")
            return
        folder_name = context.args[0].strip()
        ok, message = self.orchestrator.set_skill_enabled(folder_name=folder_name, enabled=True)
        await update.message.reply_text(message if ok else f"Error: {message}")

    async def skill_disable_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._deny_if_blocked(update):
            return
        self._track_subscriber(update)
        if not context.args:
            await update.message.reply_text("Usage: /skill_disable <folder_name>")
            return
        folder_name = context.args[0].strip()
        ok, message = self.orchestrator.set_skill_enabled(folder_name=folder_name, enabled=False)
        await update.message.reply_text(message if ok else f"Error: {message}")

    async def providers_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._deny_if_blocked(update):
            return
        self._track_subscriber(update)
        providers = self.orchestrator.list_available_providers()
        if not providers:
            await update.message.reply_text("No providers are configured in .env yet.")
            return
        await update.message.reply_text("Available providers:\n" + "\n".join([f"- {name}" for name in providers]))

    async def provider_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._deny_if_blocked(update):
            return
        self._track_subscriber(update)
        user = update.effective_user
        user_id = str(user.id) if user else "unknown"

        if not context.args:
            status = self.orchestrator.get_provider_status(user_id)
            await update.message.reply_text(
                f"Provider: {status['provider']}\nModel: {status['model']}\nBase URL: {status['base_url']}"
            )
            return

        provider = context.args[0].strip().lower()
        ok, message = self.orchestrator.set_provider_for_user(user_id, provider)
        await update.message.reply_text(message if ok else f"Error: {message}")

    async def model_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._deny_if_blocked(update):
            return
        self._track_subscriber(update)
        user = update.effective_user
        user_id = str(user.id) if user else "unknown"

        if not context.args:
            status = self.orchestrator.get_provider_status(user_id)
            await update.message.reply_text(
                f"Current model: {status['model']}\nModel override active: {status['has_model_override']}"
            )
            return

        value = " ".join(context.args).strip()
        if value.lower() in {"default", "clear", "reset"}:
            ok, message = self.orchestrator.clear_model_override_for_user(user_id)
            await update.message.reply_text(message if ok else f"Error: {message}")
            return

        ok, message = self.orchestrator.set_model_for_user(user_id, value)
        await update.message.reply_text(message if ok else f"Error: {message}")

    async def profile_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._deny_if_blocked(update):
            return
        self._track_subscriber(update)
        user = update.effective_user
        user_id = str(user.id) if user else "unknown"
        status = self.orchestrator.get_provider_status(user_id)
        text = (
            "Runtime Profile\n"
            f"- Provider: {status['provider']}\n"
            f"- Model: {status['model']}\n"
            f"- Base URL: {status['base_url']}\n"
            f"- Override: {status['has_model_override']}\n"
            f"- Available providers: {status['available_providers']}"
        )
        await update.message.reply_text(text)

    async def approve_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._deny_if_blocked(update):
            return
        self._track_subscriber(update)
        user = update.effective_user
        user_id = str(user.id) if user else "unknown"

        if not context.args:
            await update.message.reply_text("Usage: /approve <approval_id>")
            return
        approval_id = context.args[0].strip()
        ok, message = self.approvals.approve(approval_id=approval_id, approved_by=user_id)
        await update.message.reply_text(message if ok else f"Error: {message}")

    async def deny_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._deny_if_blocked(update):
            return
        self._track_subscriber(update)
        user = update.effective_user
        user_id = str(user.id) if user else "unknown"

        if not context.args:
            await update.message.reply_text("Usage: /deny <approval_id> [reason]")
            return
        approval_id = context.args[0].strip()
        reason = " ".join(context.args[1:]).strip() if len(context.args) > 1 else ""
        ok, message = self.approvals.deny(approval_id=approval_id, denied_by=user_id, reason=reason)
        await update.message.reply_text(message if ok else f"Error: {message}")

    async def pending_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._deny_if_blocked(update):
            return
        self._track_subscriber(update)
        rows = self.approvals.list_pending(limit=15)
        if not rows:
            await update.message.reply_text("No pending approvals.")
            return
        text = "\n".join([f"- {row.id} | {row.action_type} | {row.reason}" for row in rows])
        await update.message.reply_text(text)

    async def tasks_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._deny_if_blocked(update):
            return
        self._track_subscriber(update)
        user = update.effective_user
        user_id = str(user.id) if user else "unknown"
        rows = self.orchestrator.memory.list_tasks(user_id, status="open")
        if not rows:
            await update.message.reply_text("No open tasks.")
            return
        text = "\n".join([f"- {row['id']} | {row['text']}" for row in rows])
        await update.message.reply_text(text)

    async def jobs_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._deny_if_blocked(update):
            return
        self._track_subscriber(update)
        user = update.effective_user
        user_id = str(user.id) if user else "unknown"
        rows = self.orchestrator.list_session_jobs(user_id=user_id, limit=10)
        if not rows:
            await update.message.reply_text("No recent jobs.")
            return
        text = "\n".join([f"- {row['id']} | {row['status']} | error={row['error'] or '[none]'}" for row in rows])
        await update.message.reply_text(text)

    async def resume_job_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._deny_if_blocked(update):
            return
        self._track_subscriber(update)
        if not context.args:
            await update.message.reply_text("Usage: /resume_job <job_id>")
            return
        ok, message = self.orchestrator.resume_session_job(context.args[0].strip())
        await update.message.reply_text(message if ok else f"Error: {message}")

    async def message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._deny_if_blocked(update):
            return
        self._track_subscriber(update)
        if not update.message or not update.message.text:
            return

        user = update.effective_user
        user_id = str(user.id) if user else "unknown"
        text = update.message.text.strip()
        if not text:
            return

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        try:
            reply = await asyncio.to_thread(self.orchestrator.process_message, user_id, text)
        except Exception as exc:
            logger.exception("Agent processing failed")
            await update.message.reply_text(f"Agent error: {exc}")
            return

        for chunk in self._chunk_text(reply):
            await update.message.reply_text(chunk, disable_web_page_preview=True)

    async def _post_startup(self) -> None:
        self.scheduler.start()

    async def _post_shutdown(self) -> None:
        await self.scheduler.shutdown()

    async def _on_startup(self, app: Application) -> None:
        await self._post_startup()

    async def _on_shutdown(self, app: Application) -> None:
        await self._post_shutdown()

    def run(self) -> None:
        if not self.settings.telegram_bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required for Telegram mode.")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES, close_loop=False)
