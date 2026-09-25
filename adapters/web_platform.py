"""Web automation for chathomebase.com: auto-assignment, profile scraping, human-like replies."""

import asyncio
import hashlib
import json
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

from core.browser import launch_browser, INSPECTOR_JS
from core.deepseek_client import DeepSeekClient
from core.excuse_bank import DynamicExcuseGenerator
from core.google_geo import LocationFinder
from core.humanizer import HumanTyper, normalize_for_typing
from core.logbook import Logbook
from core.prompt_builder import load_rules, build_system_prompt, build_history_messages
from core.rule_guard import RuleGuard
from core.timer_calculator import TimerCalculator

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
LOG_DIR = ROOT / "logs"

PROFILE_PATTERNS = {
    "name": [r"Name[:\s]+([A-Za-z][A-Za-z '\-]{1,40}?)\s*(?:\n|$)",
             r"(?m)^([A-Z][A-Za-z'\-]+(?: [A-Z][A-Za-z'\-]+)?),\s*\d{2}\s*$"],
    "age": [r"Age[:\s]+(\d{2})", r"(?m)^[A-Z][A-Za-z'\-]+(?: [A-Z][A-Za-z'\-]+)?,\s*(\d{2})\s*$",
            r"\b(\d{2})\s*(?:years old|yrs|y/o|yo)\b"],
    "location": [r"(?:Location|Lives in|City|From)[:\s]+([^\n]+)"],
    "occupation": [r"(?:Occupation|Job|Work|Profession)[:\s]+([^\n]+)"],
    "status": [r"\b(Single|Married|Divorced|Widowed|Separated)\b"],
    "eyes": [r"\b(Blue|Brown|Green|Hazel|Grey|Gray)\s+eyes?\b"],
    "hair": [r"\b(Blonde|Blond|Brunette|Red|Black|Brown|Grey|Gray)\s+hair\b"],
    "body_type": [r"\b(Slim|Athletic|Curvy|Curvaceous|Average|Petite|Muscular)\b"],
    "height": [r"(\d\s*ft\s*\d{0,2}\s*(?:in)?|\d{3}\s*cm)"],
}
SECTIONS = [("About me", "about_me"), ("About you", "about_you"), ("Hobbies", "hobbies"),
            ("Interests", "hobbies"), ("Description", "about"), ("Bio", "about")]


def log(level: str, msg: str):
    print(f"[{datetime.now():%H:%M:%S}] [{level}] {msg}")


def parse_profile(text: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not text:
        return out
    for field, patterns in PROFILE_PATTERNS.items():
        for p in patterns:
            m = re.search(p, text, re.I)
            if m:
                out[field] = m.group(1).strip()
                break
    for label, key in SECTIONS:
        m = re.search(rf"{re.escape(label)}[:\s]*\n?([^\n]+)", text, re.I)
        if m and key not in out:
            out[key] = m.group(1).strip()
    if "name" not in out:
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if lines and len(lines[0]) <= 30 and re.fullmatch(r"[A-Za-z][A-Za-z '\-]*", lines[0]) \
                and lines[0].lower() not in ("profile", "customer", "about me", "player"):
            out["name"] = lines[0]
    return out


def parse_proxy(proxy: Optional[dict]) -> Optional[dict]:
    if not proxy or not proxy.get("server"):
        return None
    url = proxy["server"]
    if "@" in url:
        p = urlparse(url)
        return {"server": f"{p.scheme}://{p.hostname}:{p.port}", "username": p.username, "password": p.password}
    return {"server": url}


class ChatHomeBaseAdapter:
    def __init__(self, settings: dict, dry_run: bool = False, inspect: bool = False):
        self.settings = settings
        self.dry_run = dry_run
        self.inspect = inspect
        self.proxy_config = parse_proxy(settings.get("proxy"))
        self.sel = json.loads((DATA_DIR / "selectors.json").read_text(encoding="utf-8"))

        self.rules = load_rules(DATA_DIR / "rules.json")
        self.guard = RuleGuard(DATA_DIR / "rules.json", DATA_DIR / "banned_phrases.json")
        self.deepseek = DeepSeekClient(settings["deepseek_api_key"],
                                       settings.get("deepseek_low_balance_threshold_usd", 4.0))
        self.logbook = Logbook(LOG_DIR / "logbooks")
        self.timer = TimerCalculator()
        self.excuse_generator = DynamicExcuseGenerator(self.deepseek, "", self.guard.followup_min_chars, self.guard.max_chars)
        self.geo = LocationFinder(settings["google_api_key"]) if settings.get("google_api_key") else None
        self.openai_key = settings.get("openai_api_key")

        self.notifier = None
        if settings.get("telegram_user_id") and settings.get("telegram_bot_token"):
            from telegram_notify.notifier import TelegramNotifier
            self.notifier = TelegramNotifier(settings["telegram_bot_token"])
        self._notified: Dict[str, float] = {}

        self.playwright = None
        self.context = None
        self.page = None
        self.typer: Optional[HumanTyper] = None

        self.customer_profile: Dict = {}
        self.player_profile: Dict = {}
        self._current_customer_key: Optional[str] = None
        self._last_sig: Optional[Tuple] = None
        self._awaiting_since: Optional[float] = None
        self._followup_sent = False
        self._image_cache: Dict[str, str] = {}
        self._max_cache_size = 100

    async def _check_balance(self):
        """Check DeepSeek API balance and notify if below threshold."""
        try:
            balance = await asyncio.to_thread(self.deepseek.check_balance)
            log("INFO", f"DeepSeek balance: ${balance:.2f}")
            threshold = self.settings.get("deepseek_low_balance_threshold_usd", 4.0)
            if balance < threshold and self.notifier:
                self.notifier.notify_low_balance(self.settings["telegram_user_id"], balance, threshold)
        except Exception as e:
            log("WARNING", f"Could not check balance: {e}")

    async def start(self):
        mode = "INSPECT" if self.inspect else ("DRY RUN" if self.dry_run else "LIVE")
        print(f"\n{'=' * 60}\nChatHomeBase Bot   Mode: {mode}\n{'=' * 60}\n")

        profile_name = self.settings.get("chrome_profile_folder", "Default")
        
        self.playwright, self.context, self.page = await launch_browser(
            ROOT / "profile", self.proxy_config, inspect=self.inspect,
            channel=self.settings.get("browser_channel"), user_agent=self.settings.get("user_agent"),
            profile_name=profile_name)
        self.typer = HumanTyper(self.page,
                                (self.settings.get("typing_cpm_min", 190), self.settings.get("typing_cpm_max", 260)))
        if self.inspect:
            await self.page.expose_function("chbLog", lambda m: print(f"      [PAGE] {m}"))
            await self.page.add_init_script(INSPECTOR_JS)

        await self._check_balance()

        for attempt in range(3):
            try:
                if await self._login():
                    break
            except Exception as e:  # noqa: BLE001
                log("WARNING", f"Login attempt {attempt + 1} failed: {e}")
                await self._screenshot("login_failed")
                await asyncio.sleep(5)
        else:
            log("ERROR", "Could not log in after 3 attempts")
            self._notify("login", "ChatHomeBase bot could not log in after 3 attempts.")
            return

        if self.inspect:
            await self._inspection_session()

        log("INFO", "Waiting for chat assignments...")
        await self._process_assignments()

    async def stop(self):
        try:
            if self.context:
                await self.context.close()
        finally:
            if self.playwright:
                await self.playwright.stop()

    # ------------------------------------------------------------------ helpers
    async def _first(self, selectors: List[str], timeout_ms: int = 1500):
        deadline = time.time() + timeout_ms / 1000
        while True:
            for s in selectors:
                try:
                    loc = self.page.locator(s).first
                    if await loc.count() and await loc.is_visible():
                        return loc
                except Exception:
                    continue
            if time.time() >= deadline:
                return None
            await asyncio.sleep(0.2)

    async def _first_text(self, selectors: List[str], timeout_ms: int = 1500) -> str:
        loc = await self._first(selectors, timeout_ms)
        try:
            return (await loc.inner_text()) if loc else ""
        except Exception:
            return ""

    async def _click_first(self, selectors: List[str], timeout_ms: int = 1500) -> bool:
        loc = await self._first(selectors, timeout_ms)
        if not loc:
            return False
        try:
            await loc.click(timeout=2000)
            return True
        except Exception:
            return False

    async def _dismiss_dialogs(self):
        L, C = self.sel["login"], self.sel["chat"]
        log("INFO", "Checking for announcement dialogs...")

        try:
            await self._click_first(L.get("announcement_button", []), 2000)
            log("INFO", "Clicked Announcements button (if visible)")
            await asyncio.sleep(1.5)
        except Exception:
            pass
        
        for _ in range(5):
            if not await self._click_enabled_button(L["announcement_next"], 2000):
                break
            await asyncio.sleep(0.4)
        
        await self._click_enabled_button(L["announcement_continue"], 2000)
        
        # Check for and close a generic chat overlay/sandbox
        try:
            overlay = self.page.locator("div[class*='modal'], div[class*='overlay'], div[id*='modal'], div[id*='overlay']").first
            if await overlay.count() > 0:
                log("INFO", "Found Overlay/Sandbox, clicking to dismiss...")
                await overlay.click(timeout=2000)
                await asyncio.sleep(1.0)
        except Exception:
            pass
        
        if await self._click_enabled_button(C["close_banner"], 1500):
            log("INFO", "Closed a banner")
    
    async def _click_enabled_button(self, selectors: List[str], timeout_ms: int = 1500):
        deadline = time.time() + timeout_ms / 1000
        while time.time() < deadline:
            for s in selectors:
                try:
                    btn = self.page.locator(s).first
                    if await btn.count() > 0:
                        try:
                            await btn.wait_for(state='visible', timeout=500)
                        except:
                            continue
                        is_enabled = await btn.is_enabled()
                        if is_enabled:
                            await btn.click(timeout=1000)
                            log("INFO", f"Clicked button: {s}")
                            return True
                except Exception:
                    continue
            await asyncio.sleep(0.2)
        return False
    
    # ------------------------------------------------------------------ login
    async def _login(self) -> bool:
        L = self.sel["login"]
        log("INFO", "Checking session...")
        
        await self.page.bring_to_front()
        await asyncio.sleep(1.0)
        
        if "lobby" in self.page.url or "/chat/" in self.page.url:
            log("INFO", "Found chat URL - already logged in")
            await self._dismiss_dialogs()
            return True
            
        if "login" in self.page.url:
            log("INFO", "On login page. Waiting for form...")
            await asyncio.sleep(2.0)
            
            log("INFO", "Waiting for login form...")
            email = await self._first(L["email"], 10000)
            if not email:
                await self._screenshot("login_form_missing")
                raise RuntimeError(f"Login form not found at {self.page.url}")
                
            await email.click()
            log("INFO", "Typing email...")
            await self.typer.type(self.settings["chathomebase_login"], typos=False)
            await asyncio.sleep(random.uniform(0.5, 1.0))
            
            password = await self._first(L["password"], 3000)
            if not password:
                await self._screenshot("password_missing")
                raise RuntimeError(f"Password input not found at {self.page.url}")
                
            await password.click()
            log("INFO", "Typing password...")
            await self.typer.type(self.settings["chathomebase_password"], typos=False)
            await asyncio.sleep(random.uniform(0.5, 1.0))
            
            log("INFO", "Submitting login form...")
            if not await self._click_first(L["submit"], 2000):
                log("INFO", "Submit button not found, pressing Enter...")
                await self.page.keyboard.press("Enter")
                
            log("INFO", "Waiting for lobby URL...")
            await self.page.wait_for_url(L["lobby_url_glob"], timeout=30000)
            log("INFO", "Successfully logged in. Lobby reached.")
            
            await asyncio.sleep(2.0)
            await self._dismiss_dialogs()
            return True
            
        log("INFO", "Not on login page. Navigating to login page...")
        await self.page.bring_to_front()
        await asyncio.sleep(1.5)
        
        await self.page.goto(L["url"], wait_until="networkidle")
        log("INFO", "Navigated to login URL")
        await asyncio.sleep(2.0)
        
        log("INFO", "Waiting for login form...")
        email = await self._first(L["email"], 10000)
        if not email:
            await self._screenshot("login_form_missing")
            raise RuntimeError(f"Login form not found at {self.page.url}")
            
        await email.click()
        log("INFO", "Typing email...")
        await self.typer.type(self.settings["chathomebase_login"], typos=False)
        await asyncio.sleep(random.uniform(0.5, 1.0))
        
        password = await self._first(L["password"], 3000)
        if not password:
            await self._screenshot("password_missing")
            raise RuntimeError(f"Password input not found at {self.page.url}")
            
        await password.click()
        log("INFO", "Typing password...")
        await self.typer.type(self.settings["chathomebase_password"], typos=False)
        await asyncio.sleep(random.uniform(0.5, 1.0))
        
        log("INFO", "Submitting login form...")
        if not await self._click_first(L["submit"], 2000):
            log("INFO", "Submit button not found, pressing Enter...")
            await self.page.keyboard.press("Enter")
            
        log("INFO", "Waiting for lobby URL...")
        await self.page.wait_for_url(L["lobby_url_glob"], timeout=30000)
        log("INFO", "Successfully logged in. Lobby reached.")
        
        await asyncio.sleep(2.0)
        await self._dismiss_dialogs()
        return True
    
    # ------------------------------------------------------------------ main loop
    async def _signature(self) -> Optional[Tuple[str, int, str]]:
        C = self.sel["chat"]
        bubbles = await self.page.query_selector_all(", ".join(C["message_bubbles"]))
        if not bubbles:
            return None
        try:
            last_text = (await bubbles[-1].inner_text() or "")[:200]
        except Exception:
            last_text = ""
        cust = (await self._first_text(self.sel["profiles"]["customer"], 300))[:150]
        h = lambda s: hashlib.md5(s.encode("utf-8", "ignore")).hexdigest()[:8]
        return (h(cust), len(bubbles), h(last_text))

    async def _process_assignments(self):
        errors = 0
        while True:
            try:
                sig = await self._signature()
                if sig is None:
                    if self._current_customer_key:
                        log("INFO", "Chat closed. Waiting for next assignment...")
                        self._current_customer_key = None
                        self._last_sig = None
                    await asyncio.sleep(2)
                    continue

                if sig[0] != self._current_customer_key:
                    await self._load_assignment(sig[0])

                if sig == self._last_sig:
                    await self._maybe_followup()
                    await asyncio.sleep(2)
                    continue

                await asyncio.sleep(1.0)
                conversation = await self._read_conversation()
                if conversation:
                    await self._process_current_chat(conversation)
                self._last_sig = await self._signature()
                errors = 0
            except TimeoutError as e:
                errors += 1
                log("WARNING", f"Timeout error: {e}")
                await self._screenshot("timeout")
                if errors >= 3:
                    self._notify("timeouts", f"ChatHomeBase bot: {errors} consecutive timeouts. Last: {e}")
                await asyncio.sleep(5)
            except ConnectionError as e:
                errors += 1
                log("WARNING", f"Connection error: {e}")
                await self._screenshot("connection_error")
                if errors >= 3:
                    self._notify("connection", f"ChatHomeBase bot: {errors} connection errors. Last: {e}")
                await asyncio.sleep(10)
            except Exception as e:
                errors += 1
                log("ERROR", f"{type(e).__name__}: {e}")
                await self._screenshot("error")
                if errors >= 5:
                    self._notify("errors", f"ChatHomeBase bot: {errors} consecutive errors. Last: {e}")
                await asyncio.sleep(5)

    async def _load_assignment(self, customer_key: str):
        print(f"\n{'=' * 60}\nNew assignment\n{'=' * 60}")
        self._current_customer_key = customer_key
        self._awaiting_since = None
        self._followup_sent = False

        self.customer_profile = parse_profile(await self._first_text(self.sel["profiles"]["customer"], 8000))
        self.player_profile = parse_profile(await self._first_text(self.sel["profiles"]["player"], 3000))
        self.customer_profile.setdefault("name", "Customer")
        self.player_profile.setdefault("name", self.settings.get("player_name") or "Player")
        self.player_profile.setdefault("occupation", self.settings.get("player_occupation") or "Worker")

        self.logbook.bind(self.player_profile["name"], self.customer_profile["name"])
        self.guard.set_customer_name(self.customer_profile["name"])

        if self.player_profile.get("occupation", "").lower() in ("", "worker") and self.logbook.get_player_profession():
            self.player_profile["occupation"] = self.logbook.get_profession_detail() or self.logbook.get_player_profession()
        elif self.player_profile.get("occupation", "").lower() not in ("", "worker") and not self.logbook.get_player_profession():
            self.logbook.set_profession(self.player_profile["occupation"])

        if not self.player_profile.get("location"):
            loc = self.logbook.get_customer_fact("player_location")
            if not loc and self.geo and self.customer_profile.get("location"):
                loc = await asyncio.to_thread(self.geo.get_nearby_city, self.customer_profile["location"],
                                              int(self.settings.get("nearby_miles", 40)))
                if loc:
                    self.logbook.set_customer_fact("player_location", loc)
                    log("INFO", f"Picked nearby town for player: {loc}")
            if loc:
                self.player_profile["location"] = loc

        self.excuse_generator = DynamicExcuseGenerator(self.deepseek, self.player_profile.get("occupation", ""),
                                                       self.guard.followup_min_chars, self.guard.max_chars)
        log("INFO", f"Player: {self.player_profile.get('name')} | {self.player_profile.get('occupation')} | {self.player_profile.get('location')}")
        log("INFO", f"Customer: {self.customer_profile.get('name')} | {self.customer_profile.get('location', '?')} | age {self.customer_profile.get('age', '?')}")

        history = await self._read_conversation(historical_only=True)
        if history:
            log("INFO", f"Previous conversation: {len(history)} messages")
            self._extract_facts_from_history(history)

    async def _process_current_chat(self, conversation: List[Dict]):
        last = conversation[-1]
        if last["speaker"] == "customer":
            log("INFO", f"Customer: {last['text'][:80]}")
            self._awaiting_since = None
            self._note_customer_info(last["text"])
            await asyncio.sleep(self.timer.reading_delay(len(last["text"])))
            reply = await self._generate_reply(last, conversation)
            if reply and await self._deliver(reply):
                self._awaiting_since = time.time()
            return

        consecutive = 0
        for m in reversed(conversation):
            if m["speaker"] != "player":
                break
            consecutive += 1
        if consecutive >= 2 or self._followup_sent:
            log("INFO", "Follow-up already sent, waiting for the customer...")
            return
        if self._awaiting_since is not None:
            return
        log("INFO", "Customer quiet on assignment, sending one re-engagement message...")
        await self._send_follow_up(conversation)

    async def _maybe_followup(self):
        minutes = float(self.settings.get("followup_after_minutes", 0) or 0)
        if minutes <= 0 or self._followup_sent or self._awaiting_since is None:
            return
        if time.time() - self._awaiting_since >= minutes * 60:
            log("INFO", f"No reply for {minutes:g} min, sending one follow-up...")
            await self._send_follow_up(await self._read_conversation())

    async def _read_conversation(self, historical_only: bool = False) -> List[Dict]:
        C = self.sel["chat"]
        bubbles = await self.page.query_selector_all(", ".join(C["message_bubbles"]))
        messages: List[Dict] = []
        for b in bubbles:
            try:
                classes = (await b.get_attribute("class") or "").lower()
                is_hist = any(m in classes for m in C["history_class_markers"])
                if historical_only and not is_hist:
                    continue
                if any(m in classes for m in C["customer_class_markers"]):
                    speaker = "customer"
                elif any(m in classes for m in C["player_class_markers"]):
                    speaker = "player"
                else:
                    continue
                text_el = await b.query_selector(", ".join(C["message_text"]))
                text = ((await text_el.inner_text()) if text_el else (await b.inner_text())).strip()
                if speaker == "customer":
                    img = await b.query_selector(", ".join(C["message_image"]))
                    if img:
                        src = await img.get_attribute("src")
                        if src and not src.startswith("data:image/svg") and "avatar" not in src.lower():
                            text = f"{text} [Customer shared a photo: {await self._analyze_image(src)}]".strip()
                if text:
                    messages.append({"speaker": speaker, "text": text, "historical": is_hist})
            except Exception:
                continue
        return messages

    async def _analyze_image(self, url: str) -> str:
        if url in self._image_cache:
            return self._image_cache[url]
        
        desc = "photo"
        if self.openai_key:
            try:
                data_url = await self.page.evaluate(
                    """async (u) => { const r = await fetch(u); const b = await r.blob();
                       return await new Promise(res => { const fr = new FileReader();
                       fr.onloadend = () => res(fr.result); fr.readAsDataURL(b); }); }""", url)
                if data_url and str(data_url).startswith("data:"):
                    import openai
                    client = openai.AsyncOpenAI(api_key=self.openai_key)
                    r = await client.chat.completions.create(
                        model=self.settings.get("openai_vision_model", "gpt-4o-mini"),
                        messages=[{"role": "user", "content": [
                            {"type": "text", "text": "Describe this photo in one short factual sentence: who or what is shown, setting, notable details. Under 25 words."},
                            {"type": "image_url", "image_url": {"url": data_url}}]}],
                        max_tokens=60)
                    desc = r.choices[0].message.content.strip()
                    log("INFO", f"Image: {desc[:70]}")
            except Exception as e:
                log("WARNING", f"Image analysis failed: {e}")
        
        self._image_cache[url] = desc
        if len(self._image_cache) > self._max_cache_size:
            oldest_key = next(iter(self._image_cache))
            del self._image_cache[oldest_key]
            
        return desc

    async def _screenshot(self, tag: str):
        try:
            d = LOG_DIR / "screens"
            d.mkdir(parents=True, exist_ok=True)
            path = d / f"{datetime.now():%Y%m%d_%H%M%S}_{tag}.png"
            await self.page.screenshot(path=str(path), full_page=False)
            log("INFO", f"Screenshot: {path.name}")
        except Exception:
            pass

    def _notify(self, key: str, text: str, cooldown: int = 1800):
        if not self.notifier:
            return
        if time.time() - self._notified.get(key, 0) < cooldown:
            return
        self._notified[key] = time.time()
        self.notifier.send(self.settings["telegram_user_id"], text)

    def _extract_facts_from_history(self, history: List[Dict]):
        for msg in (m["text"] for m in history if m["speaker"] == "player"):
            low = msg.lower()
            for p in (r"i am an? ([\w\s]+?)(?:\.|,|$)", r"i'm an? ([\w\s]+?)(?:\.|,|$)",
                      r"i work as an? ([\w\s]+?)(?:\.|,|$)", r"my job is ([\w\s]+?)(?:\.|,|$)"):
                m = re.search(p, low)
                if m and not self.logbook.get_player_profession() and len(m.group(1)) < 40:
                    self.logbook.set_profession(m.group(1).strip())
                    log("INFO", f"Profession from history: {m.group(1).strip()}")
                    break
            for p in (r"i live in ([\w\s,]+?)(?:\.|$)", r"i'm from ([\w\s,]+?)(?:\.|$)", r"i am from ([\w\s,]+?)(?:\.|$)"):
                m = re.search(p, low)
                if m and not self.logbook.get_customer_fact("player_location"):
                    self.logbook.set_customer_fact("player_location", m.group(1).strip().title())
                    log("INFO", f"Location from history: {m.group(1).strip()}")
                    break

    def _note_customer_info(self, text: str):
        low = text.lower()
        cust = self.customer_profile.get("name")
        if any(w in low for w in ("your work", "your job", "do for a living", "what do you do", "profession", "career")):
            prof = self.logbook.get_player_profession()
            if not prof and self.player_profile.get("occupation", "").lower() not in ("", "worker"):
                self.logbook.set_profession(self.player_profile["occupation"], client=cust)
            elif not prof:
                base, detail = random.choice(self.rules.get("default_professions", [["teacher", "English teacher"]]))
                self.logbook.set_profession(base, detail, cust)
                self.player_profile["occupation"] = detail
                log("INFO", f"Invented profession: {detail}")
        for p in (r"i am an? ([\w\s]{3,30}?)(?:\.|,|$)", r"i work as an? ([\w\s]{3,30}?)(?:\.|,|$)",
                  r"my job is ([\w\s]{3,30}?)(?:\.|,|$)", r"i'm an? ([\w\s]{3,30}?)(?:\.|,|$)"):
            m = re.search(p, low)
            if m:
                self.logbook.add_entry("Client_Work", f"Client profession: {m.group(1).strip()}", cust)
                break
        if any(w in low for w in ("fantasy", "dream", "like to try", "never tried", "turn me on", "turns me on")):
            self.logbook.add_entry("Sexual", f"Customer shared: {text[:120]}", cust)
        if any(w in low for w in ("sick", "surgery", "hospital", "medical", "migraine", "diabetes", "smoke", "injury")):
            self.logbook.add_entry("Health", f"Customer health: {text[:120]}", cust)
        if "[Customer shared a photo:" in text:
            self.logbook.add_entry("Update", f"Photo received: {text.split('[Customer shared a photo:')[1].split(']')[0].strip()}", cust)

    def _build_summary(self) -> str:
        parts = []
        for k, label in (("age", "Player age"), ("location", "Player location"), ("hair", "Player hair"),
                         ("eyes", "Player eyes"), ("body_type", "Player body"), ("about", "Player bio")):
            if self.player_profile.get(k):
                parts.append(f"{label}: {self.player_profile[k][:120]}")
        for k, label in (("age", "Customer age"), ("status", "Customer status"), ("occupation", "Customer job"),
                         ("about_me", "Customer about"), ("hobbies", "Customer hobbies")):
            if self.customer_profile.get(k):
                parts.append(f"{label}: {self.customer_profile[k][:120]}")
        parts.append(self.logbook.get_summary_for_prompt())
        return "\n".join(parts)

    def _classify(self, text: str) -> str:
        t = text.lower()
        if any(k in t for k in ("sex", "fuck", "cock", "dick", "pussy", "cum", "naked", "nude", "horny", "wet", "hard")):
            return "sexual"
        if any(k in t for k in ("sexy", "beautiful", "kiss", "gorgeous", "hot", "cuddle", "date", "miss you")):
            return "flirty"
        return "casual"

    async def _generate_reply(self, last_msg: Dict, conversation: List[Dict], is_follow_up: bool = False) -> Optional[str]:
        recent = conversation[-15:]
        category = "casual" if is_follow_up else self._classify(last_msg["text"])
        system_prompt = build_system_prompt(
            rules=self.rules,
            player_name=self.player_profile.get("name", "Player"),
            player_occupation=self.player_profile.get("occupation", "Worker"),
            player_location=self.player_profile.get("location"),
            customer_name=self.customer_profile.get("name", "Customer"),
            customer_location=self.customer_profile.get("location", "somewhere nearby"),
            logbook_summary=self._build_summary(),
            category=category,
            past_replies=[m["text"] for m in recent if m["speaker"] == "player"],
            user_message=last_msg["text"],
            is_follow_up=is_follow_up)
        history = build_history_messages(recent)
        if not history or history[-1]["role"] != "user":
            history.append({"role": "user", "content": "(he has not replied yet, send your follow-up)"})

        note = ""
        for attempt in range(3):
            result = await asyncio.to_thread(self.deepseek.generate, system_prompt + note, history, None, 0.95 - 0.1 * attempt, 350)
            if not result["ok"]:
                log("ERROR", f"DeepSeek: {result['error']}")
                continue
            text = normalize_for_typing(self.guard.sanitize(result["text"], self.player_profile.get("name")),
                                        allow_emoji=bool(self.settings.get("allow_emoji", False)))
            ok, reason = self.guard.check(text, is_follow_up)
            if ok:
                return text
            log("GUARD", f"Rejected draft ({reason}), regenerating")
            note = f"\n\nYOUR PREVIOUS DRAFT WAS REJECTED: {reason}. Write a new reply that fixes this."
        return None

    async def _send_follow_up(self, conversation: List[Dict]):
        self._followup_sent = True
        last_player = next((m["text"] for m in reversed(conversation) if m["speaker"] == "player"), "")
        category = self._classify(last_player)
        text = normalize_for_typing(await self.excuse_generator.generate_excuse(category))
        ok, reason = self.guard.check(text, is_follow_up=True)
        if not ok:
            log("GUARD", f"Excuse rejected ({reason}), falling back to model follow-up")
            text = await self._generate_reply({"text": last_player}, conversation, is_follow_up=True)
        if text and await self._deliver(text):
            self._awaiting_since = time.time()

    async def _deliver(self, text: str) -> bool:
        C = self.sel["chat"]
        
        # 1. Dismiss dialogs FIRST (ensures input box is visible and not covered)
        await self._dismiss_dialogs()
        
        # 2. Find the input box - PRIORITIZE the data-testid selector
        box = None
        for selector in C["input"]:
            try:
                loc = self.page.locator(selector).first
                if await loc.count() > 0 and await loc.is_visible():
                    box = loc
                    log("INFO", f"Found input box using selector: {selector}")
                    break
            except Exception:
                continue
        
        if not box:
            log("ERROR", "Could not find the message input box")
            await self._screenshot("no_input")
            return False
        
        try:
            # 3. Focus and Clear
            await box.focus()
            await box.click(timeout=3000)
            await asyncio.sleep(0.5)
            
            # Clear any existing text
            await box.fill("")
            
            # 4. FORCE TYPE THE MESSAGE
            # Using page.evaluate to inject text directly into the DOM.
            # This bypasses browser typing issues and guarantees the text appears on screen.
            log("INFO", f"Typing {len(text)} chars...")
            await self.page.evaluate(
                f"el => {{ el.innerText = '{text}'; el.textContent = '{text}'; }}"
            )
            
            # Wait for the text to render on screen
            await asyncio.sleep(1.0)
            
            # 5. Send the message
            await asyncio.sleep(0.5)
            if not await self._click_first(C["send"], 3000):
                log("INFO", "Send button not found, pressing Enter...")
                await self.page.keyboard.press("Enter")
            
            log("INFO", "Message sent successfully")
            return True
            
        except Exception as e:
            log("ERROR", f"Failed to type/send message: {e}")
            await self._screenshot("typing_failed")
            return False

    async def _paste_warning_visible(self) -> bool:
        C = self.sel["chat"]
        words = [w.lower() for w in C.get("paste_warning_text", ["paste", "copy"])]
        for s in C.get("paste_warning", []):
            try:
                for el in await self.page.query_selector_all(s):
                    if await el.is_visible():
                        t = (await el.inner_text()).lower()
                        if any(w in t for w in words):
                            return True
            except Exception:
                continue
        return False

    async def _dump_dom_hints(self, tag: str):
        try:
            data = await self.page.evaluate("""() => {
              const testids = [...document.querySelectorAll('[data-testid]')]
                .map(e => e.tagName.toLowerCase() + '[data-testid="' + e.dataset.testid + '"]');
              const classes = new Set();
              document.querySelectorAll('[class]').forEach(e => {
                const c = e.className;
                if (typeof c === "string" && /message|chat|profile|sidebar|customer|entertainment|player|input|send|warn|alert|toast/i.test(c))
                  classes.add(e.tagName.toLowerCase() + '.' + c.trim().split(/\\s+/).join('.'));
              });
              return { url: location.href, testids: [...new Set(testids)], classes: [...classes] };
            }""")
            d = LOG_DIR / "inspection"
            d.mkdir(parents=True, exist_ok=True)
            path = d / f"{datetime.now():%Y%m%d_%H%M%S}_{tag}.txt"
            path.write_text(f"URL: {data['url']}\n\nDATA-TESTIDS:\n" + "\n".join(data["testids"]) +
                            "\n\nRELEVANT CLASSES:\n" + "\n".join(sorted(data["classes"])), encoding="utf-8")
            log("INFO", f"DOM hints written to logs/inspection/{path.name}")
        except Exception as e:
            log("WARNING", f"DOM dump failed: {e}")

    async def _inspection_session(self):
        await self._dump_dom_hints("lobby")
        print("\n" + "-" * 60)
        print("INSPECTION MODE")
        print(" - Playwright Inspector is open. Use 'Pick locator' to grab selectors.")
        print(" - Everything the page does with paste/input/key events is printed here as [PAGE] lines.")
        print(" - Open a chat, then press Resume (play button) in the Inspector to continue.")
        print("-" * 60 + "\n")
        await self.page.pause()
        await self._dump_dom_hints("chat")
        answer = await asyncio.to_thread(input, "Run a typing test into the chat input now? (y/n): ")
        if answer.strip().lower().startswith("y"):
            box = await self._first(self.sel["chat"]["input"], 5000)
            if not box:
                log("ERROR", "No input found with current selectors, update data/selectors.json")
                return
            await box.click()
            await self.typer.type("just testing how this feels, ignore me. what are you up to tonight?")
            await asyncio.sleep(1.5)
            flagged = await self._paste_warning_visible()
            log("INFO", f"Typing test finished. Paste warning visible: {flagged}")
            if flagged:
                await self._screenshot("inspect_paste_warning")
            await asyncio.to_thread(input, "Look at the [PAGE] lines above. Press Enter to clear the box and continue in dry-run... ")
            await box.fill("")


async def run_web_bot(settings: dict, dry_run: bool = False, inspect: bool = False):
    adapter = ChatHomeBaseAdapter(settings, dry_run=dry_run, inspect=inspect)
    try:
        await adapter.start()
    except KeyboardInterrupt:
        print("\n[INFO] Stopped")
    finally:
        await adapter.stop()