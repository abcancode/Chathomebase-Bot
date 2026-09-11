"""First-run setup wizard for LIVE web platform."""

from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.rule import Rule

console = Console()


def run_wizard(config_file: Path):
    """Run setup wizard for live web platform."""
    console.print(Panel.fit(
        "[bold cyan]ChatHomeBase Bot Setup[/bold cyan]\n"
        "Live Platform Version - Profiles auto-scraped from website",
        title="Welcome",
        border_style="cyan"
    ))
    
    # Check if updating existing
    existing = {}
    if config_file.exists():
        from config.settings import load_settings
        existing = load_settings(config_file)
        console.print("[yellow]Updating existing configuration...[/yellow]\n")
    
    console.rule("[bold]Your DeepSeek API Key[/bold]")
    console.print("Each user needs their own DeepSeek API key.")
    console.print("Get yours from: [cyan]platform.deepseek.com[/cyan]")
    deepseek_key = Prompt.ask("DeepSeek API key", 
                               default=existing.get("deepseek_api_key", "")).strip()
    
    console.rule("[bold]ChatHomeBase Credentials[/bold]")
    chb_email = Prompt.ask("ChatHomeBase email", 
                          default=existing.get("chathomebase_login", "")).strip()
    chb_password = Prompt.ask("ChatHomeBase password", 
                               password=True).strip()
    
    # Optional: Proxy
    console.rule("[bold]Proxy (Optional)[/bold]")
    use_proxy = Confirm.ask("Use proxy?", default=False)
    proxy = None
    if use_proxy:
        proxy_server = Prompt.ask("Proxy server (e.g., http://proxy:8080 or socks5://user:pass@host:port)").strip()
        if proxy_server:
            proxy = {"server": proxy_server}
    
    # Optional: Telegram notifications
    console.rule("[bold]Telegram Notifications (Optional)[/bold]")
    use_telegram = Confirm.ask("Enable Telegram low-balance alerts?", default=False)
    
    telegram_token = None
    telegram_user_id = None
    
    if use_telegram:
        console.print("Get your bot token from @BotFather")
        telegram_token = Prompt.ask("Telegram bot token").strip()
        console.print("Get your user ID from @userinfobot")
        telegram_user_id = Prompt.ask("Telegram user ID").strip()
    
    # Optional: OpenAI for vision
    console.rule("[bold]Image Analysis (Optional)[/bold]")
    use_vision = Confirm.ask("Enable image analysis? (Requires OpenAI API key)", default=False)
    
    openai_key = None
    if use_vision:
        console.print("Get your key from: [cyan]platform.openai.com[/cyan]")
        openai_key = Prompt.ask("OpenAI API key").strip()
    
    # Build settings
    settings = {
        **existing,
        "deepseek_api_key": deepseek_key,
        "chathomebase_login": chb_email,
        "chathomebase_password": chb_password,
        "proxy": proxy,
        "telegram_bot_token": telegram_token,
        "telegram_user_id": telegram_user_id,
        "openai_api_key": openai_key,
        "deepseek_low_balance_threshold_usd": 4.0,
    }
    
    # Save
    from config.settings import save_settings
    save_settings(config_file, settings)
    
    console.print("\n[green]✓ Setup complete![/green]")
    console.print("[cyan]Player and customer profiles will be auto-scraped from chathomebase.com[/cyan]")
    if proxy:
        console.print(f"[yellow]Proxy configured: {proxy['server']}[/yellow]")
    console.print("Run [bold]LAUNCH.bat[/bold] to start the bot.\n")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from pathlib import Path
    run_wizard(Path("config/settings.json"))