from datetime import datetime, timezone
from typing import Any

import httpx
from pydantic import BaseModel, Field

from app.tools.base import ToolContext, ToolDefinition


async def _google_get(context: ToolContext, url: str, params: dict[str, Any]) -> dict[str, Any]:
    token = context.credentials.get("access_token")
    if not token:
        raise ValueError("Connect this tool with a Google OAuth access_token")
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url, params=params, headers={"Authorization": f"Bearer {token}"})
        response.raise_for_status()
        return response.json()


async def _gmail_message(context: ToolContext, message_id: str) -> dict[str, Any]:
    data = await _google_get(
        context,
        f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}",
        {"format": "metadata", "metadataHeaders": ["Subject", "From", "Date"]},
    )
    headers = {item["name"].lower(): item["value"] for item in data.get("payload", {}).get("headers", [])}
    return {
        "id": data.get("id"),
        "thread_id": data.get("threadId"),
        "subject": headers.get("subject", "(no subject)"),
        "from": headers.get("from", ""),
        "date": headers.get("date", ""),
        "snippet": data.get("snippet", ""),
    }


class GmailSearchInput(BaseModel):
    query: str = Field(default="in:inbox", max_length=500)
    max_results: int = Field(default=10, ge=1, le=25)


class GmailSearchTool(ToolDefinition):
    name = "gmail_search"
    description = "Search the connected Gmail inbox and return message IDs and thread IDs."
    input_model = GmailSearchInput
    required_permission = "gmail:read"
    credential_fields = ["access_token"]

    async def execute(self, context: ToolContext, arguments: dict[str, Any]) -> dict[str, Any]:
        values = self.input_model.model_validate(arguments)
        data = await _google_get(
            context,
            "https://gmail.googleapis.com/gmail/v1/users/me/messages",
            {"q": values.query, "maxResults": values.max_results},
        )
        messages = [
            await _gmail_message(context, item["id"])
            for item in data.get("messages", [])
        ]
        return {"messages": messages, "result_size_estimate": data.get("resultSizeEstimate", 0)}


class CalendarEventsInput(BaseModel):
    max_results: int = Field(default=10, ge=1, le=50)
    time_min: datetime | None = None


class CalendarEventsTool(ToolDefinition):
    name = "calendar_events"
    description = "List upcoming events from the connected primary Google Calendar."
    input_model = CalendarEventsInput
    required_permission = "calendar:read"
    credential_fields = ["access_token"]

    async def execute(self, context: ToolContext, arguments: dict[str, Any]) -> dict[str, Any]:
        values = self.input_model.model_validate(arguments)
        time_min = values.time_min or datetime.now(timezone.utc)
        data = await _google_get(
            context,
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            {
                "maxResults": values.max_results,
                "timeMin": time_min.isoformat(),
                "singleEvents": "true",
                "orderBy": "startTime",
            },
        )
        events = [
            {
                "id": event.get("id"),
                "summary": event.get("summary", "(untitled)"),
                "start": event.get("start", {}),
                "end": event.get("end", {}),
                "htmlLink": event.get("htmlLink"),
            }
            for event in data.get("items", [])
        ]
        return {"events": events}
