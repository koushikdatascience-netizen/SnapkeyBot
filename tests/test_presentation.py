from app.services.presentation import parse_operator_reply, presentation_for_attachment


def test_plain_operator_reply_stays_plain():
    message, presentation = parse_operator_reply("Hello from the concierge")
    assert message == "Hello from the concierge"
    assert presentation is None


def test_email_command_builds_email_workspace():
    message, presentation = parse_operator_reply(
        "/email\nsubject: Quarterly update\nfrom: founder@example.com\nsummary: The update is ready.\nFull email body."
    )
    assert message == "The update is ready."
    assert presentation == {
        "type": "email",
        "subject": "Quarterly update",
        "from": "founder@example.com",
        "summary": "The update is ready.",
        "body": "Full email body.",
    }


def test_product_command_builds_ranked_items():
    message, presentation = parse_operator_reply(
        "/products\ntitle: Top chairs\nitem: Chair One | Rs 4,999 | 4.7 | Best value\nitem: Chair Two | Rs 6,999 | 4.8"
    )
    assert message == "Top chairs"
    assert presentation["type"] == "products"
    assert presentation["items"][0]["price"] == "Rs 4,999"
    assert presentation["items"][1]["rating"] == "4.8"


def test_video_attachment_selects_video_workspace():
    assert presentation_for_attachment("video/mp4")["type"] == "video"
    assert presentation_for_attachment("application/pdf") is None
