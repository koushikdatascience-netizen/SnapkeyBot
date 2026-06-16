# Madhushala Reporting On Supabase

This uploads only approved analytics data. The legacy ERP remains local and read-only.

```text
Madhushala SQL Server
  -> verified read-only views
  -> scheduled Python sync
  -> Supabase PostgreSQL reporting tables
  -> Snapkey voice reports and interactive charts
```

## Data Included

- Daily bill totals and average bill value
- Daily product/category sales
- Current inventory and reorder levels
- Daily purchase totals
- Daily supplier performance
- Daily accounting transaction summaries

Customer contact details, credentials, raw invoices, and unrelated ERP tables are excluded.

## 1. Create Local Reporting Views

Run this file in SQL Server Management Studio against `barmanager`:

```text
connector/create_madhushala_cloud_views.sql
```

The final three result grids should display sales, product sales, and inventory.

## 2. Get The Supabase Connection String

In Supabase:

1. Open the project.
2. Go to **Project Settings -> Database**.
3. Copy the **Session pooler** connection string.
4. Replace `[YOUR-PASSWORD]` with the database password.

Use the pooler connection string from the local Windows computer. A typical value looks like:

```text
postgresql://postgres.PROJECT_REF:PASSWORD@aws-REGION.pooler.supabase.com:5432/postgres
```

Do not expose this connection string in frontend JavaScript.

## 3. Run Initial Sync

From `D:\Snapkey Assistant`:

```powershell
$env:MSSQL_CONNECTION_STRING="DRIVER={ODBC Driver 18 for SQL Server};SERVER=.\SQLEXPRESS;DATABASE=barmanager;UID=sa;PWD=YOUR_SQL_PASSWORD;Encrypt=no;TrustServerCertificate=yes;"
$env:REPORT_SYNC_DATABASE_URL="YOUR_SUPABASE_SESSION_POOLER_CONNECTION_STRING"
$env:REPORT_TENANT_ID="2"

py -3.12 scripts\sync_sqlserver_to_postgres.py --cloud-only
```

The script automatically creates the Supabase reporting tables, enables row-level security, uploads the
verified datasets atomically, and records the upload time in `snapkey_sync_status`.

## 4. Verify In Supabase SQL Editor

```sql
select * from snapkey_sync_status where tenant_id = '2';
select * from report_sales_daily where tenant_id = '2' order by sale_date desc limit 10;
select * from report_product_sales_daily where tenant_id = '2' order by sales_amount desc limit 10;
select * from report_inventory_current where tenant_id = '2' order by stock_quantity limit 10;
```

## 5. Schedule Updates

Run every 10 to 15 minutes using Windows Task Scheduler:

```powershell
py -3.12 "D:\Snapkey Assistant\scripts\sync_sqlserver_to_postgres.py" --cloud-only
```

The local computer only needs to be online during synchronization. Snapkey can continue querying the last
successful Supabase snapshot while the local computer is offline.

## Security

- Use a dedicated SQL Server read-only login for the reporting views.
- Keep Supabase database credentials only in backend environment variables.
- Do not create public Supabase RLS policies for these tables.
- Every application query must include the authenticated user's assigned `tenant_id`.
