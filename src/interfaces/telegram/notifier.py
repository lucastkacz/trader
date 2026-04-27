import requests
import asyncio
from src.core.config import settings
from src.core.logger import logger

class TelegramNotifier:
    """
    Decoupled 1-Way Push Notifier.
    Used exclusively by the Trader Engine execution loop to safely dispatch state updates.
    """
    def __init__(self):
        self.token = settings.telegram_bot_token
        self.chat_id = settings.telegram_chat_id
        self.prefix_tag = "[TRADER PAPER]" if settings.log_level != "info" else "[TRADER LIVE]"

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
