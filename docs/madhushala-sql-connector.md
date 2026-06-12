# Madhushala Local SQL Server Connector

This connector lets Railway Snapkey query a Microsoft SQL Server running on a local Windows POS/server computer
without exposing SQL Server port `1433`.

```text
Railway Snapkey -> HTTPS Cloudflare Tunnel -> localhost:8090 connector -> local SQL Server
```

The connector accepts only four allowlisted, read-only reports. It never accepts raw SQL.

## 1. Prepare SQL Server

Install Microsoft ODBC Driver 18 for SQL Server on the Windows computer.

Create a read-only login in SQL Server Management Studio:

```sql
CREATE LOGIN snapkey_reports WITH PASSWORD = 'replace-with-a-long-password';
USE Madhushala;
CREATE USER snapkey_reports FOR LOGIN snapkey_reports;
```

Edit and run [create_reporting_views.sql](../connector/create_reporting_views.sql). Replace the placeholder source
tables and columns with the real Madhushala schema.

To inspect the real schema before editing the views:

```powershell
$env:MSSQL_CONNECTION_STRING="DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;DATABASE=Madhushala;Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;"
py -3.12 scripts/inspect_sqlserver_schema.py > sqlserver-schema.json
```

This reads table/column metadata only. Review `sqlserver-schema.json` and map the actual sales and inventory columns
in `connector/create_reporting_views.sql`.

## 2. Install And Start The Connector

From the project folder on the SQL Server computer:

```powershell
py -3.12 -m pip install -e ".[connector]"

$env:MSSQL_CONNECTION_STRING="DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;DATABASE=Madhushala;UID=snapkey_reports;PWD=YOUR_PASSWORD;Encrypt=yes;TrustServerCertificate=yes;"
$env:CONNECTOR_SECRET="generate-one-long-random-secret"

powershell -ExecutionPolicy Bypass -File scripts/run_sqlserver_connector.ps1
```

The connector listens only on `127.0.0.1:8090`. Test locally:

```powershell
$env:REPORT_TENANT_ID="shop-001"
$env:REPORT_CONNECTOR_SECRET=$env:CONNECTOR_SECRET
py -3.12 scripts/test_sqlserver_connector.py
```

## 3. Publish Through Cloudflare Tunnel

Install `cloudflared`, authenticate it, and create a named tunnel:

```powershell
cloudflared tunnel login
cloudflared tunnel create snapkey-reports
cloudflared tunnel route dns snapkey-reports reports.yourdomain.com
```

Create `%USERPROFILE%\.cloudflared\config.yml`:

```yaml
tunnel: YOUR_TUNNEL_ID
credentials-file: C:\Users\YOUR_USER\.cloudflared\YOUR_TUNNEL_ID.json

ingress:
  - hostname: reports.yourdomain.com
    service: http://127.0.0.1:8090
  - service: http_status:404
```

Start the tunnel:

```powershell
cloudflared tunnel run snapkey-reports
```

## 4. Configure Railway

Add:

```env
REPORT_CONNECTOR_URL=https://reports.yourdomain.com
REPORT_CONNECTOR_SECRET=the-exact-same-connector-secret
REPORT_TENANT_ID=shop-001
REPORT_MAX_DAYS=90
REPORT_MAX_POINTS=50
REPORT_QUERY_TIMEOUT_SECONDS=8
```

Leave `REPORT_DATABASE_URL` empty when using the SQL Server connector.

## 5. Verify

Sign in to Snapkey and call:

```text
GET /api/integrations/reports/diagnostics
Authorization: Bearer <Snapkey login token>
```

A ready response has:

```json
{
  "connected": true,
  "missing_views": [],
  "source": "sqlserver_connector"
}
```

For production, run both the connector and `cloudflared` as Windows services and restrict the Cloudflare hostname
with Access service tokens or network policies in addition to the connector secret.
