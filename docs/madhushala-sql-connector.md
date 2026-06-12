# Madhushala SQL Server Connector

Do not expose a shop's SQL Server port to the public internet. Install a small connector beside Madhushala POS that makes outbound HTTPS requests to Snapkey.

## Recommended flow

```text
Madhushala SQL Server
        |
Read-only connector Windows service
        |
Outbound HTTPS / VPN
        |
Snapkey Railway API
        |
Voice agent and live workspaces
```

The connector should use a dedicated SQL Server login with access only to approved reporting views and stored procedures. It should not receive unrestricted table-write permissions.

## Reporting operations

Expose named operations rather than arbitrary SQL:

```text
sales_summary
top_products
low_stock
cashier_variance
supplier_outstanding
stock_movement
daily_closing
```

Each operation maps to a reviewed stored procedure or parameterized query. Snapkey sends the operation name and validated date/shop filters; the connector returns JSON.

Example request:

```json
{
  "operation": "sales_summary",
  "shop_id": "SHOP-001",
  "from": "2026-06-01",
  "to": "2026-06-12"
}
```

Example response:

```json
{
  "total_sales": 84200,
  "cash": 24100,
  "upi": 60100,
  "transactions": 318
}
```

## Automation operations

Writes must use separate reviewed commands and require user confirmation:

```text
prepare_purchase_order
approve_stock_adjustment
create_supplier_task
publish_daily_closing
```

Never let an LLM generate and execute arbitrary SQL. Use parameterized queries, allowlisted operations, per-shop tenant checks, audit logs, request signatures, and idempotency keys.

## Connectivity choices

1. **Best for many clients:** connector Windows service makes outbound HTTPS calls and receives jobs through polling or a secure WebSocket.
2. **For managed installations:** connect Railway and the client network through Tailscale/WireGuard, then call a private connector API.
3. **For reporting only:** replicate approved reporting data to a cloud PostgreSQL warehouse on a schedule.

## Information needed before implementation

- SQL Server version and Windows/server environment
- Database schema or a sanitized backup
- Existing reporting views and stored procedures
- Shop/tenant identifier columns
- Which operations are read-only versus write operations
- Expected synchronization frequency
