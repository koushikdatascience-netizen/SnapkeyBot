import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import asyncpg
import pyodbc


TABLES = {
    "snapkey_sales": (
        """
        SELECT tenant_id, CONVERT(date, sold_at) AS sold_at, product_name, category_name,
               SUM(quantity) AS quantity, SUM(net_amount) AS net_amount
        FROM dbo.snapkey_sales
        WHERE tenant_id = ?
        GROUP BY tenant_id, CONVERT(date, sold_at), product_name, category_name
        """,
        ("tenant_id", "sold_at", "product_name", "category_name", "quantity", "net_amount"),
    ),
    "snapkey_inventory": (
        """
        SELECT tenant_id, product_name, category_name, stock_quantity, reorder_level
        FROM dbo.snapkey_inventory
        WHERE tenant_id = ?
        """,
        ("tenant_id", "product_name", "category_name", "stock_quantity", "reorder_level"),
    ),
    "snapkey_bills": (
        "SELECT tenant_id, sold_at, net_amount FROM dbo.snapkey_bills WHERE tenant_id = ?",
        ("tenant_id", "sold_at", "net_amount"),
    ),
    "snapkey_payments": (
        """
        SELECT tenant_id, CONVERT(date, sold_at) AS sold_at, payment_method, SUM(amount) AS amount
        FROM dbo.snapkey_payments
        WHERE tenant_id = ?
        GROUP BY tenant_id, CONVERT(date, sold_at), payment_method
        """,
        ("tenant_id", "sold_at", "payment_method", "amount"),
    ),
    "snapkey_purchases": (
        "SELECT tenant_id, purchased_at, net_amount FROM dbo.snapkey_purchases WHERE tenant_id = ?",
        ("tenant_id", "purchased_at", "net_amount"),
    ),
    "snapkey_customers": (
        "SELECT tenant_id, customer_name, visit_count FROM dbo.snapkey_customers WHERE tenant_id = ?",
        ("tenant_id", "customer_name", "visit_count"),
    ),
}
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def postgres_url() -> str:
    value = os.environ.get("REPORT_SYNC_DATABASE_URL") or os.environ.get("DATABASE_URL", "")
    if value.startswith("postgresql+asyncpg://"):
        return value.replace("postgresql+asyncpg://", "postgresql://", 1)
    if value.startswith("postgres://"):
        return value.replace("postgres://", "postgresql://", 1)
    return value


def validate_postgres_url(value: str) -> None:
    hostname = urlparse(value).hostname or ""
    if hostname.endswith(".railway.internal"):
        raise SystemExit(
            "REPORT_SYNC_DATABASE_URL uses Railway's private .railway.internal hostname. "
            "A local Windows PC cannot reach it. In the Railway PostgreSQL service, enable "
            "Public Networking/TCP Proxy and use DATABASE_PUBLIC_URL instead. Rotate the "
            "PostgreSQL password first if it has been shared."
        )


def read_source(
    connection: pyodbc.Connection, sql: str, tenant_id: str, batch_size: int
) -> list[tuple[Any, ...]]:
    cursor = connection.cursor()
    cursor.execute(sql, tenant_id)
    rows: list[tuple[Any, ...]] = []
    while batch := cursor.fetchmany(batch_size):
        rows.extend(tuple(row) for row in batch)
    return rows


async def sync_table(
    destination: asyncpg.Connection,
    table: str,
    columns: tuple[str, ...],
    rows: list[tuple[Any, ...]],
    tenant_id: str,
) -> int:
    staging = f"_sync_{table}"
    column_list = ", ".join(columns)
    await destination.execute(f"CREATE TEMP TABLE {staging} (LIKE {table}) ON COMMIT DROP")
    if rows:
        await destination.copy_records_to_table(staging, records=rows, columns=columns)
    await destination.execute(f"DELETE FROM {table} WHERE tenant_id = $1", tenant_id)
    await destination.execute(f"INSERT INTO {table} ({column_list}) SELECT {column_list} FROM {staging}")
    return len(rows)


async def run_sync(batch_size: int) -> dict[str, int]:
    source_url = os.environ.get("MSSQL_CONNECTION_STRING", "")
    destination_url = postgres_url()
    tenant_id = os.environ.get("REPORT_TENANT_ID", "")
    if not source_url or not destination_url or not tenant_id:
        raise SystemExit(
            "Set MSSQL_CONNECTION_STRING, REPORT_SYNC_DATABASE_URL (or DATABASE_URL), and REPORT_TENANT_ID"
        )
    validate_postgres_url(destination_url)

    source = pyodbc.connect(source_url, timeout=15)
    destination = await asyncpg.connect(destination_url, timeout=20)
    try:
        ddl = (PROJECT_ROOT / "connector/create_postgres_reporting_tables.sql").read_text(
            encoding="utf-8"
        )
        await destination.execute(ddl)
        source_rows = {
            table: read_source(source, sql, tenant_id, batch_size)
            for table, (sql, _columns) in TABLES.items()
        }
        counts: dict[str, int] = {}
        async with destination.transaction():
            for table, (_sql, columns) in TABLES.items():
                counts[table] = await sync_table(
                    destination, table, columns, source_rows[table], tenant_id
                )
            await destination.execute(
                """
                INSERT INTO snapkey_sync_status (tenant_id, synced_at, row_counts)
                VALUES ($1, now(), $2::jsonb)
                ON CONFLICT (tenant_id) DO UPDATE
                SET synced_at = EXCLUDED.synced_at, row_counts = EXCLUDED.row_counts
                """,
                tenant_id,
                json.dumps(counts),
            )
        return counts
    finally:
        source.close()
        await destination.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync approved SQL Server reporting views to PostgreSQL.")
    parser.add_argument("--batch-size", type=int, default=5_000)
    args = parser.parse_args()
    counts = asyncio.run(run_sync(max(100, min(args.batch_size, 20_000))))
    print(json.dumps({"synced": True, "rows": counts}, indent=2))


if __name__ == "__main__":
    main()
