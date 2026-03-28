from .bridge_webhook import BridgeWebhookAdapter
from .discord_bot import DiscordBotAdapter
from .slack_bot import SlackBotAdapter
from .telegram_bot import TelegramBotAdapter
from .whatsapp_bot import WhatsAppAdapter

__all__ = ["TelegramBotAdapter", "DiscordBotAdapter", "SlackBotAdapter", "WhatsAppAdapter", "BridgeWebhookAdapter"]
