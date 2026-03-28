from __future__ import annotations

import logging

import httpx
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from playwright.sync_api import sync_playwright

from agent1.config import Settings

logger = logging.getLogger("agent1.tools")


class WebTools:
    def __init__(self, settings: Settings):
        self.settings = settings

    @staticmethod
    def _clip(value: str, limit: int) -> str:
        if len(value) <= limit:
            return value
        return value[:limit] + "\n... [truncated]"

    def search_web(self, user_id: str, query: str, max_results: int = 5) -> str:
        logger.info("tool=search_web user=%s query=%s", user_id, query)
        query = query.strip()
        if not query:
            return "Query is empty."
        limit = max(1, min(max_results, self.settings.max_search_results))
        try:
            with DDGS() as ddgs:
                rows = list(ddgs.text(query, max_results=limit))
        except Exception as exc:
            return f"Web search failed: {exc}"

        if not rows:
            return "No web search results found."

        lines = []
        for idx, row in enumerate(rows, start=1):
            title = row.get("title", "Untitled")
            href = row.get("href", "")
            body = row.get("body", "")
            lines.append(f"{idx}. {title}\nURL: {href}\nSnippet: {body}")
        return "\n\n".join(lines)

    def browse_url(self, user_id: str, url: str) -> str:
        logger.info("tool=browse_url user=%s url=%s", user_id, url)
        url = url.strip()
        if not url:
            return "URL is empty."

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=15_000)
                page.wait_for_timeout(800)
                title = page.title() or "Untitled"
                body_text = page.locator("body").inner_text(timeout=10_000)
                browser.close()
                clipped = self._clip(body_text.strip(), self.settings.browser_max_chars)
                return f"Title: {title}\nURL: {url}\nContent:\n{clipped}"
        except Exception as playwright_exc:
            logger.warning("Playwright browse failed, using HTTP fallback: %s", playwright_exc)

        try:
            response = httpx.get(
                url,
                timeout=12.0,
                headers={"User-Agent": self.settings.web_user_agent},
                follow_redirects=True,
            )
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            title = soup.title.text.strip() if soup.title and soup.title.text else "Untitled"
            text = soup.get_text(separator=" ", strip=True)
            clipped = self._clip(text, self.settings.browser_max_chars)
            return f"Title: {title}\nURL: {url}\nContent:\n{clipped}"
        except Exception as http_exc:
            return f"Browse failed: {http_exc}"

