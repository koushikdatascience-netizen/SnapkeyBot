from fastapi.testclient import TestClient

from connector import sqlserver_connector


def connector_client(monkeypatch):
    monkeypatch.setenv("CONNECTOR_SECRET", "test-secret")
    monkeypatch.setenv("MSSQL_CONNECTION_STRING", "configured")
    monkeypatch.setenv("CONNECTOR_MAX_DAYS", "90")
    monkeypatch.setenv("CONNECTOR_MAX_POINTS", "50")
    return TestClient(sqlserver_connector.app)


def test_connector_rejects_missing_secret(monkeypatch):
    client = connector_client(monkeypatch)

    response = client.post("/reports/run", json={"tenant_id": "shop-1", "report_name": "sales_summary"})

    assert response.status_code == 401


def test_connector_runs_only_allowlisted_bounded_report(monkeypatch):
    client = connector_client(monkeypatch)

    def fake_query(sql, parameters):
        assert "snapkey_sales" in sql
        assert parameters[0] == 50
        assert parameters[1] == "shop-1"
        return [{"label": "2026-06-12", "value": 1250}]

    monkeypatch.setattr(sqlserver_connector, "query_rows", fake_query)
    response = client.post(
        "/reports/run",
        headers={"X-Snapkey-Connector-Secret": "test-secret"},
        json={"tenant_id": "shop-1", "report_name": "sales_summary", "days": 500, "limit": 500},
    )

    assert response.status_code == 200
    assert response.json()["limits"] == {"days": 90, "points": 50}
    assert response.json()["source"] == "sqlserver_connector"


def test_connector_rejects_arbitrary_sql_report(monkeypatch):
    client = connector_client(monkeypatch)

    response = client.post(
        "/reports/run",
        headers={"X-Snapkey-Connector-Secret": "test-secret"},
        json={"tenant_id": "shop-1", "report_name": "DROP TABLE sales"},
    )

    assert response.status_code == 422
