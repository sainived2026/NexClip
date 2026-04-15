"""
Nexearch — Playwright Publisher
=================================
Production Playwright-based publisher with anti-bot detection.
Supports: Instagram, TikTok, YouTube, LinkedIn, Twitter/X, Facebook.

Features:
- playwright-stealth for anti-detection
- Persistent login sessions (cookie storage)
- Human-like delays and mouse movements
- Per-platform upload flows
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger


async def _human_delay(min_ms: int = 500, max_ms: int = 2000):
    """Random human-like delay."""
    await asyncio.sleep(random.randint(min_ms, max_ms) / 1000)


async def _human_type(page, selector: str, text: str, delay_range=(50, 150)):
    """Type text with human-like character delays."""
    element = page.locator(selector)
    await element.click()
    await _human_delay(200, 500)
    for char in text:
        await element.press(char if len(char) == 1 else char)
        await asyncio.sleep(random.randint(*delay_range) / 1000)


async def _fill_first(page, selectors: List[str], text: str, delay_range=(50, 150)) -> str:
    """Fill the first selector that resolves successfully."""
    last_error = None
    for selector in selectors:
        try:
            await page.wait_for_selector(selector, timeout=5000)
            await _human_type(page, selector, text, delay_range=delay_range)
            return selector
        except Exception as exc:
            last_error = exc
    raise last_error or RuntimeError(f"No matching selector found in {selectors}")


async def _click_first(page, selectors: List[str], timeout: int = 5000) -> str:
    """Click the first visible selector that resolves successfully."""
    last_error = None
    for selector in selectors:
        try:
            await page.locator(selector).first.click(timeout=timeout)
            return selector
        except Exception as exc:
            last_error = exc
    raise last_error or RuntimeError(f"No clickable selector found in {selectors}")


def _describe_login_failure(platform: str, page_url: str, page_text: str = "") -> str:
    """Convert vague login failures into actionable platform-specific reasons."""
    url = (page_url or "").lower()
    text = (page_text or "").lower()

    if "recaptcha" in url or "captcha" in url:
        return f"{platform.capitalize()} login blocked by CAPTCHA/reCAPTCHA challenge"
    if platform == "tiktok" and ("/in/about" in url or "banned" in text or "unavailable" in text):
        return "TikTok web login/upload is unavailable in this region"
    if platform == "twitter" and "retry" in text:
        return "X/Twitter returned a retry/error page before login"
    if platform == "linkedin" and ("one-time link" in text or "weve emailed" in text or "we've emailed" in text):
        return "LinkedIn requested an email-based verification step instead of a normal sign-in"
    if platform == "threads" and "logged_out" in text:
        return "Threads returned to a logged-out state after login submit"
    if "incorrect" in text or "wrong password" in text or "try again" in text:
        return f"{platform.capitalize()} rejected the submitted credentials"
    if "verify" in text or "challenge" in text or "confirm your identity" in text:
        return f"{platform.capitalize()} requested an additional verification challenge"
    return f"Login failed for {platform}"


def _get_session_path(platform: str) -> str:
    """Get persistent browser session storage path."""
    session_dir = Path(__file__).resolve().parent.parent.parent / "arc" / "arc_agent_memory" / "browser_sessions" / platform
    session_dir.mkdir(parents=True, exist_ok=True)
    return str(session_dir / "state.json")


async def _create_stealth_browser(platform: str, headless: bool = False):
    """Create a stealth browser context with persistent sessions."""
    from playwright.async_api import async_playwright

    pw = await async_playwright().start()

    # Randomized viewport for anti-detection
    viewports = [
        {"width": 1366, "height": 768},
        {"width": 1440, "height": 900},
        {"width": 1536, "height": 864},
        {"width": 1920, "height": 1080},
    ]
    viewport = random.choice(viewports)

    # User agents pool
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    ]

    session_path = _get_session_path(platform)

    # Try to load existing session
    storage_state = session_path if os.path.exists(session_path) else None

    browser = await pw.chromium.launch(
        headless=headless,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            f"--window-size={viewport['width']},{viewport['height']}",
        ],
    )

    context = await browser.new_context(
        viewport=viewport,
        user_agent=random.choice(user_agents),
        locale="en-US",
        timezone_id="America/New_York",
        storage_state=storage_state,
        permissions=["geolocation"],
        color_scheme="light",
    )

    # Anti-detection: Override navigator.webdriver
    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
        });
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en'],
        });
        window.chrome = { runtime: {} };
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) =>
            parameters.name === 'notifications'
                ? Promise.resolve({ state: Notification.permission })
                : originalQuery(parameters);
    """)

    return pw, browser, context


async def _save_session(context, platform: str):
    """Save browser session for future reuse."""
    try:
        session_path = _get_session_path(platform)
        await context.storage_state(path=session_path)
        logger.info(f"Session saved for {platform}")
    except Exception as e:
        logger.warning(f"Could not save session for {platform}: {e}")


async def _verify_logged_in(page, platform: str, config: Dict[str, Any]) -> bool:
    """Verify that a post-login page state actually looks authenticated."""
    try:
        await page.wait_for_selector(config["logged_in_selector"], timeout=8000)
        logger.info(f"Verified active session for {platform} on current page")
        return True
    except Exception:
        pass

    page_url = (page.url or "").lower()
    page_text = ""
    try:
        page_text = ((await page.text_content("body")) or "").lower()
    except Exception:
        pass

    # Preserve challenge/login pages so the caller can report the real reason.
    if any(
        marker in page_url or marker in page_text
        for marker in (
            "captcha",
            "recaptcha",
            "challenge",
            "verify",
            "logged_out",
            "retry",
            "sign in",
            "log in",
        )
    ):
        return False

    try:
        await page.goto(config["check_url"], wait_until="domcontentloaded", timeout=30000)
        await _human_delay(1500, 2500)
        await page.wait_for_selector(config["logged_in_selector"], timeout=8000)
        logger.info(f"Verified active session for {platform} after redirecting to check URL")
        return True
    except Exception:
        return False


async def _login_if_needed(page, context, platform: str, credentials: Dict[str, str]) -> bool:
    """Check if logged in, if not perform login."""
    config = LOGIN_CHECKS.get(platform)
    if not config:
        logger.error(f"No login config for {platform}")
        return False

    # Navigate and check if already logged in
    await page.goto(config["check_url"], wait_until="domcontentloaded", timeout=30000)
    await _human_delay(2000, 4000)

    try:
        await page.wait_for_selector(config["logged_in_selector"], timeout=5000)
        logger.info(f"Already logged in to {platform}")
        return True
    except Exception:
        logger.info(f"Not logged in to {platform}, performing login...")
        login_started = await config["login_flow"](page, context, credentials)
        if not login_started:
            return False
        return await _verify_logged_in(page, platform, config)


# ═══════════════════════════════════════════════════════════
#  LOGIN FLOWS (per platform)
# ═══════════════════════════════════════════════════════════

async def _login_instagram(page, context, creds: Dict) -> bool:
    """Instagram login flow."""
    try:
        await page.goto("https://www.instagram.com/accounts/login/", wait_until="domcontentloaded")
        await _human_delay(2000, 3000)

        # Accept cookies if dialog appears
        try:
            await page.click('button:has-text("Allow")', timeout=3000)
        except Exception:
            pass

        username = creds.get("username", "")
        password = creds.get("password", "")
        await _fill_first(page, ['input[name="email"]', 'input[name="username"]'], username)
        await _human_delay(300, 700)
        await _fill_first(page, ['input[name="pass"]', 'input[name="password"]'], password)
        await _human_delay(500, 1000)
        try:
            await _click_first(page, ['div[aria-label="Log In"]', 'button:has-text("Log in")', 'button[type="submit"]'], timeout=8000)
        except Exception:
            await page.locator('input[name="pass"], input[name="password"]').first.press("Enter")
        await _human_delay(3000, 5000)

        # Handle "Save login info" prompt
        try:
            await page.click('button:has-text("Not Now")', timeout=5000)
        except Exception:
            pass

        # Handle notifications prompt
        try:
            await page.click('button:has-text("Not Now")', timeout=3000)
        except Exception:
            pass

        await _save_session(context, "instagram")
        return True
    except Exception as e:
        logger.error(f"Instagram login failed: {e}")
        return False


async def _login_tiktok(page, context, creds: Dict) -> bool:
    """TikTok login flow."""
    try:
        await page.goto("https://www.tiktok.com/login/phone-or-email/email", wait_until="domcontentloaded")
        await _human_delay(2000, 3000)

        await _fill_first(page, ['input[name="username"]', 'input[type="text"]'], creds["username"])
        await _human_delay(300, 700)
        await _fill_first(page, ['input[type="password"]'], creds["password"])
        await _human_delay(500, 1000)
        await _click_first(page, ['button[data-e2e="login-button"]', 'button:has-text("Log in")'], timeout=8000)
        await _human_delay(3000, 5000)

        await _save_session(context, "tiktok")
        return True
    except Exception as e:
        logger.error(f"TikTok login failed: {e}")
        return False


async def _login_youtube(page, context, creds: Dict) -> bool:
    """YouTube (Google) login flow."""
    try:
        await page.goto("https://accounts.google.com/signin", wait_until="domcontentloaded")
        await _human_delay(2000, 3000)

        await _fill_first(page, ['input[name="identifier"]', 'input[type="email"]'], creds["username"])
        await _human_delay(500, 1000)
        await _click_first(page, ['#identifierNext', 'button:has-text("Next")'], timeout=8000)
        await _human_delay(2000, 3000)

        await _fill_first(page, ['input[name="Passwd"]', 'input[type="password"]'], creds["password"])
        await _human_delay(500, 1000)
        await _click_first(page, ['#passwordNext', 'button:has-text("Next")'], timeout=8000)
        await _human_delay(3000, 5000)

        await _save_session(context, "youtube")
        return True
    except Exception as e:
        logger.error(f"YouTube login failed: {e}")
        return False


async def _login_linkedin(page, context, creds: Dict) -> bool:
    """LinkedIn login flow."""
    try:
        await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
        await _human_delay(2000, 3000)

        await _fill_first(page, ['#username', 'input[name="session_key"]'], creds["username"])
        await _human_delay(300, 700)
        await _fill_first(page, ['#password', 'input[name="session_password"]'], creds["password"])
        await _human_delay(500, 1000)
        await _click_first(page, ['button[type="submit"]', 'button:has-text("Sign in")'], timeout=8000)
        await _human_delay(3000, 5000)

        await _save_session(context, "linkedin")
        return True
    except Exception as e:
        logger.error(f"LinkedIn login failed: {e}")
        return False


async def _login_threads(page, context, creds: Dict) -> bool:
    """Threads login flow."""
    try:
        await page.goto("https://www.threads.com/login", wait_until="domcontentloaded")
        await _human_delay(2000, 3000)

        username = creds.get("username", "")
        password = creds.get("password", "")
        await _fill_first(
            page,
            ['input[placeholder*="Username"]', 'input[autocomplete="username"]', 'input[type="text"]'],
            username,
        )
        await _human_delay(300, 700)
        await _fill_first(page, ['input[type="password"]'], password)
        await _human_delay(500, 1000)
        try:
            await _click_first(
                page,
                ['div[role="button"]:has-text("Log in")', 'button:has-text("Log in")'],
                timeout=8000,
            )
        except Exception:
            await page.locator('input[type="password"]').first.press("Enter")
        await _human_delay(3000, 5000)

        await _save_session(context, "threads")
        return True
    except Exception as e:
        logger.error(f"Threads login failed: {e}")
        return False


async def _login_twitter(page, context, creds: Dict) -> bool:
    """Twitter/X login flow."""
    try:
        await page.goto("https://x.com/i/flow/login", wait_until="domcontentloaded")
        await _human_delay(2000, 4000)

        # Enter username
        await _fill_first(page, ['input[autocomplete="username"]', 'input[name="text"]'], creds["username"])
        await _human_delay(500, 1000)
        await _click_first(page, ['button:has-text("Next")', 'div[role="button"]:has-text("Next")'], timeout=8000)
        await _human_delay(2000, 3000)

        # Enter password
        await _fill_first(page, ['input[type="password"]'], creds["password"])
        await _human_delay(500, 1000)
        await _click_first(page, ['button[data-testid="LoginForm_Login_Button"]', 'button:has-text("Log in")'], timeout=8000)
        await _human_delay(3000, 5000)

        await _save_session(context, "twitter")
        return True
    except Exception as e:
        logger.error(f"Twitter login failed: {e}")
        return False


async def _login_facebook(page, context, creds: Dict) -> bool:
    """Facebook login flow."""
    try:
        await page.goto("https://www.facebook.com/login", wait_until="domcontentloaded")
        await _human_delay(2000, 3000)

        # Accept cookies
        try:
            await page.click('button[data-cookiebanner="accept_button"]', timeout=3000)
        except Exception:
            pass

        await _fill_first(page, ['#email', 'input[name="email"]'], creds["username"])
        await _human_delay(300, 700)
        await _fill_first(page, ['#pass', 'input[name="pass"]'], creds["password"])
        await _human_delay(500, 1000)
        try:
            await _click_first(page, ['button[name="login"]', 'div[aria-label="लॉग इन करें"]', 'div[aria-label="Log In"]'], timeout=8000)
        except Exception:
            await page.locator('#pass, input[name="pass"]').first.press("Enter")
        await _human_delay(3000, 5000)

        await _save_session(context, "facebook")
        return True
    except Exception as e:
        logger.error(f"Facebook login failed: {e}")
        return False


# ═══════════════════════════════════════════════════════════
#  UPLOAD FLOWS (per platform)
# ═══════════════════════════════════════════════════════════

async def _upload_instagram(page, video_path: str, caption: str, **kwargs) -> Dict:
    """Upload a Reel to Instagram."""
    try:
        await page.goto("https://www.instagram.com/", wait_until="domcontentloaded")
        await _human_delay(2000, 3000)

        # Click create (+) button
        await page.click('svg[aria-label="New post"]')
        await _human_delay(1000, 2000)

        # Upload file
        file_input = page.locator('input[type="file"]')
        await file_input.set_input_files(video_path)
        await _human_delay(3000, 5000)

        # Wait for processing
        try:
            await page.wait_for_selector('button:has-text("Next")', timeout=30000)
            await page.click('button:has-text("Next")')
            await _human_delay(1000, 2000)

            # Second "Next" for editing
            await page.click('button:has-text("Next")')
            await _human_delay(1000, 2000)
        except Exception:
            pass

        # Add caption
        if caption:
            caption_area = page.locator('textarea[aria-label="Write a caption..."], div[aria-label="Write a caption..."]')
            await caption_area.click()
            await _human_delay(300, 600)
            await caption_area.fill(caption)
            await _human_delay(500, 1000)

        # Share
        await page.click('button:has-text("Share")')
        await _human_delay(5000, 8000)

        return {"success": True, "platform": "instagram"}
    except Exception as e:
        return {"success": False, "error": str(e), "platform": "instagram"}


async def _upload_tiktok(page, video_path: str, caption: str, **kwargs) -> Dict:
    """Upload a video to TikTok."""
    try:
        await page.goto("https://www.tiktok.com/upload", wait_until="domcontentloaded")
        await _human_delay(2000, 4000)

        # Upload file
        file_input = page.locator('input[type="file"]')
        await file_input.set_input_files(video_path)
        await _human_delay(5000, 8000)

        # Add caption
        if caption:
            caption_area = page.locator('div[contenteditable="true"]').first
            await caption_area.click()
            await _human_delay(300, 600)
            # Clear existing text
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Delete")
            await caption_area.fill(caption)
            await _human_delay(500, 1000)

        # Post
        await page.click('button:has-text("Post")')
        await _human_delay(5000, 10000)

        return {"success": True, "platform": "tiktok"}
    except Exception as e:
        return {"success": False, "error": str(e), "platform": "tiktok"}


async def _upload_youtube(page, video_path: str, title: str, description: str, **kwargs) -> Dict:
    """Upload a video/Short to YouTube Studio."""
    try:
        await page.goto("https://studio.youtube.com/", wait_until="domcontentloaded")
        await _human_delay(2000, 4000)

        # Click upload/create button
        await page.click('#create-icon')
        await _human_delay(1000, 2000)
        await page.click('tp-yt-paper-item:has-text("Upload videos")')
        await _human_delay(1000, 2000)

        # Upload file
        file_input = page.locator('input[type="file"]')
        await file_input.set_input_files(video_path)
        await _human_delay(5000, 8000)

        # Set title
        if title:
            title_input = page.locator('#textbox').first
            await title_input.click()
            await page.keyboard.press("Control+A")
            await title_input.fill(title)
            await _human_delay(500, 1000)

        # Set description
        if description:
            desc_input = page.locator('#textbox').nth(1)
            await desc_input.click()
            await desc_input.fill(description)
            await _human_delay(500, 1000)

        # Click through to publish: Next -> Next -> Next -> Publish
        for _ in range(3):
            await page.click('button:has-text("Next")')
            await _human_delay(1000, 2000)

        # Set visibility to Public
        await page.click('tp-yt-paper-radio-button[name="PUBLIC"]')
        await _human_delay(500, 1000)

        await page.click('button:has-text("Publish")')
        await _human_delay(5000, 8000)

        return {"success": True, "platform": "youtube"}
    except Exception as e:
        return {"success": False, "error": str(e), "platform": "youtube"}


async def _upload_linkedin(page, video_path: str, caption: str, **kwargs) -> Dict:
    """Upload a video post to LinkedIn."""
    try:
        await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
        await _human_delay(2000, 3000)

        # Click "Start a post"
        await _click_first(
            page,
            [
                'button:has-text("Start a post")',
                'button[aria-label*="Start a post"]',
                '.share-box-feed-entry__trigger',
            ],
            timeout=15000,
        )
        await _human_delay(1000, 2000)

        # Click video/media button
        await _click_first(
            page,
            [
                'button[aria-label="Add media"]',
                'button[aria-label*="media"]',
                'button:has-text("Media")',
            ],
            timeout=15000,
        )
        await _human_delay(1000, 2000)

        # Upload file
        file_input = page.locator('input[type="file"]')
        await file_input.set_input_files(video_path)
        await _human_delay(5000, 10000)

        # Add caption
        if caption:
            editor = page.locator('div[role="textbox"]')
            await editor.click()
            await editor.fill(caption)
            await _human_delay(500, 1000)

        # Post
        await page.click('button:has-text("Post")')
        await _human_delay(3000, 5000)

        return {"success": True, "platform": "linkedin"}
    except Exception as e:
        return {"success": False, "error": str(e), "platform": "linkedin"}


async def _upload_twitter(page, video_path: str, caption: str, **kwargs) -> Dict:
    """Upload a video tweet to Twitter/X."""
    try:
        await page.goto("https://twitter.com/compose/tweet", wait_until="domcontentloaded")
        await _human_delay(2000, 3000)

        # Add text
        if caption:
            tweet_box = page.locator('div[data-testid="tweetTextarea_0"]')
            await tweet_box.click()
            await tweet_box.fill(caption)
            await _human_delay(500, 1000)

        # Upload media
        file_input = page.locator('input[data-testid="fileInput"]')
        await file_input.set_input_files(video_path)
        await _human_delay(5000, 8000)

        # Post
        await page.click('button[data-testid="tweetButton"]')
        await _human_delay(3000, 5000)

        return {"success": True, "platform": "twitter"}
    except Exception as e:
        return {"success": False, "error": str(e), "platform": "twitter"}


async def _upload_facebook(page, video_path: str, caption: str, **kwargs) -> Dict:
    """Upload a video to Facebook."""
    try:
        await page.goto("https://www.facebook.com/", wait_until="domcontentloaded")
        await _human_delay(2000, 3000)

        # Click "What's on your mind?" or Video
        await page.click('div[role="button"]:has-text("Video")')
        await _human_delay(1000, 2000)

        # Upload file
        file_input = page.locator('input[type="file"]')
        await file_input.set_input_files(video_path)
        await _human_delay(5000, 10000)

        # Add caption
        if caption:
            editor = page.locator('div[role="textbox"]').first
            await editor.click()
            await editor.fill(caption)
            await _human_delay(500, 1000)

        # Post
        await page.click('div[aria-label="Post"]')
        await _human_delay(5000, 8000)

        return {"success": True, "platform": "facebook"}
    except Exception as e:
        return {"success": False, "error": str(e), "platform": "facebook"}


# ═══════════════════════════════════════════════════════════
#  MAIN PUBLISHER CLASS
# ═══════════════════════════════════════════════════════════

_UPLOAD_HANDLERS = {
    "instagram": _upload_instagram,
    "tiktok": _upload_tiktok,
    "youtube": _upload_youtube,
    "linkedin": _upload_linkedin,
    "twitter": _upload_twitter,
    "facebook": _upload_facebook,
}


LOGIN_CHECKS = {
    "instagram": {
        "check_url": "https://www.instagram.com/",
        "logged_in_selector": 'svg[aria-label="Home"], a[href="/"]',
        "login_flow": _login_instagram,
    },
    "tiktok": {
        "check_url": "https://www.tiktok.com/upload",
        "logged_in_selector": '[data-e2e="upload-icon"], input[type="file"]',
        "login_flow": _login_tiktok,
    },
    "youtube": {
        "check_url": "https://studio.youtube.com/",
        "logged_in_selector": '#create-icon, button[aria-label*="Create"]',
        "login_flow": _login_youtube,
    },
    "linkedin": {
        "check_url": "https://www.linkedin.com/feed/",
        "logged_in_selector": '.feed-identity-module, .share-box-feed-entry__trigger, button[aria-label*="Start a post"]',
        "login_flow": _login_linkedin,
    },
    "twitter": {
        "check_url": "https://x.com/home",
        "logged_in_selector": '[data-testid="SideNav_AccountSwitcher_Button"], [data-testid="AppTabBar_Home_Link"]',
        "login_flow": _login_twitter,
    },
    "facebook": {
        "check_url": "https://www.facebook.com/",
        "logged_in_selector": '[aria-label="Your profile"], div[role="feed"]',
        "login_flow": _login_facebook,
    },
    "threads": {
        "check_url": "https://www.threads.com/",
        "logged_in_selector": 'a[href="/"], div[aria-label*="thread"]',
        "login_flow": _login_threads,
    },
}


class PlaywrightPublisher:
    """
    Production Playwright publisher with anti-bot detection.
    Handles login, session persistence, and file upload for all 6 platforms.
    """

    def __init__(self, platform: str, headless: bool = False):
        self.platform = platform.lower().strip()
        self.headless = headless

    async def publish(
        self,
        video_path: str,
        caption: str = "",
        title: str = "",
        description: str = "",
        credentials: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Full publish flow:
        1. Launch stealth browser
        2. Login if needed (with persistent sessions)
        3. Upload video with caption/title/description
        4. Save session for next time
        """
        from nexearch.tools.credential_vault import get_credentials

        if not credentials:
            try:
                credentials = get_credentials(self.platform)
            except ValueError as e:
                return {"success": False, "error": str(e), "method": "playwright"}

        # Resolve video path
        abs_video_path = os.path.abspath(video_path)
        if not os.path.exists(abs_video_path):
            return {
                "success": False,
                "error": f"Video file not found: {abs_video_path}",
                "method": "playwright",
            }

        pw = None
        browser = None
        try:
            pw, browser, context = await _create_stealth_browser(
                self.platform, headless=self.headless
            )
            page = await context.new_page()

            # Login
            logged_in = await _login_if_needed(
                page, context, self.platform, credentials
            )
            if not logged_in:
                page_text = ""
                try:
                    page_text = (await page.text_content("body")) or ""
                except Exception:
                    pass
                return {
                    "success": False,
                    "error": _describe_login_failure(self.platform, page.url, page_text),
                    "method": "playwright",
                }

            # Upload
            handler = _UPLOAD_HANDLERS.get(self.platform)
            if not handler:
                return {
                    "success": False,
                    "error": f"No upload handler for {self.platform}",
                    "method": "playwright",
                }

            result = await handler(
                page,
                abs_video_path,
                caption=caption,
                title=title,
                description=description,
            )
            result["method"] = "playwright"

            # Save session
            await _save_session(context, self.platform)

            return result

        except Exception as e:
            logger.error(f"Playwright publish failed for {self.platform}: {e}")
            return {
                "success": False,
                "error": str(e),
                "method": "playwright",
            }
        finally:
            if browser:
                await browser.close()
            if pw:
                await pw.stop()

    async def check_login_status(self) -> bool:
        """Check if we have a valid saved session."""
        session_path = _get_session_path(self.platform)
        return os.path.exists(session_path)
