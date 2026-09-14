"""DeepSeek API client."""

import time
from typing import Dict, List, Optional

import requests


class DeepSeekClient:
    def __init__(self, api_key: str, low_balance_threshold_usd: float = 4.0, max_retries: int = 3,
                 model: str = "deepseek-chat"):
        self.api_key = api_key
        self.low_balance_threshold = low_balance_threshold_usd
        self.max_retries = max_retries
        self.model = model
        self.base_url = "https://api.deepseek.com/v1"
        self._balance_cache: Optional[float] = None
        self._balance_time = 0.0

    def check_balance(self) -> float:
        if self._balance_cache is not None and time.time() - self._balance_time < 60:
            return self._balance_cache
        try:
            r = requests.get(f"{self.base_url}/user/balance",
                             headers={"Authorization": f"Bearer {self.api_key}"}, timeout=10)
            if r.status_code == 200:
                infos = r.json().get("balance_infos") or []
                if infos:
                    self._balance_cache = float(infos[0].get("total_balance", 0))
                    self._balance_time = time.time()
                    return self._balance_cache
                print("[WARNING] Unexpected balance format")
            else:
                print(f"[ERROR] Balance check failed: {r.status_code}")
        except Exception as e:  # noqa: BLE001
            print(f"[ERROR] Balance check exception: {e}")
        return self._balance_cache or 0.0

    def generate(self, system_prompt: str, history: List[Dict], user_message: Optional[str] = None,
                 temperature: float = 0.95, max_tokens: int = 350) -> Dict:
        messages = [{"role": "system", "content": system_prompt}] + [dict(m) for m in history]
        # Only append user_message if it is not already the last user turn (old code sent it twice).
        if user_message:
            last = messages[-1]
            if not (last["role"] == "user" and last["content"].strip() == user_message.strip()):
                messages.append({"role": "user", "content": user_message})
        if messages[-1]["role"] != "user":
            messages.append({"role": "user", "content": "(continue)"})

        for attempt in range(self.max_retries):
            try:
                r = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json={"model": self.model, "messages": messages,
                          "temperature": temperature, "max_tokens": max_tokens},
                    timeout=45,
                )
                if r.status_code == 200:
                    return {"ok": True, "text": r.json()["choices"][0]["message"]["content"].strip()}
                if r.status_code in (429, 500, 502, 503):
                    time.sleep(2 ** attempt)
                    continue
                return {"ok": False, "error": f"API error {r.status_code}: {r.text[:200]}"}
            except Exception as e:  # noqa: BLE001
                if attempt == self.max_retries - 1:
                    return {"ok": False, "error": str(e)}
                time.sleep(1.5)
        return {"ok": False, "error": "Max retries exceeded"}