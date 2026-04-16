# Telegram Integration Architecture

As the Epoch 3 Ghost Trader and Epoch 4 Production Trader operate autonomously in the cloud, human visibility becomes paramount. SSHing into the VPS or checking GitHub Actions logs is sufficient for debugging, but unacceptable for active monitoring.

We will integrate a **One-Way Telegram Notifier** to push critical events, trade executions, and system health status directly to your phone.

## Strategy: Asynchronous, Non-Blocking Webhooks

The **Golden Rule** of trading infrastructure: *Secondary systems (like logging and notifications) must NEVER crash or block the primary execution engine.*

If the Telegram API is down, the trading engine must continue executing trades without hesitation. Therefore, our Telegram Integration will use pure REST webhooks (`requests.post`) wrapped in non-blocking `asyncio.create_task` or short `timeout` blocks to prevent network hangups.

---

## 1. Environment & Infrastructure Setup

You will need to create a Telegram Bot via the "BotFather" on Telegram. 

### Variables required:
1. `TELEGRAM_BOT_TOKEN`: The API key provided by BotFather.
2. `TELEGRAM_CHAT_ID`: Your personal chat ID, ensuring the bot only messages you.

### CI/CD Security Segregation:
These variables will be added directly to the **GitHub Environments** (`ghost-trader` and later `production-trader`). The Bootstrap action will inject them securely into the `.env` file just like our exchange API keys.

By segregating these across environments, we can even have the bot prefix its messages depending on where it lives (e.g., `[👻 GHOST]` vs `[💰 LIVE]`).

---

## 2. Code Implementation Blueprint

### `src/core/notifier.py`
We will introduce a lightweight `TelegramNotifier` class handling the raw requests.

```python
import requests
import asyncio
from src.core.config import settings
from src.core.logger import logger

class TelegramNotifier:
    def __init__(self):
        self.token = settings.telegram_bot_token
        self.chat_id = settings.telegram_chat_id
        self.prefix_tag = "[👻 PAPER]" if settings.env == "production" else "[💻 DEV]"

    def _send_sync(self, message: str):
        if not self.token or not self.chat_id:
            return
            
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": f"{self.prefix_tag}\n{message}", "parse_mode": "HTML"}
        
        try:
            # 2-second timeout so a dead Telegram API doesn't freeze our trading loop!
            requests.post(url, json=payload, timeout=2.0)
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")

    async def send(self, message: str):
        """Asynchronously dispatches the webhook to keep the main thread unblocked."""
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, self._send_sync, message)
```

---

## 3. Notification Triggers (When do we alert?)

We do not want alert fatigue. If the bot alerts on every tiny standard tick, you will stop reading the message. We only alert on events that require human awareness.

### A. Lifecycle Events
- **System Boot:** Generated when `ghost_trader.py` initializes successfully. Proves the `systemd` daemon restarted properly.
  - *Example: "🟢 System Boot: Engine Synchronized on Oracle VPS. Monitoring 13 Tier 1 Pairs."*
- **Cron Check Failure:** Generated heavily by the GitHub `health.yml` pipeline if it detects stale data.

### B. Trade Execution
- **Entry Pulse:** Sent immediately when the Z-Score crosses the threshold.
  - *Example: "🚀 ENTRY SIGNAL: SOL/USDT\n• Z-Score: -3.42\n• Hedge Ratio: 0.125\n• Action: LONG Spread"*
- **Exit Pulse:** Sent immediately when Z-Score safely crosses 0 or the stop-loss is triggered.
  - *Example: "🏁 EXIT SIGNAL: SOL/USDT\n• Duration: 14h\n• Action: CLOSE Spread"*

### C. Critical Exceptions (The Watchdog)
- **API Disconnections or Fatal Errors** caught in the global `try...catch` block.
  - *Example: "⚠️ FATAL ERROR: Bybit Rate Limit Exceeded. Engine isolating..."*

---

## 4. Rollout Plan (Next Steps for You)

1. Open Telegram, search for `@BotFather`, and type `/newbot`.
2. Name it something awesome (e.g., `Lucas Quant System`).
3. Save the HTTP API Token it gives you.
4. Search for `@userinfobot` to get your exact `Chat ID`.
5. We will add those parameters to `src/core/config.py`.
6. Inject the Notifier inside the main tick loop in `scripts/ghost_trader.py`!
