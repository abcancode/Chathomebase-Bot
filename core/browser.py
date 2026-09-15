from pathlib import Path
from typing import Optional, Tuple

from playwright.async_api import async_playwright, BrowserContext, Page, Playwright

INSPECT_SIZE = (1280, 720)

# For Windows: NO sandbox flags (they cause the warning on Windows)
BASE_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-infobars",
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--disable-features=VizDisplayCompositor",
    "--disable-ipc-flooding-protection",
    "--disable-dev-shm-usage",
    "--disable-webgl",
    "--disable-webrtc",
    "--disable-audio-api",
    "--disable-gpu",
    "--disable-web-security",
    "--disable-features=IsolateOrigins,site-per-process",
    "--disable-site-isolation-trials",
]

STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {
  get: () => undefined,
});
Object.defineProperty(navigator, 'plugins', {
  get: () => [1, 2, 3, 4, 5],
});
Object.defineProperty(navigator, 'languages', {
  get: () => ['en-US', 'en'],
});
"""

INSPECTOR_JS = r"""
(() => {
  const seen = new Set();
  const log = (m) => { try { window.chbLog(m); } catch (e) { console.log('[CHB]', m); } };
  const desc = (t) => {
    if (!t || !t.tagName) return String(t && t.constructor && t.constructor.name || t);
    let s = t.tagName.toLowerCase();
    if (t.id) s += '#' + t.id;
    if (t.dataset && t.dataset.testid) s += '[data-testid=' + t.dataset.testid + ']';
    if (typeof t.className === 'string' && t.className) s += '.' + t.className.trim().split(/\s+/).slice(0, 3).join('.');
    return s;
  };
  const watched = ['paste', 'copy', 'cut', 'beforeinput', 'input', 'keydown', 'keypress', 'keyup', 'drop', 'compositionstart'];
  const orig = EventTarget.prototype.addEventListener;
  EventTarget.prototype.addEventListener = function (type, listener, opts) {
    if (watched.includes(type)) {
      const key = type + '@' + desc(this);
      if (!seen.has(key)) { seen.add(key); log('listener registered: ' + key); }
    }
    return orig.call(this, type, listener, opts);
  };
  const attach = () => {
    ['paste', 'beforeinput', 'input', 'keydown'].forEach((type) => {
      document.addEventListener(type, (e) => {
        if (type === 'keydown' && !(e.ctrlKey || e.metaKey)) return;
        log(type + ' target=' + desc(e.target) + ' inputType=' + (e.inputType || '') +
            ' isTrusted=' + e.isTrusted + ' dataLen=' + ((e.data || '').length) +
            (type === 'keydown' ? ' key=' + e.key : ''));
      }, true);
    });
    const mo = new MutationObserver((muts) => {
      for (const m of muts) for (const n of m.addedNodes) {
        if (n.nodeType === 1) {
          const txt = (n.innerText || '');
          if (/paste|copy|copied/i.test(txt) && txt.length < 400) {
            log('WARNING ELEMENT APPEARED: ' + desc(n) + ' :: ' + txt.replace(/\s+/g, ' ').slice(0, 160));
          }
        }
      }
    });
    if (document.body) mo.observe(document.body, { childList: true, subtree: true });
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', attach); else attach();
})();
"""


async def launch_browser(
    user_data_dir: Path,
    proxy_config: Optional[dict] = None,
    inspect: bool = False,
    channel: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Tuple[Playwright, BrowserContext, Page]:
    pw = await async_playwright().start()
    kwargs = dict(
        headless=False,
        proxy=proxy_config,
        ignore_default_args=["--enable-automation"],
        locale="en-US",
    )
    
    if inspect:
        w, h = INSPECT_SIZE
        kwargs["args"] = BASE_ARGS + [f"--window-size={w},{h}"]
        kwargs["viewport"] = {"width": w, "height": h}
    else:
        kwargs["args"] = BASE_ARGS + ["--start-maximized"]
        kwargs["no_viewport"] = True
        
    if user_agent:
        kwargs["user_agent"] = user_agent

    # Use your actual Chrome profile
    actual_profile = Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "User Data" / "Default"
    
    if not actual_profile.exists():
        print(f"[WARNING] Chrome profile not found at {actual_profile}")
        print(f"Using fallback profile: {user_data_dir}")
        actual_profile = user_data_dir
    
    user_data_dir = actual_profile
    
    print(f"[INFO] Using Chrome profile: {user_data_dir}")
    print(f"[INFO] Sandbox flags: OFF (Windows mode)")
    
    user_data_dir.mkdir(parents=True, exist_ok=True)
    context = None
    for ch in ([channel] if channel else ["chrome", None]):
        try:
            context = await pw.chromium.launch_persistent_context(str(user_data_dir), channel=ch, **kwargs)
            print(f"[INFO] Browser: {ch or 'bundled chromium'} ({'inspect 1280x720' if inspect else 'maximised'})")
            break
        except Exception as e:
            print(f"[WARNING] Could not launch {ch or 'bundled chromium'}: {str(e).splitlines()[0]}")
    if context is None:
        await pw.stop()
        raise RuntimeError("No browser available. Run: python -m playwright install chromium")

    await context.add_init_script(STEALTH_JS)
    page = context.pages[0] if context.pages else await context.new_page()
    
    await page.bring_to_front()
    
    return pw, context, page