from __future__ import annotations

import json
import os
from pathlib import Path

from ayassek.tools.base import BaseTool, ToolResult, ToolSpec
from ayassek.utils.logging import get_logger

logger = get_logger(__name__)

STATE_DIR = Path("data/browser_state")
STATE_FILE = STATE_DIR / "storage_state.json"


class BrowserTool(BaseTool):
    name: str = "browser"
    description: str = "Read web page content using a headless browser. Supports read/click/type/screenshot actions. Browser state (cookies) persists across calls within a session."

    def __init__(self):
        self._browser = None
        self._context = None
        self._playwright = None
        STATE_DIR.mkdir(parents=True, exist_ok=True)

    def get_spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters={
                "url": {
                    "type": "string",
                    "description": "URL to navigate to",
                },
                "action": {
                    "type": "string",
                    "description": "Action to perform: 'read' (get text), 'click' (click selector), 'type' (type into selector), 'screenshot', 'clear_state' (clear cookies/session)",
                    "enum": ["read", "click", "type", "screenshot", "clear_state"],
                    "default": "read",
                },
                "selector": {
                    "type": "string",
                    "description": "CSS selector for click/type actions",
                    "default": "",
                },
                "value": {
                    "type": "string",
                    "description": "Text to type (for 'type' action)",
                    "default": "",
                },
            },
            required=["url"],
        )

    async def _get_browser(self):
        if self._browser is None:
            try:
                from playwright.async_api import async_playwright
                p = await async_playwright().start()
                self._playwright = p
                self._browser = await p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox"],
                )
            except Exception as e:
                logger.error("Failed to launch browser: %s", e)
                raise
        return self._browser

    async def _get_context(self):
        if self._context is None:
            browser = await self._get_browser()
            storage_state = None
            if STATE_FILE.exists():
                try:
                    storage_state = json.loads(STATE_FILE.read_text())
                except Exception as e:
                    logger.warning("Failed to load browser state: %s", e)
            self._context = await browser.new_context(
                storage_state=storage_state or {},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            )
        return self._context

    async def _save_state(self):
        if self._context is None:
            return
        try:
            state = await self._context.storage_state()
            STATE_FILE.write_text(json.dumps(state, indent=2))
        except Exception as e:
            logger.warning("Failed to save browser state: %s", e)

    def _clear_state(self):
        self._context = None
        if STATE_FILE.exists():
            STATE_FILE.unlink()
        return ToolResult(success=True, output="Browser state cleared (cookies/session reset).")

    async def execute(self, url: str, action: str = "read", selector: str = "", value: str = "") -> ToolResult:
        if action == "clear_state":
            return self._clear_state()

        try:
            context = await self._get_context()
            page = await context.new_page()

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)

                if action == "read":
                    content = await page.inner_text("body") if not selector else await page.inner_text(selector)
                    title = await page.title()
                    await self._save_state()
                    await page.close()
                    return ToolResult(
                        success=True,
                        output=f"# {title}\n\n{content[:10000]}",
                        data={"title": title, "url": url, "truncated": len(content) > 10000},
                    )

                elif action == "click":
                    if not selector:
                        await page.close()
                        return ToolResult(success=False, output="Selector required for 'click' action.")
                    await page.click(selector)
                    await page.wait_for_timeout(1000)
                    content = await page.inner_text("body")
                    title = await page.title()
                    await self._save_state()
                    await page.close()
                    return ToolResult(
                        success=True,
                        output=f"# {title}\n\n{content[:5000]}",
                        data={"title": title, "url": url},
                    )

                elif action == "type":
                    if not selector or not value:
                        await page.close()
                        return ToolResult(success=False, output="Selector and value required for 'type' action.")
                    await page.fill(selector, value)
                    await self._save_state()
                    await page.close()
                    return ToolResult(success=True, output=f"Typed '{value}' into '{selector}'.")

                elif action == "screenshot":
                    screenshot = await page.screenshot(full_page=True)
                    import base64
                    b64 = base64.b64encode(screenshot).decode("utf-8")
                    await self._save_state()
                    await page.close()
                    return ToolResult(
                        success=True,
                        output=f"Screenshot captured ({len(screenshot)} bytes).",
                        data={"screenshot_b64": b64, "format": "png", "url": url},
                    )

                else:
                    await page.close()
                    return ToolResult(success=False, output=f"Unknown action: {action}")

            except Exception as e:
                await page.close()
                return ToolResult(success=False, output=f"Browser action failed: {e}")

        except Exception as e:
            logger.error("Browser tool failed: %s", e)
            return ToolResult(success=False, output=f"Browser failed: {e}")
