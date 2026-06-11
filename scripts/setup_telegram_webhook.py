import os
import re
import sys

import httpx


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
    public_url = os.environ.get("PUBLIC_URL", "").rstrip("/")
    if not token or not secret or not public_url:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET, and PUBLIC_URL")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", secret):
        raise SystemExit("TELEGRAM_WEBHOOK_SECRET may contain only letters, numbers, underscores, and hyphens")
    if not public_url.startswith("https://"):
        raise SystemExit("PUBLIC_URL must be an HTTPS URL")
    response = httpx.post(
        f"https://api.telegram.org/bot{token}/setWebhook",
        json={
            "url": f"{public_url}/api/operator/telegram",
            "secret_token": secret,
            "allowed_updates": ["message", "edited_message"],
            "drop_pending_updates": True,
        },
        timeout=30,
    )
    response.raise_for_status()
    result = response.json()
    if not result.get("ok"):
        raise SystemExit(result.get("description", "Unable to configure Telegram webhook"))
    print(result.get("description", "Webhook configured"))
    info_response = httpx.get(f"https://api.telegram.org/bot{token}/getWebhookInfo", timeout=30)
    info_response.raise_for_status()
    info = info_response.json().get("result", {})
    print(f"Webhook URL: {info.get('url') or '(not set)'}")
    print(f"Pending updates: {info.get('pending_update_count', 0)}")
    if info.get("last_error_message"):
        print(f"Last Telegram error: {info['last_error_message']}")


if __name__ == "__main__":
    try:
        main()
    except httpx.HTTPError as exc:
        print(f"Telegram request failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
