"""First-run setup wizard."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rich.console import Console          # noqa: E402
from rich.panel import Panel              # noqa: E402
from rich.prompt import Prompt, Confirm   # noqa: E402

from config.settings import load_settings, save_settings  # noqa: E402

console = Console()


def _parse_proxy(proxy_input: str):
    proxy_input = proxy_input.strip()
    if not proxy_input:
        return None
    if proxy_input.count(":") >= 3 and not proxy_input.startswith("http") and not proxy_input.startswith("socks"):
        ip, port, username, *rest = proxy_input.split(":")
        password = ":".join(rest)
        return {"server": f"http://{username}:{password}@{ip}:{port}"}
    return {"server": proxy_input}


def run_wizard(config_file: Path):
    console.print(Panel.fit(
        "[bold cyan]ChatHomeBase Bot Setup[/bold cyan]\nProfiles are auto-scraped from the website",
        title="Welcome", border_style="cyan"))

    existing = load_settings(config_file) if config_file.exists() else {}
    if existing:
        console.print("[yellow]Updating existing configuration (leave blank to keep current values)[/yellow]\n")

    console.rule("[bold]DeepSeek API key[/bold]")
    console.print("Get yours from platform.deepseek.com")
    deepseek_key = Prompt.ask("DeepSeek API key", default=existing.get("deepseek_api_key", "")).strip()

    console.rule("[bold]ChatHomeBase credentials[/bold]")
    chb_email = Prompt.ask("ChatHomeBase email", default=existing.get("chathomebase_login", "")).strip()
    chb_password = Prompt.ask("ChatHomeBase password (blank = keep current)", password=True, default="").strip()
    if not chb_password:
        chb_password = existing.get("chathomebase_password", "")

    console.rule("[bold]Proxy (optional)[/bold]")
    proxy = existing.get("proxy")
    if Confirm.ask("Use proxy?", default=bool(proxy)):
        console.print("Formats: http://user:pass@host:port   or   1.2.3.4:8080:user:pass")
        default_proxy = proxy["server"] if proxy else ""
        proxy = _parse_proxy(Prompt.ask("Proxy server", default=default_proxy))
    else:
        proxy = None

    console.rule("[bold]Telegram alerts (optional)[/bold]")
    telegram_token = existing.get("telegram_bot_token")
    telegram_user_id = existing.get("telegram_user_id")
    if Confirm.ask("Enable Telegram alerts (low balance, login failures, paste warnings)?", default=bool(telegram_token)):
        console.print("Bot token from @BotFather, user ID from @userinfobot")
        telegram_token = Prompt.ask("Telegram bot token", default=telegram_token or "").strip() or None
        telegram_user_id = Prompt.ask("Telegram user ID", default=telegram_user_id or "").strip() or None
    else:
        telegram_token = telegram_user_id = None

    console.rule("[bold]Image analysis (optional)[/bold]")
    openai_key = existing.get("openai_api_key")
    if Confirm.ask("Enable image analysis (OpenAI key)?", default=bool(openai_key)):
        openai_key = Prompt.ask("OpenAI API key", default=openai_key or "").strip() or None
    else:
        openai_key = None

    # HARD CODED: 1 minute follow-up (no user input)
    followup = 1.0

    settings = {
        **existing,
        "deepseek_api_key": deepseek_key,
        "chathomebase_login": chb_email,
        "chathomebase_password": chb_password,
        "proxy": proxy,
        "telegram_bot_token": telegram_token,
        "telegram_user_id": telegram_user_id,
        "openai_api_key": openai_key,
        "openai_vision_model": existing.get("openai_vision_model", "gpt-4o-mini"),
        "deepseek_low_balance_threshold_usd": existing.get("deepseek_low_balance_threshold_usd", 4.0),
        "followup_after_minutes": followup,
        "typing_cpm_min": existing.get("typing_cpm_min", 190),
        "typing_cpm_max": existing.get("typing_cpm_max", 260),
        "allow_emoji": existing.get("allow_emoji", False),
        "browser_channel": existing.get("browser_channel", None),
        "nearby_miles": existing.get("nearby_miles", 40),
    }
    save_settings(config_file, settings)

    console.print("\n[green]Setup complete.[/green]")
    if proxy:
        console.print(f"[yellow]Proxy: {proxy['server']}[/yellow]")
    console.print("Run [bold]LAUNCH[/bold] to go live or [bold]INSPECT[/bold] to inspect the platform.\n")


if __name__ == "__main__":
    run_wizard(ROOT / "config" / "settings.json")