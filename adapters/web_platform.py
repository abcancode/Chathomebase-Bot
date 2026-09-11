"""Web automation for chathomebase.com — Auto-assignment with profile scraping."""

import asyncio
import json
import re
import random
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict
from playwright.async_api import async_playwright, Page, Browser, BrowserContext

from core.deepseek_client import DeepSeekClient
from core.rule_guard import RuleGuard
from core.logbook import Logbook
from core.prompt_builder import load_rules, build_system_prompt, build_history_messages
from core.excuse_bank import DynamicExcuseGenerator


class ChatHomeBaseAdapter:
    """Auto-assignment bot that scrapes profiles from platform."""
    
    def __init__(self, settings: dict, dry_run: bool = False):
        self.settings = settings
        self.dry_run = dry_run
        self.proxy = settings.get("proxy")
        
        # Bot brain
        data_dir = Path(__file__).parent.parent / "data"
        log_dir = Path(__file__).parent.parent / "logs" / "logbooks"
        
        self.rules = load_rules(data_dir / "rules.json")
        self.guard = RuleGuard(
            data_dir / "rules.json",
            data_dir / "banned_phrases.json",
            "Customer"
        )
        self.deepseek = DeepSeekClient(
            api_key=settings["deepseek_api_key"],
            guard=self.guard,
            low_balance_threshold_usd=settings.get("deepseek_low_balance_threshold_usd", 4.0),
            max_retries=3
        )
        self.logbook = Logbook(log_dir, settings.get("customer_name", "Customer"))
        
        # Excuse generator for follow-ups
        self.excuse_generator = DynamicExcuseGenerator(
            self.deepseek,
            settings.get("player_occupation", "")
        )
        
        # Telegram
        self.telegram_enabled = bool(settings.get("telegram_user_id") and settings.get("telegram_bot_token"))
        if self.telegram_enabled:
            from telegram_notify.notifier import TelegramNotifier
            self.notifier = TelegramNotifier(settings.get("telegram_bot_token"))
            self.telegram_user_id = settings.get("telegram_user_id")
        
        # OpenAI for vision
        self.openai_enabled = bool(settings.get("openai_api_key"))
        self.openai_key = settings.get("openai_api_key")
        
        # Web
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
        # Scraped profiles
        self.customer_profile: Dict = {}
        self.player_profile: Dict = {}
        
    async def start(self):
        """Launch and process assignments."""
        print(f"\n{'='*60}")
        print(f"ChatHomeBase Bot")
        print(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        print(f"{'='*60}\n")
        
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=False, 
            proxy=self.proxy,
            args=["--start-fullscreen", "--force-device-scale-factor=0.95"],
            slow_mo=100
        )
        self.context = await self.browser.new_context(
            viewport={"width": 1280, "height": 720}, 
            proxy=self.proxy
        )
        self.page = await self.context.new_page()
        
        # Check balance before login
        await self._check_balance()
        
        # Login with retry
        logged_in = False
        for attempt in range(3):
            try:
                logged_in = await self._login()
                if logged_in:
                    break
            except Exception as e:
                print(f"[WARNING] Login attempt {attempt+1} failed: {e}")
                if attempt < 2:
                    print("[INFO] Retrying in 5 seconds...")
                    await asyncio.sleep(5)
        
        if not logged_in:
            print("[ERROR] Could not log in after 3 attempts")
            await self.stop()
            return
        
        print("[INFO] Waiting for chat assignments...")
        print("        (Profiles will be scraped when chat loads)\n")
        
        await self._process_assignments()
        
    async def _process_assignments(self):
        """Process chat assignments with platform history."""
        while True:
            try:
                if not await self._wait_for_assignment():
                    await asyncio.sleep(2)
                    continue
                
                print(f"\n{'='*60}")
                print(f"New Assignment")
                print(f"{'='*60}")
                
                # SCRAPE PROFILES
                self.customer_profile = await self._extract_customer_profile()
                self.player_profile = await self._extract_player_profile()
                
                # Update excuse generator with scraped occupation
                self.excuse_generator = DynamicExcuseGenerator(
                    self.deepseek,
                    self.player_profile.get("occupation", self.settings.get("player_occupation", ""))
                )
                
                # READ PLATFORM HISTORY (previous conversations)
                platform_history = await self._read_platform_history()
                
                # Update settings
                self.settings["player_name"] = self.player_profile.get("name", "Player")
                self.settings["player_occupation"] = self.player_profile.get("occupation", "Worker")
                self.guard.customer_first_name = self.customer_profile.get("name", "Customer").split()[0]
                
                print(f"[INFO] Player: {self.player_profile.get('name')}")
                print(f"[INFO] Customer: {self.customer_profile.get('name')}")
                
                if platform_history:
                    print(f"[INFO] Previous conversation: {len(platform_history)} messages")
                    await self._extract_facts_from_history(platform_history)
                
                await self._process_current_chat()
                await self._wait_for_chat_close()
                print("[INFO] Waiting for next assignment...")
                
            except Exception as e:
                print(f"[ERROR] {e}")
                await asyncio.sleep(5)
                
    async def _extract_customer_profile(self) -> Dict:
        """Scrape customer profile from LEFT sidebar."""
        profile = {}
        
        try:
            selectors = [
                "[data-testid='customerProfile']",
                ".customer-profile",
                ".left-sidebar",
                ".chat-sidebar-left"
            ]
            
            profile_text = ""
            for selector in selectors:
                try:
                    profile_text = await self.page.inner_text(selector, timeout=30000)
                    if profile_text:
                        break
                except:
                    continue
            
            # Extract fields
            patterns = {
                "name": r'Name[:\s]+([A-Za-z\s]+?)(?=\n|Age|Location|$)',
                "age": r'Age[:\s]+(\d+)',
                "location": r'Location[:\s]+([^\n]+)',
                "occupation": r'Occupation[:\s]+([^\n]+)',
                "eyes": r'(Blue|Brown|Green|Hazel) eyes?',
                "height": r'(\d+ft[\s\din-]+)',
                "body_type": r'(Slim|Athletic|Curvaceous|Average)',
                "status": r'(Single|Married|Divorced)',
            }
            
            for field, pattern in patterns.items():
                match = re.search(pattern, profile_text, re.IGNORECASE)
                if match:
                    profile[field] = match.group(1).strip()
            
            # About sections
            for section in ["About me", "About you", "Hobbies"]:
                match = re.search(f'{section}[:\s]*\n?([^\\n]+)', profile_text, re.IGNORECASE)
                if match:
                    profile[section.lower().replace(" ", "_")] = match.group(1).strip()
                    
        except Exception as e:
            print(f"[WARNING] Customer profile error: {e}")
            profile["name"] = "Customer"
        
        return profile
        
    async def _extract_player_profile(self) -> Dict:
        """Scrape PLAYER profile from RIGHT sidebar."""
        profile = {}
        
        try:
            selectors = [
                "[data-testid='playerProfile']",
                ".player-profile",
                ".right-sidebar",
                ".chat-sidebar-right",
                ".entertainment-profile"
            ]
            
            profile_text = ""
            for selector in selectors:
                try:
                    profile_text = await self.page.inner_text(selector, timeout=2000)
                    if profile_text:
                        break
                except:
                    continue
            
            patterns = {
                "name": r'Name[:\s]+([A-Za-z\s]+?)(?=\n|Age|Location|$)',
                "age": r'Age[:\s]+(\d+)',
                "occupation": r'Occupation[:\s]+([^\n]+)',
                "location": r'Location[:\s]+([^\n]+)',
                "eyes": r'(Blue|Brown|Green|Hazel) eyes?',
                "hair": r'(Blonde|Brunette|Red|Black|Brown) hair?',
                "body_type": r'(Slim|Athletic|Curvy|Average)',
            }
            
            for field, pattern in patterns.items():
                match = re.search(pattern, profile_text, re.IGNORECASE)
                if match:
                    profile[field] = match.group(1).strip()
            
            for section in ["About me", "Description", "Bio"]:
                match = re.search(f'{section}[:\s]*\n?([^\\n]+)', profile_text, re.IGNORECASE)
                if match:
                    profile["about"] = match.group(1).strip()
            
            # Fallbacks
            if not profile.get("name"):
                profile["name"] = self.settings.get("player_name") or "Player"
            if not profile.get("occupation"):
                profile["occupation"] = self.settings.get("player_occupation") or "Worker"
            if not profile.get("location"):
                profile["location"] = self.settings.get("player_location_cached")
                
        except Exception as e:
            print(f"[WARNING] Player profile error: {e}")
            profile = {
                "name": self.settings.get("player_name", "Player"),
                "occupation": self.settings.get("player_occupation", "Worker"),
                "location": self.settings.get("player_location_cached")
            }
        
        return profile
        
    async def _process_current_chat(self):
        """Process chat - respond to customer OR follow up if last message is from previous operator."""
        conversation = await self._read_conversation_history()
        print(f"[INFO] History: {len(conversation)} messages")
        
        if not conversation:
            return
        
        # Get last message
        last_msg = conversation[-1]
        
        if last_msg["speaker"] == "customer":
            # Customer spoke last - respond normally
            print(f"[INFO] Customer: {last_msg['text'][:60]}...")
            await self._check_for_new_info(last_msg["text"])
            await self._generate_response(last_msg, conversation, is_follow_up=False)
            
        elif last_msg["speaker"] == "player":
            # Previous operator spoke last, customer hasn't replied
            # Check if we already sent a follow-up
            consecutive_player = 0
            for msg in reversed(conversation):
                if msg["speaker"] == "player":
                    consecutive_player += 1
                else:
                    break
            
            if consecutive_player >= 2:
                print("[INFO] Already sent follow-up, waiting for customer...")
                return
            
            # Send follow-up with AI-generated excuse
            print("[INFO] No customer reply yet. Sending follow-up with excuse...")
            category = self._classify(last_msg["text"]) if last_msg["text"] else "casual"
            await self._send_follow_up_with_excuse(category)
        
    async def _send_follow_up_with_excuse(self, category: str = "casual"):
        """Send follow-up message with AI-generated excuse."""
        excuse = self.excuse_generator.generate_excuse(category)
        
        if excuse:
            print(f"[INFO] Generated excuse: {excuse[:80]}...")
            await self._type_response(excuse)
            await self._send_response()
        else:
            # Fallback simple follow-up
            fallbacks = [
                "Hey, you still there? What are you thinking about?",
                "Got quiet on me. What's on your mind?",
                "Still around? Tell me something interesting about you.",
                "You disappeared on me. What are you up to?"
            ]
            msg = random.choice(fallbacks)
            print(f"[INFO] Fallback follow-up: {msg}")
            await self._type_response(msg)
            await self._send_response()
        
    async def _check_for_new_info(self, customer_msg: str):
        """Check if customer asks for info and maintain consistency."""
        customer_lower = customer_msg.lower()
        
        # Profession - check logbook first
        if any(word in customer_lower for word in ["work", "job", "do for a living", "what do you do", "profession", "career"]):
            existing_prof = self.logbook.get_player_profession()
            
            if existing_prof:
                detail = self.logbook.get_profession_detail("detail")
                if not detail:
                    details = {
                        "teacher": ["English teacher", "preschool teacher", "high school math teacher"],
                        "doctor": ["general practitioner", "pediatrician", "nurse practitioner"],
                        "student": ["part-time barista", "part-time retail", "part-time tutor"],
                        "unemployed": ["between jobs", "looking for opportunities", "taking time off"]
                    }
                    base = existing_prof.lower()
                    if base in details:
                        detail = random.choice(details[base])
                        self.logbook.set_profession(existing_prof, detail, self.customer_profile.get("name"))
                        print(f"[INFO] Detailed profession: {detail}")
            else:
                # First time - invent profession
                professions = [
                    ("teacher", "English teacher"),
                    ("nurse", "pediatric nurse"),
                    ("receptionist", "hotel receptionist"),
                    ("waitress", "diner waitress"),
                    ("student", "part-time barista")
                ]
                base, detail = random.choice(professions)
                self.logbook.set_profession(base, detail, self.customer_profile.get("name"))
                self.player_profile["occupation"] = detail
                print(f"[INFO] Set profession: {detail}")
        
        # Client profession
        if any(phrase in customer_lower for phrase in ["i am a", "i work as", "my job is", "i'm a"]):
            patterns = [
                r'i am a[n]? ([\w\s]+)',
                r'i work as a[n]? ([\w\s]+)',
                r'my job is ([\w\s]+)',
                r'i\'m a[n]? ([\w\s]+)'
            ]
            for pattern in patterns:
                match = re.search(pattern, customer_lower)
                if match:
                    client_prof = match.group(1).strip()
                    self.logbook.add_entry("Client_Work", f"Client profession: {client_prof}", self.customer_profile.get("name"))
                    print(f"[INFO] Recorded client profession: {client_prof}")
                    break
        
        # Sexual preferences/fantasies
        if any(word in customer_lower for word in ["fantasy", "dream", "like to try", "never tried", "experience"]):
            if "i've never" in customer_lower or "i want to" in customer_lower:
                self.logbook.add_entry("Sexual", f"Customer shared: {customer_msg[:100]}", self.customer_profile.get("name"))
        
        # Health mentions
        if any(word in customer_lower for word in ["sick", "surgery", "medical", "health", "migraine", "glasses", "smoke"]):
            self.logbook.add_entry("Health", f"Customer health info: {customer_msg[:100]}", self.customer_profile.get("name"))
        
        # Photos received
        if "[Customer shared a photo:" in customer_msg:
            photo_desc = customer_msg.split("[Customer shared a photo:")[1].split("]")[0]
            self.logbook.add_entry("Update", f"Photo received: {photo_desc}", self.customer_profile.get("name"))
            
    async def _generate_response(self, last_msg: Dict, conversation: List[Dict], is_follow_up: bool = False):
        """Generate response using scraped profiles."""
        recent = conversation[-15:]
        category = self._classify(last_msg["text"]) if not is_follow_up else "casual"
        
        if is_follow_up:
            print("[INFO] Generating follow-up message...")
        
        system_prompt = build_system_prompt(
            rules=self.rules,
            player_name=self.player_profile.get("name", "Player"),
            player_occupation=self.player_profile.get("occupation", "Worker"),
            player_location=self.player_profile.get("location"),
            customer_name=self.customer_profile.get("name", "Customer"),
            customer_location=self.customer_profile.get("location", "Unknown"),
            logbook_summary=self._build_summary(),
            category=category,
            past_replies=[m["text"] for m in recent if m["speaker"] == "player"][-10:],
            user_message=last_msg["text"],
            is_follow_up=is_follow_up
        )
        
        history = [{"role": "user" if m["speaker"] == "customer" else "assistant", "content": m["text"]} 
                   for m in recent]
        
        result = self.deepseek.generate(system_prompt, history, user_message=last_msg["text"], temperature=0.95)
        
        if result["ok"]:
            reply = result["text"]
            print(f"[INFO] Bot: {reply[:80]}...")
            await self._type_response(reply)
            await self._send_response()
        else:
            print(f"[ERROR] {result['error']}")

    async def _read_platform_history(self) -> List[Dict]:
        """Read previous conversation history from center of interface."""
        messages = []
        
        try:
            # Look for historical messages (marked differently than current chat)
            all_bubbles = await self.page.query_selector_all(".message-blob, .chat-message")
            
            for bubble in all_bubbles:
                try:
                    classes = await bubble.get_attribute("class") or ""
                    
                    # Check if this is marked as historical/old
                    is_old = any(marker in classes for marker in ["old", "previous", "history", "past", "read-only", "archived"])
                    
                    if not is_old:
                        continue  # Skip current chat messages
                    
                    text_elem = await bubble.query_selector(".message-content, .text")
                    text = await text_elem.inner_text() if text_elem else ""
                    
                    if "customer" in classes or "client" in classes:
                        speaker = "customer"
                    elif "entertainment" in classes or "player" in classes or "operator" in classes:
                        speaker = "player"
                    else:
                        continue
                    
                    if text.strip():
                        messages.append({
                            "speaker": speaker,
                            "text": text.strip(),
                            "is_historical": True
                        })
                        
                except:
                    continue
                    
        except Exception as e:
            print(f"[WARNING] Failed to read platform history: {e}")
        
        if messages:
            print(f"[INFO] Loaded {len(messages)} messages from platform history")
            
        return messages
    
    async def _extract_facts_from_history(self, history: List[Dict]):
        """Scan previous conversation for facts player shared."""
        player_messages = [m["text"] for m in history if m["speaker"] == "player"]
        
        for msg in player_messages:
            msg_lower = msg.lower()
            
            # Extract profession mentions
            if any(phrase in msg_lower for phrase in ["i am a", "i'm a", "i work as", "my job is"]):
                patterns = [
                    r'i am a[n]? ([\w\s]+?)(?:\.|$)',
                    r'i\'m a[n]? ([\w\s]+?)(?:\.|$)',
                    r'i work as a[n]? ([\w\s]+?)(?:\.|$)',
                    r'my job is ([\w\s]+?)(?:\.|$)'
                ]
                for pattern in patterns:
                    match = re.search(pattern, msg_lower)
                    if match:
                        job = match.group(1).strip()
                        if not self.logbook.get_player_profession():
                            self.logbook.set_profession(job, client=self.customer_profile.get("name"))
                            print(f"[INFO] Extracted profession from history: {job}")
                        break
            
            # Extract location mentions
            if "i live in" in msg_lower or "i'm from" in msg_lower or "i am from" in msg_lower:
                patterns = [
                    r'i live in ([\w\s,]+?)(?:\.|$)',
                    r'i\'m from ([\w\s,]+?)(?:\.|$)',
                    r'i am from ([\w\s,]+?)(?:\.|$)'
                ]
                for pattern in patterns:
                    match = re.search(pattern, msg_lower)
                    if match:
                        loc = match.group(1).strip()
                        self.logbook.add_entry("Work", f"Location mentioned: {loc}", self.customer_profile.get("name"))
                        print(f"[INFO] Extracted location from history: {loc}")
                        break

    def _build_summary(self) -> str:
        """Build summary from profiles + logbook."""
        parts = []
        
        if self.player_profile.get("age"):
            parts.append(f"Player Age: {self.player_profile['age']}")
        if self.player_profile.get("occupation"):
            parts.append(f"Player Work: {self.player_profile['occupation']}")
        if self.player_profile.get("location"):
            parts.append(f"Player Location: {self.player_profile['location']}")
        if self.player_profile.get("about"):
            parts.append(f"Player Bio: {self.player_profile['about'][:100]}")
        
        if self.customer_profile.get("age"):
            parts.append(f"Customer Age: {self.customer_profile['age']}")
        if self.customer_profile.get("about_me"):
            parts.append(f"Customer: {self.customer_profile['about_me'][:80]}")
        
        entries = self.logbook.all_entries()[-5:]
        for e in entries:
            parts.append(f"[{e['category']}] {e['comment'][:60]}")
        
        return "\n".join(parts) if parts else "(No profile data)"
        
    async def _read_conversation_history(self) -> List[Dict]:
        """Read all messages including image detection."""
        messages = []
        bubbles = await self.page.query_selector_all(".message-blob, .chat-message")
        
        for bubble in bubbles:
            try:
                classes = await bubble.get_attribute("class") or ""
                
                if "message-customer" in classes or "customer" in classes:
                    speaker = "customer"
                elif "message-entertainment" in classes or "entertainment" in classes:
                    speaker = "player"
                else:
                    continue
                
                # Get text content
                text_elem = await bubble.query_selector(".message-content, .text")
                text = await text_elem.inner_text() if text_elem else ""
                
                # Check for images
                image_elem = await bubble.query_selector("img, .message-image, [data-testid='messageImage']")
                if image_elem and speaker == "customer":
                    image_url = await image_elem.get_attribute("src")
                    if image_url:
                        print(f"[INFO] Customer sent image")
                        image_desc = await self._analyze_image(image_url)
                        text += f" [Customer shared a photo: {image_desc}]"
                
                if text.strip():
                    messages.append({"speaker": speaker, "text": text.strip()})
                    
            except Exception as e:
                continue
        
        return messages
    
    async def _analyze_image(self, image_url: str) -> str:
        """Analyze image using OpenAI Vision if enabled."""
        if not self.openai_enabled:
            return "photo"
        
        try:
            # Download image
            response = await self.page.evaluate(f"""
                async () => {{
                    const res = await fetch("{image_url}");
                    const blob = await res.blob();
                    return new Promise((resolve) => {{
                        const reader = new FileReader();
                        reader.onloadend = () => resolve(reader.result);
                        reader.readAsDataURL(blob);
                    }});
                }}
            ''')
            
            if response and ',' in response:
                base64_data = response.split(',')[1]
                
                # Use OpenAI to analyze
                import openai
                client = openai.AsyncOpenAI(api_key=self.openai_key)
                
                result = await client.chat.completions.create(
                    model="gpt-4-vision-preview",
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Describe this image briefly and compliment what you see. If it's a person/selfie/nude, be flattering and appreciative. Keep it under 20 words."},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_data}"}}
                        ]
                    }],
                    max_tokens=60
                )
                
                desc = result.choices[0].message.content
                print(f"[INFO] Image analysis: {desc[:60]}...")
                return desc
                
        except Exception as e:
            print(f"[WARNING] Image analysis failed: {e}")
        
        return "photo"
        
    async def _type_response(self, text: str):
        await self.page.click("[data-testid='messageTextArea'], .chat-input")
        await self.page.fill("[data-testid='messageTextArea'], .chat-input", "")
        for i, char in enumerate(text):
            await self.page.fill("[data-testid='messageTextArea'], .chat-input", text[:i+1])
            await asyncio.sleep(0.01)
            
    async def _send_response(self):
        if self.dry_run:
            print("[DRY RUN] Review and press Enter...")
            input()
            await self.page.fill("[data-testid='messageTextArea'], .chat-input", "")
            return
        await self.page.click("[data-testid='sendChatMessageButton'], .send-button")
        print("[INFO] Sent")
        
    def _classify(self, text: str) -> str:
        t = text.lower()
        if any(k in t for k in ["sex", "fuck", "cock", "pussy"]):
            return "sexual"
        if any(k in t for k in ["sexy", "beautiful", "kiss"]):
            return "flirty"
        return "casual"
        
    async def _wait_for_assignment(self) -> bool:
        try:
            await self.page.wait_for_selector(".message-blob, .chat-message", timeout=10000)
            return True
        except:
            return False
            
    async def _wait_for_chat_close(self):
        for _ in range(60):
            chat = await self.page.query_selector(".message-blob")
            if not chat:
                return True
            await asyncio.sleep(1)
        return True
        
    async def _check_balance(self):
        balance = self.deepseek.check_balance()
        print(f"[INFO] DeepSeek balance: ${balance:.2f}")
        if balance < 4.0 and self.telegram_enabled:
            try:
                self.notifier.notify_low_balance(self.telegram_user_id, balance, 4.0)
            except:
                pass
        
    async def _login(self):
        """Login to chathomebase with retry logic and extended timeout."""
        print("[INFO] Logging in...")
        
        try:
            # Navigate to login page
            await self.page.goto("https://chathomebase.com/login")
            
            # Fill credentials
            await self.page.fill("input[name='email']", self.settings["chathomebase_login"])
            await self.page.fill("input[name='password']", self.settings["chathomebase_password"])
            
            # Click login button
            await self.page.click("[data-testid='signInButton']")
            
            # Wait for navigation to lobby - 30 SECOND TIMEOUT
            await self.page.wait_for_url("**/chat/lobby", timeout=30000)
            
            print("[INFO] Successfully logged in")
            
        except Exception as e:
            # Check current URL to diagnose
            current_url = self.page.url
            print(f"[ERROR] Login failed. Current URL: {current_url}")
            print(f"[ERROR] Timeout waiting for /chat/lobby: {e}")
            raise
        
        # Handle announcements dialog
        for _ in range(5):
            try:
                await self.page.click("[data-testid='announcementsDialogNextButton']", timeout=2000)
                await asyncio.sleep(0.5)
            except:
                break
        try:
            await self.page.click("[data-testid='announcementsDialogContinueButton']", timeout=2000)
        except:
            pass
            
        print("[INFO] Ready for assignments")
        return True
        
    async def stop(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()


async def run_web_bot(settings: dict, dry_run: bool = False):
    adapter = ChatHomeBaseAdapter(settings, dry_run=dry_run)
    try:
        await adapter.start()
    except KeyboardInterrupt:
        print("\n[INFO] Stopped")
    finally:
        await adapter.stop()