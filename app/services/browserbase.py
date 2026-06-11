from typing import Any

import httpx

from app.config import get_settings


def browserbase_ready() -> bool:
    settings = get_settings()
    return bool(settings.browserbase_api_key and settings.browserbase_project_id)


async def create_browserbase_session(user_id: str) -> dict[str, Any]:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://api.browserbase.com/v1/sessions",
            headers={"X-BB-API-Key": settings.browserbase_api_key},
            json={
                "projectId": settings.browserbase_project_id,
                "keepAlive": True,
                "region": settings.browserbase_region,
                "userMetadata": {"snapkeyUserId": user_id},
            },
        )
        response.raise_for_status()
        session = response.json()
        debug = await client.get(
            f"https://api.browserbase.com/v1/sessions/{session['id']}/debug",
            headers={"X-BB-API-Key": settings.browserbase_api_key},
        )
        debug.raise_for_status()
    return {**session, **debug.json()}


async def run_browser_action(connect_url: str, action: str, **values: Any) -> dict[str, Any]:
    from playwright.async_api import async_playwright

    async with async_playwright() as playwright:
        browser = await playwright.chromium.connect_over_cdp(connect_url)
        context = browser.contexts[0]
        page = context.pages[0] if context.pages else await context.new_page()
        if action == "navigate":
            await page.goto(values["url"], wait_until="domcontentloaded")
        elif action == "click":
            await page.locator(values["selector"]).click()
        elif action == "type":
            await page.locator(values["selector"]).fill(values["text"])
        elif action == "press":
            await page.locator(values["selector"]).press(values["text"])
        elif action == "scroll":
            await page.mouse.wheel(0, int(values.get("text") or 600))
        else:
            raise ValueError("Unsupported browser action")
        result = {"url": page.url, "title": await page.title()}
        await browser.close()
        return result
