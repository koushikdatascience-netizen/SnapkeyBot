# Railway PostgreSQL Reporting Sync

This keeps approved Madhushala reporting data available when the local POS computer is offline.

```text
Local SQL Server -> scheduled sync -> Railway PostgreSQL -> Snapkey reports
```

The sync reads only the `snapkey_*` reporting views. It excludes customer phone numbers, email addresses, card
numbers, credentials, and arbitrary POS tables.

## 1. Create Local Reporting Views

In SQL Server Management Studio, connect to `.\SQLEXPRESS` and execute:

```text
connector/create_reporting_views.sql
```

Find the company code to use as the tenant:

```sql
USE barmanager;
SELECT companycode, companyname FROM dbo.companymast;
```

## 2. Configure Railway

On the Snapkey Railway service, set:

```env
REPORT_DATABASE_URL=${{Postgres.DATABASE_URL}}
REPORT_TENANT_ID=YOUR_COMPANY_CODE
REPORT_CONNECTOR_URL=
ELEVENLABS_AGENT_ID=YOUR_ELEVENLABS_AGENT_ID
ELEVENLABS_API_KEY=YOUR_ELEVENLABS_API_KEY
```

Leave `REPORT_CONNECTOR_URL` empty so reports read from PostgreSQL.
The production live assistant is available at `/live`. ElevenLabs handles the realtime conversation, while
Snapkey client tools open bounded reports and pass the visible report insights back to the agent.

From the Railway PostgreSQL service's **Connect** tab, copy its public connection URL. Use the public URL only on
the local POS computer; Railway's private URL works only inside Railway.

## 3. Run The Initial Upload

From `D:\Snapkey Assistant` in PowerShell:

```powershell
$env:MSSQL_CONNECTION_STRING="DRIVER={ODBC Driver 18 for SQL Server};SERVER=.\SQLEXPRESS;DATABASE=barmanager;Trusted_Connection=yes;Encrypt=no;TrustServerCertificate=yes;"
$env:REPORT_SYNC_DATABASE_URL="postgresql://USER:PASSWORD@PUBLIC_HOST:PUBLIC_PORT/railway"
$env:REPORT_TENANT_ID="YOUR_COMPANY_CODE"

py -3.12 scripts/sync_sqlserver_to_postgres.py
```

The command creates the cloud reporting tables and uploads current sales, inventory, bills, payment totals,
purchases, and non-sensitive customer visit totals. Every refresh is atomic: failed uploads leave the previous
cloud data intact.

## 4. Schedule Updates

Create a Windows Task Scheduler task that runs every 10 minutes while the POS computer is online:

```powershell
powershell -ExecutionPolicy Bypass -File "D:\Snapkey Assistant\scripts\run_reporting_sync.ps1"
```

Set the three environment variables permanently for the task account, or define them in the task action before
calling the script. The dashboard remains available when the PC is off and shows the last successful sync.

## 5. Verify

The sync command prints row counts. In Railway PostgreSQL, verify:

```sql
SELECT * FROM snapkey_sync_status;
SELECT COUNT(*) FROM snapkey_sales;
SELECT COUNT(*) FROM snapkey_inventory;
```

Then sign in at `https://YOUR-RAILWAY-DOMAIN/live` and try:

```text
Show today's sales report
Show low stock items
Show payment mix as a donut chart
```

Reports remain available from the last successful sync even when the local POS computer is off.
