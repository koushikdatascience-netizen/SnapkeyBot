from scripts import sync_sqlserver_to_postgres
import pytest


def test_postgres_url_accepts_railway_and_sqlalchemy_formats(monkeypatch):
    monkeypatch.setenv("REPORT_SYNC_DATABASE_URL", "postgresql+asyncpg://user:pass@host/db")
    assert sync_sqlserver_to_postgres.postgres_url() == "postgresql://user:pass@host/db"

    monkeypatch.setenv("REPORT_SYNC_DATABASE_URL", "postgres://user:pass@host/db")
    assert sync_sqlserver_to_postgres.postgres_url() == "postgresql://user:pass@host/db"


def test_source_queries_are_tenant_scoped():
    assert all("tenant_id = ?" in sql for sql, _columns in sync_sqlserver_to_postgres.TABLES.values())


def test_private_railway_url_is_rejected():
    with pytest.raises(SystemExit, match="DATABASE_PUBLIC_URL"):
        sync_sqlserver_to_postgres.validate_postgres_url(
            "postgresql://user:pass@snapkey-db.railway.internal:5432/railway"
        )


def test_sync_does_not_export_sensitive_customer_fields():
    customer_sql, customer_columns = sync_sqlserver_to_postgres.TABLES["snapkey_customers"]

    assert customer_columns == ("tenant_id", "customer_name", "visit_count")
    assert "contact" not in customer_sql.lower()
    assert "email" not in customer_sql.lower()
    assert "card" not in customer_sql.lower()
