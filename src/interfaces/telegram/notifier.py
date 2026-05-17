import requests
import asyncio
from src.core.config import settings
from src.core.logger import logger


def _build_prefix_tag(environment: str | None = None, execution_mode: str | None = None) -> str:
    parts = ["TRADER"]
    if environment:
        environment_label = environment.replace("_", " ").replace("-", " ").strip().upper()
        if execution_mode != "live":
            environment_label = " ".join(
                part for part in environment_label.split() if part != "LIVE"
            )
        if environment_label:
            parts.append(environment_label)

    if execution_mode == "live":
        parts.append("LIVE")
    elif execution_mode == "state_only":
        parts.append("STATE-ONLY")
    else:
        parts.append("NON-LIVE")

    return f"[{' '.join(parts)}]"


class TelegramNotifier:
    """
    Decoupled 1-Way Push Notifier.
    Used exclusively by the Trader Engine execution loop to safely dispatch state updates.
    """
    def __init__(self, environment: str | None = None, execution_mode: str | None = None):
        self.token = settings.telegram_bot_token
        self.chat_id = settings.telegram_chat_id
        self.prefix_tag = _build_prefix_tag(environment, execution_mode)

    def _send_sync(self, message: str):
        """Synchronous HTTP dispatch with strict strict timeouts to prevent freezing."""
        if not self.token or not self.chat_id:
            return
            
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id, 
            "text": f"{self.prefix_tag}\n{message}", 
            "parse_mode": "HTML"
        }
        
        try:
            # 2.0 second timeout! The execution loop must never be blocked!
            requests.post(url, json=payload, timeout=2.0)
        except Exception as e:
            logger.error(f"Failed to send Telegram notification (Timeout/Network Error): {e}")

    async def send(self, message: str):
        """Asynchronously dispatches the webhook via executor."""
        if not self.token or not self.chat_id:
            return
            
        loop = asyncio.get_event_loop()
        # run_in_executor uses default ThreadPoolExecutor to prevent blocking the async loop
        await loop.run_in_executor(None, self._send_sync, message)
