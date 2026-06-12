import asyncio
import hmac
import os
from datetime import date, timedelta
from decimal import Decimal
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

try:
    import pyodbc
except ImportError:  # pragma: no cover - reported by diagnostics on machines without the driver package
    pyodbc = None

app = FastAPI(title="Snapkey SQL Server Connector", version="1.0.0")

REPORTS = {
    "sales_summary": {
        "title": "Sales summary",
        "chart": "bar",
        "sql": """
            SELECT TOP (?) CONVERT(date, sold_at) AS label, ROUND(SUM(net_amount), 2) AS value
            FROM dbo.snapkey_sales
            WHERE tenant_id = ? AND sold_at >= ? AND sold_at < ?
            GROUP BY CONVERT(date, sold_at)
            ORDER BY CONVERT(date, sold_at)
        """,
        "params": "dated",
    },
    "top_products": {
        "title": "Top-selling products",
        "chart": "bar",
        "sql": """
            SELECT TOP (?) product_name AS label, ROUND(SUM(quantity), 2) AS value
            FROM dbo.snapkey_sales
            WHERE tenant_id = ? AND sold_at >= ? AND sold_at < ?
            GROUP BY product_name
            ORDER BY value DESC
        """,
        "params": "dated",
    },
    "category_sales": {
        "title": "Sales by category",
        "chart": "bar",
        "sql": """
            SELECT TOP (?) category_name AS label, ROUND(SUM(net_amount), 2) AS value
            FROM dbo.snapkey_sales
            WHERE tenant_id = ? AND sold_at >= ? AND sold_at < ?
            GROUP BY category_name
            ORDER BY value DESC
        """,
        "params": "dated",
    },
    "low_stock": {
        "title": "Low-stock products",
        "chart": "bar",
        "sql": """
            SELECT TOP (?) product_name AS label, ROUND(stock_quantity, 2) AS value
            FROM dbo.snapkey_inventory
            WHERE tenant_id = ? AND stock_quantity <= reorder_level
            ORDER BY stock_quantity ASC
        """,
        "params": "tenant",
    },
    "payment_mix": {
        "title": "Sales by payment method",
        "chart": "donut",
        "sql": """
            SELECT TOP (?) payment_method AS label, ROUND(SUM(amount), 2) AS value
            FROM dbo.snapkey_payments
            WHERE tenant_id = ? AND sold_at >= ? AND sold_at < ?
            GROUP BY payment_method
            ORDER BY value DESC
        """,
        "params": "dated",
    },
    "hourly_sales": {
        "title": "Sales by hour",
        "chart": "bar",
        "sql": """
            SELECT TOP (?) CONCAT(RIGHT('0' + CAST(DATEPART(hour, sold_at) AS varchar(2)), 2), ':00') AS label,
                   ROUND(SUM(net_amount), 2) AS value
            FROM dbo.snapkey_bills
            WHERE tenant_id = ? AND sold_at >= ? AND sold_at < ?
            GROUP BY DATEPART(hour, sold_at)
            ORDER BY DATEPART(hour, sold_at)
        """,
        "params": "dated",
    },
    "average_bill": {
        "title": "Average bill value",
        "chart": "line",
        "sql": """
            SELECT TOP (?) CONVERT(date, sold_at) AS label, ROUND(AVG(net_amount), 2) AS value
            FROM dbo.snapkey_bills
            WHERE tenant_id = ? AND sold_at >= ? AND sold_at < ?
            GROUP BY CONVERT(date, sold_at)
            ORDER BY CONVERT(date, sold_at)
        """,
        "params": "dated",
    },
    "purchase_trend": {
        "title": "Purchase trend",
        "chart": "line",
        "sql": """
            SELECT TOP (?) CONVERT(date, purchased_at) AS label, ROUND(SUM(net_amount), 2) AS value
            FROM dbo.snapkey_purchases
            WHERE tenant_id = ? AND purchased_at >= ? AND purchased_at < ?
            GROUP BY CONVERT(date, purchased_at)
            ORDER BY CONVERT(date, purchased_at)
        """,
        "params": "dated",
    },
    "stock_by_category": {
        "title": "Stock by category",
        "chart": "bar",
        "sql": """
            SELECT TOP (?) category_name AS label, ROUND(SUM(stock_quantity), 2) AS value
            FROM dbo.snapkey_inventory
            WHERE tenant_id = ?
            GROUP BY category_name
            ORDER BY value DESC
        """,
        "params": "tenant",
    },
    "customer_visits": {
        "title": "Top customers by visits",
        "chart": "bar",
        "sql": """
            SELECT TOP (?) customer_name AS label, ROUND(visit_count, 2) AS value
            FROM dbo.snapkey_customers
            WHERE tenant_id = ?
            ORDER BY visit_count DESC
        """,
        "params": "tenant",
    },
}


class ConnectorRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=100)


class ReportRequest(ConnectorRequest):
    report_name: str
    days: int = Field(default=7, ge=1)
    limit: int = Field(default=20, ge=1)


def settings() -> dict[str, Any]:
    return {
        "connection_string": os.environ.get("MSSQL_CONNECTION_STRING", ""),
        "secret": os.environ.get("CONNECTOR_SECRET", ""),
        "max_days": int(os.environ.get("CONNECTOR_MAX_DAYS", "90")),
        "max_points": int(os.environ.get("CONNECTOR_MAX_POINTS", "50")),
        "timeout": int(os.environ.get("CONNECTOR_QUERY_TIMEOUT_SECONDS", "8")),
    }


def authorize(secret: Annotated[str | None, Header(alias="X-Snapkey-Connector-Secret")] = None) -> None:
    expected = settings()["secret"]
    if not expected or not secret or not hmac.compare_digest(secret, expected):
        raise HTTPException(status_code=401, detail="Invalid connector secret")


def connection():
    config = settings()
    if pyodbc is None:
        raise RuntimeError("Install pyodbc and Microsoft ODBC Driver 18 for SQL Server")
    if not config["connection_string"]:
        raise RuntimeError("MSSQL_CONNECTION_STRING is not configured")
    return pyodbc.connect(config["connection_string"], timeout=config["timeout"])


def json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date,)):
        return value.isoformat()
    return value


def query_rows(sql: str, parameters: tuple[Any, ...]) -> list[dict[str, Any]]:
    config = settings()
    database = connection()
    try:
        cursor = database.cursor()
        cursor.execute(sql, parameters)
        columns = [column[0] for column in cursor.description]
        return [
            {column: json_value(value) for column, value in zip(columns, row, strict=True)}
            for row in cursor.fetchall()
        ]
    finally:
        database.close()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/diagnostics")
async def diagnostics(payload: ConnectorRequest, _: Annotated[None, Depends(authorize)]) -> dict[str, Any]:
    def check() -> dict[str, Any]:
        config = settings()
        database = connection()
        try:
            cursor = database.cursor()
            cursor.execute("SELECT 1")
            cursor.execute(
                """
                SELECT name
                FROM sys.views
                WHERE schema_id = SCHEMA_ID('dbo')
                  AND name IN (
                      'snapkey_sales', 'snapkey_inventory', 'snapkey_bills',
                      'snapkey_payments', 'snapkey_purchases', 'snapkey_customers'
                  )
                """
            )
            views = sorted(str(row[0]) for row in cursor.fetchall())
        finally:
            database.close()
        return {
            "connected": True,
            "tenant_assigned": bool(payload.tenant_id),
            "views": views,
            "missing_views": sorted(
                {
                    "snapkey_sales", "snapkey_inventory", "snapkey_bills",
                    "snapkey_payments", "snapkey_purchases", "snapkey_customers",
                }
                - set(views)
            ),
            "limits": {
                "max_days": config["max_days"],
                "max_points": config["max_points"],
                "timeout_seconds": config["timeout"],
            },
            "source": "sqlserver_connector",
        }

    try:
        return await asyncio.wait_for(asyncio.to_thread(check), timeout=settings()["timeout"] + 1)
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail="SQL Server diagnostics timed out") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="SQL Server diagnostics failed") from exc


@app.post("/reports/run")
async def run_report(payload: ReportRequest, _: Annotated[None, Depends(authorize)]) -> dict[str, Any]:
    config = settings()
    report = REPORTS.get(payload.report_name)
    if not report:
        raise HTTPException(status_code=422, detail=f"Unknown report: {payload.report_name}")
    days = min(payload.days, config["max_days"])
    limit = min(payload.limit, config["max_points"])
    end_date = date.today() + timedelta(days=1)
    start_date = end_date - timedelta(days=days)
    parameters = (
        (limit, payload.tenant_id, start_date, end_date)
        if report["params"] == "dated"
        else (limit, payload.tenant_id)
    )
    try:
        rows = await asyncio.wait_for(
            asyncio.to_thread(query_rows, report["sql"], parameters),
            timeout=config["timeout"] + 1,
        )
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail="SQL Server report timed out") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="SQL Server report query failed") from exc
    return {
        "report_name": payload.report_name,
        "title": report["title"],
        "chart": report["chart"],
        "period": {"start": start_date.isoformat(), "end": (end_date - timedelta(days=1)).isoformat()},
        "rows": rows,
        "total": round(sum(float(row.get("value") or 0) for row in rows), 2),
        "limits": {"days": days, "points": limit},
        "source": "sqlserver_connector",
    }
