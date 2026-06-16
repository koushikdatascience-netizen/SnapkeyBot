import re
from typing import Any

from app.config import get_settings
from app.services.retail_reports import report_tenant_for, run_retail_report


REPORT_WORDS = (
    "report", "sales", "sale", "stock", "inventory", "product", "category",
    "purchase", "supplier", "account", "expense", "transaction", "bill",
    "average", "top", "best", "low", "chart", "graph", "trend",
)


def local_agent_ready() -> bool:
    return get_settings().local_agent_enabled


def local_agent_status() -> dict[str, Any]:
    settings = get_settings()
    return {
        "enabled": settings.local_agent_enabled,
        "llm_configured": bool(settings.local_agent_llm_base_url and settings.local_agent_llm_model),
        "llm_base_url": settings.local_agent_llm_base_url,
        "features": [
            "approved_postgres_reports",
            "interactive_chart_specs",
            "browser_workspace_routing",
            "camera_workspace_routing",
            "purchase_import_preview",
            "desktop_app_control_handoff",
        ],
    }


def report_intent(text: str) -> dict[str, Any] | None:
    value = text.lower()
    if not any(word in value for word in REPORT_WORDS):
        return None

    report_name = "sales_summary"
    if re.search(r"\b(low stock|reorder|inventory)\b", value):
        report_name = "low_stock"
    elif re.search(r"\b(top|best|selling).*(product|item)|\bproduct.*(top|best|selling)\b", value):
        report_name = "top_products"
    elif re.search(r"\b(category|brand)\b", value):
        report_name = "category_sales"
    elif re.search(r"\b(supplier|vendor)\b", value):
        report_name = "supplier_performance"
    elif re.search(r"\b(purchase|buying|procurement)\b", value):
        report_name = "purchase_trend"
    elif re.search(r"\b(account|expense|voucher|transaction|cash|fl|cs)\b", value):
        report_name = "account_summary"
    elif re.search(r"\b(average bill|avg bill|bill value)\b", value):
        report_name = "average_bill"

    explicit_days = re.search(r"\b(?:last|past|previous)\s+(\d{1,3})\s+days?\b", value)
    days = 7
    if explicit_days:
        days = int(explicit_days.group(1))
    elif "today" in value:
        days = 1
    elif "yesterday" in value:
        days = 2
    elif "month" in value:
        days = 30
    elif "quarter" in value:
        days = 90

    limit_match = re.search(r"\b(?:top|show|first)\s+(\d{1,2})\b", value)
    chart = "donut" if re.search(r"\b(donut|pie)\b", value) else (
        "line" if re.search(r"\b(line|trend)\b", value) else (
            "table" if re.search(r"\b(table|list)\b", value) else "bar"
        )
    )
    return {
        "report_name": report_name,
        "days": days,
        "limit": int(limit_match.group(1)) if limit_match else 20,
        "chart": chart,
    }


def _browser_workspace(text: str) -> dict[str, Any] | None:
    value = text.lower()
    if not re.search(r"\b(open|browse|visit|google|search|website|chrome|browser)\b", value):
        return None
    explicit_url = re.search(r"https?://\S+", text)
    domain = re.search(r"\b(?:www\.)?[a-z0-9-]+\.(?:com|in|org|net|io|ai)\b", text, re.I)
    url = explicit_url.group(0) if explicit_url else (f"https://{domain.group(0)}" if domain else "https://www.google.com")
    return {
        "type": "browser",
        "title": "Browser control workspace",
        "summary": "Ready for local Playwright or Browserbase control.",
        "url": url,
        "details": [
            "Use Playwright locally for free browser control.",
            "Ask for confirmation before login, purchase, send, or destructive actions.",
        ],
    }


def _camera_workspace(text: str) -> dict[str, Any] | None:
    value = text.lower()
    if not re.search(r"\b(camera|cam|cctv|worker|staff|monitor|screen|opencv)\b", value):
        return None
    camera_match = re.search(r"\b(?:cam|camera)\s*([123])\b", value)
    camera = int(camera_match.group(1)) if camera_match else 0
    return {
        "type": "monitoring",
        "title": f"Camera {camera} live view" if camera else "Camera monitoring workspace",
        "summary": "OpenCV workspace ready for live or demo feeds.",
        "selected_camera": camera,
        "focus": "workers" if re.search(r"\b(worker|staff|idle|sleeping)\b", value) else "cameras",
    }


async def handle_local_agent_command(prompt: str, email: str) -> dict[str, Any]:
    if not local_agent_ready():
        raise RuntimeError("Local agent runtime is disabled")

    intent = report_intent(prompt)
    if intent:
        result = await run_retail_report(
            intent["report_name"],
            tenant_id=report_tenant_for(email),
            days=int(intent["days"]),
            limit=int(intent["limit"]),
            chart=str(intent["chart"]),
        )
        workspace = {
            "type": "report",
            "title": result["title"],
            "summary": (
                f"{result['period']['start']} to {result['period']['end']}. "
                f"Chart: {result['chart']}."
            ),
            "chart": result["chart"],
            "rows": result["rows"],
            "total": result["total"],
            "insights": result.get("insights", []),
            "source": result.get("source", "postgres"),
        }
        return {
            "reply": f"{result['title']} is ready. {result.get('voice_summary', '')}".strip(),
            "intent": {"type": "report", **intent},
            "workspace": workspace,
            "tool": "approved_report",
            "safe": True,
        }

    camera = _camera_workspace(prompt)
    if camera:
        return {
            "reply": "Camera workspace is ready. I can explain the visible feed when a camera or demo video is connected.",
            "intent": {"type": "camera"},
            "workspace": camera,
            "tool": "opencv_workspace",
            "safe": True,
        }

    browser = _browser_workspace(prompt)
    if browser:
        return {
            "reply": "Browser workspace is ready. I will ask before any risky click, login, send, or purchase action.",
            "intent": {"type": "browser", "url": browser["url"]},
            "workspace": browser,
            "tool": "playwright_workspace",
            "safe": True,
        }

    if re.search(r"\b(purchase import|invoice|pdf|csv|upload)\b", prompt.lower()):
        return {
            "reply": "Purchase import preview is ready. Upload a PDF or CSV to extract and validate before ERP entry.",
            "intent": {"type": "purchase_import"},
            "workspace": {
                "type": "progress",
                "title": "Purchase import assistant",
                "summary": "Preview and validation only. Madhushala data is not changed.",
                "steps": ["Upload invoice", "Extract rows", "Match products", "Review totals"],
            },
            "tool": "purchase_import_preview",
            "safe": True,
        }

    return {
        "reply": (
            "The local agent is ready. Ask for sales, stock, supplier, purchase, account, browser, "
            "camera, or invoice-import workspaces."
        ),
        "intent": {"type": "help"},
        "workspace": {
            "type": "brief",
            "title": "Free local agent ready",
            "summary": "Reports, charts, browser control, camera workspace, and purchase import can run without ElevenLabs.",
            "details": [
                "Voice: Pipecat plus faster-whisper and Piper/Kokoro",
                "LLM: Ollama or vLLM",
                "Tools: approved reports, Playwright, OpenCV, purchase import",
            ],
        },
        "tool": "help",
        "safe": True,
    }
