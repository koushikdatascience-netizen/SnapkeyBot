import pytest

from app.services import local_agent


@pytest.mark.asyncio
async def test_local_agent_routes_supplier_report(monkeypatch):
    captured = {}

    async def fake_report(report_name, *, tenant_id, days, limit, chart):
        captured.update(
            {
                "report_name": report_name,
                "tenant_id": tenant_id,
                "days": days,
                "limit": limit,
                "chart": chart,
            }
        )
        return {
            "title": "Supplier performance",
            "period": {"start": "2026-06-01", "end": "2026-06-16"},
            "chart": chart,
            "rows": [{"label": "Supplier A", "value": 1000}],
            "total": 1000,
            "insights": ["Supplier A is the leading result."],
            "source": "railway_postgres",
            "voice_summary": "Supplier A is leading.",
        }

    monkeypatch.setattr(local_agent, "report_tenant_for", lambda _email: "shop-2")
    monkeypatch.setattr(local_agent, "run_retail_report", fake_report)

    result = await local_agent.handle_local_agent_command(
        "show supplier report last 30 days as line chart", "owner@example.com"
    )

    assert captured == {
        "report_name": "supplier_performance",
        "tenant_id": "shop-2",
        "days": 30,
        "limit": 20,
        "chart": "line",
    }
    assert result["intent"]["type"] == "report"
    assert result["workspace"]["type"] == "report"
    assert "Supplier performance is ready" in result["reply"]


@pytest.mark.asyncio
async def test_local_agent_routes_browser_workspace():
    result = await local_agent.handle_local_agent_command(
        "open google and search snapkey", "owner@example.com"
    )

    assert result["intent"]["type"] == "browser"
    assert result["workspace"]["type"] == "browser"
    assert result["workspace"]["url"] == "https://www.google.com"


@pytest.mark.asyncio
async def test_local_agent_routes_camera_workspace():
    result = await local_agent.handle_local_agent_command(
        "show camera 2 worker monitoring", "owner@example.com"
    )

    assert result["intent"]["type"] == "camera"
    assert result["workspace"]["type"] == "monitoring"
    assert result["workspace"]["selected_camera"] == 2
    assert result["workspace"]["focus"] == "workers"
