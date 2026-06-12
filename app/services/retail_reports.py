import asyncio
import json
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config import get_settings

REPORTS = {
    "sales_summary": {
        "title": "Sales summary",
        "chart": "bar",
        "sql": """
            SELECT DATE(sold_at) AS label, ROUND(SUM(net_amount), 2) AS value
            FROM snapkey_sales
            WHERE tenant_id = :tenant_id AND sold_at >= :start_date AND sold_at < :end_date
            GROUP BY DATE(sold_at)
            ORDER BY DATE(sold_at)
            LIMIT :limit
        """,
    },
    "top_products": {
        "title": "Top-selling products",
        "chart": "bar",
        "sql": """
            SELECT product_name AS label, ROUND(SUM(quantity), 2) AS value
            FROM snapkey_sales
            WHERE tenant_id = :tenant_id AND sold_at >= :start_date AND sold_at < :end_date
            GROUP BY product_name
            ORDER BY value DESC
            LIMIT :limit
        """,
    },
    "category_sales": {
        "title": "Sales by category",
        "chart": "bar",
        "sql": """
            SELECT category_name AS label, ROUND(SUM(net_amount), 2) AS value
            FROM snapkey_sales
            WHERE tenant_id = :tenant_id AND sold_at >= :start_date AND sold_at < :end_date
            GROUP BY category_name
            ORDER BY value DESC
            LIMIT :limit
        """,
    },
    "low_stock": {
        "title": "Low-stock products",
        "chart": "bar",
        "sql": """
            SELECT product_name AS label, ROUND(stock_quantity, 2) AS value
            FROM snapkey_inventory
            WHERE tenant_id = :tenant_id AND stock_quantity <= reorder_level
            ORDER BY stock_quantity ASC
            LIMIT :limit
        """,
    },
    "payment_mix": {
        "title": "Sales by payment method",
        "chart": "donut",
        "sql": """
            SELECT payment_method AS label, ROUND(SUM(amount), 2) AS value
            FROM snapkey_payments
            WHERE tenant_id = :tenant_id AND sold_at >= :start_date AND sold_at < :end_date
            GROUP BY payment_method ORDER BY value DESC LIMIT :limit
        """,
    },
    "hourly_sales": {
        "title": "Sales by hour",
        "chart": "bar",
        "sql": """
            SELECT CONCAT(LPAD(CAST(EXTRACT(HOUR FROM sold_at) AS VARCHAR), 2, '0'), ':00') AS label,
                   ROUND(SUM(net_amount), 2) AS value
            FROM snapkey_bills
            WHERE tenant_id = :tenant_id AND sold_at >= :start_date AND sold_at < :end_date
            GROUP BY EXTRACT(HOUR FROM sold_at) ORDER BY EXTRACT(HOUR FROM sold_at) LIMIT :limit
        """,
    },
    "average_bill": {
        "title": "Average bill value",
        "chart": "line",
        "sql": """
            SELECT DATE(sold_at) AS label, ROUND(AVG(net_amount), 2) AS value
            FROM snapkey_bills
            WHERE tenant_id = :tenant_id AND sold_at >= :start_date AND sold_at < :end_date
            GROUP BY DATE(sold_at) ORDER BY label LIMIT :limit
        """,
    },
    "purchase_trend": {
        "title": "Purchase trend",
        "chart": "line",
        "sql": """
            SELECT DATE(purchased_at) AS label, ROUND(SUM(net_amount), 2) AS value
            FROM snapkey_purchases
            WHERE tenant_id = :tenant_id AND purchased_at >= :start_date AND purchased_at < :end_date
            GROUP BY DATE(purchased_at) ORDER BY label LIMIT :limit
        """,
    },
    "stock_by_category": {
        "title": "Stock by category",
        "chart": "bar",
        "sql": """
            SELECT category_name AS label, ROUND(SUM(stock_quantity), 2) AS value
            FROM snapkey_inventory WHERE tenant_id = :tenant_id
            GROUP BY category_name ORDER BY value DESC LIMIT :limit
        """,
    },
    "customer_visits": {
        "title": "Top customers by visits",
        "chart": "bar",
        "sql": """
            SELECT customer_name AS label, ROUND(visit_count, 2) AS value
            FROM snapkey_customers WHERE tenant_id = :tenant_id
            ORDER BY visit_count DESC LIMIT :limit
        """,
    },
}

_engine: AsyncEngine | None = None


def reporting_ready() -> bool:
    settings = get_settings()
    source_ready = bool(settings.report_connector_url and settings.report_connector_secret) or bool(
        settings.report_database_url
    )
    return bool(source_ready and (settings.report_tenant_id or settings.report_tenant_map_json))


def report_tenant_for(email: str) -> str:
    settings = get_settings()
    if settings.report_tenant_map_json:
        try:
            tenant_map = json.loads(settings.report_tenant_map_json)
        except json.JSONDecodeError as exc:
            raise RuntimeError("REPORT_TENANT_MAP_JSON is invalid") from exc
        tenant_id = tenant_map.get(email.lower())
        if tenant_id:
            return str(tenant_id)
    if settings.report_tenant_id:
        return settings.report_tenant_id
    raise PermissionError("No retail reporting tenant is assigned to this user")


def report_catalog() -> list[dict[str, str]]:
    return [
        {"name": name, "title": report["title"], "chart": report["chart"]}
        for name, report in REPORTS.items()
    ]


def _report_engine() -> AsyncEngine:
    global _engine
    settings = get_settings()
    if not settings.report_database_url:
        raise RuntimeError("Retail reporting database is not configured")
    if _engine is None:
        _engine = create_async_engine(
            settings.report_database_url,
            pool_pre_ping=True,
            pool_size=3,
            max_overflow=2,
            pool_recycle=900,
        )
    return _engine


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date,)):
        return value.isoformat()
    return value


async def report_connection_diagnostics(tenant_id: str) -> dict[str, Any]:
    settings = get_settings()
    if settings.report_connector_url:
        return await _connector_request("/diagnostics", {"tenant_id": tenant_id})

    async def execute() -> dict[str, Any]:
        async with _report_engine().connect() as connection:
            await connection.execute(text("SELECT 1"))
            result = await connection.execute(
                text(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name IN (
                          'snapkey_sales', 'snapkey_inventory', 'snapkey_bills',
                          'snapkey_payments', 'snapkey_purchases', 'snapkey_customers'
                      )
                    """
                )
            )
            views = sorted(str(row[0]) for row in result.all())
            return {
                "connected": True,
                "tenant_assigned": bool(tenant_id),
                "views": views,
                "missing_views": sorted(
                    {
                        "snapkey_sales", "snapkey_inventory", "snapkey_bills",
                        "snapkey_payments", "snapkey_purchases", "snapkey_customers",
                    }
                    - set(views)
                ),
                "limits": {
                    "max_days": settings.report_max_days,
                    "max_points": settings.report_max_points,
                    "timeout_seconds": settings.report_query_timeout_seconds,
                },
            }

    try:
        return await asyncio.wait_for(execute(), timeout=settings.report_query_timeout_seconds)
    except TimeoutError as exc:
        raise TimeoutError(
            f"Database check exceeded the {settings.report_query_timeout_seconds}-second limit"
        ) from exc
    except SQLAlchemyError as exc:
        raise RuntimeError("Unable to connect to the retail reporting database") from exc


async def run_retail_report(
    report_name: str,
    *,
    tenant_id: str,
    days: int = 7,
    limit: int = 20,
) -> dict[str, Any]:
    settings = get_settings()
    report = REPORTS.get(report_name)
    if not report:
        raise ValueError(f"Unknown retail report: {report_name}")

    bounded_days = max(1, min(int(days), settings.report_max_days))
    bounded_limit = max(1, min(int(limit), settings.report_max_points))
    if settings.report_connector_url:
        return await _connector_request(
            "/reports/run",
            {
                "report_name": report_name,
                "tenant_id": tenant_id,
                "days": bounded_days,
                "limit": bounded_limit,
            },
        )
    end_date = date.today() + timedelta(days=1)
    start_date = end_date - timedelta(days=bounded_days)
    statement = text(report["sql"])
    parameters = {
        "tenant_id": tenant_id,
        "start_date": start_date,
        "end_date": end_date,
        "limit": bounded_limit,
    }

    async def execute() -> list[dict[str, Any]]:
        async with _report_engine().connect() as connection:
            result = await connection.execute(statement, parameters)
            return [
                {key: _json_value(value) for key, value in row.items()}
                for row in result.mappings().all()
            ]

    try:
        rows = await asyncio.wait_for(execute(), timeout=settings.report_query_timeout_seconds)
    except TimeoutError as exc:
        raise TimeoutError(
            f"Report exceeded the {settings.report_query_timeout_seconds}-second query limit"
        ) from exc
    except SQLAlchemyError as exc:
        raise RuntimeError("Unable to query the retail reporting database") from exc

    total = round(sum(float(row.get("value") or 0) for row in rows), 2)
    return {
        "report_name": report_name,
        "title": report["title"],
        "chart": report["chart"],
        "period": {"start": start_date.isoformat(), "end": (end_date - timedelta(days=1)).isoformat()},
        "rows": rows,
        "total": total,
        "limits": {"days": bounded_days, "points": bounded_limit},
    }


async def _connector_request(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    if not settings.report_connector_url or not settings.report_connector_secret:
        raise RuntimeError("Retail reporting connector is not fully configured")
    try:
        async with httpx.AsyncClient(timeout=settings.report_query_timeout_seconds + 3) as client:
            response = await client.post(
                f"{settings.report_connector_url.rstrip('/')}{path}",
                headers={"X-Snapkey-Connector-Secret": settings.report_connector_secret},
                json=payload,
            )
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException as exc:
        raise TimeoutError("Retail reporting connector timed out") from exc
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:300] or "Connector request failed"
        raise RuntimeError(f"Retail reporting connector rejected the request: {detail}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError("Unable to reach the retail reporting connector") from exc
