from typing import Any


SUPPORTED_PRESENTATIONS = {"email", "products", "video", "progress", "brief"}


def parse_operator_reply(text: str) -> tuple[str, dict[str, Any] | None]:
    stripped = text.strip()
    if not stripped.startswith("/"):
        return stripped, None

    first_line, _, remainder = stripped.partition("\n")
    kind = first_line[1:].strip().lower()
    if kind not in SUPPORTED_PRESENTATIONS:
        return stripped, None

    fields: dict[str, str] = {}
    items: list[dict[str, str]] = []
    steps: list[str] = []
    body_lines: list[str] = []
    for raw_line in remainder.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        key, separator, value = line.partition(":")
        normalized_key = key.strip().lower()
        if separator and normalized_key == "item":
            parts = [part.strip() for part in value.split("|")]
            items.append(
                {
                    "name": parts[0] if parts else "Result",
                    "price": parts[1] if len(parts) > 1 else "",
                    "rating": parts[2] if len(parts) > 2 else "",
                    "note": parts[3] if len(parts) > 3 else "",
                }
            )
        elif separator and normalized_key == "step":
            steps.append(value.strip())
        elif separator and normalized_key in {
            "title",
            "subtitle",
            "subject",
            "from",
            "to",
            "status",
            "summary",
            "action",
        }:
            fields[normalized_key] = value.strip()
        else:
            body_lines.append(line)

    presentation: dict[str, Any] = {"type": kind, **fields}
    if items:
        presentation["items"] = items[:20]
    if steps:
        presentation["steps"] = steps[:10]
    if body_lines:
        presentation["body"] = "\n".join(body_lines)

    message = (
        fields.get("summary")
        or fields.get("subtitle")
        or fields.get("title")
        or fields.get("subject")
        or (body_lines[0] if body_lines else f"{kind.title()} workspace is ready.")
    )
    return message, presentation


def presentation_for_attachment(content_type: str) -> dict[str, str] | None:
    if content_type.startswith("video/"):
        return {"type": "video", "title": "Live visual is ready", "status": "Connected"}
    if content_type.startswith("image/"):
        return {"type": "brief", "title": "Visual result", "status": "Ready"}
    return None
