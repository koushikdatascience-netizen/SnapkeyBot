import asyncio
import json
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

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
}

_engine: AsyncEngine | None = None


def reporting_ready() -> bool:
    settings = get_settings()
    return bool(settings.report_database_url and (settings.report_tenant_id or settings.report_tenant_map_json))


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
