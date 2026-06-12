import pytest

from app.services import retail_reports


class FakeResult:
    def mappings(self):
        return self

    def all(self):
        return [{"label": "A", "value": 10}, {"label": "B", "value": 20}]


class FakeConnection:
    async def execute(self, _statement, parameters):
        assert parameters["limit"] == 50
        assert parameters["tenant_id"] == "shop-1"
        return FakeResult()


class FakeConnectionContext:
    async def __aenter__(self):
        return FakeConnection()

    async def __aexit__(self, *_args):
        return None


class FakeEngine:
    def connect(self):
        return FakeConnectionContext()


@pytest.mark.asyncio
async def test_report_limits_large_requests(monkeypatch):
    settings = retail_reports.get_settings()
    monkeypatch.setattr(settings, "report_database_url", "mysql+asyncmy://configured")
    monkeypatch.setattr(settings, "report_tenant_id", "shop-1")
    monkeypatch.setattr(settings, "report_max_days", 90)
    monkeypatch.setattr(settings, "report_max_points", 50)
    monkeypatch.setattr(retail_reports, "_report_engine", lambda: FakeEngine())

    result = await retail_reports.run_retail_report(
        "sales_summary", tenant_id="shop-1", days=5000, limit=5000
    )

    assert result["limits"] == {"days": 90, "points": 50}
    assert result["total"] == 30.0


def test_report_tenant_map_prevents_agent_selected_tenant(monkeypatch):
    settings = retail_reports.get_settings()
    monkeypatch.setattr(settings, "report_tenant_id", "")
    monkeypatch.setattr(settings, "report_tenant_map_json", '{"owner@example.com":"shop-7"}')

    assert retail_reports.report_tenant_for("OWNER@example.com") == "shop-7"
