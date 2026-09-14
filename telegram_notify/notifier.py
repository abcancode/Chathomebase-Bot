"""Minimal Telegram Bot API notifier (no extra dependencies)."""

import requests


class TelegramNotifier:
    def __init__(self, bot_token: str):
        self.base = f"https://api.telegram.org/bot{bot_token}"

    def send(self, chat_id: str, text: str) -> bool:
        try:
            r = requests.post(f"{self.base}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=10)
            return r.status_code == 200
        except Exception as e:  # noqa: BLE001
            print(f"[WARNING] Telegram send failed: {e}")
            return False

    def notify_low_balance(self, chat_id: str, balance: float, threshold: float) -> bool:
        return self.send(chat_id, f"ChatHomeBase bot: DeepSeek balance is ${balance:.2f} (threshold ${threshold:.2f}). Top up.")