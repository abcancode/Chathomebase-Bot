"""DeepSeek API client with guard integration."""

import requests
import json
from typing import Dict, List, Optional


class DeepSeekClient:
    """Client for DeepSeek API with retry logic."""
    
    def __init__(self, api_key: str, guard=None, low_balance_threshold_usd: float = 4.0, max_retries: int = 3):
        self.api_key = api_key
        self.guard = guard
        self.low_balance_threshold = low_balance_threshold_usd
        self.max_retries = max_retries
        self.base_url = "https://api.deepseek.com/v1"
        self._balance_cache = None
        self._balance_time = 0
        
    def check_balance(self) -> float:
        """Check DeepSeek account balance."""
        import time
        if time.time() - self._balance_time < 60 and self._balance_cache is not None:
            return self._balance_cache
        
        try:
            response = requests.get(
                f"{self.base_url}/user/balance",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # DeepSeek returns balance in balance_infos array
                if "balance_infos" in data and len(data["balance_infos"]) > 0:
                    balance_info = data["balance_infos"][0]
                    balance = float(balance_info.get("total_balance", 0))
                    self._balance_cache = balance
                    self._balance_time = time.time()
                    return balance
                else:
                    print(f"[WARNING] Unexpected balance format")
                    return 0.0
            else:
                print(f"[ERROR] Balance check failed: {response.status_code}")
                
        except Exception as e:
            print(f"[ERROR] Balance check exception: {e}")
        
        return self._balance_cache or 0.0
        
    def generate(self, system_prompt: str, history: List[Dict], user_message: str, temperature: float = 0.95) -> Dict:
        """Generate response with retries and guard checking."""
        
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_message})
        
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "deepseek-chat",
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": 150
                    },
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    text = data["choices"][0]["message"]["content"].strip()
                    
                    # Apply guard if available
                    if self.guard:
                        text = self.guard.filter(text)
                    
                    return {"ok": True, "text": text}
                    
                elif response.status_code == 429:
                    import time
                    time.sleep(2 ** attempt)
                    continue
                else:
                    return {"ok": False, "error": f"API error {response.status_code}: {response.text}"}
                    
            except Exception as e:
                if attempt == self.max_retries - 1:
                    return {"ok": False, "error": str(e)}
                import time
                time.sleep(1)
        
        return {"ok": False, "error": "Max retries exceeded"}

        