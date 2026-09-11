ChatHomeBase Bot - Live Platform Setup
======================================

REQUIREMENTS:
- Windows 10/11
- Python 3.9 or higher (from python.org)
- Internet connection

WHAT THIS BOT DOES:
- Automatically logs into chathomebase.com
- Scrapes player profile from right sidebar (name, occupation, etc.)
- Scrapes customer profile from left sidebar when chat starts
- Analyzes images sent by customers (if OpenAI key provided)
- Responds to customer messages using AI
- Sends follow-up messages if customer hasn't replied
- Runs multiple accounts concurrently

SETUP:
1. Double-click SETUP.bat
2. Enter your details:
   - DeepSeek API key (from platform.deepseek.com)
   - ChatHomeBase login credentials
   - Optional: OpenAI API key (for image analysis)
   - Optional: Telegram settings for notifications
3. Wait for installation

RUN:
1. Double-click LAUNCH.bat
2. Browser opens and logs in automatically
3. Bot waits for chat assignments
4. When chat starts, bot scrapes profiles and responds automatically

MULTIPLE ACCOUNTS:
To run multiple accounts at the same time:
1. Copy this entire folder
2. Paste it in same location
3. Rename the copy (e.g., "Account-2")
4. Run SETUP.bat in new folder (enter different credentials)
5. Run LAUNCH.bat in both folders

Each account runs independently!

FEATURES:
- Auto-sends messages (no approval needed)
- 30-second login timeout with retry
- Image analysis and compliments (with OpenAI key)
- Follow-up messages when customer hasn't replied
- Profile auto-scraping (no manual entry needed)

COSTS:
- DeepSeek API: ~$0.001-0.002 per message
- OpenAI Vision: ~$0.01-0.02 per image (optional)

SUPPORT:
Contact: [your contact]