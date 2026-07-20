"""Shared browser context — patchright (stealth-patched Playwright), headed.

Hard-won finding from live testing against EB Games:
  • vanilla Playwright (headless OR headed) -> Cloudflare "Just a moment…" forever.
  • patchright HEADLESS -> still blocked.
  • patchright HEADED  -> passes instantly (real page, all products).
Cloudflare fingerprints the automation, not just the IP, so we MUST run headed with
patchright. A real browser window will appear while the collector runs — that's expected.

We keep ONE persistent context across all retailers so each site is challenged at most
once per run, and clearance cookies persist between runs (dir is git-ignored).

patchright stealth works best with NO custom user-agent, NO extra chromium args, and NO
automation-touching init scripts — so we deliberately don't set any. Don't "harden" this
by adding --disable-blink-features etc.; that re-introduces the leaks patchright removes.
"""
import os
from contextlib import contextmanager
from pathlib import Path

from patchright.sync_api import sync_playwright

USER_DATA = Path(__file__).parent / ".pw-user-data"  # git-ignored; holds CF clearance cookies


@contextmanager
def browser_context():
    # Headed by default (headless is blocked by Cloudflare). HEADLESS=1 is debug-only,
    # for non-protected pages.
    headless = os.getenv("HEADLESS", "0") == "1"
    USER_DATA.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(USER_DATA),
            channel="chromium",
            headless=headless,
            locale="en-CA",
            timezone_id="America/Vancouver",
            viewport={"width": 1440, "height": 900},
        )
        try:
            yield ctx
        finally:
            ctx.close()


def settle(page, timeout=20000):
    """Let a Cloudflare/Akamai challenge (or SSR hydration) settle."""
    try:
        page.wait_for_load_state("networkidle", timeout=timeout)
    except Exception:
        pass
