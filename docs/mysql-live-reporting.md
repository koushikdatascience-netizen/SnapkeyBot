# Madhushala MySQL Live Reporting

Snapkey live reports use short, read-only, server-aggregated queries. Raw transaction rows are never sent to the
voice agent or browser.

## Connection

Configure Railway only when it can securely reach the database through a VPN, private network, or a connector
running beside the POS database:

```env
REPORT_DATABASE_URL=mysql+asyncmy://snapkey_reports:password@private-host:3306/madhushala
REPORT_TENANT_ID=shop-001
REPORT_MAX_DAYS=90
REPORT_MAX_POINTS=50
REPORT_QUERY_TIMEOUT_SECONDS=8
```

If the username or password contains characters such as `@`, `:`, `/`, or `#`, URL-encode those characters before
placing them in `REPORT_DATABASE_URL`.

For a central database serving multiple retailers, replace `REPORT_TENANT_ID` with a server-side user mapping:

```env
REPORT_TENANT_MAP_JSON={"owner1@example.com":"shop-001","owner2@example.com":"shop-002"}
```

The voice agent cannot choose or override the tenant ID.

Do not expose MySQL port `3306` publicly. Create a dedicated MySQL user with `SELECT` permission only on the two
reporting views below.

Example read-only MySQL user:

```sql
CREATE USER 'snapkey_reports'@'%' IDENTIFIED BY 'replace-with-a-long-password';
GRANT SELECT ON madhushala.snapkey_sales TO 'snapkey_reports'@'%';
GRANT SELECT ON madhushala.snapkey_inventory TO 'snapkey_reports'@'%';
FLUSH PRIVILEGES;
```

After configuring Railway, sign in to Snapkey and call:

```text
GET /api/integrations/reports/diagnostics
Authorization: Bearer <normal Snapkey login token>
```

A ready response has `"connected": true` and an empty `"missing_views"` array. This check executes only `SELECT 1`
and checks view names; it does not scan sales data.

If the Madhushala database exists only on a shop-local Windows computer, Railway cannot reach `localhost`. Use a
private VPN such as Tailscale/WireGuard or a small outbound Snapkey connector beside the database. Do not open MySQL
port `3306` to the public internet.

## Required View Contract

Map the real Madhushala schema into these read-only views:

```sql
CREATE VIEW snapkey_sales AS
SELECT
  shop_id AS tenant_id,
  bill_datetime AS sold_at,
  item_name AS product_name,
  category_name,
  quantity,
  net_amount
FROM your_sales_items_source;

CREATE VIEW snapkey_inventory AS
SELECT
  shop_id AS tenant_id,
  item_name AS product_name,
  current_stock AS stock_quantity,
  reorder_level
FROM your_inventory_source;
```

Replace the source tables and columns with the real schema. Add indexes on the underlying sales table for
`(shop_id, bill_datetime)`, `(shop_id, item_name)`, and `(shop_id, category_name)`.

## Built-in Reports

- `sales_summary`: daily sales totals
- `top_products`: top products by quantity
- `category_sales`: sales totals by category
- `low_stock`: products at or below reorder level

All reports enforce tenant filtering, allowlisted SQL, bounded date ranges, bounded result points, and a hard query
timeout. The LLM cannot submit arbitrary SQL.

## ElevenLabs Tool

Use the existing `run_integration` client tool:

```json
{
  "tool_name": "retail_report",
  "arguments": "{\"report_name\":\"top_products\",\"days\":30,\"limit\":20}",
  "confirmed": false
}
```

Voice requests such as “show this month’s top products” are also recognized automatically by the Snapkey frontend.
